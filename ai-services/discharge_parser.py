"""
CLARA — Discharge Summary Parser
=================================
Converts raw hospital PDF text into structured JSON.

Input  : unstructured discharge summary string
Output : dict matching the DischargeSchema

Place this file at:
  C:\\clara-system\\ai-services\\discharge_parser.py

Usage:
  from discharge_parser import parse_discharge
  result = parse_discharge(raw_text)
"""

import re
from typing import Optional


# ── Schema ────────────────────────────────────────────────────────────────────

def empty_schema() -> dict:
    return {
        "condition_discharge": None,
        "chief_complaint":     None,
        "admitting_dx":        None,
        "final_dx":            None,
        "hpi":                 None,
        "pmh":                 None,
        "physical_exam": {
            "vitals":   None,
            "findings": None,
        },
        "labs": [],
    }


# ── Abbreviation expansion table ──────────────────────────────────────────────

ABBREV = {
    r"\bPTA\b":    "prior to admission",
    r"\bCC\b":     "chief complaint",
    r"\bHPI\b":    "history of present illness",
    r"\bPMH\b":    "past medical history",
    r"\bHTN\b":    "hypertension",
    r"\bDM\b":     "diabetes mellitus",
    r"\bDM2\b":    "type 2 diabetes mellitus",
    r"\bT2DM\b":   "type 2 diabetes mellitus",
    r"\bCAD\b":    "coronary artery disease",
    r"\bCHF\b":    "congestive heart failure",
    r"\bAMI\b":    "acute myocardial infarction",
    r"\bMI\b":     "myocardial infarction",
    r"\bCVA\b":    "cerebrovascular accident",
    r"\bSOB\b":    "shortness of breath",
    r"\bCP\b":     "chest pain",
    r"\bBP\b":     "blood pressure",
    r"\bHR\b":     "heart rate",
    r"\bRR\b":     "respiratory rate",
    r"\bO2\b":     "oxygen",
    r"\bO2 sat\b": "oxygen saturation",
    r"\bSpO2\b":   "oxygen saturation",
    r"\bTemp\b":   "temperature",
    r"\bWt\b":     "weight",
    r"\bHt\b":     "height",
    r"\bBMI\b":    "body mass index",
    r"\bFBS\b":    "fasting blood sugar",
    r"\bRBS\b":    "random blood sugar",
    r"\bCBC\b":    "complete blood count",
    r"\bWBC\b":    "white blood cell count",
    r"\bRBC\b":    "red blood cell count",
    r"\bHgb\b":    "hemoglobin",
    r"\bHGB\b":    "hemoglobin",
    r"\bHct\b":    "hematocrit",
    r"\bHCT\b":    "hematocrit",
    r"\bPlt\b":    "platelet count",
    r"\bPLT\b":    "platelet count",
    r"\bCr\b":     "creatinine",
    r"\bBUN\b":    "blood urea nitrogen",
    r"\bNa\b":     "sodium",
    r"\bK\b":      "potassium",
    r"\bCl\b":     "chloride",
    r"\bCO2\b":    "carbon dioxide",
    r"\bAST\b":    "aspartate aminotransferase",
    r"\bALT\b":    "alanine aminotransferase",
    r"\bALP\b":    "alkaline phosphatase",
    r"\bLDH\b":    "lactate dehydrogenase",
    r"\bLDL\b":    "low-density lipoprotein",
    r"\bHDL\b":    "high-density lipoprotein",
    r"\bTG\b":     "triglycerides",
    r"\bTSH\b":    "thyroid-stimulating hormone",
    r"\bECG\b":    "electrocardiogram",
    r"\bEKG\b":    "electrocardiogram",
    r"\bCXR\b":    "chest X-ray",
    r"\bCT\b":     "computed tomography",
    r"\bMRI\b":    "magnetic resonance imaging",
    r"\bIV\b":     "intravenous",
    r"\bPO\b":     "by mouth",
    r"\bPRN\b":    "as needed",
    r"\bBID\b":    "twice daily",
    r"\bTID\b":    "three times daily",
    r"\bQID\b":    "four times daily",
    r"\bOD\b":     "once daily",
    r"\bSQ\b":     "subcutaneous",
    r"\bSL\b":     "sublingual",
    r"\bNPO\b":    "nothing by mouth",
    r"\bICU\b":    "intensive care unit",
    r"\bER\b":     "emergency room",
    r"\bOPD\b":    "outpatient department",
    r"\bAFB\b":    "acid-fast bacilli",
    r"\bPTB\b":    "pulmonary tuberculosis",
    r"\bUTI\b":    "urinary tract infection",
    r"\bCKD\b":    "chronic kidney disease",
    r"\bARF\b":    "acute renal failure",
    r"\bAKI\b":    "acute kidney injury",
    r"\bCOPD\b":   "chronic obstructive pulmonary disease",
    r"\bCCU\b":    "cardiac care unit",
    r"\bNSR\b":    "normal sinus rhythm",
    r"\bAF\b":     "atrial fibrillation",
    r"\bAFib\b":   "atrial fibrillation",
    r"\bSVT\b":    "supraventricular tachycardia",
    r"\bPVC\b":    "premature ventricular contraction",
    r"\bGCS\b":    "Glasgow Coma Scale",
    r"\bLOC\b":    "loss of consciousness",
    r"\bRx\b":     "prescription",
    r"\bDx\b":     "diagnosis",
    r"\bSx\b":     "symptoms",
    r"\bHx\b":     "history",
    r"\bFHx\b":    "family history",
    r"\bSHx\b":    "social history",
    r"\bAOB\b":    "alcohol on breath",
    r"\bNKDA\b":   "no known drug allergies",
    r"\bNKA\b":    "no known allergies",
    r"\bs/p\b":    "status post",
    r"\bc/o\b":    "complaining of",
    r"\bw/\b":     "with",
    r"\bw/o\b":    "without",
    r"\br/o\b":    "rule out",
    r"\bR/O\b":    "rule out",
    r"\bp/w\b":    "presenting with",
}

# Common section heading aliases → canonical key
SECTION_ALIASES = {
    "condition_discharge": [
        r"condition\s+(?:upon|on|at)?\s*discharge",
        r"discharge\s+condition",
        r"condition\s+on\s+discharge",
    ],
    "chief_complaint": [
        r"chief\s+complaint",
        r"\bcc\b",
        r"presenting\s+complaint",
        r"reason\s+for\s+(?:admission|visit)",
    ],
    "admitting_dx": [
        r"admitting\s+diagnosis",
        r"admission\s+diagnosis",
        r"admitting\s+dx",
        r"diagnosis\s+on\s+admission",
        r"primary\s+diagnosis",
    ],
    "final_dx": [
        r"final\s+diagnosis",
        r"discharge\s+diagnosis",
        r"working\s+diagnosis",
        r"principal\s+diagnosis",
        r"final\s+dx",
        r"diagnosis\s+at\s+discharge",
    ],
    "hpi": [
        r"history\s+of\s+(?:present(?:ing)?\s+)?illness",
        r"\bhpi\b",
        r"present(?:ing)?\s+history",
        r"clinical\s+history",
    ],
    "pmh": [
        r"past\s+(?:medical\s+)?history",
        r"\bpmh\b",
        r"previous\s+(?:medical\s+)?history",
        r"medical\s+history",
        r"background\s+history",
    ],
    "physical_exam": [
        r"physical\s+exam(?:ination)?",
        r"\bpe\b",
        r"clinical\s+exam(?:ination)?",
        r"on\s+(?:physical\s+)?exam(?:ination)?",
    ],
    "labs": [
        r"laborator(?:y|ies)\s+(?:results?|findings?|data)",
        r"lab(?:oratory)?\s+(?:results?|findings?|data|values?)",
        r"diagnostic\s+(?:results?|findings?|data)",
        r"investigations?",
        r"pertinent\s+(?:lab|laboratory)\s+(?:results?|data)",
    ],
}

# Vital sign patterns
VITAL_PATTERNS = [
    r"(?:blood\s+pressure|bp)\s*:?\s*\d{2,3}\s*/\s*\d{2,3}",
    r"(?:heart\s+rate|hr|pulse)\s*:?\s*\d{2,3}",
    r"(?:respiratory\s+rate|rr)\s*:?\s*\d{1,2}",
    r"(?:temperature|temp)\s*:?\s*\d{2,3}(?:\.\d)?",
    r"(?:oxygen\s+saturation|spo2|o2\s+sat)\s*:?\s*\d{2,3}%?",
    r"(?:weight|wt)\s*:?\s*\d+(?:\.\d+)?\s*kg",
    r"(?:height|ht)\s*:?\s*\d+(?:\.\d+)?\s*(?:cm|m)",
    r"(?:bmi)\s*:?\s*\d+(?:\.\d+)?",
]

# Lab value pattern — detects lines like: Creatinine: 1.8 mg/dL (High)
LAB_LINE_PATTERN = re.compile(
    r"([A-Za-z][A-Za-z0-9\s/\-]{1,40}?)\s*:?\s*"  # test name
    r"([<>]?\s*\d+(?:\.\d+)?)\s*"                  # value
    r"([A-Za-z%/µμ\^0-9][A-Za-z%/µμ\^0-9\s]{0,14}?)\s*"  # unit — must start with non-space
    r"(?:\(?\s*(high|low|elevated|decreased|abnormal|critical)\s*\)?)?"  # explicit flag in parens only
    r"(?:,|;|\n|$)",
    re.IGNORECASE
)

# Date patterns (ISO, written, slashes)
DATE_PATTERN = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})"
    r"|\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"
    r"|\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE
)

# Abnormal value flag keywords
ABNORMAL_KEYWORDS = re.compile(
    r"\b(high|low|elevated|decreased|abnormal|critical|\*\*\*\s*high\s*\*\*\*|\*\*\*\s*low\s*\*\*\*|H\b|L\b)\b",
    re.IGNORECASE
)


# ── Text normalisation ────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """
    Clean raw PDF text:
    - Remove OCR noise (repeated punctuation, weird chars)
    - Collapse excessive whitespace
    - Normalize line endings
    """
    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove common OCR noise
    text = re.sub(r"[|]{2,}", " ", text)           # double pipes
    text = re.sub(r"_{3,}", " ", text)              # long underscores
    text = re.sub(r"\.{4,}", " ", text)             # excessive dots
    text = re.sub(r"-{3,}", " ", text)              # long dashes
    text = re.sub(r"\x00", "", text)                # null bytes
    text = re.sub(r"[^\x09\x0A\x20-\x7E]", " ", text)  # non-printable ASCII

    # Collapse multiple spaces on same line
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Collapse more than 2 consecutive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def to_sentence_case(text: str) -> str:
    """
    Convert text to sentence case.
    Preserves proper nouns and abbreviations as best as possible.
    """
    if not text:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = []
    for s in sentences:
        s = s.strip()
        if s:
            result.append(s[0].upper() + s[1:].lower() if len(s) > 1 else s.upper())
    return " ".join(result)


def expand_abbreviations(text: str) -> str:
    """Replace known medical abbreviations with their full terms."""
    for pattern, expansion in ABBREV.items():
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
    return text


# ── Section extraction ────────────────────────────────────────────────────────

def build_section_regex() -> re.Pattern:
    """
    Build a single regex that matches any known section heading.
    Returns a pattern with named groups for each section key.
    """
    parts = []
    for key, aliases in SECTION_ALIASES.items():
        group = "|".join(f"(?:{a})" for a in aliases)
        parts.append(f"(?P<{key}>{group})")
    combined = "|".join(parts)
    # Match heading at start of line or after newline, optional colon
    return re.compile(
        rf"(?:^|\n)\s*(?:{combined})\s*:?\s*\n?",
        re.IGNORECASE | re.MULTILINE
    )


SECTION_RE = build_section_regex()


def split_into_sections(text: str) -> dict[str, str]:
    """
    Split text into sections by detecting headings.
    Returns dict: canonical_key → section_text
    """
    sections: dict[str, str] = {}
    matches = list(SECTION_RE.finditer(text))

    for i, match in enumerate(matches):
        # Determine which key matched
        key = next(k for k, v in match.groupdict().items() if v is not None)

        # Section content is from end of this match to start of next
        start = match.end()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        # If same section appears twice, concatenate
        if key in sections:
            sections[key] = sections[key] + "\n" + content
        else:
            sections[key] = content

    return sections


# ── Physical exam parsing ─────────────────────────────────────────────────────

def parse_physical_exam(text: str) -> dict:
    """
    Separate vitals from clinical findings within a physical exam block.
    """
    vitals_lines   = []
    findings_lines = []

    for line in text.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        is_vital = any(
            re.search(p, line_stripped, re.IGNORECASE)
            for p in VITAL_PATTERNS
        )
        if is_vital:
            vitals_lines.append(line_stripped)
        else:
            findings_lines.append(line_stripped)

    return {
        "vitals":   clean_field(" ".join(vitals_lines))   or None,
        "findings": clean_field(" ".join(findings_lines)) or None,
    }


# ── Lab extraction ────────────────────────────────────────────────────────────

def normalize_flag(raw_flag: Optional[str]) -> Optional[str]:
    """
    Normalise flag strings to 'high', 'low', or None.
    Single-letter H/L are only accepted when surrounded by whitespace or parens
    — prevents 'L' in 'mmol/L' from being treated as Low.
    """
    if not raw_flag:
        return None
    f = raw_flag.strip()
    fl = f.lower()

    if fl in ("high", "elevated", "critical"):
        return "high"
    if fl in ("low", "decreased"):
        return "low"
    if fl == "abnormal":
        return "abnormal"
    # Single-letter flags only accepted as standalone tokens
    if f == "H":
        return "high"
    if f == "L":
        return "low"
    if "***" in f and "high" in fl:
        return "high"
    if "***" in f and "low" in fl:
        return "low"
    return None


def extract_labs_from_text(text: str) -> list[dict]:
    """
    Extract lab values from unstructured text using regex.
    Also checks for inline *** HIGH *** / *** LOW *** markers
    from CLARA's own lab extractor output.
    """
    results = []
    seen    = set()

    # First: look for CLARA-style flagged lines
    clara_pattern = re.compile(
        r"([A-Z][A-Z0-9\s/\-]{1,35}?):\s*"
        r"(\*{0,3}\s*(?:HIGH|LOW)\s*\*{0,3}|\d+(?:\.\d+)?)\s*"
        r"([A-Za-z%/µμ\^0-9\s]{0,15}?)\s*"
        r"(?:\(ref[^)]+\))?"
        r"(?:\s*\*{3}\s*(HIGH|LOW)\s*\*{3})?",
        re.IGNORECASE
    )

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Find date on this line or nearby
        date_match = DATE_PATTERN.search(line)
        date_val   = date_match.group(0) if date_match else None

        # Check for explicit flag marker — must be in parens or at end, not inside a unit
        # Accepts: (High), (Low), (H), (L), *** HIGH ***, *** LOW ***
        explicit_flag_pattern = re.compile(
            r"(?:\(\s*(high|low|elevated|decreased|abnormal|critical)\s*\)"
            r"|\s+(H|L)\s*$"
            r"|\*{3}\s*(high|low)\s*\*{3})",
            re.IGNORECASE
        )
        flag_match = explicit_flag_pattern.search(line)
        if flag_match:
            raw_flag = next(g for g in flag_match.groups() if g is not None)
            flag = normalize_flag(raw_flag)
        else:
            flag = None

        # Try general lab line pattern
        for m in LAB_LINE_PATTERN.finditer(line):
            test_name = m.group(1).strip().title()
            value     = m.group(2).strip()
            unit      = (m.group(3) or "").strip()
            raw_flag  = m.group(4)

            # Skip very short or numeric-only names (likely false positives)
            if len(test_name) < 3 or re.match(r"^\d+$", test_name):
                continue

            resolved_flag = normalize_flag(raw_flag) or flag

            key = (test_name, value)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "test": test_name,
                "date": date_val,
                "val":  value,
                "unit": unit or None,
                "flag": resolved_flag,
            })

    return results


# ── Field cleaning ────────────────────────────────────────────────────────────

def clean_field(text: str) -> Optional[str]:
    """
    Clean a single extracted field:
    - Normalize whitespace
    - Convert to sentence case
    - Expand abbreviations
    - Return None if empty
    """
    if not text or not text.strip():
        return None

    text = re.sub(r"\s+", " ", text).strip()
    text = expand_abbreviations(text)
    text = to_sentence_case(text)

    # Remove leading colons or bullets
    text = re.sub(r"^[\s:•\-–—]+", "", text).strip()

    return text or None


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_discharge(raw_text: str) -> dict:
    """
    Parse raw discharge summary text into structured JSON.

    Args:
        raw_text: Raw string extracted from a discharge summary PDF.

    Returns:
        dict conforming to the DischargeSchema.
    """
    schema = empty_schema()

    if not raw_text or not raw_text.strip():
        return schema

    # Step 1 — normalize
    text = normalize_text(raw_text)

    # Step 2 — split into sections
    sections = split_into_sections(text)

    # Step 3 — map sections to schema fields
    simple_fields = [
        "condition_discharge",
        "chief_complaint",
        "admitting_dx",
        "final_dx",
        "hpi",
        "pmh",
    ]

    for field in simple_fields:
        raw = sections.get(field, "")
        schema[field] = clean_field(raw)

    # Step 4 — physical exam
    pe_raw = sections.get("physical_exam", "")
    if pe_raw:
        schema["physical_exam"] = parse_physical_exam(pe_raw)
    else:
        # Try to find vitals in the full text as a fallback
        vitals_found = []
        for p in VITAL_PATTERNS:
            for m in re.finditer(p, text, re.IGNORECASE):
                vitals_found.append(m.group(0).strip())
        if vitals_found:
            schema["physical_exam"]["vitals"] = "; ".join(vitals_found)

    # Step 5 — labs
    # Prefer the dedicated lab section; fall back to full text
    lab_text = sections.get("labs", "") or text
    schema["labs"] = extract_labs_from_text(lab_text)

    # Step 6 — graceful fallback for completely missing sections
    # If no section headings were detected at all, try heuristic extraction
    if not sections:
        schema = _heuristic_fallback(text, schema)

    return schema


def _heuristic_fallback(text: str, schema: dict) -> dict:
    """
    Last-resort extraction when no section headings are detected.
    Uses the first sentence as chief complaint and scans full text for labs.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if sentences:
        schema["chief_complaint"] = clean_field(sentences[0])

    schema["labs"] = extract_labs_from_text(text)
    return schema


# ── Convenience: parse and pretty-print ──────────────────────────────────────

def parse_discharge_to_json(raw_text: str) -> str:
    """Return parsed discharge as a formatted JSON string."""
    import json
    result = parse_discharge(raw_text)
    return json.dumps(result, indent=2, ensure_ascii=False)