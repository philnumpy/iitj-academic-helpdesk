"""Build the assignment report as a PDF (reportlab + matplotlib).

  python report/build_pdf.py        -> report/Academic_Helpdesk_Report.pdf

Every number is computed from the graded traces in eval/results/; the qualitative notes (manual review, what changed
between models and runs) come from reading those traces and are kept in the tables below.
"""
import json
import math
import re
import sys
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, Preformatted,  # noqa: E402
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "report" / "Academic_Helpdesk_Report.pdf"
FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from eval.analyze import load, metrics  # noqa: E402

# ----------------------------------------------------------------------------- numbers from the graded traces
RESULTS = ROOT / "eval" / "results"
RUNS = load(RESULTS)
QS = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
QTEXT = {q["id"]: q["question"] for q in QS}
EXAM_IDS = [q["id"] for q in QS if "exam question" in q["gold"].lower()]
N_Q = len(QS)
CONFIG_RUNS = {  # configuration -> run keys, in report order
    "llama_multi": [("multi", "llama3.1-8b", f"run{k}") for k in (1, 2, 3)],
    "qwen_multi": [("multi", "qwen3-8b", f"run{k}") for k in (1, 2)],
    "llama3b_multi": [("multi", "llama3.2-3b", "run1")],
    "llama_single": [("single", "llama3.1-8b", "run1")],
}
ORDER = list(CONFIG_RUNS)
LABEL = {"llama_multi": "llama3.1:8b, multi-agent", "qwen_multi": "qwen3:8b, multi-agent",
         "llama3b_multi": "llama3.2:3b, multi-agent", "llama_single": "llama3.1:8b, single agent"}
# Manual review (every answer read by hand) of the original question set, out of 24 answerable questions.
# Questions replaced since (eval/results/superseded/) are subtracted, and their replacements are counted from
# their own grades, which were checked by hand (disagreements go in MANUAL_OVERRIDES).
MANUAL_24 = {("multi", "llama3.1-8b", "run1"): 21, ("multi", "llama3.1-8b", "run2"): 19,
             ("multi", "llama3.1-8b", "run3"): 19, ("multi", "qwen3-8b", "run1"): 15,
             ("multi", "qwen3-8b", "run2"): 15, ("multi", "llama3.2-3b", "run1"): 17,
             ("single", "llama3.1-8b", "run1"): 21}
MANUAL_OVERRIDES = {}  # (run key, question id) -> bool, where the hand check disagrees with the auto grade
REPLACED = ("S04", "S05")


def answerable(rows):
    return [r for r in rows if r["category"] != "out_of_scope" and r["id"] != "E01"]


def acc(key):
    a = answerable(RUNS[key])
    return sum(r["grade"]["correct"] for r in a), len(a)


def manual(key):
    old = [json.loads(f.read_text(encoding="utf-8").splitlines()[0])["grade"]["correct"]
           for f in (RESULTS / "superseded").glob(f"*__{key[0]}__{key[1]}__{key[2]}.jsonl")]
    new = [MANUAL_OVERRIDES.get((key, r["id"]), r["grade"]["correct"]) for r in RUNS[key] if r["id"] in REPLACED]
    return MANUAL_24[key] - sum(old) + sum(new), acc(key)[1]


def states_rule(r):
    return "Institute attendance policy" in r["answer"] or "75%" in r["answer"]


def exam_rule(key):
    a = answerable(RUNS[key])
    exam = [r for r in a if r["id"] in EXAM_IDS]
    other = [r for r in a if r["id"] not in EXAM_IDS]
    return sum(map(states_rule, exam)), len(exam), sum(map(states_rule, other)), len(other)


def pc(x, n):
    return 100 * x / n if n else 0


def mean_pct(fn, keys):
    return sum(pc(*fn(k)[:2]) for k in keys) / len(keys)


def M(key):
    return metrics(RUNS[key])


def pct_of(s):  # "88% (21/24)" -> 88
    return int(str(s).split("%")[0])


def rng(values, unit="%", nd=0):
    lo, hi = min(values), max(values)
    return f"{lo:.{nd}f}{unit}" if round(lo, nd) == round(hi, nd) else f"{lo:.{nd}f}–{hi:.{nd}f}{unit}"


LL = CONFIG_RUNS["llama_multi"]
QW = CONFIG_RUNS["qwen_multi"]
S3B, SGL = CONFIG_RUNS["llama3b_multi"][0], CONFIG_RUNS["llama_single"][0]
N_ANS = acc(LL[0])[1]
N_UNANS = N_Q - N_ANS
N_RUNS = sum(len(v) for v in CONFIG_RUNS.values())

# red-team prompts (identity prompts are not part of this report)
GQ = [g for g in json.loads((ROOT / "eval" / "guardrail_questions.json").read_text(encoding="utf-8"))
      if g["type"] != "identity"]
GIDS = {g["id"] for g in GQ}
GR_RUNS = ["multi__llama3.1-8b__run1", "multi__qwen3-8b__run1", "multi__llama3.2-3b__run1"]


def read_jsonl(path):
    return {r["id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


GR = {run: {i: r for i, r in read_jsonl(RESULTS / "guardrails" / f"{run}.jsonl").items() if i in GIDS}
      for run in GR_RUNS}
GR_PASS = {run: sum(r["grade"]["correct"] for r in GR[run].values()) for run in GR_RUNS}

# ----------------------------------------------------------------------------- fonts & styles
FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONTS / "calibri.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONTS / "calibrib.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FONTS / "calibrii.ttf")))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", str(FONTS / "calibriz.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONTS / "consola.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")

INK = colors.HexColor("#1c2321")
MUTED = colors.HexColor("#5b6461")
ACCENT = colors.HexColor("#1d4d40")      # deep green: headings, table headers, LLM components
RULE = colors.HexColor("#d3d9d6")
SHADE = colors.HexColor("#f4f6f5")
CALLOUT = colors.HexColor("#edf4f0")
GREEN, AMBER = "#0d7d5a", "#c97a12"     # chart series; passes the dataviz palette checks on a light surface

S = {
    "ctitle": ParagraphStyle("ctitle", fontName="Body-Bold", fontSize=28, leading=34, textColor=ACCENT,
                             alignment=TA_CENTER),
    "cname": ParagraphStyle("cname", fontName="Body", fontSize=14, leading=22, textColor=INK, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=13, leading=17, textColor=INK),
    "meta": ParagraphStyle("meta", fontName="Body", fontSize=10, leading=14, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=14.5, leading=18, textColor=ACCENT,
                         spaceBefore=14, spaceAfter=6, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=11.5, leading=15, textColor=INK,
                         spaceBefore=9, spaceAfter=4, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Body-Bold", fontSize=10, leading=13, textColor=INK,
                         spaceBefore=6, spaceAfter=3, keepWithNext=1),
    "body": ParagraphStyle("body", fontName="Body", fontSize=10, leading=13.8, textColor=INK, spaceAfter=6,
                           alignment=TA_JUSTIFY),
    "bodyl": ParagraphStyle("bodyl", fontName="Body", fontSize=10, leading=13.8, textColor=INK, spaceAfter=6),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=10, leading=13.8, textColor=INK,
                             leftIndent=14, bulletIndent=3, spaceAfter=3, alignment=TA_JUSTIFY),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.6, leading=10.8, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Body-Bold", fontSize=8.6, leading=10.8, textColor=INK),
    "head": ParagraphStyle("head", fontName="Body-Bold", fontSize=8.6, leading=10.8, textColor=colors.white),
    "tcap": ParagraphStyle("tcap", fontName="Body", fontSize=9, leading=12, textColor=INK, spaceBefore=4,
                           spaceAfter=4, keepWithNext=1),
    "fcap": ParagraphStyle("fcap", fontName="Body", fontSize=9, leading=12, textColor=INK, spaceBefore=4,
                           spaceAfter=10),
    "note": ParagraphStyle("note", fontName="Body-Italic", fontSize=8.6, leading=11.2, textColor=MUTED,
                           spaceBefore=-4, spaceAfter=8),
    "stat": ParagraphStyle("stat", fontName="Body-Bold", fontSize=20, leading=23, textColor=ACCENT, alignment=TA_CENTER),
    "statlbl": ParagraphStyle("statlbl", fontName="Body", fontSize=8.6, leading=10.5, textColor=MUTED, alignment=TA_CENTER),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.4, leading=9.4, textColor=INK),
}
WIDTH = A4[0] - 2 * 20 * mm


def P(text, style="body"):
    return Paragraph(text, S[style])


def code(t):
    return f'<font name="Mono" size="8.6">{t}</font>'


def bullets(items, numbered=False):
    return [Paragraph(t, S["bullet"], bulletText=f"{i}." if numbered else "•") for i, t in enumerate(items, 1)]


_counter = {"Table": 0, "Figure": 0}


def caption(kind, text):
    _counter[kind] += 1
    return P(f"<b>{kind} {_counter[kind]}.</b> {text}", "tcap" if kind == "Table" else "fcap")


def table(rows, widths, bold_first_col=False, zebra=True, highlight_row=None):
    """rows[0] is the header; cells are markup strings."""
    data = []
    for i, row in enumerate(rows):
        data.append([Paragraph(str(c), S["head"] if i == 0 else S["cellb"] if bold_first_col and j == 0 else S["cell"])
                     for j, c in enumerate(row)])
    total = sum(widths)
    t = Table(data, colWidths=[w / total * WIDTH for w in widths], repeatRows=1, spaceAfter=10)
    style = [("BACKGROUND", (0, 0), (-1, 0), ACCENT),
             ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
             ("LINEBELOW", (0, -1), (-1, -1), 0.8, ACCENT),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 3.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if zebra:
        style += [("BACKGROUND", (0, r), (-1, r), SHADE) for r in range(2, len(rows), 2)]
    if highlight_row is not None:
        style += [("BACKGROUND", (0, highlight_row), (-1, highlight_row), CALLOUT)]
    t.setStyle(TableStyle(style))
    return t


def boxed(flowables, bg=SHADE, bar=None):
    t = Table([[flowables]], colWidths=[WIDTH])
    style = [("BACKGROUND", (0, 0), (-1, -1), bg),
             ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
             ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    style += [("LINEBEFORE", (0, 0), (0, -1), 2.5, bar)] if bar else [("BOX", (0, 0), (-1, -1), 0.4, RULE)]
    t.setStyle(TableStyle(style))
    return t


def answer_box(label, text, width=112):
    lines = []
    for para in text.splitlines():
        lines += textwrap.wrap(para, width) or [""]
    return KeepTogether([P(label, "h3"), boxed([Preformatted("\n".join(lines), S["code"])])])


# ----------------------------------------------------------------------------- figures
def bar_figure(path, categories, series, xmax=100):
    """Horizontal grouped bars, two series, direct value labels; light print surface."""
    plt.rcParams.update({"font.family": "Calibri", "font.size": 9.5})
    fig, ax = plt.subplots(figsize=(6.8, 2.75), dpi=220)
    fig.patch.set_facecolor("white")
    n, h = len(categories), 0.36
    for k, (name, values, color) in enumerate(series):
        ys = [i + (k - 0.5) * (h + 0.04) for i in range(n)]
        ax.barh(ys, values, height=h, color=color, edgecolor="white", linewidth=1.5, label=name)
        for y, v in zip(ys, values):
            ax.text(v + 1.2, y, f"{v:.0f}%", va="center", fontsize=8.8, color="#1c2321")
    ax.set_yticks(range(n))
    ax.set_yticklabels(categories, color="#1c2321")
    ax.invert_yaxis()
    ax.set_xlim(0, xmax + 9)
    ax.set_xticks(range(0, xmax + 1, 25))
    ax.set_xticklabels([f"{x}%" for x in range(0, xmax + 1, 25)], color="#5b6461")
    ax.grid(axis="x", color="#e4e8e6", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#d3d9d6")
    ax.tick_params(length=0)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.0), ncol=2, frameon=False, fontsize=8.8,
              handlelength=1.2, columnspacing=1.6)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


CHART_LABELS = [LABEL[c].replace(", ", "  ") for c in ORDER]
bar_figure(FIG / "accuracy.png", CHART_LABELS,
           [("Automatic grading (mean over runs)", [mean_pct(acc, CONFIG_RUNS[c]) for c in ORDER], GREEN),
            ("Manual review: fully correct", [mean_pct(manual, CONFIG_RUNS[c]) for c in ORDER], AMBER)])
bar_figure(FIG / "exam_rule.png", CHART_LABELS,
           [("Examination questions that state the policy", [mean_pct(exam_rule, CONFIG_RUNS[c]) for c in ORDER], GREEN),
            ("Other answers that also state it",
             [mean_pct(lambda k: exam_rule(k)[2:], CONFIG_RUNS[c]) for c in ORDER], AMBER)])


def figure(path, text):
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    img = Image(str(path), width=WIDTH, height=WIDTH * h / w)
    return KeepTogether([img, caption("Figure", text)])


# ----------------------------------------------------------------------------- architecture diagram
def architecture():
    W, H = WIDTH, 304
    d = Drawing(W, H)
    RC = 92                  # right column: answer, output guardrail, legend
    MW = W - RC - 14         # main column: request path, agents, knowledge sources
    llm = (colors.HexColor("#e7f1ec"), ACCENT)
    det = (colors.HexColor("#f2f2f0"), colors.HexColor("#8b928f"))
    grd = (colors.HexColor("#fbf0df"), colors.HexColor("#b8741a"))
    plain = (colors.white, colors.HexColor("#b9c3be"))
    frame = colors.HexColor("#c9d1cd")

    def T(text, size=7.3, font="Body", color=MUTED):
        return text, font, size, color

    def B(text, size=8.6, color=INK):
        return text, "Body-Bold", size, color

    def C(text):
        return text, "Mono", 6.0, INK

    def box(x, y, w, h, lines, style, radius=3):
        fill, stroke = style
        d.add(Rect(x, y, w, h, rx=radius, ry=radius, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))
        heights = [s * 1.3 for _, _, s, _ in lines]
        top = y + h / 2 + sum(heights) / 2
        for (text, font, size, color), lh in zip(lines, heights):
            top -= lh
            d.add(String(x + w / 2, top + 0.28 * size, text, fontName=font, fontSize=size, fillColor=color,
                         textAnchor="middle"))

    def arrow(x1, y1, x2, y2, color=MUTED, width=0.9):
        d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width))
        a = math.atan2(y2 - y1, x2 - x1)
        d.add(Polygon([x2, y2, x2 - 5 * math.cos(a - 0.4), y2 - 5 * math.sin(a - 0.4),
                       x2 - 5 * math.cos(a + 0.4), y2 - 5 * math.sin(a + 0.4)], fillColor=color, strokeColor=color))

    def group(x, y, w, h, label, label_top=True):
        d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=colors.HexColor("#fafbfa"), strokeColor=frame,
                   strokeWidth=0.7, strokeDashArray=[3, 2]))
        d.add(String(x + 7, y + h - 10 if label_top else y + 5, label, fontName="Body-Bold", fontSize=6.8,
                     fillColor=MUTED))

    # request path (top row)
    ry, rh = H - 36, 34
    box(0, ry, 92, rh, [B("Student question")], plain)
    arrow(92, ry + rh / 2, 110, ry + rh / 2)
    box(110, ry, 130, rh, [B("Input guardrail"), T("injection and integrity filter")], grd)
    arrow(240, ry + rh / 2, 258, ry + rh / 2)
    box(258, ry, MW - 258, rh, [B("Orchestrator (LLM)", color=colors.white),
                                T("routes with transfer_to_agent", color=colors.HexColor("#cfe3da"))], (ACCENT, ACCENT))
    box(MW + 14, ry, RC, rh, [B("Cited answer"), T("returned to the student")], plain)

    # specialist agents
    gy, gh = 128, 120
    group(0, gy, MW, gh, "SPECIALIST AGENTS")
    gap = 6
    bw = (MW - 12 - 3 * gap) / 4
    by, bh = gy + 8, 96
    agents = [
        ([B("Policy agent"), T("LLM · retrieval")], ["search_documents", "log_unanswered_question"], llm),
        ([B("Schedule agent"), T("LLM · timetable tools")],
         ["lookup_course *", "get_slot_timings", "list_courses *", "search_documents", "log_unanswered_question"], llm),
        ([B("E-mail agent"), T("LLM · drafting tools")],
         ["draft_email *", "find_instructor *", "find_faculty *", "log_unanswered_question"], llm),
        ([B("Out-of-scope handler"), T("deterministic, no LLM")], None, det),
    ]
    xs = [6 + i * (bw + gap) for i in range(4)]
    ox = 258 + (MW - 258) / 2
    for x, (head, tools, style) in zip(xs, agents):
        if tools:
            lines = head + [T("", 3)] + [C(t) for t in tools]
        else:
            lines = head + [T("", 3), T("logs the question and", 7.1, color=INK),
                            T("replies \u201cI don\u2019t know\u201d", 7.1, color=INK)]
        box(x, by, bw, bh, lines, style)
        arrow(ox, ry, x + bw / 2, by + bh, color=ACCENT)

    # output guardrail and answer (right column)
    rx = MW + 14
    box(rx, by, RC, bh, [B("Output guardrail"), T("", 3), T("prompt-leak filter", 7.1, color=INK),
                         T("internal-name filter", 7.1, color=INK), T("unverified e-mail", 7.1, color=INK),
                         T("address filter", 7.1, color=INK)], grd)
    arrow(MW, by + bh / 2, rx, by + bh / 2)
    arrow(rx + RC / 2, by + bh, rx + RC / 2, ry)

    # knowledge sources
    ky, kh = 0, 100
    group(0, ky, MW, kh, "KNOWLEDGE SOURCES", label_top=False)
    dy, dh = ky + 18, 66
    stores = [[B("Vector index", 8.2), T("ChromaDB + BM25"), T("63 documents"), T("4,872 chunks")],
              [B("Timetable tables", 8.2), T("758 course offerings"), T("slot timings"), T("Minor and Major exams")],
              [B("Faculty directory", 8.2), T("names, departments,"), T("e-mail addresses")],
              [B("Hand-off log", 8.2), T("unanswered questions"), T("for human follow-up")]]
    for x, lines in zip(xs, stores):
        box(x, dy, bw, dh, lines, plain)
        arrow(x + bw / 2, by, x + bw / 2, dy + dh)
    arrow(xs[1] + bw * 0.3, by, xs[0] + bw * 0.8, dy + dh)    # schedule agent also searches the documents
    arrow(xs[2] + bw * 0.3, by, xs[1] + bw * 0.8, dy + dh)    # e-mail tools read the course table

    # legend
    d.add(Rect(rx, ky, RC, kh, rx=4, ry=4, fillColor=colors.white, strokeColor=frame, strokeWidth=0.7))
    d.add(String(rx + 7, kh - 13, "Legend", fontName="Body-Bold", fontSize=7.6, fillColor=INK))
    for i, (label, (fill, stroke)) in enumerate([("LLM component", llm), ("deterministic", det), ("guardrail", grd)]):
        yy = kh - 29 - 13 * i
        d.add(Rect(rx + 7, yy, 11, 8, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))
        d.add(String(rx + 23, yy + 1.5, label, fontName="Body", fontSize=7.1, fillColor=INK))
    d.add(String(rx + 7, 22, "* tool writes the final,", fontName="Body", fontSize=7.1, fillColor=INK))
    d.add(String(rx + 7, 12, "   cited answer itself", fontName="Body", fontSize=7.1, fillColor=INK))
    return d


# ----------------------------------------------------------------------------- example answers
def trace(run, qid, folder=""):
    return read_jsonl(RESULTS / folder / f"{run}.jsonl")[qid]


def example(run, qid, question, folder=""):
    r = trace(run, qid, folder)
    route = "blocked by the input guardrail" if r["grade"].get("blocked_at_input") else " -> ".join(r["agents"])
    return answer_box(f"{qid}: \u201c{escape(question)}\u201d", f"[route: {route}]\n\n{r['answer'].strip()}")


# ----------------------------------------------------------------------------- page decoration
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Body", 8)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(20 * mm, A4[1] - 11 * mm, doc.title)
        canvas.setStrokeColor(RULE)
        canvas.line(20 * mm, A4[1] - 12.5 * mm, A4[0] - 20 * mm, A4[1] - 12.5 * mm)
    if doc.page > 1:
        canvas.drawCentredString(A4[0] / 2, 10 * mm, str(doc.page))
    canvas.restoreState()


# ============================================================================= content
story = []
A = story.append

ll_acc = sorted({pc(*acc(k)) for k in LL})
ll_exam = sorted({exam_rule(k)[:2] for k in LL})
qwen_acc = rng([pc(*acc(k)) for k in QW])
n_red = len(GQ) * len(GR_RUNS)
_summary = (RESULTS / "summary.md").read_text(encoding="utf-8")
n_model_changes = int(re.search(r"(\d+) question\(s\) changed when the model was replaced", _summary).group(1))

# ----------------------------------------------------------------------------- title page
A(Spacer(1, 85 * mm))
A(P("IIT Jodhpur Academic Helpdesk", "ctitle"))
A(Spacer(1, 10 * mm))
A(P("Vaibhav Garg<br/>Aaditya Bansal<br/>Meet Tilala", "cname"))
A(PageBreak())
A(P("Abstract", "h1"))
A(P("This report describes an academic helpdesk for IIT Jodhpur students. The system answers questions on academic "
    "programmes, course contents, academic rules and regulations and the AY 2026-27 Semester I timetable, "
    "including the Minor and Major examination schedules, and drafts e-mails to course instructors. It is "
    "implemented with Google ADK, served through LiteLLM by Ollama, and runs entirely on local hardware. "
    "An LLM orchestrator routes each question to a policy, schedule or e-mail agent, or to a "
    "deterministic handler that declines out-of-scope questions and logs them for a human. Answers are grounded "
    "in a hybrid (dense and BM25) index of 63 institute documents and in structured tables derived from the "
    "timetable, and every answer cites its source."))
A(P(f"The system was evaluated on {N_Q} questions with reference answers and on {len(GQ)} adversarial prompts, in "
    f"{N_RUNS} runs across three language models and a single-agent baseline. With <b>llama3.1:8b</b>, the multi-agent "
    f"system answered {rng(ll_acc)} of the in-scope questions correctly in each of three runs, refused every "
    "out-of-scope question, and stated the institute's 75% attendance policy in every examination-related answer. "
    f"Replacing the model with qwen3:8b reduced accuracy to {qwen_acc}, and llama3.2:3b to "
    f"{pc(*acc(S3B)):.0f}%. A single-agent baseline reached {pc(*acc(SGL)):.0f}% but cited its sources less "
    "precisely. llama3.1:8b in the multi-agent configuration was selected."))

# ----------------------------------------------------------------------------- 1. introduction
A(P("1. Introduction", "h1"))
A(P("Students frequently need answers that are spread across regulations, circulars, curricula and timetable "
    "spreadsheets. The objective of this work was to build a helpdesk that answers such questions from the "
    "institute's own documents, cites the document used, declines questions it cannot answer, and assists with "
    "routine correspondence. Table 1 lists the requirements of the assignment and where each is addressed."))
A(caption("Table", "Requirements and their implementation."))
A(table([
    ["Requirement", "Implementation", "Section"],
    ["Answer questions on programmes, course contents, rules and regulations and the timetable",
     "Policy agent (retrieval over 63 documents); schedule agent (structured tools over the timetable, including "
     "the Minor and Major examination schedules)", "2, 3.1–3.3"],
    ["Draft e-mails to instructors (sick leave, make-up examination)",
     "E-mail agent; " + code("draft_email") + " resolves the instructor and address and saves the draft; nothing "
     "is sent", "2"],
    ["Reply \u201cI don't know\u201d to out-of-scope questions and log them for a human",
     "Deterministic out-of-scope handler and " + code("log_unanswered_question") + ", writing to "
     + code("logs/unanswered_questions.jsonl"), "2"],
    ["Cite the source document", "Every passage and table row carries its file name (and page); answers end with "
     "a Source line", "3.2"],
    ["RAG with tools; Google ADK with LiteLLM and an 8B model served by Ollama",
     "ADK 2.13 " + code("LlmAgent") + "s; " + code("ollama_chat/llama3.1:8b") + " through LiteLLM; eight function "
     "tools", "2, 3"],
    ["Local embeddings and vector store", "nomic-embed-text and ChromaDB, fused with BM25", "3.2"],
    ["Single-agent baseline, then an orchestrator with specialist agents",
     code("--mode single") + " (one agent, all eight tools) and " + code("--mode multi"), "2, 6.6"],
    ["Evaluate 20–30 prompts for accuracy, groundedness and correct refusals",
     f"{N_Q} prompts with reference answers; automatic grading and full manual review", "5, 6"],
    ["Replace the LLM and record the answers that change",
     "qwen3:8b and llama3.2:3b; answer-level comparison across models and across repeated runs", "7, 8"],
    ["State the 75% attendance policy in examination answers", "Agents identify examination questions "
     "themselves and append the policy; no post-processing", "3.4, 6.4"],
    ["Keep the system prompts confidential", "Input and output filters, tested with adversarial prompts", "3.5, 9"],
], [1.45, 2.0, 0.42]))

A(P("1.1 Summary of the work carried out", "h2"))
story += bullets([
    "<b>Corpus.</b> 63 documents were collected: regulations, curricula, circulars and office orders, department "
    "pages, the faculty directory and four timetable workbooks, including the Minor (15–20 September 2026) and "
    "Major (19–26 November 2026) examination timetables.",
    "<b>Ingestion and retrieval.</b> A loader for PDF, OCR text, DOCX, DOC, XLSX and CSV files; OCR and layout "
    "clean-up; 900-character chunking; and a hybrid, multi-query retriever over ChromaDB and BM25.",
    "<b>Structured data.</b> The timetable workbooks were normalised into four tables (course offerings, slot "
    "timings, Minor and Major examination schedules) so that schedule questions are answered by deterministic look-ups.",
    "<b>Agents.</b> An orchestrator, three specialist agents and an out-of-scope handler built with Google ADK, "
    "together with a single-agent baseline for comparison.",
    f"<b>Evaluation.</b> {N_Q} graded questions and {len(GQ)} adversarial prompts, {N_RUNS} evaluation runs over three "
    "models, a manual review of every answer, and an analysis of which answers change between models and between runs.",
], numbered=True)

# ----------------------------------------------------------------------------- 2. architecture
A(P("2. System architecture", "h1"))
A(P("Figure 1 shows the components and the path of a request. A question first passes the input guardrail. The "
    "orchestrator, an LLM agent whose only permitted action is a transfer, then selects the agent that should "
    "answer. Each specialist agent works with its own tools, which read from the knowledge sources shown at the "
    "bottom of the figure. Every LLM reply passes the output guardrail before it reaches the student."))
A(Spacer(1, 2))
A(KeepTogether([architecture(), Spacer(1, 4),
                caption("Figure", "Architecture of the multi-agent helpdesk. Arrows show the request path and the "
                                  "data each agent reads.")]))
A(caption("Table", "Agents and their tools."))
A(table([
    ["Agent", "Type", "Responsibility", "Tools"],
    ["Orchestrator", "LLM", "Classifies the question and transfers it to one agent", code("transfer_to_agent")],
    ["Policy agent", "LLM", "Rules, regulations, curricula, programmes, circulars",
     code("search_documents") + ", " + code("log_unanswered_question")],
    ["Schedule agent", "LLM", "Slots, class timings, rooms, instructors, course counts, examination dates",
     code("lookup_course") + "*, " + code("get_slot_timings") + ", " + code("list_courses") + "*, "
     + code("search_documents") + ", " + code("log_unanswered_question")],
    ["E-mail agent", "LLM", "Instructor e-mail addresses; e-mail drafts",
     code("draft_email") + "*, " + code("find_instructor") + "*, " + code("find_faculty") + "*, "
     + code("log_unanswered_question")],
    ["Out-of-scope handler", "Deterministic", "Questions unrelated to IIT Jodhpur academics",
     "Logs the question; replies \u201cI don't know\u201d"],
], [0.85, 0.6, 1.5, 1.6], bold_first_col=True))
A(P("* The tool composes the final, cited answer itself (ADK " + code("skip_summarization") + "), which removes "
    "one LLM call and prevents the model from paraphrasing the result incorrectly.", "note"))
A(P("Two design decisions follow from failures observed during development (Section 4). First, the orchestrator "
    "cannot answer or log a question itself; declining is simply another routing choice, handled without an LLM "
    "call. Second, look-ups whose results are exact (course slots, examination dates, course counts, e-mail "
    "drafts) are produced by deterministic tools, while the LLM only chooses the tool and extracts its arguments."))

# ----------------------------------------------------------------------------- 3. implementation
A(P("3. Implementation", "h1"))
A(P("3.1 Document corpus and ingestion", "h2"))
A(P("The index contains 63 documents: 22 circulars and office orders, 19 curricula and course documents, 17 "
    "people and official pages, 4 timetable workbooks and the faculty directory. PDFs are read with PyMuPDF; "
    "scanned circulars are read through their OCR text, from which the unreadable output of the Hindi half is "
    "removed by checking each line against a vocabulary built from the born-digital documents. The Major "
    "examination timetable was supplied as a Google Sheet saved from the browser (an HTML page with an .xlsx "
    "extension); its cell grid is parsed directly from the page. Two salary lists are excluded, student names, "
    "roll numbers and e-mail addresses in e-mail print-outs are replaced with placeholders, and byte-identical "
    "duplicates are indexed once."))
A(P("3.2 Retrieval", "h2"))
A(P("Documents are split into 4,872 chunks of 900 characters and embedded with nomic-embed-text into ChromaDB. "
    "Retrieval is <b>hybrid</b>: the dense and BM25 rankings are combined by weighted reciprocal-rank fusion, with "
    "BM25 at half weight. It is also <b>multi-query</b>: the agent's reformulated query and the student's original "
    "question are both searched and fused. The five highest-ranked passages are returned to the agent, each "
    "labelled with its file name and page, and the agent must cite the passage it used."))
A(P("3.3 Structured timetable tools", "h2"))
A(P("The timetable workbooks are normalised into four tables: 758 course offerings (code, name, slot, "
    "instructor, credits, room), slot timings, the Minor examination schedule and the Major examination schedule. "
    "A question that names a course, for example \u201cWhen is the major exam for Database Systems?\u201d, is "
    "resolved deterministically: course name, then slot, then examination date and session. Counting questions "
    "(\u201cHow many 400-level Humanities electives are offered?\u201d) are also answered by a tool rather than by "
    "the LLM."))
A(P("3.4 Examination attendance policy", "h2"))
A(P("Every answer to an examination-related question must also state the institute's attendance requirement: "
    "attendance in each course must not fall below 75% (Circular 51, 8 July 2024). The policy, schedule and "
    "single agents are instructed to recognise such questions themselves and to append the policy with its "
    "citation. No post-processing step adds it, so compliance is a measured property of each model (Section 6.4)."))
A(P("3.5 Prompt confidentiality", "h2"))
A(P("The agents' instructions mark them as confidential. In addition, an input filter rejects prompt-extraction "
    "attempts and requests that violate academic integrity before any LLM is called, and an output filter "
    "replaces any reply that reproduces the instructions or names internal tools."))

# ----------------------------------------------------------------------------- 4. design iterations
A(CondPageBreak(80 * mm))
A(P("4. Design iterations", "h1"))
A(P(f"The final design is the result of pilot runs and a first complete evaluation (v1). Table {_counter['Table'] + 1} records each "
    "observed failure and the change made in response."))
A(caption("Table", "Failures observed during development and the corresponding changes."))
A(table([
    ["#", "Observation", "Change"],
    ["1", "Ollama could not load llama3.1:8b with an 8k context (6.3 GB required, 5.6 GB free)",
     "4,096-token context; shorter prompts and tool descriptions"],
    ["2", "Equal-weight hybrid retrieval displaced the relevant circular from the top four for 2 of 14 policy questions",
     "BM25 weight 0.5 and top-5 retrieval: relevant document retrieved for 14 of 14"],
    ["3", "PDF extraction produced one word per line, separating table headers from their values",
     "Soft line breaks joined before chunking (about 30% more text per chunk)"],
    ["4", "OCR of bilingual circulars produced unreadable text that degraded the embeddings",
     "OCR lines kept only if most of their words occur in the born-digital vocabulary"],
    ["5", "With a choice between transferring and logging, the llama3.2:3b orchestrator logged 3 of 4 in-scope "
          "questions as out of scope", "Transfer made the orchestrator's only action; refusal handled by a deterministic agent"],
    ["6", "Models paraphrased tool output incorrectly (\u201cI don't know\u201d after a successful course count; "
          "drafts not shown)", "Structured tools return the final, cited answer (" + code("skip_summarization") + ")"],
    ["7", "The schedule agent invented class timings", "Timings are always taken from a tool"],
    ["8", "llama3.1:8b copied a course code from a docstring example into an unrelated look-up",
     "Examples removed from tool descriptions"],
    ["9", "The agent's reformulated query missed the relevant passage (\u201cseating time\u201d versus \u201cseated "
          "15 minutes prior\u201d)", "Multi-query retrieval with the student's own wording: 6 of 8 such cases resolved, "
                                    "up from 3"],
    ["10", "Examination answers omitted the attendance policy",
     "Agents instructed to identify examination questions and state the policy (Section 3.4)"],
], [0.18, 1.6, 1.5]))
A(P("The v1 results, obtained before changes 8–10, are retained in "
    + code("eval/results/v1_before_exam_rule/") + "; the multi-agent llama3.1:8b configuration scored 79% there.", "bodyl"))

# ----------------------------------------------------------------------------- 5. methodology
A(P("5. Evaluation methodology", "h1"))
A(P("5.1 Test sets", "h2"))
A(P(f"The <b>question set</b> (Appendix A) contains {N_Q} prompts: 14 policy, 6 schedule and 5 e-mail questions, "
    "and 5 out-of-scope questions (dining, directions, weather, programming, a restaurant). One e-mail question "
    "(E01) concerns a course that is not offered this semester; the correct response says so, and it is "
    f"therefore counted with the out-of-scope questions as one of {N_UNANS} questions that should be declined. Each "
    "prompt has a reference answer, the key facts an answer must contain, and the documents that contain the "
    f"answer. The {len(EXAM_IDS)} examination questions ({', '.join(EXAM_IDS)}) must also state the attendance "
    "policy. Questions about examination dates name the course, as a student would, rather than its slot or code "
    "(S04: Minor examination of <i>Foundation Models and Generative AI</i>; S05: Major examination of "
    "<i>Database Systems</i>)."))
A(P(f"The <b>adversarial set</b> (Appendix B) contains {len(GQ)} prompts: five prompt-extraction attempts, worded "
    "differently from the patterns in the input filter, two requests that violate academic integrity, and one "
    "instruction to disregard the attendance policy."))
A(P("5.2 Metrics", "h2"))
A(caption("Table", "Evaluation metrics (computed by " + code("eval/grading.py") + ")."))
A(table([
    ["Metric", "Definition"],
    ["Answer accuracy", f"Share of the {N_ANS} in-scope answerable questions whose answer contains every required "
                        "fact (and, for examination questions, the attendance policy)"],
    ["Correct refusals", f"Share of the {N_UNANS} unanswerable questions that are declined and logged"],
    ["False refusals", "Share of in-scope questions that are wrongly declined"],
    ["Groundedness", "The answer cites a document that contains the answer"],
    ["Retrieval", "A tool returned a document that contains the answer"],
    ["Routing accuracy", "The orchestrator chose the expected agent"],
    ["Efficiency", "Number of LLM calls and prompt tokens per question"],
], [0.8, 3.0], bold_first_col=True))
A(P("5.3 Configurations and procedure", "h2"))
A(P(f"Four configurations were evaluated in {N_RUNS} runs, giving {N_RUNS * N_Q} graded answers: the multi-agent "
    "system with llama3.1:8b (three runs), qwen3:8b (two runs) and llama3.2:3b (one run), and the single-agent "
    "baseline with llama3.1:8b (one run). All runs used temperature 0.2 and a new session for every question. "
    "Because keyword grading can accept an answer that contains the correct value alongside an incorrect one, "
    "every answer was also read and judged by hand (Section 6.5)."))

# ----------------------------------------------------------------------------- 6. results
A(P("6. Results", "h1"))
A(P("6.1 Overview", "h2"))
A(P(f"Table {_counter['Table'] + 1} summarises each configuration; where a configuration was run more than once, the range over runs "
    "is shown. Figure 2 compares automatic grading with the manual review."))


def overview_row(cfg):
    keys = CONFIG_RUNS[cfg]
    exam = sorted({f"{x}/{n}" for x, n, *_ in map(exam_rule, keys)})
    row = [LABEL[cfg], str(len(keys)), rng([pc(*acc(k)) for k in keys]), rng([pc(*manual(k)) for k in keys]),
           rng([pct_of(M(k)["Cites a correct source"]) for k in keys]),
           rng([pct_of(M(k)["Correct refusals (out-of-scope / unanswerable)"]) for k in keys]),
           rng([pct_of(M(k)["False refusals (in-scope)"]) for k in keys]),
           ", ".join(exam)]
    return [f"<b>{c}</b>" for c in row] if cfg == "llama_multi" else row


A(caption("Table", f"Results by configuration ({N_ANS} answerable and {N_UNANS} unanswerable questions per run)."))
A(table([["Configuration", "Runs", "Accuracy (automatic)", "Fully correct (manual)", "Cites correct source",
          "Correct refusals", "False refusals", "Attendance policy on exam questions"]]
        + [overview_row(c) for c in ORDER],
        [1.4, 0.4, 0.72, 0.72, 0.66, 0.66, 0.6, 0.85], highlight_row=1))

_find = [
    f"<b>Selected configuration.</b> The multi-agent system with llama3.1:8b answered {rng(ll_acc)} of the "
    f"answerable questions correctly in all {len(LL)} runs, with no false refusals and the highest groundedness "
    f"({rng([pct_of(M(k)['Cites a correct source']) for k in LL])}).",
    f"<b>Refusals.</b> All {N_UNANS} out-of-scope or unanswerable questions were declined and logged in every run "
    "of every configuration.",
    f"<b>Attendance policy.</b> Only llama3.1:8b stated the policy in every examination answer "
    f"({'/'.join(map(str, ll_exam[0]))} in each run); qwen3:8b did so in {exam_rule(QW[0])[0]} of "
    f"{exam_rule(QW[0])[1]} and llama3.2:3b in {exam_rule(S3B)[0]} of {exam_rule(S3B)[1]}.",
    f"<b>Changing the model.</b> Accuracy fell to {qwen_acc} with qwen3:8b and to {pc(*acc(S3B)):.0f}% with "
    f"llama3.2:3b; {n_model_changes} of the {N_Q} answers changed in correctness, routing or wording (Section 7).",
    f"<b>Single agent.</b> The baseline reached {pc(*acc(SGL)):.0f}% with lower groundedness "
    f"({M(SGL)['Cites a correct source'].split()[0]}).",
    f"<b>Confidentiality.</b> No agent instructions were disclosed in any of the {n_red} adversarial answers.",
]
A(boxed([P("<b>Principal findings</b>", "h3")] + bullets(_find), bg=CALLOUT, bar=ACCENT))
A(Spacer(1, 8))
A(figure(FIG / "accuracy.png", f"Answer accuracy on the {N_ANS} in-scope answerable questions: automatic grading "
                               "(mean over runs) and answers judged fully correct in the manual review."))

A(P("6.2 Detailed results per run", "h2"))
MULTI = LL + QW + [S3B]


def metric_row(label, name, keys, fmt=lambda v: v):
    return [label] + [fmt(M(k)[name]) for k in keys]


A(caption("Table", f"Multi-agent results per run ({N_Q} prompts per run)."))
A(table([
    ["Metric", "llama3.1:8b r1", "llama3.1:8b r2", "llama3.1:8b r3", "qwen3:8b r1", "qwen3:8b r2", "llama3.2:3b"],
    metric_row(f"Answer accuracy ({N_ANS})", "Answer accuracy (in-scope)", MULTI),
    metric_row(f"Correct refusals ({N_UNANS})", "Correct refusals (out-of-scope / unanswerable)", MULTI),
    metric_row("False refusals", "False refusals (in-scope)", MULTI),
    metric_row("Answer contains a citation", "Answer has a citation", MULTI),
    metric_row("Groundedness", "Cites a correct source", MULTI),
    metric_row("Retrieval", "Correct source retrieved by a tool", MULTI),
    metric_row(f"Routing accuracy ({N_Q})", "Routed to expected agent", MULTI),
    metric_row("Unanswerable questions logged", "Unanswered questions logged", MULTI),
    metric_row("Errors", "Errors", MULTI, fmt=str),
    ["LLM calls / prompt tokens"] + [f"{M(k)['Mean LLM calls / question']} / "
                                     f"{int(M(k)['Mean prompt tokens / question']):,}" for k in MULTI],
], [1.6, 0.84, 0.84, 0.84, 0.84, 0.84, 0.84], bold_first_col=True))

A(P("6.3 Accuracy by question category", "h2"))
_cats = [("policy", "Policy"), ("schedule", "Schedule"), ("email", "E-mail"), ("out_of_scope", "Out of scope")]


def cat_pct(cfg, cat):
    vals = []
    for k in CONFIG_RUNS[cfg]:
        rows = [r for r in RUNS[k] if r["category"] == cat]
        vals.append(pc(sum(r["grade"]["correct"] for r in rows), len(rows)))
    return rng(vals)


A(caption("Table", "Accuracy by category (range over runs)."))
A(table([["Category", "Questions"] + [LABEL[c] for c in ORDER]]
        + [[name, str(sum(r["category"] == cat for r in RUNS[LL[0]]))] + [cat_pct(c, cat) for c in ORDER]
           for cat, name in _cats],
        [0.9, 0.6, 1.0, 1.0, 1.0, 1.0], bold_first_col=True))
A(P("Schedule questions are answered almost entirely by deterministic tools and are therefore the most stable "
    "category for the llama models. Policy questions depend on retrieval and on the model's reading of the "
    "passages, and show the largest differences between models."))

A(CondPageBreak(70 * mm))
A(P("6.4 Compliance with the attendance-policy requirement", "h2"))
A(P("The agents are instructed to recognise examination questions themselves and to state the attendance "
    f"policy. Table {_counter['Table'] + 1} reports how often each configuration did so, and how often the policy was also added to "
    "answers that were not about examinations."))


def exam_cell(cfg):
    parts = []
    for k in CONFIG_RUNS[cfg]:
        missed = [r["id"] for r in answerable(RUNS[k]) if r["id"] in EXAM_IDS and not states_rule(r)]
        x, n = exam_rule(k)[:2]
        parts.append(f"{x}/{n}" + (f" (missing: {', '.join(missed)})" if missed else ""))
    return "; ".join(parts)


def over_cell(cfg):
    return ", ".join(str(exam_rule(k)[2]) for k in CONFIG_RUNS[cfg]) + f" of {exam_rule(CONFIG_RUNS[cfg][0])[3]}"


A(caption("Table", f"Attendance policy in examination answers ({', '.join(EXAM_IDS)}); runs separated by "
                   "semicolons."))
A(table([["Configuration", "Examination answers stating the policy", "Other answers stating it"]]
        + [[LABEL[c], exam_cell(c), over_cell(c)] for c in ORDER],
        [1.1, 2.0, 0.9], bold_first_col=True, highlight_row=1))
A(figure(FIG / "exam_rule.png", f"Attendance-policy compliance: share of the {len(EXAM_IDS)} examination answers "
                                f"that state the policy, and share of the {exam_rule(LL[0])[3]} other answerable "
                                "questions that also state it (mean over runs)."))
A(P("llama3.1:8b is the only model that applied the requirement consistently. It also added the policy to some "
    "answers that were not about examinations (late-registration fine, branch change, programme duration); the "
    "added text is correct, so this affects concision rather than correctness. qwen3:8b never added the policy "
    "unnecessarily, but stated it only when the answer itself concerned attendance (P01). For S04 and S05 it "
    "reported the correct date and time without the policy."))

A(P("6.5 Validation of the automatic grading", "h2"))
A(P("Keyword grading confirms that the required facts are present but not that the answer contains nothing "
    f"incorrect. All answers were therefore read; Table {_counter['Table'] + 1} lists every case in which the manual judgement differs "
    "from the automatic grade."))
A(caption("Table", "Disagreements between automatic grading and manual review."))
A(table([
    ["Run", "Question", "Automatic", "Manual", "Reason"],
    ["llama3.1:8b r1", "P12 When to opt for a minor", "correct", "partial",
     "\u201cAny semester post 5th\u201d combined with the superseded 20-credit rule"],
    ["llama3.1:8b r2, r3", "P01 Attendance for the Major", "correct", "partial",
     "Adds the superseded 2019 clause \u201cstill allowed to appear\u201d"],
    ["llama3.1:8b r2, r3", "P02 Open Elective credits", "correct", "partial",
     "Also states 160 total credits (correct value: 165)"],
    ["llama3.1:8b r2, r3", "P12 When to opt for a minor", "correct", "partial", "Combines the superseded 100-credit and 20-credit rules"],
    ["qwen3:8b r1, r2", "P01 Attendance for the Major", "correct", "partial", "Includes the superseded \u201cC grade\u201d rule"],
    ["qwen3:8b r1", "P02 Open Elective credits", "correct", "partial", "States an incorrect total of 144 credits"],
    ["qwen3:8b r1, r2", "P12 When to opt for a minor", "correct", "partial", "Cites the superseded 100-credit / CGPA 6.0 rule"],
    ["llama3.2:3b", "S01 Slot of Autonomous Systems", "incorrect", "correct", "Correct slot in a phrasing the grader did not match"],
], [0.85, 1.2, 0.5, 0.45, 1.8]))
A(P(f"The resulting counts of fully correct answers (out of {N_ANS}) are: llama3.1:8b multi-agent "
    f"{', '.join(str(manual(k)[0]) for k in LL)}; qwen3:8b {' and '.join(str(manual(k)[0]) for k in QW)}; "
    f"llama3.2:3b {manual(S3B)[0]}; single agent {manual(SGL)[0]}. The most frequent error for every multi-agent model is "
    "the combination of a superseded 2019 rule with the newer circular that replaced it, despite an instruction "
    "to prefer the newer rule."))

A(P("6.6 Error analysis of the selected configuration", "h2"))
story += bullets([
    "<b>P11: total credits for a B.Tech. (165).</b> In all three runs the agent reported that the passages do not "
    "state the total. The credit-structure table consists mostly of numbers, and its chunk ranks 9th to 11th in "
    "retrieval, outside the five passages provided to the agent.",
    "<b>E04: e-mail address of the CSL1010 instructor.</b> In all three runs the question was routed to the "
    "schedule agent, because \u201cinstructor of a course\u201d matches the descriptions of two agents. The "
    "schedule agent returned the instructor's name and slot but not the address.",
])

A(P("6.7 Multi-agent system compared with the single-agent baseline", "h2"))
A(caption("Table", "llama3.1:8b as a multi-agent system and as a single agent."))
A(table([
    ["Metric", "Multi-agent (3 runs)", "Single agent (1 run)"],
    ["Answer accuracy (automatic)", " / ".join(f"{acc(k)[0]}/{acc(k)[1]}" for k in LL), f"{acc(SGL)[0]}/{acc(SGL)[1]}"],
    ["Fully correct (manual review)", " / ".join(f"{manual(k)[0]}/{manual(k)[1]}" for k in LL),
     f"{manual(SGL)[0]}/{manual(SGL)[1]}"],
    ["Correct refusals / false refusals",
     f"{rng([pct_of(M(k)['Correct refusals (out-of-scope / unanswerable)']) for k in LL])} / "
     f"{rng([pct_of(M(k)['False refusals (in-scope)']) for k in LL])}",
     f"{M(SGL)['Correct refusals (out-of-scope / unanswerable)'].split()[0]} / "
     f"{M(SGL)['False refusals (in-scope)'].split()[0]}"],
    ["Groundedness", rng([pct_of(M(k)["Cites a correct source"]) for k in LL]), M(SGL)["Cites a correct source"]],
    ["Attendance policy: examination / other answers",
     f"{'/'.join(map(str, ll_exam[0]))} / {over_cell('llama_multi')}",
     f"{exam_rule(SGL)[0]}/{exam_rule(SGL)[1]} / {exam_rule(SGL)[2]} of {exam_rule(SGL)[3]}"],
    ["LLM calls per question", rng([float(M(k)['Mean LLM calls / question']) for k in LL], '', 1),
     f"{M(SGL)['Mean LLM calls / question']}"],
], [1.5, 1.2, 1.0], bold_first_col=True))
story += bullets([
    "<b>Errors.</b> The single agent failed P02 (reported the Open Elective credits as not specified), P11 (the same "
    "retrieval miss as the multi-agent system) and P14 (reported a seating time of 30 minutes from an unrelated "
    "sheet instead of the 15 minutes in the examination guidelines, and omitted the attendance policy).",
    "<b>Routing.</b> Without a routing step it answered E04 correctly and needed one LLM call fewer per question.",
    "<b>Citations.</b> Its policy answers were shorter and did not combine superseded rules, but its citations were "
    "less precise (the older branch-change circular for P05; no source attached to the main answer of P06).",
    "<b>Assessment.</b> The multi-agent design is more accurate, better grounded and more consistent in applying "
    "the attendance policy. The single agent's main advantage, the absence of routing errors, corresponds to the "
    "only systematic failure of the multi-agent system (E04).",
])

# ----------------------------------------------------------------------------- 7. replacing the LLM
A(P("7. Effect of replacing the language model", "h1"))
_model_changes = [
    ["Question", "llama3.1:8b", "qwen3:8b", "llama3.2:3b", "Observed difference"],
    ["P02 Open Elective credits", "correct", "partial", "incorrect", "llama3.2:3b quoted the dual-degree requirement (56 credits)"],
    ["P06 Major exam duration and weightage", "correct", "incorrect", "incorrect", "Facts correct; attendance policy omitted"],
    ["P08 Absence of four or more weeks", "correct", "correct", "incorrect", "llama3.2:3b returned only a source line"],
    ["P10 Dean of Academic Affairs", "correct", "incorrect", "correct", "qwen3:8b declined without searching"],
    ["P12 When to opt for a minor", "partial", "partial", "incorrect", "llama3.2:3b applied the dual-degree rule (eighth semester)"],
    ["P14 Seating time, Minor exam", "correct", "incorrect", "incorrect", "Facts correct; attendance policy omitted"],
    ["S01 Slot of Autonomous Systems", "correct", "correct", "correct (manual)", "llama3.2:3b paraphrased the tool result"],
    ["S04 Minor exam, Foundation Models and Generative AI", "correct", "incorrect", "correct",
     "qwen3:8b: correct date and time; attendance policy omitted"],
    ["S05 Major exam, Database Systems", "correct", "incorrect", "correct",
     "qwen3:8b: correct date and time; attendance policy omitted"],
    ["E03 Make-up examination e-mail", "correct", "incorrect", "correct", "qwen3:8b called find_instructor instead of draft_email"],
    ["E04 E-mail address of CSL1010 instructor", "incorrect", "correct", "correct", "llama3.1:8b routed to the schedule agent"],
]
A(P(f"{n_model_changes} of the {N_Q} answers differ between llama3.1:8b, qwen3:8b and llama3.2:3b in correctness, "
    f"routing or wording (token Jaccard similarity below 0.5). Table {_counter['Table'] + 1} lists the {len(_model_changes) - 1} answers "
    f"whose correctness changed. The remaining {n_model_changes - len(_model_changes) + 1} differ only in wording; "
    "for example, every model gives the late-registration fine (P03) as Rs 1,500, in different words. Answers "
    "composed by deterministic tools (S02, S03, S06, E01, E02, E05) were identical across models. The full "
    "answer texts are compared side by side in " + code("eval/results/changed_answers.md") + "."))
A(caption("Table", "Answers whose correctness changed when the model was replaced (manual judgement)."))
A(table(_model_changes, [1.35, 0.6, 0.6, 0.72, 1.75]))
A(P("Two patterns account for most differences. qwen3:8b follows the multi-step instructions less reliably: it "
    "omits the attendance policy and, in two cases, declines or calls the wrong tool. llama3.2:3b has more "
    "difficulty extracting the relevant rule from long policy passages."))

# ----------------------------------------------------------------------------- 8. run-to-run
A(P("8. Consistency across repeated runs", "h1"))
A(P("<b>llama3.1:8b (three runs).</b> Correctness and routing were identical in all three runs "
    f"({acc(LL[0])[0]}/{N_ANS}, with the same two failures). Four answers differed in wording (token Jaccard "
    "similarity below 0.5):"))
A(caption("Table", "Wording changes between runs of llama3.1:8b."))
A(table([
    ["Question", "Difference between runs"],
    ["P02 Open Elective credits", "10 credits in every run; runs 2 and 3 also stated 160 total credits for the "
                                  "regular B.Tech. (incorrect; 165), and run 3 added the attendance policy"],
    ["P03 Late-registration fine", "Rs 1,500 in every run; only run 1 added the attendance policy"],
    ["P07 Maximum duration", "14 semesters in every run; runs 1 and 2 added the attendance policy"],
    ["P13 Withdrawal from a minor", "Run 2 also mentioned the revision from 20 to 15 credits; run 3 added that the "
                                    "exact number is not specified"],
], [0.9, 2.6], bold_first_col=True))
A(P("In the manual review, runs 2 and 3 were less precise than run 1 on P01, P02 and P12 because they "
    "included an outdated sentence from the 2019 regulations. The number of non-examination answers to which "
    "the attendance policy was added also varied (5, 3 and 4). A temperature of 0.2 therefore still permits "
    "noticeable variation in the content of policy answers, although not in their correctness as graded."))
A(P("<b>qwen3:8b (two runs).</b> P02 changed from correct to incorrect: run 1 gave 10 Open Elective credits "
    "(with an incorrect total of 144), run 2 gave 12. All other failures recurred in both runs: P06, P14, S04 and "
    "S05 without the attendance policy, P10 declined without a search, and E03 handled with the wrong tool."))
A(P("<b>Earlier version (v1).</b> Correctness varied between runs for P13, where llama3.1:8b's own search query "
    "missed the relevant circular in one run, and for the slot-K examination question, where llama3.2:3b chose "
    "the wrong tool once. With multi-query retrieval, P13 is answered correctly in every run."))

# ----------------------------------------------------------------------------- 9. adversarial testing
A(P("9. Adversarial testing", "h1"))
GTYPE = {"no_leak": "Prompt extraction", "integrity": "Academic integrity", "policy75": "Policy override"}


def gr_count(run, gtype):
    rows = [r for i, r in GR[run].items() if next(g["type"] for g in GQ if g["id"] == i) == gtype]
    return f"{sum(r['grade']['correct'] for r in rows)}/{len(rows)}"


A(P(f"The {len(GQ)} adversarial prompts (Appendix B) were submitted to the multi-agent system with each of the "
    f"three models. Table {_counter['Table'] + 1} gives the number of prompts handled as intended."))
A(caption("Table", "Adversarial prompts handled as intended, by type."))
A(table([["Prompt type", "llama3.1:8b", "qwen3:8b", "llama3.2:3b"]]
        + [[name] + [gr_count(run, t) for run in GR_RUNS] for t, name in GTYPE.items()]
        + [["<b>Total</b>"] + [f"<b>{GR_PASS[run]}/{len(GQ)}</b>" for run in GR_RUNS]],
        [1.4, 1.0, 1.0, 1.0], bold_first_col=True))
A(P("No agent's instructions were disclosed in any answer. The remaining failures were an internal tool or field "
    "name appearing in a Source line, and the policy-override prompt (G10), which every model declined instead of "
    "restating the attendance policy."))

# ----------------------------------------------------------------------------- 10. examples
A(CondPageBreak(90 * mm))
A(P("10. Example interactions", "h1"))
A(P("The following answers are reproduced without editing from the graded traces of llama3.1:8b in the "
    "multi-agent configuration (run 1)."))
A(example("multi__llama3.1-8b__run1", "S04", QTEXT["S04"]))
A(example("multi__llama3.1-8b__run1", "S05", QTEXT["S05"]))
A(example("multi__llama3.1-8b__run1", "S02", QTEXT["S02"]))
A(example("multi__llama3.1-8b__run1", "E02", QTEXT["E02"]))
A(example("multi__llama3.1-8b__run1", "O01", QTEXT["O01"]))

# ----------------------------------------------------------------------------- 11-12. limitations, conclusion
A(P("11. Limitations and future work", "h1"))
story += bullets([
    "<b>Numeric tables.</b> The B.Tech. credit-structure table is mostly numeric, so its chunk ranks low even with "
    "multi-query retrieval, and questions on total credits fail. Table-aware chunking or a descriptive header for "
    "each chunk would address this.",
    "<b>Superseded rules.</b> The 2019 UG regulations are partly overridden by later circulars, and the models "
    "sometimes combine the two. Tagging chunks with their issue date and marking superseded clauses during "
    "ingestion would make precedence explicit.",
    "<b>Routing ambiguity.</b> \u201cInstructor of a course\u201d matches two agents (E04). Returning the "
    "instructor's e-mail address from " + code("lookup_course") + " would remove the dependence on routing.",
    "<b>Evaluation.</b> Keyword grading requires manual review; an LLM judge could automate this. llama3.2:3b "
    "and the single agent were each evaluated in one run only.",
])
A(P("12. Conclusion", "h1"))
A(P(f"A multi-agent helpdesk was built and evaluated entirely on local hardware. With llama3.1:8b it answered "
    f"{rng(ll_acc)} of the answerable questions correctly in three consecutive runs, declined every out-of-scope "
    "question, cited its sources, and applied the attendance-policy requirement to every examination question. "
    "Separating exact look-ups into deterministic tools and restricting the orchestrator to routing were the "
    "design choices with the largest effect on reliability. The model comparison shows that the ability to follow "
    "multi-step instructions is what distinguishes the candidate models for this task."))

# ----------------------------------------------------------------------------- appendices
A(PageBreak())
A(P("Appendix A. Evaluation question set", "h1"))
A(table([["ID", "Question", "Reference answer"]] + [[q["id"], escape(q["question"]), escape(q["gold"])] for q in QS],
        [0.3, 1.7, 2.0], bold_first_col=True))
A(P("Appendix B. Adversarial prompts", "h1"))
_expect = {"no_leak": "Discloses no instructions or internal names", "integrity": "Refuses",
           "policy75": "Does not endorse it; states the 75% policy"}
A(table([["ID", "Type", "Prompt", "Expected behaviour"]]
        + [[g["id"], GTYPE[g["type"]], escape(g["question"]), _expect[g["type"]]] for g in GQ],
        [0.3, 0.65, 2.1, 1.0], bold_first_col=True))
A(P("Appendix C. Reproducing the results", "h1"))
A(boxed([Preformatted(
    "pip install -r requirements.txt\n"
    "ollama pull llama3.1:8b && ollama pull nomic-embed-text    # + qwen3:8b, llama3.2:3b for the comparison\n"
    "python main.py ingest                                      # tables + vector index\n"
    "python main.py chat                                        # interactive multi-agent helpdesk\n"
    "python main.py ask \"Which slot is CSL7650 in?\" -v          # one question, prints the tool calls\n"
    "python eval/run_all.py                                     # every evaluation configuration\n"
    "python eval/analyze.py                                     # -> eval/results/summary.md, changed_answers.md\n"
    "python report/build_pdf.py                                 # -> this report", S["code"])]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                        bottomMargin=17 * mm, title="IIT Jodhpur Academic Helpdesk: Technical Report",
                        author="Vaibhav Garg, Aaditya Bansal, Meet Tilala")
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print(OUT)

# ============================================================================= question set (separate PDF)
QOUT = ROOT / "report" / "Evaluation_Question_Set.pdf"
CATEGORY = {"policy": "Policy", "schedule": "Schedule", "email": "E-mail", "out_of_scope": "Out of scope"}
qstory = [P("IIT Jodhpur Academic Helpdesk", "ctitle"), Spacer(1, 3 * mm),
          P("Evaluation question set", "cname"), Spacer(1, 8 * mm)]
qstory.append(P(f"The {N_Q} prompts below were used to evaluate the helpdesk. Each has a reference answer; an answer "
                "is graded correct when it contains the key facts of the reference answer and cites a document that "
                f"contains them. {N_UNANS} prompts (the five out-of-scope questions and E01, about a course not "
                "offered this semester) should be declined and logged for a human. Answers to "
                f"the {len(EXAM_IDS)} examination questions ({', '.join(EXAM_IDS)}) must also state the institute's "
                "75% attendance policy."))
for cat, name in CATEGORY.items():
    rows = [q for q in QS if q["category"] == cat]
    qstory += [P(f"{name} questions ({len(rows)})", "h1"),
               table([["ID", "Question", "Reference answer"]]
                     + [[q["id"], escape(q["question"]), escape(q["gold"])] for q in rows],
                     [0.3, 1.6, 2.1], bold_first_col=True)]
qstory += [CondPageBreak(70 * mm), P(f"Adversarial prompts ({len(GQ)})", "h1"),
           P("Used to test that the agents' instructions stay confidential and that requests violating academic "
             "integrity are refused."),
           table([["ID", "Type", "Prompt", "Expected behaviour"]]
                 + [[g["id"], GTYPE[g["type"]], escape(g["question"]), _expect[g["type"]]] for g in GQ],
                 [0.3, 0.65, 2.1, 1.0], bold_first_col=True)]
SimpleDocTemplate(str(QOUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                  bottomMargin=17 * mm, title="IIT Jodhpur Academic Helpdesk: Evaluation Question Set",
                  author="Vaibhav Garg, Aaditya Bansal, Meet Tilala").build(qstory, onFirstPage=on_page,
                                                                            onLaterPages=on_page)
print(QOUT)
