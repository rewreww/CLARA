import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

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
    def test_mimic_read_routes_and_private_context(self):
        for endpoint in ['summary', 'records', 'documents', 'vitals']:
            self.assertIsNotNone(route_target('GET', f'api/backend/patientdata/Patient_12345678/mimic/{endpoint}'))
        self.assertIsNotNone(route_target('GET', 'api/backend/patientdata/Patient_12345678/document'))
        self.assertIsNone(route_target('GET', 'api/backend/patientdata/Patient_12345678/mimic/context'))
        self.assertIsNone(route_target('POST', 'api/backend/patientdata/Patient_12345678/mimic/records'))

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
        upstream = next(req for req in self.requests if req.url.path == '/api/patientdata/00001/document')
        self.assertEqual(str(upstream.url),'http://127.0.0.1:5000/api/patientdata/00001/document?source=discharge%2Ffile.pdf')
        self.assertEqual(upstream.headers['range'],'bytes=0-9')
        self.assertNotIn('authorization',upstream.headers)
        self.assertNotIn('cookie',upstream.headers)
        self.assertNotIn('x-clara-gateway-key',upstream.headers)
        self.assertNotIn('set-cookie',response.headers)
        self.assertEqual(response.headers['cache-control'],'private, no-store')

    def test_stream_content_and_session_namespace(self):
        response = self.client.post('/api/llm/chat/stream',headers=AUTH,
            json={'patient_id':'00001','session_id':'session-123','message':'demo','history':[]})
        self.assertEqual(response.content,b'data: first\n\ndata: second\n\n')
        upstream_chat = next(req for req in self.requests if req.url.path == '/chat/stream')
        sent = json.loads(upstream_chat.content)
        self.assertTrue(sent['session_id'].startswith('demo-'))
        self.assertNotEqual(sent['session_id'],'session-123')
        self.client.post('/api/llm/history/clear',headers=AUTH,json={'session_id':'session-123'})
        upstream_clear = next(req for req in self.requests if req.url.path == '/history/clear')
        self.assertEqual(json.loads(upstream_clear.content)['session_id'],sent['session_id'])

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

    def test_account_allowlist_does_not_open_unrestricted_backend(self):
        self.assertIsNotNone(route_target('GET', 'api/backend/account/config'))
        self.assertIsNotNone(route_target('POST', 'api/backend/account/login'))
        self.assertIsNotNone(route_target('GET', 'api/backend/account/conversations'))
        self.assertIsNotNone(route_target('PUT', 'api/backend/account/conversations/session_abcdefgh'))
        self.assertIsNone(route_target('GET', 'api/backend/account/secrets'))
        self.assertIsNone(route_target('POST', 'api/backend/account/users/any/recovery'))

    def test_auth_enabled_rejects_unauthenticated_clinical_requests_and_preserves_login_cookie(self):
        paths = []
        def upstream(request):
            paths.append(request.url.path)
            if request.url.path == '/api/account/config':
                return httpx.Response(200, json={'enabled': True})
            if request.url.path == '/api/account/me':
                return httpx.Response(401, json={'error':'Unauthorized'})
            if request.url.path == '/api/account/login':
                return httpx.Response(200, json={'id':'test','role':'clinician'},
                    headers={'set-cookie':'clara_session=test; HttpOnly; Path=/; SameSite=Lax'})
            return httpx.Response(500)
        with patch.dict('os.environ', {'CLARA_AUTH_ENABLED':'true'}), TestClient(create_app(KEY,httpx.MockTransport(upstream))) as client:
            denied=client.get('/api/backend/patientdata/patients',headers=AUTH)
            self.assertEqual(denied.status_code,401)
            self.assertNotIn('/api/patientdata/patients',paths)
            login=client.post('/api/backend/account/login',headers=AUTH,json={'username':'test','password':'test'})
            self.assertEqual(login.status_code,200)
            self.assertIn('clara_session=',login.headers.get('set-cookie',''))

    def test_llm_cache_id_is_separated_by_authenticated_account(self):
        seen = []
        def upstream(request):
            if request.url.path == '/api/account/config':
                return httpx.Response(200,json={'enabled':True})
            if request.url.path == '/api/account/me':
                owner = request.headers.get('cookie','').replace('clara_session=','')
                return httpx.Response(200,json={'id':owner,'role':'clinician'})
            if request.url.path == '/chat/stream':
                seen.append(json.loads(request.content)['session_id'])
                return httpx.Response(200,content=b'data: {"type":"done"}\\n\\n',
                    headers={'content-type':'text/event-stream'})
            return httpx.Response(404)
        with patch.dict('os.environ', {'CLARA_AUTH_ENABLED':'true'}), TestClient(create_app(KEY,httpx.MockTransport(upstream))) as client:
            for owner in ('staff-a','staff-b'):
                response=client.post('/api/llm/chat/stream',
                    headers={**AUTH,'cookie':'clara_session='+owner},
                    json={'session_id':'session_abcdefgh','message':'hello','history':[]})
                self.assertEqual(response.status_code,200)
        self.assertEqual(len(seen),2)
        self.assertNotEqual(seen[0],seen[1])

if __name__ == '__main__':
    unittest.main()
