#!/usr/bin/env bash
# aeon-enable-skill.sh — enable a skill in aeon.yml and commit the change.
# Usage: aeon-enable-skill.sh <slug> <cron-string|workflow_dispatch>
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

SLUG="${1:?Usage: aeon-enable-skill.sh <slug> <cron-string|workflow_dispatch>}"
SCHEDULE="${2:?Usage: aeon-enable-skill.sh <slug> <cron-string|workflow_dispatch>}"
_aeon_load_config

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

GH_TOKEN="$AEON_PAT" gh api -H "Accept: application/vnd.github.raw" \
  "repos/$AEON_FORK_REPO/contents/aeon.yml" > "$TMPDIR/aeon.yml"
SHA=$(GH_TOKEN="$AEON_PAT" gh api "repos/$AEON_FORK_REPO/contents/aeon.yml" --jq '.sha')

SLUG="$SLUG" SCHEDULE="$SCHEDULE" SRC="$TMPDIR/aeon.yml" python3 <<'PY'
import os, re, pathlib, sys
p = pathlib.Path(os.environ["SRC"])
slug, schedule = os.environ["SLUG"], os.environ["SCHEDULE"]
text = p.read_text()
pattern = re.compile(r'^(\s+)' + re.escape(slug) + r':\s*\{[^}]*\}\s*(#.*)?$', re.MULTILINE)
m = pattern.search(text)
if not m:
    sys.exit(f"Skill '{slug}' not found in aeon.yml — check spelling against aeon-list-skills.sh")
indent, trailing = m.group(1), (m.group(2) or "")
suffix = f" {trailing}" if trailing else ""
new_line = f'{indent}{slug}: {{ enabled: true, schedule: "{schedule}" }}{suffix}'
text = pattern.sub(lambda _: new_line, text, count=1)
p.write_text(text)
PY

CONTENT=$(base64 < "$TMPDIR/aeon.yml" | tr -d '\n')
GH_TOKEN="$AEON_PAT" gh api --method PUT \
  "repos/$AEON_FORK_REPO/contents/aeon.yml" \
  -f message="hermes: enable $SLUG (schedule: $SCHEDULE)" \
  -f content="$CONTENT" \
  -f sha="$SHA" >/dev/null

echo "Enabled $SLUG with schedule: $SCHEDULE"
echo "See https://github.com/$AEON_FORK_REPO/actions"
