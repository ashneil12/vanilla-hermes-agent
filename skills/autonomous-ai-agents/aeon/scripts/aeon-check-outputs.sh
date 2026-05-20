#!/usr/bin/env bash
# aeon-check-outputs.sh — list commits touching outputs/ since a timestamp.
# Usage: aeon-check-outputs.sh [ISO-timestamp]   (default: 24 hours ago)
set -euo pipefail
source "$(dirname "$0")/_lib.sh"
_aeon_load_config

SINCE_ISO="${1:-}"
if [[ -z "$SINCE_ISO" ]]; then
  if date -u -v-24H +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
    SINCE_ISO=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)   # BSD/macOS
  else
    SINCE_ISO=$(date -u -d "24 hours ago" +%Y-%m-%dT%H:%M:%SZ)  # GNU
  fi
fi

GH_TOKEN="$AEON_PAT" gh api \
  "repos/$AEON_FORK_REPO/commits?path=outputs&since=$SINCE_ISO" \
  --jq '.[] | "\(.sha[:7])  \(.commit.author.date)  \(.commit.message | split("\n")[0])"'
