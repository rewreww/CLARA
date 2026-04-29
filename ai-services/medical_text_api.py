from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List

app = FastAPI()


class ProcessRequest(BaseModel):
    raw_text: str


class LabsResponse(BaseModel):
    chemistry: str
    hematology: str
    microscopy: str


class ProcessResponse(BaseModel):
    demographics: str
    discharge: str
    encounters: str
    imaging: str
    labs: LabsResponse
    prescriptions: str


def normalize_text(raw_text: str) -> str:
    """Clean spacing and normalize line breaks."""
    if raw_text is None:
        return ""

    # Convert literal escaped newline sequences into actual newlines
    # This helps when the input contains text like "Line1\nLine2".
    text = raw_text.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")

    # Convert Windows and old Mac line endings to Unix style.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split into lines and remove leading/trailing whitespace from each line.
    lines = [line.strip() for line in text.split("\n")]

    cleaned_lines: List[str] = []
    blank_seen = False

    for line in lines:
        if line == "":
            # Preserve only one blank line between paragraphs.
            if not blank_seen:
                cleaned_lines.append("")
                blank_seen = True
        else:
            # Collapse repeated spaces inside the line.
            cleaned_line = " ".join(line.split())
            cleaned_lines.append(cleaned_line)
            blank_seen = False

    return "\n".join(cleaned_lines).strip()


def categorize_text(clean_text: str) -> Dict[str, object]:
    """Split cleaned text into sections using simple keyword rules."""
    sections = {
        "demographics": [],
        "discharge": [],
        "encounters": [],
        "imaging": [],
        "labs": {
            "chemistry": [],
            "hematology": [],
            "microscopy": [],
        },
        "prescriptions": [],
    }

    current_section = "demographics"
    current_lab_section = None

    for line in clean_text.split("\n"):
        upper = line.upper()

        if "DISCHARGE SUMMARY" in upper:
            current_section = "discharge"
            current_lab_section = None
            sections[current_section].append(line)
            continue

        if "CLINICAL CHEMISTRY" in upper:
            current_section = "labs"
            current_lab_section = "chemistry"
            sections["labs"][current_lab_section].append(line)
            continue

        if "HEMATOLOGY" in upper:
            current_section = "labs"
            current_lab_section = "hematology"
            sections["labs"][current_lab_section].append(line)
            continue

        if "URINALYSIS" in upper or "MICROSCOPY" in upper:
            current_section = "labs"
            current_lab_section = "microscopy"
            sections["labs"][current_lab_section].append(line)
            continue

        if "IMAGING" in upper or "RADIOLOGY" in upper:
            current_section = "imaging"
            current_lab_section = None
            sections[current_section].append(line)
            continue

        if "PRESCRIPTIONS" in upper or "MEDICATION" in upper:
            current_section = "prescriptions"
            current_lab_section = None
            sections[current_section].append(line)
            continue

        if "ENCOUNTERS" in upper or "VISITS" in upper or "ADMISSIONS" in upper:
            current_section = "encounters"
            current_lab_section = None
            sections[current_section].append(line)
            continue

        if "DEMOGRAPHICS" in upper:
            current_section = "demographics"
            current_lab_section = None
            sections[current_section].append(line)
            continue

        if current_section == "labs" and current_lab_section is not None:
            sections["labs"][current_lab_section].append(line)
        else:
            sections[current_section].append(line)

    return {
        "demographics": "\n".join(sections["demographics"]).strip(),
        "discharge": "\n".join(sections["discharge"]).strip(),
        "encounters": "\n".join(sections["encounters"]).strip(),
        "imaging": "\n".join(sections["imaging"]).strip(),
        "labs": {
            "chemistry": "\n".join(sections["labs"]["chemistry"]).strip(),
            "hematology": "\n".join(sections["labs"]["hematology"]).strip(),
            "microscopy": "\n".join(sections["labs"]["microscopy"]).strip(),
        },
        "prescriptions": "\n".join(sections["prescriptions"]).strip(),
    }


@app.post("/process", response_model=ProcessResponse)
def process_text(request: ProcessRequest):
    """Process raw extracted text and return a structured JSON response."""
    cleaned = normalize_text(request.raw_text)

    if not cleaned:
        raise HTTPException(status_code=400, detail="raw_text must not be empty")

    categorized = categorize_text(cleaned)

    return ProcessResponse(
        demographics=categorized["demographics"],
        discharge=categorized["discharge"],
        encounters=categorized["encounters"],
        imaging=categorized["imaging"],
        labs=LabsResponse(
            chemistry=categorized["labs"]["chemistry"],
            hematology=categorized["labs"]["hematology"],
            microscopy=categorized["labs"]["microscopy"],
        ),
        prescriptions=categorized["prescriptions"],
    )


@app.get("/")
def root():
    return {"message": "Medical text processing service is ready."}
