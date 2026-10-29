"""Central configuration. Every value can be overridden with an environment variable."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
INDEX_DIR = ROOT / "data" / "index"
LOG_DIR = ROOT / "logs"
DRAFTS_DIR = ROOT / "drafts"

# --- Models (served by Ollama) -------------------------------------------------
OLLAMA_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_BASE)  # read by LiteLLM

CHAT_MODEL = os.getenv("HELPDESK_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("HELPDESK_EMBED_MODEL", "nomic-embed-text")
NUM_CTX = int(os.getenv("HELPDESK_NUM_CTX", "4096"))
TEMPERATURE = float(os.getenv("HELPDESK_TEMPERATURE", "0.2"))

# --- Retrieval -------------------------------------------------------------------
COLLECTION = "iitj_docs"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOP_K = int(os.getenv("HELPDESK_TOP_K", "5"))
BM25_WEIGHT = 0.5  # weight of BM25 relative to dense retrieval in reciprocal-rank fusion
CANDIDATES = 25  # per retriever, before reciprocal-rank fusion

# Files that are not useful for an academic helpdesk and contain personal data
# (individual salaries). They are skipped during ingestion.
EXCLUDE_PATTERNS = ["Salary"]

# Structured tables built by `python main.py ingest`
COURSES_CSV = PROCESSED_DIR / "courses.csv"
SLOTS_CSV = PROCESSED_DIR / "slot_timings.csv"
EXAMS_CSV = PROCESSED_DIR / "minor_exam_schedule.csv"
MAJOR_EXAMS_CSV = PROCESSED_DIR / "major_exam_schedule.csv"
FACULTY_CSV = RAW_DIR / "iitj_faculty.csv"
UNANSWERED_LOG = LOG_DIR / "unanswered_questions.jsonl"
INTERACTIONS_LOG = LOG_DIR / "interactions.jsonl"

for _d in (PROCESSED_DIR, INDEX_DIR, LOG_DIR, DRAFTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
