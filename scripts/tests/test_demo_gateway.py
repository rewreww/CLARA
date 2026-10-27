import json
from pathlib import Path
import sys
import unittest

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_gateway import create_app, route_target, MAX_BODY

KEY = 'test-only-key-not-a-secret-' + 'a' * 32
AUTH = {'x-clara-gateway-key': KEY}

class Body(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'data: first\n\n'
        yield b'data: second\n\n'

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        def upstream(request):
            self.requests.append(request)
            return httpx.Response(206 if 'range' in request.headers else 200,
                headers={'content-type': 'text/event-stream', 'content-range':'bytes 0-9/20',
                         'set-cookie':'must-not-leak=1', 'server':'private-backend'}, stream=Body())
        self.client = TestClient(create_app(KEY, httpx.MockTransport(upstream)))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)

    def test_key_required_even_for_health_and_docs(self):
        for path in ['/health','/docs','/api/backend/patientdata/patients']:
            self.assertEqual(self.client.get(path).status_code,401)
        self.assertEqual(self.client.get('/health',headers=AUTH).status_code,200)
        self.assertEqual(self.requests,[])

    def test_no_ingestion_write_history_dump_or_arbitrary_proxy(self):
        for method,path in [('POST','api/backend/pdfingestion/sync'),('GET','api/llm/history/known'),
            ('GET','api/llm/health'),('GET','https://example.com'),('DELETE','api/backend/patientdata/patients')]:
            self.assertIsNone(route_target(method,path))
        self.assertEqual(self.client.get('/docs',headers=AUTH).status_code,404)

    def test_preserves_pdf_range_query_and_strips_response_cookies(self):
        response = self.client.get('/api/backend/patientdata/00001/document?source=discharge%2Ffile.pdf',
            headers={**AUTH,'range':'bytes=0-9','authorization':'secret','cookie':'secret'})
        self.assertEqual(response.status_code,206)
        upstream = self.requests[0]
        self.assertEqual(str(upstream.url),'http://127.0.0.1:5000/api/patientdata/00001/document?source=discharge%2Ffile.pdf')
        self.assertEqual(upstream.headers['range'],'bytes=0-9')
        self.assertNotIn('authorization',upstream.headers)
        self.assertNotIn('x-clara-gateway-key',upstream.headers)
        self.assertNotIn('set-cookie',response.headers)
        self.assertEqual(response.headers['cache-control'],'private, no-store')

    def test_stream_content_and_session_namespace(self):
        response = self.client.post('/api/llm/chat/stream',headers=AUTH,
            json={'patient_id':'00001','session_id':'session-123','message':'demo','history':[]})
        self.assertEqual(response.content,b'data: first\n\ndata: second\n\n')
        sent = json.loads(self.requests[0].content)
        self.assertTrue(sent['session_id'].startswith('demo-'))
        self.assertNotEqual(sent['session_id'],'session-123')
        self.client.post('/api/llm/history/clear',headers=AUTH,json={'session_id':'session-123'})
        self.assertEqual(json.loads(self.requests[1].content)['session_id'],sent['session_id'])

    def test_invalid_or_oversized_json_and_missing_history_are_rejected(self):
        for body in [b'bad',b'[]']:
            self.assertEqual(self.client.post('/api/llm/chat/stream',headers=AUTH,content=body).status_code,400)
        self.assertEqual(self.client.post('/api/llm/chat/stream',headers=AUTH,
            json={'session_id':'session-123'}).status_code,400)
        self.assertEqual(self.client.post('/api/llm/chat/stream',headers=AUTH,
            content=b'x'*(MAX_BODY+1)).status_code,413)
        self.assertEqual(self.requests,[])

    def test_backend_outage_does_not_expose_exception(self):
        def unavailable(request):
            raise httpx.ConnectError('private path and configuration',request=request)
        with TestClient(create_app(KEY,httpx.MockTransport(unavailable))) as client:
            response=client.get('/api/backend/patientdata/patients',headers=AUTH)
            self.assertEqual(response.status_code,503)
            self.assertNotIn('private path',response.text)

    def test_sync_log_is_not_exposed(self):
        response=self.client.get('/api/backend/pdfingestion/sync/status',headers=AUTH)
        self.assertEqual(response.json(),{'events':[]})
        self.assertEqual(self.requests,[])

if __name__ == '__main__':
    unittest.main()
