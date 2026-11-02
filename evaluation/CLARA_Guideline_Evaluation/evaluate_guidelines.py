"""Guideline-only CLARA evaluation. Offline checking uses only Python's standard library."""
import argparse
import asyncio
import csv
import hashlib
import html
import importlib.metadata
import json
import math
import os
from pathlib import Path
from datetime import datetime, timezone

METRICS = ('context_precision', 'context_recall', 'faithfulness', 'answer_relevancy')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError(f'{path}: invalid JSON on line {n}') from exc
            if not isinstance(row, dict):
                raise ValueError(f'{path}: line {n} must be a JSON object')
            rows.append(row)
    return rows


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text_present(value):
    return isinstance(value, str) and bool(value.strip())


def unique(rows, label):
    ids = [r.get('id') for r in rows]
    require(all(text_present(i) for i in ids), f'{label}: each id must be a nonempty string')
    require(len(ids) == len(set(ids)), f'{label}: duplicate id')
    return {r['id']: r for r in rows}


def evidence_valid(item):
    return (isinstance(item, dict) and text_present(item.get('document_id'))
            and text_present(item.get('pdf_file')) and type(item.get('page')) is int
            and item['page'] >= 1 and text_present(item.get('text')))


def validate(questions, outputs, heldout=None, reference_free=False):
    require(bool(questions), 'Question file is empty; prepare source-checked questions first.')
    qmap = unique(questions, 'Questions')
    omap = unique(outputs, 'Outputs')
    require(not (set(omap) - set(qmap)), 'Outputs contain unknown question ids')
    splits = set()
    for q in questions:
        label = q['id']
        require(text_present(q.get('question')), f'{label}: question is required')
        require(q.get('source_type') == 'guideline', f'{label}: guideline source_type required')
        require(q.get('split') in ('development', 'final'), f'{label}: invalid split')
        splits.add(q['split'])
        require(type(q.get('answerable')) is bool, f'{label}: answerable must be true or false')
        require(isinstance(q.get('reference'), str), f'{label}: reference must be text')
        evidence = q.get('reference_evidence', [])
        require(isinstance(evidence, list) and all(evidence_valid(e) for e in evidence),
                f'{label}: invalid reference evidence (document, filename, physical PDF page, text)')
        if q['answerable']:
            require(text_present(q['reference']) and bool(evidence), f'{label}: answerable question needs reference and evidence')
            require(reference_free or q.get('reference_source_checked') is True, f'{label}: reference must be source-checked')
        if label not in omap:
            continue
        o = omap[label]
        require(isinstance(o.get('response'), str), f'{label}: response must be text; use empty string for no response')
        require(o.get('contexts_are_generation_input') is True, f'{label}: confirm actual context supplied to generator')
        require(isinstance(o.get('contexts'), list), f'{label}: contexts must be a list')
        require(not o.get('question') or o['question'] == q['question'], f'{label}: output question differs')
        for rank, c in enumerate(o['contexts'], 1):
            require(evidence_valid(c), f'{label}: context {rank} has incomplete provenance')
            require(c.get('source_type') == 'guideline', f'{label}: mixed or missing context source_type')
            require(type(c.get('rank')) is int and c['rank'] == rank, f'{label}: context ranks must follow supplied order, starting at 1')
    require(len(splits) == 1, 'Keep development and final questions in separate files')
    require(not reference_free or splits == {'development'}, 'Reference-free preparation is development-only')
    if heldout is not None:
        hmap = unique(heldout, 'Held-out questions')
        norm = lambda s: ' '.join(s.casefold().split())
        require(not (set(qmap) & set(hmap)), 'Question ids overlap with held-out set')
        require(not ({norm(q['question']) for q in questions} & {norm(q['question']) for q in heldout}),
                'Question text overlaps with held-out set')
    return qmap, omap


def preset(q, output, metric):
    if output is None:
        return None, 'missing_output'
    if metric == 'context_recall' and not q['answerable']:
        return None, 'excluded_unanswerable'
    if metric != 'context_recall' and not output['response'].strip():
        return None, 'excluded_missing_response'
    if not output['contexts'] and metric in ('context_precision', 'context_recall'):
        return (0.0, 'study_convention_zero') if q['answerable'] else (None, 'excluded_unanswerable')
    return None


async def score_rows(questions, outputs, metrics, sample_class, timeout, reference_free=False, progress_path=None, previous_rows=None):
    rows = []
    previous = {(r['id'], r['metric']): r for r in (previous_rows or []) if r['status'] == 'scored'}
    for q in questions:
        output = outputs.get(q['id'])
        for name in METRICS:
            fixed = preset(q, output, name)
            prior = previous.get((q['id'], name))
            if prior:
                fixed = (prior['score'], 'scored')
            if reference_free and name == 'context_recall' and output is not None:
                fixed = (None, 'excluded_pending_researcher_reference_review')
            if fixed is not None:
                value, status = fixed
            else:
                sample = sample_class(user_input=q['question'], response=output['response'],
                                      retrieved_contexts=[c['text'] for c in output['contexts']],
                                      reference=None if reference_free else q['reference'])
                try:
                    value = float(await metrics[name].single_turn_ascore(sample, timeout=timeout))
                    if not math.isfinite(value):
                        value, status = None, 'not_assessable_or_no_valid_score'
                    else:
                        status = 'scored'
                except Exception as exc:
                    # Do not persist exception messages: provider responses can contain secrets.
                    value, status = None, 'error_' + type(exc).__name__
            rows.append({'id': q['id'], 'answerable': q['answerable'], 'metric': name, 'score': value, 'status': status})
            if progress_path is not None:
                dump(progress_path, rows)
                print(q['id'], name, status, value, flush=True)
    return rows


def summarize(rows, include_strata=True):
    result = {}
    for name in METRICS:
        chosen = [r for r in rows if r['metric'] == name]
        values = [r['score'] for r in chosen if r['score'] is not None]
        counts = {}
        for r in chosen:
            counts[r['status']] = counts.get(r['status'], 0) + 1
        result[name] = {'mean': sum(values) / len(values) if values else None,
                        'scored_count': len(values), 'total_cases': len(chosen), 'status_counts': counts}
    if include_strata:
        result['by_answerability'] = {
            'answerable': summarize([r for r in rows if r['answerable']], False),
            'unanswerable': summarize([r for r in rows if not r['answerable']], False),
        }
    return result


def build_metrics():
    from dotenv import load_dotenv
    load_dotenv()
    local_embeddings = os.getenv('EVAL_EMBEDDING_PROVIDER') == 'clara-local'
    required = ['EVAL_LLM_MODEL', 'EVAL_LLM_API_KEY', 'EVAL_EMBEDDING_MODEL']
    if not local_embeddings:
        required.append('EVAL_EMBEDDING_API_KEY')
    require(all(os.getenv(k, '').strip() for k in required), 'Fill evaluator and embedding model settings in .env first')
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import LLMContextPrecisionWithoutReference, LLMContextRecall, Faithfulness, ResponseRelevancy
    from ragas.run_config import RunConfig
    extra = {}
    if 'api.groq.com' in os.getenv('EVAL_LLM_BASE_URL', ''):
        from quota_client import QuotaClient
        extra['http_async_client'] = QuotaClient(timeout=90)
    llm = LangchainLLMWrapper(ChatOpenAI(model=os.environ['EVAL_LLM_MODEL'], api_key=os.environ['EVAL_LLM_API_KEY'],
        base_url=os.getenv('EVAL_LLM_BASE_URL') or None, temperature=0, max_retries=1, timeout=90, **extra),
        bypass_n=True, bypass_temperature=True)
    if local_embeddings:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from local_embeddings import embed
        from langchain_core.embeddings import Embeddings
        class LocalEmbeddings(Embeddings):
            def embed_documents(self, texts):
                return embed(texts, os.environ['EVAL_EMBEDDING_MODEL'])
            def embed_query(self, text):
                return self.embed_documents([text])[0]
        embeddings = LangchainEmbeddingsWrapper(LocalEmbeddings())
    else:
        embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=os.environ['EVAL_EMBEDDING_MODEL'],
            api_key=os.environ['EVAL_EMBEDDING_API_KEY'], base_url=os.getenv('EVAL_EMBEDDING_BASE_URL') or None,
            max_retries=1, request_timeout=90, check_embedding_ctx_length=False))
    metrics = dict(zip(METRICS, [LLMContextPrecisionWithoutReference(llm=llm), LLMContextRecall(llm=llm),
                      Faithfulness(llm=llm), ResponseRelevancy(llm=llm, embeddings=embeddings, strictness=3)]))
    for m in metrics.values():
        m.init(RunConfig(timeout=180, max_retries=1, max_workers=1))
    return metrics


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def write_report(folder, questions, outputs, rows, summary):
    escape = lambda s: html.escape(str(s))
    parts = ['<!doctype html><meta charset="utf-8"><title>CLARA evaluation review</title>',
             '<style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:20px}pre{white-space:pre-wrap}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px}article{border-top:2px solid #345;margin-top:30px}</style>',
             '<h1>CLARA guideline evaluation</h1><p>Automated evaluation; these scores do not establish clinical correctness.</p>',
             '<h2>Summary and denominators</h2><pre>' + escape(json.dumps(summary, indent=2)) + '</pre>']
    for q in questions:
        o = outputs.get(q['id'], {})
        parts.extend(['<article><h2>' + escape(q['id']) + '</h2><p>' + escape(q['question']) + '</p>',
                      '<h3>CLARA response</h3><pre>' + escape(o.get('response', '[missing output]')) + '</pre>',
                      '<h3>' + ('Source-checked researcher reference' if q.get('reference_source_checked') else 'AI draft reference — awaiting researcher source review') + '</h3><pre>' + escape(q['reference']) + '</pre>',
                      '<h3>Reference evidence</h3><pre>' + escape(json.dumps(q.get('reference_evidence', []), indent=2)) + '</pre>',
                      '<table><tr><th>Metric</th><th>Score</th><th>Status</th></tr>'])
        for r in rows:
            if r['id'] == q['id']:
                parts.append('<tr>' + ''.join('<td>' + escape(r[k] if r[k] is not None else '—') + '</td>' for k in ('metric', 'score', 'status')) + '</tr>')
        parts.append('</table><h3>Context supplied to CLARA, in order</h3>')
        for c in o.get('contexts', []):
            parts.append('<h4>' + escape(f"{c['rank']}. {c['pdf_file']} — PDF page {c['page']}") + '</h4><pre>' + escape(c['text']) + '</pre>')
        parts.append('</article>')
    (folder / 'review.html').write_text('\n'.join(parts), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'score'])
    parser.add_argument('--questions', required=True)
    parser.add_argument('--outputs', required=True)
    parser.add_argument('--heldout', help='Optional separate question file: checks exact text/id overlap')
    parser.add_argument('--config', default='pipeline_config.json')
    parser.add_argument('--guidelines', default='guidelines')
    parser.add_argument('--results', default='results')
    parser.add_argument('--run-name', default='baseline')
    parser.add_argument('--allow-final', action='store_true', help='Explicitly run locked final evaluation')
    parser.add_argument('--allow-demo', action='store_true', help='Toy data only; never thesis results')
    parser.add_argument('--reference-free', action='store_true', help='Development only: omit Context Recall until researcher references are checked')
    parser.add_argument('--resume', help='Completed prior run: reuse successful scores only after verifying input/model/protocol identity')
    args = parser.parse_args()
    questions, outputs = read_rows(args.questions), read_rows(args.outputs)
    _, omap = validate(questions, outputs, read_rows(args.heldout) if args.heldout else None, args.reference_free)
    print(f'Validated {len(questions)} questions, {len(outputs)} outputs; {len(questions)-len(outputs)} missing outputs.')
    if args.command == 'check':
        return
    require(args.allow_final or questions[0]['split'] != 'final', 'Final set is locked; use --allow-final only for final evaluation')
    demo = any(q.get('demonstration_only') for q in questions)
    require(not demo or args.allow_demo, 'Toy examples are not thesis cases; scoring requires --allow-demo')
    require(all(ch.isalnum() or ch in '-_' for ch in args.run_name) and bool(args.run_name), 'Use letters, digits, - or _ for run name')
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    required_config = ('clara_version', 'generator_model', 'retrieval_embedding_model', 'chunk_size', 'chunk_overlap', 'top_k', 'prompt_sha256')
    require(all(k in config and config[k] not in ('', None, 'FILL_ME') for k in required_config), 'Complete all pipeline_config fields first')
    # Allowlist only: never copy arbitrary config values or environment secrets into reports.
    config = {k: config[k] for k in required_config}
    pdfs = sorted(Path(args.guidelines).rglob('*.pdf'))
    require(bool(pdfs) or demo, 'Place the exact ingested guideline PDFs in guidelines/')
    corpus = {str(p.relative_to(args.guidelines)): digest(p) for p in pdfs}
    if not demo:
        for q in questions:
            for c in q.get('reference_evidence', []) + omap.get(q['id'], {}).get('contexts', []):
                require(c['pdf_file'] in corpus, f"{q['id']}: PDF not found in corpus: {c['pdf_file']}")
    metrics = build_metrics()
    from ragas import SingleTurnSample
    folder = Path(args.results) / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + args.run_name)
    folder.mkdir(parents=True, exist_ok=False)
    versions = {p: importlib.metadata.version(p) for p in ['ragas', 'langchain-openai', 'python-dotenv']}
    manifest = {'started_utc': datetime.now(timezone.utc).isoformat(), 'demonstration_only': demo,
                'split': questions[0]['split'], 'questions_sha256': digest(args.questions),
                'outputs_sha256': digest(args.outputs), 'pipeline': config, 'corpus_sha256': corpus,
                'package_versions': versions, 'metrics': list(METRICS), 'answer_relevancy_strictness': 3,
                'evaluator_model': os.environ['EVAL_LLM_MODEL'], 'embedding_model': os.environ['EVAL_EMBEDDING_MODEL'],
                'provider_note': 'Endpoints/keys not stored. Record provider names separately without secrets.',
                'precision_variant': 'LLMContextPrecisionWithoutReference', 'timeout_seconds_per_metric': 600,
                'reference_free_development': args.reference_free,
                'completion_policy': 'independent n=1 requests; Ragas strictness preserved',
                'requested_temperature': 0,
                'embedding_provider': os.getenv('EVAL_EMBEDDING_PROVIDER', 'openai-compatible')}
    dump(folder / 'manifest.json', manifest)
    previous_rows = []
    if args.resume:
        old_folder = Path(args.resume)
        old = json.loads((old_folder / 'manifest.json').read_text(encoding='utf-8'))
        for field in ['questions_sha256', 'outputs_sha256', 'pipeline', 'corpus_sha256', 'evaluator_model',
                      'embedding_model', 'embedding_provider', 'reference_free_development',
                      'precision_variant', 'answer_relevancy_strictness', 'completion_policy', 'requested_temperature', 'package_versions']:
            require(old.get(field) == manifest.get(field), f'Cannot resume: changed {field}')
        require('completed_utc' in old, 'Resume requires a completed report with explicit scores/errors')
        with (old_folder / 'scores.csv').open(encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                if row['status'] == 'scored':
                    row['score'] = float(row['score'])
                    require(math.isfinite(row['score']), 'Invalid cached score')
                    row['answerable'] = row['answerable'] == 'True'
                    previous_rows.append(row)
        manifest['resumed_from'] = str(old_folder.resolve())
        manifest['reused_successful_scores'] = len(previous_rows)
        dump(folder / 'manifest.json', manifest)
    # Frozen inputs are evaluator-only: never feed reference answers to CLARA.
    dump(folder / 'questions.json', questions)
    dump(folder / 'outputs.json', outputs)
    rows = asyncio.run(score_rows(questions, omap, metrics, SingleTurnSample, 600, args.reference_free, folder / 'progress.json', previous_rows))
    with (folder / 'scores.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'answerable', 'metric', 'score', 'status'])
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize(rows)
    dump(folder / 'summary.json', summary)
    manifest['completed_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['completed_with_metric_errors'] = any(r['status'].startswith('error_') for r in rows)
    dump(folder / 'manifest.json', manifest)
    write_report(folder, questions, omap, rows, summary)
    print(f'Results saved to {folder.resolve()}. Open review.html; inspect errors and denominators before reporting means.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
