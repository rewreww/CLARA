"""CLARA RAGAS: fill missing metric slots without duplicating successful scores.

Combines *distinct* Nemotron, Groq and Gemini judging logs. The summary retains
provider/model for each metric. Mixed-judge scores must be disclosed in reports.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time

METRICS = ("context_recall", "context_precision", "faithfulness", "answer_relevancy")
ROOT = Path(__file__).resolve().parents[2]

def read(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def state(capture_path, nemotron_path, groq_path, gemini_path=None):
    captured, latest = {}, {}
    for row in read(capture_path):
        qid = row.get("id")
        latest[qid] = row
        if row.get("status") == "completed" and row.get("ragas_ready") and row.get("retrieved_contexts"):
            captured[qid] = row
    scored = {}
    # Prefer existing Nemotron scores when the same question + metric
    # has been scored by both. Groq scores fill missing slots only.
    for path in (gemini_path, groq_path, nemotron_path):
        if path is None:
            continue
        for row in read(path):
            if row.get("status") == "scored" and row.get("metric") in METRICS:
                scored[(row.get("id"), row.get("metric"))] = row
    return captured, latest, scored

def main():
    p = argparse.ArgumentParser(description="Resume missing CLARA RAGAS scores using Groq and Gemini fallbacks.")
    p.add_argument("--dataset", required=True)
    p.add_argument("--capture", default="tools/ragas/captured_pilot.jsonl")
    p.add_argument("--nemotron-scores", default="tools/ragas/ragas_scores.jsonl")
    p.add_argument("--groq-scores", default="tools/ragas/ragas_scores_groq.jsonl")
    p.add_argument("--groq-csv", default="tools/ragas/ragas_scores_groq.csv")
    p.add_argument("--gemini-scores", default="tools/ragas/ragas_scores_gemini.jsonl")
    p.add_argument("--gemini-csv", default="tools/ragas/ragas_scores_gemini.csv")
    p.add_argument("--summary", default="tools/ragas/ragas_summary_combined.csv")
    p.add_argument("--env-file", default="ai-services/llm_service/.env")
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--delay-seconds", type=float, default=90)
    p.add_argument("--retry-needs-review", action="store_true")
    p.add_argument("--allow-unverified-pilot", action="store_true")
    p.add_argument("--live", action="store_true")
    p.add_argument("--groq-models", default="openai/gpt-oss-20b,openai/gpt-oss-120b",
                   help="Ordered Groq model list, comma-separated; blank disables Groq")
    p.add_argument("--gemini-models", default="gemini-3.5-flash-lite",
                   help="Ordered Gemini model list, comma-separated; blank disables Gemini")
    p.add_argument("--max-output-tokens", type=int, default=3072,
                   help="Judge token limit to control free-tier TPM")
    a = p.parse_args()
    if not 1 <= a.batch_size <= 100 or a.delay_seconds < 0 or not 256 <= a.max_output_tokens <= 8192:
        p.error("batch-size must be 1..100 and delay-seconds nonnegative")
    from dotenv import dotenv_values
    config = dotenv_values(a.env_file)
    for name in ("CLARA_EVAL_TOKEN", "GROQ_API_KEY", "GEMINI_API_KEY"):
        if not os.environ.get(name) and config.get(name):
            os.environ[name] = config[name]


    dataset = read(Path(a.dataset))
    ids = [r.get("id") for r in dataset]
    if ids != [f"Q{i:03d}" for i in range(1, 101)]:
        p.error("Dataset must contain Q001-Q100, in order")
    cap, nem, groq, gemini = (Path(a.capture), Path(a.nemotron_scores), Path(a.groq_scores), Path(a.gemini_scores))
    summary = Path(a.summary)
    for path in (cap, groq, gemini, Path(a.groq_csv), Path(a.gemini_csv), summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    models = ([("groq", name.strip()) for name in a.groq_models.split(",") if name.strip()]
              + [("gemini", name.strip()) for name in a.gemini_models.split(",") if name.strip()])
    if not models:
        p.error("Specify at least one evaluator model")
    if a.live and not any(os.environ.get({"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]) for provider, _ in models):
        p.error("No configured evaluator API keys found in environment or .env")
    print("Evaluator fallback order:", " -> ".join(f"{provider}:{model}" for provider, model in models), flush=True)

    def report():
        captures, latest, scored = state(cap, nem, groq, gemini)
        with summary.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "capture_status", "reference_verified",
                             *[x for m in METRICS for x in (m, m + "_provider", m + "_model")],
                             "metrics_completed"])
            for question in dataset:
                qid = question["id"]
                row = captures.get(qid, question)
                values = []
                for m in METRICS:
                    s = scored.get((qid, m))
                    values.extend([s["score"], s.get("provider", ""), s.get("model", "")]
                                  if s else ["", "", ""])
                writer.writerow([qid, "completed" if qid in captures else latest.get(qid, {}).get("status", "pending"),
                                 row.get("reference_verified", row.get("expert_verified", False)),
                                 *values, sum((qid, m) in scored for m in METRICS)])
        fully = sum(all((qid, m) in scored for m in METRICS) for qid in ids)
        print(f"Summary {summary} | Captured {len(captures)}/100 | "
              f"Unique scores {len(scored)}/400 | Complete questions {fully}/100", flush=True)
        return captures, latest, scored

    captures, latest, scored = report()
    pending = [qid for qid in ids
               if not all((qid, m) in scored for m in METRICS)
               and (qid in captures or a.retry_needs_review
                    or latest.get(qid, {}).get("status") not in ("needs_review", "failed"))]
    selected = pending[:a.batch_size]
    print("Pending questions in this batch:", selected, flush=True)
    if not a.live:
        print("DRY RUN (no API requests). Add --live to execute.", flush=True)
        return
    last_started = None
    def run(command):
        nonlocal last_started
        if last_started is not None:
            time.sleep(max(0, a.delay_seconds - (time.monotonic() - last_started)))
        last_started = time.monotonic()
        print("Running", command[0], "for", command[command.index("--question-id") + 1], flush=True)
        return subprocess.run([sys.executable, *command], cwd=ROOT, check=False).returncode

    for qid in selected:
        captures, latest, scored = report()
        if qid not in captures:
            cmd = ["tools/ragas/run_capture_pilot.py", "--dataset", str(Path(a.dataset).resolve()),
                   "--out", str(cap.resolve()), "--max-questions", "1", "--question-id", qid, "--live"]
            if run(cmd):
                print(f"STOP: {qid} capture failed; saved results are intact")
                report()
                return
            captures, latest, scored = report()
            if qid not in captures:
                print(f"SKIP {qid}: no accepted guideline evidence. Review separately.")
                continue
        for metric in METRICS:
            if (qid, metric) in scored:
                print(f"SKIP {qid} {metric}: scored by {scored[(qid, metric)].get('provider')}", flush=True)
                continue
            # Keep every attempted model in its own provider-specific append-only score log.
            # Only fall back on an actual unsuccessful metric; never replace scored values.
            succeeded = False
            for provider, model in models:
                if not os.environ.get({"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]):
                    print(f"SKIP {provider}: API key missing", flush=True)
                    continue
                score_path = groq if provider == "groq" else gemini
                csv_path = Path(a.groq_csv) if provider == "groq" else Path(a.gemini_csv)
                cmd = ["tools/ragas/score_ragas.py", "--input", str(cap.resolve()),
                       "--output", str(score_path.resolve()), "--csv", str(csv_path.resolve()),
                       "--provider", provider, "--model", model, "--metric", metric,
                       "--max-output-tokens", str(a.max_output_tokens),
                       "--question-id", qid, "--max-questions", "1",
                       "--env-file", str(Path(a.env_file).resolve()),
                       "--rate-limit-retries", "2", "--live"]
                if a.allow_unverified_pilot:
                    cmd.append("--allow-unverified-pilot")
                print(f"Judge {qid} {metric} with {model}", flush=True)
                if run(cmd):
                    print(f"STOP: evaluator process error on {qid} {metric}; results preserved")
                    report()
                    return
                captures, latest, scored = report()
                if (qid, metric) in scored:
                    print(f"SUCCESS {qid} {metric}: {scored[(qid, metric)]['score']} from {model}", flush=True)
                    succeeded = True
                    break
                attempts = [r for r in read(score_path) if r.get("id") == qid and
                            r.get("metric") == metric and r.get("model") == model]
                failure = attempts[-1].get("error", "") if attempts else ""
                is_limit = any(term in failure.lower() for term in
                               ("429", "rate_limit", "tpm", "per minute", "per-day", "per day", "daily"))
                is_generation_failure = any(term in failure.lower() for term in
                                            ("incompleteoutput", "length", "max_tokens", "max completion"))
                if not (is_limit or is_generation_failure):
                    print(f"STOP: non-rate-limit evaluator error on {qid} {metric}: {failure[:200]}")
                    return
                print(f"Fallback: {provider}/{model} could not score {qid} {metric}; trying next model", flush=True)
            if not succeeded:
                print(f"STOP: all configured models failed on {qid} {metric}. "
                      "Existing metric scores remain intact.")
                report()
                return
    report()
    print("Batch ended; rerun same command to continue pending metrics.", flush=True)

if __name__ == "__main__":
    main()
