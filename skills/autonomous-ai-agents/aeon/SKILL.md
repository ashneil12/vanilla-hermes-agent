---
name: aeon
description: Run scheduled tasks via your Aeon GitHub Actions fork.
version: 0.1.0
author: ashneil12
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    category: autonomous-ai-agents
    tags: [aeon, scheduled, delegation, github-actions, async]
    related_skills: [hermes-agent, github]
    config:
      - key: aeon_github_pat
        description: GitHub PAT (classic, repo + workflow scopes) for the user's Aeon fork.
        prompt: GitHub Personal Access Token
      - key: aeon_fork_repo
        description: The user's Aeon fork in owner/repo form, e.g. ashneil12/aeon.
        prompt: Aeon fork repo (owner/repo)
---

# Aeon Skill

Aeon is an autonomous-agent framework that runs on the user's GitHub Actions. This skill lets you delegate recurring, stateful, or scheduled work to the user's Aeon fork instead of doing it yourself — you stay the synchronous brain, Aeon is the asynchronous one. Think of it as your async second self.

The split is by *when*, not *what*: if the user is waiting on the answer now, do it yourself. If the work can defer, runs on a cadence, or benefits from state across runs, delegate it to Aeon.

## When to Use

Delegate to Aeon when any of these apply:

- The user says "every day at X", "every time Y happens", or "ping me when Z"
- The result should arrive in Telegram/Discord without re-engaging this chat
- The user wants stateful tracking across days (digests, monitors, leaderboards)
- A skill that already does this exists in their fork (check `aeon-list-skills.sh` first)

Stay inline (do NOT delegate) when:

- The user is waiting on output right now
- The work is novel and won't recur
- The action is destructive on resources outside the Aeon fork
- A skill is flagged `[SPEND]` (moves money) and the user has not approved this specific run

## Prerequisites

This skill reads two values from `config.yaml` (shown in the `[Skill config: ...]` block above when set):

- `aeon_github_pat` — a classic GitHub PAT with `repo` + `workflow` scopes
- `aeon_fork_repo` — the user's Aeon fork, e.g. `ashneil12/aeon`

The user sets both in **Settings → AEON** in the Hermes WebUI (one-time). If the config block above shows either as `(not set)`, do not run the scripts — tell the user to enable AEON in Settings first. The user must also have forked `aaronjmars/aeon` and added `ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`) + a notification channel as Actions secrets on their fork.

The helper scripts auto-load both values from `config.yaml` — you never need to pass the token yourself.

## How to Run

Use the `terminal` tool to run the helper scripts in this skill's `scripts/` directory. Each script self-loads credentials; just call it.

| Operation | Command |
|---|---|
| List available skills | `bash scripts/aeon-list-skills.sh` |
| Invoke a skill now | `bash scripts/aeon-invoke.sh <slug> [var]` |
| Enable/schedule a skill | `bash scripts/aeon-enable-skill.sh <slug> "<cron>"` |
| Check recent outputs | `bash scripts/aeon-check-outputs.sh [iso-timestamp]` |

## Quick Reference

```
bash scripts/aeon-list-skills.sh                       # discover
bash scripts/aeon-invoke.sh morning-brief              # one-shot
bash scripts/aeon-invoke.sh repo-pulse "owner/repo"    # one-shot with var
bash scripts/aeon-enable-skill.sh morning-brief "0 7 * * *"   # daily 7am UTC
bash scripts/aeon-check-outputs.sh                     # what ran recently
```

## Procedure

1. **Classify** the request against the When-to-Use rubric. If it stays inline, stop and just do it.
2. **Discover**: run `aeon-list-skills.sh` and match candidates by description. Note any `[SPEND]` flag.
3. **Gate spend**: if a candidate is `[SPEND]`, surface it and require explicit user approval before invoking.
4. **Act**: one-shot → `aeon-invoke.sh`; recurring → `aeon-enable-skill.sh` with a cron string.
5. **Confirm**: tell the user where to expect the result (their Aeon Telegram/Discord channel, or the next Hermes session via output ingestion).

To surface what Aeon did while the user was away, run `aeon-check-outputs.sh` and read the new `outputs/<skill>/<date>.md` files.

## Pitfalls

- **Not configured** → scripts exit with "AEON not configured". Tell the user to set the PAT + fork repo in Settings → AEON. Do not try to work around it.
- **workflow_dispatch ignores `var` from aeon.yml** → on manual invokes, always pass `var` explicitly via `aeon-invoke.sh <slug> <var>`. Scheduled cron runs read their configured var automatically.
- **`[SPEND]` skills** → the upstream catalog has `distribute-tokens` and `contributor-reward` that move money. Treat them as approval-required even if the manifest lacks the spend flag.
- **PAT scope** → a fine-grained PAT scoped to one repo breaks self-push on the fork. A classic PAT with `repo` + `workflow` is required.

## Verification

1. `bash scripts/aeon-list-skills.sh` → JSON-ish list including `heartbeat` and `morning-brief`. (401/403 = wrong PAT scope.)
2. `bash scripts/aeon-invoke.sh heartbeat` → prints a dispatch confirmation. (Failure here = missing `workflow` scope.)
3. Check `https://github.com/<aeon_fork_repo>/actions` → a Heartbeat run appears within ~2 min. (No run = fork missing `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` secret.)
