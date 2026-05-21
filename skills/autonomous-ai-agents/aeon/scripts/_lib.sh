# _lib.sh — shared helpers for the aeon skill. Source this; don't execute it.
#
# Token-only model: the user pastes a GitHub PAT in Settings -> AEON
# (skills.config.aeon_github_pat). The fork repo is NOT required up front —
# _aeon_load_config resolves it from config, else auto-discovers the user's
# existing fork of aaronjmars/aeon. The fork is CREATED only by aeon-setup.sh,
# never as a side effect of a read. Env vars (AEON_PAT/AEON_FORK_REPO) win.

_aeon_cfg_path() { echo "${HERMES_HOME:-$HOME/.hermes}/config.yaml"; }

# Load AEON_PAT from config.yaml (required). Exits non-zero with a message.
_aeon_load_pat() {
  [[ -n "${AEON_PAT:-}" ]] && { export AEON_PAT; return 0; }
  command -v python3 >/dev/null 2>&1 || { echo "python3 not on PATH" >&2; return 127; }
  AEON_PAT="$(CFG="$(_aeon_cfg_path)" python3 - <<'PY'
import os, sys
try:
    import yaml
    with open(os.environ["CFG"]) as fh:
        data = yaml.safe_load(fh) or {}
except Exception:
    sys.exit(0)
sc = (((data.get("skills") or {}).get("config")) or {})
print(str(sc.get("aeon_github_pat") or ""))
PY
)"
  if [[ -z "${AEON_PAT:-}" ]]; then
    echo "AEON not configured. Paste a GitHub token in Settings -> AEON." >&2
    return 1
  fi
  export AEON_PAT
}

# Read the recorded fork repo from config.yaml (may be empty).
_aeon_repo_from_config() {
  command -v python3 >/dev/null 2>&1 || return 0
  CFG="$(_aeon_cfg_path)" python3 - <<'PY'
import os, sys
try:
    import yaml
    with open(os.environ["CFG"]) as fh:
        data = yaml.safe_load(fh) or {}
except Exception:
    sys.exit(0)
sc = (((data.get("skills") or {}).get("config")) or {})
print(str(sc.get("aeon_fork_repo") or ""))
PY
}

# Discover an existing fork of aaronjmars/aeon in the authed account (read-only).
# Echoes owner/repo or nothing.
_aeon_discover_fork() {
  command -v gh >/dev/null 2>&1 || { echo ""; return 0; }
  GH_TOKEN="$AEON_PAT" gh repo list --fork --limit 200 --json nameWithOwner,parent \
    --jq '[.[] | select(.parent.nameWithOwner=="aaronjmars/aeon") | .nameWithOwner][0] // ""' 2>/dev/null || echo ""
}

# Persist the resolved repo into config.yaml so later calls + the WebUI see it.
_aeon_persist_repo() {
  local repo="${1:-}"; [[ -z "$repo" ]] && return 0
  command -v python3 >/dev/null 2>&1 || return 0
  CFG="$(_aeon_cfg_path)" REPO="$repo" python3 - <<'PY'
import os
try:
    import yaml
except Exception:
    raise SystemExit(0)
cfg = os.environ["CFG"]
try:
    with open(cfg) as fh:
        data = yaml.safe_load(fh) or {}
except FileNotFoundError:
    data = {}
except Exception:
    raise SystemExit(0)
data.setdefault("skills", {}).setdefault("config", {})["aeon_fork_repo"] = os.environ["REPO"]
try:
    with open(cfg, "w") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False)
except Exception:
    raise SystemExit(0)
PY
}

# For read/invoke scripts: ensure AEON_PAT + an EXISTING fork. Never creates —
# if no fork exists, points the agent at aeon-setup.sh.
_aeon_load_config() {
  _aeon_load_pat || return $?
  [[ -z "${AEON_FORK_REPO:-}" ]] && AEON_FORK_REPO="$(_aeon_repo_from_config)"
  if [[ -z "${AEON_FORK_REPO:-}" ]]; then
    AEON_FORK_REPO="$(_aeon_discover_fork)"
    [[ -n "${AEON_FORK_REPO:-}" ]] && _aeon_persist_repo "$AEON_FORK_REPO"
  fi
  if [[ -z "${AEON_FORK_REPO:-}" ]]; then
    echo "No Aeon fork found for this account yet. Run: bash scripts/aeon-setup.sh" >&2
    return 1
  fi
  export AEON_PAT AEON_FORK_REPO
}
