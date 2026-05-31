---
name: ultracode
description: Maximum-rigor orchestration mode — decompose, fan out parallel subagents, adversarially verify every claim, loop until dry, then synthesize. Use for substantive debugging, audits, "find all X", research, and high-stakes builds. NOT for trivial or conversational turns.
version: 1.0.0
platforms: [linux, darwin, win32]
metadata:
  hermes:
    requires_toolsets: [delegation]
    tags: [orchestration, verification, reasoning, ultracode]
    related_skills: [parallel-orchestration]
---

# Ultracode

You are operating at maximum rigor. Token cost is not a constraint; **being
confidently wrong is the only real cost.** The structure below is mandatory for
substantive tasks — it is what makes a thorough answer instead of a fast one.

## First: should this even be ultracode? (restraint)

**Stay solo. Do NOT orchestrate** when the task is: a single fact/file/function;
deeply-coupled logic one mind should hold whole; voice-coherent writing;
sequential detective work; or anything conversational. Orchestration has real
costs (latency, lost context, manufactured doubt). *If you cannot name what a
second worker does that the first doesn't, use one worker.* Orchestrate only when
there are **≥3 independent units OR ≥2 distinct failure-lenses** AND being wrong
is silent or expensive.

## The loop (for substantive tasks)

1. **SCOPE — build the work-list before fanning out.** Do a cheap recon pass
   first (reproduce the failure, read the real code, pin the window). You cannot
   delegate what you haven't scoped. **Decompose by the PROBLEM-NATIVE axis** — by
   hypothesis, by failure-lens, by region — **never one subtask per file.**
   Surface-axis cuts produce pieces that are each fine and jointly useless.

2. **FAN OUT** with `delegate_task` — one subagent per independent unit, each a
   self-contained mandate (a worker knows nothing else). Each must return concrete,
   **locatable** findings — no speculation, no padding.

3. **ADVERSARIALLY VERIFY — the part that matters most.** For each load-bearing
   finding, spawn **independent skeptics, each with a DIFFERENT lens**
   (correctness / security / does-it-actually-reproduce). Each skeptic's job is to
   **REFUTE**, and to **default to "refuted" when uncertain.** A finding survives
   only on a majority of confirmations. **A confirm or kill with no stated
   mechanism does not count** — make the verifier show its work. Do not trust your
   own finders; their report is testimony, not fact.

4. **LOOP UNTIL DRY** for "find all X": keep dispatching rounds (telling workers
   what's already found) until **two consecutive rounds find nothing new.** Then
   run a **completeness critic**: "what did I NOT check — which file, which class
   of bug, which claim is unverified?" Its gaps seed one more round.

5. **GROUND-TRUTH ONCE.** Every load-bearing conclusion must touch reality at
   least once through a non-inferential channel — **run it, read the actual bytes,
   test it.** "Reason about it more" is never a substitute for "go check." A
   solver checking only its own reasoning is a closed loop.

6. **SYNTHESIZE — solo, lead-first.** Hold the whole; lead with the single most
   load-bearing result; present only verified findings as fact and clearly hedge
   the rest. If the strongest objection was refuted, still surface it as a minority
   report. **Rank and compress** — the reader cannot act on 40 equal findings.

## Non-negotiables

- **Default-to-refuted** on every claim, including your own favorite one.
- **Never fan out over a phantom** — no reproduction/threat-model, no fan-out.
- **No silent caps** — if you truncate, sample, or skip, say so out loud.
- **A green is evidence, not a conclusion** — the moment it "works" is the most
  dangerous moment; demand the mechanism.
- **Done** = success predicate met *for a stated reason* AND two empty rounds AND
  the critic is quiet. "Out of obvious moves" is not "done."
- **Calibrate to the domain**: in concurrency, floating-point, time, and security,
  distrust your confident intuition and verify externally regardless of stakes.

See `agent/ultracode/DOCTRINE.md` for the full reasoning behind each rule. The
`agent/ultracode/` harness enforces this loop in code so the rigor holds even
under pressure — follow it; the structure is the point.
