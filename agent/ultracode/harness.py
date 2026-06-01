"""harness.py — the ultracode run() entry. Steer -> plan -> find(loop) -> verify
-> critic -> synthesize, composing every module into one deterministic loop.

This is what the benchmark drives. Two DI seams (``delegate_fn`` for the parallel
finder/skeptic fan-out, ``aux_call_fn`` for the tools-off plan/critic/synthesize
calls) let the whole thing run against ANY backend — the real Hermes runtime, or
the DeepSeek client the benchmark injects, or fakes in tests.

The structure IS the value: a weak model wrapped in decompose -> fan-out ->
adversarially-verify -> loop-until-dry -> synthesize should beat the same weak
model answering in one shot — IF the instructions are operational, not lazy. The
benchmark exists to prove that, and to expose laziness the moment the weak model
finds the gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from agent.ultracode.adapters import aux_call, delegate_fanout, extract_json, runtime_from_agent
from agent.ultracode.config import UltracodeConfig
from agent.ultracode.critic import completeness_critic
from agent.ultracode.discovery import discover
from agent.ultracode.ledger import RunLedger
from agent.ultracode.schema import Finding, StageResult, dedupe_findings, reconcile_findings
from agent.ultracode.steering import Decision, decide
from agent.ultracode.planner import Plan, plan as make_plan, replan_for_gaps
from agent.ultracode.triage import assess
from agent.ultracode.verify import survivors as _survivors, verify_findings


@dataclass
class UltracodeResult:
    task: str
    mode: str  # "solo" | "ultracode"
    answer: str = ""
    decision: Optional[Decision] = None
    plan: Optional[Plan] = None
    findings: List[Finding] = field(default_factory=list)
    survivors: List[Finding] = field(default_factory=list)
    caps_announced: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "task": self.task[:120],
            "mode": self.mode,
            "n_findings": len(self.findings),
            "n_survivors": len(self.survivors),
            "stages": self.stages,
            "caps": self.caps_announced,
        }


def _finder_prompt(goal: str, context: str, sub_context: str, avoid: List[Finding]) -> str:
    avoid_block = ""
    if avoid:
        listed = "\n".join(f"- {f.claim} ({f.locator})" for f in avoid[:40])
        avoid_block = f"\nALREADY FOUND (do NOT repeat these; find only NEW, distinct issues):\n{listed}\n"
    return (
        f"You are an investigator. MANDATE: {goal}\n"
        f"{('FOCUS: ' + sub_context + chr(10)) if sub_context else ''}"
        f"\nMATERIAL:\n{context}\n"
        f"{avoid_block}\n"
        "Report ONLY concrete, specific, locatable findings — no speculation, no padding. "
        "If you assert something, you must be able to point to exactly where.\n"
        'Reply with ONLY JSON: {"findings":[{"claim":"<specific>","locator":"<file:line or section>",'
        '"evidence":"<why it is true>","severity":"info|low|medium|high|critical"}]}. '
        'Return {"findings":[]} if there is genuinely nothing.'
    )


def _parse_findings(entry: dict, source_label: str) -> List[Finding]:
    if not isinstance(entry, dict) or entry.get("status") != "completed":
        return []
    parsed = extract_json(entry.get("summary") or "")
    items = parsed.get("findings", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
    out: List[Finding] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("claim", "")).strip():
            try:
                out.append(
                    Finding(
                        claim=str(it["claim"]).strip(),
                        locator=str(it.get("locator", "")).strip(),
                        evidence=str(it.get("evidence", "")).strip(),
                        severity=str(it.get("severity", "info")).strip() or "info",
                        source_label=source_label,
                    ).validate()
                )
            except ValueError:
                continue
    return out


def _solo_audit(task: str, context: str, *, model, rt, aux_call_fn):
    """A single thorough pass — the disciplined default the discernment gate
    decides whether to escalate beyond. Returns (findings, answer)."""
    text = aux_call(
        [{"role": "system", "content": "You are an expert auditor. Do a thorough single-pass analysis. "
          "Be specific and locatable; do not pad with speculation."},
         {"role": "user", "content": f"{task}\n\nMATERIAL:\n{context}\n\n"
          'Reply with ONLY JSON: {"findings":[{"claim":"<specific>","locator":"<line/section>",'
          '"evidence":"<why>","severity":"info|low|medium|high|critical"}], "answer":"<lead-first summary>"}'}],
        model=model, temperature=0.3, max_tokens=4000, main_runtime=rt, call_fn=aux_call_fn,
    )
    parsed = extract_json(text)
    items = parsed.get("findings", []) if isinstance(parsed, dict) else []
    findings: List[Finding] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("claim", "")).strip():
            try:
                findings.append(Finding(
                    claim=str(it["claim"]).strip(), locator=str(it.get("locator", "")).strip(),
                    evidence=str(it.get("evidence", "")).strip(),
                    severity=str(it.get("severity", "info")).strip() or "info", source_label="solo",
                ).validate())
            except ValueError:
                continue
    answer = (parsed.get("answer") if isinstance(parsed, dict) else None) or (text if isinstance(text, str) else "")
    return findings, answer


def _solo_summary(findings: List[Finding], answer: str) -> str:
    fs = "\n".join(f"- [{f.severity}] {f.claim} ({f.locator})" for f in findings) or "(no findings)"
    return f"{answer}\n\nFINDINGS ({len(findings)}):\n{fs}"


def run(
    task: str,
    *,
    context: str = "",
    agent: Any = None,
    delegate_fn: Optional[Callable[..., str]] = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    config: Optional[UltracodeConfig] = None,
    model: Optional[str] = None,
    run_id: str = "ultracode",
    force_orchestrate: Optional[bool] = None,
    enable_ledger: bool = True,
    ledger_path: Optional[str] = None,
) -> UltracodeResult:
    cfg = config or UltracodeConfig()
    led = RunLedger(run_id, path=ledger_path) if enable_ledger else None
    rt = runtime_from_agent(agent)

    decision = decide(task, cfg, force_orchestrate=force_orchestrate)
    if led:
        led.event("decision", {"orchestrate": decision.orchestrate, "shape": decision.shape.value, "reason": decision.reason})

    # --- restraint: stay solo unless a real signal says otherwise -------------
    if not decision.orchestrate:
        answer = aux_call(
            [
                {"role": "system", "content": "Answer the task directly, concisely, and correctly."},
                {"role": "user", "content": f"{task}\n\n{context}".strip()},
            ],
            model=model, temperature=0.3, max_tokens=2000, main_runtime=rt, call_fn=aux_call_fn,
        )
        res = UltracodeResult(task=task, mode="solo", answer=answer, decision=decision, stages=["solo"])
        if led:
            led.event("done", res.summary())
        return res

    # --- DISCERNMENT: choose DEPTH — solo / light-ensemble / full ------------
    # The recall fix: "not full" still ENSEMBLES (solo union a finder wave) so
    # recall >= any single pass — never the bare-solo single-call variance that
    # dipped recall before. Bare-solo is reserved for trivial turns (handled
    # above). Full adds loop-until-dry. Escalate to full only when triage earns it.
    seed_findings: List[Finding] = []
    pre_stages: List[str] = []
    light = False
    if cfg.discernment and force_orchestrate is not True:
        solo_findings, solo_answer = _solo_audit(task, context, model=model, rt=rt, aux_call_fn=aux_call_fn)
        tv = assess(task, _solo_summary(solo_findings, solo_answer), context_size=len(context),
                    aux_call_fn=aux_call_fn, agent=agent, model=model)
        if led:
            led.event("triage", {"orchestrate": tv.orchestrate, "confidence": tv.confidence,
                                  "stakes": tv.stakes, "gaps": tv.gaps, "reason": tv.reason})
        seed_findings = solo_findings   # always build ON the solo pass (union -> recall)
        light = not tv.orchestrate      # not full -> LIGHT ensemble (one finder wave, no loop)
        pre_stages = ["solo-audit", "triage:" + ("light" if light else "escalate")]

    # --- plan (work-list before fan-out) -------------------------------------
    plan = make_plan(task, decision, context="", config=cfg, agent=agent, aux_call_fn=aux_call_fn, model=model)
    caps = list(plan.caps_announced)
    if seed_findings:
        caps.append(f"discernment: escalated, seeded orchestration with {len(seed_findings)} solo finding(s)")
    if led:
        led.event("plan", {"n_subtasks": len(plan.subtasks), "delegated": plan.delegated, "rationale": plan.rationale})

    # --- find: one finder per subtask, looped-until-dry if the shape says so --
    def finder_round(round_idx: int, known: List[Finding]) -> List[Finding]:
        known = list(seed_findings) + list(known)  # finders always see the solo pass -> find NEW
        if round_idx == 0 or not cfg.reactive_replan:
            subtasks = plan.subtasks
        else:
            # emergent decomposition: re-DERIVE targeted subtasks from findings-so-far,
            # rather than re-running the same finders. The work-list is a living object.
            summaries = [f"{f.claim} ({f.locator})" for f in known]
            subtasks = replan_for_gaps(task, summaries, context=context, max_subtasks=cfg.max_finders,
                                       aux_call_fn=aux_call_fn, agent=agent, model=model)
            if not subtasks:
                return []  # planner declares the surface exhausted -> contributes to dry
        tasks = [{"goal": _finder_prompt(st.goal, context, st.context, known)} for st in subtasks]
        results = delegate_fanout(tasks, parent_agent=agent, max_children=cfg.max_children,
                                  concurrency=cfg.concurrency, delegate_fn=delegate_fn)
        found: List[Finding] = []
        for i, entry in enumerate(results):
            label = subtasks[i % len(subtasks)].goal[:48] if subtasks else f"finder-{i}"
            found.extend(_parse_findings(entry if isinstance(entry, dict) else {}, f"r{round_idx}:{label}"))
        return found

    effective_loop = decision.loop_until_dry and not light  # light = single wave, no loop
    if effective_loop:
        report = discover(finder_round, config=cfg, seen_keys={f.dedup_key() for f in seed_findings})
        findings = dedupe_findings(seed_findings + report.findings)
        caps.extend(report.caps_announced)
        stages = pre_stages + ["plan", f"discover(loop, {report.rounds_run} rounds, {report.stop_reason})"]
        if led:
            led.event("discovery", {"rounds": report.rounds_run, "fresh_per_round": report.fresh_per_round, "stop": report.stop_reason})
    else:
        # light/non-loop: solo UNION one finder wave -> recall >= any single pass
        findings = dedupe_findings(seed_findings + finder_round(0, []))
        stages = pre_stages + ["plan", "find(light)" if light else "find"]

    # root-cause reconciliation: collapse near-duplicate findings (over-generation)
    if cfg.reconcile:
        before = len(findings)
        findings = reconcile_findings(findings)
        if before != len(findings):
            caps.append(f"reconciled {before} -> {len(findings)} findings (merged near-duplicates)")

    if len(findings) > cfg.max_findings:
        caps.append(f"findings capped at max_findings={cfg.max_findings} (announced)")
        findings = findings[: cfg.max_findings]
    if led:
        led.stage(StageResult(stage="find", findings=findings, caps_announced=caps))

    # --- adversarially verify: independent skeptics, default-to-refuted -------
    if decision.verify and findings:
        verify_findings(findings, context=context, parent_agent=agent, config=cfg, lenses=decision.lenses,
                        delegate_fn=delegate_fn, concurrency=cfg.concurrency)
        stages.append(f"verify({len(decision.lenses)} lenses, quorum {cfg.effective_quorum(len(decision.lenses))})")
        survs = _survivors(findings)
    else:
        survs = findings
    if led:
        led.stage(StageResult(stage="verify", findings=findings))

    # --- ground-truth-once: RUN a repro to confirm survivors (opt-in) --------
    if cfg.execution_verify and survs and context:
        from agent.ultracode.groundtruth import ground_truth_pass
        n_confirmed = ground_truth_pass(survs, context, aux_call_fn=aux_call_fn, agent=agent, model=model)
        stages.append(f"ground-truth(ran repros; {n_confirmed} confirmed by execution)")
        if led:
            led.event("ground_truth", {"confirmed_by_execution": n_confirmed, "checked": len(survs)})

    # --- completeness critic (gaps surfaced, never silently dropped) ---------
    crit = completeness_critic(task, findings, caps_announced=caps, agent=agent, aux_call_fn=aux_call_fn, model=model)
    if crit.gaps:
        caps.append(f"completeness critic flagged {len(crit.gaps)} gap(s): {'; '.join(crit.gaps[:3])}")
    stages.append("critic")
    if led:
        led.event("critic", {"gaps": crit.gaps, "coverage_note": crit.coverage_note, "independent": crit.independent})

    # --- synthesize (solo, non-delegable; lead with load-bearing; keep dissent) ---
    answer = _synthesize(task, survs, findings, crit_note=crit.coverage_note, model=model, rt=rt, aux_call_fn=aux_call_fn)
    stages.append("synthesize")

    res = UltracodeResult(
        task=task, mode=("discerned-light" if light else "ultracode"), answer=answer, decision=decision, plan=plan,
        findings=findings, survivors=survs, caps_announced=caps, stages=stages,
    )
    if led:
        led.event("done", res.summary())
    return res


def _synthesize(task, survivors, all_findings, *, crit_note, model, rt, aux_call_fn) -> str:
    refuted = [f for f in all_findings if f not in survivors]
    surv_block = "\n".join(
        f"- [{f.severity}] {f.claim} ({f.locator}) — survived {sum(1 for v in f.votes if v.verdict.value=='confirmed')}/{len(f.votes)} skeptics"
        for f in survivors
    ) or "(no findings survived verification)"
    dissent = "\n".join(f"- {f.claim} ({f.locator})" for f in refuted[:10]) or "(none)"
    user = (
        f"TASK:\n{task}\n\n"
        f"VERIFIED FINDINGS (survived adversarial verification):\n{surv_block}\n\n"
        f"REFUTED/UNVERIFIED (do not present as fact; mention only if load-bearing):\n{dissent}\n\n"
        f"COMPLETENESS NOTE: {crit_note or '(none)'}\n\n"
        "Write the final answer to the task. Lead with the single most load-bearing result. "
        "Present only verified findings as fact; clearly hedge anything unverified. "
        "If a refuted item is the strongest objection to your conclusion, surface it as a minority report. "
        "Be concrete and ranked; do not pad."
    )
    return aux_call(
        [{"role": "system", "content": "You are the synthesizer. Ranked, lead-first, calibrated, no padding."},
         {"role": "user", "content": user}],
        model=model, temperature=0.3, max_tokens=2500, main_runtime=rt, call_fn=aux_call_fn,
    )
