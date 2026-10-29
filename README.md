# IIT Jodhpur Academic Helpdesk — multi-agent RAG with Google ADK + Ollama

Created by **Vaibhav Garg, Aaditya Bansal and Meet Tilala** (4th-year students, IIT Jodhpur).

A local, laptop-friendly helpdesk agent that answers questions about IIT Jodhpur academic programs, course
contents, rules and regulations and the AY 2026-27 Semester I timetable, and drafts e-mails to course
instructors (leave, sick leave, make-up exam). It refuses ("I don't know") anything outside that scope,
logs every question it cannot answer for a human, and cites the document each answer came from.
Every answer to an examination question also states the institute's 75% attendance requirement.

Everything runs locally: **Google ADK** for the agents, **LiteLLM → Ollama** for the chat model
(`llama3.1:8b` by default; `qwen3:8b` and `llama3.2:3b` were evaluated as alternatives),
**nomic-embed-text** for embeddings and **ChromaDB** as the vector store.

## Architecture

```
                         input guardrail (prompt injection / extraction, academic dishonesty)
                                          │
                          ┌───────────────▼───────────────┐
  student question ───▶   │  helpdesk_orchestrator (LLM)  │   only action: transfer_to_agent
                          └───────────────┬───────────────┘
     ┌───────────────────┬────────────────┼──────────────────┬─────────────────────┬──────────────┐
     ▼                   ▼                ▼                  ▼                     ▼              ▼
 policy_agent      schedule_agent     email_agent      out_of_scope_agent     about_agent
 (LLM)             (LLM)              (LLM)            (no LLM): logs the     (no LLM): who built
 rules, regs,      slots, timings,    e-mail IDs,      question, replies      the helpdesk and
 curricula,        rooms, exam dates, e-mail drafts    "I don't know"         what it can do
 circulars         course counts      (never sent)
 ─ search_documents ─ lookup_course *  ─ draft_email *
 ─ log_unanswered   ─ get_slot_timings ─ find_instructor *
                    ─ list_courses *   ─ find_faculty *
                    ─ search_documents ─ log_unanswered
                    ─ log_unanswered
 * deterministic tool that writes the final, cited answer itself (ADK skip_summarization)
                                          │
                         output guardrail on every LLM reply (prompt-leak filter, unverified e-mail filter)
```

* **RAG**: 63 documents → 900-character chunks → `nomic-embed-text` → ChromaDB. Retrieval is
  *hybrid* (dense vectors + BM25, weighted reciprocal-rank fusion) and *multi-query*: the agent's rewritten
  query and the student's original question are searched together and fused. Each passage carries a
  `cite_as` (file name + page) and the policy agent must end its answer with `Source: <cite_as>`.
* **Structured tools**: the timetable spreadsheets are normalised into `data/processed/courses.csv`
  (758 course offerings), `slot_timings.csv`, `minor_exam_schedule.csv` and `major_exam_schedule.csv`
  (a course look-up returns its slot, room, instructor and both exam dates). The Major-exam timetable is a
  Google Sheet saved from the browser (an HTML page with an `.xlsx` name); `tables.py` reads the cell grid
  embedded in the page. Counting ("how many 400-level
  Humanities electives?") is done by a tool, not by the LLM. For course look-ups, counts, instructor
  e-mails and e-mail drafts the LLM chooses the tool and extracts its arguments, and the tool composes the
  final, cited answer (small local models were unreliable at re-phrasing these results).
* **Examination answers**: the policy, schedule and single agents are instructed to recognise examination
  questions themselves and to add the 75% attendance rule (Circular 51, 8 July 2024) to the answer.
* **Out-of-scope / identity**: the orchestrator's only action is a transfer, so refusing or describing the
  helpdesk are just two more routing choices, handled by deterministic agents (no extra LLM call).
* **Guardrails** (`helpdesk/guardrails.py`, ADK callbacks), three layers that keep the prompts confidential:
  1. every agent's instructions say they are confidential and that document text is data, not instructions;
  2. an input filter blocks prompt-injection / prompt-extraction phrasings and academic-dishonesty requests
     (forged certificates, cheating, proxy attendance, leaked papers) before any LLM sees them;
  3. an output filter replaces any reply that reproduces 8+ consecutive words of the instructions, removes
     internal tool/agent/field names (e.g. a "Source: cite_as = None" line), removes `@iitj.ac.in` addresses
     that are in neither the faculty directory nor the documents, and strips qwen3 `<think>` blocks.
     Blocks are logged to `logs/guardrail_events.jsonl`.
* **Human hand-off**: `log_unanswered_question` (and the out-of-scope agent) append to
  `logs/unanswered_questions.jsonl`; the runner also logs refusals where the model forgot the tool.
  All interactions (route, tool calls, sources, token counts, latency) go to `logs/interactions.jsonl`.
* **Single-agent baseline**: `--mode single` runs one agent that holds all eight tools.

## Project layout

```
run.py                         one-command start: checks requirements and models, opens the chat
main.py                        CLI: ingest | chat | ask | unanswered
helpdesk/config.py             models, paths, retrieval parameters (all overridable by env vars)
helpdesk/ingest.py             loading (PDF / OCR txt / DOCX / DOC / XLSX / CSV), OCR clean-up, chunking, embedding cache
helpdesk/tables.py             timetable spreadsheets -> tidy CSVs
helpdesk/retriever.py          hybrid, multi-query dense + BM25 retriever
helpdesk/tools.py              the agent tools
helpdesk/agents.py             ADK agents (multi-agent + single-agent baseline) and their instructions
helpdesk/guardrails.py         input / output guardrails (ADK callbacks)
helpdesk/service.py            ADK Runner wrapper that returns answer + trace
adk_agents/                    entry point for `adk web`
eval/questions.json            30 evaluation prompts with gold answers and expected source documents
eval/guardrail_questions.json  10 red-team prompts (identity, prompt extraction, academic integrity)
eval/run_eval.py               runs + auto-grades a question set (resumable)
eval/run_all.py                every evaluation configuration in sequence
eval/analyze.py                metrics, run-to-run and model-to-model changes -> eval/results/summary.md,
                               eval/results/changed_answers.md
eval/results/                  graded traces (v1_before_exam_rule/ = earlier development version,
                               after_fixes/ = re-test of the affected prompts after the post-evaluation fixes)
REPORT.md                      findings (Markdown)
report/build_pdf.py            builds the report and question-set PDFs
data/index/chroma/             the vector index (ChromaDB)
data/processed/                timetable tables used by the structured tools
data/raw/iitj_faculty.csv      faculty directory (the other source documents are not in the repository)
```

## Quick start

Requirements: Python 3.10+ and [Ollama](https://ollama.com) running locally (~7 GB free RAM for an 8B model).

```bash
python run.py
```

`run.py` installs the Python requirements if they are missing, pulls `llama3.1:8b` and `nomic-embed-text`
through Ollama if they are not available yet, and opens the interactive multi-agent helpdesk. The vector
index (`data/index/chroma/`, 4,872 chunks), the timetable tables (`data/processed/`) and the faculty
directory are included in the repository, so no ingestion step is needed. Options: `--mode single`,
`--model qwen3:8b`, `-v` (print tool calls).

## Usage

```bash
python main.py chat                         # interactive multi-agent helpdesk
python main.py chat --mode single           # single-agent baseline
python main.py ask "What is the slot for the course Autonomous Systems?" -v   # -v prints tool calls
python main.py ask "..." --model qwen3:8b
python main.py unanswered                   # questions waiting for a human
adk web adk_agents                          # optional: ADK developer UI
```

Environment overrides: `HELPDESK_MODEL`, `HELPDESK_EMBED_MODEL`, `HELPDESK_NUM_CTX` (default 4096),
`HELPDESK_TEMPERATURE` (default 0.2), `HELPDESK_TOP_K` (default 5), `OLLAMA_API_BASE`.

## Evaluation

```bash
python eval/run_all.py                                                   # everything below, in sequence
python eval/run_eval.py --mode multi  --model llama3.1:8b --run 1        # 30 prompts
python eval/run_eval.py --mode multi  --model llama3.1:8b --run 2        # repeat: which answers change
python eval/run_eval.py --mode multi  --model qwen3:8b   --run 1         # replace the LLM
python eval/run_eval.py --mode multi  --model llama3.1:8b --run 1 --questions guardrail_questions.json
python eval/run_eval.py --mode single --model llama3.1:8b --run 1        # single-agent baseline
python eval/analyze.py                                                   # -> eval/results/summary.md
```

Each answer is auto-graded: key facts present (including the 75% rule for exam questions), refusal when
expected, citation present, correct source cited and retrieved, correct routing. `changed_answers.md`
lists, side by side, every answer that changed between repeated runs or between models.
See [REPORT.md](REPORT.md) for the results.

## Corpus

The index was built from the following documents, which are not included in the repository (only the
index built from them is); `python main.py ingest` rebuilds the index and tables if they are placed in
`data/raw/`: academic regulations (UG 2019, PG 2022), curricula of the
B.Tech./B.S. programs, the HSS concept note, the Engineering Science and minor/specialisation guidelines,
recent circulars and office orders (attendance policy, examination scheme, branch change, credit revision,
late-registration fine, appointments of Deans/Heads 2026, examination guidelines, pre-registration and
minor-exam e-mails), department people pages, the faculty directory (`iitj_faculty.csv`) and the
AY 2026-27 Semester I timetable spreadsheets, including the Minor (15–20 Sept 2026) and Major
(19–26 Nov 2026) examination timetables.

Privacy: the two salary lists in `data/raw/official/` are excluded from the index, and student names,
roll numbers and student e-mail addresses in the e-mail print-outs are replaced with dummy values during
ingestion. Scanned circulars are read through their OCR `.txt` companions (with the OCR gibberish of their
Hindi half filtered out), and byte-identical duplicates are indexed once.
