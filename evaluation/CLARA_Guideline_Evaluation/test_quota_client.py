import asyncio
import unittest
import httpx
from quota_client import QuotaClient


class QuotaTests(unittest.IsolatedAsyncioTestCase):
    async def test_requests_are_serialized_and_headers_update_budget(self):
        active = 0
        maximum = 0
        async def handler(request):
            nonlocal active, maximum
            active += 1
            maximum = max(active, maximum)
            await asyncio.sleep(0)
            active -= 1
            return httpx.Response(200, json={'ok': True}, headers={
                'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '7000'})
        async with QuotaClient(transport=httpx.MockTransport(handler)) as client:
            client._available = 8000
            await asyncio.gather(*(client.post('https://example.test/chat', json={'messages': []}) for _ in range(2)))
            self.assertEqual(maximum, 1)
            self.assertEqual(client._available, 7000)

    async def test_oversized_prompt_does_not_make_request(self):
        async with QuotaClient(transport=httpx.MockTransport(lambda request: self.fail('Network not expected'))) as client:
            with self.assertRaises(ValueError):
                await client.post('https://example.test/chat', json={'messages': ['x' * 30000]})
