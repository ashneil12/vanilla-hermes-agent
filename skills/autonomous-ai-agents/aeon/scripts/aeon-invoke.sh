#!/usr/bin/env bash
# aeon-invoke.sh — dispatch an Aeon skill via workflow_dispatch.
# Usage: aeon-invoke.sh <slug> [var]
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

SKILL="${1:?Usage: aeon-invoke.sh <slug> [var]}"
VAR="${2:-}"
_aeon_load_config

if [[ -n "$VAR" ]]; then
  GH_TOKEN="$AEON_PAT" gh workflow run aeon.yml --repo "$AEON_FORK_REPO" -f skill="$SKILL" -f var="$VAR"
else
  GH_TOKEN="$AEON_PAT" gh workflow run aeon.yml --repo "$AEON_FORK_REPO" -f skill="$SKILL"
fi

echo "Dispatched: $SKILL${VAR:+ (var=$VAR)} on $AEON_FORK_REPO"
echo "Watch: GH_TOKEN=\$AEON_PAT gh run watch --repo $AEON_FORK_REPO"
