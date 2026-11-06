import unittest
from unittest.mock import Mock, patch
import requests
from fastapi import HTTPException
import openrouter_client as adapter
import llm_client as service
import guideline_trace


class OpenRouterTests(unittest.TestCase):
    def response(self, status=200, body=None):
        result = Mock(status_code=status)
        result.json.return_value = body if body is not None else {"choices": [{"finish_reason": "stop", "message": {"content": " Answer "}}]}
        return result

    def test_payload_and_complete_answer(self):
        with patch.object(adapter.requests, 'post', return_value=self.response()) as post:
            self.assertEqual(adapter.generate('evidence', 'secret', 'model:free', True), 'Answer')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['messages'][-1]['content'], 'evidence')
        self.assertEqual(payload['model'], 'model:free')
        self.assertNotIn('models', payload)

    def test_operational_failures(self):
        for status in (402, 408, 429, 500, 502, 503, 504):
            with self.subTest(status=status), patch.object(adapter.requests, 'post', return_value=self.response(status)):
                with self.assertRaises(adapter.OpenRouterUnavailable):
                    adapter.generate('prompt', 'secret', 'model:free')
        with patch.object(adapter.requests, 'post', side_effect=requests.Timeout):
            with self.assertRaises(adapter.OpenRouterUnavailable):
                adapter.generate('prompt', 'secret', 'model:free')

    def test_invalid_and_truncated_output(self):
        for body in ({'choices': []}, {'choices': [{'finish_reason': 'length', 'message': {'content': 'partial'}}]}, {'choices': [{'finish_reason': 'stop', 'message': {'content': ''}}]}):
            with patch.object(adapter.requests, 'post', return_value=self.response(body=body)):
                with self.assertRaises(adapter.OpenRouterUnavailable):
                    adapter.generate('prompt', 'secret', 'model:free')

    def test_access_errors_and_refusals_are_not_outages(self):
        for response in (self.response(401), self.response(403), self.response(400), self.response(body={'choices': [{'finish_reason': 'content_filter', 'message': {}}]})):
            with patch.object(adapter.requests, 'post', return_value=response):
                with self.assertRaises(HTTPException):
                    adapter.generate('prompt', 'secret', 'model:free')
        with patch.object(adapter.requests, 'post') as post:
            with self.assertRaises(HTTPException):
                adapter.generate('prompt', 'secret', 'paid-model')
            post.assert_not_called()

    def test_fallback_and_trace(self):
        with patch.object(service, 'LLM_PROVIDER', 'openrouter'), \
             patch.object(adapter, 'generate', side_effect=adapter.OpenRouterUnavailable('quota')), \
             patch.object(service, 'call_groq', return_value='fallback') as groq, guideline_trace.capture() as trace:
            self.assertEqual(service.call_llm('same prompt'), 'fallback')
            groq.assert_called_once_with('same prompt')
            self.assertEqual([c['provider'] for c in trace['generation_calls']], ['openrouter', 'groq'])

    def test_primary_success_and_rejection_do_not_call_groq(self):
        with patch.object(service, 'LLM_PROVIDER', 'openrouter'), patch.object(service, 'call_groq') as groq:
            with patch.object(adapter, 'generate', return_value='primary'):
                self.assertEqual(service.call_llm('prompt'), 'primary')
            with patch.object(adapter, 'generate', side_effect=HTTPException(502, 'denied')):
                with self.assertRaises(HTTPException):
                    service.call_llm('prompt')
            groq.assert_not_called()

    def test_both_providers_fail_safely(self):
        with patch.object(service, 'LLM_PROVIDER', 'openrouter'), \
             patch.object(adapter, 'generate', side_effect=adapter.OpenRouterUnavailable('quota')), \
             patch.object(service, 'call_groq', side_effect=HTTPException(503, 'private provider detail')):
            with self.assertRaises(HTTPException) as caught:
                service.call_llm('prompt')
            self.assertEqual(caught.exception.status_code, 503)
            self.assertNotIn('private', caught.exception.detail)


if __name__ == '__main__':
    unittest.main()
