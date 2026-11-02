"""Merge successful capture attempts; keep failures as missing outputs, never zeros."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / '.clara/evaluation/pilot'


def prepare():
    records, ledger = {}, []
    for folder in [PILOT / 'baseline-01', PILOT / 'retry-01']:
        path = folder / 'outputs.jsonl'
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            ledger.append({'id': row['id'], 'attempt': folder.name, 'status': row['capture_status']})
            if row['capture_status'] == 'complete':
                records[row['id']] = row
    (PILOT / 'captured_outputs.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records.values()), encoding='utf-8')
    (PILOT / 'attempts.json').write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    shutil.copyfile(PILOT / 'baseline-01/pipeline_config.json', PILOT / 'pipeline_config.json')
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for folder in ['ai-services/rag', 'ai-services/llm_service', 'evaluation']
                     for p in (ROOT / folder).rglob('*.py') if '__pycache__' not in p.parts}
    (PILOT / 'source-hashes.json').write_text(json.dumps(source_hashes, indent=2), encoding='utf-8')
    print(f'{len(records)} successful outputs prepared; missing cases remain in scoring denominator.')


if __name__ == '__main__':
    prepare()
