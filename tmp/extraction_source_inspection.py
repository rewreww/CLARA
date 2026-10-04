import collections, hashlib, json, pathlib, urllib.request
from pypdf import PdfReader

out = pathlib.Path('output/research/extraction-samples')
out.mkdir(parents=True, exist_ok=True)
rows = []
for path in sorted(pathlib.Path(r'C:\Users\acer-\Desktop\Patients').rglob('*.pdf')):
    reader = PdfReader(path)
    texts = [page.extract_text() or '' for page in reader.pages]
    rows.append({'path': str(path.relative_to(pathlib.Path(r'C:\Users\acer-\Desktop\Patients'))), 'pages': len(texts), 'text_characters': [len(t.strip()) for t in texts], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
pathlib.Path('tmp/local-record-format-profile.json').write_text(json.dumps(rows, indent=2))
print(json.dumps({'pdf_files': len(rows), 'unique_pdf_hashes': len({r['sha256'] for r in rows}), 'pages': sum(r['pages'] for r in rows), 'empty_text_pages': sum(n == 0 for r in rows for n in r['text_characters']), 'categories': dict(collections.Counter('discharge' if 'discharge' in r['path'].lower() else 'laboratory' for r in rows))}))
for short, repo in [('australian', 'RootCauseAnalytics/synthetic-australian-medical-documents-sample'), ('recognition', 'morzel85/synthetic-medical-document-recognition-benchmark')]:
    url = f'https://huggingface.co/api/datasets/{repo}'
    with urllib.request.urlopen(url, timeout=45) as response:
        data = json.load(response)
    (out / f'{short}-repository-metadata.json').write_text(json.dumps(data, indent=2))
    print(json.dumps({'dataset': short, 'commit': data.get('sha'), 'files': len(data.get('siblings', [])), 'examples': [f['rfilename'] for f in data.get('siblings', [])][:15]}))
