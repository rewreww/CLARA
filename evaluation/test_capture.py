import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ai-services/llm_service'))
import guideline_trace
from provenance import page_passages


class CaptureTests(unittest.TestCase):
    def test_exact_cross_page_text_is_preserved(self):
        chunk = {'text': 'Alpha\n beta  gamma\ndelta', 'chunk_id': 'x'}
        result = page_passages(chunk, {'document_id': 'hash', 'pdf_file': 'x.pdf'},
                               [{'page': 3, 'text': 'Alpha beta'}, {'page': 4, 'text': 'gamma delta'}])
        self.assertEqual([p['page'] for p in result], [3, 4])
        self.assertEqual(''.join(p['text'] for p in result), chunk['text'])

    def test_ambiguous_or_missing_text_fails_closed(self):
        for text in ['missing', 'same']:
            with self.assertRaises(ValueError):
                page_passages({'text': text}, {}, [{'page': 1, 'text': 'same same'}])

    def test_inactive_capture_changes_nothing(self):
        guideline_trace.generation('normal prompt', 'huggingface')

    def test_exact_order_and_retry_inputs(self):
        with guideline_trace.capture() as trace:
            guideline_trace.passage({'text': 'first'})
            guideline_trace.passage({'text': 'second'})
            guideline_trace.generation('first second', 'groq')
            guideline_trace.generation('first second retry instruction', 'groq')
            self.assertEqual(len(trace['generation_calls']), 2)
            with self.assertRaises(ValueError):
                guideline_trace.generation('second first', 'groq')

    def test_truncating_adapter_and_cross_request_leakage(self):
        with guideline_trace.capture():
            with self.assertRaises(ValueError):
                guideline_trace.generation('input', 'huggingface')
        with guideline_trace.capture() as trace:
            self.assertEqual(trace['passages'], [])


if __name__ == '__main__':
    unittest.main()
