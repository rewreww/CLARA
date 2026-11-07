import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz
import claim_validation as validation
import guideline_grounding as grounding
import grounding_reviewer
import llm_client as service


class ClaimValidationTests(unittest.TestCase):
    def setUp(self):
        self.source = {'citation_id': 'G1', 'source': 'scope', 'title': 'Scope document',
                       'pdf_file': 'scope.pdf', 'page': 18, 'page_end': 18,
                       '_evidence': ['Chronic kidney disease has a global prevalence of 9.1%.']}

    def answer(self, text='An ACE inhibitor is the drug of choice.', quote=None):
        return json.dumps({'paragraphs': [{'text': text, 'evidence': [
            {'source_id': 'G1', 'quote': quote or self.source['_evidence'][0]}]}]})

    def test_reported_bare_source_failure_is_now_rejected(self):
        answer = json.dumps({'paragraphs':[{'text':'An ACE inhibitor is recommended.', 'source_id':'G1'}]})
        self.assertIsNone(grounding.render_citations(answer, [self.source]))

    def test_server_owned_passage_text_cannot_be_replaced_by_model(self):
        self.source['_passages'] = {'G1.P1': self.source['_evidence'][0]}
        draft = json.dumps({'paragraphs':[{'text':'A factual point.',
            'evidence':[{'source_id':'G1', 'passage_id':'G1.P1'}]}]})
        claims, error = validation.prepare_review(draft, [self.source])
        self.assertIsNone(error)
        self.assertEqual(claims[0]['evidence'][0]['quote'], self.source['_evidence'][0])
        self.assertIsNone(validation.prepare_review(draft.replace('G1.P1', 'G2.P1'), [self.source])[0])

    def test_absence_claim_review_receives_all_available_evidence(self):
        other = {**self.source, 'citation_id':'G2', '_evidence':['A treatment recommendation exists here.']}
        draft = self.answer(text='The supplied excerpts do not specify any treatment.')
        with patch.object(service, 'review_guideline_claims', return_value=(False, 'Other evidence contains treatment.')) as review, \
             patch.object(service, 'call_llm', return_value=draft):
            service.finalize_guideline_answer(draft, [self.source, other], 'prompt')
        self.assertEqual(len(review.call_args.args[2]), 2)

    def test_treatment_quote_cannot_be_assigned_to_scope_page(self):
        answer = self.answer(quote='An ACE inhibitor is recommended as first-line treatment.')
        claims, error = validation.prepare_review(answer, [self.source])
        self.assertIsNone(claims)
        self.assertIn('absent', error)

    def test_real_but_unrelated_quote_requires_semantic_review_and_fails_closed(self):
        draft = self.answer()
        self.assertIsNotNone(validation.prepare_review(draft, [self.source])[0])
        with patch.object(service, 'review_guideline_claims', return_value=(False, 'Prevalence does not support a drug recommendation.')) as review, \
             patch.object(service, 'call_llm', return_value=draft) as repair:
            result = service.finalize_guideline_answer(draft, [self.source], 'Evidence prompt', 'Drug of choice?')
        self.assertEqual(review.call_count, 2)
        repair.assert_called_once()
        self.assertNotIn('ACE inhibitor', result)
        self.assertEqual(service.public_guideline_sources([self.source]), [])

    def test_review_outage_never_releases_the_draft(self):
        with patch.object(service, 'review_guideline_claims', side_effect=grounding_reviewer.ReviewUnavailable()), \
             patch.object(service, 'call_llm') as model:
            result = service.finalize_guideline_answer(self.answer(), [self.source], 'prompt')
        self.assertIn('withheld', result)
        model.assert_not_called()
        self.assertEqual(service.public_guideline_sources([self.source]), [])

    def test_operational_review_failure_uses_one_configured_fallback(self):
        claims, _ = validation.prepare_review(self.answer(), [self.source])
        good = '{"checks":[{"id":1,"supported":true,"reason":"Supported"}]}'
        with patch.object(service, 'GROQ_API_KEY', 'test'), patch.object(service, 'OPENROUTER_API_KEY', 'test'), \
             patch.object(grounding_reviewer, 'review', side_effect=[grounding_reviewer.ReviewUnavailable(retryable=True), good]) as review:
            self.assertTrue(service.review_guideline_claims('Question', claims)[0])
        self.assertEqual(review.call_count, 2)
        self.assertNotEqual(review.call_args_list[0].args[1], review.call_args_list[1].args[1])

    def test_nonoperational_failure_never_switches_reviewers(self):
        claims, _ = validation.prepare_review(self.answer(), [self.source])
        with patch.object(grounding_reviewer, 'review', side_effect=grounding_reviewer.ReviewUnavailable('Refused')) as review:
            with self.assertRaises(grounding_reviewer.ReviewUnavailable):
                service.review_guideline_claims('Question', claims)
        review.assert_called_once()

    def test_format_repair_does_not_consume_the_evidence_repair(self):
        draft = self.answer()
        with patch.object(service, 'call_llm', return_value=draft) as repair, \
             patch.object(service, 'review_guideline_claims', side_effect=[(False, 'Unsupported wording.'), (True, '')]):
            result = service.finalize_guideline_answer('not JSON', [self.source], 'prompt')
        self.assertEqual(repair.call_count, 2)
        self.assertIn('Based on', result)
        self.assertIn('Rejected draft', repair.call_args.args[0])

    def test_every_point_requires_an_explicit_boolean_review(self):
        for raw in ['{}', '{"checks":[]}', '{"checks":[{"id":1,"supported":"true","reason":"yes"}]}',
                    '{"checks":[{"id":1,"supported":true,"reason":"yes"},{"id":1,"supported":true,"reason":"yes"}]}']:
            self.assertFalse(validation.parse_review(raw, 2)[0])
        self.assertTrue(validation.parse_review('{"checks":[{"id":1,"supported":true,"reason":"Supported"}]}', 1)[0])

    def test_review_uses_only_the_claims_own_evidence(self):
        claims, _ = validation.prepare_review(self.answer(), [self.source])
        prompt = validation.review_prompt('Drug of choice?', claims)
        self.assertIn('Prevalence'.lower(), prompt.lower())
        self.assertIn('WITH albuminuria', prompt)
        self.assertNotIn('previous conversation', prompt.lower())

    def test_exact_quote_page_is_used_instead_of_passage_start(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guide.pdf'
            with fitz.open() as pdf:
                pdf.new_page().insert_text((72, 72), 'Introductory text for a test passage.')
                pdf.new_page().insert_text((72, 72), 'The exact supporting statement is here.')
                pdf.save(path)
            with patch.object(grounding, 'ROOT', Path(directory)):
                source = grounding.verified_source({'source':'guide', 'text':
                    'Introductory text for a test passage. The exact supporting statement is here.'})
                self.assertEqual(source['pages'], [1, 2])
                self.assertEqual(grounding.locate_supporting_pages(source, ['The exact supporting statement is here.']), [2])


if __name__ == '__main__':
    unittest.main()
