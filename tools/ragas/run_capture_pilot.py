"""Local-only CLARA guideline evidence capture. No LLM calls without --live."""
import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

def read_rows(path):
    p = Path(path)
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()] if p.exists() else []

def append(path, obj):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--out", default="captured_pilot.jsonl")
    p.add_argument("--url", default="http://127.0.0.1:8001/evaluation/guideline")
    p.add_argument("--max-questions", type=int, default=1)
    p.add_argument("--question-id", default="", help="Capture only this Q001-Q100 ID")
    p.add_argument("--live", action="store_true")
    a = p.parse_args()
    if not 1 <= a.max_questions <= 100:
        p.error("Batch supports 1 to 100 questions.")
    sample = read_rows(a.dataset)
    if len(sample) != 100 or [row.get("id") for row in sample] != [f"Q{i:03d}" for i in range(1, 101)]:
        raise SystemExit("Expected exactly 100 ordered records Q001 through Q100.")
    if a.question_id and a.question_id not in {row["id"] for row in sample}:
        p.error("Unknown question ID")
    completed = {r.get("id") for r in read_rows(a.out) if r.get("status") == "completed" and r.get("ragas_ready") and r.get("retrieved_contexts")}
    todo = [r for r in sample if r["id"] not in completed and (not a.question_id or r["id"] == a.question_id)][:a.max_questions]
    print("Capture ready; requests planned:", len(todo) if a.live else 0, "previously completed:", sorted(completed))
    if not a.live:
        print("DRY RUN: no API calls")
        return
    token = os.getenv("CLARA_EVAL_TOKEN", "")
    if not token:
        raise SystemExit("Set CLARA_EVAL_TOKEN before running live capture.")
    for idx, row in enumerate(todo):
        if idx:
            time.sleep(20)
        payload = {"message": row["question"], "patient_id": None, "admission_id": None, "history": [],
                   "session_id": "ragas-capture-" + row["id"], "active_section": None}
        req = urllib.request.Request(a.url, data=json.dumps(payload).encode("utf-8"), method="POST",
                  headers={"Content-Type": "application/json", "X-Clara-Eval-Token": token})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=240) as response:
                result = json.load(response)
            contexts = result.get("retrieved_contexts") or []
            ready = bool(result.get("ragas_ready")) and bool(contexts) and bool(result.get("response", "").strip())
            record = {"id": row["id"], "status": "completed" if ready else "needs_review",
                      "question": row["question"], "reference_answer": row["reference_answer"],
                      "reference_verified": bool(row.get("expert_verified", False)),
                      "response": result.get("response", ""), "retrieved_contexts": contexts,
                      "source_metadata": result.get("sources", []), "ragas_ready": ready,
                      "model_configured": result.get("llm_model_configured"),
                      "evaluation_status": result.get("evaluation_status"),
                      "duration_seconds": round(time.monotonic() - start, 2),
                      "recorded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        except urllib.error.HTTPError as e:
            record = {"id": row["id"], "status": "failed", "error": f"HTTP {e.code}: {e.read(1000).decode('utf-8', 'replace')}"}
        except (OSError, ValueError, TimeoutError) as e:
            record = {"id": row["id"], "status": "failed", "error": str(e)}
        append(a.out, record)
        print(row["id"], record["status"], "contexts:", len(record.get("retrieved_contexts") or []))
        if record["status"] != "completed":
            print("Stopped to preserve free-tier usage; inspect", a.out)
            break
if __name__ == "__main__":
    main()
