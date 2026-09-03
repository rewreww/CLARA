import os
from functools import lru_cache

import requests


EMBEDDING_PROVIDER = os.getenv("RAG_EMBEDDING_PROVIDER", "sentence-transformers").strip().lower()
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").strip()


@lru_cache(maxsize=1)
def _sentence_transformer():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. Run: "
            "pip install -r ai-services/requirements.txt"
        ) from exc

    return SentenceTransformer(EMBED_MODEL)


def get_embedding(text: str) -> list[float]:
    if EMBEDDING_PROVIDER in {"sentence-transformers", "sentence_transformers", "hf", "huggingface"}:
        embedding = _sentence_transformer().encode(text, normalize_embeddings=True)
        return embedding.tolist()

    if EMBEDDING_PROVIDER == "ollama":
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    raise RuntimeError(
        f"Unsupported RAG_EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER}. "
        "Use 'sentence-transformers' or 'ollama'."
    )
