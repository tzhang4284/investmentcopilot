"""Claude client singleton and call-construction helpers.

All Claude calls go through here so model constraints stay enforced in one place:
claude-opus-4-8 rejects temperature/top_p/top_k/budget_tokens — never add them.
"""

from __future__ import annotations

from functools import lru_cache

from ...config import settings

MODEL_DEEP = "claude-opus-4-8"
MODEL_FAST = "claude-haiku-4-5"


def ai_available() -> bool:
    import os

    return bool(settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"))


@lru_cache(maxsize=1)
def get_client():
    import anthropic

    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()
