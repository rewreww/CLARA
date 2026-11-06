"""
CLARA RAG Retriever — v2
Returns structured dicts with page numbers and metadata.
Backward-compatible: retrieve_guidelines() still works for llm_client.py.
"""

import os
import re
import time
import logging
from functools import lru_cache
import chromadb

try:
    from .embeddings import EMBED_MODEL, get_embedding
    from .lexical import PassageIndex, tokens
except ImportError:
    from embeddings import EMBED_MODEL, get_embedding
    from lexical import PassageIndex, tokens

CHROMA_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
COLLECTION    = "clara_guidelines"
TOP_K         = 8
MIN_RELEVANCE = 40.0

_DIAGNOSIS_HINTS = {
    "hypertension": (
        "hypertension", "hypertensive", "high blood pressure", "blood pressure", "htn",
    ),
    "heart_failure": (
        "heart failure", "hfref", "hfpef", "cardiac failure", "congestive heart failure", "chf",
    ),
    "dyslipidemia": (
        "dyslipidemia", "cholesterol", "ldl", "hdl", "triglyceride", "hyperlipidemia",
    ),
    "atrial_fibrillation": (
        "atrial fibrillation", "afib", "atrial flutter", "anticoagulation", "cardioversion",
    ),
    "coronary_artery_disease": (
        "coronary artery", "acute coronary", "myocardial infarction", "stemi", "nstemi", "acs",
    ),
    "arrhythmia": (
        "arrhythmia", "bradycardia", "tachycardia", "pacemaker", "ventricular fibrillation",
    ),
    "valvular": (
        "valvular", "mitral", "aortic", "tricuspid", "regurgitation", "stenosis",
    ),
}

_MANAGEMENT_TERMS = (
    "procedure", "procedures", "treat", "treatment", "manage", "management",
    "medication", "therapy", "recommend", "what should", "what to do", "follow up",
    "antihypertensive", "drug", "should be used", "comorbid",
)


@lru_cache(maxsize=1)
def _passage_index(directory, collection_name, refresh_bucket):
    collection = chromadb.PersistentClient(path=directory).get_collection(collection_name)
    return PassageIndex(collection.get(include=['documents', 'metadatas']))


def infer_diagnosis_hint(query: str) -> str | None:
    """Infer a topic preference without excluding cross-condition evidence."""
    text = (query or "").lower()
    scores = {
        category: sum(term in text for term in terms)
        for category, terms in _DIAGNOSIS_HINTS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best]:
        return best
    return 'hypertension' if re.search(r'\b(bp|abpm|hbpm)\b', text) else None


def is_management_query(query: str) -> bool:
    text = (query or "").lower()
    return any(term in text for term in _MANAGEMENT_TERMS)


def retrieve(
    query: str,
    diagnosis_hint: str = None,
    top_k: int = TOP_K,
    only_recommendations: bool = False,
) -> list[dict]:
    """
    Returns list of dicts:
      source, page, section_heading, diagnosis_category,
      text, relevance (cosine similarity), retrieval_score (hybrid rank score),
      is_philippine, is_recommendation. Topic/recommendation flags are preferences.
    """
    if not os.path.exists(CHROMA_DIR):
        return []

    try:
        client     = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(COLLECTION)
    except Exception:
        return []

    # Search across the collection: heuristic category/recommendation tags must
    # not exclude relevant cross-condition passages. Fuse semantic and lexical
    # scores so terms buried past the encoder's token limit remain discoverable.
    candidates = {}
    index = None
    def add(identifier, doc, meta, lexical_score=0.0, similarity=None):
        item = candidates.setdefault(identifier, {
            'source': meta.get('source', 'unknown'), 'pdf_file': meta.get('pdf_file'),
            'chunk_id': identifier, 'page': meta.get('page'),
            'section_heading': meta.get('section_heading', ''),
            'diagnosis_category': meta.get('diagnosis_category', 'general'),
            'text': doc.strip(), 'relevance': 0.0, 'retrieval_score': 0.0,
            'is_philippine': meta.get('country') == 'philippines',
            'is_recommendation': meta.get('is_recommendation', False),
        })
        item['retrieval_score'] += .5 * lexical_score
        if similarity is not None:
            item['relevance'] = round(similarity, 1)
            item['retrieval_score'] += .5 * max(0, min(1, similarity / 100))
    try:
        index = _passage_index(CHROMA_DIR, COLLECTION, int(time.monotonic() // 300))
        lexical_matches = index.search(query)
        maximum = lexical_matches[0][1] if lexical_matches else 1
        for position, score in lexical_matches:
            data = index.records
            add(data['ids'][position], data['documents'][position], data['metadatas'][position], lexical_score=score / maximum)
    except Exception:
        logging.getLogger(__name__).exception('Guideline lexical retrieval failed')
    try:
        results = collection.query(query_embeddings=[get_embedding(query)],
            n_results=min(max(30, top_k), collection.count()),
            include=['documents', 'metadatas', 'distances'])
        for rank, (identifier, doc, meta, distance) in enumerate(zip(
                results['ids'][0], results['documents'][0], results['metadatas'][0], results['distances'][0]), 1):
            similarity = (1 - distance) * 100
            if similarity >= MIN_RELEVANCE:
                add(identifier, doc, meta, similarity=similarity)
    except Exception:
        logging.getLogger(__name__).exception('Guideline semantic retrieval failed')
    # Relevance first; local provenance and heuristic tags only break ties.
    ranking = lambda item: (
        -item['retrieval_score'], not item['is_philippine'],
        item['diagnosis_category'] != diagnosis_hint,
        only_recommendations and not item['is_recommendation'],
    )
    # Rare query concepts are important constraints, not optional keywords.
    # Without this, generic drug passages can outrank a lactation-specific one.
    if index is not None:
        data = index.records
        positions = {identifier: i for i, identifier in enumerate(data['ids'])}
        from_tokens = set(tokens(query))
        specific = {term for term in from_tokens if index.idf.get(term, 0) >= 5}
        if specific:
            for item in candidates.values():
                position = positions.get(item['chunk_id'])
                if position is not None:
                    coverage = len(specific.intersection(index.counts[position])) / len(specific)
                    item['retrieval_score'] *= .25 + .75 * coverage
    return sorted(candidates.values(), key=ranking)[:top_k]


def following_passage(chunk):
    """One contiguous indexed passage, for answers continued on the next page."""
    if not chunk.get('chunk_id'):
        return None
    index = _passage_index(CHROMA_DIR, COLLECTION, int(time.monotonic() // 300))
    data = index.records
    try:
        position = data['ids'].index(chunk['chunk_id'])
    except ValueError:
        return None
    meta = data['metadatas'][position]
    if not isinstance(meta.get('chunk_index'), int):
        return None
    for i, candidate in enumerate(data['metadatas']):
        if (candidate.get('source') == meta.get('source')
                and candidate.get('chunk_index') == meta['chunk_index'] + 1
                and 0 <= (candidate.get('page') or 0) - (meta.get('page') or 0) <= 1):
            return {**chunk, **candidate, 'chunk_id': data['ids'][i], 'text': data['documents'][i]}
    return None


def retrieve_guidelines(query: str) -> str:
    """Legacy function — kept for backward compatibility with llm_client.py."""
    chunks = retrieve(query)
    if not chunks:
        return "[GUIDELINES] No relevant guideline sections found."

    has_ph = any(c["is_philippine"] for c in chunks)
    lines  = ["[RELEVANT CLINICAL GUIDELINES]"]
    if has_ph:
        lines.append(
            "NOTE: Philippine-specific guidelines included. "
            "Prefer Philippine guidelines when they differ from international ones."
        )
    for i, c in enumerate(chunks):
        label     = "[Philippine]" if c["is_philippine"] else "[International]"
        page_info = f" p.{c['page']}" if c["page"] else ""
        lines.append(
            f"\n--- {label} excerpt {i+1} "
            f"(source: {c['source']}{page_info}, relevance: {c['relevance']}%) ---"
        )
        lines.append(c["text"])
    return "\n".join(lines)
