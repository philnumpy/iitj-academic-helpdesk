"""Thin wrapper around the ADK Runner: ask a question, get the answer plus a trace
(route, tool calls, cited sources, latency) used by the CLI and by the evaluation."""
import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from . import config
from .agents import build_multi_agent, build_single_agent

APP_NAME = "iitj_academic_helpdesk"
# ADK suggests Gemini context caching on every multi-agent run; irrelevant for Ollama.
logging.getLogger("google_adk").setLevel(logging.ERROR)
REFUSAL_PATTERN = re.compile(r"\b(i don't know|i do not know|i'm sorry|not (?:able|available)|cannot (?:find|answer)|"
                             r"could not find|no (?:course|information)|not (?:listed|found))\b", re.I)


class Helpdesk:
    def __init__(self, mode: str = "multi", model: str | None = None):
        self.mode, self.model = mode, model or config.CHAT_MODEL
        self.agent = build_multi_agent(self.model) if mode == "multi" else build_single_agent(self.model)
        self.sessions = InMemorySessionService()
        self.runner = Runner(agent=self.agent, app_name=APP_NAME, session_service=self.sessions)

    async def new_session(self, user_id: str = "student") -> str:
        s = await self.sessions.create_session(app_name=APP_NAME, user_id=user_id, session_id=uuid.uuid4().hex)
        return s.id

    async def ask_async(self, question: str, session_id: str | None = None, user_id: str = "student") -> dict:
        session_id = session_id or await self.new_session(user_id)
        msg = types.Content(role="user", parts=[types.Part(text=question)])
        trace = {"question": question, "mode": self.mode, "model": self.model, "agents": [], "route": None,
                 "tool_calls": [], "sources": [], "answer": "", "error": None,
                 "llm_calls": 0, "prompt_tokens": 0, "output_tokens": 0}
        t0 = time.time()
        try:
            async for ev in self.runner.run_async(user_id=user_id, session_id=session_id, new_message=msg):
                if ev.author and ev.author != "user" and (not trace["agents"] or trace["agents"][-1] != ev.author):
                    trace["agents"].append(ev.author)
                if ev.usage_metadata and not ev.partial:
                    trace["llm_calls"] += 1
                    trace["prompt_tokens"] += ev.usage_metadata.prompt_token_count or 0
                    trace["output_tokens"] += ev.usage_metadata.candidates_token_count or 0
                for fc in ev.get_function_calls():
                    trace["tool_calls"].append({"agent": ev.author, "tool": fc.name, "args": dict(fc.args or {})})
                    if fc.name == "transfer_to_agent":
                        trace["route"] = (fc.args or {}).get("agent_name")
                for fr in ev.get_function_responses():
                    trace["sources"].extend(_sources(fr.response))
                    # Deterministic tools write the final answer themselves (skip_summarization)
                    if ev.actions.skip_summarization and isinstance(fr.response, dict) and fr.response.get("answer"):
                        trace["answer"] = fr.response["answer"]
                if ev.content and ev.content.parts and not ev.partial:
                    text = "".join(p.text or "" for p in ev.content.parts if not getattr(p, "thought", False)).strip()
                    if text:
                        trace["answer"] = text
        except Exception as e:  # keep the evaluation running; record the failure
            trace["error"] = f"{type(e).__name__}: {e}"
        trace["latency_s"] = round(time.time() - t0, 1)
        trace["sources"] = list(dict.fromkeys(trace["sources"]))
        trace["answering_agent"] = trace["agents"][-1] if trace["agents"] else None
        trace["logged_unanswered"] = (any(c["tool"] == "log_unanswered_question" for c in trace["tool_calls"])
                                      or trace["answering_agent"] == "out_of_scope_agent")  # it logs by itself
        self._log(trace)
        return trace

    def ask(self, question: str, session_id: str | None = None) -> dict:
        return asyncio.run(self.ask_async(question, session_id))

    def _log(self, trace: dict):
        now = datetime.now().isoformat(timespec="seconds")
        # Safety net: if an agent refused but forgot to call the logging tool, log it for the human.
        if not trace["logged_unanswered"] and (trace["error"] or REFUSAL_PATTERN.search(trace["answer"] or "")
                                               or not trace["answer"]):
            entry = {"time": now, "question": trace["question"], "reason": trace["error"] or "agent could not answer",
                     "agent": trace["answering_agent"], "logged_by": "system"}
            trace["logged_unanswered"] = True
            with open(config.UNANSWERED_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        with open(config.INTERACTIONS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": now} | trace, ensure_ascii=False) + "\n")


def _sources(resp) -> list[str]:
    """Pull the cite_as strings out of a tool response (nested dicts/lists)."""
    out = []
    if isinstance(resp, dict):
        for k, v in resp.items():
            if k == "cite_as" and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_sources(v))
    elif isinstance(resp, list):
        for v in resp:
            out.extend(_sources(v))
    return out
