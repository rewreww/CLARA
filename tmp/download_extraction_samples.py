"""Download a small, version-pinned public synthetic evaluation set; no local patient data is uploaded."""
import concurrent.futures, hashlib, json, pathlib, urllib.parse, urllib.request

ROOT = pathlib.Path('output/research/extraction-samples')
datasets = [
    ('australian', 'RootCauseAnalytics/synthetic-australian-medical-documents-sample', 'CC-BY-NC-4.0'),
    ('recognition', 'morzel85/synthetic-medical-document-recognition-benchmark', 'CC-BY-4.0'),
]
jobs = []
for short, repo, license_id in datasets:
    meta = json.loads((ROOT / f'{short}-repository-metadata.json').read_text())
    for item in meta['siblings']:
        name = item['rfilename']
        if short == 'australian':
            selected = name in {'README.md', 'ground_truth.csv', 'ground_truth.jsonl', 'bboxes.jsonl', 'manifest.json', 'splits.json'} or (name.endswith('.pdf') and any(t in name for t in ['discharge_summary', 'pathology_report']))
        else:
            prefix = 'synthetic_Adam_Hirthe_1ce276e5'
            selected = name in {'README.md', 'data/manifest.json', f'data/fhir/patients/{prefix}.json'} or name in {f'data/pdf/{prefix}_{kind}_type_1_ver_1.pdf' for kind in ['diagnostic', 'notes', 'report']} or name == f'data/pdf/{prefix}_diagnostic_type_1_ver_1_dpi_300_clear_2p_img.pdf'
        if selected:
            url = f'https://huggingface.co/datasets/{repo}/resolve/{meta["sha"]}/{urllib.parse.quote(name)}'
            jobs.append((short, repo, license_id, name, meta['sha'], url))

def download(job):
    short, repo, license_id, name, commit, url = job
    dest = ROOT / short / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read()
    if name.endswith('.pdf') and not content.startswith(b'%PDF'):
        raise ValueError(f'Not a PDF: {name}')
    dest.write_bytes(content)
    return {'dataset': repo, 'commit': commit, 'license': license_id, 'source_url': url, 'local_path': str(dest), 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    rows = list(executor.map(download, jobs))
(ROOT / 'download-manifest.json').write_text(json.dumps(rows, indent=2))
print(json.dumps({'downloaded_files': len(rows), 'pdf_files': sum(r['local_path'].endswith('.pdf') for r in rows), 'total_bytes': sum(r['bytes'] for r in rows), 'manifest': str(ROOT / 'download-manifest.json')}))
