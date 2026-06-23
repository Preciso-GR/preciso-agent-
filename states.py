from __future__ import annotations

from agent.workflow import PrecisoAgentWorkflow
from config import ensure_workspace, get_settings


def build_graph():
    settings = get_settings()
    ensure_workspace(settings)
    return PrecisoAgentWorkflow(settings).graph

