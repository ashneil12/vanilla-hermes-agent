"""planner.py — PLAN(tools-off) -> subtasks, with the scale-to-the-ask gate.

A bounded, tools-off LLM call turns a task into a small set of orthogonal
subtasks (the work-list). Shape adopted from upstream PR #35978's
PLAN->fan-out->SYNTHESIZE split, with the fixes the critique demanded: a real
JSON extractor with repair (not greedy regex), an ANNOUNCED cap (not a silent
[:8]), and a scale-DOWN gate (a single trivial subtask -> fall back to solo).

The planner is told to decompose by the PROBLEM-NATIVE axis (hypothesis / lens /
region), never by the surface unit (file) — the doctrine's cardinal rule —
because a weak model will default to by-file unless told otherwise. That
instruction is the difference between lazy and real, and it is exactly what a
weaker model exposes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from agent.ultracode.adapters import aux_call, extract_json, runtime_from_agent
from agent.ultracode.config import UltracodeConfig
from agent.ultracode.schema import SubtaskSpec
from agent.ultracode.steering import Decision


@dataclass
class Plan:
    subtasks: List[SubtaskSpec] = field(default_factory=list)
    rationale: str = ""
    delegated: bool = True  # False => scale-down gate fired, run solo
    caps_announced: List[str] = field(default_factory=list)


_PLAN_SYSTEM = (
    "You are the PLANNER for an exhaustive investigation harness. You do not do the work; "
    "you cut it into a SMALL set of orthogonal, independently-runnable subtasks. "
    "CARDINAL RULE: decompose by the PROBLEM-NATIVE axis — by hypothesis, by failure-lens, by "
    "region-of-concern, by claim — NEVER by the obvious surface unit (one subtask per file). "
    "Surface-axis cuts produce locally-correct, jointly-useless pieces. Each subtask must be a "
    "self-contained mandate a fresh worker can execute knowing nothing else. If the task is small "
    "enough for one focused pass, say so (one subtask) rather than manufacturing parallelism."
)


def plan(
    task: str,
    decision: Decision,
    *,
    context: str = "",
    config: Optional[UltracodeConfig] = None,
    agent: Any = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    model: Optional[str] = None,
) -> Plan:
    """Decompose ``task`` into orthogonal subtasks via a tools-off LLM call."""
    cfg = config or UltracodeConfig()
    max_subtasks = max(1, decision.n_finders)

    user = (
        f"TASK:\n{task}\n\n"
        f"{('CONTEXT:' + chr(10) + context + chr(10) + chr(10)) if context else ''}"
        f"Decomposition shape hint: {decision.shape.value}. "
        f"Produce AT MOST {max_subtasks} subtasks along the problem-native axis.\n\n"
        'Reply with ONLY JSON: {"rationale": "<why this axis>", '
        '"subtasks": [{"goal": "<self-contained mandate>", "context": "<what the worker needs>"}, ...]}. '
        "If one focused pass suffices, return exactly one subtask."
    )
    messages = [{"role": "system", "content": _PLAN_SYSTEM}, {"role": "user", "content": user}]

    try:
        text = aux_call(
            messages,
            model=model,
            temperature=0.2,
            max_tokens=1500,
            main_runtime=runtime_from_agent(agent),
            call_fn=aux_call_fn,
        )
    except Exception as exc:
        # planner failure -> degrade to a single solo subtask (the whole task)
        return Plan(
            subtasks=[SubtaskSpec(goal=task, context=context).validate()],
            rationale=f"planner unavailable ({exc}); running whole task as one pass",
            delegated=False,
            caps_announced=["planner unavailable; degraded to solo"],
        )

    parsed = extract_json(text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("subtasks"), list) or not parsed["subtasks"]:
        return Plan(
            subtasks=[SubtaskSpec(goal=task, context=context).validate()],
            rationale="planner reply unparseable; running whole task as one pass",
            delegated=False,
            caps_announced=["planner reply unparseable; degraded to solo"],
        )

    raw = parsed["subtasks"]
    caps: List[str] = []
    if len(raw) > max_subtasks:
        caps.append(f"planner returned {len(raw)} subtasks; capped to {max_subtasks} (announced, not silent)")
        raw = raw[:max_subtasks]

    subtasks: List[SubtaskSpec] = []
    for item in raw:
        if isinstance(item, dict) and str(item.get("goal", "")).strip():
            subtasks.append(
                SubtaskSpec(goal=str(item["goal"]).strip(), context=str(item.get("context", "")).strip()).validate()
            )
    if not subtasks:
        subtasks = [SubtaskSpec(goal=task, context=context).validate()]

    # scale-to-the-ask DOWN gate: a single subtask means orchestration buys nothing.
    delegated = len(subtasks) > 1
    return Plan(
        subtasks=subtasks,
        rationale=str(parsed.get("rationale", "")).strip(),
        delegated=delegated,
        caps_announced=caps,
    )


_REPLAN_SYSTEM = (
    "You are RE-PLANNING a live investigation. Given what has ALREADY been found, your job is to find "
    "what is STILL MISSING — areas, hypotheses, or bug-classes not yet investigated. Emit NEW, targeted "
    "subtasks that probe the uncovered ground. Do NOT repeat what's already found. If you genuinely "
    "believe the surface is exhausted, return an empty list — that is how the loop knows it is dry."
)


def replan_for_gaps(
    task: str,
    found_summaries: List[str],
    *,
    context: str = "",
    gaps: Optional[List[str]] = None,
    max_subtasks: int = 3,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    agent: Any = None,
    model: Optional[str] = None,
) -> List[SubtaskSpec]:
    """Emergent decomposition: given findings-so-far (and optional critic gaps),
    generate NEW targeted subtasks for the next discovery round — the work-list as
    a living object, re-derived from evidence rather than re-run verbatim."""
    found = "\n".join(f"- {s}" for s in found_summaries[:60]) or "(nothing found yet)"
    gap_block = ("\nKNOWN GAPS to target:\n" + "\n".join(f"- {g}" for g in gaps[:10])) if gaps else ""
    user = (
        f"TASK:\n{task}\n\n"
        f"{('MATERIAL:' + chr(10) + context + chr(10) + chr(10)) if context else ''}"
        f"ALREADY FOUND:\n{found}\n{gap_block}\n\n"
        f"Produce up to {max_subtasks} NEW subtasks that investigate what is still uncovered.\n"
        'Reply with ONLY JSON: {"subtasks":[{"goal":"<new targeted mandate>","context":"<what to focus on>"}]}. '
        "Empty subtasks list means the surface is exhausted."
    )
    try:
        text = aux_call(
            [{"role": "system", "content": _REPLAN_SYSTEM}, {"role": "user", "content": user}],
            model=model, temperature=0.3, max_tokens=1200,
            main_runtime=runtime_from_agent(agent), call_fn=aux_call_fn,
        )
    except Exception:
        return []
    parsed = extract_json(text)
    items = parsed.get("subtasks", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
    out: List[SubtaskSpec] = []
    for item in (items or [])[:max_subtasks]:
        if isinstance(item, dict) and str(item.get("goal", "")).strip():
            out.append(SubtaskSpec(goal=str(item["goal"]).strip(), context=str(item.get("context", "")).strip()).validate())
    return out
