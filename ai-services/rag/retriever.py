"""
CLARA RAG Retriever
Called by llm_client.py to fetch relevant guideline sections
based on the doctor's question.
"""

import os
import requests
import chromadb

# ── Paths ──────────────────────────────────────────────────────────────────────
CHROMA_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
COLLECTION  = "clara_guidelines"
TOP_K       = 3   # number of guideline chunks to retrieve per query


def get_embedding(text: str) -> list[float]:
    """Convert a query string into a vector using Ollama."""
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60
    )
    response.raise_for_status()
    return response.json()["embedding"]


def retrieve_guidelines(query: str) -> str:
    """
    Given a doctor's question or clinical topic, retrieve the most
    relevant guideline chunks from ChromaDB.
    Returns a formatted string ready to be injected into the LLM prompt.
    """
    # Check ChromaDB exists — if ingest.py has never been run, warn gracefully
    if not os.path.exists(CHROMA_DIR):
        return "[GUIDELINES] No guidelines database found. Run ingest.py first."

    try:
        client     = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(COLLECTION)
    except Exception:
        return "[GUIDELINES] Guidelines database not initialised. Run ingest.py first."

    # Convert query to vector and search
    try:
        query_embedding = get_embedding(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        return f"[GUIDELINES] Retrieval error: {str(e)}"

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        return "[GUIDELINES] No relevant guideline sections found."

    # Format the retrieved chunks into a readable block
    lines = ["[RELEVANT CLINICAL GUIDELINES]"]
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        relevance = round((1 - dist) * 100, 1)  # cosine distance → % similarity
        source    = meta.get("source", "unknown")
        lines.append(f"\n--- Guideline excerpt {i+1} (source: {source}, relevance: {relevance}%) ---")
        lines.append(doc.strip())

    return "\n".join(lines)