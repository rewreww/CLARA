# CLARA cleanup and working-baseline audit

Date: 20 October 2026, Asia/Manila  
Baseline commit: `6a72ed9` — `safety v before cleanup`

## Engineering assessment

CLARA has a working local build and useful passing tests, but it is not ready for a broad deletion or restructuring pass. The main cleanup opportunities are generated files committed to Git, a handful of unused symbols, an optional legacy parser stack, and deployment instructions that no longer match the application.

Two reproducible correctness problems should be fixed before larger refactoring: stale patient responses can overwrite the current record's lab state, and the document watcher leaves pending semaphore waits behind after timed syncs. There are also database credentials in committed build outputs.

This was an analysis pass. No existing application source, dependencies, configuration, database records, model, guideline index, or patient documents were changed. New audit documents and isolated diagnostic probes were added. Builds generated local outputs; temporary audit build outputs were removed afterward.

**Confidence boundary:** builds, existing tests, read-only database/controller calls, and a synthetic ML prediction passed. This is not a full browser-to-database-to-LLM acceptance test, and it does not establish clinical validity.

## Baseline verification

- Git working tree was clean at the start.
- Frontend production build: passed with Vite 5.4.21 and Node 22.19.0. Output went to a separate audit directory so tracked `frontend/dist` stayed unchanged. Browserslist reported outdated browser data; this was not a build failure.
- Backend .NET build: passed with zero warnings/errors, targeting .NET 8 using installed SDK 10.0.201.
- Windows notifier build: passed with zero warnings/errors. No notification was sent.
- Frontend tests: **7/7 passed**, covering conversation restoration, context bounds, persistence merging, source URLs, and citation pages.
- LLM history and document-preview tests: **4/4 passed**. Model calls in the chat tests are mocked. The sandboxed attempt stalled; rerunning outside its socket restrictions passed.
- Legacy Python discharge-parser script: **22/22 assertions passed**. These are tests of the Python parser, not the active C# ingestion implementation.
- `pip check`: passed in the existing virtual environment.
- Local application services on ports 3000, 5000, 8000, 8001, 8002, and 11434 were stopped at inspection. PostgreSQL on 5432 was reachable.
- Database probe explicitly enabled PostgreSQL session read-only mode. It found **5 patients, 35 documents, 491 lab records, 9 discharge summaries, 0 documents marked failed, and 0 pending migrations**.
- The patient-list controller and eight additional read-only controller calls per patient completed: chemistry, hematology, microscopy, discharge list, parsed discharge, vitals, vitals timeline, and structured RAG context. This verifies controller execution against the existing database, not HTTP routing or the accuracy of every returned field.
- Two small synthetic checks of the production C# extractor passed: basic creatinine extraction and discharge diagnosis-section boundaries.
- Saved ML model: loaded successfully; a synthetic request returned all **8 targets** with probabilities in range. The model expects **147 features**; the probe supplied 5 and reported 142 missing. This is execution validation only.
- Chroma's SQLite catalog was inspected in read-only mode: `clara_guidelines`, 384 dimensions, 2,185 vector records. No embedding model or guideline retrieval was exercised, and no index rebuild was run.
- `docker compose config --quiet`: syntax/configuration parsing passed with an obsolete `version` warning. **Docker deployment itself is broken by source-level mismatches described below.**

Not exercised: live external/local LLM generation, live guideline retrieval, browser interaction, source-PDF HTTP preview, document additions/deletions, notification delivery, fresh-machine installation, Docker image builds, or model training. No ingestion, migration application, credential rotation, or Git history rewriting was performed. The audit probe restore used cached packages but could not obtain NuGet vulnerability data; no dependency-security certification is implied.

## Actual feature and service map

The active path is:

1. React/Vite on port 3000 proxies `/api/backend` to the .NET API on 5000 and `/api/llm` to FastAPI on 8001.
2. The .NET API serves PostgreSQL-backed patient records and previews. Its background workers ingest patient PDFs and notify Windows.
3. The LLM service retrieves structured patient data from the .NET API, evaluates safety rules, optionally retrieves guideline chunks from Chroma, and calls the selected model provider.
4. Assessment requests in streaming chat can call the ML service on port 8002.
5. The Python parser on port 8000 is a documented optional legacy path. The current frontend patient views do not use it.

### Keep: demonstrated application or operational dependencies

- `backend/Data`, migrations, `ClinicalTextExtractor`, `PdfParser`, sync services, controllers, and progress events.
- All frontend components currently in the tree: the import scan found no orphan component. `ActivityTimeline`, evidence/source previews, conversation history, prescriptions, and alerts are connected.
- `llm_service/mcp_tools.py`: this is the application's local Python tool dispatcher, not an independently launched MCP server.
- `rule_engine/rules.py`: used by clinical alerts and chat.
- `ml_service/app.py`, `model.pkl`, `model_meta.json`, and `column_config.json`: used by live assessment code in `llm_client.py:1432`.
- `rag/retriever.py`, `rag/embeddings.py`, guideline PDFs, and the current Chroma index: active runtime resources. Do not classify persisted vectors as disposable build output.
- `tools/CLARA.Notifier` and `scripts/register-clara-notifications.ps1`: the backend resolves and launches the notifier executable. It is not unused merely because the solution file does not list it.
- `dotnet-tools.json`: `dotnet tool list --local` successfully discovered `dotnet-ef` 8.0.11 here. Do not relocate it just because it is not under `.config`.
- `ml_service/train.py`, evaluation notebooks, dataset, and research samples: offline development/research assets, not runtime dependencies. Preserve or deliberately archive them rather than equating “not imported” with “unneeded.”

### High-confidence unused-code candidates

These have no executable repository consumer in the searches performed. Public endpoints and externally imported Python APIs still need compatibility consideration.

- `frontend/src/hooks/useDischarge.js`: no local importers; active panels perform their own discharge requests.
- `backend/Models/PatientDto.cs`: no C# consumers; the only other reference found was in an IDE cache. Active DTOs are defined in controllers.
- `FOLDER_SECTIONS` and `QUICK_PROMPTS` in `frontend/src/constants.js`: unreferenced exports. Keep the URL and `STATUS_COLOR` exports.
- `retrieve_guidelines` import in `ai-services/llm_service/llm_client.py:31`: unused. The wrapper function in `rag/retriever.py:143` has no executable caller found, but should be considered separately from its unused import.
- `parse_discharge_to_json` in `ai-services/discharge_parser.py:415`: no caller found.
- `extract_ecg_values` in `ai-services/lab_extractors.py:246`: no caller found. Removing it would remove an unconnected helper, not a verified working ECG feature.
- `_b64`, `_sys_rag`, and `Any` imports in `medical_text_api.py`: no loaded-name usages in the AST scan.
- Explicit .NET references to `FluentValidation.AspNetCore` and `Newtonsoft.Json`: no validators, registrations, or namespace/API consumers found. `Microsoft.AspNetCore.OpenApi` also has no direct API usage found. Treat these as dependency-removal candidates and rebuild/restore after each change; Swagger itself remains in use.
- The `AIServices` section in `backend/appsettings.json`: no C# reader found. It is misleading because changing `MLServiceUrl` there does not change the hardcoded Python ML URL.

The scan was not a formal proof of every unused local variable, CSS selector, dynamically loaded member, or external API consumer.

### Legacy or incomplete features: decide separately

- `medical_text_api.py` plus `discharge_parser.py` and `lab_extractors.py` form a coherent legacy stack of roughly 1,550 lines. The README still documents it and Vite still has `/api/labs` pointing to it. It can be retired after confirming there are no external scripts/Postman users and preserving relevant extraction fixtures. Do not delete just one module and leave its startup command.
- Backend `pdfingestion/patients` and `pdfingestion/extract` support the legacy parser and manual diagnostics. Keep them until the legacy retirement decision is complete.
- `/chat` and `/chat/stream` duplicate substantial orchestration. The UI calls streaming chat; the nonstreaming route is still an exposed API. ML assessment is wired into streaming chat, so consolidating them needs behavior-parity tests, not just deletion.
- The Imaging tab is explicitly a placeholder: `MainContent.jsx:81` displays “Imaging is not yet available.” It is not a working feature to preserve through testing; hiding it is a product choice.
- `frontend/tests/preview-fixture.mjs` is an intentionally isolated UI fixture server. It is a developer command, not unused application code.

## Repository hygiene

At the baseline, Git tracked **415 files totaling approximately 302.35 MiB**, including 70 source files in the application areas. Sizes are the current checkout's tracked file sizes, not Git-history size or total disk usage.

### Generated output to stop tracking

- `.codex-build/backend`: 102 files, approximately 38.39 MiB.
- `tmp/ui-backend-build`: 102 files, approximately 38.41 MiB.
- `frontend/dist`: 5 files, approximately 2.06 MiB.
- Together: **209 files / approximately 78.86 MiB**. They can be reproduced by builds; no checked-in startup command found uses those two temporary backend output locations.
- `backend/CLARA.Backend.csproj.lscache`: IDE-generated cache.
- `ai-services/ml_service/.ipynb_checkpoints/Untitled-checkpoint.ipynb`: byte-identical to `Untitled.ipynb`.
- Root `dasd` and the malformed filename beginning `s -ExecutionPolicy RemoteSigned)`: captured Git log text, not executable commands.

For build folders, prefer removing them from Git tracking while retaining local copies initially. Add scoped ignores in the same change, including `frontend/dist/`, `.codex-build/`, temporary build directories, `*.lscache`, `.ipynb_checkpoints/`, and local appsettings copies at any depth. Adding ignores alone does not untrack files already committed.

### Preserve or archive deliberately

- `ai-services/rag` is approximately 139.76 MiB, mostly persisted index data.
- Guideline PDFs total approximately 62.48 MiB.
- `output/research` and portions of `tmp` contain paper comparisons, parser probes, downloaded public fixtures, and extraction evidence. They are not production code, but some scripts reference their current paths.
- Do not blanket-delete `tmp`, all PDFs, datasets, notebooks, model files, or Chroma folders. Establish an archive/asset policy first.

## Findings that affect “keep it working”

### 1. High: stale responses can cross patient boundaries

Evidence: `frontend/src/hooks/useLabData.js:25` updates state after every response without checking which patient/request is still current. `reset()` clears data but does not invalidate an outstanding request. `App.jsx` keeps this hook mounted while patients change.

The diagnostic probe executes the actual hook source with controlled synthetic requests: start A, reset/select B, finish B, finish A. The final state contains A's results. Since the data object records section type but not patient ID, section matching does not prevent a same-section mixup.

Similar unguarded request patterns occur in `useTrends`, `useVitals`, `OverviewPanel`, `DischargePanel`, and `PrescriptionsPanel`; those were identified by inspection, not individually reproduced.

Fix direction: bind results to patient/request identity, cancel or invalidate old requests, reset loading/error state consistently, and add a delayed-response patient-switch regression test. `useChat` already uses cancellation and request versions and is a useful local pattern.

### 2. Medium: document watcher loses prompt wakeups after idle intervals

Evidence: `backend/Ingestion/PatientDocumentSyncWorker.cs:43` races `syncSignal.WaitAsync()` against `Task.Delay()`. When the delay wins, the losing semaphore wait remains queued.

The isolated probe reproduced the sequence: the abandoned waiter consumed the next release and the current waiter did not wake. Repeated idle intervals can accumulate waiters. Periodic scans still run, so this is delayed event-driven sync rather than proof of permanent data loss.

Fix direction: use the timeout overload of semaphore `WaitAsync`, or explicitly cancel/await the losing wait. Test idle interval → one file event → prompt sync.

### 3. High: database credentials are committed inside generated output

Both `.codex-build/backend/appsettings.Development.local.json` and `tmp/ui-backend-build/appsettings.Development.local.json` contain a nonempty database password. Values were not printed or included in this report. The existing ignore rule protects only `backend/appsettings.Development.local.json`.

Stop tracking these copies. If the repository/history has been shared, rotate the affected credential. Deleting the current files does not remove older commits; history cleanup, if needed, is a separate coordinated operation. No credential changes were made during the audit.

### 4. High for Docker use: deployment definitions do not match the application

- Compose builds `./ai-services/ml_service/Dockerfile`, which does not exist.
- `frontend/Dockerfile` copies `/app/build`; Vite emits `/app/dist`.
- The frontend image uses Node 18, while the installed locked PDF.js package declares Node `>=22.13.0 || >=24`.
- `frontend/nginx.conf` serves static files only. Production `/api/backend` and `/api/llm` requests have no proxy routes and can fall through to the SPA HTML.
- Compose has no LLM or PostgreSQL service/configuration, maps the ML service to port 8000 instead of its 8002 entry point, and maps backend traffic to port 80 without configuring that listening port in the checked-in setup.
- The separate `ai-services/Dockerfile` runs `python app.py` from the AI-services root, where no `app.py` exists.

Do not advertise Docker as an alternative working startup command until the complete chain is repaired and tested. A successful Compose config parse is not a deployment test.

### 5. Medium: a clean install is not the environment that passed the tests

The existing virtual environment has FastAPI 0.136.1, Uvicorn 0.46.0, and Pydantic 2.13.3. `requirements.txt` pins 0.104.1, 0.24.0, and 2.5.0 respectively. Several other dependencies are unpinned, and the tests directly import `httpx` through FastAPI's test client without a dedicated test dependency declaration.

`pip check` establishes that the current installed environment is consistent; it does not prove the declared environment installs or behaves identically. Validate a separate fresh environment before changing or pruning dependency versions. Align the README's Node requirement with the actual dependency engine constraint.

### 6. Medium: configuration and startup documentation drift

- `llm_client.py:49` defaults to Gemini; the README and project decisions describe Groq/free-local setup without documenting Gemini.
- `llm_client.py:1108` hardcodes the ML URL, so the .NET `AIServices` setting cannot redirect it.
- `backend/Program.cs:8` adds the development-local JSON file after the default configuration providers and in every environment. If present, its values can override environment/command-line configuration unexpectedly.
- The tracked backend settings contain no connection string. A clean clone needs an explicitly documented local connection-string setup before `dotnet run`.
- Frontend `package.json` lacks a test command even though seven tests exist.
- The notifier depends on a specific package directory under `%USERPROFILE%\\.nuget\\packages`, rather than restoring Windows App SDK through a normal package reference; it builds on this machine, but a fresh-machine setup is not established.

Make one accurate local runbook, distinguish mandatory and optional services, provide placeholder-only config examples, and document test commands. Preserve provider choices until the intended default is decided.

### 7. Medium: guideline rebuild replaces the working index before success is known

`rag/ingest.py:188` deletes the current collection before extracting/embedding the replacements. Individual embedding failures are skipped, and the command still prints completion, potentially with zero chunks.

This is why `python -m rag.ingest` should not be run casually during cleanup. Build and validate a replacement index first, then swap it in. The current index was retained untouched.

### 8. Medium: active extraction and UI behavior have little regression coverage

There is no committed .NET test project. The detailed parser test script validates the legacy Python implementation, while ingestion uses C#. Most important patient-switching, date selection, sync, extraction, and provider flows lack automated regression tests.

The large files are maintenance pressure points: `llm_client.py` 1,573 lines, `PatientDataController.cs` 935, `ClinicalTextExtractor.cs` 703, `OverviewPanel.jsx` 549, and `PatientDocumentSyncService.cs` 539. Splitting them is useful later, after behavior is characterized.

A further ingestion consideration: the unchanged-file shortcut checks content hash and whether *any* derived records exist (`PatientDocumentSyncService.cs:156,235`). A parser update alone will not automatically reparse previously indexed documents. Any extraction refactor needs an explicit reindex/version policy.

## Recommended cleanup sequence

1. **Protect the baseline.** Keep the existing commit. Separately back up PostgreSQL and the original patient PDF folder: Git does not back up that live state. Do not move/delete source PDFs as repository cleanup; ingestion intentionally removes database records when their source PDFs disappear.
2. **Fix the two reproduced correctness bugs in small changes**, with regression checks for patient-switch ordering and idle watcher wakeups. Re-run existing checks.
3. **Remove generated artifacts from tracking**, add scoped ignores, and address the credential copies. Preserve local build copies until the documented startup path is exercised.
4. **Remove high-confidence unused symbols/imports and duplicate checkpoint/log captures.** Restore/build/test after dependency changes. Avoid unrelated formatting rewrites.
5. **Establish repeatable commands and dependency declarations.** Verify a clean virtual environment and align docs/configuration. Repair Docker separately, or clearly mark it unsupported.
6. **Retire the legacy parser as a complete compatibility change** only after checking external usage and transferring useful tests/fixtures to the C# parser. Keep a documented transition rather than leaving broken imports/proxies.
7. **Refactor large modules** and consolidate discharge requests/chat orchestration only after characterization tests. Preserve the model, guideline index, provenance, and offline research assets.

## Reproducible checks

Run from `C:\clara-system` unless a working directory is shown.

```powershell
# Existing application checks
node --test frontend/tests/conversations.test.mjs
dotnet build backend/CLARA.Backend.csproj --no-restore
dotnet build tools/CLARA.Notifier/CLARA.Notifier.csproj --no-restore
.\.venv\Scripts\python.exe -m pip check
docker compose config --quiet

# From frontend: use a dedicated output to avoid rewriting tracked dist
npm run build -- --outDir ../tmp/cleanup-audit/frontend-build

# From ai-services
..\.venv\Scripts\python.exe test_discharge_parser.py

# From ai-services/llm_service
..\..\.venv\Scripts\python.exe -m unittest -v test_chat_history test_document_preview

# New audit-only diagnostics, from repository root
node tmp/cleanup-audit/race-probe.mjs
.\.venv\Scripts\python.exe tmp/cleanup-audit/ml-probe.py
dotnet run --project tmp/cleanup-audit/backend-probe/Audit.csproj
```

The race probe succeeds when it reproduces the current bug; it is not a passing regression test for a future fix. The backend probe sets read-only database mode, reads the configured local database, exercises controllers, reproduces the semaphore pattern, and emits counts/status only. Audit probes are retained for review, not installed into the application.
