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

import pytest

import model_tools  # noqa: F401 — import triggers discover_builtin_tools()
from tools.registry import registry
from toolsets import get_toolset, resolve_toolset
import tools.audio_generate_tool as audio_mod


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
