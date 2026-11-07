import unittest
from unittest.mock import Mock, patch
import grounding_reviewer as reviewer


class ReviewerClientTests(unittest.TestCase):
    def setUp(self):
        reviewer.review.cache_clear()

    def test_exact_review_is_cached_and_uses_bounded_json_request(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices':[{'finish_reason':'stop', 'message':{'content':'{"checks":[]}'}}]}
        with patch.object(reviewer.requests, 'post', return_value=response) as post:
            for _ in range(2):
                reviewer.review('evidence', 'groq', 'openai/gpt-oss-20b', 'test-key')
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs['timeout'], (10, 35))
        self.assertEqual(post.call_args.kwargs['json']['response_format'], {'type':'json_object'})

    def test_truncation_and_refusal_are_never_accepted(self):
        for choice in [{'finish_reason':'length', 'message':{'content':'partial'}},
                       {'finish_reason':'stop', 'message':{'content':'{}', 'refusal':'declined'}}]:
            response = Mock(status_code=200)
            response.json.return_value = {'choices':[choice]}
            with patch.object(reviewer.requests, 'post', return_value=response):
                with self.assertRaises(reviewer.ReviewUnavailable):
                    reviewer.review('evidence', 'groq', 'model', 'test-key')

    def test_network_failure_does_not_retry_or_approve(self):
        with patch.object(reviewer.requests, 'post', side_effect=reviewer.requests.Timeout()) as post:
            with self.assertRaises(reviewer.ReviewUnavailable):
                reviewer.review('evidence', 'groq', 'model', 'test-key')
        post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
