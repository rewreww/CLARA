# CLARA guideline development evaluation

## Verified baseline (November 2, 2026, Asia/Manila)

The completed report is
`.clara/evaluation/scores/20261101T160910005200Z_baseline-paced/review.html`.
Its directory name uses UTC. Five captured questions produced 15 valid scores:
Context Precision mean 0.46666666663 (5/5), Faithfulness 0.45714285714 (5/5),
Answer Relevancy 0.80248693279 (5/5). Context Recall is excluded for all five
pending researcher reference review. No evaluator errors remain in this report.
These five selected development questions do not establish overall system quality
or clinical correctness. Six successful metric values were reused from the linked
identical-input run; nine rate-limited values were retried after quota pacing was
added. The first compatibility attempt was aborted and marked as such.

The local-only `probe_retrieval.py` comparison disabled the recommendation filter
without changing the questions. It left selected sources unchanged for four
questions and did not fix off-target retrieval for question one. That change was
not promoted into the application. The probe is diagnostic, not a second Ragas
evaluation or evidence of improved answer quality.

For normal use from the repository root:

```powershell
.\evaluate-clara.ps1 -Action Check
.\evaluate-clara.ps1 -Action Score -RunName development
```

The default scores the three reference-free metrics on saved outputs. It does
not regenerate CLARA answers. After changing CLARA, capture fresh outputs into a
new run and point the toolkit CLI at them; rescoring old answers does not measure
an application improvement. After a researcher actually reviews and updates all
reference flags, `-ReferencesReviewed` enables validation and scoring of all four.
That switch cannot override unchecked flags.

The evaluation environment is `.clara/evaluation/venv`. CLARA's production
environment, patient ingestion workflow, live service, and guideline index are
not redeployed or rebuilt by this workflow. This pilot exercises the actual
`chat_stream` handler in a separate process, with empty patient ID and history.
Patient tools, clinical rules, and predictions are blocked in the pilot.
The wider application still contains rule and prediction code; this pilot does
not establish that the whole application is RAG/LLM-only.

## Reproducible artifacts

- `audit_guidelines.py`: extract all 11 PDFs (2,508 physical pages) once, cached
  by SHA-256 under `.clara/evaluation/extraction`. Unchanged PDFs reuse the cache.
- `.clara/evaluation/corpus.json`: document hashes, extractor version, page counts,
  sparse-page flags and cache locations. This is not a visual/clinical validation.
- `.clara/evaluation/pilot/draft_questions.jsonl`: five AI-drafted development
  questions/references based on the 2020 hypertension guideline. A researcher
  must check these before setting `reference_source_checked` to true.
- `generation_questions.jsonl`: only IDs and questions; references are excluded.
- Capture folders: exact prompts for every generation attempt, ordered selected
  passage texts, answers, completion status, pipeline configuration.
- `captured_outputs.jsonl`: successful captures only; `attempts.json` retains
  failed attempts. Missing cases remain explicitly represented in scoring.

The normal chat path gains opt-in ContextVar tracing only. It does not write
evaluation logs by default. Capture supports the Groq adapter; adapters that
truncate tokens or silently fall back are rejected until instrumented correctly.
Cross-page passages are split using verified contiguous matches in cached PDF
text, preserving all original characters and order. Missing or ambiguous matches
fail capture rather than inventing provenance. This verifies source association,
not whether PDF extraction preserved every symbol or table relationship.

## Commands (from C:\clara-system)

```powershell
.\.venv\Scripts\python.exe evaluation\audit_guidelines.py
# Run prepare_pilot.py only once; it refuses to overwrite researcher edits.
.\.venv\Scripts\python.exe evaluation\prepare_pilot.py
# This explicitly makes real generator requests using the existing configuration:
.\.venv\Scripts\python.exe evaluation\capture_pilot.py --questions .clara\evaluation\pilot\generation_questions.jsonl --output .clara\evaluation\pilot\NEW-RUN --generate
```

For the initial baseline, `prepare_scoring.py` merges `baseline-01` and `retry-01`
and retains the attempt ledger. Do not reuse these names for later experiments.
Each later comparison must use new output folders and record its changed setting.

Evaluator settings are private in `CLARA_Guideline_Evaluation/.env` (Git-ignored).
The evaluator uses the existing Groq account and cached local MiniLM embeddings
via CLARA's Python interpreter. Embeddings do not require a separate paid API.
The evaluator runs in its own environment; resolved package versions must be
saved with the results. Models from the same provider/family can share biases;
scores are not independent clinical validation.

From `evaluation/CLARA_Guideline_Evaluation`, run:

```powershell
C:\clara-system\.clara\evaluation\venv\Scripts\python.exe evaluate_guidelines.py score --questions C:\clara-system\.clara\evaluation\pilot\draft_questions.jsonl --outputs C:\clara-system\.clara\evaluation\pilot\captured_outputs.jsonl --config C:\clara-system\.clara\evaluation\pilot\pipeline_config.json --guidelines C:\clara-system\ai-services\guidelines --results C:\clara-system\.clara\evaluation\scores --run-name baseline-reference-free --reference-free
```

`--reference-free` is development-only. It scores Context Precision, Faithfulness,
and Answer Relevancy, excluding Context Recall with an explicit reason. Draft
references are not passed to these metrics. After researcher source-checking,
remove the flag to score all four. Final cases remain locked and must not be
created from or tuned using these development questions.

## Extraction findings to address before wider evaluation

The automated pass flagged 29 sparse pages; 23 are in the heart-failure PDF.
Physical page 263 of that PDF contains plotted diagnostic-accuracy data that the
plain text extraction misses (it returns figure headings and a page label).
The heart-failure algorithm on physical page 19 is also flagged for visual review.
Sparse does not mean blank or unusable; dense pages may also have extraction errors.

Visual inspection of physical pages 16, 18 and 19 of the hypertension PDF found
that page 16's table shows a greater-than-or-equal symbol, while PyMuPDF returns
only a greater-than symbol for that cell. Do not silently correct all greater-than
signs: verify each affected span against its rendered page. Page 19 contains a
two-column ABPM/HBPM comparison: preserve row/column association when answering.
The 2,508-page collection has not been visually reviewed in full.

The existing ingestion rebuilds the whole collection, permits oversized
paragraphs despite a 350-word target, and records only the first page for chunks
spanning pages. Preserve the baseline, then test a page-aware, tokenizer-aware,
incremental replacement in a separate collection before deploying it. Do not
choose chunk size from page count or improve scores by changing references to
match model answers. Investigate retrieval of cover, contents and bibliography
pages in the captured baseline before tuning the same fixed development cases.

The included toolkit's mocked report test was fixed to mock Ragas imports and
package-version metadata. Its passing offline suite is not proof of live provider
compatibility. Real run manifests and per-case errors are the evidence for that.

Groq supports only `n=1` per completion request
([provider documentation](https://console.groq.com/docs/openai)). The Ragas wrapper
uses `bypass_n=True` so Answer Relevancy still generates three questions via
separate requests. Requested evaluator temperature stays at zero. `quota_client.py`
serializes evaluator requests and uses Groq's returned token quota headers to
pace them; metric timeouts allow this waiting. Individual errors remain unscored.
`progress.json` saves each completed metric. A completed run can be retried with
`--resume ABSOLUTE_RUN_FOLDER`: hashes, model settings, corpus, package versions
and protocol fields must match before successful scores can be reused. The new
manifest links the previous run and records the number of reused scores.
