"""Entry point for the ADK developer UI:  adk web adk_agents   (then pick "academic_helpdesk")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from helpdesk.agents import build_multi_agent  # noqa: E402

root_agent = build_multi_agent()
