import sys
from pathlib import Path
import unittest
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_watchdog import probe, restart_due


class WatchdogTests(unittest.TestCase):
    def test_health_requires_application_identity(self):
        for response in (httpx.Response(200, text='<html>sign in</html>'),
                         httpx.Response(302, headers={'location': 'https://login.example'}),
                         httpx.Response(200, json={'status': 'unrelated'}),
                         httpx.Response(503)):
            with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
                self.assertFalse(probe(client, 'https://example.test/health', 'secret', ('status', 'gateway_ready')))

    def test_health_supplies_gateway_and_bypass_headers(self):
        def handler(request):
            self.assertEqual(request.headers['x-clara-gateway-key'], 'secret')
            self.assertEqual(request.headers['X-Tunnel-Skip-AntiPhishing-Page'], '1')
            return httpx.Response(200, json={'status': 'gateway_ready'})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            self.assertTrue(probe(client, 'https://example.test/health', 'secret', ('status', 'gateway_ready')))

    def test_transient_failure_does_not_restart_tunnel(self):
        self.assertFalse(restart_due(1, 0, 300))
        self.assertFalse(restart_due(3, 250, 300))
        self.assertTrue(restart_due(3, 0, 300))

    def test_vercel_check_requires_patient_api_response(self):
        for body, expected in [({'patients': []}, True), ({'patients': 'error'}, False),
                               ({'events': []}, False), ([], False)]:
            with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as client:
                self.assertEqual(probe(client, 'https://example.test/api/backend/patientdata/patients',
                                       expected=('patients', list)), expected)

    def test_connection_failure_is_unhealthy(self):
        def offline(request):
            raise httpx.ConnectError('offline', request=request)
        with httpx.Client(transport=httpx.MockTransport(offline)) as client:
            self.assertFalse(probe(client, 'https://example.test/health'))


if __name__ == '__main__':
    unittest.main()
