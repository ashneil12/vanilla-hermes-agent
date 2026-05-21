#!/usr/bin/env bash
# aeon-setup.sh — ensure the user has an Aeon fork, creating one if needed.
#
# Resolution order: recorded in config -> existing fork of aaronjmars/aeon in
# the account -> fork aaronjmars/aeon. Persists the result to config.yaml and
# prints the owner/repo slug on stdout. Run this once before delegating; the
# other scripts then auto-resolve the fork.
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
echo "$repo"
{
  echo "Aeon fork ready: $repo"
  echo "NOTE: a freshly forked Aeon needs ANTHROPIC_API_KEY (or CLAUDE_CODE_OAUTH_TOKEN)"
  echo "      + a notification channel (Telegram/Discord/Slack) as Actions secrets before"
  echo "      scheduled runs work. Confirm with the user before the first autonomous run."
} >&2
