import json
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import llm_client as service


class MimicChatTests(unittest.TestCase):
    def test_scoped_evidence_stream_and_no_legacy_rules(self):
        source = {'type': 'patient_pdf', 'source': 'Admission_87654321/Chemistry/test.pdf', 'page': 1}
        response = Mock()
        response.json.return_value = {'context': 'Hemoglobin 8.6 g/dL; admission 87654321', 'sources': [source]}
        with patch.object(service.requests, 'get', return_value=response) as get, \
             patch.object(service, 'is_management_query', return_value=False), \
             patch.object(service, 'classify_question', return_value='other'), \
             patch.object(service, 'call_llm', return_value='Hemoglobin is 8.6 g/dL.') as model, \
             patch.object(service.rule_engine, 'evaluate_labs') as rules:
            result = TestClient(service.app).post('/chat/stream', json={
                'patient_id': 'Patient_12345678', 'admission_id': '87654321',
                'active_section': 'hematology', 'message': 'Summarize hemoglobin',
                'history': [{'role': 'doctor', 'content': 'Earlier question'}]})
        self.assertEqual(get.call_args.kwargs['params']['admission'], '87654321')
        self.assertEqual(get.call_args.kwargs['params']['category'], 'hematology')
        self.assertIn('8.6 g/dL', model.call_args.args[0])
        self.assertIn('Earlier question', model.call_args.args[0])
        rules.assert_not_called()
        events = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1]['type'], 'done')
        self.assertIn(source, next(x['sources'] for x in events if x['type'] == 'sources'))

    def test_missing_scope_and_unsupported_alerts(self):
        with patch.object(service.requests, 'get') as get:
            client = TestClient(service.app)
            result = client.post('/chat', json={'patient_id': 'Patient_12345678', 'message': 'Review'})
            self.assertEqual(result.status_code, 422)
            get.assert_not_called()
            self.assertEqual(client.post('/clinical-alerts', json={'patient_id': 'Patient_12345678'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
