#!/usr/bin/env bash
# aeon-setup.sh — ensure the user has an Aeon fork (creating one via the GitHub
# REST API if needed) and wire its run-eligibility gate. gh-free: curl + the PAT.
# Resolution: recorded in config -> existing fork of aaronjmars/aeon -> fork it.
# Prints the owner/repo slug on stdout.
set -euo pipefail
source "$(dirname "$0")/_lib.sh"
_aeon_load_pat
command -v curl >/dev/null 2>&1 || { echo "curl not on PATH" >&2; exit 127; }

repo="$(_aeon_repo_from_config)"
[[ -z "$repo" ]] && repo="$(_aeon_discover_fork)"

if [[ -z "$repo" ]]; then
  echo "No Aeon fork found — forking aaronjmars/aeon into your account..." >&2
  _aeon_api POST "repos/aaronjmars/aeon/forks" '{}' >/dev/null 2>&1 || true
  # Forks are created asynchronously — poll briefly for it to appear.
  for _ in $(seq 1 15); do
    repo="$(_aeon_discover_fork)"; [[ -n "$repo" ]] && break
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
  _aeon_set_var() {  # create-or-update an Actions variable
    local name="$1" val="$2" body
    body="$(NAME="$name" VAL="$val" python3 -c "import os,json;print(json.dumps({'name':os.environ['NAME'],'value':os.environ['VAL']}))")"
    _aeon_api POST "repos/$repo/actions/variables" "$body" >/dev/null 2>&1 \
      || _aeon_api PATCH "repos/$repo/actions/variables/$name" "$body" >/dev/null 2>&1
  }
  if _aeon_set_var HERMES_AEON_GATE_URL "$HERMES_AEON_GATE_URL" \
     && _aeon_set_var HERMES_INSTANCE_ID "$HERMES_INSTANCE_ID"; then
    echo "Run-eligibility gate wired (instance $HERMES_INSTANCE_ID)." >&2
  else
    echo "WARN: could not set gate repo variables. Scheduled runs won't be pause-gated." >&2
  fi
fi

echo "$repo"
{
  echo "Aeon fork ready: $repo"
  echo "NOTE: a freshly forked Aeon needs ANTHROPIC_API_KEY (or CLAUDE_CODE_OAUTH_TOKEN)"
  echo "      + a notification channel (Telegram/Discord/Slack) as Actions secrets before"
  echo "      scheduled runs work. Confirm with the user before the first autonomous run."
} >&2
