import os
os.environ['HF_HUB_OFFLINE'] = '1'
import sys
import json
import time
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'ai-services/llm_service'))
sys.stdout.reconfigure(encoding='utf-8')
import llm_client as service
question = 'What antihypertensives should be used according to what comorbid conditions are present?'
history = [service.HistoryEntry(role='doctor',content='When is ambulatory blood pressure monitoring recommended?')]
request = service.ChatRequest(message=question, history=history)
started = time.perf_counter()
prompt, sources = service.prepare_general_chat(request)
print('retrieval_seconds',round(time.perf_counter()-started,2),flush=True)
for source in sources:
    print('SOURCE',source['source'],source['pages'],flush=True)
Path(root / 'tmp/general-comorbidity-prompt.txt').write_text(prompt,encoding='utf-8')
started = time.perf_counter()
answer = service.generate_general_answer(request,prompt,sources)
print('generation_seconds',round(time.perf_counter()-started,2),flush=True)
print('ANSWER',answer,flush=True)
(root / 'tmp/general-comorbidity-result.json').write_text(json.dumps({'answer': answer,'sources':service.public_guideline_sources(sources)},ensure_ascii=False,indent=2),encoding='utf-8')
for question in ['How should home blood pressure be measured?', 'What antihypertensives are safe while breast feeding?']:
    started = time.perf_counter()
    _, sources = service.prepare_general_chat(service.ChatRequest(message=question,history=history))
    print('CONTROL',question,'seconds',round(time.perf_counter()-started,2),'pages',[(s['source'],s['pages']) for s in sources],flush=True)
