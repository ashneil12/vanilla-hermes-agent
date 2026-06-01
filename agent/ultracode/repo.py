"""repo.py — ultracode at REPO scale: ingest a large codebase, chunk by file,
and fan out one finder per chunk.

A 50k–200k-line repo cannot fit in a single context, so single-shot audit is
physically impossible — this is the regime where orchestration is mandatory, not
optional. The design scales linearly: N chunks -> N finders, capped only by the
concurrency knob (and now safe to run concurrently thanks to the delegate_task
thread-safety patch). Findings across all files are reconciled (root-cause dedup)
and verified (bounded to the load-bearing severities to keep cost linear-ish).

This is the capability the report flagged as missing: the harness ingested one
context blob; now it ingests a directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

from agent.ultracode.adapters import delegate_fanout, extract_json
from agent.ultracode.config import UltracodeConfig
from agent.ultracode.schema import Finding, dedupe_findings, reconcile_findings
from agent.ultracode.verify import survivors as _survivors, verify_findings


@dataclass
class Chunk:
    path: str          # repo-relative path
    start: int         # 1-based start line
    text: str


@dataclass
class RepoAuditResult:
    n_files: int = 0
    n_chunks: int = 0
    findings: List[Finding] = field(default_factory=list)
    survivors: List[Finding] = field(default_factory=list)
    caps_announced: List[str] = field(default_factory=list)

    def by_file(self):
        out = {}
        for f in self.survivors:
            fp = f.locator.split(":")[0]
            out.setdefault(fp, []).append(f)
        return out


_DEFAULT_EXCLUDE = ("/test", "/tests/", "/migrations/", "/.git/", "/node_modules/", "__pycache__")


def chunk_repo(
    root: str,
    *,
    ext: str = ".py",
    max_chunk_lines: int = 350,
    max_files: Optional[int] = None,
    include_substr: Tuple[str, ...] = (),
    exclude_substr: Tuple[str, ...] = _DEFAULT_EXCLUDE,
    min_file_lines: int = 8,
) -> List[Chunk]:
    """Walk ``root`` and produce chunks (a big file becomes several)."""
    paths: List[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.endswith(ext):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            norm = "/" + rel.replace(os.sep, "/")
            if any(x in norm for x in exclude_substr):
                continue
            if include_substr and not any(x in norm for x in include_substr):
                continue
            paths.append((full, rel))
    paths.sort(key=lambda p: p[1])
    if max_files:
        paths = paths[:max_files]

    chunks: List[Chunk] = []
    for full, rel in paths:
        try:
            lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        if len(lines) < min_file_lines:
            continue
        for start in range(0, len(lines), max_chunk_lines):
            seg = lines[start : start + max_chunk_lines]
            # prefix each line with its absolute line number so locators are precise
            body = "\n".join(f"{start + i + 1}: {ln}" for i, ln in enumerate(seg))
            chunks.append(Chunk(path=rel, start=start + 1, text=body))
    return chunks


def _finder_prompt(task: str, chunk: Chunk) -> str:
    return (
        f"You are auditing ONE file from a large codebase. {task}\n\n"
        f"FILE: {chunk.path} (lines {chunk.start}+; line numbers are prefixed)\n\n"
        f"{chunk.text}\n\n"
        "Report ONLY concrete, real, locatable issues in THIS file — no speculation, no style nits. "
        'Reply with ONLY JSON: {"findings":[{"claim":"<specific>","line":<int>,'
        '"evidence":"<why>","severity":"info|low|medium|high|critical"}]}. Empty if none.'
    )


def _parse(entry, chunk: Chunk) -> List[Finding]:
    if not isinstance(entry, dict) or entry.get("status") != "completed":
        return []
    parsed = extract_json(entry.get("summary") or "")
    items = parsed.get("findings", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
    out: List[Finding] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("claim", "")).strip():
            line = it.get("line", chunk.start)
            locator = f"{chunk.path}:{line}"
            try:
                out.append(Finding(
                    claim=str(it["claim"]).strip(), locator=locator,
                    evidence=str(it.get("evidence", "")).strip(),
                    severity=str(it.get("severity", "info")).strip() or "info",
                    source_label=chunk.path,
                ).validate())
            except ValueError:
                continue
    return out


def audit_repo(
    chunks: List[Chunk],
    task: str,
    *,
    delegate_fn: Optional[Callable[..., str]] = None,
    config: Optional[UltracodeConfig] = None,
    agent: Any = None,
    concurrency: int = 24,
    verify_severities: Tuple[str, ...] = ("critical", "high"),
    progress: Optional[Callable[[str], None]] = None,
) -> RepoAuditResult:
    """Fan out one finder per chunk, aggregate, reconcile, and verify the
    load-bearing findings. Scales to any repo size — cost is linear in chunks."""
    cfg = config or UltracodeConfig()
    res = RepoAuditResult(n_files=len({c.path for c in chunks}), n_chunks=len(chunks))
    if not chunks:
        return res

    tasks = [{"goal": _finder_prompt(task, c)} for c in chunks]
    if progress:
        progress(f"finders: {len(tasks)} chunks across {res.n_files} files (concurrency {concurrency})")
    results = delegate_fanout(tasks, parent_agent=agent, max_children=cfg.max_children,
                              concurrency=concurrency, delegate_fn=delegate_fn)
    raw: List[Finding] = []
    for i, entry in enumerate(results):
        raw.extend(_parse(entry if isinstance(entry, dict) else {}, chunks[i]))
    res.caps_announced.append(f"audited {res.n_chunks} chunks / {res.n_files} files; {len(raw)} raw findings")

    findings = reconcile_findings(raw) if cfg.reconcile else dedupe_findings(raw)
    if len(raw) != len(findings):
        res.caps_announced.append(f"reconciled {len(raw)} -> {len(findings)} (merged duplicates across files)")

    # verify only the load-bearing severities (keeps repo-scale cost bounded)
    to_verify = [f for f in findings if (f.severity or "").lower() in verify_severities]
    if cfg.verify and to_verify:
        if progress:
            progress(f"verifying {len(to_verify)} {'/'.join(verify_severities)} findings adversarially")
        verify_findings(to_verify, parent_agent=agent, config=cfg, lenses=cfg.verify_lenses,
                        delegate_fn=delegate_fn, concurrency=concurrency)
        kept = set(id(f) for f in _survivors(to_verify))
        # survivors = (verified high-sev that survived) + (all lower-sev, reported with caveat)
        res.survivors = [f for f in findings if (f.severity or "").lower() not in verify_severities or id(f) in kept]
    else:
        res.survivors = findings
    res.findings = findings
    return res
