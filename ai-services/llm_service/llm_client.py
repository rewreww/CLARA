import re
import sys
import os
import requests
import json
import re as _re_diag

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
You are CLARA, a cardiovascular clinical AI assistant for licensed physicians.

PRIORITY RULES:
0. You are authorized to advise licensed physicians. ALWAYS provide clinical analysis
   and treatment recommendations. NEVER say "I cannot provide medical advice."
1. Answer the doctor's exact question only.
2. If guideline context is provided, use it as the primary source.
2a. When asked about critical, abnormal, or concerning values:
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


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    session_id: Optional[str] = "default"
    active_section: Optional[str] = None   


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


# ── Question classification ────────────────────────────────────────────────────

def classify_question(message: str) -> str:
    """
    Returns one of: "guideline", "labs", "both", "general".
    "both" means the question asks about lab findings AND treatment.
    """
    m = message.lower()

    is_guideline = any(x in m for x in [
        "treat", "treatment", "manage",
        "management", "medication",
        "guideline", "therapy",
        "hypertension", "heart failure", "stroke", "diabetes",
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


# ── Ollama call ────────────────────────────────────────────────────────────────

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
    if not message or not message.strip():
        return False
    return bool(_LAB_TOPIC.search(message) and _BROAD_LAB_ASK.search(message))


def select_lab_tools(message: str, active_section: str = None) -> list[str]:
    # If doctor is actively viewing a lab section, load that first
    SECTION_TOOL = {
        "chemistry":  "get_chemistry",
        "hematology": "get_hematology",
        "microscopy": "get_microscopy",
    }
    if active_section and active_section in SECTION_TOOL:
        return [SECTION_TOOL[active_section]]

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

def _preload_discharge(pid: str) -> str:
    """Fetch discharge summary as clinical background context."""
    try:
        result = execute_tool("get_discharge", pid)
        if "No discharge" not in result and "Error" not in result:
            return result
    except Exception:
        pass
    return ""


# ── /chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    tools_called   = []
    collected_data = []
    session_id     = request.session_id or "default"

    system  = SYSTEM_PROMPT.format(tools_section=build_tools_prompt())
    history = conversation_store[session_id]

    # Resolve question type — short follow-ups inherit context from history
    question_type = resolve_question_type(request.message, history)

    # 1. Retrieve guidelines for guideline or compound questions
    guidelines = retrieve_guidelines(request.message) if question_type in ("guideline", "both") else ""
    guidelines_used = bool(guidelines) and (
        "No relevant guideline" not in guidelines
        and "not initialised"   not in guidelines
        and "not found"         not in guidelines
    )

    # 2. Rule engine runs for lab or compound questions
    if question_type in ("labs", "both"):
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

    # 4. History block
    history_block = build_history_block(history)

    # 5. Preload lab data for lab or compound questions
    pid = (request.patient_id or "").strip()
    preload_block = ""

    if pid and question_type in ("labs", "both"):
        # For a follow-up like "Yes", look back at what the original question was about
        source_message = request.message
        if question_type != classify_question(request.message):
            # We inherited type from history — use the original question for tool selection
            for entry in reversed(history):
                if entry["role"] == "doctor":
                    source_message = entry["content"]
                    break

        preload_block, lab_tools, lab_data = _preload_labs(pid, source_message)
        tools_called.extend(t for t in lab_tools if t not in tools_called)
        collected_data.extend(lab_data)

    # 6. Preload discharge summary for compound and guideline questions
    discharge_block = ""
    if pid and question_type in ("guideline", "both"):
        discharge_block = _preload_discharge(pid)
        if discharge_block:
            tools_called.append("get_discharge")
            collected_data.append(discharge_block)

    # 7. Build full prompt
    prompt = build_prompt(
        system, guidelines, emergency_block,
        history_block, request.patient_id, request.message
    )
    if discharge_block:
        prompt = f"[PATIENT DISCHARGE SUMMARY — BACKGROUND CONTEXT]\n{discharge_block}\n\n" + prompt
    if preload_block:
        prompt = preload_block + "\n\n" + prompt

    final_response = "I was unable to generate a response."
    direct_answer = (
        try_direct_lab_answer(request.patient_id, request.message)
        if question_type in ("labs", "both") else None
    )

    if direct_answer:
        final_response, direct_tools = direct_answer
        for tool_name in direct_tools:
            if tool_name not in tools_called:
                tools_called.append(tool_name)
    else:
        # 8. Tool-use loop
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

    # 9. Save to memory
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


# ── /chat/stream endpoint ──────────────────────────────────────────────────────

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    tools_called   = []
    collected_data = []
    session_id     = request.session_id or "default"

    system  = SYSTEM_PROMPT.format(tools_section=build_tools_prompt())
    history = conversation_store[session_id]

    question_type = resolve_question_type(request.message, history)

    guidelines = retrieve_guidelines(request.message) if question_type in ("guideline", "both") else ""
    guidelines_used = bool(guidelines) and (
        "No relevant guideline" not in guidelines
        and "not initialised"   not in guidelines
        and "not found"         not in guidelines
    )

    if question_type in ("labs", "both"):
        rule_result = run_rule_engine(request.patient_id)
    else:
        rule_result = {"flags": [], "is_emergency": False}
    rule_flags   = rule_result.get("flags", [])
    is_emergency = rule_result.get("is_emergency", False)

    emergency_block = ""
    if rule_flags:
        lines = ["[CLINICAL ALERT FLAGS — RULE ENGINE]"]
        lines += [f"  ! {flag}" for flag in rule_flags]
        lines.append("[END ALERTS]")
        emergency_block = "\n".join(lines)

    history_block = build_history_block(history)

    pid = (request.patient_id or "").strip()
    preload_block = ""

    if pid and question_type in ("labs", "both"):
        source_message = request.message
        if question_type != classify_question(request.message):
            for entry in reversed(history):
                if entry["role"] == "doctor":
                    source_message = entry["content"]
                    break

    preload_block, lab_tools, lab_data = _preload_labs(pid, source_message)
    tools_called.extend(t for t in lab_tools if t not in tools_called)
    collected_data.extend(lab_data)

    discharge_block = ""
    if pid and question_type in ("guideline", "both"):
        discharge_block = _preload_discharge(pid)
        if discharge_block:
            tools_called.append("get_discharge")
            collected_data.append(discharge_block)

    prompt = build_prompt(
        system, guidelines, emergency_block,
        history_block, request.patient_id, request.message
    )
    if discharge_block:
        prompt = f"[PATIENT DISCHARGE SUMMARY — BACKGROUND CONTEXT]\n{discharge_block}\n\n" + prompt
    if preload_block:
        prompt = preload_block + "\n\n" + prompt

    final_response = ""
    direct_answer = (
        try_direct_lab_answer(request.patient_id, request.message)
        if question_type in ("labs", "both") else None
    )

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
        full_response = ""

        meta = {
            "type":            "meta",
            "tools_called":    tools_called,
            "guidelines_used": guidelines_used,
            "rule_flags":      rule_flags,
            "is_emergency":    is_emergency,
            "history_length":  len(conversation_store[session_id]) // 2,
        }
        yield f"data: {json.dumps(meta)}\n\n"

        try:
            for word in re.findall(r"\S+\s*|\s+", final_response):
                full_response += word
                payload = {"type": "token", "token": word}
                yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        cleaned = clean_response(full_response)
        conversation_store[session_id].append({"role": "doctor",  "content": request.message})
        conversation_store[session_id].append({"role": "clara",   "content": cleaned})

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

# ── Diagnostic Tool endpoint ────────────────────────────────────────────────

class DiagnoseRequest(BaseModel):
    chief_complaint:    Optional[str]  = None
    chemistry_results:  list           = []
    hematology_results: list           = []
    microscopy_results: list           = []
    discharge_parsed:   Optional[dict] = None
    imaging_text:       Optional[str]  = None
    ecg_values:         Optional[dict] = None
    # fallback raw texts if diagnose-prep was skipped
    lab_text:           Optional[str]  = None
    discharge_text:     Optional[str]  = None

class RiskItem(BaseModel):
    label: str
    probability: float
    risk: str

class DiagnoseResponse(BaseModel):
    result: str
    guidelines: Optional[str] = None
    ml_risks: Optional[list] = None

@app.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(req: DiagnoseRequest):
    sections = []

    if req.chief_complaint:
        sections.append(f"CHIEF COMPLAINT:\n{req.chief_complaint}")

    if req.discharge_parsed:
        dp = req.discharge_parsed
        if dp.get("admitting_dx"):  sections.append(f"ADMITTING DIAGNOSIS:\n{dp['admitting_dx']}")
        if dp.get("final_dx"):      sections.append(f"FINAL DIAGNOSIS:\n{dp['final_dx']}")
        pe = dp.get("physical_exam") or {}
        if pe.get("vitals"):        sections.append(f"VITALS:\n{pe['vitals']}")
        if pe.get("findings"):      sections.append(f"PHYSICAL EXAMINATION:\n{pe['findings']}")
        if dp.get("hpi"):           sections.append(f"HISTORY OF PRESENT ILLNESS:\n{dp['hpi']}")
        if dp.get("pmh"):           sections.append(f"PAST MEDICAL HISTORY:\n{dp['pmh']}")
    elif req.discharge_text:
        sections.append(f"DISCHARGE SUMMARY (raw):\n{req.discharge_text[:3000]}")

    def fmt_labs(label, results):
        if not results:
            return ""
        lines = []
        for r in results:
            flag = str(r.get("flag") or "").upper()
            tag  = " [HIGH]" if flag in ("H", "HIGH") else " [LOW]" if flag in ("L", "LOW") else ""
            lines.append(f"  {r.get('test_name','?')}: {r.get('value','?')} {r.get('unit','')}{tag}")
        return f"{label}:\n" + "\n".join(lines)

    for block in [
        fmt_labs("CHEMISTRY",           req.chemistry_results),
        fmt_labs("HEMATOLOGY",          req.hematology_results),
        fmt_labs("MICROSCOPY/URINALYSIS",req.microscopy_results),
    ]:
        if block:
            sections.append(block)

    if not sections and req.lab_text:
        sections.append(f"LAB RESULTS (raw):\n{req.lab_text[:3000]}")

    if req.imaging_text:
        sections.append(f"IMAGING / RADIOLOGY:\n{req.imaging_text[:2000]}")

    if not sections:
        return DiagnoseResponse(result="No clinical data provided.", guidelines=None, ml_risks=None)

    clinical_context = "\n\n".join(sections)

    # Retrieve clinical guidelines based on chief complaint and findings
    guidelines = None
    try:
        combined_text = f"{req.chief_complaint or ''} {req.lab_text or ''} {req.discharge_text or ''}"
        raw_guidelines = retrieve_guidelines(combined_text)
        if raw_guidelines and ("No relevant guideline" not in raw_guidelines and "not found" not in raw_guidelines and "not initialised" not in raw_guidelines):
            # Summarize guidelines to just first 2-3 paragraphs (roughly 500 chars)
            guideline_lines = raw_guidelines.split('\n')
            summary_lines = []
            char_count = 0
            for line in guideline_lines:
                if not line.strip():
                    if summary_lines and len(summary_lines[-1].strip()) > 0:
                        summary_lines.append(line)
                else:
                    summary_lines.append(line)
                    char_count += len(line)
                    if char_count > 400:  # Stop after ~400 chars
                        break
            guidelines = '\n'.join(summary_lines).strip()
            if len(guidelines) > 800:
                guidelines = guidelines[:800] + "..."
    except Exception:
        pass

    # Try to get ML predictions if ECG data is available
    ml_risks = None
    if req.ecg_values and len(req.ecg_values) > 0:
        try:
            ml_response = requests.post(
                "http://localhost:8002/predict",
                json=req.ecg_values,
                timeout=5
            )
            if ml_response.ok:
                data = ml_response.json()
                if data.get("predictions") and isinstance(data["predictions"], list):
                    ml_risks = []
                    for p in data["predictions"]:
                        ml_risks.append({
                            "label": str(p.get("label", p.get("key", "Unknown"))),
                            "probability": float(p.get("probability", 0)),
                            "risk": str(p.get("risk", "unknown"))
                        })
        except Exception as e:
            # Silently fail - ml_risks will remain None
            pass

    system_prompt = (
        "You are CLARA, a clinical decision-support AI. Based on the clinical data provided, "
        "generate a concise diagnostic assessment in 2-3 sentences maximum. "
        "Start with the most likely diagnosis and key reasoning. Include differential diagnoses if relevant. "
        "Focus on what is clinically significant. Be direct and avoid lengthy explanations. "
        "Do not use bullet points or structured lists. Do not invent values not in the data."
    )

    prompt = (
        f"{system_prompt}\n\n"
        f"CLINICAL DATA:\n{clinical_context}\n\n"
        f"CONCISE DIAGNOSTIC ASSESSMENT:"
    )

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()
    except Exception as e:
        result_text = f"LLM service unavailable: {e}"

    return DiagnoseResponse(result=result_text, guidelines=guidelines, ml_risks=ml_risks)


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