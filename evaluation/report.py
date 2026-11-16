"""Print, save, load and compare evaluation runs."""

import json
from pathlib import Path

from evaluation.dataset import DatasetError
from evaluation.deepeval_judge import METRICS as DEEPEVAL_METRICS  # DeepEval is only loaded when judging
from evaluation.judge import LOW_FAITHFULNESS
from evaluation.judge import METRICS as JUDGE_METRICS  # RAGAS itself is only loaded when judging
from evaluation.metrics import COUNTS, METRICS

_JUDGE_LABELS = dict(JUDGE_METRICS) | dict(DEEPEVAL_METRICS)
# Key in a saved run, and its metrics
_JUDGES = (("ragas", JUDGE_METRICS), ("deepeval", DEEPEVAL_METRICS))
# Most below-threshold DeepEval scores listed with their reasons (the rest are in the saved file)
_MAX_LOW_SCORES = 15

_RETRIEVAL = ("hit", "reciprocal_rank", "precision", "context_recall", "correct_empty")
_ANSWERS = ("refusal_correct", "key_facts", "all_key_facts", "citations_valid", "cites_expected")
_LABELS = {name: label for name, label, _ in METRICS} | dict(COUNTS)
_KINDS = {name: kind for name, _, kind in METRICS}
_LINE = "=" * 78


# ---------------------------------------------------------------- formatting
def _fmt(name: str, entry: dict | None) -> str:
    if not entry or not entry["n"]:
        return "-"
    value = entry["value"]
    if name in dict(COUNTS) or name in ("passed", "errors"):
        return f"{int(value)} / {entry['n']}"
    return f"{value:.3f}" if _KINDS.get(name) == "score" else f"{value * 100:.1f}%"

def _settings_line(settings: dict) -> str:
    if settings.get("reranker_enabled"):
        return (f"reranker {settings['rerank_model']} (fetch {settings['retrieval_fetch_k']}, "
                f"min {settings['rerank_min_score']}, best-min {settings['rerank_min_best_score']}, "
                f"top {settings['rerank_top_n']})")
    return (f"embeddings only (top {settings['top_k']}, min {settings['min_relevance_score']}, "
            f"margin {settings['relative_score_margin']})")


def _llm_line(settings: dict) -> str:
    # Runs saved before LLM_PROVIDER existed always used Gemini
    provider = settings.get("llm_provider", "gemini")
    return f"{provider} {settings.get('llm_model') or settings.get('gemini_llm_model')}"


def failure_reasons(record: dict) -> list[str]:
    if record.get("error"):
        return [f"error: {record['error']}"]
    scores, reasons = record["scores"], []
    if scores.get("false_refusal"):
        reasons.append('said "not found" but the answer IS in the documents (false refusal)')
    if scores.get("hallucination"):
        reasons.append('answered, but the documents do NOT contain the answer (hallucination)')
    if scores.get("correct_empty") == 0.0:
        reasons.append("off-topic question, but retrieval returned passages")
    if scores.get("missing_sources"):
        reasons.append(f"retrieval missed: {', '.join(scores['missing_sources'])}")
    if scores.get("missing_facts"):
        reasons.append(f"answer is missing key fact(s): {', '.join(scores['missing_facts'])}")
    if scores.get("cites_expected") == 0.0:
        reasons.append("the answer does not cite any of the expected sources")
    return reasons or ["did not meet all checks"]


# ---------------------------------------------------------------- report
def print_report(run: dict, show_failures: bool = True) -> None:
    summary = run["summary"]
    print(f"\n{_LINE}\nEVALUATION REPORT  |  {run['dataset']}  |  tag: {run['tag']}  |  {run['mode']}")
    print(f"{_LINE}")
    print(f"Questions : {len(run['results'])}   User: {run['user_id']}   Started: {run['started_at']}")
    print(f"Ranking   : {_settings_line(run['settings'])}")
    if run["mode"] == "full":
        print(f"Answers   : {_llm_line(run['settings'])}")
    print(f"Duration  : {run['duration_seconds']}s   Rerank requests used: {run['rerank_requests']}")

    print("\nRETRIEVAL")
    for name in _RETRIEVAL:
        if name in summary:
            print(f"  {_LABELS[name]:<28}{_fmt(name, summary[name]):>10}   (n={summary[name]['n']})")
    if any(name in summary for name in _ANSWERS):
        print("\nANSWERS")
        for name in _ANSWERS + tuple(dict(COUNTS)):
            if name in summary:
                print(f"  {_LABELS[name]:<28}{_fmt(name, summary[name]):>10}   (n={summary[name]['n']})")
    _print_judge(run)
    _print_deepeval(run)
    print(f"\nPASSED  {_fmt('passed', summary['passed'])} questions")
    errors = [r for r in run["results"] if r.get("error")]
    if errors:
        # Old runs (before errors were kept apart) counted them as failures
        print(f"\n  WARNING: {len(errors)} question(s) could not run (errors below), so this report is "
              "incomplete.\n  Errors are not counted in the scores above. Re-run them with --ids once fixed.")

    full = run["mode"] == "full"
    columns = ("passed", "hit", "reciprocal_rank") + (("all_key_facts", "refusal_correct") if full else ())
    heads = ("Passed", "Hit", "MRR") + (("Facts", "Refusal") if full else ())
    print("\nBY QUESTION TYPE")
    print(f"  {'type':<20}{'n':>4}" + "".join(f"{h:>10}" for h in heads))
    for kind, stats in run["by_type"].items():
        n = sum(1 for r in run["results"] if r["type"] == kind)
        print(f"  {kind:<20}{n:>4}" + "".join(f"{_fmt(c, stats.get(c)):>10}" for c in columns))

    skipped = [r for r in run["results"] if r.get("skipped")]
    if skipped:
        print(f"\nSKIPPED ({len(skipped)}): {', '.join(r['id'] for r in skipped)} - {skipped[0]['skipped']}")

    if errors:
        print(f"\nERRORS ({len(errors)}): {', '.join(r['id'] for r in errors)}")
        for cause in dict.fromkeys(r.get("error_cause") or r["error"] for r in errors):
            print(f"  - {cause[:220]}")
        print(f"  Re-run: python main.py evaluate --ids {','.join(r['id'] for r in errors)}")

    failures = [r for r in run["results"] if r["passed"] is False and not r.get("error")]
    if show_failures and failures:
        print(f"\nFAILURES ({len(failures)})")
        for record in failures:
            print(f"\n  {record['id']} [{record['type']}] {record['question']}")
            for reason in failure_reasons(record):
                print(f"     - {reason}")
            if record.get("searched_for") and record["searched_for"] != record["question"]:
                searched = " ".join(record["searched_for"].split())
                print(f"     searched for: {searched[:160]}{'...' if len(searched) > 160 else ''}")
            got = [f"{p['score']:.3f} {p['file_name'][:20]} ({p.get('section') or 'page ' + str(p.get('page_number'))})"
                   for p in record.get("passages", [])[:3]]
            print(f"     retrieved: {'; '.join(got) if got else 'nothing'}")
            if record.get("answer"):
                answer = " ".join(record["answer"].split())
                print(f"     answer: {answer[:160]}{'...' if len(answer) > 160 else ''}")
            if record.get("ragas"):
                print(f"     judge: {_judge_scores(record['ragas'])}")
            if record.get("deepeval"):
                print(f"     deepeval: {_judge_scores(record['deepeval'])}")
    print()


# ---------------------------------------------------------------- AI judge
def _judge_scores(scores: dict) -> str:
    return ", ".join(f"{_JUDGE_LABELS[name].lower()} {value:.2f}" for name, value in scores.items())


def _print_judge_warnings(judge: dict) -> None:
    if judge.get("failed"):
        print(f"  WARNING: {judge['failed']} judge score(s) could not be given (left out of the averages).")
    if judge.get("stopped"):
        print(f"  WARNING: {judge['stopped']}.\n  Grade this saved run again later with --judge-run / --deepeval-run.")


def _print_judge(run: dict) -> None:
    judge = run.get("ragas")
    if not judge:
        return
    print(f"\nAI JUDGE ({judge['judge']})")
    for name, label in JUDGE_METRICS:
        entry = judge["summary"].get(name)
        if entry:
            print(f"  {label:<28}{entry['value']:>10.3f}   (n={entry['n']})")
    _print_judge_warnings(judge)
    low = sorted((r for r in run["results"] if r.get("ragas", {}).get("faithfulness", 1) < LOW_FAITHFULNESS),
                 key=lambda r: r["ragas"]["faithfulness"])
    if low:
        print(f"  Read these answers (faithfulness below {LOW_FAITHFULNESS}: claims the passages may not support):")
        for record in low:
            print(f"     {record['id']} {record['ragas']['faithfulness']:.2f}  {record['question'][:60]}")


def _print_deepeval(run: dict) -> None:
    judge = run.get("deepeval")
    if not judge:
        return
    threshold = judge["threshold"]
    print(f"\nAI JUDGE ({judge['judge']}, pass mark {threshold})")
    for name, label in DEEPEVAL_METRICS:
        entry = judge["summary"].get(name)
        if entry:
            print(f"  {label:<28}{entry['value']:>10.3f}   passed {entry['passed']} / {entry['n']}")
    _print_judge_warnings(judge)
    low = sorted(((value, name, record) for record in run["results"]
                  for name, value in (record.get("deepeval") or {}).items() if value < threshold),
                 key=lambda item: item[0])
    if low:
        print("  Below the pass mark, with the judge's reason (lowest first):")
        for value, name, record in low[:_MAX_LOW_SCORES]:
            reason = record.get("deepeval_reasons", {}).get(name, "")
            print(f"     {record['id']} {_JUDGE_LABELS[name].lower()} {value:.2f}: "
                  f"{reason[:150]}{'...' if len(reason) > 150 else ''}")
        if len(low) > _MAX_LOW_SCORES:
            print(f"     ...and {len(low) - _MAX_LOW_SCORES} more (all reasons are in the saved file)")


# ---------------------------------------------------------------- save / load
def save_run(run: dict, results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = run["started_at"].replace(":", "").replace("-", "").replace("+0000", "")[:15]
    path = results_dir / f"{stamp}_{run['tag']}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_run(reference: str, results_dir: Path) -> dict:
    """`reference` is a file path or a tag (the latest run with that tag is used)."""
    path = Path(reference)
    if not path.is_file():
        matches = sorted(results_dir.glob(f"*_{reference}.json"))
        if not matches:
            raise DatasetError(f"No saved run found for '{reference}' in {results_dir}")
        path = matches[-1]
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- compare
def _change(name: str, ea: dict | None, eb: dict | None) -> str:
    if not (ea and eb):
        return ""
    delta = eb["value"] - ea["value"]
    if name in dict(COUNTS) or name == "passed":
        return f"{delta:+.0f}"
    if _KINDS.get(name) == "score":
        return f"{delta:+.3f}"
    return f"{delta * 100:+.1f}%"


def compare_runs(a: dict, b: dict) -> dict:
    """What changed from run A to run B: metrics, AI judge scores, fixed and broken questions."""
    metrics = []
    for name in _RETRIEVAL + _ANSWERS + tuple(dict(COUNTS)) + ("passed",):
        ea, eb = a["summary"].get(name), b["summary"].get(name)
        if ea or eb:
            metrics.append({"name": name, "label": _LABELS.get(name, "Passed"), "a": _fmt(name, ea),
                            "b": _fmt(name, eb), "change": _change(name, ea, eb)})

    judges = []
    for key, judge_metrics in _JUDGES:
        judge_a, judge_b = a.get(key), b.get(key)
        if not judge_a and not judge_b:
            continue
        rows = []
        for name, label in judge_metrics:
            ea = (judge_a or {}).get("summary", {}).get(name)
            eb = (judge_b or {}).get("summary", {}).get(name)
            if ea or eb:
                shown_a, shown_b = (f"{e['value']:.3f}" if e else "-" for e in (ea, eb))
                rows.append({"name": name, "label": label, "a": shown_a, "b": shown_b,
                             "change": f"{eb['value'] - ea['value']:+.3f}" if ea and eb else ""})
        judges.append({"key": key, "a": judge_a["judge"] if judge_a else None,
                       "b": judge_b["judge"] if judge_b else None, "metrics": rows})

    before = {r["id"]: r for r in a["results"]}
    fixed, broken = [], []
    for record in b["results"]:
        old = before.get(record["id"])
        if old is None or old["passed"] is None or record["passed"] is None:
            continue
        if not old["passed"] and record["passed"]:
            fixed.append(record["id"])
        elif old["passed"] and not record["passed"]:
            broken.append({"id": record["id"], "type": record["type"], "question": record["question"],
                           "reasons": failure_reasons(record)})

    def side(run: dict) -> dict:
        return {"tag": run["tag"], "mode": run["mode"], "dataset": run["dataset"],
                "ranking": _settings_line(run["settings"]),
                "answers": _llm_line(run["settings"]) if run["mode"] == "full" else None}

    return {"a": side(a), "b": side(b), "same_dataset": a["dataset"] == b["dataset"],
            "metrics": metrics, "judges": judges, "fixed": fixed, "broken": broken}


def print_comparison(a: dict, b: dict) -> None:
    comparison = compare_runs(a, b)
    print(f"\n{_LINE}\nCOMPARISON   A = {a['tag']} ({a['mode']})   B = {b['tag']} ({b['mode']})\n{_LINE}")
    for letter in ("a", "b"):
        run = comparison[letter]
        print(f"{letter.upper()}: {run['ranking']}" + (f", answers {run['answers']}" if run["answers"] else ""))
    if not comparison["same_dataset"]:
        print(f"\n  Warning: different datasets ({a['dataset']} vs {b['dataset']}), so scores are not comparable.")

    print(f"\n  {'metric':<28}{'A':>10}{'B':>10}{'change':>10}")
    for row in comparison["metrics"]:
        print(f"  {row['label']:<28}{row['a']:>10}{row['b']:>10}{row['change']:>10}")

    for judge in comparison["judges"]:
        print(f"\n  AI judge   A: {judge['a'] or 'not judged'}   B: {judge['b'] or 'not judged'}")
        for row in judge["metrics"]:
            print(f"  {row['label']:<28}{row['a']:>10}{row['b']:>10}{row['change']:>10}")

    fixed, broken = comparison["fixed"], comparison["broken"]
    print(f"\n  Fixed in B ({len(fixed)}): " + (", ".join(fixed) or "none"))
    print(f"  Broken in B ({len(broken)}): " + (", ".join(r["id"] for r in broken) or "none"))
    for record in broken:
        print(f"     {record['id']} [{record['type']}] {record['question']}")
        for reason in record["reasons"]:
            print(f"        - {reason}")
    print()
