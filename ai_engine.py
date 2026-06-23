from __future__ import annotations

from config import get_settings
from groq_client import GroqAgentClient


settings = get_settings()
llm_engine = GroqAgentClient(settings)

