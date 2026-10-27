"""Live localhost checks. No record contents or credentials are printed."""
import json
import argparse
from pathlib import Path
import uuid
import httpx
from dotenv import dotenv_values

folder = Path(__file__).resolve().parents[1] / '.clara' / 'deployment'
key = dotenv_values(folder / 'gateway.env')['CLARA_GATEWAY_KEY']
parser = argparse.ArgumentParser()
parser.add_argument('--public', action='store_true', help='Verify the HTTPS tunnel URL saved in the private Vercel configuration')
args = parser.parse_args()
base_url = dotenv_values(folder / 'vercel.env')['CLARA_GATEWAY_URL'] if args.public else 'http://127.0.0.1:8765'
if args.public and not base_url.startswith('https://'):
    raise SystemExit('Public gateway verification requires an HTTPS URL.')
with httpx.Client(base_url=base_url, timeout=110, trust_env=False,
                  headers={'Accept':'application/json', 'X-Tunnel-Skip-AntiPhishing-Page':'1'}, follow_redirects=False) as client:
    assert client.get('/api/backend/patientdata/patients').status_code == 401
    client.headers['x-clara-gateway-key'] = key
    assert client.get('/health').json()['status'] == 'gateway_ready'
    assert client.post('/api/backend/pdfingestion/sync').status_code == 404
    patients = client.get('/api/backend/patientdata/patients')
    patients.raise_for_status()
    records = patients.json()
    if isinstance(records, dict):
        records = records.get('patients', [])
    assert records, 'No demo patients returned'
    pdf = client.get('/api/backend/patientdata/00001/document',
        params={'source':'discharge/2023-02-23/patient_00001_Discharge.pdf'}, headers={'Range':'bytes=0-99'})
    assert pdf.status_code == 206 and pdf.content.startswith(b'%PDF')
    assert pdf.headers['cache-control'] == 'private, no-store'
    session = 'verify-demo-' + uuid.uuid4().hex
    try:
        with client.stream('POST','/api/llm/chat/stream',json={
            'patient_id':'00001','session_id':session,
            'message':'What are the cholesterol results?', 'history':[]}) as response:
            response.raise_for_status()
            assert 'text/event-stream' in response.headers.get('content-type','')
            lines = [line for line in response.iter_lines() if line.startswith('data:')]
            assert len(lines) >= 2, 'Expected multiple streaming events'
            events = [json.loads(line[5:].strip()) for line in lines]
            assert any(event.get('type') == 'done' for event in events), 'Stream did not finish'
    finally:
        client.post('/api/llm/history/clear',json={'session_id':session}).raise_for_status()
    print(f'PASS: authentication, blocked admin route, {len(records)} demo patients, PDF byte ranges, chat SSE completion, history cleanup.')
