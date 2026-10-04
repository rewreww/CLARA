---
license: cc-by-nc-4.0
language:
  - en
task_categories:
  - token-classification
  - image-classification
  - image-to-text
  - object-detection
  - document-question-answering
  - text-classification
tags:
  - medical
  - healthcare
  - clinical
  - australian
  - health
  - synthetic
  - medical-record
  - document-ai
  - ocr
  - llm
  - sample
  - model
  - icd-10-am
  - named-entity-recognition
  - layout-analysis
size_categories:
  - n<1K
pretty_name: Synthetic Australian Medical Documents - Sample
thumbnail: preview.png
---
# Synthetic Australian Medical Documents - Sample
**A 50-document free sample of a 5,000-document library of synthetic Australian medical PDFs.** PHI-free. Modelled on Australian healthcare documentation. Pre-labelled with structured ground truth and pixel-precise bounding boxes. Released under CC-BY-NC 4.0 for evaluation and non-commercial research.

See [Pricing & licensing](#full-library--commercial-licensing) below.

## What's in this sample
| Field | Value |
| --- | --- |
| Documents | 50 |
| Document types | 29 (of 45 in full library) |
| Total field bboxes | 682 (avg 13.6 per doc) |
| Splits | 37 train / 13 test (stratified by doc type) |
| Format | Clean PDFs + scanned variants |
| Licence | CC-BY-NC 4.0 |
| Disclaimer | Every doc footer: *"SYNTHETIC TRAINING DOCUMENT - NOT FOR CLINICAL USE"* |

50 documents is enough to:

- Inspect the format and label schema
- Run a sanity-check fine-tune on document classification or NER
- Verify the ground-truth schema matches your downstream task
- Decide whether the full 5,000-doc library is worth licensing

## Why this library exists
The bottleneck for medical document AI in Australia is training data:

- Real hospital PDFs are locked behind the Privacy Act
- Generic synthetic medical text (LLM-generated) has no layout, no scans, no labels - useless for vision models like LayoutLMv3 / Donut / DocFormer
- Public datasets like MIMIC are US-centric, doc-type-limited, and increasingly restricted

This library is the missing piece: **visually realistic, fully-labelled, jurisdiction-specific synthetic PDFs**. Modelled on real Australian hospital and GP-clinic document conventions; every entity is synthetic.

## Document types in this sample (29 of 45)
| Doc type | Count |
| --- | --- |
| ed_assessment | 4 |
| discharge_summary | 4 |
| prescription | 3 |
| referral_letter | 3 |
| progress_note | 3 |
| medication_chart | 3 |
| pathology_report | 2 |
| physiotherapy_assessment | 2 |
| imaging_report | 2 |
| vascular_ultrasound_report | 2 |
| ecg_report | 2 |
| fluid_order | 2 |
| mental_health_assessment | 2 |
| anaesthetic_record | 1 |
| ambulance_record | 1 |
| audiology_assessment | 1 |
| ophthalmology_assessment | 1 |
| speech_pathology_assessment | 1 |
| endoscopy_report | 1 |
| ecg_12lead | 1 |
| pathology_request | 1 |
| medical_certificate | 1 |
| consent_for_treatment | 1 |
| admission_checklist | 1 |
| patient_safety_checklist | 1 |
| correct_patient_checklist | 1 |
| infusion_pump_checklist | 1 |
| internal_correspondence | 1 |
| external_correspondence | 1 |

**Specialty distribution**: General Medicine (11), Cardiology (10), Gastroenterology (7), Psychiatry (6), Neurology (4), Respiratory (4), General Surgery (3), Renal (2), Endocrinology (2), Physiotherapy (1).

The full 5,000-doc library covers **45 document types** with stratified balance across all of them.

## Scan-quality variants
Real hospital PDFs aren't pristine digital files. They're faxed, scanned at low DPI, photocopied, and sent through multiple layers of email compression. Models trained only on clean digital PDFs collapse on first contact with reality.

In this sample, each document ships with **one scanned variant** drawn from four quality tiers:

| Quality tier | Count in sample | Description |
| --- | --- | --- |
| `scanned` | 27 | 300 DPI scan with mild noise / skew |
| `clean` | 16 | Digital-native PDF |
| `poor` | 6 | 150 DPI, heavier noise, slight rotation |
| `fax` | 1 | Binarised, dropouts, lowest fidelity |

In the **full 5,000-doc library** every document is rendered in clean and lower quality scanned format, so you can train across the realistic scan-quality spectrum.

## File layout
```
├── pdfs/                       # Clean reportlab PDFs (one per doc)
├── pdfs_scanned/               # Scanned variants (rotated, noisy, JPEG'd)
├── ground_truth.csv            # Per-doc structured labels
├── ground_truth.jsonl          # Same in JSONL
├── bboxes.jsonl                # Per-doc bbox layout annotations
├── splits.json                 # Train / test partitions
├── manifest.json               # library summary statistics
├── preview.png                 # Sample document thumbnail
└── README.md
```

## Quick start
```python
import json

# Load ground truth
with open("ground_truth.jsonl") as f:
    rows = [json.loads(line) for line in f]

# Load splits
with open("splits.json") as f:
    splits = json.load(f)

# Get train rows
train_filenames = set(splits["train"]["filenames"])
train_rows = [r for r in rows if r["pdf_filename"] in train_filenames]

# Index bboxes by doc
with open("bboxes.jsonl") as f:
    bboxes_index = {
        json.loads(l)["pdf_filename"]: json.loads(l)["bboxes"]
        for l in f
    }

print(f"{len(rows)} docs across {len(set(r['document_type'] for r in rows))} types")
```

## Ground-truth schema
Each row in `ground_truth.csv` / `ground_truth.jsonl` includes:

- **Patient identifiers** - `patient_name`, `patient_dob`, `patient_age`, `patient_sex`, `patient_address`, `mrn`, `medicare`, `nok_name`
- **Document metadata** - `document_type`, `document_id`, `pdf_filename`, `case_id`, `specialty`
- **Clinical** - `principal_diagnosis`, `principal_icd`, `additional_diagnoses`, `medications`, `new_medications`
- **Cross-references** - `hospital_name`, `hospital_lhd`, `ward`, `gp_name`, `gp_clinic`, clinician names with provider numbers
- **Doc-type-specific fields** - `triage_category`, `accession_no`, `lab_ref`, `procedure`, `anaesthetic_type`, `moca_total`, `hads_anxiety`, `hads_depression`, `lvef_percent`, etc.
- **Bounding boxes** - `bboxes_json` column + per-doc records in `bboxes.jsonl`

## Bounding-box layout annotations
Every labelled field has its location on the page recorded as `(x, y, width, height, page)` in PDF points.

- **682 total field bboxes** in this sample (13.6 average per doc)
- Available in `ground_truth.csv` (`bboxes_json` column) and `bboxes.jsonl`
- Compatible with LayoutLMv3, Donut, DocFormer, and DocVQA training pipelines

Because the library is generated programmatically, every field's exact pixel position is known. Labels are ground truth, not noisy OCR approximations.

## Why this library vs alternatives
|  | This library | Generic synthetic medical text | Real medical PDFs |
| --- | --- | --- | --- |
| Visual fidelity | High (NSW Health style) | Plain text only | High but legally restricted |
| PHI / privacy risk | **Zero** | Zero | High (Privacy Act / HIPAA) |
| Doc type coverage | 45 (full) / 29 (sample) | 1-3 typical | Whatever partner has |
| Pre-labelled ground truth | Manual labelling required |
| BBox layout annotations | Manual annotation required |
| Scanned variants | 4 tiers (full) | N/A | Already scanned |
| Time to first model | Today | Days | Months |
| Cost | $0 sample / $2K–$25K full | Free / low | $50K+ overhead |

## Tasks supported
- Document classification (45 classes in full library)
- Named-entity recognition (140+ entity types across full library)
- Structured extraction (PDF - schema)
- Layout-aware extraction (LayoutLMv3, Donut, DocFormer)
- OCR robustness (scan-quality variants)
- Document Q&A (DocVQA-style)
- Document summarisation
- De-identification benchmarking (every PHI-shaped field is known)
- Continued pretraining for AU-clinical language models

## Reproducibility
Generated from a deterministic Python pipeline. Same seed - identical library, byte-for-byte. The full library and generator licence include source code and seeds.

## Ethics & compliance
- No real patient data was used at any point in generation
- Names, MRNs, Medicare numbers, addresses, dates, and clinical findings are entirely synthetic
- Every document carries a footer disclaimer: *"SYNTHETIC TRAINING DOCUMENT - NOT FOR CLINICAL USE"*
- Released under CC-BY-NC 4.0 for non-commercial use

> ⚠️ **Important**: This dataset is not a substitute for real-world clinical data. Models trained on this library alone should be validated on actual hospital data before clinical deployment. Any apparent resemblance to real individuals or events is purely coincidental.> 

## Full library & commercial licensing
This is a **50-document sample**. The full library available for commercial licensing includes:

- **5,000 documents** across all 45 doc types
- **Four scan-quality tiers** for every document (20,000 PDFs total)
- **Bounding-box annotations** for every labelled field (~14 per doc)
- **Stratified 70 / 15 / 15 train / val / test splits**
- **12 months of email support**

| Tier | Documents | Price (USD) |
| --- | --- | --- |
| Sample | 50 | This listing - free |
| Standard | 500 | $2,000 - $5,000 |
| Large | 5,000 | $10,000 - $25,000 |
| Mega | 50,000+ | Quote on request |
| Custom commission | To spec | $5,000 - $30,000 |
| Generator licence (run yourself) | - | $25,000 - $50,000 |

**Discounts**: 3+ standard licences to same buyer = 10% off · Annual subscription, refreshed quarterly = 20% off · Academic researchers (proof of affiliation) = 50% off.

For commercial licensing, custom case mixes, specific document type subsets, or hospital-specific branding, email [**jack.webb@rootcauseanalytics.com.au**](mailto:jack.webb@rootcauseanalytics.com.au). Response within 24 hours during AU business hours.

## Citation
```
@dataset{webb_2026_synthetic_au_medical_sample,
  title    = {Synthetic Australian Medical Documents - Sample},
  author   = {Webb, Jack},
  year     = {2026},
  publisher = {Hugging Face},
  version  = {0.1.0},
  url      = {https://huggingface.co/datasets/RootCauseAnalytics/synthetic-australian-medical-documents-sample}
}
```

## Versions
- **v0.1.0** - Initial release: 50 documents, 29 doc types, 682 bbox annotations, scanned variants

## Maintainer
**Jack Webb**, Root Cause Analytics - Sydney, Australia · [jack.webb@rootcauseanalytics.com.au](mailto:jack.webb@rootcauseanalytics.com.au)