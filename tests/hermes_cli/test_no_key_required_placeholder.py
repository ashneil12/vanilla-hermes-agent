"""Regression: the `no-key-required` sentinel must not be treated as a usable secret.

The resolver assigns `no-key-required` to keyless/local endpoints so the OpenAI SDK
accepts a non-empty api_key. If `has_usable_secret` accepts it, the sentinel can land
in an explicit/candidate slot (e.g. propagated to `self._explicit_api_key` via a model
switch) and PREEMPT a real env-derived key (e.g. VENICE_API_KEY) — making resumed
sessions send `Bearer no-key-required` and 401 while fresh chats work.
"""
from hermes_cli.auth import has_usable_secret


def test_no_key_sentinels_are_not_usable_secrets():
    assert has_usable_secret("no-key-required") is False
    assert has_usable_secret("no-key") is False
    assert has_usable_secret("NO-KEY-REQUIRED") is False  # case-insensitive


def test_real_secret_still_usable():
    assert has_usable_secret("VENICE_INFERENCE_KEY_GvQaE5O2laUM9KfulyxiYE") is True
    assert has_usable_secret("sk-or-v1-0123456789abcdef") is True


def test_custom_base_url_resolves_openai_api_key(monkeypatch):
    """HermesOS stores a custom provider's per-instance key in OPENAI_API_KEY paired
    with its base_url. Resolution must use it for a configured custom (non-openai.com)
    endpoint instead of falling through to 'no-key-required' — which 401s on resume.
    Covers venice/groq/gemini/nous/xai/bankr/crof/opengateway (all provider=custom).
    """
    from hermes_cli.runtime_provider import resolve_runtime_provider
    monkeypatch.setenv("OPENAI_API_KEY", "sk-hermesos-customkey-1234567890")
    for v in ("GROQ_API_KEY", "VENICE_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    for base in ("https://api.groq.com/openai/v1", "https://api.venice.ai/api/v1",
                 "https://api.x.ai/v1", "https://inference-api.nousresearch.com/v1"):
        r = resolve_runtime_provider(requested="custom", explicit_base_url=base)
        assert r["api_key"] == "sk-hermesos-customkey-1234567890", f"{base} -> {r['api_key']!r}"
