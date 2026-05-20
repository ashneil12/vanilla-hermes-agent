#!/usr/bin/env bash
# aeon-list-skills.sh — print available Aeon skills (slug, category, schedule, spend, description).
set -euo pipefail
source "$(dirname "$0")/_lib.sh"
_aeon_load_config

GH_TOKEN="$AEON_PAT" gh api \
  -H "Accept: application/vnd.github.raw" \
  "repos/$AEON_FORK_REPO/contents/skills.json" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
skills = data.get('skills', [])
print(f'# {len(skills)} skills in {data.get(\"repo\", \"\")}')
for s in skills:
    spend = ' [SPEND]' if s.get('spend') else ''
    sched = s.get('schedule') or '(on-demand)'
    print(f\"{s.get('slug')}  [{s.get('category')}]  sched={sched}{spend}\")
    print(f\"    {s.get('description', '')}\")
"
