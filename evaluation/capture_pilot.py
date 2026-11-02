"""Run guideline-only questions through CLARA's real streaming handler.

No references are loaded. Uses an isolated in-process service instance, no patient
ID/history/tools; logs the exact generation inputs. Requires --generate.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
import time
from provenance import page_passages

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ai-services/llm_service'))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'


async def run(args):
    import llm_client as service
    import guideline_trace
    if service.LLM_PROVIDER != 'groq':
        raise ValueError('Pilot requires the configured Groq adapter; no silent provider fallback.')
    questions = [json.loads(line) for line in Path(args.questions).read_text(encoding='utf-8').splitlines() if line.strip()]
    if any(set(q) != {'id', 'question'} for q in questions):
        raise ValueError('Generation input must contain only id and question, never references.')
    corpus = json.loads((ROOT / '.clara/evaluation/corpus.json').read_text(encoding='utf-8'))
    registry = {Path(d['pdf_file']).stem: d for d in corpus['documents']}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    config = {'clara_version': 'working-tree-sha256:' + hashlib.sha256(Path(service.__file__).read_bytes()).hexdigest(),
              'generator_model': service.GROQ_MODEL, 'retrieval_embedding_model': service.RAG_EMBED_MODEL,
              'chunk_size': 'legacy 350 words target; oversized paragraphs not split',
              'chunk_overlap': 'legacy up to 60 whole-paragraph words', 'top_k': 5,
              'prompt_sha256': hashlib.sha256(service.SYSTEM_PROMPT.encode()).hexdigest()}
    config['grounding_sha256'] = hashlib.sha256(Path(service.guideline_grounding.__file__).read_bytes()).hexdigest()
    config['retriever_sha256'] = hashlib.sha256((ROOT / 'ai-services/rag/retriever.py').read_bytes()).hexdigest()
    config['guideline_max_completion_tokens'] = 2400
    config['guideline_reasoning_effort'] = 'medium' if service.GROQ_MODEL in {'openai/gpt-oss-20b', 'openai/gpt-oss-120b'} else 'provider_default'
    (output / 'pipeline_config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    def blocked(*args, **kwargs):
        raise RuntimeError('Patient tools, clinical rules, and prediction models are forbidden in guideline pilot')
    # A regression into a patient/tool path fails the run rather than mixing sources.
    service.execute_tool = blocked
    service.run_ml_assessment = blocked
    service.rule_engine = blocked
    with (output / 'outputs.jsonl').open('w', encoding='utf-8') as stream:
        for index, q in enumerate(questions, 1):
            session = 'guideline-eval-' + uuid.uuid4().hex
            started = time.monotonic()
            events, trace = [], {'passages': [], 'generation_calls': []}
            record = {'id': q['id'], 'question': q['question'], 'response': '', 'contexts': [],
                      'contexts_are_generation_input': False,
                      'route': service.resolve_question_type(q['question'], [])}
            (output / 'progress.json').write_text(json.dumps({'completed': index-1, 'total': len(questions),
                'current_id': q['id'], 'current_question': q['question']}), encoding='utf-8')
            try:
                with guideline_trace.capture() as trace:
                    response = service.chat_stream(service.ChatRequest(patient_id='', message=q['question'], session_id=session, history=[]))
                    async for raw in response.body_iterator:
                        raw = raw.decode() if isinstance(raw, bytes) else raw
                        events.extend(json.loads(line[5:]) for line in raw.splitlines() if line.startswith('data:'))
                record['response'] = ''.join(e['token'] for e in events if e['type'] == 'token')
                record['sources'] = next((e.get('sources', []) for e in reversed(events) if e['type'] == 'meta'), [])
                if any(e['type'] == 'error' for e in events) or not any(e['type'] == 'done' for e in events):
                    raise RuntimeError('Generation failed or did not complete; see local service diagnostics')
                for chunk in trace['generation_calls'][-1]['passages'] if trace['generation_calls'] else []:
                    doc = registry[chunk['source']]
                    pages = json.loads(Path(doc['extraction']).read_text(encoding='utf-8'))
                    record['contexts'].extend(page_passages(chunk, doc, pages))
                for rank, passage in enumerate(record['contexts'], 1):
                    passage['rank'] = rank
                record['contexts_are_generation_input'] = bool(trace['generation_calls'])
                record['capture_status'] = 'complete' if trace['generation_calls'] else 'no_generation'
            except Exception as exc:
                record['capture_status'] = 'error_' + type(exc).__name__
                record['error_detail'] = str(exc)
            finally:
                service.conversation_store.pop(session, None)
                record['generation_calls'] = len(trace['generation_calls'])
                record['elapsed_seconds'] = round(time.monotonic() - started, 2)
                record['service_errors'] = [e.get('message') for e in events if e['type'] == 'error']
                (output / (q['id'] + '.trace.json')).write_text(json.dumps(trace, indent=2), encoding='utf-8')
                (output / (q['id'] + '.events.json')).write_text(json.dumps(events, indent=2), encoding='utf-8')
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            stream.flush()
            print(q['id'], record['capture_status'], len(record['contexts']), 'passages', flush=True)
            (output / 'progress.json').write_text(json.dumps({'completed': index, 'total': len(questions),
                'last_id': q['id'], 'last_status': record['capture_status']}), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    if not args.generate:
        parser.error('--generate is required: this makes real CLARA model requests for the input questions, plus any retries.')
    asyncio.run(run(args))
