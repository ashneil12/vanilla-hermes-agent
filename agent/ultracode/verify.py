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

    A vote only COUNTS (as a confirm or a kill) if it is a completed, parseable
    verdict WITH a stated mechanism — this enforces both 'reports are testimony'
    (non-completion / garble = UNKNOWN) and 'kill-the-killer' (a refutation must
    state its mechanism). Everything that doesn't count becomes PARTIAL = ABSTAIN:
    it neither confirms nor kills, so an UNKNOWN can't silently destroy a true
    finding (the asymmetric-rejection failure the doctrine warned about)."""
    def abstain(note: str) -> VerifierVote:
        return VerifierVote(lens, Verdict.PARTIAL, rationale=f"abstain: {note}").validate()

    if not isinstance(entry, dict) or entry.get("status") != "completed":
        return abstain("skeptic did not complete (UNKNOWN, not a kill)")
    parsed = extract_json(entry.get("summary") or "")
    if not isinstance(parsed, dict) or "verdict" not in parsed:
        return abstain("skeptic reply unparseable")
    raw_verdict = str(parsed.get("verdict", "")).strip().lower()
    rationale = str(parsed.get("rationale", "")).strip()
    try:
        verdict = Verdict(raw_verdict)
    except ValueError:
        return abstain(f"unknown verdict {raw_verdict!r}")
    # a confirm or a kill with no mechanism does not count — it abstains.
    if verdict in (Verdict.CONFIRMED, Verdict.REFUTED) and not rationale:
        return abstain("verdict asserted with no mechanism")
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
    survival_mode: str = "defend",
) -> List[Finding]:
    """survival_mode:
    - "defend" (default, for FINDINGS that carry their own evidence): a finding
      survives UNLESS a quorum of skeptics refutes it WITH a mechanism. Protects
      true positives from miscalibrated kills (the doctrine's symmetric burden).
    - "prove" (for bare CLAIMS that carry no evidence): a claim survives ONLY IF a
      quorum of skeptics confirms it. Catches subtly-false claims a single pass
      would accept."""
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
        votes = [_vote_from_result(by_index.get(fi * n_lenses + li, {}), lens) for li, lens in enumerate(lenses)]
        finding.votes = votes
        # only mechanism-backed verdicts count (abstains are PARTIAL, see _vote_from_result)
        confirms = sum(1 for v in votes if v.verdict == Verdict.CONFIRMED)
        kills = sum(1 for v in votes if v.verdict == Verdict.REFUTED)
        if survival_mode == "prove":
            finding.survived = confirms >= quorum
            finding.verdict = Verdict.CONFIRMED if finding.survived else Verdict.REFUTED
        else:  # "defend"
            finding.survived = kills < quorum
            if not finding.survived:
                finding.verdict = Verdict.REFUTED
            elif confirms >= 1:
                finding.verdict = Verdict.CONFIRMED
            else:
                finding.verdict = Verdict.PARTIAL  # survived but unverified — report with caveat
        finding.validate()
    return findings


def survivors(findings: List[Finding]) -> List[Finding]:
    """The findings that survived adversarial verification."""
    return [f for f in findings if f.survived]
