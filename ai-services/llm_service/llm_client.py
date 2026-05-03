import re
import sys
import os
import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from collections import defaultdict

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from mcp_tools import TOOL_DEFINITIONS, execute_tool, build_tools_prompt
from rag.retriever import retrieve_guidelines
from rule_engine.rules import rule_engine

app = FastAPI()

OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:1b"

conversation_store: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 10

SYSTEM_PROMPT = """You are CLARA, a clinical AI assistant specialized in cardiovascular case assessment.
Your job is to help doctors interpret lab findings, identify trends, and flag concerns.

Rules you must follow:
- Always cite specific lab values when making a statement.
- Flag any value marked *** HIGH *** or *** LOW *** explicitly.
- If data is missing or unclear, say so — do not guess.
- Do not prescribe or give final diagnoses — support the doctor's judgment.
- Where relevant, reference the clinical guidelines provided to support your answer.
- You have memory of the current conversation — use it to answer follow-up questions.
- Be concise. Doctors are busy.

{tools_section}"""


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
    """Fetch lab results and evaluate clinical rules."""
    all_results = []
    for lab_type in ["chemistry", "hematology"]:
        try:
            r = requests.post(
                f"http://localhost:8000/{lab_type}-results",
                json={"patient": patient_id, "labs": lab_type},
                timeout=30
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            all_results.extend(results)
        except Exception:
            continue
    return rule_engine.evaluate_labs(all_results)

    # Print exact test names so we can see what the rule engine receives
    print(f"[RULE ENGINE] Test names in data:")
    for result in all_results:
        print(f"  '{result.get('test_name')}' = {result.get('value')} {result.get('unit')}")

    print(f"[RULE ENGINE] Total results: {len(all_results)}")
    rule_result = rule_engine.evaluate_labs(all_results)
    print(f"[RULE ENGINE] Flags: {rule_result.get('flags', [])}")
    return rule_result


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
        "If you need patient data, call a tool using the format: "
        "TOOL: <tool_name> PATIENT: <patient_id>"
    )
    parts.append(
        "If you already have enough to answer, answer directly. "
        "Use conversation history above to answer follow-up questions."
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

    # 5. Build initial prompt using safe helper
    prompt = build_prompt(
        system, guidelines, emergency_block,
        history_block, request.patient_id, request.message
    )

    final_response = "I was unable to generate a response."

    # 6. Tool-use loop
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
            "Now answer the doctor's question directly using this data.",
            "Do not call another tool unless the question requires data you still do not have.",
            "Begin your answer with the clinical finding.",
            "Do not repeat the patient ID or question.",
            ""
        ])

    # 7. Save to memory
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