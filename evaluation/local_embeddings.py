"""Use CLARA's cached local embedding model from an isolated evaluator env."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def embed(texts, model):
    cache = ROOT / '.clara/evaluation/embedding-cache'
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([model, texts], ensure_ascii=False).encode()).hexdigest()
    target = cache / (key + '.json')
    if not target.exists():
        inputs = cache / (key + '.input.json')
        inputs.write_text(json.dumps({'model': model, 'texts': texts}), encoding='utf-8')
        env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1'}
        subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), str(Path(__file__).resolve()),
                        str(inputs), str(target)], env=env, check=True, timeout=180,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return json.loads(target.read_text(encoding='utf-8'))


if __name__ == '__main__':
    from sentence_transformers import SentenceTransformer
    data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    model = SentenceTransformer(data['model'], local_files_only=True)
    vectors = model.encode(data['texts'], normalize_embeddings=True).tolist()
    Path(sys.argv[2]).write_text(json.dumps(vectors), encoding='utf-8')
