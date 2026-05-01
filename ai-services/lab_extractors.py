"""
Lab Extractors Module

This module provides functions to extract structured lab results from raw text.
It handles chemistry, hematology, and microscopy tests with proper parsing of
values, units, and reference ranges.

Processing Steps:
1. Normalize the raw text (clean spacing, normalize line breaks)
2. Find all test matches in the text and sort by position
3. For each test, extract a segment from its position to the next test
4. Parse the value, unit, and references from the segment
5. Return structured results as list of dictionaries
"""

import re
from typing import Dict, List, Optional, Tuple


def normalize_text(raw_text: str) -> str:
    """
    Normalize raw lab text for consistent parsing.

    Steps:
    1. Replace various line break formats with \n
    2. Split into lines and strip whitespace
    3. Collapse multiple blank lines into single blank lines
    4. Join back into text

    Args:
        raw_text: The raw text from PDF extraction

    Returns:
        Normalized text with clean spacing
    """
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
    """
    Extract numeric value and unit from a text window.

    Uses regex to find patterns like "155 g/L" or "5.2 x 10^12/L".
    Validates units against allowed list.

    Args:
        window: Text segment to search for value and unit

    Returns:
        Tuple of (value as float or None, unit as string)
    """
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z0-9/%°µμ\s\^]+(?:/[A-Za-z]+)?)?", window)
    if not match:
        return None, ""

    value = float(match.group(1))
    unit = (match.group(2) or "").strip()
    if unit:
        unit_lower = unit.lower()
        if not re.match(r"^(mg/dl|mmol/l|u/l|g/l|g/dl|%|fl|pg|x\s*10\^?12/l|x\s*10\^?9/l|sec|mins?|mm/hr|x\s*10\^?12/L|x\s*10\^?9/L|x\s*10\^12/L|x\s*10\^9/L)$", unit_lower):
            unit = ""
    return value, unit


def _find_string_value(window: str) -> str:
    """
    Extract string value from a text window (for qualitative results).

    Cleans the text after the test name, removing leading colon and whitespace.

    Args:
        window: Text segment after the test match

    Returns:
        Cleaned string value
    """
    # Remove leading/trailing whitespace and colon if present
    value = window.strip()
    if value.startswith(':'):
        value = value[1:].strip()
    return value


def _parse_reference_values(text: str, want_unit: Optional[str] = None) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse reference ranges from text, like "(120-160)" or "less than 20".

    Handles formats: "120-160", "less than 20", "> 10"
    Can filter by specific unit if provided.

    Args:
        text: Text to search for references
        want_unit: Optional unit to match (e.g., "mg/dL")

    Returns:
        Tuple of (low, high) or (None, high) for "less than"
    """
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


def _parse_test(text: str, name: str, pattern: str, preferred_units: List[str], is_string: bool = False) -> Optional[Dict[str, object]]:
    """
    Parse a single test from the text segment.

    Steps:
    1. Find the test pattern match
    2. Extract window after the match
    3. Get value (numeric or string) and unit
    4. Parse reference ranges
    5. Return structured result or None if no value found

    Args:
        text: Text segment containing the test
        name: Test name
        pattern: Regex pattern to match test
        preferred_units: List of possible units for this test
        is_string: Whether this test has string value (qualitative)

    Returns:
        Dict with test_name, value, unit, references or None
    """
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None

    window = text[match.end() : match.end() + 240]
    if is_string:
        value = _find_string_value(window)
        unit = ""
    else:
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


def _extract_lab_values(raw_text: str, tests: List[Tuple[str, str, List[str], bool]]) -> List[Dict[str, object]]:
    """
    Main extraction function for lab values.

    Steps:
    1. Normalize the input text
    2. Find all test matches and sort by position (to handle order)
    3. For each test, create a segment from its position to the next test
    4. Parse each segment individually
    5. Collect successful parses into results list

    Args:
        raw_text: Raw lab text
        tests: List of (name, pattern, units, is_string) tuples

    Returns:
        List of parsed test results
    """
    text = normalize_text(raw_text)
    candidates: List[Tuple[int, str, str, List[str], bool]] = []

    for name, pattern, units, is_string in tests:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            candidates.append((match.start(), name, pattern, units, is_string))

    candidates.sort(key=lambda item: item[0])
    results: List[Dict[str, object]] = []

    for index, (start, name, pattern, units, is_string) in enumerate(candidates):
        match = re.search(pattern, text[start:], re.IGNORECASE | re.DOTALL)
        if not match:
            continue

        end = len(text)
        if index + 1 < len(candidates):
            end = candidates[index + 1][0]

        segment = text[start:end]
        parsed = _parse_test(segment, name, pattern, units, is_string)
        if parsed:
            results.append(parsed)

    return results


def extract_chemistry_results(raw_text: str) -> List[Dict[str, object]]:
    """
    Extract chemistry lab results.

    Tests include metabolic panel, lipids, enzymes, electrolytes.
    All are numeric values with units and references.
    """
    tests = [
        ("CREATININE", r"creatinine", ["mg/dL"], False),
        ("BLOOD URIC ACID", r"blood uric acid", ["mg/dL"], False),
        ("FBS", r"(?:fbs|fasting blood sugar)", ["mg/dL"], False),
        ("TOTAL CHOLESTEROL", r"total\s*cholesterol", ["mg/dL"], False),
        ("TRIGLYCERIDES", r"triglycerides", ["mg/dL"], False),
        ("HDL", r"\bhdl\b", ["mg/dL"], False),
        ("LDL", r"\bldl\b", ["mg/dL"], False),
        ("VLDL", r"\bvldl\b", ["mg/dL"], False),
        ("CHOLESTEROL/HDL RATIO", r"cholesterol\s*/\s*hdl\s*ratio|cholesterol\s*hdl\s*ratio", [], False),
        ("SGPT/ALT", r"sgpt\s*/\s*alt|alt\b", ["U/L"], False),
        ("SODIUM", r"sodium", ["mmol/L"], False),
        ("POTASSIUM", r"potassium", ["mmol/L"], False),
        ("CHLORIDE", r"chloride", ["mmol/L"], False),
    ]
    return _extract_lab_values(raw_text, tests)


def extract_hematology_results(raw_text: str) -> List[Dict[str, object]]:
    """
    Extract hematology lab results.

    Includes CBC parameters, coagulation tests, blood grouping.
    Mix of numeric values and string results (blood types, remarks).
    """
    tests = [
        ("HEMOGLOBIN", r"hemoglobin", ["g/L"], False),
        ("HEMATOCRIT", r"hematocrit", ["%"], False),
        ("RBC", r"r\.b\.c\.|rbc", ["x 10\^12/L"], False),
        ("WBC", r"w\.b\.c\.|wbc", ["x 10\^9/L"], False),
        ("NEUTROPHILS", r"neutrophils", ["%"], False),
        ("LYMPHOCYTES", r"lymphocytes", ["%"], False),
        ("MONOCYTES", r"monocytes", ["%"], False),
        ("EOSINOPHILS", r"eosinophils", ["%"], False),
        ("BASOPHILS", r"basophils", ["%"], False),
        ("STABS", r"stabs", ["%"], False),
        ("PLATELET COUNT", r"platelet count", ["x 10\^9/L"], False),
        ("MCV", r"\bmcv\b", ["fl"], False),
        ("MCH", r"\bmch\b", ["pg"], False),
        ("MCHC", r"\bmchc\b", ["g/dl"], False),
        ("ESR", r"\besr\b", ["mm/hr"], False),
        ("BLEEDING TIME", r"bleeding time", ["min"], False),
        ("CLOTTING TIME", r"clotting time", ["min"], False),
        ("PROTIME CONTROL TEST", r"protime control test", ["sec"], False),
        ("%ACT INR", r"%act inr", [], False),
        ("APTT CONTROL TEST", r"aptt control test", ["sec"], False),
        ("ABO TYPE", r"abo type", [], True),
        ("RH TYPE", r"rh type", [], True),
        ("REMARKS", r"remarks", [], True),
    ]
    return _extract_lab_values(raw_text, tests)


def extract_microscopy_results(raw_text: str) -> List[Dict[str, object]]:
    """
    Extract urine microscopy results.

    Includes physical examination, chemical tests, and microscopic findings.
    Mix of qualitative strings and quantitative counts.
    """
    tests = [
        ("COLOR", r"\bcolor\b", [], True),
        ("TRANSPARENCY", r"transparency", [], True),
        ("RBC", r"r\.b\.c\.|rbc", [], False),
        ("PUS CELLS", r"pus cells", [], False),
        ("LEUKOCYTES", r"leukocytes", [], False),
        ("PH", r"\bph\b", [], False),
        ("SP. GRAVITY", r"sp\.\s*gravity", [], False),
        ("EPITHELIAL CELLS", r"epithelial cells", [], True),
        ("HYALINE", r"hyaline", [], True),
        ("FINE GRANULAR", r"fine granular", [], True),
        ("COARSE GRANULAR", r"coarse granular", [], True),
        ("BILIRUBIN", r"bilirubin", [], True),
        ("MUCUS THREADS", r"mucus threads", [], True),
        ("UROBILINOGEN", r"urobilinogen", [], True),
        ("YEAST CELLS", r"yeast cells", [], True),
        ("RENAL CELLS", r"renal cells", [], True),
        ("KETONE", r"ketone", [], True),
        ("PROTEIN", r"protein", [], True),
        ("NITRITE", r"nitrite", [], True),
        ("GLUCOSE", r"glucose", [], True),
        ("URINE PREGNANCY TEST", r"urine pregnancy test", [], True),
        ("URINE MICRAL TEST", r"urine micral test", ["mg/L"], True),
        ("AMORPHOUS URATES", r"amorphous urates", [], True),
        ("URIC ACID", r"uric acid", [], True),
        ("CALCIUM OXALATE", r"calcium oxalate", [], True),
        ("AMORPHOUS PHOSPHATES", r"amorphous phosphates", [], True),
        ("TRIPLE PHOSPHATES", r"triple phosphates", [], True),
    ]
    return _extract_lab_values(raw_text, tests)
