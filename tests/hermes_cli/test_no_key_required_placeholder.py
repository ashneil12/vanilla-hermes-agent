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
