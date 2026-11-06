import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import llm_client as service


class GeneralChatTests(unittest.TestCase):
    def test_missing_patient_forms_use_rag_and_return_sources(self):
        for patient in ({}, {'patient_id': None}, {'patient_id': ''}, {'patient_id': ' '}):
            for endpoint in ('/chat', '/chat/stream'):
                with self.subTest(patient=patient, endpoint=endpoint):
                    sources = [{'type': 'guideline', 'source': 'guide', 'page': 2,
                                'citation_id': 'G1', '_evidence': ['Evidence']}]
                    with patch.object(service, 'build_guideline_bundle', return_value=('Evidence', sources)) as retrieve, \
                         patch.object(service, 'call_llm', return_value='Draft') as model, \
                         patch.object(service, 'finalize_guideline_answer', return_value='Cited answer') as validate, \
                         patch.object(service.requests, 'get') as patient_fetch, \
                         patch.object(service, 'execute_tool') as tool, \
                         patch.object(service, 'run_ml_assessment') as ml, \
                         patch.object(service.rule_engine, 'evaluate_labs') as rules:
                        result = TestClient(service.app).post(endpoint, json={**patient, 'message': 'Explain hypertension'})
                    self.assertEqual(result.status_code, 200)
                    retrieve.assert_called_once_with('Explain hypertension')
                    self.assertIn('No patient is selected', model.call_args.args[0])
                    validate.assert_called_once()
                    for mock in (patient_fetch, tool, ml, rules):
                        mock.assert_not_called()
                    if endpoint.endswith('stream'):
                        events = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith('data: ')]
                        kinds = [event['type'] for event in events]
                        self.assertLess(kinds.index('sources'), kinds.index('token'))
                        self.assertEqual(kinds[-1], 'done')
                        data = next(event for event in events if event['type'] == 'meta')
                    else:
                        data = result.json()
                    self.assertEqual(data['sources'][0]['page'], 2)
                    self.assertNotIn('_evidence', data['sources'][0])

    def test_no_evidence_does_not_generate_unsupported_answer(self):
        with patch.object(service, 'build_guideline_bundle', return_value=('No evidence', [])), \
             patch.object(service, 'call_llm') as model:
            response = TestClient(service.app).post('/chat', json={'message': 'Unknown topic'})
        model.assert_not_called()
        self.assertEqual(response.json()['response'], service.guideline_grounding.NO_EVIDENCE)
        self.assertEqual(response.json()['sources'], [])

    def test_followup_uses_explicit_history_not_patient_session_cache(self):
        service.conversation_store['general-isolation-test'] = [{'role': 'doctor', 'content': 'Private patient record'}]
        try:
            with patch.object(service, 'build_guideline_bundle', return_value=('', [])) as retrieve:
                prompt, _ = service.prepare_general_chat(service.ChatRequest(
                    session_id='general-isolation-test', message='What about treatment?',
                    history=[service.HistoryEntry(role='doctor', content='Explain hypertension')]))
            self.assertIn('hypertension', retrieve.call_args.args[0])
            self.assertIn('What about treatment?', retrieve.call_args.args[0])
            self.assertNotIn('Private patient record', prompt)
        finally:
            service.conversation_store.pop('general-isolation-test', None)


if __name__ == '__main__':
    unittest.main()
