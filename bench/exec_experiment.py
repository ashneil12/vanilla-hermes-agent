"""Does execution-augmented solving close the search/compute failures?

For the tasks flash got wrong both single-shot AND under ultracode, all of which are
systematic-search / computation problems, test: let flash WRITE a self-contained Python
program that computes the answer, RUN it (run_python), and use the output. This mirrors
how an expert solves them — recognize it's computable, write the search, run it.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.ultracode.execute import run_python, extract_code
from bench.cognitive_tasks import COGNITIVE_TASKS
from bench.cognitive_bench import is_correct
from bench.deepseek_client import DeepSeekClient

# the genuine compute/search failures (both flash modes wrong, judged)
TARGETS = [
    "lateral_insight__binary-digit-multiple",
    "lateral_insight__two-jug-six-liters",
    "constraint_planning__hazmat-truck-knapsack",
    "algorithm_reasoning__factorial-trailing-zeros",
    "lateral_insight__factorial-trailing-zeros",
    "causal_counterfactual__collatz-27-steps",
    "quantitative_reasoning__power-tower-mod-100",
    "lateral_insight__gossip-calls",
    "constraint_planning__two-machine-makespan",
    "multi_hop_inference__relay-medal-handoff",
]

_SYS = ("You solve problems by WRITING AND RUNNING code. Given a problem, write a single self-contained "
        "Python 3 program (standard library only) that COMPUTES the answer by brute force / systematic "
        "search / simulation — do not try to reason it out, let the program do the work — and prints ONLY "
        "the final answer on the last line. Wrap the program in a ```python code block.")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    idx = {t.id: t for t in COGNITIVE_TASKS}
    ok = 0
    tasks = [idx[t] for t in TARGETS if t in idx]
    for t in tasks:
        c = DeepSeekClient(model=model, max_workers=2)
        reply = c.chat([{"role": "system", "content": _SYS},
                        {"role": "user", "content": t.prompt}], temperature=0.2, max_tokens=2500)
        code = extract_code(type(c)._content(reply))
        res = run_python(code, timeout=10.0) if code else None
        out = (res.stdout.strip() if res and res.ok else f"(no run: {res.stderr[:80] if res else 'no code'})")
        # the answer is the program's output; score it (also include reasoning-free output)
        good = is_correct(out, t)
        ok += good
        print(f"  {'OK ' if good else 'XX '} {t.id.split('__')[1]:34} -> {out[:50]!r}  (truth {t.answer[:30]!r})", flush=True)
    print(f"\n=== execution-augmented solved {ok}/{len(tasks)} of the compute-hard targets ===")


if __name__ == "__main__":
    main()
