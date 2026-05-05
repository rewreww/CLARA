import re
import sys
import os
import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from collections import defaultdict

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

OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:1b"

conversation_store: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 10

SYSTEM_PROMPT = """You are CLARA, a clinical AI assistant specialized in cardiovascular assessment.

STRICT RULES:
- You MUST call all relevant tools to retrieve patient data before answering ANY clinical question.
- Do NOT answer without data unless explicitly told no data is available.
- Do NOT rely only on ***HIGH*** or ***LOW*** flags — interpret their clinical meaning.

When analyzing labs:
1. Identify abnormal values (HIGH/LOW)
2. Explain WHY they are clinically significant
3. Link abnormalities to possible conditions or risks
4. Prioritize findings (most concerning first)
5. Reference exact values and units
6. If multiple abnormalities exist, explain relationships between them

Output style:
- Start with the most critical finding
- Be concise but clinically meaningful
- Avoid generic statements like "this is high" — always explain impact

If data is incomplete:
- Clearly state what is missing and what is needed

When [ALL LAB DATA — PRELOADED] appears in the prompt, that data is already complete for chemistry, hematology, and urinalysis/microscopy — answer from it. Do not ask the doctor to call tools for those labs.{tools_section}"""


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


def call_ollama(prompt: str) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
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


def wants_full_lab_scan(message: str) -> bool:
    """
    Detect questions that imply reviewing the full laboratory picture, so we can
    preload all lab modalities without relying on the LLM to chain tool calls.
    """
    if not message or not message.strip():
        return False
    return bool(_LAB_TOPIC.search(message) and _BROAD_LAB_ASK.search(message))


def build_prompt(
    system: str,
    guidelines: str,
    emergency_block: str,
    history_block: str,
    patient_id: str,
    message: str
) -> str:
    """Build the full prompt as a single clean concatenation."""
    parts = [system, ""]

    if guidelines:
        parts.append(guidelines)
        parts.append("")

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

    # 1. Retrieve relevant guidelines
    guidelines = retrieve_guidelines(request.message)
    guidelines_used = (
        "No relevant guideline" not in guidelines
        and "not initialised"   not in guidelines
        and "not found"         not in guidelines
    )

    # 2. Run rule engine — always runs regardless of LLM tool calls
    rule_result  = run_rule_engine(request.patient_id)
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
    if pid and wants_full_lab_scan(request.message):
        preload_lines = [
            "[ALL LAB DATA — PRELOADED BY SERVER]",
            "The following blocks contain chemistry, hematology, and microscopy/urinalysis (when available).",
            "Interpret abnormalities with clinical context. Cite specific values and *** HIGH *** / *** LOW *** flags.",
            "",
        ]
        for tool_name, block in fetch_all_lab_blocks(pid):
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

    # 7. Tool-use loop
    for _ in range(4):
        response_text = call_ollama(prompt)
        tool_call     = parse_tool_call(response_text)

        if tool_call is None:
            final_response = clean_response(response_text)

            if not final_response and collected_data:
                retry_prompt = "\n".join([
                    system, "",
                    guidelines, "",
                    emergency_block, "",
                    "Patient data already retrieved:",
                    "\n\n".join(collected_data), "",
                    f"Answer this question: {request.message}",
                    "Be concise. Start with the clinical finding."
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
            "Now analyze the retrieved lab data clinically:"
            "Identify abnormal values"
            "Explain their significance"
            "Prioritize risks"
            "Reference exact values and units"
            "Do not just label HIGH/LOW — interpret them medically"
            "Start with the most critical issue"
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