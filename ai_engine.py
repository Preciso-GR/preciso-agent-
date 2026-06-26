from __future__ import annotations

from agent_llm import AgentLLM
from config import get_settings


settings = get_settings()
llm_engine = AgentLLM(settings)
