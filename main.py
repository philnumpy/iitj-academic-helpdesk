"""IIT Jodhpur Academic Helpdesk - command line entry point.

  python main.py ingest                         build tables + vector index from data/raw
  python main.py chat  [--mode multi|single] [--model llama3.1:8b]
  python main.py ask "question" [--mode ...] [--model ...]
  python main.py unanswered                     show questions logged for a human
"""
import argparse
import asyncio
import json
import sys
import warnings

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def show(trace: dict, verbose: bool):
    print(f"\n{trace['answer'] or '(no answer)'}")
    if trace["error"]:
        print(f"\n[error] {trace['error']}")
    footer = f"[{' -> '.join(trace['agents'])} | {trace['latency_s']}s]"
    if trace["sources"]:
        footer += "\n[documents consulted: " + " | ".join(trace["sources"][:6]) + "]"
    print("\n" + footer)
    if verbose:
        for c in trace["tool_calls"]:
            print(f"   tool {c['agent']}.{c['tool']}({json.dumps(c['args'], ensure_ascii=False)})")


async def chat(mode: str, model: str | None, verbose: bool):
    from helpdesk.service import Helpdesk
    hd = Helpdesk(mode, model)
    sid = await hd.new_session()
    print(f"IIT Jodhpur Academic Helpdesk ({mode}-agent, {hd.model}). Type 'exit' to quit.")
    while True:
        try:
            q = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if q:
            show(await hd.ask_async(q, sid), verbose)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["ingest", "chat", "ask", "unanswered"])
    ap.add_argument("question", nargs="?")
    ap.add_argument("--mode", choices=["multi", "single"], default="multi")
    ap.add_argument("--model", default=None, help="Ollama model name, e.g. llama3.1:8b or qwen3:8b")
    ap.add_argument("-v", "--verbose", action="store_true", help="print tool calls")
    a = ap.parse_args()

    if a.command == "ingest":
        from helpdesk.ingest import build_index
        build_index()
    elif a.command == "chat":
        asyncio.run(chat(a.mode, a.model, a.verbose))
    elif a.command == "ask":
        if not a.question:
            ap.error("ask needs a question")
        from helpdesk.service import Helpdesk
        show(Helpdesk(a.mode, a.model).ask(a.question), a.verbose)
    else:
        from helpdesk.config import UNANSWERED_LOG
        if not UNANSWERED_LOG.exists():
            print("No unanswered questions logged yet.")
            return
        for line in UNANSWERED_LOG.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            print(f"{e['time']}  [{e['agent']}/{e['logged_by']}] {e['question']}  -- {e['reason']}")


if __name__ == "__main__":
    main()
