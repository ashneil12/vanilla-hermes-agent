"""Default SOUL.md seeded into HERMES_HOME on first run.

This fork ships as **Operator OS**: the default identity is the v3.8 Operator OS
brain (an opinionated Hormozi-style business co-founder), loaded from the bundled
profile when present. Falls back to a short generic Hermes identity if the
bundled file is missing (e.g. a partial checkout / installed wheel without the
profiles tree).
"""

from pathlib import Path

_FALLBACK_SOUL_MD = (
    "You are Hermes Agent, an intelligent AI assistant created by Nous Research. "
    "You are helpful, knowledgeable, and direct. You assist users with a wide "
    "range of tasks including answering questions, writing and editing code, "
    "analyzing information, creative work, and executing actions via your tools. "
    "You communicate clearly, admit uncertainty when appropriate, and prioritize "
    "being genuinely useful over being verbose unless otherwise directed below. "
    "Be targeted and efficient in your exploration and investigations."
)


def _load_default_soul() -> str:
    # Bundled at <repo>/profiles/operatoros/SOUL.md; this file is
    # <repo>/hermes_cli/default_soul.py, so parent.parent is the repo root.
    try:
        soul = (
            Path(__file__).resolve().parent.parent
            / "profiles" / "operatoros" / "SOUL.md"
        )
        if soul.is_file():
            text = soul.read_text(encoding="utf-8").strip()
            if text:
                return text
    except Exception:
        pass
    return _FALLBACK_SOUL_MD


DEFAULT_SOUL_MD = _load_default_soul()
