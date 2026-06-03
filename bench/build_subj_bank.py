"""Write bench/subjective_tasks.py's SUBJECTIVE_TASKS from a generation-workflow result JSON."""

import json
import sys
from pathlib import Path

HEADER = '''"""SUBJECTIVE generation tasks (auto-generated + verified). See build_subj_bank.py."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SubjTask:
    id: str
    category: str
    brief: str
    rubric: List[str]
    constraints: str = ""
    why_ultracode: str = ""


def by_category():
    out = {}
    for t in SUBJECTIVE_TASKS:
        out.setdefault(t.category, []).append(t)
    return out


SUBJECTIVE_TASKS: List[SubjTask] = [
'''


def _extract(blob):
    if isinstance(blob, dict):
        if "result" in blob and isinstance(blob["result"], dict):
            blob = blob["result"]
        if "kept" in blob:
            return blob["kept"]
    if isinstance(blob, list):
        return blob
    raise SystemExit("no task list found")


def main():
    tasks = _extract(json.loads(Path(sys.argv[1]).read_text()))
    out = Path(__file__).resolve().parent / "subjective_tasks.py"
    lines = [HEADER]
    seen, n = set(), 0
    for t in tasks:
        tid = str(t.get("id", "")).strip()
        rubric = [str(x) for x in (t.get("rubric") or []) if str(x).strip()]
        if not tid or tid in seen or len(rubric) < 3:
            continue
        seen.add(tid)
        lines.append("    SubjTask(")
        lines.append(f"        id={tid!r}, category={str(t.get('category',''))!r},")
        lines.append(f"        brief={str(t.get('brief',''))!r},")
        lines.append(f"        rubric={rubric!r},")
        lines.append(f"        constraints={str(t.get('constraints',''))!r},")
        lines.append(f"        why_ultracode={str(t.get('why_ultracode',''))!r},")
        lines.append("    ),")
        n += 1
    lines.append("]\n")
    out.write_text("\n".join(lines))
    print(f"wrote {n} subjective tasks to {out}")


if __name__ == "__main__":
    main()
