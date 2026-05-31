"""Adversarial verification — the cognitive core, and the thing no upstream PR has.

The stance, straight from the doctrine: for each load-bearing finding, spawn K
*independent* skeptics, each looking through a DIFFERENT failure-lens, each
instructed to REFUTE and to default the verdict to ``refuted`` under uncertainty.
A finding survives only on a quorum of confirmations. Two refinements the
distillation insisted on:

  * KILL THE KILLER — a refutation must itself state a mechanism; a skeptic that
    says "looks wrong" without a reason is as suspect as a finder that says
    "looks fine". This protects a correct front-runner from a miscalibrated kill.
  * REPORTS ARE TESTIMONY, NOT FACT — a skeptic that asserts a verdict with no
    rationale/evidence is downgraded to ``refuted`` (uncertain), because the most
    dangerous unaudited input is the orchestrator believing its own workers.

Concurrency is a SIBLING delegate fan-out (one subagent per finding×lens), never
threaded ``call_llm`` — see CONTRACTS.md §2 (call_llm's routing globals are not
thread-safe) and §1 (verifiers as siblings dodge the depth=1 nesting cap).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from agent.ultracode.adapters import delegate_fanout, extract_json
from agent.ultracode.config import UltracodeConfig
from agent.ultracode.schema import Finding, Verdict, VerifyLens, VerifierVote

_LENS_BRIEF = {
    VerifyLens.CORRECTNESS: "Does the logic actually hold? State the causal chain end to end. If you cannot, it is refuted.",
    VerifyLens.SECURITY: "Is this exploitable / unsafe in the way claimed, or does the claim overstate/understate the risk? Reachability matters.",
    VerifyLens.REPRODUCES: "Does this actually reproduce / is the evidence real? Would the cited fact survive someone re-running it? Unreproducible => refuted.",
    VerifyLens.COMPLETENESS: "Does the claim's explanation predict EXACTLY the observed set — no unexplained survivors, no unexplained collateral?",
    VerifyLens.PERFORMANCE: "Is the measurement valid (mean vs p99, warm vs cold, within noise)? A within-noise delta is refuted.",
    VerifyLens.STYLE: "Is this a real defect or a cosmetic nit dressed up as one? Demote cosmetics.",
}


def _skeptic_prompt(finding: Finding, lens: VerifyLens, context: str = "") -> str:
    material = f"\nMATERIAL TO CHECK THE CLAIM AGAINST (ground truth — read it, do not guess):\n{context}\n" if context else ""
    return (
        f"You are an adversarial verifier. Your job is to REFUTE the claim below, not to confirm it.\n"
        f"LENS: {lens.value} — {_LENS_BRIEF.get(lens, 'Attack the claim on its merits.')}\n"
        f"{material}\n"
        f"CLAIM: {finding.claim}\n"
        f"EVIDENCE OFFERED: {finding.evidence or '(none given)'}\n"
        f"LOCATOR: {finding.locator or '(none)'}\n\n"
        "Rules:\n"
        "1. DEFAULT TO REFUTED. If you cannot establish the claim holds with a stated mechanism, your verdict is 'refuted'.\n"
        "2. KILL THE KILLER: if you refute, you must state the MECHANISM of the refutation — a bare 'seems wrong' is not allowed.\n"
        "3. Do not trust the offered evidence at face value; check it against ground truth where you can (read the locator, reason about the mechanism). Reasoning is not evidence — prefer to actually verify.\n"
        "4. Verdict 'confirmed' only if the claim holds for a stated, checkable reason. 'partial' if it holds in a narrowed form.\n\n"
        'Reply with ONLY a JSON object: {"verdict": "confirmed"|"partial"|"refuted", "rationale": "<mechanism, 1-3 sentences>"}'
    )


def _vote_from_result(entry: Dict[str, Any], lens: VerifyLens) -> VerifierVote:
    """Parse one skeptic's delegate-result entry into a vote.

    Testimony discipline: a non-completed task, an unparseable reply, or a verdict
    asserted with no rationale all collapse to REFUTED (uncertain), never silently
    to 'confirmed'."""
    if not isinstance(entry, dict) or entry.get("status") != "completed":
        return VerifierVote(lens, Verdict.REFUTED, rationale="skeptic did not complete; treated as unverified").validate()
    parsed = extract_json(entry.get("summary") or "")
    if not isinstance(parsed, dict) or "verdict" not in parsed:
        return VerifierVote(lens, Verdict.REFUTED, rationale="skeptic reply unparseable; treated as unverified").validate()
    raw_verdict = str(parsed.get("verdict", "")).strip().lower()
    rationale = str(parsed.get("rationale", "")).strip()
    try:
        verdict = Verdict(raw_verdict)
    except ValueError:
        return VerifierVote(lens, Verdict.REFUTED, rationale=f"unknown verdict {raw_verdict!r}; treated as unverified").validate()
    # Kill-the-killer / testimony: a confirm or kill with no stated mechanism is not trustworthy.
    if verdict in (Verdict.CONFIRMED, Verdict.REFUTED) and not rationale:
        return VerifierVote(lens, Verdict.REFUTED, rationale="verdict asserted with no mechanism; treated as unverified").validate()
    return VerifierVote(lens, verdict, rationale=rationale).validate()


def verify_findings(
    findings: List[Finding],
    *,
    context: str = "",
    parent_agent: Any = None,
    config: Optional[UltracodeConfig] = None,
    lenses: Optional[List[VerifyLens]] = None,
    delegate_fn: Optional[Callable[..., str]] = None,
    toolsets: Optional[List[str]] = None,
) -> List[Finding]:
    """Run the skeptic pool over ``findings`` and annotate each with votes,
    aggregate verdict, and ``survived``.

    Returns the SAME Finding objects, mutated with .votes/.verdict/.survived.
    A finding survives iff confirmed-votes >= quorum (majority by default).
    """
    cfg = config or UltracodeConfig()
    lenses = lenses or cfg.verify_lenses
    if not findings or not lenses:
        for f in findings:
            f.survived = True if not lenses else f.survived
        return findings

    n_lenses = len(lenses)
    # Build one sibling subagent task per (finding, lens), in a stable order.
    tasks: List[Dict[str, Any]] = []
    for f in findings:
        for lens in lenses:
            t: Dict[str, Any] = {"goal": _skeptic_prompt(f, lens, context)}
            if toolsets is not None:
                t["toolsets"] = list(toolsets)
            tasks.append(t)

    results = delegate_fanout(
        tasks,
        parent_agent=parent_agent,
        role="leaf",
        max_children=cfg.max_children,
        delegate_fn=delegate_fn,
    )
    # delegate_fanout preserves global submission order, so result i maps to
    # (finding i // n_lenses, lens i % n_lenses).
    by_index: Dict[int, Dict[str, Any]] = {}
    for entry in results:
        if isinstance(entry, dict):
            by_index[int(entry.get("task_index", len(by_index)))] = entry

    quorum = cfg.effective_quorum(n_lenses)
    for fi, finding in enumerate(findings):
        votes: List[VerifierVote] = []
        for li, lens in enumerate(lenses):
            entry = by_index.get(fi * n_lenses + li, {})
            votes.append(_vote_from_result(entry, lens))
        finding.votes = votes
        confirmed = sum(1 for v in votes if v.verdict == Verdict.CONFIRMED)
        refuted = sum(1 for v in votes if v.verdict == Verdict.REFUTED)
        finding.survived = confirmed >= quorum
        # aggregate verdict: survival => confirmed; clear majority refuted => refuted; else partial
        if finding.survived:
            finding.verdict = Verdict.CONFIRMED
        elif refuted > n_lenses - quorum:
            finding.verdict = Verdict.REFUTED
        else:
            finding.verdict = Verdict.PARTIAL
        finding.validate()
    return findings


def survivors(findings: List[Finding]) -> List[Finding]:
    """The findings that survived adversarial verification."""
    return [f for f in findings if f.survived]
