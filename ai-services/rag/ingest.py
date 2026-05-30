"""
CLARA RAG Ingestion Script — v2
Improvements: page numbers, paragraph-aware chunking,
diagnosis category tagging, recommendation detection.
Re-run this whenever you add a new CPG PDF.
"""

import os
import re
import sys
import fitz  # pymupdf
import chromadb
import requests

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDELINES_DIR = os.path.join(BASE_DIR, "guidelines")
CHROMA_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

OLLAMA_URL    = "http://localhost:11434"
EMBED_MODEL   = "nomic-embed-text"
COLLECTION    = "clara_guidelines"
CHUNK_SIZE    = 350
CHUNK_OVERLAP = 60

_PH_KEYWORDS = [
    "philippine", "philippines", "pilipinas",
    "psh", "phsih", "pccp", "psc",
    "philippine society", "philippine heart",
    "philippine college of cardiology",
    "dept of health", "department of health",
    "doh philippines",
]

DIAGNOSIS_CATEGORIES = {
    "heart_failure":  [
        "heart failure", "hfref", "hfpef", "hfmref",
        "systolic dysfunction", "diastolic dysfunction",
        "lvef", "cardiac failure", "chf", "reduced ejection",
        "preserved ejection",
    ],
    "hypertension": [
        "hypertension", "htn", "high blood pressure",
        "antihypertensive", "systolic pressure", "diastolic pressure",
        "blood pressure control", "hypertensive",
    ],
    "dyslipidemia": [
        "dyslipidemia", "cholesterol", "ldl-c", "hdl-c",
        "triglyceride", "statin", "lipid-lowering", "hyperlipidemia",
        "lipid management", "cardiovascular risk reduction",
    ],
    "atrial_fibrillation": [
        "atrial fibrillation", "atrial flutter", " af ",
        "afib", "anticoagulation", "rate control", "rhythm control",
        "cardioversion", "stroke prevention",
    ],
    "coronary_artery_disease": [
        "coronary artery disease", "cad", "acute coronary",
        "unstable angina", "myocardial infarction", "acs",
        "nstemi", "stemi", "revascularization", "percutaneous coronary",
    ],
    "arrhythmia": [
        "arrhythmia", "bradycardia", "tachycardia",
        "ventricular tachycardia", "ventricular fibrillation",
        "icd", "pacemaker", "ablation",
    ],
    "valvular": [
        "valvular", "mitral valve", "aortic valve", "tricuspid",
        "stenosis", "regurgitation", "valve replacement",
    ],
}

_RECOMMENDATION_RE = re.compile(
    r"class\s+i|class\s+ii|class\s+iii"
    r"|level\s+of\s+evidence|loe\s*:"
    r"|is\s+recommended|are\s+recommended"
    r"|should\s+be\s+(?:given|used|prescribed|considered|started)"
    r"|is\s+indicated|is\s+contraindicated"
    r"|strong\s+recommendation|conditional\s+recommendation"
    r"|grade\s+[abc1-9]|evidence\s+[abc]",
    re.IGNORECASE,
)


def detect_country(pdf_file: str, full_text: str) -> str:
    combined = (pdf_file + " " + full_text[:3000] + full_text[-1000:]).lower()
    return "philippines" if any(kw in combined for kw in _PH_KEYWORDS) else "international"


def detect_diagnosis_category(text: str) -> str:
    t = text.lower()
    scores = {cat: sum(1 for kw in kws if kw in t)
              for cat, kws in DIAGNOSIS_CATEGORIES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def detect_section_heading(text: str) -> str:
    for line in text[:250].split("\n"):
        line = line.strip()
        if 5 < len(line) < 100 and line == line.upper() and not line.isdigit():
            return line[:80]
        if re.match(r"^\d+[\.\d]*\s+[A-Z]", line) and len(line) < 100:
            return line[:80]
    return ""


def is_recommendation_chunk(text: str) -> bool:
    return bool(_RECOMMENDATION_RE.search(text))


def extract_pages(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    doc.close()
    print(f"  Extracted {len(pages)} pages from {os.path.basename(pdf_path)}")
    return pages


def split_into_chunks(pages: list[dict], chunk_size: int, overlap: int) -> list[dict]:
    """Paragraph-aware chunking that preserves page numbers."""
    paragraphs = []
    for page_info in pages:
        for para in re.split(r"\n{2,}", page_info["text"]):
            para = para.strip()
            if len(para.split()) >= 6:
                paragraphs.append({"page": page_info["page"], "text": para})

    chunks  = []
    current = []
    current_words = 0

    def flush(paras):
        if not paras:
            return
        text = " ".join(p["text"] for p in paras)
        chunks.append({
            "text":             text,
            "page":             paras[0]["page"],
            "is_recommendation": is_recommendation_chunk(text),
            "section_heading":  detect_section_heading(text),
        })

    for para in paragraphs:
        wc = len(para["text"].split())
        if current_words + wc > chunk_size and current:
            flush(current)
            # carry overlap into next chunk
            overlap_buf, overlap_wc = [], 0
            for p in reversed(current):
                pw = len(p["text"].split())
                if overlap_wc + pw <= overlap:
                    overlap_buf.insert(0, p)
                    overlap_wc += pw
                else:
                    break
            current       = overlap_buf + [para]
            current_words = sum(len(p["text"].split()) for p in current)
        else:
            current.append(para)
            current_words += wc

    flush(current)
    return chunks


def get_embedding(text: str) -> list[float]:
    r = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embedding"]


def ingest():
    if not os.path.exists(GUIDELINES_DIR):
        print(f"ERROR: Guidelines folder not found at {GUIDELINES_DIR}")
        sys.exit(1)

    pdf_files = [f for f in os.listdir(GUIDELINES_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"ERROR: No PDF files found in {GUIDELINES_DIR}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF(s): {', '.join(pdf_files)}\n")

    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection(COLLECTION)
        print("Cleared existing collection.\n")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    total_chunks = 0

    for pdf_file in pdf_files:
        pdf_path    = os.path.join(GUIDELINES_DIR, pdf_file)
        source_name = os.path.splitext(pdf_file)[0]
        print(f"Processing: {pdf_file}")

        pages = extract_pages(pdf_path)
        if not pages:
            print(f"  WARNING: No text extracted — PDF may be scanned. Skipping.\n")
            continue

        full_text = " ".join(p["text"] for p in pages)
        country   = detect_country(pdf_file, full_text)
        print(f"  Country tag: {country}")

        chunks = split_into_chunks(pages, CHUNK_SIZE, CHUNK_OVERLAP)
        print(f"  Split into {len(chunks)} paragraph-aware chunks")

        ids = []; embeddings = []; documents = []; metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{source_name}_chunk_{i}"
            diag_cat = detect_diagnosis_category(chunk["text"])
            print(f"  Embedding chunk {i+1}/{len(chunks)} (p.{chunk['page']}, {diag_cat})...", end="\r")

            try:
                emb = get_embedding(chunk["text"])
            except Exception as e:
                print(f"\n  WARNING: Failed to embed chunk {i}: {e}")
                continue

            ids.append(chunk_id)
            embeddings.append(emb)
            documents.append(chunk["text"])
            metadatas.append({
                "source":             source_name,
                "chunk_index":        i,
                "pdf_file":           pdf_file,
                "country":            country,
                "page":               chunk["page"],
                "section_heading":    chunk["section_heading"],
                "diagnosis_category": diag_cat,
                "is_recommendation":  chunk["is_recommendation"],
            })

        if ids:
            collection.add(ids=ids, embeddings=embeddings,
                           documents=documents, metadatas=metadatas)
            total_chunks += len(ids)
            print(f"\n  Stored {len(ids)} chunks from {pdf_file}\n")

    print(f"\nIngestion complete. Total chunks stored: {total_chunks}")
    print(f"ChromaDB location: {CHROMA_DIR}")


if __name__ == "__main__":
    ingest()