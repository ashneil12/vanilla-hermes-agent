"""Run the ultracode repo-scale audit on a real codebase directory."""

import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.ultracode.config import UltracodeConfig
from agent.ultracode.repo import audit_repo, chunk_repo
from agent.ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient

AUDIT = ("Find REAL security and correctness vulnerabilities: injection (SQL/command/template), "
         "broken auth / missing access-control / IDOR, weak crypto / hardcoded secrets, insecure "
         "deserialization, SSRF, and clear logic bugs. No style nits.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--include", default="")
    ap.add_argument("--max-files", type=int, default=35)
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--out", default="bench/results/repo_audit")
    args = ap.parse_args()

    inc = tuple(s for s in args.include.split(",") if s)
    chunks = chunk_repo(args.root, include_substr=inc, max_files=args.max_files)
    files = sorted({c.path for c in chunks})
    print(f"chunks={len(chunks)} files={len(files)}", flush=True)

    client = DeepSeekClient(model=args.model, max_workers=24)
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY],
                          max_children=8, concurrency=24)
    t0 = time.time()
    res = audit_repo(chunks, AUDIT, delegate_fn=client.delegate_fn, config=cfg,
                     concurrency=24, verify_severities=("critical", "high"), progress=lambda m: print("  " + m, flush=True))
    dt = time.time() - t0
    u = client.usage.snapshot()
    out = {
        "files": res.n_files, "chunks": res.n_chunks, "seconds": round(dt, 1), "usage": u,
        "caps": res.caps_announced,
        "audited_files": files,
        "survivors": [f.as_dict() for f in res.survivors],
    }
    Path(args.out).with_suffix(".json").write_text(json.dumps(out, indent=2))
    print(f"\n=== {res.n_files} files, {res.n_chunks} chunks, {len(res.survivors)} findings, {dt:.0f}s, {u['total_tokens']}tok ===", flush=True)
    for f in sorted(res.survivors, key=lambda x: ({"critical":0,"high":1,"medium":2,"low":3,"info":4}.get((x.severity or "info").lower(), 5))):
        print(f"  [{(f.severity or 'info'):8}] {f.claim[:84]:84} @{f.locator}", flush=True)


if __name__ == "__main__":
    main()
