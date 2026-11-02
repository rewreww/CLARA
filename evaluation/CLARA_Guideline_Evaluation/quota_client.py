"""Serialize Groq evaluator requests and pace against returned token quotas."""
import asyncio
import json
import math
import time
import httpx


class QuotaClient(httpx.AsyncClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._quota_lock = asyncio.Lock()
        self._capacity = 8000.0
        self._available = 0.0  # Conservative startup, including other active clients.
        self._updated = time.monotonic()

    async def send(self, request, **kwargs):
        async with self._quota_lock:
            payload = json.loads(request.content)
            # Conservative input estimate plus output allowance; authoritative
            # response headers correct the estimate after every request.
            estimate = math.ceil(len(json.dumps(payload.get('messages', []), ensure_ascii=False)) / 3) + 1024
            if estimate > self._capacity:
                raise ValueError('Evaluator prompt exceeds conservative token budget; inspect context size.')
            while True:
                now = time.monotonic()
                self._available = min(self._capacity, self._available + (now-self._updated)*self._capacity/60)
                self._updated = now
                if self._available >= estimate:
                    break
                await asyncio.sleep(min(45, (estimate-self._available)*60/self._capacity + 0.1))
            self._available -= estimate
            response = await super().send(request, **kwargs)
            if 'x-ratelimit-limit-tokens' in response.headers:
                self._capacity = float(response.headers['x-ratelimit-limit-tokens'])
            if 'x-ratelimit-remaining-tokens' in response.headers:
                self._available = max(0, float(response.headers['x-ratelimit-remaining-tokens']))
            self._updated = time.monotonic()
            return response
