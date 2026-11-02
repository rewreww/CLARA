import asyncio
import copy
import tempfile
import json
import os
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from pathlib import Path
from evaluate_guidelines import validate, score_rows, summarize, write_report, METRICS, build_metrics, main

Q = {'id': 'dev-001', 'question': 'What should a citation contain?', 'reference': 'Document ID and page.',
     'source_type': 'guideline', 'split': 'development', 'answerable': True, 'reference_source_checked': True,
     'reference_evidence': [{'document_id': 'toy', 'pdf_file': 'toy.pdf', 'page': 1, 'text': 'Use document ID and page.'}]}
C = dict(Q['reference_evidence'][0], source_type='guideline', rank=1)
O = {'id': Q['id'], 'response': 'Document ID and page.', 'contexts': [C], 'contexts_are_generation_input': True}

class Sample:
    def __init__(self, **kwargs): self.data = kwargs

class Metric:
    def __init__(self, value=0.75, error=False): self.value, self.error = value, error
    async def single_turn_ascore(self, sample, timeout):
        if self.error: raise RuntimeError('secret must not be logged')
        return self.value

class EvaluationTests(unittest.TestCase):
    def run_scores(self, output=O, question=Q, overrides=None):
        metrics = {k: Metric() for k in METRICS}
        metrics.update(overrides or {})
        return asyncio.run(score_rows([question], {} if output is None else {question['id']: output}, metrics, Sample, 1))

    def test_valid(self): validate([Q], [O])
    def test_duplicates(self):
        with self.assertRaises(ValueError): validate([Q, Q], [O])
    def test_context_rank_order(self):
        o = copy.deepcopy(O); o['contexts'][0]['rank'] = 2
        with self.assertRaises(ValueError): validate([Q], [o])
    def test_context_source(self):
        o = copy.deepcopy(O); o['contexts'][0]['source_type'] = 'patient'
        with self.assertRaises(ValueError): validate([Q], [o])
    def test_actual_input_confirmation(self):
        o = dict(O, contexts_are_generation_input=False)
        with self.assertRaises(ValueError): validate([Q], [o])
    def test_reference_must_be_checked(self):
        with self.assertRaises(ValueError): validate([dict(Q, reference_source_checked=False)], [O])
    def test_reference_free_development_excludes_recall(self):
        q = dict(Q, reference_source_checked=False)
        validate([q], [O], reference_free=True)
        rows = asyncio.run(score_rows([q], {q['id']: O}, {k: Metric() for k in METRICS}, Sample, 1, True))
        self.assertIsNone(rows[1]['score'])
        self.assertEqual(rows[1]['status'], 'excluded_pending_researcher_reference_review')
    def test_reference_free_final_is_forbidden(self):
        with self.assertRaises(ValueError):
            validate([dict(Q, split='final')], [O], reference_free=True)
    def test_resume_reuses_only_successful_scores(self):
        cached = [{'id': Q['id'], 'metric': 'faithfulness', 'status': 'scored', 'score': .25},
                  {'id': Q['id'], 'metric': 'answer_relevancy', 'status': 'error_RateLimitError', 'score': None}]
        rows = asyncio.run(score_rows([Q], {Q['id']: O}, {k: Metric() for k in METRICS}, Sample, 1, previous_rows=cached))
        self.assertEqual(rows[2]['score'], .25)
        self.assertEqual(rows[3]['score'], .75)
    def test_holdout_overlap(self):
        with self.assertRaises(ValueError): validate([Q], [O], [dict(Q, id='final-01', split='final')])
    def test_missing_outputs_are_not_zero(self):
        rows = self.run_scores(None)
        self.assertTrue(all(r['score'] is None and r['status'] == 'missing_output' for r in rows))
    def test_empty_context_study_convention(self):
        rows = self.run_scores(dict(O, contexts=[]))
        self.assertEqual([r['score'] for r in rows[:2]], [0., 0.])
        self.assertTrue(all(r['status'] == 'study_convention_zero' for r in rows[:2]))
    def test_missing_response_recall_still_assessable(self):
        rows = self.run_scores(dict(O, response=''))
        self.assertEqual([r['score'] for r in rows], [None, .75, None, None])
    def test_unanswerable_recall_excluded(self):
        rows = self.run_scores(question=dict(Q, answerable=False, reference=''))
        self.assertEqual(rows[1]['status'], 'excluded_unanswerable')
    def test_errors_not_zero_or_secret(self):
        rows = self.run_scores(overrides={'faithfulness': Metric(error=True)})
        self.assertEqual(rows[2]['status'], 'error_RuntimeError')
        self.assertIsNone(rows[2]['score'])
        self.assertNotIn('secret', str(rows))
    def test_nan_never_perfect(self):
        rows = self.run_scores(overrides={'faithfulness': Metric(float('nan'))})
        self.assertIsNone(summarize(rows)['faithfulness']['mean'])
        self.assertEqual(summarize(rows)['faithfulness']['scored_count'], 0)
    def test_complete_run_writes_auditable_outputs_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            q = dict(Q, demonstration_only=True)
            (root / 'q.jsonl').write_text(json.dumps(q) + '\n')
            (root / 'o.jsonl').write_text(json.dumps(O) + '\n')
            config = dict(clara_version='test', generator_model='test', retrieval_embedding_model='test',
                          chunk_size=100, chunk_overlap=10, top_k=3, prompt_sha256='test', api_key='dummy-private-credential-8871')
            (root / 'config.json').write_text(json.dumps(config))
            argv = ['evaluate_guidelines.py', 'score', '--questions', str(root / 'q.jsonl'),
                    '--outputs', str(root / 'o.jsonl'), '--config', str(root / 'config.json'),
                    '--results', str(root / 'results'), '--guidelines', str(root / 'guidelines'), '--allow-demo']
            with patch('sys.argv', argv), patch.dict('sys.modules', {'ragas': SimpleNamespace(SingleTurnSample=Sample)}), patch('evaluate_guidelines.build_metrics', return_value={k: Metric() for k in METRICS}), patch.dict(os.environ, {'EVAL_LLM_MODEL':'test', 'EVAL_EMBEDDING_MODEL':'test', 'EVAL_LLM_API_KEY':'dummy-private-credential-8871'}):
                with patch('evaluate_guidelines.importlib.metadata.version', return_value='mock-offline-test'):
                    main()
            run = next((root / 'results').iterdir())
            self.assertEqual(json.loads((run / 'summary.json').read_text())['context_recall']['mean'], .75)
            self.assertIn('completed_utc', json.loads((run / 'manifest.json').read_text()))
            self.assertNotIn('dummy-private-credential-8871', (run / 'manifest.json').read_text())
            self.assertTrue((run / 'review.html').is_file())

    def test_html_escapes_untrusted_text(self):
        q = dict(Q, question='<script>alert(1)</script>')
        with tempfile.TemporaryDirectory() as tmp:
            write_report(Path(tmp), [q], {Q['id']: O}, [], {})
            report = (Path(tmp) / 'review.html').read_text()
            self.assertNotIn('<script>', report)
            self.assertIn('&lt;script&gt;', report)

if __name__ == '__main__': unittest.main()
