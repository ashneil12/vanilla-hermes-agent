"""Tests for uv-tool install detection in the update path (issue #29700).

``uv tool install hermes-agent`` lives outside any venv, so the previous
``uv pip install --upgrade`` update path failed with ``No virtual
environment found``. ``is_uv_tool_install`` should detect this layout and
both the user-facing recommended command and the actual
``_cmd_update_pip`` subprocess invocation should switch to
``uv tool upgrade hermes-agent``.

Detection is restricted to properties of the running interpreter
(``sys.prefix`` / ``sys.executable``) so a pip/venv install on a machine
that also has ``uv tool install hermes-agent`` does not get misclassified.
"""
from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Managed-uv compatibility for tests that patch shutil.which
# ---------------------------------------------------------------------------
# The production code now uses ``ensure_uv()`` / ``update_managed_uv()``
# instead of ``shutil.which("uv")``.  Many tests in this file patch
# ``shutil.which`` to control whether uv is "available" — these autouse
# fixtures make the managed_uv functions delegate to the patched
# ``shutil.which`` so the existing test setup keeps working without
# per-test changes.
@pytest.fixture(autouse=True)
def _patch_managed_uv(request, tmp_path, monkeypatch):
    """Make managed_uv helpers follow shutil.which mocking in tests."""
    import shutil

    # _cmd_update_pip now calls ensure_uv_cache_env(), which mutates
    # os.environ['UV_CACHE_DIR']. Isolate HERMES_HOME to a throwaway tmp path and
    # drop any ambient UV_CACHE_DIR so that pin is deterministic and never touches
    # the runner's ~/.hermes; monkeypatch restores os.environ after each test.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)

    # resolve_uv delegates to shutil.which("uv") so that test patches
    # on shutil.which flow through naturally.
    def _fake_resolve_uv():
        return shutil.which("uv")

    def _fake_ensure_uv():
        return shutil.which("uv")

    def _fake_update_managed_uv():
        return None  # never actually self-update in tests

    with patch("hermes_cli.managed_uv.resolve_uv", side_effect=_fake_resolve_uv), \
         patch("hermes_cli.managed_uv.ensure_uv", side_effect=_fake_ensure_uv), \
         patch("hermes_cli.managed_uv.update_managed_uv", side_effect=_fake_update_managed_uv):
        yield


# ---------------------------------------------------------------------------
# is_uv_tool_install
# ---------------------------------------------------------------------------


class TestIsUvToolInstall:
    def test_returns_true_when_sys_prefix_matches_uv_tool_layout(self):
        from hermes_cli import config

        with patch.object(config.sys, "prefix", "/home/user/.local/share/uv/tools/hermes-agent"):
            assert config.is_uv_tool_install() is True

    def test_returns_true_when_sys_executable_matches_uv_tool_layout(self):
        """Some uv-tool layouts surface the marker on ``sys.executable`` (bin/python)."""
        from hermes_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(
                 config.sys,
                 "executable",
                 "/home/user/.local/share/uv/tools/hermes-agent/bin/python",
             ):
            assert config.is_uv_tool_install() is True

    def test_returns_false_when_neither_prefix_nor_executable_matches(self):
        from hermes_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(config.sys, "executable", "/usr/bin/python3"):
            assert config.is_uv_tool_install() is False

    def test_does_not_consult_uv_tool_list(self):
        """Detection must NOT shell out: ``uv tool list`` would false-positive
        when the active install is pip/venv but the machine also has
        ``uv tool install hermes-agent`` somewhere on disk. Copilot review on
        PR #29703 flagged this; the fix is to never call ``uv tool list``
        from the detection path."""
        from hermes_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(config.sys, "executable", "/usr/bin/python3"), \
             patch("subprocess.run") as mock_run:
            assert config.is_uv_tool_install() is False
            mock_run.assert_not_called()

    def test_case_insensitive_match(self):
        """Match must be case-insensitive — Windows paths preserve case
        (e.g. ``...AppData\\Local\\UV\\Tools\\hermes-agent``) and a case-sensitive
        check would miss them. We exercise the lower-cased compare path here
        without monkey-patching ``os.sep``, which would break the whole suite."""
        from hermes_cli import config

        with patch.object(
            config.sys, "prefix", "/HOME/USER/.local/share/UV/Tools/hermes-agent"
        ):
            assert config.is_uv_tool_install() is True

    def test_handles_empty_executable(self):
        from hermes_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(config.sys, "executable", ""):
            assert config.is_uv_tool_install() is False


# ---------------------------------------------------------------------------
# recommended_update_command_for_method
# ---------------------------------------------------------------------------


class TestRecommendedUpdateCommandForUvTool:
    def test_uv_tool_install_recommends_uv_tool_upgrade(self):
        from hermes_cli import config

        with patch("shutil.which", return_value="/usr/local/bin/uv"), \
             patch.object(config, "is_uv_tool_install", return_value=True):
            cmd = config.recommended_update_command_for_method("pip")
            assert cmd == "uv tool upgrade hermes-agent"

    def test_uv_tool_install_recommends_uv_tool_upgrade_even_without_uv_on_path(self):
        """Recommendation reflects the *install method*, not whether ``uv`` is
        currently on PATH — the user needs to know the right command to run."""
        from hermes_cli import config

        with patch("shutil.which", return_value=None), \
             patch.object(config, "is_uv_tool_install", return_value=True):
            cmd = config.recommended_update_command_for_method("pip")
            assert cmd == "uv tool upgrade hermes-agent"

    def test_uv_pip_install_keeps_legacy_recommendation(self):
        """Existing behavior: uv is on PATH but Hermes is a regular pip install."""
        from hermes_cli import config

        with patch("shutil.which", return_value="/usr/local/bin/uv"), \
             patch.object(config, "is_uv_tool_install", return_value=False):
            cmd = config.recommended_update_command_for_method("pip")
            assert cmd == "uv pip install --upgrade hermes-agent"

    def test_no_uv_falls_back_to_plain_pip(self):
        from hermes_cli import config

        with patch("shutil.which", return_value=None), \
             patch.object(config, "is_uv_tool_install", return_value=False):
            cmd = config.recommended_update_command_for_method("pip")
            assert cmd == "pip install --upgrade hermes-agent"

    def test_recommendation_does_not_spawn_subprocess(self):
        """Computing the recommendation string must be cheap — no ``uv tool list``
        spawn. Copilot review on PR #29703 flagged the prior subprocess hop
        as adding overhead and a multi-second timeout window for what is
        purely a display string."""
        from hermes_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(config.sys, "executable", "/usr/bin/python3"), \
             patch("shutil.which", return_value="/usr/local/bin/uv"), \
             patch("subprocess.run") as mock_run:
            cmd = config.recommended_update_command_for_method("pip")
            mock_run.assert_not_called()
            assert cmd == "uv pip install --upgrade hermes-agent"


# ---------------------------------------------------------------------------
# _cmd_update_pip subprocess command
# ---------------------------------------------------------------------------


class TestCmdUpdatePipUsesUvTool:
    @patch("subprocess.run")
    def test_runs_uv_tool_upgrade_when_uv_tool_install(self, mock_run):
        """The actual subprocess invocation must switch to ``uv tool upgrade``."""
        from hermes_cli.main import _cmd_update_pip

        mock_run.return_value = subprocess.CompletedProcess(["uv"], 0, stdout="", stderr="")
        with patch("shutil.which", return_value="/usr/local/bin/uv"), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=True):
            _cmd_update_pip(SimpleNamespace())

        assert mock_run.call_args[0][0] == ["/usr/local/bin/uv", "tool", "upgrade", "hermes-agent"]

    @patch("subprocess.run")
    def test_runs_uv_pip_install_when_not_uv_tool(self, mock_run):
        """Existing behavior preserved when uv is present but Hermes isn't a tool install."""
        from hermes_cli.main import _cmd_update_pip

        mock_run.return_value = subprocess.CompletedProcess(["uv"], 0, stdout="", stderr="")
        with patch("shutil.which", return_value="/usr/local/bin/uv"), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=False):
            _cmd_update_pip(SimpleNamespace())

        assert mock_run.call_args[0][0] == [
            "/usr/local/bin/uv",
            "pip",
            "install",
            "--upgrade",
            "hermes-agent",
        ]

    @patch("subprocess.run")
    def test_falls_back_to_pip_when_no_uv(self, mock_run):
        from hermes_cli.main import _cmd_update_pip

        mock_run.return_value = subprocess.CompletedProcess(["pip"], 0, stdout="", stderr="")
        with patch("shutil.which", return_value=None), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=False):
            _cmd_update_pip(SimpleNamespace())

        cmd = mock_run.call_args[0][0]
        assert cmd[1:] == ["-m", "pip", "install", "--upgrade", "hermes-agent"]

    @patch("subprocess.run")
    def test_exits_nonzero_on_subprocess_failure(self, mock_run):
        from hermes_cli.main import _cmd_update_pip

        mock_run.return_value = subprocess.CompletedProcess(["uv"], 1, stdout="", stderr="")
        with patch("shutil.which", return_value="/usr/local/bin/uv"), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                _cmd_update_pip(SimpleNamespace())
        assert exc_info.value.code == 1

    @patch("subprocess.run")
    def test_uv_tool_install_without_uv_on_path_exits_with_hint(self, mock_run):
        """If the running interpreter looks like a uv-tool install but ``uv`` is
        somehow missing from PATH, surface a clear hint instead of silently
        falling back to ``python -m pip``, which would either fail (no venv)
        or upgrade the wrong copy."""
        from hermes_cli.main import _cmd_update_pip

        with patch("shutil.which", return_value=None), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                _cmd_update_pip(SimpleNamespace())
        assert exc_info.value.code == 1
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# pipx-managed installs, --system fallback, and VIRTUAL_ENV overlay
# (issue #29700 / #35031 family — consolidated update-path handling)
# ---------------------------------------------------------------------------


class TestCmdUpdatePipInstallLayouts:
    """The uv pip path must adapt to where the running interpreter lives:

    - inside a venv (launcher shim)  -> export VIRTUAL_ENV, no ``--system``
    - bare pip outside any venv      -> add ``--system``, no overlay
    - pipx-managed                   -> ``pipx upgrade``
    """

    @patch("subprocess.run")
    def test_pipx_managed_uses_pipx_upgrade(self, mock_run, monkeypatch):
        from hermes_cli import main as hm

        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        monkeypatch.setattr(hm.sys, "prefix", "/home/u/.local/pipx/venvs/hermes-agent")
        monkeypatch.setattr(hm.sys, "base_prefix", "/usr")

        def _which(name):
            return {"uv": "/usr/bin/uv", "pipx": "/usr/bin/pipx"}.get(name)

        with patch("shutil.which", side_effect=_which), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=False):
            hm._cmd_update_pip(SimpleNamespace())

        assert mock_run.call_args[0][0] == ["/usr/bin/pipx", "upgrade", "hermes-agent"]
        # pipx upgrade ignores VIRTUAL_ENV; we must not set it.
        assert "env" not in mock_run.call_args.kwargs

    @patch("subprocess.run")
    def test_pipx_layout_without_pipx_binary_treated_as_venv(
        self, mock_run, monkeypatch
    ):
        from hermes_cli import main as hm

        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        monkeypatch.setattr(hm.sys, "prefix", "/home/u/.local/pipx/venvs/hermes-agent")
        monkeypatch.setattr(hm.sys, "base_prefix", "/usr")

        # pipx layout detected via prefix, but pipx binary missing on PATH.
        def _which(name):
            return "/usr/bin/uv" if name == "uv" else None

        with patch("shutil.which", side_effect=_which), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=False):
            hm._cmd_update_pip(SimpleNamespace())

        # prefix != base_prefix, so this is treated as a venv -> overlay, no --system.
        assert mock_run.call_args[0][0] == [
            "/usr/bin/uv", "pip", "install", "--upgrade", "hermes-agent",
        ]
        assert mock_run.call_args.kwargs["env"]["VIRTUAL_ENV"].endswith("hermes-agent")

    @patch("subprocess.run")
    def test_bare_pip_outside_venv_adds_system(self, mock_run, monkeypatch):
        from hermes_cli import main as hm

        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        # No venv: prefix == base_prefix.
        monkeypatch.setattr(hm.sys, "prefix", "/usr")
        monkeypatch.setattr(hm.sys, "base_prefix", "/usr")

        with patch("shutil.which", return_value="/usr/bin/uv"), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=False):
            hm._cmd_update_pip(SimpleNamespace())

        assert mock_run.call_args[0][0] == [
            "/usr/bin/uv", "pip", "install", "--system", "--upgrade", "hermes-agent",
        ]
        assert "env" not in mock_run.call_args.kwargs

    @patch("subprocess.run")
    def test_venv_exports_virtualenv_and_omits_system(self, mock_run, monkeypatch):
        from hermes_cli import main as hm

        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(hm.sys, "prefix", "/home/u/.hermes/hermes-agent/venv")
        monkeypatch.setattr(hm.sys, "base_prefix", "/usr")

        with patch("shutil.which", return_value="/usr/bin/uv"), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=False):
            hm._cmd_update_pip(SimpleNamespace())

        cmd = mock_run.call_args[0][0]
        assert "--system" not in cmd
        assert cmd == ["/usr/bin/uv", "pip", "install", "--upgrade", "hermes-agent"]
        assert mock_run.call_args.kwargs["env"]["VIRTUAL_ENV"] == "/home/u/.hermes/hermes-agent/venv"


# ---------------------------------------------------------------------------
# ensure_uv_cache_env — the cache-dir pin that survives a stale/foreign
# UV_CACHE_DIR (e.g. a /state/.env written before a HERMES_HOME migration moved
# the home from /home/hermeswebui to /home/hermes). Regression for the support
# report:
#   error: Failed to initialize cache at `/home/hermeswebui/.hermes/cache/uv`
#     Caused by: failed to create directory ...: Permission denied (os error 13)
# ---------------------------------------------------------------------------


class TestEnsureUvCacheEnv:
    def test_pins_cache_under_hermes_home_when_unset(self, tmp_path, monkeypatch):
        from hermes_cli import managed_uv

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.delenv("UV_CACHE_DIR", raising=False)

        result = managed_uv.ensure_uv_cache_env()

        assert result == str(tmp_path / "cache" / "uv")
        assert os.environ["UV_CACHE_DIR"] == str(tmp_path / "cache" / "uv")
        assert (tmp_path / "cache" / "uv").is_dir()

    def test_overrides_unwritable_inherited_cache(self, tmp_path, monkeypatch):
        """A UV_CACHE_DIR pointing at an uncreatable path (the foreign-home case)
        is replaced with the managed $HERMES_HOME/cache/uv path."""
        from hermes_cli import managed_uv

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        # A regular file blocks creating a dir beneath it -> NotADirectoryError,
        # standing in for "owned by another user / Permission denied".
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        monkeypatch.setenv("UV_CACHE_DIR", str(blocker / "uv"))

        managed_uv.ensure_uv_cache_env()

        assert os.environ["UV_CACHE_DIR"] == str(tmp_path / "cache" / "uv")

    def test_keeps_writable_inherited_cache(self, tmp_path, monkeypatch):
        """A user-set, writable UV_CACHE_DIR is honored, not clobbered."""
        from hermes_cli import managed_uv

        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
        custom = tmp_path / "custom-cache"
        monkeypatch.setenv("UV_CACHE_DIR", str(custom))

        result = managed_uv.ensure_uv_cache_env()

        assert result == str(custom)
        assert os.environ["UV_CACHE_DIR"] == str(custom)

    @patch("subprocess.run")
    def test_cmd_update_pip_pins_cache_before_upgrade(self, mock_run, tmp_path, monkeypatch):
        """The PyPI self-upgrade pins UV_CACHE_DIR (the reported brick) regardless
        of which install layout runs the upgrade."""
        from hermes_cli.main import _cmd_update_pip

        mock_run.return_value = subprocess.CompletedProcess(["uv"], 0, stdout="", stderr="")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        # Stand in for the stale/foreign /home/hermeswebui cache with an
        # uncreatable path (under a regular file) so it's unwritable even as root.
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        monkeypatch.setenv("UV_CACHE_DIR", str(blocker / "uv"))

        with patch("shutil.which", return_value="/usr/local/bin/uv"), \
             patch("hermes_cli.config.is_uv_tool_install", return_value=False):
            _cmd_update_pip(SimpleNamespace())

        assert os.environ["UV_CACHE_DIR"] == str(tmp_path / "cache" / "uv")
