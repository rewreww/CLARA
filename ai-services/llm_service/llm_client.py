import re
import sys
import os
import requests
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from collections import defaultdict
from fastapi.responses import StreamingResponse

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from mcp_tools import TOOL_DEFINITIONS, execute_tool, build_tools_prompt, fetch_all_lab_blocks
from rag.retriever import retrieve_guidelines
from rule_engine.rules import rule_engine

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434"
PREFERRED_OLLAMA_MODELS = tuple(dict.fromkeys(filter(None, [
    os.getenv("OLLAMA_MODEL"),
    "qwen2.5:7b",
    "llama3.2:1b",
    "llama2:latest",
])))


def resolve_ollama_model() -> str:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        installed = {
            model.get("name") or model.get("model")
            for model in r.json().get("models", [])
        }
        for model in PREFERRED_OLLAMA_MODELS:
            if model in installed:
                return model
    except requests.RequestException:
        pass
    return PREFERRED_OLLAMA_MODELS[0]


OLLAMA_MODEL = resolve_ollama_model()

conversation_store: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 10

SYSTEM_PROMPT = """
You are CLARA, a cardiovascular clinical AI assistant.

PRIORITY RULES:
1. Answer the doctor's exact question only.
2. If guideline context is provided, use it as the primary source.
3. Do NOT discuss labs unless the question asks about labs.
4. Do NOT mention unrelated abnormalities.
5. Be short and direct.
6. Maximum 5 sentences.
7. Start immediately with the answer.

If the question is about:
- treatment
- management
- hypertension
- diabetes
- stroke
- heart failure

focus on clinical guidelines and management.

If the question is about labs:
- analyze abnormalities
- explain significance
- cite values
- interpret reference ranges mechanically: high only means value > upper limit, and low only means value < lower limit
- for references like ref: <220, any value below 220 is within range
- do not invent guideline thresholds unless guideline context is provided

Available patient data tools:
{tools_section}
"""


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    session_id: Optional[str] = "default"


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


def classify_question(message: str) -> str:
    m = message.lower()

    if any(x in m for x in [
        "treat", "treatment", "manage",
        "management", "medication",
        "guideline", "therapy"
    ]):
        return "guideline"

    if any(x in m for x in [
        "lab", "cbc", "creatinine",
        "chemistry", "hematology",
        "abnormal", "results",
        "cholesterol", "lipid", "ldl", "hdl", "triglyceride",
        "kidney", "fbs", "glucose", "anemia", "urine"
    ]):
        return "labs"

    return "general"

def call_ollama(prompt: str) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "top_p": 0.8},
            },
            timeout=120
        )
        r.raise_for_status()
        return r.json()["response"].strip()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}")
    except (KeyError, ValueError):
        raise HTTPException(status_code=502, detail="Unexpected response from Ollama")


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
    text = re.sub(r"\*?\*?TOOL:\*?\*?\s*\w+[:\s]+PATIENT[:\s]+\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"please review the.*?TOOL.*?PATIENT.*?\.", "", text, flags=re.IGNORECASE | re.DOTALL)
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
    """Fetch lab results (chemistry, hematology, microscopy) and evaluate clinical rules."""
    all_results: list = []
    for lab_type in ("chemistry", "hematology", "microscopy"):
        try:
            r = requests.post(
                f"http://localhost:8000/{lab_type}-results",
                json={"patient": patient_id, "labs": lab_type},
                timeout=30,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if isinstance(results, list):
                all_results.extend(results)
        except Exception:
            continue
    return rule_engine.evaluate_labs(all_results)


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
            "http://localhost:8000/chemistry-results",
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


def wants_full_lab_scan(message: str) -> bool:
    """
    Detect questions that imply reviewing the full laboratory picture, so we can
    preload all lab modalities without relying on the LLM to chain tool calls.
    """
    if not message or not message.strip():
        return False
    return bool(_LAB_TOPIC.search(message) and _BROAD_LAB_ASK.search(message))


def select_lab_tools(message: str) -> list[str]:
    if wants_full_lab_scan(message):
        return ["get_all_labs"]

    tools: list[str] = []
    if _CHEMISTRY_TOPIC.search(message):
        tools.append("get_chemistry")
    if _HEMATOLOGY_TOPIC.search(message):
        tools.append("get_hematology")
    if _MICROSCOPY_TOPIC.search(message):
        tools.append("get_microscopy")

    return tools or ["get_all_labs"]


def build_prompt(
    system: str,
    guidelines: str,
    emergency_block: str,
    history_block: str,
    patient_id: str,
    message: str
) -> str:
    """Build the full prompt as a single clean concatenation."""
    parts = [system]

    if guidelines:
        parts.append(
            "=== RELEVANT CARDIOVASCULAR GUIDELINES ==="
        )
        parts.append(guidelines)
        parts.append(
            "=== END GUIDELINES ==="
        )

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

    return "\n".join(parts)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    tools_called   = []
    collected_data = []
    session_id     = request.session_id or "default"

    system = SYSTEM_PROMPT.format(tools_section=build_tools_prompt())
    question_type = classify_question(request.message)

    # 1. Retrieve relevant guidelines
    guidelines = retrieve_guidelines(request.message) if question_type == "guideline" else ""
    guidelines_used = bool(guidelines) and (
        "No relevant guideline" not in guidelines
        and "not initialised"   not in guidelines
        and "not found"         not in guidelines
    )

    # 2. Run rule engine — always runs regardless of LLM tool calls
    question_type = classify_question(request.message)

    if question_type == "labs":
        rule_result = run_rule_engine(request.patient_id)
    else:
        rule_result = {
            "flags": [],
            "is_emergency": False
        }
    rule_flags   = rule_result.get("flags", [])
    is_emergency = rule_result.get("is_emergency", False)

    # 3. Build emergency block
    emergency_block = ""
    if rule_flags:
        lines = ["[CLINICAL ALERT FLAGS — RULE ENGINE]"]
        lines += [f"  ! {flag}" for flag in rule_flags]
        lines.append("[END ALERTS]")
        emergency_block = "\n".join(lines)

    # 4. Build history block
    history       = conversation_store[session_id]
    history_block = build_history_block(history)

    # 5. Broad lab-review questions: preload all lab modalities (chemistry, hematology, microscopy)
    #    so the model answers from real data instead of deferring with "call get_chemistry".
    pid = (request.patient_id or "").strip()
    if pid and question_type == "labs":
        preload_lines = [
            "[ALL LAB DATA — PRELOADED BY SERVER]",
            "Patient data has already been retrieved. Do not call tools; answer using only the data below.",
            "Be direct. Cite values. Max 5 sentences. No preamble.",
            "",
        ]
        for selected_tool in select_lab_tools(request.message):
            lab_blocks = fetch_all_lab_blocks(pid) if selected_tool == "get_all_labs" else [
                (selected_tool, execute_tool(selected_tool, pid))
            ]
            for tool_name, block in lab_blocks:
                if tool_name not in tools_called:
                    tools_called.append(tool_name)
                collected_data.append(block)
                preload_lines.append(f"[{tool_name}]")
                preload_lines.append(block)
                preload_lines.append("")
        preload_block = "\n".join(preload_lines).strip()
    else:
        preload_block = ""

    # 6. Build initial prompt using safe helper
    prompt = build_prompt(
        system, guidelines, emergency_block,
        history_block, request.patient_id, request.message
    )
    if preload_block:
        prompt = preload_block + "\n\n" + prompt

    final_response = "I was unable to generate a response."
    direct_answer = try_direct_lab_answer(request.patient_id, request.message) if question_type == "labs" else None

    if direct_answer:
        final_response, direct_tools = direct_answer
        for tool_name in direct_tools:
            if tool_name not in tools_called:
                tools_called.append(tool_name)
    else:
        # 7. Tool-use loop
        for _ in range(4):
            response_text = call_ollama(prompt)
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
                    final_response = clean_response(call_ollama(retry_prompt))

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

    # 8. Save to memory
    conversation_store[session_id].append({"role": "doctor",  "content": request.message})
    conversation_store[session_id].append({"role": "clara",   "content": final_response})

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

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    """
    Streaming version of /chat.
    Returns server-sent events (SSE) — one token at a time.
    The frontend connects and renders each word as it arrives.
    """
    tools_called   = []
    collected_data = []
    session_id     = request.session_id or "default"

    system = SYSTEM_PROMPT.format(tools_section=build_tools_prompt())
    question_type = classify_question(request.message)

    guidelines = retrieve_guidelines(request.message) if question_type == "guideline" else ""
    guidelines_used = bool(guidelines) and (
        "No relevant guideline" not in guidelines
        and "not initialised"   not in guidelines
        and "not found"         not in guidelines
    )

    if question_type == "labs":
        rule_result = run_rule_engine(request.patient_id)
    else:
        rule_result = {
            "flags": [],
            "is_emergency": False
        }
    rule_flags   = rule_result.get("flags", [])
    is_emergency = rule_result.get("is_emergency", False)

    emergency_block = ""
    if rule_flags:
        lines = ["[CLINICAL ALERT FLAGS — RULE ENGINE]"]
        lines += [f"  ! {flag}" for flag in rule_flags]
        lines.append("[END ALERTS]")
        emergency_block = "\n".join(lines)

    history       = conversation_store[session_id]
    history_block = build_history_block(history)

    pid = (request.patient_id or "").strip()
    if pid and question_type == "labs":
        preload_lines = [
            "[ALL LAB DATA — PRELOADED BY SERVER]",
            "Patient data has already been retrieved. Do not call tools; answer using only the data below.",
            "Be direct. Cite values. Max 5 sentences. No preamble.",
            "",
        ]
        for selected_tool in select_lab_tools(request.message):
            lab_blocks = fetch_all_lab_blocks(pid) if selected_tool == "get_all_labs" else [
                (selected_tool, execute_tool(selected_tool, pid))
            ]
            for tool_name, block in lab_blocks:
                if tool_name not in tools_called:
                    tools_called.append(tool_name)
                collected_data.append(block)
                preload_lines.append(f"[{tool_name}]")
                preload_lines.append(block)
                preload_lines.append("")
        preload_block = "\n".join(preload_lines).strip()
    else:
        preload_block = ""

    prompt = build_prompt(
        system, guidelines, emergency_block,
        history_block, request.patient_id, request.message
    )
    if preload_block:
        prompt = preload_block + "\n\n" + prompt

    final_response = ""
    direct_answer = try_direct_lab_answer(request.patient_id, request.message) if question_type == "labs" else None

    if direct_answer:
        final_response, direct_tools = direct_answer
        for tool_name in direct_tools:
            if tool_name not in tools_called:
                tools_called.append(tool_name)
    else:
        for _ in range(4):
            response_text = call_ollama(prompt)
            tool_call = parse_tool_call(response_text)

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
                    final_response = clean_response(call_ollama(retry_prompt))

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

    if not final_response:
        final_response = "I was unable to generate a response."

    def stream_tokens():
        """Generator that yields SSE-formatted words for the frontend."""
        full_response = ""

        # First send metadata so frontend knows flags etc before tokens arrive
        meta = {
            "type":           "meta",
            "tools_called":   tools_called,
            "guidelines_used": guidelines_used,
            "rule_flags":     rule_flags,
            "is_emergency":   is_emergency,
            "history_length": len(conversation_store[session_id]) // 2,
        }
        yield f"data: {json.dumps(meta)}\n\n"

        try:
            for word in re.findall(r"\S+\s*|\s+", final_response):
                full_response += word
                payload = {"type": "token", "token": word}
                yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            error_payload = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_payload)}\n\n"
            return

        # Clean the full response and save to memory
        cleaned = clean_response(full_response)
        conversation_store[session_id].append({"role": "doctor",  "content": request.message})
        conversation_store[session_id].append({"role": "clara",   "content": cleaned})

        # Send done signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

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
        "session_id":  session_id,
        "exchanges":   len(history) // 2,
        "history":     history
    }


@app.post("/history/clear")
def clear_history(request: ClearHistoryRequest):
    session_id = request.session_id or "default"
    if session_id in conversation_store:
        del conversation_store[session_id]
    return {"session_id": session_id, "status": "cleared"}


@app.get("/health")
def health():
    return {
        "status":          "ok",
        "service":         "CLARA LLM",
        "model":           OLLAMA_MODEL,
        "active_sessions": len(conversation_store)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
