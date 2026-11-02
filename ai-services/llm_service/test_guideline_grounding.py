import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import fitz
from fastapi.testclient import TestClient
import guideline_grounding as grounding
import llm_client as service


class GroundingTests(unittest.TestCase):
    def test_bp_question_reaches_guidelines_without_patient_labs(self):
        for question in ['What is the best way to decide whether to go by home blood pressures that are normal versus office blood pressures that are high?',
                         'Home BP is normal but office BP is high. What next?', 'How is ABPM used?']:
            self.assertEqual(service.classify_question(question), 'guideline')
        self.assertEqual(service.classify_question('Review my blood chemistry results'), 'labs')

    def test_source_pages_verified_across_boundary_and_stale_text_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.pdf'
            with fitz.open() as pdf:
                pdf.new_page().insert_text((72,72), 'First page evidence.')
                pdf.new_page().insert_text((72,72), 'Second page evidence.')
                pdf.save(path)
            chunk = {'source':'test','page':99,'text':'First page evidence. Second page evidence.'}
            with patch.object(grounding,'ROOT',Path(directory)):
                result = grounding.verified_source(chunk)
                self.assertEqual(result['pages'], [1,2])
                self.assertIsNone(grounding.verified_source(dict(chunk,text='Invented evidence')))

    def test_citations_are_resolved_not_blindly_prepended(self):
        sources = [{'citation_id':'G1','title':'Guideline title','pdf_file':'test.pdf','page':2,'page_end':3,
                    '_evidence':['This is exact supporting evidence.']}]
        paragraph = {'text': 'Supported answer.', 'evidence': [{'source_id': 'G1', 'quote': 'This is exact supporting evidence.'}]}
        answer = json.dumps({'paragraphs': [paragraph]})
        self.assertIn('PDF pages 2-3', grounding.render_citations(answer, sources))
        self.assertNotIn('(G1)', grounding.render_citations(answer.replace('Supported answer.', 'Supported answer (G1).'), sources))
        self.assertIsNone(grounding.render_citations('Unsupported answer.', sources))
        self.assertIsNone(grounding.render_citations(answer.replace('G1','G9'), sources))
        self.assertIsNone(grounding.render_citations(answer.replace('exact supporting','invented unsupported'), sources))
        self.assertIsNone(grounding.render_citations(json.dumps({'paragraphs':[paragraph,{'text':'Extra claim.'}]}), sources))
        self.assertIsNone(grounding.render_citations(json.dumps({'paragraphs':[{'text':'Claim',
            'evidence':[{'source_id':[]}]}]}), sources))
        self.assertIsNotNone(grounding.render_citations(json.dumps({'paragraphs':[{'text':'Supported answer.',
            'evidence':[{'source_id':'G1'}]}]}), sources))
        self.assertNotIn('_evidence', service.public_guideline_sources(sources)[0])
        sources[0]['_evidence'] = ['This is exact sup-\nporting evidence.']
        self.assertIsNotNone(grounding.render_citations(answer, sources))

    def test_missing_evidence_does_not_return_model_recommendation(self):
        with patch.object(service,'call_llm') as model:
            answer = service.finalize_guideline_answer('Take a drug.', [], 'prompt')
        self.assertEqual(answer, grounding.NO_EVIDENCE)
        model.assert_not_called()

    def test_compact_sources_are_cited_once_without_dropping_needed_pages(self):
        sources = [{'citation_id':f'G{i}', 'title':'Guideline', 'pdf_file':'guideline.pdf',
                    'page':page, 'page_end':page} for i,page in enumerate([19,20,30],1)]
        payload = {'paragraphs': [
            {'text':'First requested point.', 'evidence':[{'source_id':'G1'}]},
            {'text':'Second requested point.', 'evidence':[{'source_id':'G1'},{'source_id':'G2'}]}]}
        with patch.object(service,'call_llm') as model:
            result = service.finalize_guideline_answer(json.dumps(payload), sources, 'prompt')
        self.assertEqual(result.count('Guideline'),1)
        self.assertIn('PDF pages 19-20',result)
        self.assertNotIn('Source:',result)
        self.assertNotIn('guideline.pdf',result)
        self.assertIn('Second requested point.',result)
        self.assertEqual([s['page'] for s in service.public_guideline_sources(sources)], [19,20])
        model.assert_not_called()

    def test_single_page_answer_does_not_display_other_retrieved_pages(self):
        sources = [{'citation_id':f'G{i}', 'title':'Guideline', 'pdf_file':'guideline.pdf',
                    'page':page, 'page_end':page} for i,page in enumerate([19,20],1)]
        answer = json.dumps({'paragraphs':[{'text':'Direct answer.', 'source_id':'G1'}]})
        result = service.finalize_guideline_answer(answer, sources, 'prompt')
        self.assertIn('PDF page 19',result)
        self.assertNotIn('20',result)
        self.assertEqual([s['page'] for s in service.public_guideline_sources(sources)], [19])

    def test_simple_question_retries_expansion_instead_of_silently_truncating(self):
        sources = [{'citation_id':'G1','title':'Guideline','pdf_file':'test.pdf','page':19,'page_end':19}]
        question = 'Should normal home BP or high office BP be used?'
        draft = json.dumps({'paragraphs':[{'text':'Direct answer.','source_id':'G1'},
                                         {'text':'Unrequested follow-up.','source_id':'G1'}]})
        revised = json.dumps({'paragraphs':[{'text':'Direct answer with essential qualification.','source_id':'G1'}]})
        with patch.object(service,'call_llm',return_value=revised) as model:
            result = service.finalize_guideline_answer(draft, sources, 'prompt', question)
        model.assert_called_once()
        self.assertIn('exactly ONE paragraph',model.call_args.args[0])
        self.assertIn('essential qualification',result)
        self.assertNotIn('Unrequested follow-up',result)
        self.assertFalse(grounding.wants_brief_answer('Explain in detail how ABPM differs from HBPM.'))
        self.assertFalse(grounding.wants_brief_answer('What device is recommended and under what conditions is the alternative used?'))

    def test_bad_citation_retry_fails_closed(self):
        sources = [{'citation_id':'G1','title':'Guideline','pdf_file':'test.pdf','page':2,'page_end':2}]
        with patch.object(service,'call_llm', return_value='Based on [G9], invented answer.'):
            answer = service.finalize_guideline_answer('Uncited answer.', sources, 'evidence prompt')
        self.assertNotIn('invented answer', answer)
        self.assertIn('could not produce', answer)

    def test_groq_withholds_truncated_answer_and_budgets_guideline_output(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'length', 'message': {'content': 'Partial answer'}}]}
        with patch.object(service, 'GROQ_API_KEY', 'test-only'), \
             patch.object(service, 'GROQ_MODEL', 'openai/gpt-oss-20b'), \
             patch.object(service.requests, 'post', return_value=response) as post:
            with self.assertRaises(service.HTTPException):
                service.call_groq(grounding.INSTRUCTIONS)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['max_completion_tokens'], 2400)
        self.assertEqual(payload['reasoning_effort'], 'medium')

    def test_non_guideline_prompt_does_not_accidentally_enable_json_mode(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices':[{'finish_reason':'stop','message':{'content':'Plain answer.'}}]}
        prompt = service.SYSTEM_PROMPT.format(tools_section='') + '\nQuestion: How is pulse measured?'
        self.assertIn('GUIDELINE ANSWER REQUIREMENTS',prompt)
        with patch.object(service,'GROQ_API_KEY','test-only'), \
             patch.object(service,'GROQ_MODEL','openai/gpt-oss-20b'), \
             patch.object(service.requests,'post',return_value=response) as post:
            self.assertEqual(service.call_groq(prompt),'Plain answer.')
        payload = post.call_args.kwargs['json']
        self.assertNotIn('response_format',payload)
        self.assertEqual(payload['max_completion_tokens'],800)

    def test_antihypertensive_questions_use_guidelines(self):
        for question in [
            'What antihypertensives should be used according to what comorbid conditions are present?',
            'What antihypertensives are safe while breast feeding?',
        ]:
            self.assertEqual(service.classify_question(question), 'guideline')

    def test_groq_request_errors_are_specific_and_not_retried(self):
        for status, code, expected in [
            (400, 'json_validate_failed', 'valid response format'),
            (400, 'output_parse_failed', 'valid response format'),
            (401, None, 'credentials or access'),
            (400, None, 'rejected CLARA'),
        ]:
            response = Mock(status_code=status)
            response.json.return_value = {'error': {'code': code, 'message': 'PRIVATE BODY'}}
            with self.subTest(status=status, code=code), \
                 patch.object(service, 'GROQ_API_KEY', 'test-only'), \
                 patch.object(service.requests, 'post', return_value=response) as post:
                with self.assertRaises(service.HTTPException) as caught:
                    service.call_groq('test prompt')
                self.assertEqual(caught.exception.status_code, 502)
                self.assertIn(expected, caught.exception.detail)
                self.assertNotIn('PRIVATE BODY', caught.exception.detail)
                post.assert_called_once()

    def test_both_chat_routes_render_verified_sources_instead_of_json(self):
        source = {'citation_id':'G1','title':'Verified guideline','pdf_file':'test.pdf',
                  'source':'test','page':7,'page_end':7,'_evidence':['Use the supported measurement method.']}
        answer = json.dumps({'paragraphs':[{'text':'Use the supported measurement method.',
            'evidence':[{'source_id':'G1','quote':'Use the supported measurement method.'}]}]})
        client = TestClient(service.app)
        for route in ['/chat', '/chat/stream']:
            with patch.object(service,'build_guideline_bundle',return_value=('Guideline evidence',[source])), \
                 patch.object(service,'call_llm',return_value=answer):
                response = client.post(route,json={'patient_id':'','message':'How should home BP be measured?',
                    'session_id':'grounding-test-'+route,'history':[]})
            self.assertEqual(response.status_code,200)
            if route.endswith('stream'):
                events = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')]
                text = ''.join(e['token'] for e in events if e['type']=='token')
                self.assertNotIn('_evidence',response.text)
            else:
                text = response.json()['response']
            self.assertTrue(text.startswith('Based on Verified guideline'))
            self.assertIn('PDF page 7',text)
            self.assertNotIn('"paragraphs"',text)

    def test_stream_with_no_evidence_never_calls_model(self):
        with patch.object(service,'build_guideline_bundle',return_value=('Evidence unavailable',[])), \
             patch.object(service,'call_llm') as model:
            response = TestClient(service.app).post('/chat/stream',json={
                'patient_id':'','message':'What does the BP guideline recommend?',
                'session_id':'grounding-empty-test','history':[]})
        model.assert_not_called()
        self.assertIn('done', response.text)

if __name__ == '__main__':
    unittest.main()
