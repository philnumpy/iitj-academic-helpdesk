"""Guardrails, implemented as Google ADK callbacks so they apply inside the agent framework:

1. Input  (before_agent_callback on the entry agent): blocks prompt-injection / prompt-extraction attempts
   and requests that break academic integrity (forged certificates, cheating, proxy attendance) before
   any LLM sees them.
2. Output (after_model_callback on every LLM agent):
   * prompt-leak filter - if a reply reproduces any run of 8 consecutive words from the agents'
     confidential instructions, it is replaced by a refusal;
   * internal-name filter - tool, agent and field names (e.g. "Source: cite_as = None") are removed;
   * e-mail filter - @iitj.ac.in addresses that appear neither in the faculty directory nor in the
     indexed documents are removed, so a hallucinated address never reaches a student;
   * qwen3 "<think>" blocks are stripped.
3. The instructions themselves (agents.py) tell every agent to keep its instructions confidential.

Every block is written to logs/guardrail_events.jsonl.
"""
import json
import re
from datetime import datetime
from functools import lru_cache

import pandas as pd
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from . import config

GUARDRAIL_LOG = config.LOG_DIR / "guardrail_events.jsonl"

PROMPT_REFUSAL = ("I can't share my instructions or internal configuration, and I can't change how I work. "
                  "I'm happy to help with IIT Jodhpur academic questions: programs, courses, timetables, "
                  "rules and regulations, or e-mails to instructors.")
INTEGRITY_REFUSAL = ("I can't help with that: it would violate IIT Jodhpur's academic integrity rules. "
                     "If you have a genuine problem (illness, a missed exam, low attendance), I can explain the "
                     "rules or draft an honest e-mail to your instructor.")

# Phrasings used to extract or override a system prompt. Kept specific ("your/system/hidden prompt")
# so that ordinary questions such as "what are the instructions for the minor exam?" still pass.
INJECTION = re.compile("|".join([
    r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(instructions?|rules|prompts?|guidelines|guardrails|restrictions)\b",
    r"\b(your|system|hidden|initial|original|secret|internal|developer|base)\s+(prompts?|instructions?|message|rules|guidelines|configuration|directives)\b",
    r"\b(reveal|show|print|repeat|output|display|dump|leak|expose|share|translate|summari[sz]e|paraphrase|encode|spell out)\b.{0,50}\bprompts?\b",
    r"\b(repeat|print|output|copy)\b.{0,30}\b(everything|text|words|all)\b.{0,20}\b(above|before|earlier|so far)\b",
    r"\bwhat (were you|are you) (told|instructed|programmed)\b|\bhow (were|are) you (instructed|programmed|configured|prompted)\b",
    r"\b(jailbreak|developer mode|dan mode|do anything now|god mode)\b",
    r"\b(pretend|act|behave|roleplay|role-play)\b.{0,30}\b(unrestricted|no (rules|restrictions|limits)|different (ai|assistant|model)|without (rules|restrictions))\b",
    r"\byou are (now|no longer)\b",
    r"\b(base64|rot13|hex)\b.{0,40}\b(instructions?|prompts?|rules)\b",
]), re.I)

INTEGRITY = re.compile("|".join([
    r"\b(fake|forge[ds]?|forging|fabricate[ds]?|counterfeit|falsif(y|ied))\b.{0,40}\b(medical|certificate|document|signature|note|attendance|leave|letter|grade|marksheet|transcript)",
    r"\bproxy\b.{0,20}\battendance\b|\b(mark|give)\b.{0,15}\b(my|me)\b.{0,15}\battendance\b.{0,20}\b(absent|without|proxy)",
    r"\bcheat(ing)?\b.{0,30}\b(exam|test|quiz|minor|major|assignment)|\b(exam|test|quiz)\b.{0,20}\bcheat",
    r"\b(leak(ed)?|get|obtain|steal)\b.{0,30}\b(question paper|exam paper|answer key)\b",
    r"\b(give|send|share|tell|provide)\s+(me\s+|us\s+)?(the\s+)?(answers|solutions)\s+(for|to|of)\b.{0,30}\b(exam|minor|major|quiz|test|paper)\b",
    r"\b(hack|break into)\b.{0,30}\b(erp|portal|grades?|records?)\b|\bchange my (grade|marks|attendance)\b",
]), re.I)

_THINK = re.compile(r"<think>.*?</think>\s*", re.S)
# Tool, agent and field names are internal: small models sometimes cite them ("Source: cite_as = None")
_INTERNAL = re.compile(r"\b(transfer_to_agent|search_documents|log_unanswered_question|lookup_course|draft_email|"
                       r"get_slot_timings|list_courses|find_instructor|find_faculty|cite_as|policy_agent|"
                       r"schedule_agent|email_agent|out_of_scope_agent|about_agent|helpdesk_orchestrator)\b|/no_think",
                       re.I)
_EMAIL = re.compile(r"[\w.+-]+@iitj\.ac\.in", re.I)


def _log(kind: str, agent: str, text: str):
    entry = {"time": datetime.now().isoformat(timespec="seconds"), "guardrail": kind, "agent": agent, "text": text[:500]}
    with open(GUARDRAIL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _reply(text: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=text)])


# --------------------------------------------------------------------------- input
def check_input(question: str) -> str | None:
    """Return a refusal for a blocked request, else None."""
    if INJECTION.search(question):
        return PROMPT_REFUSAL
    if INTEGRITY.search(question):
        return INTEGRITY_REFUSAL
    return None


def input_guardrail(callback_context: CallbackContext) -> types.Content | None:
    content = callback_context.user_content
    question = "".join(p.text or "" for p in (content.parts if content else []))
    refusal = check_input(question)
    if refusal:
        _log("input_injection" if refusal == PROMPT_REFUSAL else "input_integrity", callback_context.agent_name, question)
        return _reply(refusal)  # ADK skips the agent and returns this instead
    return None


# --------------------------------------------------------------------------- output
_PROTECTED: list[str] = []      # confidential instruction texts, registered by agents.py
_ALLOWED: list[str] = []        # texts the agents are told to say verbatim (refusals, exam rule, identity)


def protect(instructions: list[str], allowed_outputs: list[str]):
    _PROTECTED[:] = instructions
    _ALLOWED[:] = allowed_outputs


def _shingles(text: str, n: int = 8) -> set[tuple]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


@lru_cache(maxsize=1)
def _secret_shingles() -> frozenset:
    allowed = set().union(*(_shingles(t) for t in _ALLOWED)) if _ALLOWED else set()
    secret = set().union(*(_shingles(t) for t in _PROTECTED)) if _PROTECTED else set()
    return frozenset(secret - allowed)


def leaks_prompt(text: str) -> bool:
    return bool(_shingles(text) & _secret_shingles())


@lru_cache(maxsize=1)
def known_emails() -> frozenset:
    emails = set()
    fac = pd.read_csv(config.FACULTY_CSV, dtype=str).fillna("")
    for col in ("Email ID", "Other Email IDs"):
        for cell in fac[col]:
            emails.update(e.lower() for e in _EMAIL.findall(cell))
    from .retriever import get_retriever  # documents mention office addresses such as examhelp@iitj.ac.in
    for doc in get_retriever().docs:
        emails.update(e.lower() for e in _EMAIL.findall(doc))
    return frozenset(emails)


def _scrub_internal(text: str) -> str:
    """Drop "Source:" lines that name a tool or field instead of a document; remove the names elsewhere."""
    text = re.sub(r"[ \t]*\bsources?\s*:[^\n]*", lambda m: "" if _INTERNAL.search(m.group()) else m.group(),
                  text, flags=re.I)
    text = _INTERNAL.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def output_guardrail(callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
    content = llm_response.content
    if not content or not content.parts or not any(p.text for p in content.parts):
        return None  # tool calls / transfers pass through
    text = "".join(p.text or "" for p in content.parts if not getattr(p, "thought", False))
    clean = _THINK.sub("", text).strip()
    if leaks_prompt(clean):
        _log("output_prompt_leak", callback_context.agent_name, clean)
        clean = PROMPT_REFUSAL
    if _INTERNAL.search(clean):
        _log("output_internal_name", callback_context.agent_name, clean)
        clean = _scrub_internal(clean)
    unknown = [e for e in _EMAIL.findall(clean) if e.lower() not in known_emails()]
    for e in unknown:
        _log("output_unverified_email", callback_context.agent_name, e)
        clean = clean.replace(e, "[unverified e-mail address removed]")
    if clean == text:
        return None
    parts = [p for p in content.parts if not p.text] + [types.Part(text=clean)]
    return LlmResponse(content=types.Content(role=content.role or "model", parts=parts),
                       usage_metadata=llm_response.usage_metadata)
