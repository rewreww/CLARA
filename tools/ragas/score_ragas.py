"""Sequential, resumable RAGAS evaluator for CLARA's local evidence captures."""
import argparse
import asyncio
import csv
import datetime as dt
import json
import math
import os
import time
from pathlib import Path

os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")

def read_rows(path):
    p = Path(path)
    return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()] if p.exists() else []

def save_row(path, row):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def save_csv(path, rows):
    fields = ["id", "metric", "score", "status", "provider", "model", "reference_verified", "evaluated_at_utc", "error"]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

async def run():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="captured_pilot.jsonl")
    p.add_argument("--output", default="ragas_scores.jsonl")
    p.add_argument("--csv", default="ragas_scores.csv")
    p.add_argument("--provider", choices=("groq", "openrouter"), default="groq")
    p.add_argument("--model", default="")
    p.add_argument("--metric", choices=METRICS, default="context_recall")
    p.add_argument("--max-questions", type=int, default=1)
    p.add_argument("--question-id", default="", help="Score only this Q001-Q100 ID")
    p.add_argument("--env-file", default="")
    p.add_argument("--allow-unverified-pilot", action="store_true")
    p.add_argument("--delay-seconds", type=float, default=20.0)
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    if args.delay_seconds < 0:
        p.error("delay-seconds must be nonnegative")
    if not 1 <= args.max_questions <= 100:
        p.error("Batch max-questions must be between 1 and 100")
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    latest = {}
    for row in read_rows(args.input):
        if row.get("status") == "completed" and row.get("ragas_ready") and row.get("retrieved_contexts"):
            latest[row["id"]] = row
    valid = sorted(latest.values(), key=lambda r: r["id"])
    if not valid:
        raise SystemExit("No context-captured records. Run run_capture_pilot.py first.")
    if any(not r.get("reference_verified") for r in valid) and not args.allow_unverified_pilot:
        raise SystemExit("Reference answers not physician verified; use --allow-unverified-pilot for preliminary tests.")
    provider = args.provider
    model = args.model or (os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
                           if provider == "groq" else os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"))
    if provider == "openrouter" and not model.endswith(":free"):
        raise SystemExit("OpenRouter evaluator must use a :free model.")
    prior = read_rows(args.output)
    done = {(r.get("id"), r.get("metric"), r.get("provider"), r.get("model")) for r in prior if r.get("status") == "scored"}
    todo = [r for r in valid if (not args.question_id or r["id"] == args.question_id) and (r["id"], args.metric, provider, model) not in done][:args.max_questions]
    print("Eligible records:", len(valid), "metric:", args.metric, "model:", model, "new records:", len(todo))
    if not args.live:
        print("DRY RUN: no judge requests made")
        return
    api_key = os.getenv("GROQ_API_KEY" if provider == "groq" else "OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing evaluator API key in env-file or environment.")
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import ContextPrecisionWithReference, ContextRecall, Faithfulness, AnswerRelevancy
    base = "https://api.groq.com/openai/v1" if provider == "groq" else "https://openrouter.ai/api/v1"
    client = AsyncOpenAI(api_key=api_key, base_url=base, max_retries=0, timeout=90)
    llm = llm_factory(model, provider="openai", client=client, max_tokens=8192)
    if args.metric == "context_precision":
        evaluator = ContextPrecisionWithReference(llm=llm)
    elif args.metric == "context_recall":
        evaluator = ContextRecall(llm=llm)
    elif args.metric == "faithfulness":
        evaluator = Faithfulness(llm=llm)
    else:
        from ragas.embeddings import HuggingFaceEmbeddings
        evaluator = AnswerRelevancy(llm=llm, embeddings=HuggingFaceEmbeddings(model="sentence-transformers/all-MiniLM-L6-v2", device="cpu"))
    for index, row in enumerate(todo):
        if index:
            await asyncio.sleep(args.delay_seconds)
        if args.metric in ("context_precision", "context_recall"):
            inputs = {"user_input": row["question"], "retrieved_contexts": row["retrieved_contexts"], "reference": row["reference_answer"]}
        elif args.metric == "faithfulness":
            inputs = {"user_input": row["question"], "response": row["response"], "retrieved_contexts": row["retrieved_contexts"]}
        else:
            inputs = {"user_input": row["question"], "response": row["response"]}
        record = {"id": row["id"], "metric": args.metric, "provider": provider, "model": model,
                  "reference_verified": row.get("reference_verified", False),
                  "evaluated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            outcome = await evaluator.ascore(**inputs)
            score = float(outcome.value)
            if not math.isfinite(score):
                raise ValueError("RAGAS returned non-finite score")
            record.update(status="scored", score=score)
        except Exception as error:
            record.update(status="failed", error=f"{type(error).__name__}: {str(error)[:600]}")
        save_row(args.output, record)
        save_csv(args.csv, read_rows(args.output))
        print(record["id"], args.metric, record["status"], record.get("score", record.get("error")))
        if record["status"] != "scored":
            print("Stopped after evaluator failure to protect free-tier quota.")
            break
    print("Saved", args.output, "and", args.csv)

if __name__ == "__main__":
    asyncio.run(run())
