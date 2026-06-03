"""Combine keyword scoring (crisp-answer categories) with an LLM-judge (paragraph-answer
categories) for a fair Opus-vs-DeepSeek cognitive ratio.

Keyword matching is robust for crisp answers (numbers, names, code output) but brittle for
diagnostic-paragraph answers (algorithm_reasoning, proof_flaw_detection, subtle_bug_hunt),
where a correct answer can miss exact multi-keyword signatures. For those categories we emit
the (prompt, ground-truth, anonymized solver answers) to judge_input.json for an LLM judge,
then `combine` merges the judge verdicts back in.

  python bench/cog_final_score.py prep    # write judge_input.json for the paragraph categories
  python bench/cog_final_score.py combine  # merge judge_verdicts.json + keyword scores -> final ratio
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.cognitive_tasks import COGNITIVE_TASKS
from bench.cognitive_bench import is_correct

RES = Path(__file__).resolve().parent / "results"
JUDGE_CATEGORIES = {"algorithm_reasoning", "proof_flaw_detection", "subtle_bug_hunt"}
SOLVERS = {
    "opus": RES / "cog_opus_answers.json",
    "ds_baseline": RES / "cog_baseline_deepseek-v4-flash.json",
    "ds_ultracode": RES / "cog_ultracode_deepseek-v4-flash.json",
}


def _load(p):
    return json.loads(Path(p).read_text()) if Path(p).exists() else {}


def prep():
    idx = {t.id: t for t in COGNITIVE_TASKS}
    answers = {k: _load(p) for k, p in SOLVERS.items()}
    items = []
    for tid, t in idx.items():
        if t.category not in JUDGE_CATEGORIES:
            continue
        items.append({
            "id": tid, "category": t.category, "prompt": t.prompt, "ground_truth": t.answer,
            "answers": {k: answers[k].get(tid, {}).get("answer", "") for k in SOLVERS},
        })
    (RES / "judge_input.json").write_text(json.dumps(items, indent=1))
    print(f"wrote {len(items)} paragraph-category items to judge_input.json")


def _agg(rows):
    by = {}
    for cat, ok in rows:
        c = by.setdefault(cat, [0, 0]); c[0] += int(ok); c[1] += 1
    overall = sum(int(ok) for _, ok in rows) / max(len(rows), 1)
    return overall, {k: (v[0] / v[1], v[1]) for k, v in by.items()}


def combine():
    idx = {t.id: t for t in COGNITIVE_TASKS}
    answers = {k: _load(p) for k, p in SOLVERS.items()}
    verdicts = _load(RES / "judge_verdicts.json")  # {id: {solver: bool}}
    table = {}
    for solver in SOLVERS:
        rows = []
        for tid, t in idx.items():
            if t.category in JUDGE_CATEGORIES and tid in verdicts:
                ok = bool(verdicts[tid].get(solver, False))
            else:
                ok = is_correct(answers[solver].get(tid, {}).get("answer", ""), t)
            rows.append((t.category, ok))
        table[solver] = _agg(rows)
    for solver, (overall, per) in table.items():
        print(f"\n### {solver}: overall = {overall:.3f}")
        for c, (acc, n) in sorted(per.items()):
            print(f"    {c:24} {acc:.2f}  (n={n})")
    o = table["opus"][0]
    print(f"\n=== ultracode-flash / opus = {table['ds_ultracode'][0]/o:.1%}  "
          f"|  single-shot flash / opus = {table['ds_baseline'][0]/o:.1%}  "
          f"|  ultracode lift over single-shot = {table['ds_ultracode'][0]-table['ds_baseline'][0]:+.3f} ===")


if __name__ == "__main__":
    (prep if (len(sys.argv) > 1 and sys.argv[1] == "prep") else combine)()
