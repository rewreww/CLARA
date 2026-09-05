import requests
import os
import time
from urllib.parse import quote

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:5000/api/patientdata").rstrip("/")
PATIENT_DATA_CACHE_SECONDS = max(0, int(os.getenv("PATIENT_DATA_CACHE_SECONDS", "5")))

ALL_LAB_TOOL_NAMES = ("get_chemistry", "get_hematology", "get_microscopy")
PATIENT_CONTEXT_TOOL_NAME = "get_patient_context"
_TOOL_CACHE: dict[tuple[str, str], tuple[float, str]] = {}

TOOL_DEFINITIONS = [
    {
        "name": PATIENT_CONTEXT_TOOL_NAME,
        "description": (
            "Fetches a compact RAG-ready clinical context for a patient from PostgreSQL, "
            "including demographics, diagnoses, medications, abnormal labs, recent labs, "
            "and latest discharge summary. Prefer this for broad patient, diagnosis, "
            "medication, management, or summary questions."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_abnormal_labs",
        "description": (
            "Fetches only the abnormal lab section from the patient's structured context. "
            "Use this for questions about critical, high, low, concerning, or out-of-range lab values."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_recent_labs",
        "description": (
            "Fetches the compact recent-lab section from the patient's structured context. "
            "Use this for quick lab summaries when exact per-lab reference ranges are not required."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_diagnoses",
        "description": "Fetches documented diagnoses from the patient's structured PostgreSQL context.",
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_medications",
        "description": "Fetches documented medications from the patient's structured PostgreSQL context.",
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_latest_discharge_summary",
        "description": "Fetches the latest discharge-summary section from the patient's structured PostgreSQL context.",
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_chemistry",
        "description": (
            "Fetches clinical chemistry lab results for a patient. "
            "Use this when the doctor asks about blood sugar, cholesterol, "
            "creatinine, electrolytes, liver enzymes, or kidney function."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_hematology",
        "description": (
            "Fetches hematology lab results for a patient. "
            "Use this when the doctor asks about blood counts, hemoglobin, "
            "WBC, RBC, platelets, clotting time, or bleeding time."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_microscopy",
        "description": (
            "Fetches urinalysis and microscopy results for a patient. "
            "Use this when the doctor asks about urine results, pus cells, "
            "protein, glucose in urine, or kidney-related urinalysis findings."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_discharge",
        "description": (
            "Fetches the discharge summary for a patient. "
            "Use this when the doctor asks about diagnosis, discharge notes, "
            "clinical history, or what happened during the hospital stay."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_all_labs",
        "description": (
            "Fetches chemistry, hematology, AND microscopy/urinalysis in one step. "
            "Use this when the doctor asks for a broad lab review: any abnormalities, "
            "labs to worry about, screening all results, or overview of laboratory data."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001"
        }
    },
    {
        "name": "get_trends",
        "description": (
            "Fetches lab results across multiple dates for a patient to show trends over time. "
            "Use this when the doctor asks about changes, trends, improvement, worsening, "
            "or comparison of lab values over time."
        ),
        "parameters": {
            "patient_id": "The patient folder ID, e.g. 00001",
            "lab_type":   "One of: chemistry, hematology, microscopy"
        }
    },
]


def _to_float(val) -> "float | None":
    """Coerce string numbers to float for comparison; returns None if not numeric."""
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None


def _ref_text(low, high) -> str:
    """Format reference range — handles all four cases including lower-bound-only."""
    if low is not None and high is not None:
        return f" (ref: {low}–{high})"
    if high is not None:
        return f" (ref: <{high})"
    if low is not None:
        return f" (ref: >{low})"
    return ""


def format_lab_results(data: dict, lab_type: str) -> str:
    """Turn raw lab JSON into a readable string block for the AI."""
    results = data.get("results", [])
    if not results:
        return f"No {lab_type} results found."

    lines    = []
    abnormal = []

    for result in results:
        low     = result.get("reference_low")
        high    = result.get("reference_high")
        ref     = _ref_text(low, high)
        has_ref = low is not None or high is not None

        # Coerce value to float so string numbers like "72" are still compared
        numeric = _to_float(result.get("value"))

        flag = ""
        if numeric is not None:
            if high is not None and numeric > high:
                flag = " *** HIGH ***"
                abnormal.append(
                    f"{result['test_name']}: {result['value']} {result['unit']}{ref} *** HIGH ***"
                )
            elif low is not None and numeric < low:
                flag = " *** LOW ***"
                abnormal.append(
                    f"{result['test_name']}: {result['value']} {result['unit']}{ref} *** LOW ***"
                )
            elif has_ref:
                flag = " [WITHIN RANGE]"   # explicit normal — model must not override this

        lines.append(
            f"  {result['test_name']}: {result['value']} {result['unit']}{ref}{flag}".strip()
        )

    output = f"[{lab_type.upper()} RESULTS]\n" + "\n".join(lines)

    # Append a clear abnormal summary so the LLM can't miss flagged values
    if abnormal:
        output += f"\n\n[ABNORMAL {lab_type.upper()} VALUES — THESE REQUIRE ATTENTION]\n"
        output += "\n".join(f"  ! {a}" for a in abnormal)
    else:
        output += f"\n\n[ALL {lab_type.upper()} VALUES WITHIN RANGE — NO ABNORMALITIES]"

    return output


def fetch_patient_context(patient_id: str) -> str:
    patient_path = quote(str(patient_id).strip(), safe="")
    r = requests.get(f"{DATA_SERVICE_URL}/{patient_path}/rag-context", timeout=30)
    r.raise_for_status()
    data = r.json()
    context = str(data.get("context") or "").strip()
    return context if context else "No patient context found."


def fetch_patient_document_context(patient_id: str, query: str) -> tuple[str, list[dict]]:
    patient_path = quote(str(patient_id).strip(), safe="")
    r = requests.get(
        f"{DATA_SERVICE_URL}/{patient_path}/document-context",
        params={"query": query or ""},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    context = str(data.get("context") or "").strip()
    sources = data.get("sources") or []
    return context if context else "No extracted patient PDF text found.", sources


def _context_section(patient_id: str, header: str, empty_message: str) -> str:
    context = fetch_patient_context(patient_id)
    lines = context.splitlines()
    selected: list[str] = []
    collecting = False

    for line in lines:
        stripped = line.strip()
        if stripped == header:
            collecting = True
            continue
        if collecting and stripped.startswith("[") and stripped.endswith("]"):
            break
        if collecting and stripped:
            selected.append(stripped)

    if not selected:
        return empty_message
    return f"{header}\n" + "\n".join(selected)


def _cache_get(tool_name: str, patient_id: str) -> str | None:
    if PATIENT_DATA_CACHE_SECONDS <= 0:
        return None

    entry = _TOOL_CACHE.get((tool_name, patient_id))
    if not entry:
        return None

    cached_at, value = entry
    if time.monotonic() - cached_at > PATIENT_DATA_CACHE_SECONDS:
        _TOOL_CACHE.pop((tool_name, patient_id), None)
        return None

    return value


def _cache_set(tool_name: str, patient_id: str, value: str) -> str:
    if PATIENT_DATA_CACHE_SECONDS > 0:
        _TOOL_CACHE[(tool_name, patient_id)] = (time.monotonic(), value)
    return value


def execute_tool(tool_name: str, patient_id: str) -> str:
    patient_id = str(patient_id or "").strip()
    cached = _cache_get(tool_name, patient_id)
    if cached is not None:
        return cached

    try:
        if tool_name == PATIENT_CONTEXT_TOOL_NAME:
            return _cache_set(tool_name, patient_id, fetch_patient_context(patient_id))

        elif tool_name == "get_abnormal_labs":
            return _cache_set(tool_name, patient_id, _context_section(patient_id, "[ABNORMAL LABS]", "No abnormal labs found in patient context."))

        elif tool_name == "get_recent_labs":
            return _cache_set(tool_name, patient_id, _context_section(patient_id, "[RECENT LABS]", "No recent labs found in patient context."))

        elif tool_name == "get_diagnoses":
            return _cache_set(tool_name, patient_id, _context_section(patient_id, "[DIAGNOSES]", "No diagnoses found in patient context."))

        elif tool_name == "get_medications":
            return _cache_set(tool_name, patient_id, _context_section(patient_id, "[MEDICATIONS]", "No medications found in patient context."))

        elif tool_name == "get_latest_discharge_summary":
            return _cache_set(tool_name, patient_id, _context_section(
                patient_id,
                "[LATEST DISCHARGE SUMMARY]",
                "No latest discharge summary found in patient context.",
            ))

        elif tool_name == "get_chemistry":
            r = requests.post(
                f"{DATA_SERVICE_URL}/chemistry-results",
                json={"patient": patient_id, "labs": "chemistry"},
                timeout=30
            )
            r.raise_for_status()
            return _cache_set(tool_name, patient_id, format_lab_results(r.json(), "chemistry"))

        elif tool_name == "get_hematology":
            r = requests.post(
                f"{DATA_SERVICE_URL}/hematology-results",
                json={"patient": patient_id, "labs": "hematology"},
                timeout=30
            )
            r.raise_for_status()
            return _cache_set(tool_name, patient_id, format_lab_results(r.json(), "hematology"))

        elif tool_name == "get_microscopy":
            r = requests.post(
                f"{DATA_SERVICE_URL}/microscopy-results",
                json={"patient": patient_id, "labs": "microscopy"},
                timeout=30
            )
            r.raise_for_status()
            return _cache_set(tool_name, patient_id, format_lab_results(r.json(), "microscopy"))

        elif tool_name == "get_discharge":
            r = requests.post(
                f"{DATA_SERVICE_URL}/discharge-parsed",
                json={"patient": patient_id},
                timeout=30
            )
            r.raise_for_status()
            data = r.json()
            if not data.get("found"):
                return _cache_set(tool_name, patient_id, "No discharge summary found.")
            pieces = [
                data.get("final_dx"),
                data.get("admitting_dx"),
                data.get("hpi"),
                data.get("pmh"),
                data.get("followup"),
            ]
            discharge = "\n".join(str(piece).strip() for piece in pieces if piece)
            return _cache_set(tool_name, patient_id, f"[DISCHARGE SUMMARY]\n{discharge[:2000]}" if discharge else "No discharge summary found.")

        elif tool_name == "get_all_labs":
            parts = []
            for sub in ALL_LAB_TOOL_NAMES:
                parts.append(execute_tool(sub, patient_id))
            return _cache_set(tool_name, patient_id, "\n\n".join(parts))

        elif tool_name == "get_trends":
            try:
                r = requests.post(
                    f"{DATA_SERVICE_URL}/labs-timeline",
                    json={"patient": patient_id, "lab_type": "chemistry"},
                    timeout=30
                )
                r.raise_for_status()
                data     = r.json()
                timeline = data.get("timeline", [])
                if not timeline:
                    return _cache_set(tool_name, patient_id, "No trend data found — ensure labs are stored in date subfolders (YYYY-MM-DD).")

                lines = ["[LAB TRENDS OVER TIME — CHEMISTRY]"]
                for entry in timeline:
                    lines.append(f"\n  Date: {entry['date']}")
                    for res in entry["results"]:
                        low  = res.get("reference_low")
                        high = res.get("reference_high")
                        numeric = _to_float(res.get("value"))
                        flag = ""
                        if numeric is not None:
                            if high is not None and numeric > high: flag = " *** HIGH ***"
                            elif low is not None and numeric < low: flag = " *** LOW ***"
                        lines.append(f"    {res['test_name']}: {res['value']} {res['unit']}{flag}")
                return _cache_set(tool_name, patient_id, "\n".join(lines))
            except requests.RequestException as e:
                return f"Error fetching trends: {str(e)}"

        else:
            return f"Unknown tool: {tool_name}"

    except requests.RequestException as e:
        return f"Error fetching {tool_name}: {str(e)}"


def build_tools_prompt() -> str:
    lines = [
        "You have access to the following tools to look up patient data.",
        "To use a tool, respond ONLY with this exact format on its own line:",
        "TOOL: <tool_name> PATIENT: <patient_id>",
        "",
        "Available tools:",
    ]
    for tool in TOOL_DEFINITIONS:
        lines.append(f"- {tool['name']}: {tool['description']}")
    lines += [
        "",
        "Rules for tool use:",
        "- For broad clinical questions about the patient, start with get_patient_context.",
        "- For focused patient facts, use the narrow context tools: get_abnormal_labs, "
        "get_recent_labs, get_diagnoses, get_medications, or get_latest_discharge_summary.",
        "- If the question is a broad lab review (any abnormals, all labs, worried about labs), "
        "call get_all_labs once instead of separate chemistry/hematology/microscopy calls.",
        "- Only call a tool if you need data you do not already have.",
        "- After receiving tool results, answer the doctor's question directly.",
        "- If you have enough data already, skip the tool and answer immediately.",
    ]
    return "\n".join(lines)


def fetch_all_lab_blocks(patient_id: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for sub in ALL_LAB_TOOL_NAMES:
        out.append((sub, execute_tool(sub, patient_id)))
    return out


def fetch_patient_context_block(patient_id: str) -> tuple[str, str]:
    return PATIENT_CONTEXT_TOOL_NAME, execute_tool(PATIENT_CONTEXT_TOOL_NAME, patient_id)
