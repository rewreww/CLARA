import { Divider, Grid, H1, H2, Link, Pill, Row, Stack, Stat, Table, Text, useCanvasState } from 'cursor/canvas';

const metrics = [
  ['28-day mortality', '98.25%', '0.00%', '0.00%', '0.000', '0.769', '0 / 6'],
  ['28-day readmission', '90.77%', '0.00%', '0.00%', '0.000', '0.631', '0 / 36'],
  ['6-month mortality', '97.51%', '100.00%', '9.09%', '0.167', '0.747', '1 / 11'],
  ['6-month readmission', '62.84%', '54.55%', '34.18%', '0.420', '0.627', '54 / 158'],
  ['6-month ED return', '61.10%', '50.00%', '36.54%', '0.422', '0.615', '57 / 156'],
  ['MI comorbidity*', '93.77%', '83.33%', '17.24%', '0.286', '0.884', '5 / 29'],
  ['CHF history*', '98.00%', '97.91%', '100.00%', '0.989', '0.942', '374 / 374'],
];

const comparison = [
  ['Main task', 'Extract entities and summarize reports', 'Parse reports, retrieve guidelines, answer questions and predict tabular outcomes'],
  ['Data used', 'MIMIC-III plus synthetic clinical reports', '2,008-row heart-failure CSV; patient records and guidelines serve separate roles'],
  ['Model evidence', 'Gemini/GPT-style API; exact evaluated snapshot unspecified', 'Saved XGBoost model verified against all eight confusion matrices'],
  ['F1 meaning', 'Entity extraction: reported 0.875', 'Outcome/classification F1; directly comparable extraction benchmark not found'],
  ['Structured data', 'JSON/CSV output described', 'PostgreSQL patient records, mapped model features'],
  ['Guideline grounding', 'Validation and terminology standardization described', 'Philippine guideline retrieval with source/page metadata'],
  ['MRI evidence', 'No separate MRI cohort or MRI-specific evaluation documented', 'Current ML CSV has no MRI images or image labels'],
];

const issues = [
  ['1', 'Label leakage and meaning', 'CCI includes the MI/CHF targets; CHF=0 can mean no prior CHF history in an HF patient.', 'Remove target-derived inputs; separate documented history from future outcomes.'],
  ['2', 'Training versus chat inputs', 'Chat builder supports at most 33 of 147 features. At least 114 cannot be populated through this path.', 'Train with a feasible core feature set and verify units and prediction-time alignment.'],
  ['3', 'Oxygen encoding', '110 AmbientAir entries become missing, then receive the oxygen-therapy median.', 'Add a codebook-verified category mapping and retrain.'],
  ['4', 'Clinical text parsing', 'Synthetic “No diabetes. No CKD.” becomes two positive flags; numeric zero becomes missing.', 'Preserve negation, uncertainty, history, zero, comparators and scientific notation.'],
  ['5', 'Sparse inputs and rare outcomes', '40 features exceed 50% missingness; only 37 28-day deaths in the entire CSV.', 'Compare compact, regularized models; retain uncertainty and event counts.'],
  ['6', 'Thresholds and probabilities', 'One 0.5 cutoff and common risk bands; some probability scores lose to a prevalence baseline.', 'Tune endpoint thresholds and calibration inside development folds.'],
];

export default function CLARAPaperComparison() {
  const [tab, setTab] = useCanvasState('clara-paper-comparison-section', 'comparison');
  const tabs = [ ['comparison', 'Paper and CLARA'], ['metrics', 'Verified metrics'], ['data', 'CSV and access'], ['priorities', 'Improvement plan'] ];
  return (
    <Stack gap={18} style={{ padding: 20 }}>
      <H1>CLARA: evidence and improvement priorities</H1>
      <Text>6 September 2026 · IJERTV15IS043028 · All 10 pages reviewed</Text>
      <Text weight="semibold">Correct inputs and labels before trying to raise model scores. The paper’s extraction F1 and CLARA’s prognosis F1 measure different tasks.</Text>
      <Grid columns="repeat(auto-fit, minmax(160px, 1fr))" gap={16}>
        <Stat value="2,008" label="Rows in CLARA’s training CSV" />
        <Stat value="33 / 147" label="Maximum features supported by chat builder" />
        <Stat value="0 / 6" label="28-day deaths detected in current test set" />
      </Grid>
      <Row gap={8} wrap>
        {tabs.map(([id,label]) => <Pill key={id} active={tab === id} onClick={() => setTab(id)}>{label}</Pill>)}
      </Row>
      <Divider />
      {tab === 'comparison' && <Stack gap={14}>
        <H2>Capabilities and evidence</H2>
        <Table framed={false} headers={['Dimension','Paper','CLARA']} rows={comparison} />
        <Text size="small" tone="secondary">Sources: uploaded paper pp. 5–10; CLARA training, prediction, parsing and guideline-retrieval code inspected on 6 September 2026. Implemented capabilities do not establish higher accuracy.</Text>
        <H2>How much confidence to place in the paper</H2>
        <Text>The paper reports precision 0.89, recall 0.86, entity F1 0.875 and summary relevance 4.4/5. It does not connect an identifiable report cohort, annotation protocol, patient split, exact model snapshot or uncertainty intervals to those results.</Text>
        <Text>Figure 1 contains study/death counts, but their relationship to the extraction test is unexplained. Treat the paper as related work; a matched extraction benchmark is needed for a performance comparison.</Text>
        <Link href="https://www.ijert.org/automated-analysis-of-medical-and-mri-reports-using-large-language-models-ijertv15is043028">Read the publisher’s paper page</Link>
      </Stack>}
      {tab === 'metrics' && <Stack gap={14}>
        <H2>Current model: 401-row internal test set</H2>
        <Table framed={false} headers={['Outcome','Accuracy','Precision','Recall','F1','ROC-AUC','Detected / actual positives']} rows={metrics} columnAlign={['left','right','right','right','right','right','right']} />
        <Text size="small" tone="secondary">Source: current model.pkl evaluated on the train.py split (80/20, seed 42, joint valid-label filter). All eight saved confusion matrices matched. Binary scores use class 1. Model and dataset were not changed.</Text>
        <Text>* MI and CHF are admission comorbidities, with CCI-derived label leakage in the current inputs. Their scores do not establish future MI prediction or general-population HF diagnosis.</Text>
        <Text>HF type: accuracy 70.32%, macro-F1 0.293, macro one-vs-rest ROC-AUC 0.624. There are no Right-class predictions. Always predicting Both would achieve 70.57% accuracy.</Text>
        <Text>Always predicting no 28-day death would achieve 98.50% accuracy—higher than the model’s 98.25%. The six positive cases are too few for a stable estimate.</Text>
        <H2>Missing-input stress test: ranking quality</H2>
        <Table framed={false} headers={['Endpoint','Full CSV ROC-AUC','114 unavailable fields masked','Full CSV AP','Masked AP']} rows={[
          ['28-day mortality','0.769','0.546','0.354','0.026'],
          ['6-month readmission','0.627','0.544','0.538','0.450'],
        ]} />
        <Text size="small" tone="secondary">Source: same frozen model/test rows, with fields absent from the chat builder set to missing. Remaining values retain original CSV encodings. AP is average precision. This controlled stress test is not a production-performance measurement; some fixed-threshold F1 values increase despite weaker ranking.</Text>
      </Stack>}
      {tab === 'data' && <Stack gap={14}>
        <H2>What CLARA’s CSV contains</H2>
        <Table framed={false} headers={['Property','Observed value']} rows={[
          ['Rows / columns','2,008 / 167'], ['Configured inputs / targets','147 / 8'], ['Rows in saved train / test','1,606 / 401'],
          ['Missing encoded input cells','19.54%'], ['Features >50% / >80% missing','40 / 9'], ['Full-row / feature-row duplicates','0 / 0'],
          ['28-day / 6-month death positives','37 / 57'], ['28-day / 6-month readmission positives','140 / 773'],
          ['Rows with any missing target','1; excluded from every target by current training code'],
        ]} />
        <Text size="small" tone="secondary">Source: complete local dataset.csv and column_config.json, audited 6 September 2026. Missingness is measured after current categorical encoding and numeric coercion.</Text>
        <Text>The schema and row count strongly match Zigong’s hospitalized heart-failure cohort. Exact source version is unverified: official variable counts differ from the local CSV. This is a single-hospital HF cohort, requiring separate validation in CLARA’s intended Philippine population.</Text>
        <Link href="https://physionet.org/content/heart-failure-zigong/1.3/">Zigong dataset and access conditions</Link>
        <H2>Can the paper’s data be obtained?</H2>
        <Text>MIMIC-III v1.4 is available after PhysioNet credentialing, required training and a data-use agreement. The exact author-selected reports, clinician annotations and synthetic dataset were not found as a released resource.</Text>
        <Text>NOTEEVENTS contains report text linked by patient/encounter IDs. Its rows are not ready-made prognosis examples and do not contain the paper’s entity annotations. Build separate extraction and outcome datasets with explicit labels and patient splits.</Text>
        <Row gap={16} wrap>
          <Link href="https://physionet.org/content/mimiciii/1.4/">MIMIC-III v1.4</Link>
          <Link href="https://mimic.mit.edu/docs/faq/how-to-get-access.html">Access instructions</Link>
          <Link href="https://mimic.mit.edu/docs/iii/tables/noteevents.html">NOTEEVENTS schema</Link>
        </Row>
        <Text>Keep restricted-data processing local under the project’s free/local constraint. Do not assume the ordinary Groq demo route meets MIMIC’s use conditions.</Text>
        <Link href="https://physionet.org/news/2023/#responsible-use-of-mimic-data-with-online-services-like-gpt">PhysioNet guidance on online services</Link>
      </Stack>}
      {tab === 'priorities' && <Stack gap={14}>
        <H2>Changes to evaluate first</H2>
        <Table framed={false} headers={['Order','Issue','Evidence','Action']} rows={issues} />
        <H2>Experiment sequence</H2>
        <Text>Freeze the baseline and prediction time. Repair encoding, units and assertion handling. Remove label-derived inputs. Compare a feasible core feature set using regularized logistic regression and boosted trees. Add target-specific weighting, thresholds and calibration inside development folds.</Text>
        <Text>Report positive-class precision/recall/F1, specificity, balanced accuracy, AP, ROC-AUC, probability quality and uncertainty. Retain patient-disjoint external or later-period data for final confirmation.</Text>
        <Text>Build a separate clinician-annotated report benchmark for the comparison with this paper. Measure entity extraction, lab value/unit/date correctness, critical omissions, source support, retrieval recall and clinician verification time. Score real and synthetic reports separately.</Text>
        <Text>Correcting leakage may lower a recorded score. A useful improvement must hold on valid unseen data and actual CLARA inputs; a gain in every metric cannot be promised.</Text>
        <Row gap={16} wrap>
          <Link href="https://scikit-learn.org/stable/modules/classification_threshold.html">Threshold selection</Link>
          <Link href="https://scikit-learn.org/stable/modules/calibration.html">Probability calibration</Link>
        </Row>
      </Stack>}
    </Stack>
  );
}
