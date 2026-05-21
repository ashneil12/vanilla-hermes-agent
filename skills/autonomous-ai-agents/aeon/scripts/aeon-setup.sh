#!/usr/bin/env bash
# aeon-setup.sh — ensure the user has an Aeon fork, creating one if needed, and
# wire its run-eligibility gate.
#
# Resolution order: recorded in config -> existing fork of aaronjmars/aeon in
# the account -> fork aaronjmars/aeon. Persists the result to config.yaml and
# prints the owner/repo slug on stdout. If HERMES_INSTANCE_ID + HERMES_AEON_GATE_URL
# are present in the env (the dashboard injects them), also sets them as repo
# variables so the fork's gate job skips scheduled work while this instance is
# paused/stopped/suspended.
set -euo pipefail
source "$(dirname "$0")/_lib.sh"
_aeon_load_pat
command -v gh >/dev/null 2>&1 || { echo "gh CLI not on PATH" >&2; exit 127; }

repo="$(_aeon_repo_from_config)"
[[ -z "$repo" ]] && repo="$(_aeon_discover_fork)"

if [[ -z "$repo" ]]; then
  echo "No Aeon fork found — forking aaronjmars/aeon into your account..." >&2
  GH_TOKEN="$AEON_PAT" gh repo fork aaronjmars/aeon --clone=false >&2 || true
  user="$(GH_TOKEN="$AEON_PAT" gh api user --jq .login 2>/dev/null || echo "")"
  # Forks are created asynchronously — poll briefly for it to appear.
  for _ in $(seq 1 15); do
    repo="$(_aeon_discover_fork)"; [[ -n "$repo" ]] && break
    if [[ -n "$user" ]] && GH_TOKEN="$AEON_PAT" gh api "repos/$user/aeon" >/dev/null 2>&1; then
      repo="$user/aeon"; break
    fi
    sleep 2
  done
fi

[[ -z "$repo" ]] && { echo "Could not discover or create an Aeon fork." >&2; exit 1; }

_aeon_persist_repo "$repo"

# --- Wire the run-eligibility gate (best-effort) ---------------------------
# The dashboard injects HERMES_INSTANCE_ID + HERMES_AEON_GATE_URL into this
# container. Setting them as repo variables arms the fork's `gate` job, which
# skips scheduled work whenever the dashboard reports the instance inactive.
if [[ -n "${HERMES_INSTANCE_ID:-}" && -n "${HERMES_AEON_GATE_URL:-}" ]]; then
  if GH_TOKEN="$AEON_PAT" gh variable set HERMES_AEON_GATE_URL --repo "$repo" --body "$HERMES_AEON_GATE_URL" >/dev/null 2>&1 \
     && GH_TOKEN="$AEON_PAT" gh variable set HERMES_INSTANCE_ID --repo "$repo" --body "$HERMES_INSTANCE_ID" >/dev/null 2>&1; then
    echo "Run-eligibility gate wired (instance $HERMES_INSTANCE_ID)." >&2
  else
    echo "WARN: could not set gate repo variables (PAT scope?). Scheduled runs won't be pause-gated." >&2
  fi
  # The `gate` job itself must exist in the fork's messages.yml. It ships in
  # aaronjmars/aeon (upstream PR) so forks inherit it; if a fork predates that,
  # the variables are harmless no-ops until the workflow is updated.
fi

echo "$repo"
{
  echo "Aeon fork ready: $repo"
  echo "NOTE: a freshly forked Aeon needs ANTHROPIC_API_KEY (or CLAUDE_CODE_OAUTH_TOKEN)"
  echo "      + a notification channel (Telegram/Discord/Slack) as Actions secrets before"
  echo "      scheduled runs work. Confirm with the user before the first autonomous run."
} >&2
