"""Run the IIT Jodhpur Academic Helpdesk with a single command:

    python run.py                       multi-agent helpdesk with llama3.1:8b
    python run.py --mode single         single-agent baseline
    python run.py --model qwen3:8b      another Ollama chat model
    python run.py -v                    also print the tool calls

On first use it installs the Python requirements if they are missing, checks that Ollama is running and pulls
the chat and embedding models if they are not available yet. The vector index and the timetable tables are
shipped in data/, so the chat opens straight away.
"""
import argparse
import asyncio
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODULES = ["google.adk", "litellm", "chromadb", "ollama", "fitz", "docx", "openpyxl", "pandas", "rapidfuzz",
           "langchain_text_splitters"]


def _missing(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is None
    except ModuleNotFoundError:
        return True


def ensure_requirements():
    missing = [m for m in MODULES if _missing(m)]
    if missing:
        print(f"Installing Python requirements (missing: {', '.join(missing)}) ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])


def ensure_models(models: list[str]):
    import ollama
    try:
        listed = ollama.list()
    except Exception:
        sys.exit("Ollama is not running. Install it from https://ollama.com, start it, and run this script again.")
    have = set()
    for m in listed.models:
        have |= {m.model, m.model.removesuffix(":latest")}
    for model in models:
        if model in have:
            continue
        print(f"Pulling {model} (first run only) ...")
        for p in ollama.pull(model, stream=True):
            if p.total:
                print(f"\r  {p.status}: {100 * (p.completed or 0) / p.total:5.1f}%", end="", flush=True)
        print()


def ensure_index():
    from helpdesk import config
    tables = [config.COURSES_CSV, config.SLOTS_CSV, config.EXAMS_CSV, config.MAJOR_EXAMS_CSV]
    try:
        import chromadb
        chunks = chromadb.PersistentClient(path=str(config.INDEX_DIR / "chroma")).get_collection(config.COLLECTION).count()
    except Exception:
        chunks = 0
    if chunks and all(p.exists() for p in tables):
        return
    if not (config.RAW_DIR / "timetables").exists():
        sys.exit("The vector index or the timetable tables are missing from data/, and the source documents needed "
                 "to rebuild them are not in data/raw/.")
    print("Building the timetable tables and the vector index ...")
    from helpdesk.ingest import build_index
    build_index()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["multi", "single"], default="multi")
    ap.add_argument("--model", default=None, help="Ollama chat model, e.g. llama3.1:8b or qwen3:8b")
    ap.add_argument("-v", "--verbose", action="store_true", help="print tool calls")
    a = ap.parse_args()

    ensure_requirements()
    sys.path.insert(0, str(ROOT))
    from helpdesk import config
    ensure_models([a.model or config.CHAT_MODEL, config.EMBED_MODEL])
    ensure_index()

    from main import chat
    asyncio.run(chat(a.mode, a.model, a.verbose))


if __name__ == "__main__":
    main()
