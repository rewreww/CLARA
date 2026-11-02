"""Offline retrieval ablation: disable only the recommendation metadata filter."""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ai-services/llm_service'))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'


if __name__ == '__main__':
    import llm_client as service
    import guideline_trace
    pilot = ROOT / '.clara/evaluation/pilot'
    questions = [json.loads(l) for l in (pilot / 'generation_questions.jsonl').read_text(encoding='utf-8').splitlines()]
    rows = []
    for q in questions:
        for variant in ['baseline', 'recommendation_filter_off']:
            with guideline_trace.capture() as trace:
                if variant == 'baseline':
                    text, sources = service.build_guideline_bundle(q['question'])
                else:
                    with patch.object(service, 'is_management_query', return_value=False):
                        text, sources = service.build_guideline_bundle(q['question'])
            rows.append({'id': q['id'], 'variant': variant, 'sources': sources, 'passages': trace['passages']})
            print(q['id'], variant, [(s['source'][:45], s['page']) for s in sources], flush=True)
    (pilot / 'retrieval-ablation.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
