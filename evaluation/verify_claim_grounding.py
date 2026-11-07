"""Development regressions from reported chats, not the reserved thesis test set.

Calls configured free providers. Saves exact evidence, review decisions and timings.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ai-services/llm_service'))
import llm_client as service
import guideline_trace
import claim_validation


def source_for(path, page):
    with fitz.open(path) as document:
        text = document[page - 1].get_text()
    source = service.guideline_grounding.verified_source({'source': path.stem, 'text': text})
    source.update(citation_id='G1', _evidence=[text])
    return source, claim_validation.normalize(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--reviews-only', action='store_true')
    parser.add_argument('--answers-only', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    failed = False
    if not args.answers_only:
        old = next((ROOT / 'ai-services/guidelines').glob('Old*Renal*'))
        scope, scope_text = source_for(old, 18)
        treatment, text = source_for(ROOT / 'ai-services/guidelines/JCH-23-1637.pdf', 7)
        treatment_quote = text[text.index('13.1 '):text.index('13.2 ')].strip()
        combination_quote = text[text.index('13.2 '):text.index('Clinical question 14')].strip()
        scope_quote = re.search(r'Chronic kidney disease has a global.*?mortality\.\[11\]', scope_text).group()
        main_guideline = next((ROOT / 'ai-services/guidelines').glob('*Management of Hypertension in the Philippines.pdf'))
        options, options_text = source_for(main_guideline, 26)
        cases = [
            ('wrong_document_quote', scope, 'An ACE inhibitor is recommended.', treatment_quote, False),
            ('unrelated_real_quote', scope, 'An ACE inhibitor or ARB is first-line therapy for CKD with albuminuria.', scope_quote, False),
            ('lost_albuminuria_condition', treatment, 'An ACE inhibitor or ARB is the first-line drug of choice for everyone with chronic renal failure.', treatment_quote, False),
            ('reversed_threshold', treatment, 'An ACE inhibitor or ARB is first-line for CKD patients with urinary albumin-to-creatinine ratio below 30 mg/g.', treatment_quote, False),
            ('reversed_contraindication', treatment, 'An ACE inhibitor and an ARB should be combined for hypertension in CKD.', combination_quote, False),
            ('inflated_recommendation_strength', options, 'Beta blockers are preferred initial therapy for all hypertensive patients with coronary artery disease, acute coronary syndrome, high sympathetic drive, or pregnancy.', options_text, False),
            ('supported_conditional_answer', treatment, 'If CKD is accompanied by urinary albumin-to-creatinine ratio ≥30 mg/g, an ACE inhibitor or ARB at maximally tolerated dose is recommended first-line. This recommendation is conditional on albuminuria, which the question has not established.', treatment_quote, True),
        ]
        for name, source, text, quote, expected in cases:
            draft = json.dumps({'paragraphs': [{'text': text, 'evidence': [{'source_id': 'G1', 'quote': quote}]}]})
            started = time.perf_counter()
            claims, reason = claim_validation.prepare_review(draft, [source])
            with guideline_trace.capture() as trace:
                accepted = False
                if claims:
                    accepted, reason = service.review_guideline_claims('What is the drug of choice for hypertension in chronic renal failure?', claims)
            record = {'name': name, 'accepted': accepted, 'expected': expected, 'reason': reason,
                      'elapsed_seconds': round(time.perf_counter() - started, 2), 'trace': trace}
            (output / (name + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({key: value for key, value in record.items() if key != 'trace'}, ensure_ascii=True), flush=True)
            failed |= accepted != expected
    if not args.reviews_only:
        questions = [
            ('renal_failure', 'What is the drug of choice to treat hypertension in someone with chronic renal failure?'),
            ('comorbid_conditions', 'What antihypertensives should be used according to what comorbid conditions are present?'),
            ('breastfeeding', 'What antihypertensives are safe while breast feeding?'),
            ('home_office_bp', 'What is the best way to decide whether to go by home blood pressures that are normal versus office blood pressures that are high?'),
        ]
        for name, question in questions:
            request = service.ChatRequest(message=question, history=[service.HistoryEntry(
                role='doctor', content='How should blood pressure be measured?')])
            started = time.perf_counter()
            with guideline_trace.capture() as trace:
                prompt, sources = service.prepare_general_chat(request)
                retrieved = time.perf_counter()
                answer = service.generate_general_answer(request, prompt, sources)
            public = service.public_guideline_sources(sources)
            accepted = bool(public)
            record = {'question': question, 'accepted': accepted, 'answer': answer, 'sources': public,
                      'retrieval_seconds': round(retrieved - started, 2),
                      'total_seconds': round(time.perf_counter() - started, 2), 'trace': trace}
            (output / (name + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({key: value for key, value in record.items() if key not in ('trace', 'sources')}, ensure_ascii=True), flush=True)
            print('CITED', [(source['pdf_file'], source['pages']) for source in public], flush=True)
            failed |= not accepted
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
