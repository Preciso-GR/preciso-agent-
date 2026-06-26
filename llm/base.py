from __future__ import annotations

import json
from typing import Protocol


class LLMProvider(Protocol):
    """Provider-agnostic LLM surface used by the agent.

    The agent only needs two shapes:
      - complete_json: a completion the caller will json.loads()
      - complete_text: a free-form prose completion

    Each provider owns its own wire format (Groq uses OpenAI-style JSON mode;
    Anthropic/Bedrock are prompt-driven and reject sampling params), so the
    agent code stays identical across providers.
    """

    name: str

    @property
    def available(self) -> bool:
        ...

    def complete_json(self, *, system: str, user: str) -> str:
        ...

    def complete_text(self, *, system: str, user: str) -> str:
        ...


# Appended to JSON system prompts for providers without a native JSON mode, so
# Claude returns a bare object instead of a fenced/annotated one.
JSON_ONLY_SUFFIX = (
    "\n\nReturn ONLY the raw JSON value. Do not wrap it in Markdown code fences, "
    "do not prefix it with a label, and do not add any commentary before or after it."
)


def extract_json_text(raw: str) -> str:
    """Best-effort recovery of a JSON document from a model reply.

    Strips Markdown code fences and leading/trailing prose so the result is
    safe to hand to json.loads(). Returns the original string if no better
    candidate is found.
    """
    text = raw.strip()
    if text.startswith("```"):
        # Drop the opening fence (``` or ```json) and the closing fence.
        body = text.split("```", 2)
        if len(body) >= 2:
            fenced = body[1]
            if "\n" in fenced:
                fenced = fenced.split("\n", 1)[1]
            text = fenced.strip()

    # Trim to the outermost JSON object/array if there is surrounding prose.
    start = min(
        (pos for pos in (text.find("{"), text.find("[")) if pos != -1),
        default=-1,
    )
    if start > 0:
        text = text[start:]
    return text.strip()


def looks_like_json(raw: str) -> bool:
    try:
        json.loads(extract_json_text(raw))
        return True
    except (json.JSONDecodeError, ValueError):
        return False
