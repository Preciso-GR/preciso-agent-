from __future__ import annotations

from config import Settings
from llm.base import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Construct the configured LLM provider.

    ``groq`` (default), ``anthropic``, or ``bedrock`` — selected by
    ``LLM_PROVIDER``. Providers import their SDKs lazily, so installing only the
    one you use is enough.
    """
    provider = settings.llm_provider
    if provider == "anthropic":
        from llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    if provider == "bedrock":
        from llm.anthropic_provider import BedrockProvider

        return BedrockProvider(settings)
    if provider == "groq":
        from llm.groq_provider import GroqProvider

        return GroqProvider(settings)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Use one of: groq, anthropic, bedrock."
    )


__all__ = ["build_llm_provider", "LLMProvider"]
