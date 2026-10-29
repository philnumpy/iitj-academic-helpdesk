"""Tools exposed to the agents. ADK turns each function signature + docstring into a tool declaration,
so docstrings are kept short (every token is re-read by the LLM on each call).

Two kinds of tools:
* search_documents returns passages that the LLM must read and summarise (RAG).
* The structured tools (timetable, people, e-mail) are deterministic. The LLM decides which one to call
  and extracts the arguments; the tool then writes the final, cited answer itself and sets ADK's
  `skip_summarization`, so the answer reaches the student verbatim. 3B-8B models frequently dropped or
  garbled these results (e.g. "I don't know" after a successful lookup, or an e-mail draft that was never
  shown) when asked to re-phrase them, and the extra LLM call cost minutes on a CPU.
"""
import json
import re
from datetime import datetime
from functools import lru_cache

import pandas as pd
from google.adk.tools import ToolContext
from rapidfuzz import fuzz, process

from . import config
from .retriever import get_retriever

FACULTY_SRC = config.FACULTY_CSV.name
HANDOFF = "Your question has been logged so that a human can answer it."


@lru_cache(maxsize=1)
def _courses() -> pd.DataFrame:
    df = pd.read_csv(config.COURSES_CSV, dtype=str).fillna("")
    df["co_instructor"] = df["co_instructor"].str.replace(r"\b\d{3,}-", "", regex=True)
    return df


@lru_cache(maxsize=1)
def _slots() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Weekly slot timings, minor-exam and major-exam schedules (one row per slot)."""
    return (pd.read_csv(config.SLOTS_CSV, dtype=str), pd.read_csv(config.EXAMS_CSV, dtype=str),
            pd.read_csv(config.MAJOR_EXAMS_CSV, dtype=str))


@lru_cache(maxsize=1)
def _faculty() -> pd.DataFrame:
    return pd.read_csv(config.FACULTY_CSV, dtype=str).fillna("")


def _final(result: dict, tool_context: ToolContext | None) -> dict:
    """Mark the tool result as the agent's final answer (no LLM re-phrasing)."""
    if tool_context is not None:
        tool_context.actions.skip_summarization = True
    if result.get("cite_as") and "Source:" not in result["answer"]:
        result["answer"] += f"\n\nSource: {result['cite_as']}"
    return result


def _fmt_time(t: str) -> str:
    """'9– 9:50' -> '9:00-9:50'."""
    def hm(x):
        x = x.strip()
        return x if ":" in x else f"{x}:00"
    m = re.match(r"\s*([\d:]+)\s*[-–]\s*([\d:]+)(.*)", t)
    return f"{hm(m.group(1))}-{hm(m.group(2))}{m.group(3)}" if m else t


def _course_record(r: pd.Series) -> dict:
    return {k: r[k] for k in ("code", "name", "credits", "ltp", "slot", "instructor", "co_instructor",
                              "department", "classroom", "remarks") if r[k]} | {"cite_as": r["source"]}


def _find_courses(query: str, limit: int = 5) -> pd.DataFrame:
    df = _courses()
    code = re.sub(r"\s+", "", query).upper()
    m = re.search(r"[A-Z]{2,4}\d{4,5}", code)
    if m:
        return df[df["code"] == m.group(0)].head(limit)
    hits = process.extract(query.lower(), df["name"].str.lower(), scorer=fuzz.token_set_ratio,
                           limit=limit * 3, score_cutoff=80)
    if not hits:
        return df.iloc[0:0]
    best = hits[0][1]
    idx = [i for _, score, i in hits if score >= best - 5]
    return df.loc[idx].head(limit)


# =========================================================================== RAG
def search_documents(query: str, tool_context: ToolContext = None) -> dict:
    """Search IIT Jodhpur academic documents (regulations, curricula, circulars, exam guidelines, people pages).

    Args:
        query: focused search query.
    """
    # Multi-query retrieval: also search with the student's own wording. The agent's rewritten query alone
    # retrieved the answer-bearing chunk for 3/8 failure cases, the fused pair for 6/8 (see REPORT.md).
    queries = [query]
    if tool_context is not None and tool_context.user_content:
        queries.append("".join(p.text or "" for p in tool_context.user_content.parts or []))
    hits = get_retriever().search(queries)
    return {"status": "success",
            "passages": [{"cite_as": f"{h['source']}, page {h['page']}", "text": h["text"]} for h in hits]}


# =========================================================================== timetable
def _slot_info(slot: str) -> dict | None:
    m = re.match(r"\s*([A-Z]+\d*)", slot.upper())
    if not m:
        return None
    s = m.group(1)
    timings, minors, majors = _slots()
    t, e, mj = timings[timings["slot"] == s], minors[minors["slot"] == s], majors[majors["slot"] == s]
    if t.empty and e.empty and mj.empty:
        return None
    weekly = {}
    for _, r in t.iterrows():
        weekly.setdefault(r["applies_to"], []).append(f"{r['day']} {_fmt_time(r['time'])}")
    info = {"slot": s, "weekly": weekly, "cite_as": sorted(set(t["source"]) | set(e["source"]) | set(mj["source"]))}
    if not e.empty:
        info["minor_exam"] = f"{e.iloc[0]['date']}, {e.iloc[0]['time']} (tentative)"
    if not mj.empty:
        info["major_exam"] = f"{mj.iloc[0]['date']}, {mj.iloc[0]['time']} (tentative)"
    return info


def _slot_text(info: dict) -> str:
    parts = [f"{', '.join(v)}" + (f" [{k}]" if len(info["weekly"]) > 1 else "") for k, v in info["weekly"].items()]
    return "; ".join(parts) or "timings not in the slot grid"


def lookup_course(course: str, tool_context: ToolContext = None) -> dict:
    """Find a course of AY 2026-27 Semester I by code or name: slot, class timings, instructor, credits, room.

    Args:
        course: the course code or course name exactly as the student wrote it.
    """
    rows = _find_courses(course, limit=3)
    if rows.empty:
        return _final({"status": "not_found",
                       "answer": f"I don't know: no course matching '{course}' is listed in the AY 2026-27 "
                                 f"Semester I timetable. {HANDOFF}"}, tool_context)
    lines, cites = [], []
    for _, r in rows.iterrows():
        line = f"{r['code']} {r['name']}: slot {r['slot'] or '-'}"
        info = _slot_info(r["slot"]) if r["slot"] else None
        if info:
            line += f" ({_slot_text(info)})"
            cites += info["cite_as"]
        line += f"; instructor {r['instructor'] or 'not listed'}"
        if r["co_instructor"]:
            line += f" (co-instructors: {r['co_instructor']})"
        if r["credits"]:
            line += f"; {r['credits']} credits" + (f" (L-T-P {r['ltp']})" if r["ltp"] else "")
        if r["classroom"]:
            line += f"; classroom {r['classroom']}"
        if info and "minor_exam" in info:
            line += f"; minor exam {info['minor_exam']}"
        if info and "major_exam" in info:
            line += f"; major exam {info['major_exam']}"
        lines.append(line + ".")
        cites.insert(0, r["source"])
    return _final({"status": "success", "answer": "\n".join(lines),
                   "cite_as": "; ".join(dict.fromkeys(cites))}, tool_context)


def get_slot_timings(slot_or_course: str) -> dict:
    """Minor and Major exam dates and weekly class times of a timetable slot or of a course.

    Args:
        slot_or_course: the slot name, course code or course name exactly as the student wrote it.
    """
    # Not a final-answer tool: the agent phrases the reply itself so that it can add the attendance rule
    # to examination questions.
    course = None
    # Accept "K", "slot K", "K slot", "K courses": an upper-case slot token, optionally after "slot"
    m = re.match(r"\s*(?:[Ss]lot\s+)?([A-Z]{1,2}\d{0,2})(?:\s+(?:slot|courses?|classes)\b.*)?\s*$", slot_or_course)
    info = _slot_info(m.group(1)) if m else None
    if not info:
        rows = _find_courses(slot_or_course, limit=1)
        if not rows.empty and rows.iloc[0]["slot"]:
            course = rows.iloc[0]
            info = _slot_info(course["slot"])
    if not info:
        return {"status": "not_found", "message": f"'{slot_or_course}' is not a known slot or course."}
    out = {"status": "success", "slot": info["slot"], "weekly_classes": _slot_text(info),
           "minor_exam": info.get("minor_exam", "not in the minor-exam timetable"),
           "major_exam": info.get("major_exam", "not in the major-exam timetable"),
           "cite_as": "; ".join(([course["source"]] if course is not None else []) + info["cite_as"])}
    if course is not None:
        out["course"] = f"{course['code']} {course['name']}"
    return out


DEPT_ALIASES = {
    "School of Liberal Arts (SoLA)": ["humanities", "hss", "liberal arts", "sola", "social science", "hum"],
    "Computer Science and Engineering": ["cse", "computer science", "cs"],
    "Electrical Engineering": ["ee", "electrical"],
    "Mechanical Engineering": ["me", "mechanical"],
    "Civil and Infrastructure Engineering": ["civil", "cie", "ci"],
    "Chemical Engineering": ["chemical", "che"],
    "Mathematics": ["math", "maths", "mathematics"],
    "School of Management and Entrepreneurship (SME)": ["management", "sme", "mba"],
    "School of Artificial Intelligence and Data Science (AIDE)": ["aide", "ai", "data science", "artificial intelligence"],
    "Bioscience and Bioengineering": ["bio", "bsbe", "bioengineering", "bioscience"],
    "Materials Engineering": ["materials", "mt", "metallurgy"],
    "School of Design": ["design", "sod"],
}


def _resolve_department(dept: str) -> str | None:
    d = dept.lower().replace("department", "").replace("dept", "").strip()
    for full, aliases in DEPT_ALIASES.items():
        if d in aliases or d == full.lower():
            return full
    names = sorted(set(_courses()["department"]) - {""})
    best = process.extractOne(d, names, scorer=fuzz.partial_ratio, score_cutoff=75)
    return best[0] if best else None


def list_courses(department: str, level: int, tool_context: ToolContext = None) -> dict:
    """Count and list courses offered this semester by a department, optionally at one level.

    Args:
        department: department name or abbreviation as the student wrote it.
        level: 100, 200, 300, 400, 600 or 700 (first digit of the code number); 0 for all.
    """
    full = _resolve_department(department)
    if not full:
        return _final({"status": "not_found",
                       "answer": f"I don't know: '{department}' does not match any department in the timetable. {HANDOFF}"},
                      tool_context)
    df = _courses()
    df = df[(df["department"] == full) & df["code"].str.fullmatch(r"[A-Z]{2,4}\d{4,5}")]
    level = int(level or 0)
    if level:
        df = df[df["code"].str.extract(r"(\d)", expand=False) == str(level // 100)]
    df = df.drop_duplicates("code")
    scope = f"at the {level} level " if level else ""
    lines = [f"{full} offers {len(df)} course(s) {scope}in AY 2026-27 Semester I:"]
    lines += [f"- {r.code} {r['name']} (slot {r.slot}, {r.instructor})" for _, r in df.iterrows()]
    cite = "; ".join(sorted(set(df["source"]))) or "AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Classroom Allocation)"
    return _final({"status": "success", "count": len(df), "answer": "\n".join(lines), "cite_as": cite}, tool_context)


# =========================================================================== people / email
def _split_names(text: str) -> list[str]:
    parts = re.split(r",|/|&|\band\b|\(\d\)", text)
    names = []
    for p in parts:
        p = re.sub(r"\b(Prof|Dr|Mr|Ms|Mrs)\.?\s*", "", p).strip(" .")
        if len(p) > 2 and p.upper() not in {"TBD", "NA", "??"}:
            names.append(p)
    return names


def _match_faculty(name: str, department: str = "") -> dict | None:
    fac = _faculty()
    hits = process.extract(name, fac["Faculty Name"], scorer=fuzz.token_set_ratio, limit=5, score_cutoff=80)
    if not hits:
        return None
    # Prefer the candidate from the course's department when scores tie
    hits.sort(key=lambda h: (h[1], department[:12].lower() in fac.loc[h[2], "Department"].lower()), reverse=True)
    r = fac.loc[hits[0][2]]
    return {"name": r["Faculty Name"], "email": r["Email ID"], "department": r["Department"],
            "designation": r["Designation"]}


def _instructors_for(course: str) -> tuple[dict | None, list[dict]]:
    rows = _find_courses(course, limit=1)
    if rows.empty:
        return None, []
    c = rows.iloc[0]
    people = []
    for n in _split_names(c["instructor"]) + _split_names(c["co_instructor"]):
        f = _match_faculty(n, c["department"])
        people.append(f | {"listed_as": n} if f else {"name": n, "email": None, "listed_as": n})
    return _course_record(c), people


def _not_offered(course: str, what: str) -> str:
    return (f"I don't know: course '{course}' is not listed in the AY 2026-27 Semester I timetable, so I cannot "
            f"find its instructor{what}. Please check the course code. {HANDOFF}")


def find_instructor(course: str, tool_context: ToolContext = None) -> dict:
    """Instructor(s) of a course and their e-mail IDs.

    Args:
        course: course code or name.
    """
    course_rec, people = _instructors_for(course)
    if course_rec is None:
        return _final({"status": "not_found", "answer": _not_offered(course, "")}, tool_context)
    lines = [f"Instructor(s) of {course_rec['code']} {course_rec['name']}:"]
    lines += [f"- {p['name']}: {p['email'] or 'e-mail ID not in the faculty directory'}"
              + (f" ({p['designation']}, {p['department']})" if p.get("designation") else "") for p in people]
    return _final({"status": "success", "answer": "\n".join(lines),
                   "cite_as": f"{course_rec['cite_as']}; {FACULTY_SRC}"}, tool_context)


def find_faculty(name: str, tool_context: ToolContext = None) -> dict:
    """A faculty member's e-mail ID, department and designation.

    Args:
        name: faculty name.
    """
    f = _match_faculty(re.sub(r"\b(Prof|Dr)\.?\s*", "", name))
    if not f:
        return _final({"status": "not_found",
                       "answer": f"I don't know: no faculty member named '{name}' is in the faculty directory. {HANDOFF}"},
                      tool_context)
    return _final({"status": "success", "cite_as": FACULTY_SRC,
                   "answer": f"{f['name']} ({f['designation']}, {f['department']}): {f['email']}"}, tool_context)


REQUEST_TEXT = {
    "sick_leave": ("Request for Medical Leave",
                   "Due to illness, I am unable to attend classes {details}. I kindly request you to grant me "
                   "medical leave for this period. I will submit the medical certificate from the Institute "
                   "Health Centre as supporting documentation and will make sure to catch up on the material covered."),
    "leave": ("Request for Leave of Absence",
              "I would like to request leave of absence {details}. I will make sure to cover the material "
              "taught during my absence and complete any pending work."),
    "makeup_exam": ("Request for Permission to Take a Make-up Examination",
                    "I was unable to appear / will be unable to appear for the examination {details}. I kindly "
                    "request your permission to take a make-up examination. I will provide the necessary "
                    "supporting documents and will follow whatever schedule you find convenient."),
    "other": ("Request", "{details}"),
}


def draft_email(course: str, request_type: str, details: str, student_name: str, roll_number: str,
                tool_context: ToolContext = None) -> dict:
    """Draft (not send) an e-mail from a student to the instructor of a course; saved for review.

    Args:
        course: course code or name.
        request_type: sick_leave, leave, makeup_exam or other.
        details: short phrase, e.g. "for 2 days".
        student_name: student name or "".
        roll_number: roll number or "".
    """
    course_rec, people = _instructors_for(course)
    if course_rec is None:
        return _final({"status": "not_found", "answer": _not_offered(course, " or e-mail ID; no draft was created")},
                      tool_context)
    to = [p for p in people if p.get("email")]
    if not to:
        return _final({"status": "not_found",
                       "answer": f"I don't know the e-mail ID of the instructor(s) of {course_rec['code']}: they are "
                                 f"not in the faculty directory, so no draft was created. {HANDOFF}"}, tool_context)
    rtype = request_type if request_type in REQUEST_TEXT else "other"
    subject, para = REQUEST_TEXT[rtype]
    details = details.strip().rstrip(".") or "as discussed"
    student_name = student_name.strip() or "[Your Name]"
    roll_number = roll_number.strip() or "[Your Roll Number]"
    primary = to[0]
    title = "Prof." if "Professor" in primary.get("designation", "") else "Dr."
    body = (f"Dear {title} {primary['name']},\n\n"
            f"I am {student_name} (Roll No. {roll_number}), a student registered in {course_rec['code']}: "
            f"{course_rec['name']} (slot {course_rec.get('slot', '-')}).\n\n"
            f"{para.format(details=details).rstrip('.')}.\n\n"
            "I would be grateful for your consideration.\n\n"
            f"Thanking you,\nYours sincerely,\n{student_name}\nRoll No. {roll_number}")
    cc = ", ".join(p["email"] for p in to[1:]) or "-"
    text = f"To: {primary['email']}\nCc: {cc}\nSubject: {subject} - {course_rec['code']} {course_rec['name']}\n\n{body}"
    path = config.DRAFTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{course_rec['code']}_{rtype}.txt"
    path.write_text(text + "\n", encoding="utf-8")
    answer = (f"Here is a draft for you to review:\n\n{text}\n\n"
              f"This draft has NOT been sent. It is saved at {path.relative_to(config.ROOT)}; please review it before sending.")
    return _final({"status": "success", "answer": answer,
                   "cite_as": f"{course_rec['cite_as']}; {FACULTY_SRC}"}, tool_context)


# =========================================================================== human hand-off
def log_unanswered_question(question: str, reason: str, tool_context: ToolContext) -> dict:
    """Log a question you cannot answer so a human can answer it later.

    Args:
        question: the question verbatim.
        reason: e.g. "out of scope" or "not found in documents".
    """
    entry = {"time": datetime.now().isoformat(timespec="seconds"), "question": question,
             "reason": reason, "agent": tool_context.agent_name, "logged_by": "agent"}
    with open(config.UNANSWERED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {"status": "logged", "message": "The question was logged for a human to answer."}
