# CLARA guideline evaluation toolkit

This is a separate Python evaluation tool for improving CLARA's answers from guideline PDFs. It does not change CLARA, ingest PDFs, implement retrieval, or generate reference answers. Your existing CLARA pipeline remains responsible for extraction, retrieval, and generation. Start with guideline-only questions, then evaluate patient and mixed-source questions in a later, separate implementation.

## Start here on Windows

1. Extract the ZIP into a normal folder, such as `Documents\CLARA_Guideline_Evaluation`.
2. Install Python 3.12 from python.org if needed. Double-click `SETUP_WINDOWS.bat`. It installs dependencies in a private `.venv` folder and runs offline tests. Internet is required for installation.
3. Open this folder in VS Code. Open Terminal → New Terminal. Use the commands below in that folder.
4. Run this safe demonstration check. It makes **no model calls**:

```powershell
.venv\Scripts\python evaluate_guidelines.py check --questions examples/toy_questions.jsonl --outputs examples/toy_outputs.jsonl
```

Expected: `Validated 1 questions, 1 outputs; 0 missing outputs.` The example is an invented, nonmedical citation manual. It is not a PHA guideline or a thesis test case.

On macOS/Linux: `python3.12 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, then replace `.venv\Scripts\python` with `.venv/bin/python` in commands. Offline input validation and unit tests need only the Python standard library. Real scoring needs the installed dependencies.

## First real pilot: one guideline and five questions

1. Put **one exact guideline PDF already ingested by CLARA** inside `guidelines/`. Keep its filename stable. Check extraction manually, especially tables, recommendation conditions, units, symbols, and page mapping. Ragas scores do not independently verify PDF extraction.
2. Prepare five development questions. Write short reference answers directly from the PDF, preserving relevant conditions, values, and units. Save one JSON object per line in `data/dev_questions.jsonl`, following `examples/toy_questions.jsonl`. Remove `demonstration_only` for real cases. A line can contain nested objects; the entire question must remain on one physical line. JSON uses double quotes and `true`/`false`.
3. Source-check every reference against its original PDF before setting `reference_source_checked` to `true`. This means researcher source-checking, not clinical validation or expert review. Record supporting verbatim excerpts, filename, stable document ID and **1-based physical PDF page**. Preserve the guideline title/version/date in your document registry. A printed page label can differ from the physical PDF page.
4. Ask CLARA **only each question**, using its normal guideline corpus. Do not send it the reference answer or reference evidence. Export its response and the exact context that reached the generator into `data/dev_outputs.jsonl`.
5. Run `check`, configure evaluator settings, then run `score` below.

Initially cover direct retrieval, conditional recommendations, multiple supporting passages, and clearly unanswerable questions. Five cases are a debugging pilot, not a justified final thesis sample size. Choose the eventual sample size and distribution with your adviser.

## What CLARA must export (integration point)

The examples contain the complete input schemas. Match outputs to questions with a unique `id`.

Capture context **after filtering, reranking and truncation, immediately before the final generation request**. Preserve passage text and its supplied order. Each context has `rank` starting at 1, `source_type: "guideline"`, `document_id`, `pdf_file`, `page`, `text`, and optionally `chunk_id`. If a chunk crosses pages, export separate page-specific passages while preserving their text/order, or adapt the schema before testing. Do not invent a single page for a cross-page chunk.

`contexts_are_generation_input: true` is a declaration that you captured that final input. The tool cannot independently verify the declaration. Never substitute newly retrieved passages or raw search candidates that CLARA did not receive. Evaluate any earlier retrieval stage separately with a named protocol.

A minimal integration in the Python RAG service is:

```python
# Existing CLARA code: these variables must come from the actual generation path.
# Save this only AFTER the same ordered texts have been sent to the generator.
record = {
    "id": question_id,
    "question": user_question,
    "response": generated_answer,
    "contexts_are_generation_input": True,
    "contexts": actual_ordered_guideline_passages,
}
# Append json.dumps(record) + "\n" to an evaluation-only output file.
# Reference answers are not part of this record or CLARA's prompt.
```

This is an integration contract, not a patch to your current app. Your source code is needed to place it correctly. Include any other factual source material supplied to the generator if it supports claims; otherwise Faithfulness only tests the exported context. Restrict the initial run to guideline-only mode. Each output record must contain the complete final response. Use `response: ""` if generation returned nothing and `contexts: []` if no evidence reached it. Missing output records are reported separately. Unknown IDs, duplicate IDs, mixed patient contexts and invalid ranks are rejected.

## Evaluator configuration

Copy `.env.example` to `.env`. Fill a chat evaluator model/key and an embedding model/key. Keys stay on your machine; do not send them in chat or include `.env` in shared archives. API-based evaluation can incur charges and sends questions, passages, references and answers to the configured evaluator provider. Start with the five-case pilot.

The evaluator can use an OpenAI-compatible chat endpoint. A Grok generator and a different evaluator are possible, but the exact endpoint/model must support the structured-output behavior used by Ragas; verify this with the pilot. An OpenAI-compatible chat endpoint does not automatically supply embeddings: configure a separate supported embeddings endpoint. A blank base URL selects OpenAI. The toolkit does not supply models, keys, or free API credits. A compatible local endpoint can be configured; its compatibility and performance still need testing.

Use a fixed evaluator model and evaluation embedding model across comparisons. Evaluation embeddings are separate from CLARA's retrieval embeddings. Temperature is 0, but model scoring can still vary. Audit a sample of evaluator judgments against the source and repeat a small unchanged subset to assess variation before interpreting small improvements.

Copy `pipeline_config.example.json` to `pipeline_config.json`. Replace all `FILL_ME` values with actual settings. `chunk_size` and `chunk_overlap` must describe the same units used by your pipeline (record units with the values, e.g., `"800 tokens"`). Record the actual generator model, retrieval embedding model, top-k, CLARA version/commit, and SHA-256 of the exact system prompt. The allowlisted config is copied to run reports; put no secrets in it.

## Check and score

```powershell
.venv\Scripts\python evaluate_guidelines.py check --questions data/dev_questions.jsonl --outputs data/dev_outputs.jsonl
.venv\Scripts\python evaluate_guidelines.py score --questions data/dev_questions.jsonl --outputs data/dev_outputs.jsonl --config pipeline_config.json --run-name baseline
```

Scoring runs sequentially. Multiple evaluator requests may be needed for each metric and question. No model requests are made by `check`, installation, or tests. Do not use toy scores in your thesis; scoring toy data requires an explicit `--allow-demo` flag.

Open the new timestamped folder in `results/`, then double-click **review.html**. It contains the question, response, reference, supporting evidence, actual supplied passages, scores and statuses. You also get:

- `scores.csv`: one row per question and metric, with a score or an explicit non-score status.
- `summary.json`: per-metric means, scored counts, total cases and status counts, plus separate answerable/unanswerable summaries.
- `manifest.json`: package/model settings, input hashes, PDF hashes and pipeline configuration.
- Frozen `questions.json` and `outputs.json`: evaluator-only copies for audit.

Runs get separate folders; the tool does not overwrite a previous run. Keep reports private until reviewed: they contain full input text. Document IDs and page numbers are validated structurally; researchers still need to check that excerpts and references actually correspond to the cited pages. The corpus hash proves which PDF bytes were used, not extraction quality.

## Metrics matching SOP 3

| Output | Ragas 0.3.9 implementation | Meaning / limitation |
|---|---|---|
| Context Precision | `LLMContextPrecisionWithoutReference` | Relevance and order of supplied guideline passages relative to the generated response; not an independent correctness check. |
| Context Recall | `LLMContextRecall` | Reference claims supported by retrieved/supplied guideline evidence; reference preparation affects reliability. |
| Faithfulness | `Faithfulness` | Generated claims supported by supplied context; does not independently establish clinical correctness. |
| Answer Relevancy | `ResponseRelevancy`, strictness 3 | Reverse-generated questions compared through embeddings; not a factual-accuracy score. Ragas can also penalize noncommittal answers. |

This deliberately pins Ragas 0.3.9 and its compatible LangChain adapter API for reproducibility; it is not a claim that 0.3.9 is the newest release. The pinned wrappers emit deprecation warnings in this release. Upgrade only as a separately validated protocol change. `requirements-lock.txt` records the fully resolved test environment; `requirements.txt` pins the three direct libraries plus SOCKS support. To reproduce the resolved environment on a compatible Python/platform, install with `-r requirements-lock.txt`. Setup uses the direct pins for portability; retain `pip freeze` with each study environment.

Scoring conventions are explicit:

- Answerable questions with a logged empty context receive zero Context Precision and Context Recall under your study convention. This is labeled `study_convention_zero`.
- Blank responses are excluded from Context Precision, Faithfulness and Answer Relevancy; Context Recall can still evaluate logged retrieval.
- Missing output records receive no invented score. Investigate them before interpreting results.
- Unanswerable questions are excluded from reference-based Context Recall. Review abstention manually; these four metrics alone do not measure safe refusal. For fair thesis reporting, use the separate answerable/unanswerable summaries rather than the overall mean when reporting these different tasks.
- Nonfinite metric values are labeled `not_assessable_or_no_valid_score`, never changed to 1. This status does not prove there were no claims: inspect the case.
- Evaluator exceptions are labeled by exception type and excluded from the mean. Fix and rerun failed cases/runs; do not count API failures as zero. Every summary exposes the denominator and all status counts.
- The package does not set an arbitrary clinical pass threshold or fabricate results. The four scores do not directly measure reference-answer correctness; inspect clinical conditions and claims against the PDF during manual review.

## Improvement cycle and final evaluation

1. Freeze the first development questions/references and exact corpus. Save the baseline configuration and outputs.
2. Review low-scoring and missing/error cases against the source. Low recall can indicate omitted evidence; low precision can indicate poorly ordered or irrelevant passages. Low faithfulness can indicate unsupported generated claims. These are investigation signals, not automatic diagnoses of the software fault.
3. Change one setting at a time (e.g., top-k, chunk boundaries, reranking or prompt). Keep the evaluator fixed.
4. Rerun the same questions through CLARA, export NEW outputs, and score under a new run name. Compare matched question/metric rows and manually review changed answers, alongside latency and cost. Do not compare means with different denominators without explaining exclusions.
5. Keep a distinct final question set that has never been used for tuning. `check --heldout data/final_questions.jsonl` detects exact normalized question-text or ID overlap; researchers must also check semantic overlap manually. The option does not certify that a set was truly withheld.
6. Questions marked `split: "final"` are locked for scoring unless `--allow-final` is supplied. Once the pipeline and evaluation protocol are frozen, perform the final run and retain every artifact. Do not repeatedly use final scores to tune the system.

## Verification performed for this package

Fifteen offline tests check validation, source/order rules, set overlap, missing outputs, empty contexts, exclusions, failed/NaN scores HTML escaping, and a complete report-writing run with mocked scores. Metric construction is checked against installed Ragas and LangChain versions without network calls. No real guideline ingestion, CLARA integration, model scoring, clinical validation or thesis results are claimed. A live pilot is still required with your actual guideline, CLARA logs and configured providers.

Official metric documentation used:
- https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/context_precision/
- https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/context_recall/
- https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/faithfulness/
- https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/answer_relevance/
