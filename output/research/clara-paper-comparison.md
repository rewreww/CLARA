# CLARA compared with the IJERT medical report analyzer

Review date: 6 September 2026. Paper: Abhinav Pal, Kartik Garg, Harsh and Shivam Sharma, *Automated Analysis of Medical and MRI Reports Using Large Language Models*, IJERT 15(04), April 2026, IJERTV15IS043028, 10 pages.

CLARA's highest priorities are to correct input handling, remove label leakage, train for the features available in its actual workflow, and evaluate each task separately. The paper provides a useful description of a report-processing workflow, but it does not establish that its system is more accurate than CLARA. Its F1 of 0.875 evaluates clinical entity extraction; CLARA's saved F1 values evaluate tabular classifications and future outcomes.

The existing CSV is relevant to heart-failure prognosis. MIMIC-III could support report extraction and summarization research, and a separately designed prognosis dataset. It is not a replacement CSV that can be dropped into the current training script.

## Evidence and scope

I read all ten PDF pages, inspected their rendered figures and results table, inspected CLARA's current source, profiled the complete training CSV, and reconstructed the test split to run the saved model. All eight saved confusion matrices reproduced exactly. No model was retrained, no thresholds were selected, and no application source or original dataset was changed. A second run masked features unavailable through the chat builder; that was an artificial missing-input stress test, not a measurement on hospital patients.

The working tree already contained changes in the LLM service, RAG database, backend patient controller and frontend. Findings refer to that current working tree. The reviewed CSV has SHA-256 `1cd77f7b8932fb248cb7390cf0c01bbb42863cd67fd11a93ef211315d6d9242c`.

## What the paper actually evaluates

Pages 5-8 describe ingestion, text preprocessing, LLM extraction and summarization, output validation, structured JSON/CSV output, and clinician-facing display. The implementation section describes Python, Streamlit, Flask, and a Gemini/GPT-style API, without specifying one reproducible model snapshot and configuration. CSV is described as an output format; the paper does not identify a ready-made feature/label training CSV comparable to CLARA's.

Page 8 reports entity precision 0.89, recall 0.86 and F1 0.875 using MIMIC-III and synthetic reports with clinician annotations. It also reports summary relevance 4.4/5 and a reduction from 12-15 minutes to 2-3 minutes per report, described as 80-85% time reduction. The reported precision and recall yield approximately 0.8747 F1, so their rounding is internally consistent. The timing ranges alone imply possible reductions of 75-86.7%; paired measurements would be needed to substantiate the stated narrower range.

Important reporting gaps limit reproducibility:

- No identifiable report cohort, note IDs, exact evaluated sample size, real/synthetic mixture, or patient split tied to the entity-extraction scores. Figure 1 on pages 2 and 4 contains study/death counts, but the text does not connect those counts to the entity-extraction evaluation.
- No annotation release, annotation guideline, entity matching rule, micro/macro averaging definition, per-entity breakdown, or inter-annotator agreement.
- No exact model version, prompts, inference settings, synthetic-generation procedure, uncertainty intervals or reproducible code link.
- No controlled ablation showing that the proposed validation or feedback steps caused the reported improvement.
- Despite the title and an MRI illustration, no separately specified MRI cohort, raw-image model, segmentation/classification evaluation or MRI-specific result is documented. Do not treat the study as evidence for interpreting MRI scans.
- Page 9 labels its results table as suggested and retains conversational drafting text. These are reporting-quality concerns; they do not, by themselves, establish that the results were fabricated.

Use the paper as related work and a source of design ideas. Do not use 87.5% as a directly comparable CLARA prognosis target or as a clinical deployment standard. [Publisher page](https://www.ijert.org/automated-analysis-of-medical-and-mri-reports-using-large-language-models-ijertv15is043028).

## How CLARA compares

CLARA already implements several elements described in the paper: PDF/laboratory parsing, structured patient records in PostgreSQL, an LLM interface, guideline retrieval, and a React clinician interface. Its guideline retrieval includes source filenames, pages, topic filters and prioritization of Philippine guidelines. Its separate XGBoost service adds tabular predictions beyond the paper's documented extraction and summary task. These are implemented capabilities, not proof of higher accuracy.

The most useful ideas to adopt from the paper are a consistent structured output schema, validation of extracted facts, standardized clinical terms, and clinician-reviewed reference annotations. CLARA needs benchmarks for these functions: its saved prognosis scores cannot establish how accurately it extracts lab results, preserves negation, retrieves supporting guideline passages or writes faithful summaries. The inspected repository includes parser examples and assertions, but I did not find a clinician-annotated extraction benchmark reporting precision/recall/F1.

## The datasets and CSV files

### CLARA's current CSV

The actual local file has 2,008 rows and 167 columns. Configuration selects 147 inputs and eight targets; 12 other columns are unused. One missing emergency-return label causes the current all-target filter to discard an otherwise usable row. The saved evaluation contains 1,606 training rows and 401 test rows. There are no exact duplicate full rows or duplicate encoded feature rows. All 2,008 inpatient numbers are unique, with no overlap across the reconstructed split; an admission identifier alone cannot establish that repeated people are absent.

Its row count, field names and outcomes strongly match the Zigong heart-failure dataset. The official release describes a single Chinese hospital, admissions in 2016-2019, and 2,008 heart-failure patients. This is a provenance inference: I did not obtain an authenticated original file or verify a byte-for-byte match. The current official page lists 168 variables, while the original descriptor lists 166 attributes; those counts alone cannot identify the local version or transformations. Obtain the original file manifest and codebook before recording an exact version. [Official dataset](https://physionet.org/content/heart-failure-zigong/1.3/).

The descriptor identifies MI and CHF fields as admission comorbidities. In particular, CHF=0 can indicate no prior CHF history in someone diagnosed with heart failure for the first time at the index hospitalization. It does not mean that person is a healthy negative control. The CCI is derived from those comorbidities, and laboratory values are from admission day one. [Original data descriptor](https://www.nature.com/articles/s41597-021-00835-9).

Consequences for CLARA:

- This cohort can support outcome research among hospitalized HF patients. It cannot establish general-population heart-failure detection or diagnosis across all cardiovascular patients.
- Keep history/comorbidity classification distinct from future mortality and readmission. The MI label does not establish incident future MI prediction.
- `type.of.heart.failure` is encoded as Left/Right/Both, not HFrEF/HFpEF.
- A Chinese single-center cohort requires separate evaluation in CLARA's intended Philippine setting.
- `dischargeDay`, discharge destination, in-hospital outcome and event times are currently excluded from inputs. Preserve that protection and audit every proposed new feature against the prediction time.

### Can we get the paper's dataset?

**The underlying MIMIC-III database: yes, subject to approved access. The authors' exact experiment dataset: not currently verified as obtainable.**

Reference 2 identifies MIMIC-III v1.4. PhysioNet currently requires a credentialed account, the specified CITI training, and acceptance of the dataset's data-use agreement. A student can apply using their institutional affiliation and supervisor reference. I did not sign agreements or download restricted records. [MIMIC-III v1.4](https://physionet.org/content/mimiciii/1.4/), [official access instructions](https://mimic.mit.edu/docs/faq/how-to-get-access.html).

MIMIC-III is a collection of relational CSV tables. For report work, begin with `NOTEEVENTS.csv` or its compressed distribution. Its documented columns include `ROW_ID`, `SUBJECT_ID`, `HADM_ID`, `CHARTDATE`, `CHARTTIME`, `CATEGORY`, `DESCRIPTION`, `ISERROR` and `TEXT`. It contains discharge summaries and several report types. The `TEXT` column is source text, not the paper's clinician-created entity labels. [NOTEEVENTS documentation](https://mimic.mit.edu/docs/iii/tables/noteevents.html).

Depending on the task, `PATIENTS`, `ADMISSIONS`, `LABEVENTS`, `D_LABITEMS`, `DIAGNOSES_ICD` and `PRESCRIPTIONS` provide related patient, encounter, laboratory, diagnosis and medication information. Build explicit joins and task-specific labels; do not feed the raw notes table to the existing 147-column classifier. Absence of a recorded readmission at the source hospital is not proof of no readmission elsewhere.

I found no linked release of the selected report cohort, synthetic reports, clinician entity annotations, model prompts or split manifest in the attached paper, publisher page or targeted title/paper-ID searches. Request these materials from the authors. Cohort identifiers and annotations derived from restricted notes may themselves require controlled sharing. The paper's CC BY license does not grant access to MIMIC records.

A concrete author request should ask for the MIMIC version and cohort-selection code, permitted note-ID manifest, report counts and types, synthetic generation scripts/seeds, annotation schema and adjudication process, patient-disjoint splits, exact model/prompt settings and scoring code. No message has been sent to the authors.

For CLARA's free/local constraint, run restricted-data processing locally in an authorized environment. Do not assume the default Groq demo route is permitted for MIMIC. PhysioNet explicitly restricts sharing credentialed data through ordinary third-party services and lists particular acceptable cloud arrangements with conditions. [PhysioNet guidance](https://physionet.org/news/2023/#responsible-use-of-mimic-data-with-online-services-like-gpt).

### Dataset design to use in CLARA

Maintain three separate resources. These are proposed schemas, not existing datasets:

1. **Outcome modeling:** one row per eligible encounter at a specified prediction time, with permitted patient/encounter keys, predictor timestamps, units, source, follow-up completeness, and independently defined outcome labels. Keep labels separate from model inputs. Split by patient, and use a later-time/hospital test set when possible.
2. **Report extraction:** source document ID, patient split, page/section, source text, annotated entity spans, normalized lab/test or diagnosis, value, comparator, unit, negation, historical/current status, experiencer and adjudication status. JSONL is convenient for nested annotations; CSV is also possible with one annotation per row.
3. **Guideline retrieval and answers:** clinical question, reference passages/pages, required patient facts, expected grounded conclusions, and clinician review. Clinical guidelines belong in retrieval, not automatically in an outcome-model training CSV.

Synthetic reports can exercise unusual formats and edge cases in development. Keep their results separate from the primary real-report test results, and do not regard generated patients as new observed mortality outcomes.

## Verified CLARA baseline

All figures below use the current model and reconstructed 401-row test set. Precision, recall and F1 are for class 1; HF type instead uses macro-F1 over its three classes. They are internal retrospective estimates, not external clinical validation.

- **28-day mortality:** accuracy 98.25%, precision 0%, recall 0%, F1 0.000, ROC-AUC 0.769. Detected 0 of 6 positive cases. Always predicting no death would achieve 98.50% accuracy.
- **28-day readmission:** accuracy 90.77%, precision 0%, recall 0%, F1 0.000, ROC-AUC 0.631. Detected 0 of 36 positive cases. Always predicting no readmission would achieve 91.02% accuracy.
- **6-month mortality:** accuracy 97.51%, precision 100%, recall 9.09%, F1 0.167, ROC-AUC 0.747. That 100% precision represents one true positive and zero false positives; the model missed ten of eleven deaths.
- **6-month readmission:** accuracy 62.84%, precision 54.55%, recall 34.18%, F1 0.420, ROC-AUC 0.627.
- **6-month ED return:** accuracy 61.10%, precision 50%, recall 36.54%, F1 0.422, ROC-AUC 0.615.
- **MI comorbidity:** accuracy 93.77%, precision 83.33%, recall 17.24%, F1 0.286, ROC-AUC 0.884. Interpret only after correcting label leakage and label meaning.
- **CHF history/comorbidity:** accuracy 98.00%, precision 97.91%, recall 100%, F1 0.989, ROC-AUC 0.942. The cohort and leakage prevent treating this as evidence of general HF diagnosis.
- **HF type:** accuracy 70.32%, macro-F1 0.293, macro one-vs-rest ROC-AUC 0.624. Recall for the Right class is 0%; no Right predictions were made. Always choosing Both would achieve 70.57% accuracy.

I also computed average precision (AP, a specified summary of the precision-recall curve, not trapezoidal PR-AUC) from the saved model probabilities. AP is 0.354 for 28-day mortality, 0.155 for 28-day readmission, 0.272 for 6-month mortality, 0.538 for 6-month readmission and 0.511 for ED return. The corresponding test event prevalences are 0.015, 0.090, 0.027, 0.394 and 0.389. The mortality estimate is unstable with only six positives.

Brier scores for 28-day readmission, 6-month readmission and ED return are 0.0876, 0.2420 and 0.2483. Constant probabilities based on training prevalence score 0.0823, 0.2389 and 0.2377 respectively; lower is better. These models do not beat that probability baseline on this split. Brier measures overall probability quality, not calibration alone; inspect reliability curves too.

## Improvements in priority order

### 1. Correct label definitions and leakage

`CCI.score` is currently an input when predicting MI and CHF, although it is computed from a comorbidity list containing those labels. In the local CSV, the unweighted sum of the 16 comorbidity flags equals CCI in 2,003 of 2,008 rows. This provides additional local evidence of label-derived information. Remove CCI from these tasks, or use a documented target-independent construction that is actually available at inference. Reassess whether these should be prediction targets at all; usually known history should be extracted as history.

This correction may lower recorded scores. That is a more honest baseline. CCI may be a legitimate predictor for a later outcome when all of its ingredients are known before the prediction time; it is not prohibited for every target.

Source: [feature and target configuration](/C:/clara-system/ai-services/ml_service/column_config.json), and the original data descriptor linked above.

### 2. Make training and inference use the same feature definitions

Static inspection of `build_ml_features` identifies at most 33 of the model's 147 features: 18 labs, five vital measurements, age/sex, seven comorbidities and LVEF. At least 114 features cannot be supplied through this builder. Actual coverage can be lower; the public prediction endpoint can accept more features when called separately.

In a controlled stress test, masking those 114 fields in the same test rows reduced 28-day mortality ROC-AUC from 0.769 to 0.546 and AP from 0.354 to 0.026. Six-month readmission ROC-AUC fell from 0.627 to 0.544. Some fixed-threshold F1 values increased despite poorer ranking, demonstrating why multiple measures matter. The experiment preserves original CSV values for the remaining fields and does not simulate all parsing, unit or hospital-distribution differences. It is not a production-performance estimate.

Choose a feasible core feature set, train with that same set, and evaluate an extended model only if the additional inputs will actually be collected. Audit units, measurement time and code definitions for every input. The current builder ignores the supplied lab `unit`, passes raw age against midpoint-coded age categories, and uses final-discharge diagnoses for comorbidities while the original dataset uses admission information. A named prediction time must resolve that mismatch.

Validate an abstention rule for missing essential inputs and out-of-cohort cases. The current API reports missing fields but can still generate probabilities from an almost entirely imputed row. Feature count alone is insufficient: missing an essential measurement can matter more than missing several optional fields.

Source: [chat feature builder](/C:/clara-system/ai-services/llm_service/llm_client.py:1004).

### 3. Repair input encoding and clinical text interpretation

- The configuration recognizes `OxygenTherapy` but omits `AmbientAir`. All 110 ambient-air values become missing, then get imputed as 1. Add an explicit, codebook-verified mapping and preserve missing as unknown. Retrain after changing encodings.
- Respiratory support is 97.91% missing. Median imputation can assign a ventilation category to an unspecified entry. Determine whether blank means none, unknown or not recorded before coding it.
- Forty features exceed 50% missingness and nine exceed 80%; overall 19.54% of encoded feature cells are missing. Compare removal of sparse inputs and missingness indicators within training folds, rather than automatically keeping all variables.
- Isolated synthetic tests of the actual builder turned `No diabetes. No CKD.` into positive diabetes and CKD flags. Preserve negation, family history, uncertainty and historical status before creating ML inputs.
- `_number(0)` returns missing; `1.2e3` becomes 1.2; `<0.01` loses the comparator. Parse numeric value, inequality and units separately, preserving zero and scientific notation.

Sources: [categorical encoding](/C:/clara-system/ai-services/ml_service/column_config.json:226), [numeric parser and feature builder](/C:/clara-system/ai-services/llm_service/llm_client.py:1017).

### 4. Train and evaluate each outcome independently

The present `MultiOutputClassifier` fits separate estimators with one common base configuration; it does not learn a joint representation of the outcomes. Separate per-outcome pipelines would allow independent valid-label masks, weighting, model selection, calibration and thresholds. The current all-label mask discards one row from every outcome because only ED return is missing.

The full dataset has only 37 28-day deaths, 57 6-month deaths and 51 Right-type cases. Benchmark regularized logistic regression and a shallower, regularized XGBoost model before increasing model size. The current XGBoost configuration uses depth 6 and 300 trees with no target-specific imbalance weighting or early stopping. Evaluate weighting candidates using training-fold class counts. Any resampling must occur inside training folds; ordinary SMOTE over integer-coded nominal categories can create meaningless category values.

Use stratified cross-validation per endpoint, with grouping by person when identifiers allow it. Fit imputers, encoders, feature selection, resampling, calibration and threshold selection entirely inside the development process. Current imputation is already fitted inside the training pipeline, which is a correct element to preserve. Obtain patient-disjoint external or later-period data for the final confirmation, especially after using the current test set diagnostically.

Source: [training and evaluation](/C:/clara-system/ai-services/ml_service/train.py:179).

### 5. Select thresholds for the intended use and calibrate probabilities

The API uses 0.5 for Yes/No and 0.35/0.65 for low/moderate/high risk across endpoints. These cutoffs have no saved validation evidence. Select a separate operating threshold using out-of-fold development predictions. F1 is one option; for missed-event-sensitive use, clinicians should define an acceptable sensitivity, false-alert burden and utility tradeoff. Do not optimize on the final test set or on in-sample predictions.

Lowering a threshold may improve recall and F1 while reducing precision or accuracy. It does not improve ROC-AUC or the underlying ranking by itself. Compare uncalibrated and cross-validated sigmoid-calibrated probabilities; tiny rare-event samples may not support flexible calibration. Validate reliability with plots and Brier/log loss. [Threshold selection](https://scikit-learn.org/stable/modules/classification_threshold.html), [probability calibration](https://scikit-learn.org/stable/modules/calibration.html).

Persist per-target precision, recall, F1, specificity, balanced accuracy, AP, ROC-AUC, Brier score, confusion matrix, positive counts and uncertainty intervals alongside the model. Record averaging definitions, label meaning, split manifest, data hash, feature schema, software versions and threshold selection protocol. The current training code prints classification reports but only saves AUROC and confusion matrices.

The mean of MI/CHF probabilities and mortality/readmission probabilities is not a validated overall clinical risk. Likewise, the confidence of a predicted HF subtype is not the severity of disease. Present named endpoints and uncertainty/coverage separately. Source: [prediction response](/C:/clara-system/ai-services/ml_service/app.py:143).

### 6. Build the benchmark that can actually compare with this paper

As an initial feasibility study, prepare roughly 100-200 permitted, representative local reports, with the final size determined by entity counts and desired precision of estimates. Use independent clinician annotation and adjudication. Split by patient and document source/template, keep synthetic tests separate, and reserve an untouched test set.

Compare the same reports through the current parser, structured LLM extraction, and a hybrid pipeline. Score exact span/type extraction and normalized clinical-field correctness separately. A lab result is correct only when the test, value, comparator, unit and date/context match. Report micro-F1, macro-F1 and per-entity precision/recall, including negated and historical findings. Missing text from OCR or document layout belongs in an end-to-end evaluation too.

Evaluate summaries for supported facts, critical omissions, incorrect numerical values and clinician-rated usefulness. Evaluate retrieval with recall@k and whether cited pages support each claim. CLARA's RAG relevance percentage is derived from embedding distance; it is not a calibrated probability that an answer is correct. Use source excerpts and factual provenance as explanations. Measure processing plus clinician verification time using paired reports; a fluent summary or short processing time alone is insufficient evidence of a useful improvement.

Source: [guideline retriever](/C:/clara-system/ai-services/rag/retriever.py:125).

## A practical experiment sequence

1. Freeze the verified baseline, data hash and task definitions. Resolve whether CLARA predicts at admission or discharge and identify permitted input times.
2. Fix categorical/numeric/negation/unit handling and remove target-derived inputs. Validate on targeted synthetic cases and reviewed reports.
3. Compare core-feature versus extended-feature models, each trained with its own feature set. Make 6-month readmission a practical initial research endpoint because it has 773 positive records; retain mortality as a distinct, small-event task without strong performance claims.
4. Compare regularized logistic regression and regularized boosted trees, then add imbalance weighting. Use the same valid development folds for a fair comparison.
5. Select endpoint thresholds and calibration inside cross-validation. Evaluate once on a protected test cohort and report uncertainty, all metrics and alert burden.
6. Run the report-extraction and guideline-grounding benchmark separately. Evaluate the combined pipeline so extraction errors and missing inputs are reflected in downstream results.
7. Validate on a permitted Philippine cohort with actual follow-up before interpreting the scores as evidence for the intended local clinical workflow.

No defensible accuracy or F1 gain can be promised from these changes before those experiments. CLARA can improve on this paper most convincingly through correct labels, usable inputs, reproducible evaluation, clinician-reviewed extraction and local validation.
