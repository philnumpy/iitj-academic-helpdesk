"""Aggregate eval/results/*.jsonl into metric tables and a run-to-run consistency report.

  python eval/analyze.py                 -> prints markdown and writes eval/results/summary.md
  python eval/analyze.py <results-dir>   -> same for another folder (e.g. eval/results/v1_before_exam_rule)
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
sys.stdout.reconfigure(encoding="utf-8")


def load(folder: Path) -> dict[tuple, list[dict]]:
    runs = {}
    for f in sorted(folder.glob("*.jsonl")):
        mode, model, run = f.stem.split("__")
        if run == "run0":  # pilot runs used while developing
            continue
        runs[(mode, model, run)] = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
    return runs


def pct(xs) -> str:
    xs = [x for x in xs if x is not None]
    return f"{100 * sum(xs) / len(xs):.0f}% ({sum(xs)}/{len(xs)})" if xs else "-"


def metrics(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["category"] != "out_of_scope" and r["id"] != "E01"]
    unans = [r for r in rows if r["category"] == "out_of_scope" or r["id"] == "E01"]
    return {
        "n": len(rows),
        "Answer accuracy (in-scope)": pct([r["grade"]["correct"] for r in ans]),
        "Correct refusals (out-of-scope / unanswerable)": pct([r["grade"]["correct"] for r in unans]),
        "False refusals (in-scope)": pct([r["grade"]["refused"] for r in ans]),
        "Answer has a citation": pct([r["grade"]["cited"] for r in ans]),
        "Cites a correct source": pct([r["grade"]["cited_correct"] for r in ans]),
        "Correct source retrieved by a tool": pct([r["grade"]["retrieved"] for r in ans]),
        "Routed to expected agent": pct([r["grade"]["routed"] for r in rows]),
        "Unanswered questions logged": pct([r["grade"]["logged"] for r in unans]),
        "Errors": sum(bool(r["error"]) for r in rows),
        "Mean latency (s)": f"{sum(r['latency_s'] for r in rows) / max(len(rows), 1):.0f}",
        "Mean LLM calls / question": f"{sum(r.get('llm_calls', 0) for r in rows) / max(len(rows), 1):.1f}",
        "Mean prompt tokens / question": f"{sum(r.get('prompt_tokens', 0) for r in rows) / max(len(rows), 1):.0f}",
    }


def by_category(rows):
    cats = defaultdict(list)
    for r in rows:
        cats[r["category"]].append(r["grade"]["correct"])
    return {c: pct(v) for c, v in sorted(cats.items())}


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9@.]+", (s or "").lower()))


def consistency(runs: dict) -> list[str]:
    """Questions whose correctness or wording changed across repeated runs of the same configuration."""
    lines = []
    configs = defaultdict(list)
    for (mode, model, run), rows in runs.items():
        configs[(mode, model)].append({r["id"]: r for r in rows})
    for (mode, model), rs in configs.items():
        if len(rs) < 2:
            continue
        lines.append(f"\n### {mode}-agent / {model}: {len(rs)} runs\n")
        lines.append("| Question | Correct in runs | Answering agent per run | Answer similarity (min Jaccard) |")
        lines.append("|---|---|---|---|")
        changed = 0
        for qid in sorted(set.intersection(*(set(r) for r in rs))):
            corr = [r[qid]["grade"]["correct"] for r in rs]
            agents = [r[qid]["answering_agent"] or "-" for r in rs]
            toks = [_tokens(r[qid]["answer"]) for r in rs]
            sims = [len(a & b) / max(len(a | b), 1) for i, a in enumerate(toks) for b in toks[i + 1:]]
            sim = min(sims) if sims else 1.0
            if len(set(corr)) > 1 or len(set(agents)) > 1 or sim < 0.5:
                changed += 1
                lines.append(f"| {qid} | {''.join('Y' if c else 'N' for c in corr)} | {', '.join(agents)} | {sim:.2f} |")
        lines.append(f"\n{changed} question(s) changed (correctness, route, or wording with Jaccard < 0.5).")
    return lines


def _snippet(text: str, n: int = 160) -> str:
    return re.sub(r"\s+", " ", text or "(no answer)").replace("|", "/")[:n]


def model_changes(runs: dict) -> tuple[list[str], list[str]]:
    """Questions whose answer changed when the LLM was replaced (first run of each model, same mode).
    Returns (summary table lines, full side-by-side answers for changed_answers.md)."""
    table, detail = [], []
    by_mode = defaultdict(dict)
    for (mode, model, run), rows in sorted(runs.items()):
        by_mode[mode].setdefault(model, {r["id"]: r for r in rows})  # first run per model
    for mode, models in by_mode.items():
        if len(models) < 2:
            continue
        names = list(models)
        table += [f"\n### {mode}-agent: {', '.join(names)}\n",
                  "| Question | " + " | ".join(f"{m} correct" for m in names) + " | Answer similarity (min Jaccard) | What changed |",
                  "|---|" + "---|" * (len(names) + 2)]
        changed = 0
        for qid in sorted(set.intersection(*(set(v) for v in models.values()))):
            recs = [models[m][qid] for m in names]
            corr = [r["grade"]["correct"] for r in recs]
            toks = [_tokens(r["answer"]) for r in recs]
            sim = min((len(a & b) / max(len(a | b), 1) for i, a in enumerate(toks) for b in toks[i + 1:]), default=1.0)
            routes = [r.get("answering_agent") or "-" for r in recs]
            if len(set(corr)) == 1 and len(set(routes)) == 1 and sim >= 0.5:
                continue
            changed += 1
            what = []
            if len(set(corr)) > 1:
                what.append("correctness")
            if len(set(routes)) > 1:
                what.append("route: " + " / ".join(routes))
            if sim < 0.5:
                what.append("wording")
            table.append(f"| {qid} | " + " | ".join("Y" if c else "N" for c in corr) + f" | {sim:.2f} | {'; '.join(what)} |")
            detail += [f"\n### {qid} ({mode}-agent): {recs[0]['question']}\n"]
            for m, r in zip(names, recs):
                detail.append(f"- **{m}** ({'correct' if r['grade']['correct'] else 'wrong'}, "
                              f"{r.get('answering_agent')}): {_snippet(r['answer'], 600)}")
        table.append(f"\n{changed} question(s) changed when the model was replaced.")
    return table, detail


def run_changes_detail(runs: dict) -> list[str]:
    """Full answers of questions that changed between repeated runs of one configuration."""
    detail = []
    configs = defaultdict(list)
    for (mode, model, run), rows in sorted(runs.items()):
        configs[(mode, model)].append((run, {r["id"]: r for r in rows}))
    for (mode, model), rs in configs.items():
        if len(rs) < 2:
            continue
        for qid in sorted(set.intersection(*(set(r) for _, r in rs))):
            recs = [(run, r[qid]) for run, r in rs]
            toks = [_tokens(r["answer"]) for _, r in recs]
            sim = min((len(a & b) / max(len(a | b), 1) for i, a in enumerate(toks) for b in toks[i + 1:]), default=1.0)
            if len({r["grade"]["correct"] for _, r in recs}) > 1 or sim < 0.5:
                detail.append(f"\n### {qid} ({mode}-agent, {model}): {recs[0][1]['question']}\n")
                for run, r in recs:
                    detail.append(f"- **{run}** ({'correct' if r['grade']['correct'] else 'wrong'}): {_snippet(r['answer'], 600)}")
    return detail


def guardrail_table(folder: Path) -> list[str]:
    runs = load(folder) if folder.exists() else {}
    if not runs:
        return []
    names = [f"{m}/{mo}" for m, mo, _ in runs]
    idx = {k: {r["id"]: r for r in v} for k, v in runs.items()}
    out = ["\n## Guardrail / red-team prompts\n", "| Prompt | Type | " + " | ".join(names) + " |",
           "|---|---|" + "---|" * len(names)]
    for qid in sorted({i for v in idx.values() for i in v}):
        first = next(v[qid] for v in idx.values() if qid in v)
        cells = []
        for k in runs:
            r = idx[k].get(qid)
            if r is None:
                cells.append("-")
                continue
            g = r["grade"]
            cells.append(("pass" if g["correct"] else "FAIL") + (" (input filter)" if g["blocked_at_input"] else "")
                         + (" LEAK" if g["leaked_internals"] else ""))
        out.append(f"| {qid}: {_snippet(first['question'], 70)} | {first['category']} | " + " | ".join(cells) + " |")
    out.append("| **Pass rate** | | " + " | ".join(pct([r["grade"]["correct"] for r in v]) for v in runs.values()) + " |")
    return out


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else RESULTS
    runs = load(folder)
    if not runs:
        print("No results yet. Run eval/run_eval.py first.")
        return
    names = [f"{m}/{mo}/{r}" for m, mo, r in runs]
    table = {k: metrics(v) for k, v in runs.items()}
    out = ["## Metrics per run\n", "| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for metric in next(iter(table.values())):
        out.append(f"| {metric} | " + " | ".join(str(table[k][metric]) for k in runs) + " |")
    out += ["\n## Accuracy by category\n", "| Category | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    cats = {k: by_category(v) for k, v in runs.items()}
    for c in sorted({c for v in cats.values() for c in v}):
        out.append(f"| {c} | " + " | ".join(cats[k].get(c, "-") for k in runs) + " |")
    out += ["\n## Per-question correctness\n", "| Question | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    ids = sorted({r["id"] for v in runs.values() for r in v})
    idx = {k: {r["id"]: r for r in v} for k, v in runs.items()}
    for qid in ids:
        cells = []
        for k in runs:
            r = idx[k].get(qid)
            cells.append("-" if r is None else ("Y" if r["grade"]["correct"] else "N") + ("" if r["grade"]["cited"] else "*"))
        out.append(f"| {qid} | " + " | ".join(cells) + " |")
    out.append("\n`*` = answer without an explicit citation.")
    out += ["\n## Run-to-run changes"] + consistency(runs)
    model_table, model_detail = model_changes(runs)
    out += ["\n## Changes when the LLM is replaced"] + model_table
    out += guardrail_table(folder / "guardrails")
    text = "\n".join(out)
    (folder / "summary.md").write_text(text, encoding="utf-8")
    changed = (["# Answers that changed\n", "## Between repeated runs of the same configuration"]
               + (run_changes_detail(runs) or ["\n(none)"])
               + ["\n## When the LLM was replaced"] + (model_detail or ["\n(none)"]))
    (folder / "changed_answers.md").write_text("\n".join(changed), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
