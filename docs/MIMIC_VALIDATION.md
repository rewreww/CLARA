# MIMIC import and survey handoff

The configured PDF source is `%USERPROFILE%\Desktop\MIMIC_100_Patients`.
The configured database is `clara_mimic_test`, using the existing local PostgreSQL credentials.
`Desktop\Patients` is preserved. CLARA does not read Source_CSV files for this import.
Background import is disabled so that a restart cannot silently begin a full import.
Keep the export unchanged during validation; unchanged size, modification time and parser version are used to skip previously completed PDFs.

## Start and representative import

Run PowerShell in `C:\clara-system`. PostgreSQL must be running (Windows Services → postgresql-x64-18 → Start, as administrator if necessary).

```powershell
.\start-clara.ps1 -NoBrowser
.\scripts\import-mimic.ps1 -Patients Patient_10014729
```

Open http://localhost:3000. Read and accept the research agreement yourself. Select the patient and an admission, then open Patient records.
The initial technical smoke check uses Patient_10014729; this is not a completed manual CSV validation.
Technical checks on November 6: 199 PDFs imported with zero reported failures; a repeat import skipped all 199 without adding documents. Admission-scoped API retrieval, source PDFs and a live streaming Groq answer passed. Backend/frontend builds and 61 regression tests passed. The full agreement-to-record browser interaction and clinician review remain manual checks.
Choose additional patients from Patient_Index.csv: one with several admissions, one with extensive ICU and medication-administration records, and one with unlinked records.
Import each using the same command with its actual folder name. Logs are saved under `.clara\mimic-import`.
Do not run imports concurrently. A stopped import can be resumed with the same command.

## Compare representative results yourself

For each selected patient/admission, use both **Extracted rows** and **Source PDFs**. Compare displayed cells against that patient's `Source_CSV` files, filtering by subject_id and hadm_id where supplied. Records without hadm_id must stay under **Records without an admission link**.

- Check IDs and admission dates against patients/admissions. Age is the export's age in its reference year; dates are shifted and must not be interpreted as current dates.
- Labs: join by the printed laboratory result identifier (labevent_id), then check label, value, unit, reference lower/upper limits, source flag and charttime. Check a negative result, unavailable value, comparator and abnormal result. For example, hemoglobin printed as g/dL must remain g/dL, not be labeled g/L.
- ICU rows: match the selected stay, displayed observation, timestamp, value and unit against chartevents/outputevents/datetimeevents. Check multiple rows on multipage PDFs. Input/ingredient events retain amount and rate as separate printed cells.
- Medication orders: match prescriptions/pharmacy separately from emar/emar_detail. Verify start/stop times, dose, dose unit, route and administration status. A prescription is not proof a dose was administered.
- Diagnoses/procedures: preserve ICD code as text, version and printed description. Check microbiology, provider orders, transfers/services and administrative categories too.
- Open source links on both the first and a later PDF page. Confirm that the citation is the same patient and admission.
- Ask a specific question such as “Summarize hemoglobin values with units and dates.” Check every answer against cited PDFs. Change admission and confirm a new chat starts. Reopen a saved chat and confirm its admission is restored. Test unlinked records separately.

PDF exports show selected source columns, not every CSV field. Compare the fields actually printed; never count an unavailable PDF field as successfully extracted from CSV. Visual line wrapping remains in raw cells. Missing values are unknown. The AI uses a bounded retrieval subset (up to 40 matching rows and 24,000 characters), not the complete medical record. Broad summaries can omit records; use category tabs, search, pagination and original PDFs for review. Narrative discharge summaries are absent. Legacy automated clinical rules and ML assessments are disabled for MIMIC records.

## Import and manually validate all 100

After representative checks pass:

```powershell
.\scripts\import-mimic.ps1 -All
```

This scans all 100 patient folders and can take a long time. Keep PostgreSQL and CLARA running. Monitor another PowerShell window with:

```powershell
(Invoke-RestMethod http://localhost:5000/api/pdfingestion/sync/status).events | Select-Object -Last 5
```

For every patient record the folder ID, admission IDs, expected/imported PDF counts, failed PDFs, categories checked, source CSV comparisons, discrepancies and reviewer/date. Require zero unresolved failures. Compare document inventory to Document_Index.csv plus the patient/admission overview PDFs (28,774 PDFs in this export; 100 patients and 275 admission folders). Document_Index.csv excludes the 375 overview PDFs. Do not compare the total PDF-table row count directly to all CSV rows: overview tables and selected export fields make those different quantities.

Useful read-only SQL in pgAdmin, connected specifically to `clara_mimic_test`:

```sql
SELECT count(*) FROM patients;
SELECT "PatientId", "ExtractionStatus", count(*)
FROM patient_documents GROUP BY 1, 2 ORDER BY 1, 2;
SELECT "PatientId", "AdmissionId", "Category", count(*)
FROM mimic_pdf_rows GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
```

## Switch the reviewed database and source together

Do this only after your manual sign-off. In pgAdmin back up `clara_mimic_test` and restore into a new database named `clara_mimic_validated`; verify its counts and source comparisons. Preserve both `clara_db` and the test database.
Stop CLARA with `.\stop-clara.ps1`. In `backend/appsettings.json`, set the **same PatientDocumentSync section** to the reviewed source FolderPath and `DatabaseName: clara_mimic_validated`; keep Enabled false for the frozen survey dataset. Check that `appsettings.Development.local.json` has no conflicting PatientDocumentSync overrides. Restart with `.\start-clara.ps1 -NoBrowser` and repeat patient/admission/PDF/chat checks.
The source path and database name are read when the backend starts; restart after changing them. Never point a MIMIC source at the legacy database.

## Hosted survey

The local app is http://localhost:3000. The existing Vercel frontend must be rebuilt/deployed with these frontend changes before surveying through its public URL; an old frontend does not support admission selection. Follow `docs/MICROSOFT_TUNNEL.md` for the existing protected gateway and deployment. Do not distribute the survey link until the reviewed database is active, the updated frontend is deployed, and a phone on mobile data can select a patient/admission, view records, open PDFs and complete a cited chat response. Verify both a new and a restored conversation.

The research agreement is acknowledged by each user. Technical startup, build and smoke checks are separate from your manual dataset validation and clinician evaluation.
