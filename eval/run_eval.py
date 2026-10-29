"""Run the question set through the helpdesk and store graded traces.

  python eval/run_eval.py --mode multi --model llama3.1:8b --run 1
  python eval/run_eval.py --mode single --model llama3.2:3b --run 1 --ids P01 S01
  python eval/run_eval.py --ids P05 P07 --tag after_fixes      # -> eval/results/after_fixes/

Results are appended to eval/results/<mode>__<model>__run<k>.jsonl; questions already present in that
file are skipped, so an interrupted run can simply be restarted.
"""
import argparse
import asyncio
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from eval.grading import grade, grade_guard  # noqa: E402
from helpdesk.service import Helpdesk  # noqa: E402

RESULTS = ROOT / "eval" / "results"


async def main(a):
    qfile = ROOT / "eval" / (a.questions or "questions.json")
    questions = json.loads(qfile.read_text(encoding="utf-8"))
    guard = qfile.name.startswith("guardrail")
    if a.ids:
        questions = [q for q in questions if q["id"] in a.ids]
    RESULTS.mkdir(parents=True, exist_ok=True)
    hd = Helpdesk(a.mode, a.model)
    base = RESULTS / a.tag if a.tag else RESULTS
    folder = base / "guardrails" if guard else base
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{a.mode}__{hd.model.replace(':', '-')}__run{a.run}.jsonl"
    done = {json.loads(l)["id"] for l in out.read_text(encoding="utf-8").splitlines()} if out.exists() else set()
    print(f"{out.name}: {len(questions) - len(done & {q['id'] for q in questions})} questions to run")
    for q in questions:
        if q["id"] in done:
            continue
        trace = await hd.ask_async(q["question"])  # fresh session per question
        g = grade_guard(q, trace) if guard else grade(q, trace)
        rec = {"id": q["id"], "category": q.get("category") or q["type"], "run": a.run} | trace | {"grade": g}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        flag = "OK " if g["correct"] else "XX "
        print(f"{flag}{q['id']} [{trace['latency_s']:6.1f}s] {'->'.join(trace['agents'])}: "
              f"{(trace['answer'] or trace['error'] or '').replace(chr(10), ' ')[:150]}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["multi", "single"], default="multi")
    ap.add_argument("--model", default=None)
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--questions", default=None, help="question file in eval/, e.g. guardrail_questions.json")
    ap.add_argument("--tag", default=None, help="write to eval/results/<tag>/ instead, e.g. after_fixes")
    asyncio.run(main(ap.parse_args()))
