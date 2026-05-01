import re
from typing import Dict, List, Optional, Tuple


def normalize_text(raw_text: str) -> str:
    """Clean spacing and normalize line breaks for lab text."""
    if raw_text is None:
        return ""

    text = raw_text.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]

    cleaned_lines: List[str] = []
    blank_seen = False

    for line in lines:
        if line == "":
            if not blank_seen:
                cleaned_lines.append("")
                blank_seen = True
        else:
            cleaned_lines.append(" ".join(line.split()))
            blank_seen = False

    return "\n".join(cleaned_lines).strip()


def _find_value_and_unit(window: str) -> Tuple[Optional[float], str]:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z/%°µμ]+(?:/[A-Za-z]+)?)?", window)
    if not match:
        return None, ""

    value = float(match.group(1))
    unit = (match.group(2) or "").strip()
    if unit:
        unit_lower = unit.lower()
        if not re.match(r"^(mg/dl|mmol/l|u/l|g/l|g/dl|%|fl|pg|x\s*10\^?12/l|x\s*10\^?9/l)$", unit_lower):
            unit = ""
    return value, unit


def _parse_reference_values(text: str, want_unit: Optional[str] = None) -> Tuple[Optional[float], Optional[float]]:
    text = text.lower()
    patterns = []
    if want_unit:
        unit = re.escape(want_unit.lower())
        patterns.append(rf"([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*{unit}")
        patterns.append(rf"less than\s*([0-9]+(?:\.[0-9]+)?)\s*{unit}")
        patterns.append(rf">\s*([0-9]+(?:\.[0-9]+)?)\s*{unit}")
    else:
        patterns.append(r"([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)")
        patterns.append(r"less than\s*([0-9]+(?:\.[0-9]+)?)")
        patterns.append(r">\s*([0-9]+(?:\.[0-9]+)?)")

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) == 2 and match.group(2) is not None:
                return float(match.group(1)), float(match.group(2))
            if len(match.groups()) == 1:
                return None, float(match.group(1))

    return None, None


def _parse_test(text: str, name: str, pattern: str, preferred_units: List[str]) -> Optional[Dict[str, object]]:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None

    window = text[match.end() : match.end() + 240]
    value, unit = _find_value_and_unit(window)
    if value is None:
        return None

    unit_lower = unit.lower()
    if not unit:
        for candidate in preferred_units:
            if candidate.lower() in window.lower():
                unit = candidate
                break

    reference_low, reference_high = None, None
    for candidate in preferred_units:
        reference_low, reference_high = _parse_reference_values(window, want_unit=candidate)
        if reference_low is not None or reference_high is not None:
            break

    if reference_low is None and reference_high is None:
        reference_low, reference_high = _parse_reference_values(window)

    return {
        "test_name": name,
        "value": value,
        "unit": unit,
        "reference_low": reference_low,
        "reference_high": reference_high,
    }


def _extract_lab_values(raw_text: str, tests: List[Tuple[str, str, List[str]]]) -> List[Dict[str, object]]:
    text = normalize_text(raw_text)
    candidates: List[Tuple[int, str, str, List[str]]] = []

    for name, pattern, units in tests:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            candidates.append((match.start(), name, pattern, units))

    candidates.sort(key=lambda item: item[0])
    results: List[Dict[str, object]] = []

    for index, (start, name, pattern, units) in enumerate(candidates):
        match = re.search(pattern, text[start:], re.IGNORECASE | re.DOTALL)
        if not match:
            continue

        end = len(text)
        if index + 1 < len(candidates):
            end = candidates[index + 1][0]

        segment = text[start:end]
        parsed = _parse_test(segment, name, pattern, units)
        if parsed:
            results.append(parsed)

    return results


def extract_chemistry_results(raw_text: str) -> List[Dict[str, object]]:
    tests = [
        ("CREATININE", r"creatinine", ["mg/dL"]),
        ("BLOOD URIC ACID", r"blood uric acid", ["mg/dL"]),
        ("FBS", r"(?:fbs|fasting blood sugar)", ["mg/dL"]),
        ("TOTAL CHOLESTEROL", r"total\s*cholesterol", ["mg/dL"]),
        ("TRIGLYCERIDES", r"triglycerides", ["mg/dL"]),
        ("HDL", r"\bhdl\b", ["mg/dL"]),
        ("LDL", r"\bldl\b", ["mg/dL"]),
        ("VLDL", r"\bvldl\b", ["mg/dL"]),
        ("CHOLESTEROL/HDL RATIO", r"cholesterol\s*/\s*hdl\s*ratio|cholesterol\s*hdl\s*ratio", []),
        ("SGPT/ALT", r"sgpt\s*/\s*alt|alt\b", ["U/L"]),
        ("SODIUM", r"sodium", ["mmol/L"]),
        ("POTASSIUM", r"potassium", ["mmol/L"]),
        ("CHLORIDE", r"chloride", ["mmol/L"]),
    ]
    return _extract_lab_values(raw_text, tests)


def extract_hematology_results(raw_text: str) -> List[Dict[str, object]]:
    tests = [
        ("HEMOGLOBIN", r"hemoglobin", ["g/L"]),
        ("HEMATOCRIT", r"hematocrit", ["%"]),
        ("RBC", r"r\.b\.c\.|rbc", ["x 10\^12/L"]),
        ("WBC", r"w\.b\.c\.|wbc", ["x 10\^9/L"]),
        ("PLATELET COUNT", r"platelet count", ["x 10\.9/L"]),
        ("MCV", r"\bmcv\b", ["fl"]),
        ("MCH", r"\bmch\b", ["pg"]),
        ("MCHC", r"\bmchc\b", ["g/dl"]),
    ]
    return _extract_lab_values(raw_text, tests)


def extract_microscopy_results(raw_text: str) -> List[Dict[str, object]]:
    tests = [
        ("COLOR", r"\bcolor\b", []),
        ("TRANSPARENCY", r"transparency", []),
        ("RBC", r"r\.b\.c\.|rbc", []),
        ("PUS CELLS", r"pus cells", []),
        ("BLOOD", r"\bblood\b", []),
        ("LEUKOCYTES", r"leukocytes", []),
        ("PH", r"\bph\b", []),
        ("SP. GRAVITY", r"sp\.\s*gravity", []),
    ]
    return _extract_lab_values(raw_text, tests)
