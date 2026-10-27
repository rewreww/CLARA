"""Restricted localhost gateway for scheduled CLARA respondent sessions."""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 3 * 1024 * 1024
PRIVATE = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
           "X-Accel-Buffering": "no", "X-Robots-Tag": "noindex, nofollow"}
POST_BACKEND = {"chemistry-results", "hematology-results", "microscopy-results",
                "labs-timeline", "discharge-list", "discharge-parsed", "vitals", "vitals-timeline"}
POST_LLM = {"chat/stream", "clinical-alerts", "privacy/sanitize-history", "history/clear"}


def route_target(method, path):
    if method in {"GET", "HEAD"}:
        if path == "api/backend/patientdata/patients":
            return "http://127.0.0.1:5000/api/patientdata/patients"
        if re.fullmatch(r"api/backend/patientdata/[0-9]{5}/document", path):
            return "http://127.0.0.1:5000/" + path.replace("api/backend/", "api/", 1)
        if path == "api/llm/documents/guideline":
            return "http://127.0.0.1:8001/documents/guideline"
    if method == "POST":
        if path.removeprefix("api/backend/patientdata/") in POST_BACKEND and path.startswith("api/backend/patientdata/"):
            return "http://127.0.0.1:5000/" + path.replace("api/backend/", "api/", 1)
        if path.startswith("api/llm/") and path.removeprefix("api/llm/") in POST_LLM:
            return "http://127.0.0.1:8001/" + path.removeprefix("api/llm/")
    return None


def create_app(key, transport=None):
    if len(key) < 32:
        raise ValueError("Gateway key is missing or too short. Run scripts/prepare_demo.py first.")
    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(timeout=httpx.Timeout(110, connect=5),
                                    limits=httpx.Limits(max_connections=24),
                                    follow_redirects=False, trust_env=False, transport=transport) as client:
            app.state.client = client
            yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    chat_slots = asyncio.Semaphore(4)
    chat_times = deque()

    def error(status, message):
        return JSONResponse({"detail": message}, status_code=status, headers=PRIVATE)

    @app.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
    async def proxy(path: str, request: Request):
        supplied = request.headers.get('x-clara-gateway-key', '')
        if not hmac.compare_digest(supplied.encode(), key.encode()):
            return error(401, 'Gateway authentication required')
        if path == 'health' and request.method == 'GET':
            return JSONResponse({'status': 'gateway_ready'}, headers=PRIVATE)
        # Respondents do not need the ingestion worker's logs or filesystem paths.
        if path == 'api/backend/pdfingestion/sync/status' and request.method == 'GET':
            return JSONResponse({'events': []}, headers=PRIVATE)
        target = route_target(request.method, path)
        if not target:
            return error(404, 'This endpoint is not available in the respondent demo')
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return error(413, 'Request exceeds the demo size limit')
        if request.method == 'POST':
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError()
            except (ValueError, UnicodeDecodeError):
                return error(400, 'Expected a JSON object')
            if path.endswith(('chat/stream', 'history/clear')):
                session = data.get('session_id')
                if not isinstance(session, str) or not 8 <= len(session) <= 200:
                    return error(400, 'A conversation identifier is required')
                # Keep demo conversations separate from the local researcher's chats.
                data['session_id'] = 'demo-' + hmac.new(key.encode(), session.encode(), hashlib.sha256).hexdigest()
            if path.endswith('chat/stream'):
                if not isinstance(data.get('history'), list):
                    return error(400, 'Explicit conversation history is required')
            body = json.dumps(data).encode()
        is_chat = path.endswith('chat/stream')
        acquired = False
        if is_chat:
            now = time.monotonic()
            while chat_times and now - chat_times[0] > 60:
                chat_times.popleft()
            if len(chat_times) >= 30:
                return error(429, 'Demo chat is busy; try again in one minute')
            try:
                await asyncio.wait_for(chat_slots.acquire(), timeout=0.1)
                acquired = True
                chat_times.append(now)
            except asyncio.TimeoutError:
                return error(429, 'Four chats are already running; please try again shortly')
        headers = {name: request.headers[name] for name in ('accept', 'content-type', 'range', 'if-range') if name in request.headers}
        try:
            outgoing = app.state.client.build_request(request.method, target,
                params=request.query_params.multi_items(), content=bytes(body), headers=headers)
            upstream = await app.state.client.send(outgoing, stream=True)
        except httpx.HTTPError:
            if acquired:
                chat_slots.release()
            return error(503, 'CLARA backend is offline. Please contact the research team.')
        if upstream.status_code >= 500 or 300 <= upstream.status_code < 400:
            await upstream.aclose()
            if acquired:
                chat_slots.release()
            return error(502, 'The CLARA service could not complete this request')
        response_headers = {name: value for name, value in upstream.headers.items()
            if name in {'content-type', 'content-range', 'accept-ranges', 'content-disposition', 'content-encoding'}}
        response_headers.update(PRIVATE)

        async def chunks():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()
                if acquired:
                    chat_slots.release()
        return StreamingResponse(chunks(), status_code=upstream.status_code, headers=response_headers)

    return app


def configured_app():
    from dotenv import dotenv_values
    values = dotenv_values(ROOT / '.clara' / 'deployment' / 'gateway.env')
    return create_app(os.environ.get('CLARA_GATEWAY_KEY') or values.get('CLARA_GATEWAY_KEY') or '')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(configured_app(), host='127.0.0.1', port=8765, access_log=False, server_header=False)
