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
from agent.ultracode.schema import Finding, StageResult, dedupe_findings
from agent.ultracode.steering import Decision, decide
from agent.ultracode.planner import Plan, plan as make_plan
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

    # --- plan (work-list before fan-out) -------------------------------------
    plan = make_plan(task, decision, context="", config=cfg, agent=agent, aux_call_fn=aux_call_fn, model=model)
    caps = list(plan.caps_announced)
    if led:
        led.event("plan", {"n_subtasks": len(plan.subtasks), "delegated": plan.delegated, "rationale": plan.rationale})

    # --- find: one finder per subtask, looped-until-dry if the shape says so --
    def finder_round(round_idx: int, known: List[Finding]) -> List[Finding]:
        tasks = [
            {"goal": _finder_prompt(st.goal, context, st.context, known)}
            for st in plan.subtasks
        ]
        results = delegate_fanout(tasks, parent_agent=agent, max_children=cfg.max_children, delegate_fn=delegate_fn)
        found: List[Finding] = []
        for i, entry in enumerate(results):
            label = plan.subtasks[i % len(plan.subtasks)].goal[:48] if plan.subtasks else f"finder-{i}"
            found.extend(_parse_findings(entry if isinstance(entry, dict) else {}, f"r{round_idx}:{label}"))
        return found

    if decision.loop_until_dry:
        report = discover(finder_round, config=cfg)
        findings = report.findings
        caps.extend(report.caps_announced)
        stages = ["plan", f"discover(loop, {report.rounds_run} rounds, {report.stop_reason})"]
        if led:
            led.event("discovery", {"rounds": report.rounds_run, "fresh_per_round": report.fresh_per_round, "stop": report.stop_reason})
    else:
        findings = dedupe_findings(finder_round(0, []))
        stages = ["plan", "find"]

    if len(findings) > cfg.max_findings:
        caps.append(f"findings capped at max_findings={cfg.max_findings} (announced)")
        findings = findings[: cfg.max_findings]
    if led:
        led.stage(StageResult(stage="find", findings=findings, caps_announced=caps))

    # --- adversarially verify: independent skeptics, default-to-refuted -------
    if decision.verify and findings:
        verify_findings(findings, parent_agent=agent, config=cfg, lenses=decision.lenses, delegate_fn=delegate_fn)
        stages.append(f"verify({len(decision.lenses)} lenses, quorum {cfg.effective_quorum(len(decision.lenses))})")
        survs = _survivors(findings)
    else:
        survs = findings
    if led:
        led.stage(StageResult(stage="verify", findings=findings))

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
        task=task, mode="ultracode", answer=answer, decision=decision, plan=plan,
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
