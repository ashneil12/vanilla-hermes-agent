# _lib.sh — shared helpers for the aeon skill. Source this; don't execute it.
#
# Loads AEON_PAT and AEON_FORK_REPO from ~/.hermes/config.yaml (skills.config.*),
# unless already set in the environment (env wins, for testing). Exits non-zero
# with a user-facing message if AEON is not configured.

_aeon_load_config() {
  if [[ -n "${AEON_PAT:-}" && -n "${AEON_FORK_REPO:-}" ]]; then
    return 0
  fi

  command -v python3 >/dev/null 2>&1 || { echo "python3 not on PATH" >&2; return 127; }
  local cfg="${HERMES_HOME:-$HOME/.hermes}/config.yaml"

  local loaded
  loaded="$(CFG="$cfg" python3 <<'PY'
import os, sys
cfg = os.environ["CFG"]
try:
    import yaml
except Exception:
    sys.exit(0)  # no yaml -> emit nothing, fall through to "not configured"
try:
    with open(cfg) as fh:
        data = yaml.safe_load(fh) or {}
except FileNotFoundError:
    sys.exit(0)
except Exception as exc:
    print(f"# config parse error: {exc}", file=sys.stderr)
    sys.exit(0)
sc = (((data.get("skills") or {}).get("config")) or {})
pat = str(sc.get("aeon_github_pat") or "")
repo = str(sc.get("aeon_fork_repo") or "")
# Tab-separated so values with spaces survive.
print(pat + "\t" + repo)
PY
)"

  if [[ -n "$loaded" ]]; then
    AEON_PAT="${AEON_PAT:-$(printf '%s' "$loaded" | cut -f1)}"
    AEON_FORK_REPO="${AEON_FORK_REPO:-$(printf '%s' "$loaded" | cut -f2)}"
  fi

  if [[ -z "${AEON_PAT:-}" || -z "${AEON_FORK_REPO:-}" ]]; then
    echo "AEON not configured. Set the GitHub PAT + fork repo in Settings -> AEON." >&2
    return 1
  fi

  export AEON_PAT AEON_FORK_REPO
}
