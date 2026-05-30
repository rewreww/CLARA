"""
CLARA RAG Retriever — v2
Returns structured dicts with page numbers and metadata.
Backward-compatible: retrieve_guidelines() still works for llm_client.py.
"""

import os
import requests
import chromadb

CHROMA_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
OLLAMA_URL    = "http://localhost:11434"
EMBED_MODEL   = "nomic-embed-text"
COLLECTION    = "clara_guidelines"
TOP_K         = 8
MIN_RELEVANCE = 40.0


def get_embedding(text: str) -> list[float]:
    r = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embedding"]


def retrieve(
    query: str,
    diagnosis_hint: str = None,
    top_k: int = TOP_K,
    only_recommendations: bool = False,
) -> list[dict]:
    """
    Returns list of dicts:
      source, page, section_heading, diagnosis_category,
      text, relevance, is_philippine, is_recommendation
    """
    if not os.path.exists(CHROMA_DIR):
        return []

    try:
        client     = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(COLLECTION)
    except Exception:
        return []

    # Build optional where filter
    where = None
    if diagnosis_hint and only_recommendations:
        where = {"$and": [
            {"diagnosis_category": {"$eq": diagnosis_hint}},
            {"is_recommendation":  {"$eq": True}},
        ]}
    elif diagnosis_hint:
        where = {"diagnosis_category": {"$eq": diagnosis_hint}}
    elif only_recommendations:
        where = {"is_recommendation": {"$eq": True}}

    try:
        query_emb = get_embedding(query)
        kwargs = dict(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where
        results = collection.query(**kwargs)
    except Exception:
        # Fallback: query without filter (handles old un-re-ingested data)
        try:
            results = collection.query(
                query_embeddings=[get_embedding(query)],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

    docs  = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    matched = []
    for doc, meta, dist in zip(docs, metas, dists):
        relevance = round((1 - dist) * 100, 1)
        if relevance >= MIN_RELEVANCE:
            matched.append({
                "source":             meta.get("source", "unknown"),
                "page":               meta.get("page"),
                "section_heading":    meta.get("section_heading", ""),
                "diagnosis_category": meta.get("diagnosis_category", "general"),
                "text":               doc.strip(),
                "relevance":          relevance,
                "is_philippine":      meta.get("country") == "philippines",
                "is_recommendation":  meta.get("is_recommendation", False),
            })

    # Philippine chunks first, then by descending relevance
    matched.sort(key=lambda x: (0 if x["is_philippine"] else 1, -x["relevance"]))
    return matched


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