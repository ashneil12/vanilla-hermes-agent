from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "docker" / "entrypoint.sh"


def test_bind_mounted_config_chown_happens_before_privilege_drop():
    text = ENTRYPOINT.read_text(encoding="utf-8")

    root_phase, non_root_phase = text.split("# --- Running as hermes from here ---", maxsplit=1)

    assert '"$HERMES_HOME/config.yaml"' in root_phase
    assert "chown hermes:hermes \"$managed_file\"" in root_phase
    assert "chown hermes:hermes \"$HERMES_HOME/config.yaml\"" not in non_root_phase

