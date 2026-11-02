"""One live guideline-only chat check. Source cards are NOT Ragas context capture."""
import json
from pathlib import Path
import uuid

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    question = json.loads((ROOT / '.clara/evaluation/grounding/questions.jsonl').read_text(encoding='utf-8'))
    response = requests.post('http://127.0.0.1:8001/chat/stream', json={
        'patient_id': '', 'message': question['question'],
        'session_id': 'grounding-smoke-' + uuid.uuid4().hex, 'history': [],
    }, timeout=180)
    response.raise_for_status()
    events = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')]
    answer = ''.join(event['token'] for event in events if event['type'] == 'token')
    record = {'purpose': 'Live endpoint smoke check, not exact generation-context capture',
              'question': question, 'answer': answer, 'events': events}
    (ROOT / '.clara/evaluation/grounding/live-smoke.json').write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
    assert not any(event['type'] == 'error' for event in events), 'Live generation error; inspect saved events'
    assert any(event['type'] == 'done' for event in events), 'Stream did not complete'
    assert answer.startswith('Based on ') and 'PDF page' in answer, 'Expected verified citation opening'
    assert '"paragraphs"' not in answer, 'Internal model JSON leaked into chat'
    print(answer)
    print('\nLive endpoint check passed.')


if __name__ == '__main__':
    main()
