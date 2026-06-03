# Cognitive head-to-head: Opus baseline vs DeepSeek+ultracode

**Question:** on genuinely reasoning-hard tasks (where a weak model's reasoning is the bottleneck),
how close does ultracode-on-DeepSeek-flash get to baseline Opus?

**Method.** 109 cognitively-hard tasks across 10 categories (deductive logic, quantitative, code-output
trace, subtle-bug-hunt, algorithm-reasoning, causal/counterfactual, proof-flaw-detection, constraint-
planning, lateral-insight, multi-hop inference), each generated and **independently verified** (every
answer re-derived from scratch, code executed) so the ground truth is objective. Three solvers, scored
the same way: **Opus** (me, solving directly = the baseline), **DeepSeek-flash single-shot**, and
**DeepSeek-flash + ultracode** (the harness: decompose → fan out → verify → synthesize).

**Scoring.** Crisp-answer tasks (numbers, names, outputs) are keyword-scored against ground truth.
Paragraph-answer tasks (find-the-bug, find-the-flawed-step, derive-the-complexity) and any crisp task a
solver got marked wrong are re-scored by an **LLM judge** against ground truth, anonymized and judged on
substance — because keyword matching systematically **under**-counts correct-but-terse answers (ultracode's
synthesis says "B", the signature wanted "B is the Spy"). Keyword-*true* matches are trusted (specific
signatures don't false-positive).

## Result

| solver | score | ratio vs Opus |
|---|---|---|
| **Opus baseline (me)** | **109 / 109 = 1.000** | — |
| DeepSeek-flash single-shot | 92 / 109 = 0.844 | **84.4 %** |
| **DeepSeek-flash + ultracode** | **100 / 109 = 0.917** | **91.7 %** |

**ultracode-flash reaches 91.7 % of baseline Opus, +7.3 points over single-shot flash** — above the
70–80 % target. (Naive keyword-only scoring read 0.79; it was an artifact of penalizing ultracode's terse
synthesized answers, which the judge corrected.)

### Per category (correct / n)

| category | Opus | flash single-shot | flash + ultracode |
|---|---|---|---|
| deductive_logic | 12/12 | 10/12 | 11/12 |
| quantitative_reasoning | 12/12 | 12/12 | 12/12 |
| code_output_trace | 12/12 | 11/12 | 11/12 |
| subtle_bug_hunt | 10/10 | 9/10 | 10/10 |
| algorithm_reasoning | 10/10 | 7/10 | 8/10 |
| causal_counterfactual | 12/12 | 8/12 | **12/12** |
| proof_flaw_detection | 10/10 | 10/10 | 9/10 |
| constraint_planning | 12/12 | 11/12 | 11/12 |
| lateral_insight | 12/12 | 8/12 | **10/12** |
| multi_hop_inference | 7/7 | 6/7 | 6/7 |

### What ultracode did and didn't fix
- **Biggest lifts where the harness helped:** causal_counterfactual (8→12) and lateral_insight (8→10) —
  multi-step simulation/induction tasks (pirate game, cyclic XOR at step 100, water-jug min-pours) where
  the decompose-and-verify discipline kept flash from a one-pass slip. It also **filled in empty answers**
  the single-shot left blank on hard paragraph tasks.
- **The 9 remaining ultracode failures cluster on SEARCH / COMPUTE tasks:** `binary-digit-multiple` (BFS
  over remainders), `two-jug-six-liters` (BFS over states), `hazmat-knapsack` (constrained knapsack),
  `factorial-trailing-zeros` (solve z(n)≥100). These need systematic enumeration a language model can't do
  reliably in-head — but flash can *write correct code for them*. The harness has `run_python` but only
  uses it for the finding-arbiter, not as a reasoning aid. **Wiring execution into solving is the next
  lever** (see the gap-closing work).

**Honest caveat:** reasoning quality is genetics; the harness narrows the gap (structure, verification,
not-leaving-blanks), it doesn't replace model intelligence. 91.7 % is the ceiling of what *this* harness
extracts from flash on these tasks today — the execution and self-consistency levers target the rest.
