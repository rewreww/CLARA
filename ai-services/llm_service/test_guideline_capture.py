import unittest
from unittest.mock import patch
import guideline_trace
import llm_client as service


class GuidelineCaptureTests(unittest.TestCase):
    def setUp(self):
        def source(chunk):
            return {'source': chunk['source'], 'title': chunk['source'], 'pdf_file': chunk['source'] + '.pdf',
                    'page': chunk['page'], 'page_end': chunk['page'], 'pages': [chunk['page']], 'type': 'guideline'}
        patcher = patch.object(service.guideline_grounding, 'verified_source', side_effect=source)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_supplied_passages_are_captured(self):
        chunks = [{'source': f'doc-{i}', 'page': 1, 'text': f'evidence-{i}', 'relevance': 100-i,
                   'is_philippine': True, 'is_recommendation': True} for i in range(5)]
        with guideline_trace.capture() as trace, patch.object(service, 'retrieve', return_value=chunks):
            context, sources = service.build_guideline_bundle('guideline treatment')
            self.assertEqual(len(sources), 3)
            self.assertEqual([p['text'] for p in trace['passages']], ['evidence-0', 'evidence-1', 'evidence-2'])
            self.assertNotIn('evidence-3', context)
            with patch.object(service, 'LLM_PROVIDER', 'groq'), patch.object(service, 'call_groq', return_value='mock response') as model:
                service.call_llm('prefix\n' + context)
                self.assertEqual(trace['generation_calls'][0]['prompt'], model.call_args.args[0])

    def test_two_passages_from_same_page_are_not_collapsed(self):
        chunks = [{'source': 'same', 'page': 1, 'text': text} for text in ['first', 'second']]
        with guideline_trace.capture() as trace, patch.object(service, 'retrieve', return_value=chunks):
            context, sources = service.build_guideline_bundle('guideline')
            self.assertEqual(len(sources), 1)
            self.assertEqual(len(trace['passages']), 2)
            self.assertLess(context.index('first'), context.index('second'))


if __name__ == '__main__':
    unittest.main()
