"""SUBJECTIVE generation tasks (marketing / email / creative / rhetoric / naming / microcopy).

No single right answer — quality is craft and taste. Each task carries a RUBRIC (4-6 specific,
checkable criteria a great output must meet) and CONSTRAINTS (objective: word/line limits,
must-include, format). These let a rubric-judge score otherwise-subjective output, and they are
chosen so an explore-many-candidates-then-graft process (judge-panel) should beat a single draft.
Auto-generated + verified; populated by build_subj_bank.py.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SubjTask:
    id: str
    category: str
    brief: str                       # the creative brief shown to a writer
    rubric: List[str]                # 4-6 checkable quality criteria
    constraints: str = ""            # objective hard constraints (length, must-include, format)
    why_ultracode: str = ""          # why multi-candidate + critique beats one shot


SUBJECTIVE_TASKS: List[SubjTask] = []


def by_category():
    out = {}
    for t in SUBJECTIVE_TASKS:
        out.setdefault(t.category, []).append(t)
    return out
