"""Write bench/cognitive_tasks.py's COGNITIVE_TASKS from a generation-workflow result JSON.

Usage: python bench/build_cog_bank.py <workflow_output.json>
The JSON may be the raw workflow .output (has {"result": {"kept": [...]}}) or just {"kept": [...]}
or a bare list of task dicts. Each task dict: {id, category, prompt, answer, difficulty, signatures}.
"""

import json
import sys
from pathlib import Path

HEADER = '''"""Cognitively-hard benchmark tasks with OBJECTIVE ground truth (auto-generated + verified).

Generated across reasoning categories and independently verified (each answer re-derived from
scratch, code executed) before inclusion. Scoring: a solver's final answer is CORRECT if it
matches any `signatures` variant (AND-list of lowercased keywords). Built by build_cog_bank.py.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class CogTask:
    id: str
    category: str
    prompt: str
    answer: str
    difficulty: str
    signatures: List[List[str]]


def by_category():
    out = {}
    for t in COGNITIVE_TASKS:
        out.setdefault(t.category, []).append(t)
    return out


COGNITIVE_TASKS: List[CogTask] = [
'''


def _extract(blob):
    if isinstance(blob, dict):
        if "result" in blob and isinstance(blob["result"], dict):
            blob = blob["result"]
        if "kept" in blob:
            return blob["kept"]
    if isinstance(blob, list):
        return blob
    raise SystemExit("could not find a task list in the input JSON")


def main():
    src = Path(sys.argv[1])
    tasks = _extract(json.loads(src.read_text()))
    out = Path(__file__).resolve().parent / "cognitive_tasks.py"
    lines = [HEADER]
    seen = set()
    n = 0
    for t in tasks:
        tid = str(t.get("id", "")).strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        sigs = t.get("signatures") or []
        # normalize signatures to List[List[str]]
        norm = [[str(k) for k in variant] for variant in sigs if isinstance(variant, list) and variant]
        if not norm:
            continue
        lines.append("    CogTask(")
        lines.append(f"        id={tid!r}, category={str(t.get('category',''))!r}, difficulty={str(t.get('difficulty','hard'))!r},")
        lines.append(f"        prompt={str(t.get('prompt',''))!r},")
        lines.append(f"        answer={str(t.get('answer',''))!r},")
        lines.append(f"        signatures={norm!r},")
        lines.append("    ),")
        n += 1
    lines.append("]\n")
    out.write_text("\n".join(lines))
    print(f"wrote {n} tasks to {out}")


if __name__ == "__main__":
    main()
