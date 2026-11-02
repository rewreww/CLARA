"""Map captured text to physical pages without altering or re-retrieving it."""
import re


def page_passages(chunk, document, pages):
    text = str(chunk['text']).strip()
    tokens = list(re.finditer(r'\S+', text))
    if not tokens:
        raise ValueError('Empty captured passage')
    normalized = ' '.join(t.group() for t in tokens)
    source_tokens = []
    source_pages = []
    for page in pages:
        words = page['text'].split()
        source_tokens.extend(words)
        source_pages.extend([page['page']] * len(words))
    source = ' '.join(source_tokens)
    matches = list(re.finditer(r'(?<!\S)' + re.escape(normalized) + r'(?!\S)', source))
    if len(matches) != 1:
        raise ValueError('Passage mapping is absent or ambiguous; do not invent a page number')
    offset = len(source[:matches[0].start()].split())
    assigned = source_pages[offset:offset + len(tokens)]
    result = []
    begin = 0
    for i in range(1, len(tokens) + 1):
        if i == len(tokens) or assigned[i] != assigned[begin]:
            start = tokens[begin].start()
            end = tokens[i].start() if i < len(tokens) else len(text)
            result.append({'document_id': document['document_id'], 'pdf_file': document['pdf_file'],
                           'page': assigned[begin], 'text': text[start:end],
                           'source_type': 'guideline', 'chunk_id': chunk.get('chunk_id'),
                           'captured_text_start': start, 'captured_text_end': end})
            begin = i
    assert ''.join(p['text'] for p in result) == text
    return result
