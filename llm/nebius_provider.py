from __future__ import annotations

from config import Settings
from llm.base import extract_json_text


class NebiusProvider:
    """Open models hosted on Nebius Token Factory.

    Token Factory exposes an OpenAI-compatible chat completions API, so the
    ``openai`` SDK is pointed at the Nebius base URL (``NEBIUS_BASE_URL``; the
    legacy AI Studio endpoint ``https://api.studio.nebius.com/v1/`` also
    works). JSON mode is requested natively, with ``extract_json_text`` as a
    safety net for models that wrap the payload anyway.
    """

    name = "nebius"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        if settings.nebius_api_key:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.nebius_api_key,
                base_url=settings.nebius_base_url,
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete_json(self, *, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.settings.nebius_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        return extract_json_text(raw) or "{}"

    def complete_text(self, *, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.settings.nebius_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""
