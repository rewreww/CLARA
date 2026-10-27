# Demo record name removal

The current demo dataset has been processed for **personal names only**. This is
not complete de-identification: dates, ages, hospital numbers and other details
remain. Do not describe these records as anonymous or synthetic on that basis.

## Normal operation

- Continue using the existing Desktop `Patients` folders, patient IDs and launcher.
- Patient labels and structured chat context use `Patient <folder ID>`.
- The active PDFs have actual text redactions, including patient, physician and
  signatory names. Page counts, file paths and clinical text are preserved.
- Synchronization re-extracts those PDFs into PostgreSQL using the existing flow.
- Saved browser conversations are cleaned through the local LLM service before
  being restored. Conversation IDs, patient IDs, clinical text and source links
  remain intact. If cleanup is unavailable, old chats stay in storage and restore
  is retried when the service is available; they are not silently deleted.
- Known old names are also removed from historical model context and generated
  responses. The private dictionary is loaded from
  `.clara/name-redaction/names.json`, or `NAME_REDACTION_DICTIONARY` if set.

The original PDFs are recoverable in `.clara/name-redaction/originals`, outside
the served patient tree. The dictionary, manifest, staged PDFs and originals are
gitignored. They must remain private and must not be uploaded with the frontend.
Git alone does not back up the patient PDFs or the local PostgreSQL database.

## Adding or replacing PDFs

Patient-ID labels do not redact new PDF contents automatically. Newly added PDFs
must be checked and redacted before respondent use. `scripts/redact_demo_names.py`
stages name redactions without changing originals; `apply` checks original and
staged hashes, preserves recovery copies and then replaces the active PDFs.
Use a fresh work directory for another run. Keep the historical name dictionary
when processing a replacement dataset so old saved chats can still be cleaned.
This helper recognizes the current text-based demo layouts; it is not OCR or a
general personal-information detection system. Review unfamiliar layouts manually.

## Verification

The initial run compared all 35 files (57 pages), requiring identical non-name
text tokens and unchanged page counts. The production C# parser comparison uses:

```powershell
dotnet run --project scripts/tests/NameRedactionProbe -- ORIGINAL_ROOT REDACTED_ROOT
```

It compares demographics, laboratory extraction and discharge content, excluding
the three name-bearing discharge header fields. It never prints clinical values.
Render and inspect redacted PDFs before applying a new run.

With CLARA running, verify the patient APIs, document retrieval, PDF download
hashes and historical chat cleanup using:

```powershell
.\.venv\Scripts\python.exe scripts\verify_name_redaction.py
```

Only the current known names are covered by the historical chat dictionary;
unrelated names manually typed into a chat are not a general name-detection use case.
