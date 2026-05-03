import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

CLEANER_URL = "http://localhost:8000"   # your existing FastAPI
OLLAMA_URL  = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:1b"

SYSTEM_PROMPT = """You are CLARA, a clinical AI assistant specialized in cardiovascular case assessment.

You are given structured patient data including lab results and discharge summaries.
Your job is to help doctors interpret findings, identify trends, and flag concerns.

Rules you must follow:
- Always cite specific lab values when making a statement
- Flag any value outside its reference range explicitly
- If data is missing or unclear, say so — do not guess
- Do not prescribe or give final diagnoses — support the doctor's judgment
- Be concise. Doctors are busy."""


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    include_discharge: Optional[bool] = False


class ChatResponse(BaseModel):
    patient_id: str
    response: str
    context_used: list[str]


def fetch_lab_results(patient_id: str, lab_type: str) -> dict:
    """Call your existing cleaner service to get structured lab results."""
    try:
        r = requests.post(
            f"{CLEANER_URL}/{lab_type}-results",
            json={"patient": patient_id, "labs": lab_type},
            timeout=30
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return {}


def build_patient_context(patient_id: str, include_discharge: bool) -> tuple[str, list[str]]:
    """Gather all available patient data and format it as context for the LLM."""
    context_parts = []
    sources_used = []

    # Fetch all three lab types
    for lab_type in ["chemistry", "hematology", "microscopy"]:
        data = fetch_lab_results(patient_id, lab_type)
        results = data.get("results", [])
        if results:
            sources_used.append(lab_type)
            lines = []
            for result in results:
                low  = result.get("reference_low")
                high = result.get("reference_high")
                ref  = f" (ref: {low}–{high})" if low and high else \
                       f" (ref: <{high})"       if high          else ""
                flag = ""
                if isinstance(result["value"], (int, float)):
                    if high and result["value"] > high: flag = " *** HIGH ***"
                    if low  and result["value"] < low:  flag = " *** LOW ***"
                lines.append(
                    f"  {result['test_name']}: {result['value']} {result['unit']}{ref}{flag}".strip()
                )
            context_parts.append(f"[{lab_type.upper()} RESULTS]\n" + "\n".join(lines))

    # Optionally pull discharge text via categorize endpoint
    if include_discharge:
        try:
            resp = requests.post(
                f"{CLEANER_URL}/categorize",
                json={"patient": patient_id, "labs": "labs"},
                timeout=30
            )
            resp.raise_for_status()
            discharge = resp.json().get("discharge", "").strip()
            if discharge:
                context_parts.append(f"[DISCHARGE SUMMARY]\n{discharge[:2000]}")
                sources_used.append("discharge")
        except requests.RequestException:
            pass

    full_context = "\n\n".join(context_parts) if context_parts \
                   else "No patient data available."
    return full_context, sources_used


def ask_ollama(system: str, user_message: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{system}\n\n{user_message}",
        "stream": False
    }
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["response"]
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}")
    except (KeyError, ValueError):
        raise HTTPException(status_code=502, detail="Unexpected response from Ollama")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    # 1. Gather patient data
    context, sources = build_patient_context(
        request.patient_id,
        request.include_discharge
    )

    # 2. Build the full user message with context injected
    user_message = f"""Patient ID: {request.patient_id}

--- PATIENT DATA ---
{context}
--- END PATIENT DATA ---

Doctor's question: {request.message}"""

    # 3. Ask Ollama
    answer = ask_ollama(SYSTEM_PROMPT, user_message)

    return ChatResponse(
        patient_id=request.patient_id,
        response=answer,
        context_used=sources
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "CLARA LLM"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)