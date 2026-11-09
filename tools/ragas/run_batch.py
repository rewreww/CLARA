"""Resumable CLARA RAGAS batch runner. Run locally with the existing backend."""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

METRICS = ("context_recall", "context_precision", "faithfulness", "answer_relevancy")
ROOT = Path(__file__).resolve().parents[2]

def rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def snapshot(captures, scores, provider, model):
    completed = {r.get("id"): r for r in rows(captures)
                 if r.get("status") == "completed" and r.get("ragas_ready") and r.get("retrieved_contexts")}
    scored = {}
    for r in rows(scores):
        if r.get("provider") == provider and r.get("model") == model and r.get("status") == "scored":
            scored[(r.get("id"), r.get("metric"))] = r
    return completed, scored

def main():
    p = argparse.ArgumentParser(description="Capture and score a resumable CLARA batch; stop on failures.")
    p.add_argument("--dataset", required=True)
    p.add_argument("--capture", default="tools/ragas/captured_pilot.jsonl")
    p.add_argument("--scores", default="tools/ragas/ragas_scores.jsonl")
    p.add_argument("--csv", default="tools/ragas/ragas_scores.csv")
    p.add_argument("--summary", default="tools/ragas/ragas_summary.csv")
    p.add_argument("--env-file", default="ai-services/llm_service/.env")
    p.add_argument("--provider", choices=("openrouter", "groq"), default="openrouter")
    p.add_argument("--model", default="")
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--delay-seconds", type=float, default=30)
    p.add_argument("--allow-unverified-pilot", action="store_true")
    p.add_argument("--live", action="store_true", help="Required to make API requests")
    a = p.parse_args()
    if not 1 <= a.batch_size <= 100 or a.delay_seconds < 0:
        p.error("batch-size must be 1..100 and delay-seconds nonnegative")
    try:
        from dotenv import dotenv_values
    except ImportError:
        p.error("Install dependencies from tools/ragas/requirements_ragas.txt first")
    cfg = dotenv_values(a.env_file)
    model = a.model or (cfg.get("OPENROUTER_MODEL") if a.provider == "openrouter" else cfg.get("GROQ_MODEL"))
    model = model or ("nvidia/nemotron-3-ultra-550b-a55b:free" if a.provider == "openrouter" else "openai/gpt-oss-20b")
    if a.provider == "openrouter" and not model.endswith(":free"):
        p.error("OpenRouter model must end in :free")
    dataset = rows(Path(a.dataset))
    ids = [r.get("id") for r in dataset]
    if len(ids) != 100 or ids != [f"Q{i:03d}" for i in range(1, 101)]:
        p.error("Dataset must contain Q001-Q100 in order")
    capture, scores = Path(a.capture), Path(a.scores)
    for path in (capture, scores, Path(a.csv), Path(a.summary)):
        path.parent.mkdir(parents=True, exist_ok=True)
    def report():
        complete, graded = snapshot(capture, scores, a.provider, model)
        with Path(a.summary).open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "capture_status", *METRICS, "reference_verified"])
            for item in dataset:
                id = item["id"]
                cr = complete.get(id)
                writer.writerow([id, "completed" if cr else "pending",
                    *[graded.get((id, metric), {}).get("score", "") for metric in METRICS],
                    bool((cr or item).get("reference_verified", (cr or item).get("expert_verified", False)))])
        print(f"Saved summary: {a.summary} | Captured {len(complete)}/100 | Scores {len(graded)}/400", flush=True)
    report()
    if not a.live:
        print("DRY RUN: no requests made. Add --live to execute.")
        return
    completed, graded = snapshot(capture, scores, a.provider, model)
    pending = [id for id in ids if id not in completed or any((id, m) not in graded for m in METRICS)]
    target_ids = pending[:a.batch_size]
    if not target_ids:
        print("Everything already scored.")
        return
    last_call = 0
    def run(args):
        nonlocal last_call
        if last_call:
            time.sleep(max(0, a.delay_seconds - (time.monotonic() - last_call)))
        print("Running:", " ".join(args[2:]), flush=True)
        last_call = time.monotonic()
        return subprocess.run([sys.executable, *args], cwd=ROOT, check=False).returncode
    for id in target_ids:
        completed, graded = snapshot(capture, scores, a.provider, model)
        if id not in completed:
            cmd = ["tools/ragas/run_capture_pilot.py", "--dataset", str(Path(a.dataset).resolve()),
                   "--out", str(capture.resolve()), "--max-questions", "1", "--live"]
            if run(cmd) != 0:
                print(f"STOP: capture script failed while targeting {id}.")
                report()
                return
            completed, graded = snapshot(capture, scores, a.provider, model)
            if id not in completed:
                print(f"STOP: {id} lacks an accepted captured response. Inspect {capture}")
                report()
                return
        for metric in METRICS:
            if (id, metric) in graded:
                print(f"Skipping existing {id} {metric}")
                continue
            cmd = ["tools/ragas/score_ragas.py", "--input", str(capture.resolve()),
                   "--output", str(scores.resolve()), "--csv", str(Path(a.csv).resolve()),
                   "--provider", a.provider, "--model", model, "--metric", metric,
                   "--max-questions", "1", "--env-file", str(Path(a.env_file).resolve()), "--live"]
            if a.allow_unverified_pilot:
                cmd.append("--allow-unverified-pilot")
            if run(cmd) != 0:
                print(f"STOP: scoring subprocess failed on {id} {metric}")
                report()
                return
            completed, graded = snapshot(capture, scores, a.provider, model)
            if (id, metric) not in graded:
                print(f"STOP: scoring failed on {id} {metric}; review {scores}")
                report()
                return
            print(f"Success: {id} {metric} = {graded[(id, metric)]['score']}", flush=True)
        report()
    print("Batch finished. Rerun the same command to continue.", flush=True)

if __name__ == "__main__":
    main()
