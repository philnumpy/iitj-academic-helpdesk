"""Run every evaluation configuration back to back (resumable), then build the summary.

  python eval/run_all.py

The order puts the most informative runs first, since a CPU-only laptop needs hours per run.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN, GUARD = "questions.json", "guardrail_questions.json"
CONFIGS = [  # (question file, mode, model, run); llama3.1:8b is the selected model
    (MAIN, "multi", "llama3.1:8b", 1),
    (GUARD, "multi", "llama3.1:8b", 1),
    (MAIN, "multi", "qwen3:8b", 1),
    (GUARD, "multi", "qwen3:8b", 1),
    (MAIN, "multi", "llama3.1:8b", 2),   # repeated run: which answers change between runs
    (MAIN, "multi", "llama3.2:3b", 1),
    (GUARD, "multi", "llama3.2:3b", 1),
    (MAIN, "single", "llama3.1:8b", 1),  # single-agent baseline
    (MAIN, "multi", "llama3.1:8b", 3),
    (MAIN, "multi", "qwen3:8b", 2),
]
MODELS = ["llama3.1:8b", "qwen3:8b", "llama3.2:3b"]

if __name__ == "__main__":
    only = sys.argv[1:]  # optional filter, e.g. "multi:qwen3:8b"
    for qfile, mode, model, run in CONFIGS:
        if only and f"{mode}:{model}" not in only:
            continue
        print(f"\n=== {qfile} / {mode} / {model} / run {run} ===", flush=True)
        for m in MODELS:  # free RAM between models
            subprocess.run(["ollama", "stop", m], capture_output=True)
        subprocess.run([sys.executable, str(ROOT / "eval" / "run_eval.py"), "--mode", mode, "--model", model,
                        "--run", str(run), "--questions", qfile], check=False)
    subprocess.run([sys.executable, str(ROOT / "eval" / "analyze.py")], check=False)
