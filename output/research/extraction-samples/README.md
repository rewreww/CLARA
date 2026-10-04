# Public synthetic medical-record samples for CLARA

Downloaded and inspected on 2026-09-06. All downloaded patient records are synthetic.
This folder is separate from CLARA's live patient folders and database.

## Start with these files

- Discharge summary: `australian/pdfs/0041_discharge_summary_AORTIC_STENOSIS_Conti.pdf`
- Laboratory tables: `recognition/data/pdf/synthetic_Adam_Hirthe_1ce276e5_diagnostic_type_1_ver_1.pdf`
- Narrative note: `recognition/data/pdf/synthetic_Adam_Hirthe_1ce276e5_notes_type_1_ver_1.pdf`
- Discharge reference fields: `australian/ground_truth.csv` and `australian/ground_truth.jsonl`
- Laboratory source record: `recognition/data/fhir/patients/synthetic_Adam_Hirthe_1ce276e5.json`
- Download URLs, exact repository revisions, licenses, file sizes and SHA-256 hashes: `download-manifest.json`

## Source and license

1. [RootCauseAnalytics synthetic Australian medical documents](https://huggingface.co/datasets/RootCauseAnalytics/synthetic-australian-medical-documents-sample), CC BY-NC 4.0.
   The free sample has 50 distinct documents with 50 distinct synthetic patient names across 29 document types; the additional versions do not represent additional patients.
   Downloaded four discharge summaries and two pathology reports, each with its corresponding variant: 12 PDFs. Two selected variants are clean copies, so not everything inside `pdfs_scanned` is an image-only scan.
   The pathology reports describe tissue examinations; they are not replacements for CLARA's chemistry, CBC or urinalysis tables. The discharge summaries are the closer match from this source.
   The original CSV/JSONL contains reference fields for all 50 documents; only the six selected document identities are downloaded here. Labels include demographics, diagnoses and medications where applicable. They are not exhaustive annotations of every clinical fact or laboratory measurement in each PDF.
   Preserve attribution and the noncommercial license. The creator's README is saved under `australian/README.md`.

2. [Synthetic Medical Document Recognition Benchmark, by Miłosz Orzeł](https://huggingface.co/datasets/morzel85/synthetic-medical-document-recognition-benchmark), CC BY 4.0; underlying synthetic records generated with Synthea.
   The full repository has five synthetic patients, 135 source documents and 1,890 PDFs including visual variants. Those PDF counts do not indicate independent patients.
   Downloaded three searchable PDFs for one synthetic patient (diagnostic tables, a narrative note and a medical overview), plus one image-only version of the diagnostic report: four PDFs.
   The companion FHIR bundle is a longitudinal record, not a document-specific answer key. Match its observations and dates to the displayed PDF before scoring. Reference ranges are explicitly absent in the selected diagnostic PDF; do not invent labels for them.
   Preserve attribution. The creator's README is saved under `recognition/README.md`.

## What was checked

The existing five local patient folders contain 35 PDFs: nine discharge files and 26 laboratory files, with 32 unique file hashes. Local patient information was not sent to either source. Layout inspection showed patient headers, multi-column lab results and reference intervals.

An isolated console program links CLARA's current `backend/Ingestion/PdfParser.cs` and `ClinicalTextExtractor.cs` directly. It uses existing local PdfPig assemblies and does not call the database, APIs or language model. Its source is under `tmp/extraction-probe/` at the project root.

`current-parser-probe.json` contains the outputs for all 16 public PDFs and four explicit numerical stress cases plus one heading-variation case. Both extraction methods were invoked directly for inspection; this bypasses the production document router. Lab results produced from a discharge document are therefore not evidence of production ingestion behavior.

Observed limitations:

- All five selected image-only PDFs yielded zero clinical text after removing parser page markers.
- All four clean Australian discharge summaries have a principal diagnosis visible in the PDF; the current `FinalDiagnosis` output is null. The current section patterns do not recognize that heading.
- A synthetic `BASOPHILS 0.5 %` input produces numeric value 50 instead of 0.5.
- Repeated creatinine values on two dates produce only the first observation in the probe.
- A micro-unit input loses its unit, and the deliberately constructed scientific-notation input is parsed as its mantissa alone.
- On the public diagnostic PDF, the leukocyte value 7.6059 is extracted as 7.605910 because adjacent unit digits enter the text stream. Several units or test-name variants are missed.

These are diagnostic checks, not a measured accuracy, precision, recall or F1 score. The database's fixed `ExtractionConfidence = 0.85m` is also not an empirical evaluation score.

## Evaluation use

Treat the selected files as development examples because they have already been inspected. Reserve different patients/documents for final evaluation, and keep all clean/scanned/template variants of a patient in the same split. Synthetic layout tests do not establish performance on real Philippine hospital records.

Define a shared answer schema for document fields and lab tuples (test, value, unit, date, reference interval and flag), check labels against the rendered pages, then compare the current parser and improvements on the same untouched evaluation documents. Report tabular-lab, narrative and scanned-document results separately. A higher score on this new dataset alone would not prove that CLARA outperforms the paper on its different, unreleased evaluation cohort.

For larger structured synthetic records, see [Synthea downloads](https://synthetichealth.github.io/downloads.html), including CSV and FHIR samples. These are not hospital-layout PDFs.
For real deidentified narrative discharge reports, see [MIMIC-IV-Note](https://physionet.org/content/mimic-iv-note/2.1/); access requires PhysioNet credentialing and the applicable data-use agreement. It is not a collection of original formatted hospital PDFs.
