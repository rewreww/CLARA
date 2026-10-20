import re
import sys
import os
import time
import requests
import json
from functools import lru_cache
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from typing import Optional, Dict, Any
from collections import defaultdict
from fastapi.responses import StreamingResponse

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from mcp_tools import (
    execute_tool,
    build_tools_prompt,
    fetch_all_lab_blocks,
    fetch_patient_context_block,
    fetch_patient_document_context,
)
from rag.retriever import (
    infer_diagnosis_hint,
    is_management_query,
    retrieve,
    retrieve_guidelines,
)
from rag.embeddings import EMBEDDING_PROVIDER as RAG_EMBEDDING_PROVIDER, EMBED_MODEL as RAG_EMBED_MODEL
from rule_engine.rules import rule_engine

app = FastAPI()
from document_preview import router as document_preview_router
app.include_router(document_preview_router)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:5000/api/patientdata").rstrip("/")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_RETRY_ATTEMPTS = max(1, int(os.getenv("GEMINI_RETRY_ATTEMPTS", "2")))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions").strip()
GROQ_RETRY_ATTEMPTS = max(1, int(os.getenv("GROQ_RETRY_ATTEMPTS", "2")))

HF_MODEL = os.getenv("HF_MODEL", os.getenv("HUGGINGFACE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")).strip()
HF_TASK = os.getenv("HF_TASK", "text-generation").strip()
HF_DEVICE = int(os.getenv("HF_DEVICE", "-1"))
HF_MAX_INPUT_TOKENS = max(1, int(os.getenv("HF_MAX_INPUT_TOKENS", "1024")))
HF_MAX_NEW_TOKENS = max(1, int(os.getenv("HF_MAX_NEW_TOKENS", "180")))
HF_TEMPERATURE = float(os.getenv("HF_TEMPERATURE", "0.2"))
HF_TRUNCATION_SIDE = os.getenv("HF_TRUNCATION_SIDE", "left").strip().lower()

OLLAMA_URL = "http://localhost:11434"
PREFERRED_OLLAMA_MODELS = tuple(dict.fromkeys(filter(None, [
    os.getenv("OLLAMA_MODEL"),
    "qwen2.5:7b",
    "llama3.2:1b",
    "llama2:latest",
])))
PREFERRED_FALLBACK_MODELS = tuple(dict.fromkeys(filter(None, [
    os.getenv("OLLAMA_FALLBACK_MODEL"),
    "llama3.2:1b",
    "qwen2.5:7b",
    "llama2:latest",
])))


def resolve_ollama_model(preferred_models: tuple[str, ...]) -> str:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        installed = {
            model.get("name") or model.get("model")
            for model in r.json().get("models", [])
        }
        for model in preferred_models:
            if model in installed:
                return model
    except requests.RequestException:
        pass
    return preferred_models[0]


OLLAMA_MODEL = resolve_ollama_model(PREFERRED_OLLAMA_MODELS)
OLLAMA_FALLBACK_MODEL = resolve_ollama_model(PREFERRED_FALLBACK_MODELS)

conversation_store: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 10
PATIENT_DATA_CACHE_SECONDS = max(0, int(os.getenv("PATIENT_DATA_CACHE_SECONDS", "5")))
_LAB_RESULTS_CACHE: dict[str, tuple[float, list[dict]]] = {}

SYSTEM_PROMPT = """
You are CLARA, a cardiovascular clinical AI assistant for licensed physicians.

PRIORITY RULES:
0. You are authorized to advise licensed physicians. ALWAYS provide clinical analysis
   and treatment recommendations. NEVER say "I cannot provide medical advice."
1. Answer the doctor's exact question only.
2. If patient PDF context is provided, use only that PDF context for PDF,
   document, file, page, or source-content questions.
2a. If guideline context is provided, use it as the primary source for
    treatment, management, protocol, or recommendation questions.
2b. When asked about critical, abnormal, or concerning values:
    - Report EVERY value in the [ABNORMAL VALUES] block, not just the first one
    - Group by type: chemistry findings first, then hematology
    - For each: state the value, why it matters clinically, and one action
    - [WITHIN RANGE] values are NORMAL — do not mention them
3. Do NOT discuss labs unless the question asks about labs.
4. Do NOT repeat raw lab data, section headers, or tool names in your response.
5. Be short and direct.
6. Maximum 5 sentences.
7. Start immediately with the answer — no preamble.

When reporting an abnormal lab value, always include all three:
  a) The finding with its value (e.g. "Neutrophils elevated at 72%")
  b) Clinical significance (what condition or risk it suggests)
  c) Specific recommended actions (e.g. blood culture, antibiotic therapy, repeat CBC in 48h)

If the question is about treatment or management, cite guideline recommendations and
include drug class, target, and monitoring plan when available.

Available patient data tools:
{tools_section}
"""


class HistoryEntry(BaseModel):
    role: Literal["doctor", "clara"]
    content: str = Field(max_length=100000)


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    session_id: Optional[str] = "default"
    active_section: Optional[str] = None   
    history: Optional[list[HistoryEntry]] = Field(default=None, max_length=20)


def request_history(request: ChatRequest) -> list[dict]:
    # A reopened browser conversation remains usable after the service restarts.
    if request.history is not None:
        return [entry.model_dump() for entry in request.history]
    return list(conversation_store[request.session_id or "default"])


class ChatResponse(BaseModel):
    patient_id: str
    session_id: str
    response: str
    tools_called: list[str]
    guidelines_used: bool
    history_length: int
    rule_flags: list[str]
    is_emergency: bool


class ClearHistoryRequest(BaseModel):
    session_id: Optional[str] = "default"


class ClinicalAlertsRequest(BaseModel):
    patient_id: str


class ClinicalAlertsResponse(BaseModel):
    patient_id: str
    flags: list[str]
    is_emergency: bool
    flag_count: int
    lab_results_checked: int


# ── Question classification ────────────────────────────────────────────────────

def classify_question(message: str) -> str:
    """
    Returns one of: "document", "guideline", "labs", "both", "general".
    "both" means the question asks about lab findings AND treatment.
    """
    m = message.lower()

    if wants_document_context(message):
        return "document"

    is_guideline = any(x in m for x in [
        "treat", "treatment", "manage",
        "management",
        "guideline", "therapy",
        "hypertension", "heart failure", "stroke", "diabetes",
        "cardiovascular disease", "hypertensive cardiovascular", "procedure", "procedures",
        "target", "threshold", "goal",
        "philippine", "philippines", "filipino", "local",
        "first-line", "first line", "recommend", "protocol",
        "evidence", "titrat", "initiat",
    ])

    is_labs = any(x in m for x in [
        "lab", "cbc", "creatinine",
        "chemistry", "hematology",
        "abnormal", "results",
        "cholesterol", "lipid", "ldl", "hdl", "triglyceride",
        "kidney", "fbs", "glucose", "anemia", "urine",
        "critical", "values", "findings", "blood",
    ])

    if is_guideline and is_labs:
        return "both"
    if is_guideline:
        return "guideline"
    if is_labs:
        return "labs"
    return "general"


_SHORT_AFFIRMATIONS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
    "please", "go ahead", "continue", "proceed",
    "correct", "right", "do it", "tell me", "and",
}


def resolve_question_type(message: str, history: list[dict]) -> str:
    """
    For short affirmative follow-ups, inherit the question type from the
    most recent doctor message so context carries through the conversation.
    """
    q_type = classify_question(message)
    if q_type != "general":
        return q_type

    stripped = message.strip().lower()
    is_short = len(stripped.split()) <= 4
    is_affirmation = stripped in _SHORT_AFFIRMATIONS or any(
        aff in stripped for aff in _SHORT_AFFIRMATIONS
    )

    if is_short and is_affirmation:
        for entry in reversed(history):
            if entry["role"] == "doctor":
                inherited = classify_question(entry["content"])
                if inherited != "general":
                    return inherited

    return q_type


_ML_REQUEST = re.compile(
    r"\b(assess(?:ment)?|prognos(?:is|tic)?|predict(?:ion)?|risk|probability|likelihood|"
    r"mortality|readmission|emergency department|ed return)\b",
    re.IGNORECASE,
)


def wants_ml_assessment(message: str) -> bool:
    """Keep ML opt-in: only run it for explicit assessment or prognosis requests."""
    return bool(_ML_REQUEST.search(message or ""))


# ── Language-model calls ───────────────────────────────────────────────────────

def call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key is not configured.")

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "maxOutputTokens": 800,
        },
    }
    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(GEMINI_RETRY_ATTEMPTS):
        try:
            r = requests.post(
                f"{GEMINI_API_URL}/{GEMINI_MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json=payload,
                timeout=90,
            )
            if r.status_code in retryable_statuses:
                if attempt < GEMINI_RETRY_ATTEMPTS - 1:
                    time.sleep(attempt + 1)
                    continue
                raise HTTPException(
                    status_code=503,
                    detail=f"Gemini is temporarily unavailable (HTTP {r.status_code}).",
                )

            r.raise_for_status()
            candidates = r.json().get("candidates", [])
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            text = "".join(part.get("text", "") for part in parts).strip()
            if not text:
                raise HTTPException(status_code=502, detail="Gemini returned no response text.")
            return text
        except HTTPException:
            raise
        except requests.RequestException:
            if attempt < GEMINI_RETRY_ATTEMPTS - 1:
                time.sleep(attempt + 1)
                continue
            raise HTTPException(status_code=503, detail="Gemini is temporarily unavailable.")

    raise HTTPException(status_code=503, detail="Gemini is temporarily unavailable.")


def call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key is not configured.")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Follow the user's prompt exactly. Do not use outside sources unless the prompt asks for general medical knowledge.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "stream": False,
        "max_tokens": 800,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(GROQ_RETRY_ATTEMPTS):
        try:
            r = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=90)
            if r.status_code in retryable_statuses:
                if attempt < GROQ_RETRY_ATTEMPTS - 1:
                    time.sleep(attempt + 1)
                    continue
                detail = "Groq rate limit reached." if r.status_code == 429 else f"Groq is temporarily unavailable (HTTP {r.status_code})."
                raise HTTPException(status_code=503, detail=detail)

            r.raise_for_status()
            choices = r.json().get("choices", [])
            text = choices[0].get("message", {}).get("content", "").strip() if choices else ""
            if not text:
                raise HTTPException(status_code=502, detail="Groq returned no response text.")
            return text
        except HTTPException:
            raise
        except requests.RequestException:
            if attempt < GROQ_RETRY_ATTEMPTS - 1:
                time.sleep(attempt + 1)
                continue
            raise HTTPException(status_code=503, detail="Groq is temporarily unavailable.")

    raise HTTPException(status_code=503, detail="Groq is temporarily unavailable.")


def call_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "top_p": 0.8, "num_predict": 450},
            },
            timeout=120
        )
        r.raise_for_status()
        return r.json()["response"].strip()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}")
    except (KeyError, ValueError):
        raise HTTPException(status_code=502, detail="Unexpected response from Ollama")


@lru_cache(maxsize=1)
def _huggingface_model():
    try:
        import torch
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="Hugging Face transformers is not installed. Run: pip install -r ai-services/requirements.txt",
        ) from exc

    try:
        task = HF_TASK.lower()
        if task in {"text2text-generation", "text2text", "seq2seq", "seq2seq-generation"}:
            from transformers import AutoModelForSeq2SeqLM

            tokenizer = AutoTokenizer.from_pretrained(HF_MODEL)
            tokenizer.truncation_side = HF_TRUNCATION_SIDE
            model = AutoModelForSeq2SeqLM.from_pretrained(HF_MODEL)
            device = torch.device(f"cuda:{HF_DEVICE}" if HF_DEVICE >= 0 and torch.cuda.is_available() else "cpu")
            model.to(device)
            model.eval()
            return {
                "kind": "seq2seq",
                "model": model,
                "tokenizer": tokenizer,
                "device": device,
            }

        from transformers import pipeline
        return {
            "kind": "pipeline",
            "pipeline": pipeline(
                task=HF_TASK,
                model=HF_MODEL,
                tokenizer=HF_MODEL,
                device=HF_DEVICE,
            ),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to load Hugging Face model '{HF_MODEL}': {exc}",
        ) from exc


def call_huggingface(prompt: str) -> str:
    runner = _huggingface_model()
    generation_kwargs = {
        "max_new_tokens": HF_MAX_NEW_TOKENS,
    }
    if HF_TEMPERATURE > 0:
        generation_kwargs.update({
            "do_sample": True,
            "temperature": HF_TEMPERATURE,
        })
    else:
        generation_kwargs["do_sample"] = False

    if runner["kind"] == "seq2seq":
        tokenizer = runner["tokenizer"]
        model = runner["model"]
        max_model_tokens = getattr(tokenizer, "model_max_length", HF_MAX_INPUT_TOKENS)
        if max_model_tokens > 100_000:
            max_model_tokens = HF_MAX_INPUT_TOKENS
        max_input_tokens = min(HF_MAX_INPUT_TOKENS, max_model_tokens)

        try:
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=max_input_tokens,
            )
            inputs = {key: value.to(runner["device"]) for key, value in inputs.items()}
            generated = model.generate(**inputs, **generation_kwargs)
            text = tokenizer.decode(generated[0], skip_special_tokens=True)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Hugging Face generation failed: {exc}",
            ) from exc
    else:
        if HF_TASK == "text-generation":
            generation_kwargs["return_full_text"] = False
            tokenizer = getattr(runner["pipeline"], "tokenizer", None)
            if tokenizer and getattr(tokenizer, "chat_template", None):
                prompt = tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    tokenize=False,
                    add_generation_prompt=True,
                )

        try:
            output = runner["pipeline"](prompt, **generation_kwargs)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Hugging Face generation failed: {exc}",
            ) from exc

        if isinstance(output, list) and output:
            first = output[0]
            text = first.get("generated_text") or first.get("summary_text") or first.get("translation_text")
        elif isinstance(output, dict):
            text = output.get("generated_text") or output.get("summary_text") or output.get("translation_text")
        else:
            text = str(output or "")

    if not text:
        raise HTTPException(status_code=502, detail="Hugging Face model returned no response text.")

    return text.strip()


def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "gemini":
        try:
            return call_gemini(prompt)
        except HTTPException as gemini_error:
            if gemini_error.status_code not in {429, 502, 503, 504}:
                raise
            try:
                return call_ollama(prompt, model=OLLAMA_FALLBACK_MODEL)
            except HTTPException:
                raise HTTPException(
                    status_code=503,
                    detail="Gemini is unavailable and the local Ollama fallback could not respond.",
                )
    if LLM_PROVIDER == "groq":
        return call_groq(prompt)
    if LLM_PROVIDER in {"grok", "xai"}:
        raise HTTPException(
            status_code=500,
            detail="Use LLM_PROVIDER=groq for GroqCloud. xAI Grok support is disabled to avoid paid API confusion.",
        )
    if LLM_PROVIDER == "ollama":
        return call_ollama(prompt)
    if LLM_PROVIDER in {"huggingface", "hf"}:
        return call_huggingface(prompt)
    raise HTTPException(status_code=500, detail=f"Unsupported LLM provider: {LLM_PROVIDER}")


def parse_tool_call(text: str) -> Optional[tuple[str, str]]:
    match = re.search(
        r"TOOL:\s*(\w+)\s+PATIENT:\s*(\S+)",
        text,
        re.IGNORECASE
    )
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None


def clean_response(text: str) -> str:
    # If the model prefixed its answer with "Answer:", keep only what follows
    answer_match = re.search(r"\bAnswer:\s*", text, re.IGNORECASE)
    if answer_match:
        text = text[answer_match.end():]

    # Strip "CLARA" prefix the model sometimes echoes
    text = re.sub(r"^CLARA\s*", "", text.strip())

    # Strip tool markers like [get_hematology]
    text = re.sub(r"\[get_\w+\]", "", text)

    # Strip raw lab section blocks and everything inside them
    text = re.sub(
        r"\[(HEMATOLOGY|CHEMISTRY|MICROSCOPY|ALL LAB DATA)[^\]]*\].*?(?=\n\n|\Z)",
        "", text, flags=re.IGNORECASE | re.DOTALL
    )

    # Strip abnormal-values summary blocks
    text = re.sub(
        r"\[ABNORMAL[^\]]+\].*?(?=\n\n|\Z)",
        "", text, flags=re.IGNORECASE | re.DOTALL
    )

    # Strip "ALL X VALUES WITHIN RANGE" lines
    text = re.sub(r"\[ALL[^\]]+WITHIN RANGE[^\]]*\]", "", text, flags=re.IGNORECASE)

    # Strip TOOL: ... PATIENT: ... lines
    text = re.sub(r"\*?\*?TOOL:\*?\*?\s*\w+[:\s]+PATIENT[:\s]+\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"please review the.*?TOOL.*?PATIENT.*?\.", "", text, flags=re.IGNORECASE | re.DOTALL)

    # Strip [DATA RETRIEVED ...] markers
    text = re.sub(r"\[DATA RETRIEVED[^\]]*\]", "", text)
    text = re.sub(r"TOOL RESULT for \w+:", "", text)

    lines = text.split("\n")
    clean_lines = [
        line for line in lines
        if not line.strip().startswith("Patient ID:")
        and not line.strip().startswith("Doctor's question:")
        and not re.match(r"TOOL:\s*\w+\s+PATIENT:", line.strip())
        and not re.match(r"\[CLINICAL ALERT", line.strip())
        and not re.match(r"\[END ALERTS\]", line.strip())
        and not re.match(r"\[RELEVANT CLINICAL", line.strip())
        and not re.match(r"\[CONVERSATION HISTORY\]", line.strip())
        and not re.match(r"\[END HISTORY\]", line.strip())
        and not re.match(r"\[PRELOADED\]", line.strip())
    ]
    return "\n".join(clean_lines).strip()


def build_history_block(history: list[dict]) -> str:
    if not history:
        return ""
    recent = history[-(MAX_HISTORY * 2):]
    lines = ["[CONVERSATION HISTORY]"]
    for entry in recent:
        role = "Doctor" if entry["role"] == "doctor" else "CLARA"
        lines.append(f"{role}: {entry['content']}")
    lines.append("[END HISTORY]")
    return "\n".join(lines)


def run_rule_engine(patient_id: str) -> Dict[str, Any]:
    return rule_engine.evaluate_labs(fetch_patient_lab_results(patient_id))


def fetch_patient_lab_results(patient_id: str) -> list[dict]:
    patient_id = str(patient_id or "").strip()
    if PATIENT_DATA_CACHE_SECONDS > 0:
        cached = _LAB_RESULTS_CACHE.get(patient_id)
        if cached and time.monotonic() - cached[0] <= PATIENT_DATA_CACHE_SECONDS:
            return list(cached[1])

    all_results: list = []
    for lab_type in ("chemistry", "hematology", "microscopy"):
        try:
            r = requests.post(
                f"{DATA_SERVICE_URL}/{lab_type}-results",
                json={"patient": patient_id, "labs": lab_type},
                timeout=30,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if isinstance(results, list):
                all_results.extend(results)
        except Exception:
            continue
    if PATIENT_DATA_CACHE_SECONDS > 0:
        _LAB_RESULTS_CACHE[patient_id] = (time.monotonic(), list(all_results))
    return all_results


@app.post("/clinical-alerts", response_model=ClinicalAlertsResponse)
def clinical_alerts(request: ClinicalAlertsRequest):
    """Run the rule engine against the patient's extracted lab results only."""
    lab_results = fetch_patient_lab_results(request.patient_id)
    evaluation = rule_engine.evaluate_labs(lab_results)
    flags = evaluation.get("flags", [])
    return ClinicalAlertsResponse(
        patient_id=request.patient_id,
        flags=flags,
        is_emergency=bool(evaluation.get("is_emergency", False)),
        flag_count=len(flags),
        lab_results_checked=len(lab_results),
    )


def lab_status(result: dict) -> str:
    value = result.get("value")
    low = result.get("reference_low")
    high = result.get("reference_high")
    if isinstance(value, (int, float)):
        if high is not None and value > high:
            return "high"
        if low is not None and value < low:
            return "low"
    return "within range"


def ref_text(result: dict) -> str:
    low = result.get("reference_low")
    high = result.get("reference_high")
    if low is not None and high is not None:
        return f"ref {low}-{high}"
    if high is not None:
        return f"ref <{high}"
    if low is not None:
        return f"ref >{low}"
    return "no reference range"


def try_direct_lab_answer(patient_id: str, message: str) -> Optional[tuple[str, list[str]]]:
    m = message.lower()
    if not any(term in m for term in ["cholesterol", "lipid", "ldl", "hdl", "triglyceride"]):
        return None

    try:
        r = requests.post(
            f"{DATA_SERVICE_URL}/chemistry-results",
            json={"patient": patient_id, "labs": "chemistry"},
            timeout=30,
        )
        r.raise_for_status()
    except requests.RequestException:
        return None

    wanted = ("CHOLESTEROL", "TRIGLYCERIDES", "HDL", "LDL", "VLDL")
    results = [
        item for item in r.json().get("results", [])
        if any(name in item.get("test_name", "").upper() for name in wanted)
    ]
    if not results:
        return None

    parts = []
    for item in results:
        name = item.get("test_name", "Lab")
        value = item.get("value")
        unit = item.get("unit") or ""
        parts.append(f"{name}: {value} {unit}".strip() + f" ({ref_text(item)}, {lab_status(item)}).")

    return "Cholesterol/lipid results: " + " ".join(parts), ["get_chemistry"]


_LAB_TOPIC = re.compile(
    r"\b(labs?|laboratory|chemistry|hematology|cbc\b|urinalysis|microscopy|blood work|lab work|"
    r"lab results?|lab values?|lab tests?|metabolic panel)\b",
    re.IGNORECASE,
)
_BROAD_LAB_ASK = re.compile(
    r"\b(any|all|everything|abnormal|out of range|o\.?r\.?|concern(ed)?|worried|worry|worrisome|"
    r"red flag|screen|overview|should i|findings|values?|review|flagged|elevated|decreased|high|low|"
    r"panic|critical)\b",
    re.IGNORECASE,
)
_SAFETY_RULE_TOPIC = re.compile(
    r"\b(critical|panic|emergency|urgent|danger(?:ous)?|red flag|life[- ]?threatening|"
    r"needs? immediate|stat)\b",
    re.IGNORECASE,
)
_STRICT_PATIENT_REFERENCE = re.compile(
    r"\b(this patient|current patient|selected patient|patient'?s|for him|for her|"
    r"for them|given his|given her|given their|his labs?|her labs?|their labs?|"
    r"his diagnosis|her diagnosis|their diagnosis|case|chart|record)\b",
    re.IGNORECASE,
)
_CHEMISTRY_TOPIC = re.compile(
    r"\b(cholesterol|ldl|hdl|triglycerides?|creatinine|glucose|fbs|sodium|potassium|"
    r"electrolytes?|sgpt|alt|chemistry|kidney|renal|liver)\b",
    re.IGNORECASE,
)
_HEMATOLOGY_TOPIC = re.compile(
    r"\b(cbc|hematology|hemoglobin|haemoglobin|hgb|wbc|rbc|platelets?|hematocrit|"
    r"neutrophils?|lymphocytes?|anemia|anaemia|blood count)\b",
    re.IGNORECASE,
)
_MICROSCOPY_TOPIC = re.compile(
    r"\b(urine|urinalysis|microscopy|pus cells?|protein|casts?|crystals?|bacteria)\b",
    re.IGNORECASE,
)
_PATIENT_CONTEXT_TOPIC = re.compile(
    r"\b(patient|summary|overview|context|diagnos(?:is|es)|medication|meds?|prescription|"
    r"discharge|history|hpi|pmh|clinical course|hospital course|follow[- ]?up|"
    r"management|treat(?:ment)?|procedure|plan|risk|assessment)\b",
    re.IGNORECASE,
)
_DOCUMENT_CONTEXT_TOPIC = re.compile(
    r"\b(pdf|document|file|page|pages|source document|source file|content|extracted text|"
    r"raw text|read this|what does .* say|according to .*pdf)\b",
    re.IGNORECASE,
)
_SPECIFIC_DOCUMENT_REFERENCE = re.compile(
    r"\b[A-Z]{2,10}[-_ ]?\d{2}[-_ ]?\d{3,}\b|\.pdf\b",
    re.IGNORECASE,
)


def wants_full_lab_scan(message: str) -> bool:
    if not message or not message.strip():
        return False
    return bool(_LAB_TOPIC.search(message) and _BROAD_LAB_ASK.search(message))


def wants_safety_rule_check(message: str, question_type: str) -> bool:
    if question_type not in ("labs", "both"):
        return False
    return bool(_SAFETY_RULE_TOPIC.search(message or ""))


def select_lab_tools(message: str, active_section: str = None) -> list[str]:
    SECTION_TOOL = {
        "chemistry":  "get_chemistry",
        "hematology": "get_hematology",
        "microscopy": "get_microscopy",
    }

    if wants_full_lab_scan(message):
        return ["get_all_labs"]

    tools: list[str] = []
    if _CHEMISTRY_TOPIC.search(message):
        tools.append("get_chemistry")
    if _HEMATOLOGY_TOPIC.search(message):
        tools.append("get_hematology")
    if _MICROSCOPY_TOPIC.search(message):
        tools.append("get_microscopy")

    if tools:
        return tools

    # If doctor is actively viewing a lab section and asks a nonspecific lab
    # follow-up, prefer that section instead of loading all modalities.
    if active_section and active_section in SECTION_TOOL:
        return [SECTION_TOOL[active_section]]

    return ["get_all_labs"]


def wants_patient_context(message: str, question_type: str) -> bool:
    if question_type == "guideline":
        return bool(_STRICT_PATIENT_REFERENCE.search(message or ""))
    if question_type == "both":
        return True
    return bool(_PATIENT_CONTEXT_TOPIC.search(message or ""))


def wants_document_context(message: str) -> bool:
    text = message or ""
    return bool(_SPECIFIC_DOCUMENT_REFERENCE.search(text) or _DOCUMENT_CONTEXT_TOPIC.search(text))


def _preload_patient_context(pid: str) -> tuple[str, list[str], list[str]]:
    tool_name, block = fetch_patient_context_block(pid)
    if not block or block.startswith("Error fetching"):
        return "", [], []
    lines = [
        "[PATIENT CONTEXT - PRELOADED BY SERVER]",
        "Use this as the structured patient record. Do not call another patient-data tool unless a specific detail is missing.",
        block,
    ]
    return "\n".join(lines).strip(), [tool_name], [block]


def _preload_document_context(pid: str, message: str) -> tuple[str, list[str], list[str], list[dict]]:
    try:
        block, sources = fetch_patient_document_context(pid, message)
    except Exception:
        return "", [], [], []

    if not block or block.startswith("No extracted") or block.startswith("No matching"):
        return "", [], [], sources

    lines = [
        "[PATIENT PDF CONTEXT - PRELOADED BY SERVER]",
        "Do NOT call tools. Answer using only these patient PDF excerpts.",
        "Start with: Based on <PDF source> p.<page>, ... when a page is available.",
        "Only cite or mention PDF sources present in this block.",
        block,
    ]
    return "\n".join(lines).strip(), ["get_patient_documents"], [block], sources


def _source_display_name(source: dict) -> str:
    title = str(source.get("title") or source.get("source") or "the patient PDF").strip()
    page = source.get("page")
    if page:
        return f"{title} p.{page}"
    return title


def ensure_pdf_source_opening(text: str, sources: list[dict]) -> str:
    cleaned = (text or "").strip()
    if not cleaned or not sources:
        return cleaned
    if re.match(r"^\s*based\s+(on|from)\b", cleaned, re.IGNORECASE):
        return cleaned
    return f"Based on {_source_display_name(sources[0])}: {cleaned}"


def build_no_tool_prompt() -> str:
    return (
        "No patient-data tools are available for this request. "
        "Answer using only the patient PDF context, patient context, lab data, "
        "guideline context, and conversation history already provided."
    )


def build_prompt(
    system: str,
    guidelines: str,
    emergency_block: str,
    history_block: str,
    patient_id: str,
    message: str
) -> str:
    parts = [system]

    if guidelines:
        parts.append("=== RELEVANT CARDIOVASCULAR GUIDELINES ===")
        parts.append(guidelines)
        parts.append("=== END GUIDELINES ===")

    if emergency_block:
        parts.append(emergency_block)
        parts.append("")

    if history_block:
        parts.append(history_block)
        parts.append("")

    parts.append(f"Patient ID: {patient_id}")
    parts.append(f"Doctor's question: {message}")
    parts.append("")
    parts.append(
        "If you still need patient data not shown above, retrieve it using exactly one line in this format: "
        "TOOL: <tool_name> PATIENT: <patient_id>"
    )
    parts.append(
        "For a broad lab review, prefer TOOL: get_all_labs PATIENT: <patient_id> so all lab modalities load at once."
    )
    parts.append(
        "If you already have enough information in the prompt to answer, respond directly. "
        "Use conversation history for follow-up questions."
    )
    parts.append(
        "If [PATIENT PDF CONTEXT] is present, answer from that PDF context only and start by naming "
        "the PDF source and page when available."
    )
    parts.append(
        "Give an evidence-grounded, decisive clinical answer when guideline context is available. "
        "For management questions, state the immediate procedure, treatment direction, and monitoring plan. "
        "Do not invent patient facts or present model estimates as confirmed diagnoses."
    )

    return "\n".join(parts)


def _preload_labs(pid: str, message: str, active_section: str = None) -> tuple[str, list[str], list[str]]:
    tools_called: list[str] = []
    collected_data: list[str] = []
    all_blocks: list[str] = []

    for selected_tool in select_lab_tools(message, active_section):
        lab_blocks = fetch_all_lab_blocks(pid) if selected_tool == "get_all_labs" else [
            (selected_tool, execute_tool(selected_tool, pid))
        ]
        for tool_name, block in lab_blocks:
            if tool_name not in tools_called:
                tools_called.append(tool_name)
            collected_data.append(block)
            all_blocks.append(block)

    # Build explicit abnormal summary the model cannot miss
    abnormal_lines = []
    for block in all_blocks:
        for line in block.splitlines():
            if "*** HIGH ***" in line or "*** LOW ***" in line:
                abnormal_lines.append(line.strip())

    preload_lines = [
        "[LAB DATA — PRELOADED BY SERVER]",
        "Do NOT call tools. Answer using only the data below.",
        "Do NOT comment on [WITHIN RANGE] values.",
        "",
    ]

    if abnormal_lines:
        preload_lines.append("[ABNORMAL VALUES — REPORT ALL OF THESE, NOT JUST THE FIRST]")
        preload_lines.extend(f"  {l}" for l in abnormal_lines)
        preload_lines.append("")

    for tool_name, block in zip(tools_called, collected_data):
        preload_lines.append(f"[{tool_name}]")
        preload_lines.append(block)
        preload_lines.append("")

    return "\n".join(preload_lines).strip(), tools_called, collected_data

def build_guideline_bundle(query: str) -> tuple[str, list[dict]]:
    """Return focused RAG context plus compact source metadata for the chat UI."""
    diagnosis_hint = infer_diagnosis_hint(query)
    management_query = is_management_query(query)
    chunks = retrieve(
        query,
        diagnosis_hint=diagnosis_hint,
        only_recommendations=management_query,
        top_k=5,
    )
    if not chunks and management_query:
        chunks = retrieve(query, diagnosis_hint=diagnosis_hint, top_k=5)
    if not chunks and diagnosis_hint:
        chunks = retrieve(query, top_k=5)
    if not chunks:
        return "", []

    # Keep the answer focused: prefer Philippine recommendation excerpts and
    # avoid sending several nearly identical chunks from one page to the LLM.
    chunks.sort(key=lambda chunk: (
        0 if chunk.get("is_philippine") else 1,
        0 if chunk.get("is_recommendation") else 1,
        -float(chunk.get("relevance") or 0),
    ))

    lines = ["[RELEVANT CLINICAL GUIDELINES]"]
    sources = []
    seen = set()
    for chunk in chunks:
        source = str(chunk.get("source") or "Clinical guideline")
        page = chunk.get("page")
        key = (source, page)
        if key not in seen:
            if len(sources) >= 3:
                continue
            sources.append({
                "title": source.replace("_", " "),
                "source": source,
                "page": page,
                "section": chunk.get("section_heading") or "",
                "type": "guideline",
            })
            seen.add(key)
        region = "Philippine" if chunk.get("is_philippine") else "International"
        page_text = f" p.{page}" if page else ""
        lines.append(f"\n--- {region} guideline: {source}{page_text} ---")
        lines.append(str(chunk.get("text") or "").strip())
    return "\n".join(lines), sources


ML_LAB_MAP = {
    "CREATININE": "creatinine", "BLOOD URIC ACID": "uric_acid",
    "SODIUM": "sodium", "POTASSIUM": "potassium", "CHLORIDE": "chloride",
    "TOTAL CHOLESTEROL": "cholesterol", "TRIGLYCERIDES": "triglyceride",
    "HDL": "hdl_cholesterol", "LDL": "ldl_cholesterol",
    "HEMOGLOBIN": "hemoglobin", "HEMATOCRIT": "hematocrit",
    "RBC": "red_blood_cell", "WBC": "white_blood_cell",
    "PLATELET COUNT": "platelet", "MCV": "mean_corpuscular_volume",
    "MCH": "mean_hemoglobin_volume", "MCHC": "mean_hemoglobin_concentration",
    "ESR": "esr",
}


def _number(value) -> Optional[float]:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else None


def build_ml_features(patient_id: str, lab_results: list[dict]) -> dict:
    """Use already retrieved patient data; never use known ML target labels as inputs."""
    features: dict = {}
    for result in lab_results:
        feature = ML_LAB_MAP.get(str(result.get("test_name") or "").upper())
        value = _number(result.get("value"))
        if feature and value is not None:
            features[feature] = value

    try:
        vitals = requests.post(
            f"{DATA_SERVICE_URL}/vitals",
            json={"patient": patient_id}, timeout=20,
        ).json()
        if vitals.get("bp"):
            features["systolic_blood_pressure"] = vitals["bp"].get("numeric")
            bp_match = re.search(r"(\d+)\s*/\s*(\d+)", str(vitals["bp"].get("value") or ""))
            if bp_match:
                features["diastolic_blood_pressure"] = float(bp_match.group(2))
        if vitals.get("hr"):
            features["pulse"] = vitals["hr"].get("numeric")
        if vitals.get("rr"):
            features["respiration"] = vitals["rr"].get("numeric")
        if vitals.get("temp"):
            features["body_temperature"] = vitals["temp"].get("numeric")
    except requests.RequestException:
        pass

    try:
        parsed = requests.post(
            f"{DATA_SERVICE_URL}/discharge-parsed",
            json={"patient": patient_id}, timeout=20,
        ).json()
        header = parsed.get("header") or {}
        age = _number(header.get("age"))
        if age is not None:
            features["age_category"] = age
        sex = str(header.get("sex") or "").lower()
        if sex.startswith("f"):
            features["gender"] = "Female"
        elif sex.startswith("m"):
            features["gender"] = "Male"

        clinical_text = " ".join(str(parsed.get(key) or "") for key in ("admitting_dx", "final_dx", "pmh")).lower()
        for feature, terms in {
            "diabetes": ["diabetes", "diabetic mellitus"],
            "copd": ["copd", "chronic obstructive pulmonary"],
            "moderate_to_severe_chronic_kidney_disease": ["chronic kidney", "ckd"],
            "acute_renal_failure": ["acute renal failure", "acute kidney injury", "aki"],
            "cerebrovascular_disease": ["stroke", "cerebrovascular"],
            "peripheral_vascular_disease": ["peripheral vascular"],
            "liver_disease": ["liver disease", "cirrhosis"],
        }.items():
            if any(term in clinical_text for term in terms):
                features[feature] = 1
        lvef = re.search(r"(?:lvef|ejection fraction|ef)\s*(?:is|of|:)?\s*([0-9]{1,3}(?:\.\d+)?)\s*%?", clinical_text)
        if lvef:
            features["lvef"] = float(lvef.group(1))
    except requests.RequestException:
        pass

    return {key: value for key, value in features.items() if value is not None}


def run_ml_assessment(patient_id: str, lab_results: list[dict]) -> tuple[list[dict], dict]:
    features = build_ml_features(patient_id, lab_results)
    if not features:
        return [], {"features_received": 0, "total_features": 0}
    try:
        response = requests.post(
            "http://localhost:8002/predict",
            json={"features": features}, timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("predictions") or [], {
            "features_received": data.get("features_received", 0),
            "total_features": data.get("features_received", 0) + len(data.get("missing_features", [])),
        }
    except requests.RequestException:
        return [], {"features_received": len(features), "total_features": len(features)}


def format_ml_context(predictions: list[dict], coverage: dict) -> str:
    if not predictions:
        return ""
    lines = [
        "[ML CLINICAL ASSESSMENT]",
        "Model outputs are estimates for clinician review, not confirmed diagnoses.",
    ]
    for prediction in predictions:
        label = prediction.get("label", prediction.get("key", "Assessment"))
        probability = float(prediction.get("probability", 0)) * 100
        if prediction.get("target_type") == "multiclass":
            lines.append(f"- {label}: {prediction.get('prediction', 'Unknown')} ({probability:.1f}% confidence)")
        else:
            lines.append(f"- {label}: {probability:.1f}% estimated probability")
    if coverage.get("total_features"):
        lines.append(f"Model input coverage: {coverage['features_received']}/{coverage['total_features']} features.")
    return "\n".join(lines)


# ── /chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    tools_called   = []
    collected_data = []
    session_id     = request.session_id or "default"

    system  = SYSTEM_PROMPT.format(tools_section=build_tools_prompt())
    history = request_history(request)

    # Resolve question type — short follow-ups inherit context from history
    question_type = resolve_question_type(request.message, history)
    pid = (request.patient_id or "").strip()

    direct_answer = (
        try_direct_lab_answer(pid, request.message)
        if pid and question_type == "labs" else None
    )
    if direct_answer:
        final_response, direct_tools = direct_answer
        tools_called.extend(t for t in direct_tools if t not in tools_called)
        conversation_store[session_id] = (history + [
            {"role": "doctor", "content": request.message},
            {"role": "clara", "content": final_response},
        ])[-(MAX_HISTORY * 2):]
        return ChatResponse(
            patient_id=request.patient_id,
            session_id=session_id,
            response=final_response,
            tools_called=tools_called,
            guidelines_used=False,
            history_length=len(conversation_store[session_id]) // 2,
            rule_flags=[],
            is_emergency=False,
        )

    document_context_block = ""
    patient_sources: list[dict] = []
    if pid and question_type == "document":
        document_context_block, document_tools, document_data, patient_sources = _preload_document_context(pid, request.message)
        tools_called.extend(t for t in document_tools if t not in tools_called)
        collected_data.extend(document_data)

    # 1. Retrieve guidelines for guideline or compound questions. PDF/document
    # questions stay isolated so source cards cannot point at unrelated PDFs.
    guidelines, _guideline_sources = (
        build_guideline_bundle(request.message)
        if question_type in ("guideline", "both") and not document_context_block
        else ("", [])
    )
    guidelines_used = bool(guidelines) and (
        "No relevant guideline" not in guidelines
        and "not initialised"   not in guidelines
        and "not found"         not in guidelines
    )

    # 2. Rule engine runs only for explicit safety/abnormality checks.
    if wants_safety_rule_check(request.message, question_type):
        rule_result = run_rule_engine(request.patient_id)
    else:
        rule_result = {"flags": [], "is_emergency": False}
    rule_flags   = rule_result.get("flags", [])
    is_emergency = rule_result.get("is_emergency", False)

    # 3. Emergency alert block
    emergency_block = ""
    if rule_flags:
        lines = ["[CLINICAL ALERT FLAGS — RULE ENGINE]"]
        lines += [f"  ! {flag}" for flag in rule_flags]
        lines.append("[END ALERTS]")
        emergency_block = "\n".join(lines)
    elif wants_safety_rule_check(request.message, question_type):
        emergency_block = "[CLINICAL ALERT FLAGS — RULE ENGINE]\nNo critical lab rule flags were triggered.\n[END ALERTS]"

    # 4. History block
    history_block = build_history_block(history)

    # 5. Preload lab data for lab or compound questions
    patient_context_block = ""
    preload_block = ""

    if pid and wants_patient_context(request.message, question_type) and question_type not in ("labs", "document"):
        patient_context_block, context_tools, context_data = _preload_patient_context(pid)
        tools_called.extend(t for t in context_tools if t not in tools_called)
        collected_data.extend(context_data)

    if pid and question_type in ("labs", "both") and not wants_safety_rule_check(request.message, question_type):
        # For a follow-up like "Yes", look back at what the original question was about
        source_message = request.message
        if question_type != classify_question(request.message):
            # We inherited type from history — use the original question for tool selection
            for entry in reversed(history):
                if entry["role"] == "doctor":
                    source_message = entry["content"]
                    break

        preload_block, lab_tools, lab_data = _preload_labs(pid, source_message, request.active_section)
        tools_called.extend(t for t in lab_tools if t not in tools_called)
        collected_data.extend(lab_data)

    system = SYSTEM_PROMPT.format(
        tools_section=build_no_tool_prompt()
        if (document_context_block or patient_context_block or preload_block or guidelines or emergency_block)
        else build_tools_prompt()
    )

    # 7. Build full prompt
    prompt = build_prompt(
        system, guidelines, emergency_block,
        history_block, request.patient_id, request.message
    )
    if patient_context_block:
        prompt = patient_context_block + "\n\n" + prompt
    if preload_block:
        prompt = preload_block + "\n\n" + prompt
    if document_context_block:
        prompt = document_context_block + "\n\n" + prompt

    final_response = "I was unable to generate a response."
    allow_model_tools = not (collected_data or guidelines or emergency_block or document_context_block)

    # 8. Tool-use loop. Most routes preload the required data, so the model should answer
    # immediately instead of discovering extra tools on its own.
    for _ in range(2 if allow_model_tools else 1):
        response_text = call_llm(prompt)
        tool_call     = parse_tool_call(response_text)

        if tool_call is None:
            final_response = clean_response(response_text)

            if not final_response and collected_data:
                retry_prompt = "\n".join([
                    system, "",
                    "Patient data:",
                    "\n\n".join(collected_data), "",
                    f"Question: {request.message}",
                    "Answer directly in 3 sentences or fewer. No preamble."
                ])
                final_response = clean_response(call_llm(retry_prompt))

            break

        if not allow_model_tools:
            retry_prompt = prompt + "\n\nDo not call tools. Answer directly from the provided context in 5 sentences or fewer."
            final_response = clean_response(call_llm(retry_prompt))
            break

        tool_name, patient_id = tool_call
        if tool_name not in tools_called:
            tools_called.append(tool_name)

        tool_result = execute_tool(tool_name, patient_id)
        collected_data.append(tool_result)

        prompt += "\n".join([
            "",
            f"[DATA RETRIEVED - {tool_name}]",
            tool_result,
            "",
            f"Answer this specific question using the data above: {request.message}",
            "Be direct. Maximum 5 sentences. Start with the finding, not a preamble.",
            ""
        ])

    if patient_sources:
        final_response = ensure_pdf_source_opening(final_response, patient_sources)

    # 9. Save to memory
    conversation_store[session_id] = (history + [
        {"role": "doctor", "content": request.message},
        {"role": "clara", "content": final_response},
    ])[-(MAX_HISTORY * 2):]

    return ChatResponse(
        patient_id      = request.patient_id,
        session_id      = session_id,
        response        = final_response,
        tools_called    = tools_called,
        guidelines_used = guidelines_used,
        history_length  = len(conversation_store[session_id]) // 2,
        rule_flags      = rule_flags,
        is_emergency    = is_emergency
    )


# ── /chat/stream endpoint ──────────────────────────────────────────────────────

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    def stream_tokens():
        started = time.perf_counter()
        session_id = request.session_id or "default"
        tools_called: list[str] = []
        collected_data: list[str] = []
        guideline_sources: list[dict] = []
        patient_sources: list[dict] = []
        ml_predictions: list[dict] = []
        ml_coverage: dict = {}

        def event(payload: dict):
            return f"data: {json.dumps(payload)}\n\n"

        def status(label: str):
            return event({"type": "status", "label": label})

        try:
            history = request_history(request)
            question_type = resolve_question_type(request.message, history)
            pid = (request.patient_id or "").strip()
            direct_answer = (
                try_direct_lab_answer(pid, request.message)
                if pid and question_type == "labs" else None
            )
            needs_document_context = not direct_answer and bool(pid) and question_type == "document"
            needs_guidelines = not direct_answer and not needs_document_context and question_type in ("guideline", "both")
            needs_ml = not direct_answer and bool(pid) and wants_ml_assessment(request.message)
            needs_rules = not direct_answer and bool(pid) and (
                wants_safety_rule_check(request.message, question_type) or needs_ml
            )
            needs_patient_context = not direct_answer and bool(pid) and (
                (wants_patient_context(request.message, question_type) and not needs_document_context) or needs_ml
            )

            if not (needs_document_context or needs_guidelines or needs_rules or needs_ml):
                yield status("Preparing a response")

            guidelines = ""
            if needs_guidelines:
                yield status("Checking cardiovascular guidelines")
                guidelines, guideline_sources = build_guideline_bundle(request.message)
                yield event({"type": "sources", "sources": guideline_sources})
            guidelines_used = bool(guideline_sources)

            document_context_block = ""
            if needs_document_context:
                yield status("Reading patient PDF source")
                document_context_block, document_tools, document_data, patient_sources = _preload_document_context(pid, request.message)
                yield event({"type": "sources", "sources": patient_sources + guideline_sources})
                tools_called.extend(t for t in document_tools if t not in tools_called)
                collected_data.extend(document_data)

            lab_results: list[dict] = []
            rule_flags: list[str] = []
            is_emergency = False
            if needs_rules:
                yield status("Checking patient safety rules")
                lab_results = fetch_patient_lab_results(pid)
                rule_result = rule_engine.evaluate_labs(lab_results)
                rule_flags = rule_result.get("flags", [])
                is_emergency = rule_result.get("is_emergency", False)
                tools_called.append("rule_engine")

            emergency_block = ""
            if rule_flags:
                lines = ["[CLINICAL ALERT FLAGS - RULE ENGINE]"]
                lines += [f"  ! {flag}" for flag in rule_flags]
                lines.append("[END ALERTS]")
                emergency_block = "\n".join(lines)
            elif wants_safety_rule_check(request.message, question_type):
                emergency_block = "[CLINICAL ALERT FLAGS - RULE ENGINE]\nNo critical lab rule flags were triggered.\n[END ALERTS]"

            patient_context_block = ""
            if needs_patient_context:
                yield status("Reading the structured patient record")
                patient_context_block, context_tools, context_data = _preload_patient_context(pid)
                tools_called.extend(t for t in context_tools if t not in tools_called)
                collected_data.extend(context_data)

            preload_block = ""
            if (
                not direct_answer
                and pid
                and question_type in ("labs", "both")
                and not wants_safety_rule_check(request.message, question_type)
            ):
                yield status("Reading relevant laboratory results")
                source_message = request.message
                if question_type != classify_question(request.message):
                    for entry in reversed(history):
                        if entry["role"] == "doctor":
                            source_message = entry["content"]
                            break
                preload_block, lab_tools, lab_data = _preload_labs(pid, source_message, request.active_section)
                tools_called.extend(t for t in lab_tools if t not in tools_called)
                collected_data.extend(lab_data)

            ml_context = ""
            if needs_ml:
                yield status("Running the machine-learning assessment")
                if not lab_results:
                    lab_results = fetch_patient_lab_results(pid)
                ml_predictions, ml_coverage = run_ml_assessment(pid, lab_results)
                if ml_predictions:
                    tools_called.append("ml_assessment")
                    ml_context = format_ml_context(ml_predictions, ml_coverage)

            clinical_work_performed = needs_document_context or needs_guidelines or needs_rules or needs_ml
            if clinical_work_performed:
                yield status("Integrating retrieved clinical information")
            system = SYSTEM_PROMPT.format(
                tools_section=build_no_tool_prompt()
                if (document_context_block or patient_context_block or preload_block or guidelines or emergency_block or ml_context)
                else build_tools_prompt()
            )
            prompt = build_prompt(
                system, guidelines, emergency_block,
                build_history_block(history), request.patient_id, request.message,
            )
            if patient_context_block:
                prompt = patient_context_block + "\n\n" + prompt
            if preload_block:
                prompt = preload_block + "\n\n" + prompt
            if ml_context:
                prompt = ml_context + "\n\n" + prompt
            if document_context_block:
                prompt = document_context_block + "\n\n" + prompt

            final_response = ""
            if direct_answer:
                final_response, direct_tools = direct_answer
                tools_called.extend(t for t in direct_tools if t not in tools_called)
            else:
                allow_model_tools = not (collected_data or guidelines or emergency_block or ml_context or document_context_block)
                for _ in range(2 if allow_model_tools else 1):
                    response_text = call_llm(prompt)
                    tool_call = parse_tool_call(response_text)
                    if tool_call is None:
                        final_response = clean_response(response_text)
                        break
                    if not allow_model_tools:
                        retry_prompt = prompt + "\n\nDo not call tools. Answer directly from the provided context in 5 sentences or fewer."
                        final_response = clean_response(call_llm(retry_prompt))
                        break
                    tool_name, patient_id = tool_call
                    if tool_name not in tools_called:
                        tools_called.append(tool_name)
                    tool_result = execute_tool(tool_name, patient_id)
                    collected_data.append(tool_result)
                    prompt += "\n".join([
                        "", f"[DATA RETRIEVED - {tool_name}]", tool_result, "",
                        f"Answer this specific question using the data above: {request.message}",
                        "Be direct, evidence-grounded, and concise.", "",
                    ])

            if not final_response:
                final_response = "I was unable to generate a response from the available patient data."
            if patient_sources:
                final_response = ensure_pdf_source_opening(final_response, patient_sources)

            yield event({
                "type": "meta",
                "tools_called": tools_called,
                "guidelines_used": guidelines_used,
                "guideline_sources": guideline_sources,
                "sources": patient_sources + guideline_sources,
                "rule_flags": rule_flags,
                "is_emergency": is_emergency,
                "ml_used": bool(ml_predictions),
                "history_length": len(history) // 2,
            })
            yield status("Writing the clinical response" if clinical_work_performed else "Writing the response")

            full_response = ""
            for word in re.findall(r"\S+\s*|\s+", final_response):
                full_response += word
                yield event({"type": "token", "token": word})
        except Exception as e:
            yield event({"type": "error", "message": str(e)})
            return

        cleaned = clean_response(full_response)
        conversation_store[session_id] = (history + [
            {"role": "doctor", "content": request.message},
            {"role": "clara", "content": cleaned},
        ])[-(MAX_HISTORY * 2):]

        yield event({
            "type": "done",
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        })

    return StreamingResponse(
        stream_tokens(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.get("/history/{session_id}")
def get_history(session_id: str):
    history = conversation_store.get(session_id, [])
    return {
        "session_id": session_id,
        "exchanges":  len(history) // 2,
        "history":    history
    }


@app.post("/history/clear")
def clear_history(request: ClearHistoryRequest):
    session_id = request.session_id or "default"
    if session_id in conversation_store:
        del conversation_store[session_id]
    return {"session_id": session_id, "status": "cleared"}

@app.get("/health")
def health():
    llm_model = {
        "gemini": GEMINI_MODEL,
        "groq": GROQ_MODEL,
        "ollama": OLLAMA_MODEL,
        "huggingface": HF_MODEL,
        "hf": HF_MODEL,
    }.get(LLM_PROVIDER, "unknown")

    return {
        "status":          "ok",
        "service":         "CLARA LLM",
        "provider":        LLM_PROVIDER,
        "model":           llm_model,
        "rag_embedding_provider": RAG_EMBEDDING_PROVIDER,
        "rag_embedding_model":    RAG_EMBED_MODEL,
        "active_sessions": len(conversation_store)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
