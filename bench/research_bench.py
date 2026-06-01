"""Research A/B: single-shot vs ultracode-research, scored on ground-truth fact recall."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.ultracode.config import UltracodeConfig
from agent.ultracode.harness import run
from agent.ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient
from bench.research_tasks import RESEARCH_TASKS
from bench.scorer import matches_bug


def recall(answer: str, task) -> tuple:
    a = (answer or "").lower()
    found = [b.name for b in task.planted if matches_bug(a, b)]
    return len(found) / len(task.planted), [b.name for b in task.planted if b.name not in found]


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.COMPLETENESS],
                          max_finders=4, concurrency=12, max_children=8)
    br, ur = [], []
    for t in RESEARCH_TASKS:
        cb = DeepSeekClient(model=model, max_workers=8)
        out = cb.chat([{"role": "system", "content": "Answer thoroughly and accurately."},
                       {"role": "user", "content": t.prompt}], temperature=0.3, max_tokens=4000)
        b_ans = type(cb)._content(out)
        b_rec, b_missed = recall(b_ans, t)
        br.append(b_rec)

        cu = DeepSeekClient(model=model, max_workers=12)
        t0 = time.time()
        res = run(t.prompt, kind="research", force_orchestrate=True, delegate_fn=cu.delegate_fn,
                  aux_call_fn=cu.aux_call_fn, config=cfg, enable_ledger=False, run_id=t.id)
        u_rec, u_missed = recall(res.answer, t)
        ur.append(u_rec)
        print(f"  {t.id:14} planted={len(t.planted)}  baseline_recall={b_rec:.2f} (missed {b_missed})  "
              f"ultracode_recall={u_rec:.2f} (missed {u_missed}) [{res.mode}, {time.time()-t0:.0f}s, {cu.usage.snapshot()['total_tokens']}tok]", flush=True)
    print(f"\n=== {model}: baseline mean recall={sum(br)/len(br):.3f}  ultracode mean recall={sum(ur)/len(ur):.3f} ===", flush=True)


if __name__ == "__main__":
    main()
