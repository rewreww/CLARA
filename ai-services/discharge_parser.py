"""
CLARA discharge summary parser.

Parses common discharge-summary headings into stable fields for the API and UI.
The parser is section-aware so Final Diagnosis stops at the next recognized
heading instead of swallowing Chief Complaint, HPI, PMH, PE, or lab sections.
"""

import json
import re
from typing import Optional


def empty_schema() -> dict:
    return {
        "condition_discharge": None,
        "chief_complaint": None,
        "admitting_dx": None,
        "final_dx": None,
        "hpi": None,
        "pmh": None,
        "physical_exam": {
            "vitals": None,
            "findings": None,
        },
        "laboratory_data": None,
        "labs": [],
        "hospital_course": [],
    }


SECTION_PATTERNS = [
    ("condition_discharge", r"condition\s+upon\s+discharge"),
    ("chief_complaint", r"chief\s+complaint"),
    ("admitting_dx", r"admitting\s+diagnosis"),
    ("final_dx", r"final\s+diagnosis"),
    ("hpi", r"history\s+of\s+present\s+illness"),
    ("pmh", r"past\s+(?:medical\s+)?history"),
    ("physical_exam", r"physical\s+exam(?:ination)?"),
    ("laboratory_data", r"laboratory\s+(?:data|results?)"),
    ("hospital_course", r"(?:hospital\s+course|course\s+in\s+the\s+ward|course\s+in\s+ward)"),
]

SECTION_RE = re.compile(
    r"(?im)(?:^|\n)\s*("
    + "|".join(pattern for _, pattern in SECTION_PATTERNS)
    + r")\s*:?\s*"
)


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[|]{2,}", " ", text)
    text = re.sub(r"_{3,}", " ", text)
    text = re.sub(r"\.{4,}", " ", text)
    text = re.sub(r"-{3,}", " ", text)
    text = re.sub(r"\x00", "", text)
    text = re.sub(r"[^\x09\x0A\x20-\x7E]", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_field(text: Optional[str]) -> Optional[str]:
    if not text or not text.strip():
        return None

    return re.sub(r"\s+", " ", text).strip()


def section_key(label: str) -> Optional[str]:
    for key, pattern in SECTION_PATTERNS:
        if re.fullmatch(pattern, label.strip(), flags=re.IGNORECASE):
            return key
    return None


def extract_sections(text: str) -> dict:
    matches = []
    for match in SECTION_RE.finditer(text):
        key = section_key(match.group(1))
        if key:
            matches.append((key, match.start(), match.end()))

    sections = {}
    for index, (key, _heading_start, content_start) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text)
        content = text[content_start:next_start].strip(" :\n\t")
        if content:
            sections.setdefault(key, content)

    return sections


def extract_physical_exam(section_text: Optional[str]) -> dict:
    exam = {
        "vitals": None,
        "findings": None,
    }

    text = clean_field(section_text)
    if not text:
        return exam

    vitals_match = re.match(r"(?P<vitals>.*?\d{2,3}\s*%\.?)\s*(?P<rest>.*)", text)
    if vitals_match and re.search(
        r"\b(?:BP|HR|RR|TEMP|SPO2|PR)\b|(?:\d{2,3}/\d{2,3})|(?:\s>\s)",
        vitals_match.group("vitals"),
        re.IGNORECASE,
    ):
        exam["vitals"] = vitals_match.group("vitals").strip()
        exam["findings"] = vitals_match.group("rest").strip() or None
    else:
        exam["findings"] = text

    return exam


def parse_flag(raw_flag: Optional[str]) -> Optional[str]:
    if not raw_flag:
        return None

    flag = raw_flag.strip().lower()
    if flag in ["h", "high"]:
        return "high"
    if flag in ["l", "low"]:
        return "low"
    return "abnormal"


def extract_labs(section_text: Optional[str]) -> list:
    if not section_text:
        return []

    labs = []
    item_re = re.compile(
        r"(?P<test>[A-Za-z][A-Za-z0-9 /+^-]*?)"
        r"(?:\s*\((?P<date>\d{2}/\d{2})\))?\s*:\s*"
        r"(?P<value>.*?)(?=\s+[A-Za-z][A-Za-z0-9 /+^-]*?"
        r"(?:\s*\(\d{2}/\d{2}\))?\s*:|$)",
        re.IGNORECASE,
    )

    for match in item_re.finditer(section_text):
        test = match.group("test").strip(" .;")
        value = match.group("value").strip(" .;")
        flag_match = re.search(r"\((H|HIGH|L|LOW|ABNORMAL)\)$", value, re.IGNORECASE)
        if flag_match:
            value = value[:flag_match.start()].strip()

        unit_match = re.match(
            r"(?P<val>[<>]?\s*\d+(?:\.\d+)?)"
            r"(?:\s*(?P<unit>[A-Za-z/%^0-9]+(?:/[A-Za-z0-9^]+)?))?$",
            value,
        )

        labs.append({
            "test": clean_field(test),
            "date": match.group("date"),
            "val": unit_match.group("val").strip() if unit_match else value,
            "unit": unit_match.group("unit") if unit_match else None,
            "flag": parse_flag(flag_match.group(1) if flag_match else None),
        })

    return labs


def extract_hospital_course(text: Optional[str]) -> list:
    if not text:
        return []

    pattern = re.compile(
        r"((?:on\s+the\s+day\s+of\s+admission)|"
        r"(?:(?:on\s+the\s+)?\d+(?:st|nd|rd|th)?\s+hospital\s+day))"
        r"\s*\((\d{2}/\d{2})\)",
        re.IGNORECASE,
    )

    matches = list(pattern.finditer(text))
    results = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        results.append({
            "label": clean_field(match.group(1)),
            "date": match.group(2),
            "content": clean_field(content),
        })

    return results


def parse_discharge(raw_text: str) -> dict:
    schema = empty_schema()

    if not raw_text or not raw_text.strip():
        return schema

    text = normalize_text(raw_text)
    sections = extract_sections(text)

    for key in [
        "condition_discharge",
        "chief_complaint",
        "admitting_dx",
        "final_dx",
        "hpi",
        "pmh",
        "laboratory_data",
    ]:
        schema[key] = clean_field(sections.get(key))

    schema["physical_exam"] = extract_physical_exam(sections.get("physical_exam"))
    schema["labs"] = extract_labs(sections.get("laboratory_data"))
    schema["hospital_course"] = extract_hospital_course(sections.get("hospital_course") or text)

    return schema


def parse_discharge_to_json(raw_text: str) -> str:
    return json.dumps(parse_discharge(raw_text), indent=2, ensure_ascii=False)
