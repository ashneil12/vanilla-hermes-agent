"""Task kinds — generalize the harness beyond code auditing to ANY task.

The ultracode loop (decompose -> fan out -> adversarially verify -> synthesize) is
general; only the PROMPTS were code-specific. This module classifies the task and
supplies kind-aware instructions for the worker (what to produce), the skeptic
(what to check), and the finding noun, so the same harness handles research,
analysis, Q&A, and code — and routes generative work to a judge-panel.
"""

from __future__ import annotations

import re


class TaskKind:
    CODE = "code"              # find bugs/vulnerabilities in code
    RESEARCH = "research"      # investigate a question; claims must be sourced + fact-checked
    ANALYSIS = "analysis"      # analyze material/data; extract evidenced findings
    QA = "qa"                  # answer a hard question; decompose into sub-answers
    GENERATIVE = "generative"  # produce an artifact (writing/design/naming) -> judge-panel
    GENERIC = "generic"


_CODE = re.compile(r"\b(bug|vulnerab|audit|security|exploit|inject|cve|code|function|class|refactor|crash|stack trace|exception)\b", re.I)
_RESEARCH = re.compile(r"\b(research|investigate|find out|sources?|fact[- ]?check|compare|what is|who|when|history of|state of|landscape|survey|cite)\b", re.I)
_GENERATIVE = re.compile(r"\b(write|draft|compose|design|name|brainstorm|generate ideas|come up with|create a|tagline|slogan|copy|essay|story|poem|plan a)\b", re.I)
_ANALYSIS = re.compile(r"\b(analy[sz]e|assess|evaluate|review|critique|break down|pros and cons|tradeoffs?|implications?|data|dataset|metrics)\b", re.I)
_QA = re.compile(r"\b(why|how (do|does|can|should)|explain|reason|decide|should (i|we)|which|recommend)\b", re.I)


def classify_kind(task: str, context: str = "") -> str:
    """Heuristic task-kind classifier (the planner refines)."""
    t = task or ""
    # code wins if there's actual code material or explicit code signals
    if _CODE.search(t) or (context and re.search(r"\bdef |class |import |function |=>|;\n", context)):
        return TaskKind.CODE
    if _GENERATIVE.search(t):
        return TaskKind.GENERATIVE
    if _RESEARCH.search(t):
        return TaskKind.RESEARCH
    if _ANALYSIS.search(t):
        return TaskKind.ANALYSIS
    if _QA.search(t):
        return TaskKind.QA
    return TaskKind.GENERIC


_NOUN = {
    TaskKind.CODE: "bug/vulnerability",
    TaskKind.RESEARCH: "claim (with source)",
    TaskKind.ANALYSIS: "finding",
    TaskKind.QA: "sub-answer/claim",
    TaskKind.GENERIC: "finding",
}


def finding_noun(kind: str) -> str:
    return _NOUN.get(kind, "finding")


_WORKER = {
    TaskKind.CODE: (
        "Find REAL, locatable bugs/vulnerabilities. Trace untrusted input to dangerous sinks; check "
        "cross-branch consistency, TOCTOU, missing checks. locator = file:line."
    ),
    TaskKind.RESEARCH: (
        "Investigate the sub-question and report FACTUAL CLAIMS that answer it. Every claim must carry the "
        "specific source/evidence it rests on. Do not state anything you cannot support. locator = the source."
    ),
    TaskKind.ANALYSIS: (
        "Analyze the material and report concrete, evidenced findings/insights — not generic observations. "
        "Each finding must point to what in the material supports it. locator = where in the material."
    ),
    TaskKind.QA: (
        "Produce the key sub-answers/claims needed to answer the question rigorously, each with its "
        "justification/reasoning. locator = the basis for the claim."
    ),
    TaskKind.GENERIC: (
        "Produce concrete, specific, supported findings for this sub-task. Each must be justifiable. "
        "locator = the basis/evidence."
    ),
}


def worker_instruction(kind: str) -> str:
    return _WORKER.get(kind, _WORKER[TaskKind.GENERIC])


_SKEPTIC = {
    TaskKind.CODE: "Does this bug actually hold? State the mechanism / data-flow. If you cannot, refute it.",
    TaskKind.RESEARCH: "Is this claim ACCURATE and genuinely supported by its cited source? Beware citogenesis (sources that copied each other). If unsupported or wrong, refute it.",
    TaskKind.ANALYSIS: "Is this finding actually warranted by the material, or an overreach / unsupported inference? If unsupported, refute it.",
    TaskKind.QA: "Is this sub-answer correct and its reasoning sound? Check the logic end-to-end. If the reasoning breaks, refute it.",
    TaskKind.GENERIC: "Is this claim true and supported by a stated mechanism/evidence? If not, refute it.",
}


def skeptic_instruction(kind: str) -> str:
    return _SKEPTIC.get(kind, _SKEPTIC[TaskKind.GENERIC])
