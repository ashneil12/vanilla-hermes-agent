"""Tests for repo-scale chunked auditing (no live model)."""

import json
import os

from agent.ultracode.config import UltracodeConfig
from agent.ultracode.repo import audit_repo, chunk_repo


def _write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text)


def test_chunk_repo_splits_large_files_and_excludes(tmp_path):
    root = str(tmp_path)
    _write(root, "app/core.py", "\n".join(f"line{i}" for i in range(800)))  # -> multiple chunks
    _write(root, "app/small.py", "\n".join(f"x{i}" for i in range(20)))
    _write(root, "tests/test_core.py", "should be excluded\n" * 50)
    _write(root, "app/tiny.py", "a\nb")  # below min_file_lines -> skipped

    chunks = chunk_repo(root, max_chunk_lines=350)
    paths = {c.path for c in chunks}
    assert any("core.py" in p for p in paths)
    assert any("small.py" in p for p in paths)
    assert not any("test_core" in p for p in paths)   # excluded
    assert not any("tiny.py" in p for p in paths)      # too small
    # core.py (800 lines) -> 3 chunks of <=350
    core_chunks = [c for c in chunks if c.path.endswith("core.py")]
    assert len(core_chunks) == 3
    # line numbers are prefixed and continue across chunks
    assert core_chunks[0].start == 1 and core_chunks[1].start == 351
    assert "351: line350" in core_chunks[1].text


def test_audit_repo_aggregates_and_verifies(tmp_path):
    root = str(tmp_path)
    _write(root, "a/db.py", "\n".join(f"q{i}" for i in range(30)))
    _write(root, "a/util.py", "\n".join(f"u{i}" for i in range(30)))
    chunks = chunk_repo(root, max_chunk_lines=350)

    def fake_delegate(*, tasks, parent_agent, role):
        results = []
        for i, t in enumerate(tasks):
            goal = t["goal"]
            if "adversarial verifier" in goal:  # skeptic
                claim = goal.split("CLAIM:", 1)[1].split("\n", 1)[0].strip()
                v = "confirmed" if "sql" in claim.lower() else "refuted"
                results.append({"task_index": i, "status": "completed",
                                "summary": json.dumps({"verdict": v, "rationale": "m"})})
            else:  # finder: db.py reports a critical SQLi, util.py a low nit
                if "db.py" in goal:
                    body = {"findings": [{"claim": "SQL injection in query", "line": 5, "evidence": "concat", "severity": "critical"}]}
                else:
                    body = {"findings": [{"claim": "minor style", "line": 2, "evidence": "x", "severity": "low"}]}
            if "adversarial verifier" not in goal:
                results.append({"task_index": i, "status": "completed", "summary": json.dumps(body)})
        return json.dumps({"results": results})

    res = audit_repo(chunks, "Find security bugs.", delegate_fn=fake_delegate,
                     config=UltracodeConfig(), concurrency=8)
    assert res.n_files == 2
    locators = {f.locator for f in res.findings}
    assert any("db.py:5" in l for l in locators)
    # the critical SQLi (verified) survives; the low nit is reported (not verified, kept)
    surv_claims = [f.claim for f in res.survivors]
    assert any("SQL" in c for c in surv_claims)
    bf = res.by_file()
    assert any("db.py" in k for k in bf)
