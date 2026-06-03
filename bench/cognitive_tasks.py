"""Cognitively-hard benchmark tasks with OBJECTIVE ground truth.

Auto-generated across 10 reasoning categories and independently verified (each answer
re-derived from scratch, code actually executed) before inclusion. The point of this bank
is to bear hard on the COGNITIVE side — where a weaker model's reasoning breaks down — with
answers that are determinable, not opinion, so Opus and DeepSeek+ultracode are scored the
same objective way.

Scoring: a solver's final answer is CORRECT if it matches any `signatures` variant — an
AND-list of lowercased keywords specific enough to reject near-misses (the verifier tuned them).
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CogTask:
    id: str
    category: str
    prompt: str
    answer: str                       # the single correct final answer (reference)
    difficulty: str                   # hard | very-hard | brutal
    signatures: List[List[str]]       # OR of AND-keyword-lists, matched against a solver's answer


# Populated by tools/load from the generation workflow (see cognitive_bench / build step).
COGNITIVE_TASKS: List[CogTask] = []


def by_category():
    out = {}
    for t in COGNITIVE_TASKS:
        out.setdefault(t.category, []).append(t)
    return out
