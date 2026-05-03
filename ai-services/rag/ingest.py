"""
CLARA RAG Ingestion Script
Run this once every time you add a new guideline PDF.
It reads all PDFs from the guidelines folder, splits them into chunks,
generates embeddings using Ollama, and stores them in ChromaDB.
"""

import os
import sys
import fitz  # pymupdf
import chromadb
import requests

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDELINES_DIR = os.path.join(BASE_DIR, "guidelines")
CHROMA_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_URL     = "http://localhost:11434"
EMBED_MODEL    = "nomic-embed-text"
COLLECTION     = "clara_guidelines"
CHUNK_SIZE     = 400   # words per chunk
CHUNK_OVERLAP  = 80    # words of overlap between chunks so context is not lost


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file using pymupdf."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text.strip())
    doc.close()
    print(f"  Extracted {len(pages)} pages from {os.path.basename(pdf_path)}")
    return "\n\n".join(pages)


def split_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping word-based chunks.
    Overlap means the last N words of one chunk appear at the start
    of the next — this prevents a sentence being cut in half at a boundary.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def get_embedding(text: str) -> list[float]:
    """
    Call Ollama's embedding endpoint to convert text into a vector.
    This is what allows semantic search — similar meaning = similar vector.
    """
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60
    )
    response.raise_for_status()
    return response.json()["embedding"]


def ingest():
    # ── Check guidelines folder ────────────────────────────────────────────────
    if not os.path.exists(GUIDELINES_DIR):
        print(f"ERROR: Guidelines folder not found at {GUIDELINES_DIR}")
        sys.exit(1)

    pdf_files = [f for f in os.listdir(GUIDELINES_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"ERROR: No PDF files found in {GUIDELINES_DIR}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF(s): {', '.join(pdf_files)}\n")

    # ── Connect to ChromaDB ───────────────────────────────────────────────────
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection so re-running ingest is always clean
    try:
        client.delete_collection(COLLECTION)
        print("Cleared existing collection.\n")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"}  # cosine similarity for medical text
    )

    # ── Process each PDF ──────────────────────────────────────────────────────
    total_chunks = 0

    for pdf_file in pdf_files:
        pdf_path = os.path.join(GUIDELINES_DIR, pdf_file)
        source_name = os.path.splitext(pdf_file)[0]
        print(f"Processing: {pdf_file}")

        # Extract text
        full_text = extract_text_from_pdf(pdf_path)
        if not full_text.strip():
            print(f"  WARNING: No text extracted — PDF may be scanned. Skipping.\n")
            continue

        # Split into chunks
        chunks = split_into_chunks(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
        print(f"  Split into {len(chunks)} chunks")

        # Embed and store each chunk
        ids        = []
        embeddings = []
        documents  = []
        metadatas  = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{source_name}_chunk_{i}"
            print(f"  Embedding chunk {i+1}/{len(chunks)}...", end="\r")

            try:
                embedding = get_embedding(chunk)
            except Exception as e:
                print(f"\n  WARNING: Failed to embed chunk {i}: {e}")
                continue

            ids.append(chunk_id)
            embeddings.append(embedding)
            documents.append(chunk)
            metadatas.append({
                "source": source_name,
                "chunk_index": i,
                "pdf_file": pdf_file
            })

        # Store batch in ChromaDB
        if ids:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            total_chunks += len(ids)
            print(f"\n  Stored {len(ids)} chunks from {pdf_file}\n")

    print(f"Ingestion complete. Total chunks stored: {total_chunks}")
    print(f"ChromaDB location: {CHROMA_DIR}")


if __name__ == "__main__":
    ingest()