from __future__ import annotations

from config import Settings
from llm.base import JSON_ONLY_SUFFIX, extract_json_text

# Headroom for a full extraction payload while staying under the SDK's
# non-streaming HTTP timeout guard (~16K is the documented safe ceiling).
MAX_TOKENS = 16000


class _AnthropicStyleProvider:
    """Shared Messages-API logic for Claude on the Anthropic API and Bedrock.

    Both surfaces expose the identical ``client.messages.create`` shape. Note
    the current Claude models (Opus 4.8 / 4.7) reject ``temperature`` and have
    no OpenAI-style JSON mode, so JSON is enforced via the system prompt and
    recovered from the first text block.
    """

    name = "anthropic"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._model = ""

    @property
    def available(self) -> bool:
        return self._client is not None

    def _message(self, *, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()

    def complete_json(self, *, system: str, user: str) -> str:
        raw = self._message(system=system + JSON_ONLY_SUFFIX, user=user)
        return extract_json_text(raw) or "{}"

    def complete_text(self, *, system: str, user: str) -> str:
        return self._message(system=system, user=user)


class AnthropicProvider(_AnthropicStyleProvider):
    """Claude via the first-party Anthropic API."""

    name = "anthropic"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._model = settings.anthropic_model
        if settings.anthropic_api_key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


class BedrockProvider(_AnthropicStyleProvider):
    """Claude via Amazon Bedrock (AWS-native auth + billing).

    Credentials come from the standard AWS chain (env vars, shared profile,
    or instance/role); only the region is configured here. Model IDs carry the
    ``anthropic.`` prefix (e.g. ``anthropic.claude-opus-4-8``).
    """

    name = "bedrock"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._model = settings.bedrock_model
        if settings.aws_region:
            try:
                from anthropic import AnthropicBedrockMantle
            except ImportError as exc:  # pragma: no cover - surfaced to caller
                raise ImportError(
                    "Bedrock support needs the bedrock extra. Run: "
                    "pip install 'anthropic[bedrock]'"
                ) from exc
            self._client = AnthropicBedrockMantle(aws_region=settings.aws_region)
