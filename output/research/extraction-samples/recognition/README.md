---
license: cc-by-4.0
pretty_name: Synthetic Medical Document Recognition Benchmark
language:
  - en
task_categories:
  - image-to-text
  - document-question-answering
tags:
  - medical
  - synthetic
  - document-ai
  - ocr
  - fhir
configs:
  - config_name: png_clear
    default: true
    data_files:
      - split: test
        path: "data/png/*_clear.png"
  - config_name: png_photo_misoriented_skewed_clipped
    data_files:
      - split: test
        path: "data/png/*_photo_mis_ske_cli.png"
  - config_name: png_photo_skewed
    data_files:
      - split: test
        path: "data/png/*_photo_ske.png"
  - config_name: png_photo_skewed_clipped
    data_files:
      - split: test
        path: "data/png/*_photo_ske_cli.png"
  - config_name: png_photo_stained
    data_files:
      - split: test
        path: "data/png/*_photo_sta.png"
  - config_name: png_photo_stained_misoriented_skewed
    data_files:
      - split: test
        path: "data/png/*_photo_sta_mis_ske.png"
  - config_name: png_photo_stained_misoriented_skewed_clipped
    data_files:
      - split: test
        path: "data/png/*_photo_sta_mis_ske_cli.png"
  - config_name: png_photo_stained_skewed
    data_files:
      - split: test
        path: "data/png/*_photo_sta_ske.png"
  - config_name: png_photocopy_misoriented
    data_files:
      - split: test
        path: "data/png/*_photocopy_mis.png"
  - config_name: png_photocopy_misoriented_rotated_clipped
    data_files:
      - split: test
        path: "data/png/*_photocopy_mis_rot_cli.png"
  - config_name: png_photocopy_rotated
    data_files:
      - split: test
        path: "data/png/*_photocopy_rot.png"
  - config_name: png_photocopy_rotated_clipped
    data_files:
      - split: test
        path: "data/png/*_photocopy_rot_cli.png"
  - config_name: png_photocopy_straight
    data_files:
      - split: test
        path: "data/png/*_photocopy_str.png"
---

# Synthetic Medical Document Recognition Benchmark

This dataset contains synthetic, English-language medical records rendered as
documents for evaluating automated data extraction and de-identification
systems. Each synthetic patient has a longitudinal FHIR R4 record and multiple
visual representations derived from that record.

Every rendered document is clearly marked as synthetic. This makes the dataset
suitable for manual testing, product demonstrations, and workflows that benefit
from realistic-looking medical documents without exposing real patient data.

The dataset is designed as an evaluation benchmark, not as a training corpus.
It is too small for representative model training, and its repeated elements,
synthetic-data notices, and watermarks could provide shortcuts for a trained
model.

All people, clinical histories, organizations, and practitioners in this
dataset are synthetic. The dataset is intended for software development and
benchmarking, not for clinical use.

## Bundle contents

The published bundle contains five synthetic patients:

- Adam Hirthe (`1ce276e5`)
- Andres O'Hara (`348deeaf`)
- Carolann Pfeffer (`ebd5380d`)
- Marion Cormier (`2a636504`)
- Rebecka Aufderhar (`8e9abf1d`)

For each patient, the bundle provides 27 document layouts across several
document categories and three visual template variants. The document categories
include clinical timelines, contact information and contact forms, diagnostic
documents, notes, observations, reports, surveys, and vaccination histories.

The bundle contains:

| Path | Contents |
| --- | --- |
| `data/html/` | 135 source documents with selectable text: 27 per patient. |
| `data/pdf/` | 1,890 PDFs. This includes searchable PDFs rendered directly from HTML and image-only PDFs for pristine and degraded variants. |
| `data/png/` | 5,707 page images rendered at 300 DPI. Multi-page documents have one PNG per page. |
| `data/fhir/patients/` | Five FHIR R4 transaction bundles containing the underlying longitudinal patient records. |
| `data/fhir/practitioners/` | Referenced practitioner resources needed to resolve the selected patient bundles. |
| `data/fhir/organizations/` | Referenced organization and location resources needed to resolve the selected patient bundles. |
| `data/manifest.json` | The selected patient files, supporting FHIR files, and file counts for the bundle. |

Supporting FHIR resources are stored once even when they are referenced by
multiple patients. The patient bundles contain their clinical resources and
resolve all internal `urn:uuid:` references. Practitioner, organization, and
location references that live outside a patient bundle can be resolved using
the companion files included under `data/fhir/`.

Synthea run metadata and the source-generation project are intentionally not
included. They are not required to consume the rendered documents or their
FHIR companions.

## Document categories and typical length

Each patient has one document for every document-category × template-variant
combination: nine document categories and three template variants, for 27
source documents per patient. The average lengths below were measured from the
clear 300-DPI renderings in this release. Each average covers 15 documents
(five patients × three template variants); the range shows the shortest and
longest document in that category.

| Document category | Contents | Average pages | Range |
| --- | --- | ---: | ---: |
| `clinical_timeline` | A chronological longitudinal record of encounters, procedures, diagnostic reports, conditions, medication requests, and immunizations. | 14.6 | 9–22 |
| `contact_form` | A patient-completed, handwritten-style contact form containing identity, demographic, address, telephone, email, and verification fields. | 1 | 1 |
| `contact_info` | A typed administrative summary of patient identity, demographics, address, telephone, email, and record-verification information. | 1 | 1 |
| `diagnostic` | Diagnostic and laboratory panels with result names, values, units, reference ranges, interpretations, status, date, and performer when available. | 4.53 | 2–10 |
| `notes` | Narrative procedure or clinical-activity notes with service dates and associated clinician and facility information. | 1 | 1 |
| `observation` | Charts and summaries of longitudinal numeric observations, such as weight, BMI, blood pressure, pulse, respiration, pain score, and GAD-7 score when present. | 1 | 1 |
| `report` | A compact overview of key medical data: allergies, conditions, medications, encounters, procedures, vaccinations, observations, and patient details. | 2.47 | 2–3 |
| `survey` | The latest PRAPARE social-needs survey rendered as a patient-completed paper or checkbox form. | 2 | 2 |
| `vaccination_history` | Immunization history with administration date, vaccine and CVX code, status, facility, manufacturer, lot, site, route, source, and notes when available. | 1.67 | 1–2 |

The degraded PNG and image-only PDF variants preserve the pagination of their
corresponding clear document.

### Three vendor and style variants

Every document category has `type_1`, `type_2`, and `type_3`. These are three
independent visual presentations of the same category of patient information,
intended to simulate documents produced by different vendors and systems.
Depending on the document category, the variants differ in branding,
typography, spacing, table or card structure, information density, handwriting
treatment, and patient-facing versus clinician-facing presentation.

The variants also exercise different date conventions where dates are displayed:

- `type_1` primarily uses US numeric dates such as `08/24/2026`;
- `type_2` primarily uses abbreviated month names such as `Aug 24, 2026`;
- `type_3` primarily uses ISO-style dates such as `2026-08-24`.

## Rendered document variants

The PNG collection contains a pristine rendering of every page and simulated
capture degradations suitable for document-recognition testing. These include:

- clear 300-DPI renders;
- photocopies with straight, misoriented, rotated, clipped, and combined
  variants;
- photographs with stains, perspective skew, page bend, misorientation,
  clipping, and combined variants.

Every degraded page is derived from its corresponding clear page. Image-only
PDFs combine the pages of each PNG variant in their original page order.
Searchable PDFs preserve the text and vector content of the HTML source.


## File naming

Files belonging to the same patient share a stable prefix:

```text
synthetic_<Given>_<Family>_<patient-id>
```

For example:

```text
synthetic_Adam_Hirthe_1ce276e5_report_type_2_ver_1.html
synthetic_Adam_Hirthe_1ce276e5_report_type_2_ver_1.pdf
synthetic_Adam_Hirthe_1ce276e5_report_type_2_ver_1_p_2_of_3_dpi_300_photo_ske.png
synthetic_Adam_Hirthe_1ce276e5.json
```

Common filename fields are:

- `type_<n>`: visual template variant;
- `ver_<n>`: document-content version;
- `p_<n>_of_<n>`: page number and total page count;
- `dpi_300`: raster resolution;
- `clear`, `photo_*`, or `photocopy_*`: capture/degradation variant;
- `_img.pdf`: a PDF assembled from raster page images rather than a
  searchable PDF rendered directly from HTML.

The degradation tokens can be read from left to right:

| Token | Meaning |
| --- | --- |
| `clear` | Pristine raster rendering without simulated capture degradation. |
| `photo` | Simulated photograph of a document. |
| `photocopy` | Simulated photocopied document. |
| `sta` | Stained with randomized marks or discoloration. |
| `ske` | Skewed: perspective, page bend, and rotation simulate a photograph taken at an angle. |
| `mis` | Misoriented by 90, 180, or 270 degrees. |
| `rot` | Rotated by a smaller non-right angle. |
| `cli` | Clipped: part of the page extends beyond the image boundary. |
| `str` | Straight photocopy without rotation or clipping. |

Combined tokens mean that all named effects are present. For example,
`photo_sta_ske` is a stained, skewed photograph;
`photo_mis_ske_cli` is a misoriented, skewed, clipped photograph; and
`photocopy_mis_rot_cli` is a misoriented, rotated, clipped photocopy.

The shared patient prefix is the join key between HTML, PDF, PNG, and patient
FHIR files. A patient FHIR bundle represents the complete longitudinal record;
it is therefore a companion to all documents for that patient, rather than a
ground-truth file for only one rendered document.

## Downloading selected files with Python

The full repository is large, so consumers can use
[`snapshot_download`](https://huggingface.co/docs/huggingface_hub/guides/download#filter-files-to-download)
from `huggingface_hub` with glob-style `allow_patterns` and `ignore_patterns`.
Install the client first:

```console
python -m pip install -U huggingface_hub
```

With `uv`, add it to a project with:

```console
uv add huggingface_hub
```

Or install it into the current environment without changing project
dependencies:

```console
uv pip install -U huggingface_hub
```

The following downloads every image-only PDF while skipping searchable PDFs,
HTML, PNG, and FHIR files:

```python
from huggingface_hub import snapshot_download

repo_id = "morzel85/synthetic-medical-document-recognition-benchmark"

snapshot_download(
    repo_id=repo_id,
    repo_type="dataset",
    allow_patterns="data/pdf/*_img.pdf",
    local_dir="benchmark",
)
```

Download only clear image-only PDFs:

```python
snapshot_download(
    repo_id=repo_id,
    repo_type="dataset",
    allow_patterns="data/pdf/*_clear*_img.pdf",
    local_dir="benchmark-clear-pdfs",
)
```

The wildcard between `clear` and `_img.pdf` also matches the optional page
count in names such as `_clear_3p_img.pdf`.

Download all image-only PDFs that simulate stained photographs, including
stained-and-skewed and other combined variants:

```python
snapshot_download(
    repo_id=repo_id,
    repo_type="dataset",
    allow_patterns="data/pdf/*_photo_sta*_img.pdf",
    local_dir="benchmark-stained-photo-pdfs",
)
```

Download only the searchable PDFs rendered directly from HTML:

```python
snapshot_download(
    repo_id=repo_id,
    repo_type="dataset",
    allow_patterns="data/pdf/*.pdf",
    ignore_patterns="data/pdf/*_img.pdf",
    local_dir="benchmark-searchable-pdfs",
)
```

Patterns can also select a patient, document family, or condition. For example,
this downloads Adam Hirthe's clear report PDFs:

```python
snapshot_download(
    repo_id=repo_id,
    repo_type="dataset",
    allow_patterns=(
        "data/pdf/synthetic_Adam_Hirthe_1ce276e5_report_*_clear*_img.pdf"
    ),
    local_dir="adam-clear-reports",
)
```

The same approach works for `data/png/`, `data/html/`, and `data/fhir/`.

## Simulated handwriting

Handwritten-looking fields are rendered using CSS and handwriting fonts
licensed under the SIL Open Font License, with per-glyph variation added during
rendering. They are not produced using a handwriting model trained on the
[IAM Handwriting Database](https://fki.tic.heia-fr.ch/databases/iam-handwriting-database).
Such a model might produce more realistic results, but it could introduce
licensing restrictions because the database's official terms limit its use to
non-commercial research. This dataset is intended to support both commercial
and non-commercial use under the CC BY 4.0 license.

## Author and attribution

Created by [Miłosz Orzeł](https://morzel.net).

The underlying synthetic health records were generated with
[Synthea](https://synthetichealth.github.io/synthea/).
