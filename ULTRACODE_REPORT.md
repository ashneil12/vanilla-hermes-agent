# Ultracode → Hermes — overnight build & benchmark report

_Built autonomously overnight on branch `feat/ultracode-tier3` in an isolated
worktree. Your `main` was never touched; nothing pushed. 76 tests green, 14 commits._

## TL;DR — the honest verdict

I built the full ultracode harness, stress-tested it, compared it against my own
orchestration, and benchmarked it hard against `deepseek-v4-pro` **and**
`deepseek-v4-flash`. The truthful result, stated plainly because the whole
doctrine is "don't be confidently wrong":

> **On tasks within a model's single-shot reach, ultracode is net-negative — it
> matches recall at 27–37× the token cost and can *hurt* precision by
> over-generating findings.** Both pro and flash one-shot every small/moderate
> bug-finding and claim-refutation task I gave them (recall 1.0), leaving nothing
> for orchestration to win.

That is not a failure of the harness — it's a finding about *when* to use it.
Ultracode is **not a 24/7 "always on" win**; it's a **regime tool**. Its value
shows only where single-shot genuinely fails: large/many-file codebases (attention
dilution), genuinely subtle or adversarial cases, precision-critical work, or a
model too weak to one-shot the task. The large-codebase test below probes the
first of those directly.

## What got built (all tested, committed)

`agent/ultracode/`: `schema · graph · adapters · config · reasoning · ledger ·
verify · discovery · critic · steering · planner · harness · mode · conductor`
plus `DOCTRINE.md`, `CONTRACTS.md`, the `ultracode` SKILL, and a DeepSeek
benchmark suite in `bench/`. The loop: **steer → plan → find (reactive
loop-until-dry) → adversarially verify (VOI-triaged) → completeness-critic →
synthesize**, every fork call funnelled through one verified seam.

## Stress test — 100+ parallel agents

`delegate_fanout` gained concurrent-wave dispatch. Proven (fake backend, no API):

| N agents | per-call cap | peak concurrency | speedup | result |
|---|---|---|---|---|
| 100 | 3 | **100** | 80× | all complete, indices correct |
| 600 | 8 | 200 | 155× | all complete, 15% failures handled |

**The orchestration logic manages 100+ in parallel.** The real limiter is the
backend: the actual Hermes `delegate_task` mutates a process-global and is **not
concurrency-safe**, so true on-runtime scale needs that fixed (or
`max_concurrent_children` raised). That's the concrete upstream fix this surfaces.

## Self-comparison — the harness vs me, on the same task

I ran the 12-bug audit through my *own* Claude ultracode (a Workflow) and scored
it the same way:

| | recall | precision | agents | notes |
|---|---|---|---|---|
| Claude-ultracode (ad-hoc) | 12/12 | 0.89 | 32 | **0% verifier cull, visible duplicates** |
| DeepSeek harness | 12/12 | 0.93 | ~40 | dedup + mechanism-required verify |

My own synthesis flagged it: *"the verifiers were rubber-stamping and never
deduplicating across finder outputs."* **The harness is more disciplined than I am
orchestrating by feel** — it dedups and its default-to-refuted verify requires a
stated mechanism. The shared gap: near-duplicate findings (same bug, different
wording) slip past hash-dedup → both need **root-cause reconciliation**.

## Benchmarks (A/B vs raw single-shot, deterministic scoring)

**Small/moderate bug-finding (5 tasks, 16–27 planted):**

| model | baseline R / P | ultracode R / P | cost |
|---|---|---|---|
| pro (bigbug 12-bug) | 1.00 / 0.92 | 1.00 / 0.93 | 3k → 81k tok (27×) |
| flash (5 tasks) | 1.00 / 0.87 | 1.00 / **0.81** | 8k → 297k tok (37×) |

**Claim refutation (adversarial layer, isolated):** both baseline and ultracode
hit 1.00 accuracy / 1.00 false-refute-rate — a ceiling; the model catches every
obvious-false claim single-shot. (The fix here: ultracode's `true_keep_rate=1.0` —
it didn't over-refute true claims.)

**Large codebase tests — the attention-dilution / needle-in-haystack regime:**

| task | model | baseline R / P | ultracode R / P | cost |
|---|---|---|---|---|
| large (120 ln, 21 bugs, dense) | flash | **1.00 / 1.00** | 0.95 / 0.94 | 4k → 288k tok (78×) |
| large2 (924 ln, 21 bugs, sparse) | flash | **1.00 / 1.00** | _pending_ | 9k → … |

The escalation from 40 → 924 lines, dense and sparse, pro and flash, hit the
**same ceiling every time: single-shot baseline recall 1.00.** On the 120-line
dense task ultracode was strictly *worse* — it found all 21 pre-verify but a
single over-zealous skeptic killed a real bug (0.95) and 2 spurious survived, at
78× cost. (That 1-lens-kill fragility is now fixed: a kill requires ≥2 mechanism-
backed refutations.) **Even a 924-line file with sparse bugs did not open a recall
gap** — these models are simply not attention-limited at this scale.

## Real harness issues found (and what I did)

1. **Over-refutation** (v2): default-to-refuted + confirm-quorum killed *real*
   bugs (recall 1.0→0.81). **Fixed** with defend/prove survival modes (the
   doctrine's symmetric-burden rule) — recall recovered to 1.0.
2. **Verification cost** dominates (~60k tok/task). **Mitigated** with VOI-triaged
   verification (severity-weighted lenses ≈ halves skeptic calls).
3. **Over-generation** hurts precision on easy tasks: more finders + reactive
   replan → more findings → more spurious survive. The scale-to-the-ask gate
   should suppress looping on small inputs (refinement noted).
4. **Skeptics judged blind** to the code. **Fixed** — they now read the material.
5. DeepSeek is a reasoning model: tight `max_tokens` truncates output silently.
   **Fixed** with a token floor.

## When to turn it on (recommendation)

- **OFF** for quick/moderate tasks with a capable model — it's pure overhead there.
- **ON** for: large/multi-file audits, genuinely subtle or adversarial review,
  precision-critical sign-off, or driving a cheap/weak model on a hard task (the
  "make a weak model punch above its weight" case — *if* the large-task result
  below bears it out).
- The **steering gate already encodes restraint** (solo by default); the missing
  piece is auto-scaling rigor to input size so it never over-serves a small task.

## Honest next steps to make it a keeper, not a gimmick

1. **Ground-truth-once is not yet real**: workers *reason*, they don't *run* code.
   Wire an execution tool to the finders/skeptics so verification touches reality
   — that's where a harness can beat single-shot reasoning.
2. **Root-cause dedup** (semantic reconciliation) to kill the over-generation.
3. **Auto-scale rigor to input size / stakes** so small tasks stay cheap.
4. **Fix Hermes `delegate_task` thread-safety** for true on-runtime 100-parallel.
5. Re-benchmark on **real large repos** (the regime that should justify the cost).
