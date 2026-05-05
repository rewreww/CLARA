import requests
from typing import Any

CLEANER_URL = "http://localhost:8000"


# Tool definitions — these are what we show Ollama so it knows what's available.
# Each tool has a name, a description the AI reads, and the parameters it needs.
# Used for automatic full-lab pull (broad lab-review questions).
ALL_LAB_TOOL_NAMES = ("get_chemistry", "get_hematology", "get_microscopy")


TOOL_DEFINITIONS = [
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
]


def format_lab_results(data: dict, lab_type: str) -> str:
    """Turn raw lab JSON into a readable string block for the AI."""
    results = data.get("results", [])
    if not results:
        return f"No {lab_type} results found."

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
    return f"[{lab_type.upper()} RESULTS]\n" + "\n".join(lines)


def execute_tool(tool_name: str, patient_id: str) -> str:
    """
    Execute a tool by name and return its result as a formatted string.
    This is what actually calls your medical_text_api service.
    """
    try:
        if tool_name == "get_chemistry":
            r = requests.post(
                f"{CLEANER_URL}/chemistry-results",
                json={"patient": patient_id, "labs": "chemistry"},
                timeout=30
            )
            r.raise_for_status()
            return format_lab_results(r.json(), "chemistry")

        elif tool_name == "get_hematology":
            r = requests.post(
                f"{CLEANER_URL}/hematology-results",
                json={"patient": patient_id, "labs": "hematology"},
                timeout=30
            )
            r.raise_for_status()
            return format_lab_results(r.json(), "hematology")

        elif tool_name == "get_microscopy":
            r = requests.post(
                f"{CLEANER_URL}/microscopy-results",
                json={"patient": patient_id, "labs": "microscopy"},
                timeout=30
            )
            r.raise_for_status()
            return format_lab_results(r.json(), "microscopy")

        elif tool_name == "get_discharge":
            r = requests.post(
                f"{CLEANER_URL}/categorize",
                json={"patient": patient_id, "labs": "labs"},
                timeout=30
            )
            r.raise_for_status()
            discharge = r.json().get("discharge", "").strip()
            return f"[DISCHARGE SUMMARY]\n{discharge[:2000]}" if discharge \
                   else "No discharge summary found."

        elif tool_name == "get_all_labs":
            parts = []
            for sub in ALL_LAB_TOOL_NAMES:
                parts.append(execute_tool(sub, patient_id))
            return "\n\n".join(parts)

        else:
            return f"Unknown tool: {tool_name}"

    except requests.RequestException as e:
        return f"Error fetching {tool_name}: {str(e)}"


def build_tools_prompt() -> str:
    """
    Formats the tool list into plain text instructions for Ollama.
    Ollama 3.2:1b does not support native tool-use JSON,
    so we instruct it in the system prompt instead.
    """
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
        "- If the question is a broad lab review (any abnormals, all labs, worried about labs), "
        "call get_all_labs once instead of separate chemistry/hematology/microscopy calls.",
        "- Only call a tool if you need data you do not already have.",
        "- After receiving tool results, answer the doctor's question directly.",
        "- If you have enough data already, skip the tool and answer immediately.",
    ]
    return "\n".join(lines)


def fetch_all_lab_blocks(patient_id: str) -> list[tuple[str, str]]:
    """
    Run all three lab extractors. Returns [(tool_name, formatted_block), ...].
    Never raises — failed endpoints become error strings in the block.
    """
    out: list[tuple[str, str]] = []
    for sub in ALL_LAB_TOOL_NAMES:
        out.append((sub, execute_tool(sub, patient_id)))
    return out