"""Read-only PDF extraction audit. Cache by PDF hash; never opens the live index."""
import hashlib
import json
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.clara/evaluation'


def audit():
    OUT.mkdir(parents=True, exist_ok=True)
    documents = []
    for pdf in sorted((ROOT / 'ai-services/guidelines').glob('*.pdf')):
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        cache = OUT / 'extraction' / digest
        cache.mkdir(parents=True, exist_ok=True)
        target = cache / 'pages.json'
        if target.exists():
            pages = json.loads(target.read_text(encoding='utf-8'))
        else:
            with fitz.open(pdf) as doc:
                pages = []
                for number, page in enumerate(doc, 1):
                    text = page.get_text()
                    pages.append({'page': number, 'text': text, 'characters': len(text.strip()),
                                  'replacement_characters': text.count('\ufffd'),
                                  'images': len(page.get_images()), 'label': page.get_label()})
            target.write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
        row = {'pdf_file': pdf.name, 'document_id': digest, 'pages': len(pages),
               'characters': sum(p['characters'] for p in pages),
               'sparse_pages': [p['page'] for p in pages if p['characters'] < 80],
               'replacement_character_pages': [p['page'] for p in pages if p['replacement_characters']],
               'extraction': str(target), 'extractor': 'PyMuPDF ' + fitz.VersionBind}
        documents.append(row)
        print(f"{len(pages)} pages; {len(row['sparse_pages'])} sparse; {len(row['replacement_character_pages'])} with replacement characters | {pdf.name}")
    result = {'documents': documents, 'pages': sum(d['pages'] for d in documents),
              'note': 'Automated inventory, not proof of extraction or clinical correctness. Sparse pages may be covers or blank pages.'}
    (OUT / 'corpus.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result


if __name__ == '__main__':
    audit()
