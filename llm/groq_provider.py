from __future__ import annotations

from config import Settings


class GroqProvider:
    """Groq-hosted open models via the OpenAI-style chat completions API."""

    name = "groq"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        if settings.groq_api_key:
            from groq import Groq

            self._client = Groq(api_key=settings.groq_api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete_json(self, *, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.settings.groq_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or "{}"

    def complete_text(self, *, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.settings.groq_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""
