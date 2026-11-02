"""Prepare AI-drafted development references for researcher review, never final cases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.clara/evaluation/pilot'


def prepare():
    corpus = json.loads((OUT.parent / 'corpus.json').read_text(encoding='utf-8'))
    doc = next(d for d in corpus['documents'] if 'Management of Hypertension in' in d['pdf_file'])
    pages = {p['page']: p['text'] for p in json.loads(Path(doc['extraction']).read_text(encoding='utf-8'))}
    specs = [
        ('How does the 2020 Philippine hypertension guideline recommend confirming hypertension outside the office?',
         'Out-of-office measurements are recommended to confirm hypertension. ABPM is preferred; HBPM is an acceptable alternative.', [16]),
        ('According to the 2020 Philippine hypertension guideline, what device is recommended for blood-pressure measurement, and under what conditions can a manual aneroid device be used?',
         'A properly validated semi-automated oscillometric device is recommended in or out of the office. A manual aneroid device may be used if the examiner is efficient and well trained and the device is periodically checked according to standard maintenance procedures.', [17, 18]),
        ('According to the 2020 Philippine hypertension guideline, how should the patient prepare for blood-pressure measurement, and how many readings and occasions should be averaged?',
         'The patient should rest for more than five minutes, seated with feet flat and back supported; avoid coffee, smoking, and exercise for 30 minutes; empty the bladder; and avoid talking. Average at least two readings on at least two occasions; readings should be 1–2 minutes apart.', [18, 19]),
        ('According to Table 2 of the 2020 Philippine hypertension guideline, how do ABPM and HBPM differ in measurement timing, patient activity, triggering measurements, and awareness of readings?',
         'ABPM measures over 24 hours during waking and sleeping, regular activities and sleep; the device triggers measurements automatically and the patient is unaware of readings. HBPM measures daily for several days during waking hours at seated rest; the patient triggers measurements and is usually aware of the readings.', [19]),
        ('For which special situations does the 2020 Philippine hypertension guideline recommend an aneroid sphygmomanometer, and what limitation of automated devices is described for atrial fibrillation?',
         'The aneroid device is recommended for arrhythmias or extreme BP levels. The text says an automated device may not be used in atrial fibrillation because of inconsistency in the oscillometric waveform.', [18]),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    questions = []
    for i, (question, reference, page_numbers) in enumerate(specs, 1):
        questions.append({'id': f'htn-dev-{i:03}', 'question': question,
                          'reference': reference, 'source_type': 'guideline', 'split': 'development',
                          'answerable': True, 'reference_source_checked': False,
                          'reference_author': 'AI draft; awaiting researcher source review',
                          'reference_evidence': [{'document_id': doc['document_id'], 'pdf_file': doc['pdf_file'],
                                                  'page': n, 'text': pages[n]} for n in page_numbers]})
    for filename, rows in [('draft_questions.jsonl', questions),
                           ('generation_questions.jsonl', [{'id': q['id'], 'question': q['question']} for q in questions])]:
        target = OUT / filename
        if target.exists():
            raise FileExistsError(f'Refusing to overwrite researcher edits: {target}')
        target.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in rows), encoding='utf-8')
    print('Prepared 5 development questions. References are AI drafts, not researcher-approved.')


if __name__ == '__main__':
    prepare()
