"""Regression guard for media-generation tool wiring.

Each invariant below silently broke ``audio_generate`` in production at least
once (see the four audio fixes May 2026). They are network-free and key-free so
they run in CI and fail the build BEFORE a broken :stable image can ship — the
point being that an upstream sync or refactor can't quietly regress media gen
again.

Bug history these cover:
  1. Venice audio polled ``GET /audio/{id}`` (404) instead of the queue/retrieve
     flow → music requests hard-errored.
  2. ``audio_generate`` wasn't listed in the ``video_gen`` toolset definition →
     the LLM never saw the tool.
  3. The tool/system-prompt didn't steer code-biased models to the tool →
     they hand-rolled WAVs via the terminal/skills.
  4. The registered handler was ``lambda **kw:`` (zero positional params); the
     executor calls ``handler(args, **kwargs)`` → ``TypeError`` on every agent
     call (a direct function call masked it).
"""

import inspect
import os

import pytest

import model_tools  # noqa: F401 — import triggers discover_builtin_tools()
from tools.registry import registry
from toolsets import get_toolset, resolve_toolset, _HERMES_CORE_TOOLS
import tools.audio_generate_tool as audio_mod
import tools.image_generation_tool as image_mod
import tools.venice_extras_tool as extras_mod


class TestMediaToolWiring:
    def test_audio_generate_registered(self):
        assert registry.get_entry("audio_generate") is not None, (
            "audio_generate is not registered — discover_builtin_tools() should "
            "self-register it from tools/audio_generate_tool.py"
        )

    def test_audio_generate_member_of_video_gen_toolset(self):
        # Bug 2: a tool only reaches the model if its toolset definition lists it.
        assert "audio_generate" in get_toolset("video_gen")["tools"]
        assert "audio_generate" in resolve_toolset("video_gen")
        assert registry.get_entry("audio_generate").toolset == "video_gen"

    def test_sibling_media_tools_still_wired(self):
        assert "video_generate" in resolve_toolset("video_gen")
        assert "image_generate" in resolve_toolset("image_gen")

    def test_audio_handler_accepts_positional_args_dict(self):
        # Bug 4: the executor invokes ``entry.handler(args, **kwargs)``. A handler
        # that takes no positional parameter (``lambda **kw:``) raises TypeError
        # on every agent call. Verify the registered handler can bind a dict.
        handler = registry.get_entry("audio_generate").handler
        sig = inspect.signature(handler)
        try:
            sig.bind({"prompt": "x"})
        except TypeError:
            pytest.fail(
                "audio_generate handler must accept a positional args dict "
                "(executor calls handler(args, **kwargs)); got "
                f"signature {sig}"
            )

    def test_venice_queue_and_retrieve_endpoints(self):
        # Bug 1: Venice audio is POST /audio/queue then POST /audio/retrieve
        # (binary), NOT GET /audio/{queue_id}.
        src = inspect.getsource(audio_mod)
        assert "/audio/queue" in src
        assert "/audio/retrieve" in src, (
            "Venice audio must poll POST /audio/retrieve; a GET /audio/{id} poll 404s"
        )

    def test_media_generation_guidance_present_and_wired(self):
        # Bug 3: steer code-biased models to the tools instead of writing code.
        from agent.prompt_builder import MEDIA_GENERATION_GUIDANCE

        assert "audio_generate" in MEDIA_GENERATION_GUIDANCE
        import agent.system_prompt as sp

        assert "MEDIA_GENERATION_GUIDANCE" in inspect.getsource(sp), (
            "MEDIA_GENERATION_GUIDANCE must be appended in build_system_prompt_parts"
        )


# Native Venice extra tools (tools/venice_extras_tool.py). Same bug-4 handler
# invariant as audio_generate: the executor calls handler(args, **kwargs), so a
# zero-positional ``lambda **kw:`` handler TypeErrors on every agent call.
_EXTRA_TOOLS = {
    "image_styles": "image_gen",
    "text_parser": "web",
    "video_transcribe": "web",
    "voice_clone": "tts",
    "audio_quote": "video_gen",
    "video_quote": "video_gen",
    "crypto_rpc": "crypto",
}


class TestVeniceExtrasWiring:
    @pytest.mark.parametrize("tool,toolset", sorted(_EXTRA_TOOLS.items()))
    def test_extra_tool_registered_in_its_toolset(self, tool, toolset):
        entry = registry.get_entry(tool)
        assert entry is not None, f"{tool} not registered"
        assert entry.toolset == toolset, f"{tool} should be in toolset {toolset}"
        assert tool in resolve_toolset(toolset), f"{tool} missing from resolved {toolset}"

    @pytest.mark.parametrize("tool", sorted(_EXTRA_TOOLS))
    def test_extra_tool_in_core_composite(self, tool):
        # Without core membership the toolset's subset-check fails and the
        # whole toolset silently disappears from the LLM's tool list.
        assert tool in _HERMES_CORE_TOOLS, f"{tool} missing from _HERMES_CORE_TOOLS"

    @pytest.mark.parametrize("tool", sorted(_EXTRA_TOOLS))
    def test_extra_handler_accepts_positional_args_dict(self, tool):
        handler = registry.get_entry(tool).handler
        try:
            inspect.signature(handler).bind({"network": "list"})
        except TypeError:
            pytest.fail(f"{tool} handler must accept a positional args dict")

    def test_crypto_rpc_blocks_signing_methods(self, monkeypatch):
        # Read-only by design: state-changing/signing methods must be refused
        # BEFORE any network call (so this stays key-free/network-free).
        monkeypatch.setenv("VENICE_API_KEY", "test-key-not-used")
        import json as _json

        for m in ("eth_sendTransaction", "eth_sendRawTransaction", "personal_sign"):
            out = _json.loads(extras_mod.crypto_rpc_tool("ethereum", m))
            assert out["success"] is False
            assert out["error_type"] == "write_method_blocked", (
                f"{m} must be blocked; got {out}"
            )


class TestMediaConfigHonoring:
    """Guard the Settings → Media controls against becoming dead controls:
    the agent generators must read the config defaults the WebUI persists."""

    def test_audio_generate_reads_configured_model(self):
        assert hasattr(audio_mod, "_read_configured_audio_model")
        src = inspect.getsource(audio_mod.audio_generate_tool)
        assert "_read_configured_audio_model" in src, (
            "audio_generate must honor audio_gen.model so the Media music-model "
            "dropdown is a live control"
        )

    def test_image_generate_reads_configured_style(self):
        assert hasattr(image_mod, "_read_configured_image_style")
        src = inspect.getsource(image_mod._dispatch_to_plugin_provider)
        assert "style_preset" in src and "_read_configured_image_style" in src, (
            "image dispatch must forward image_gen.style_preset so the Media "
            "Style dropdown is a live control"
        )
