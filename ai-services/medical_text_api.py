import requests
import re as _re

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi.middleware.cors import CORSMiddleware
from discharge_parser import parse_discharge

from lab_extractors import (
    normalize_text,
    extract_chemistry_results,
    extract_hematology_results,
    extract_microscopy_results,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class LabRequest(BaseModel):
    patient: str
    labs: str


class LabResult(BaseModel):
    test_name: str
    value: Union[float, str]
    unit: str
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None


class LabResponse(BaseModel):
    patient: str
    results: List[LabResult]


class ParsedLabItem(BaseModel):
    test: str
    date: Optional[str] = None
    val:  str
    unit: Optional[str] = None
    flag: Optional[str] = None

class PhysicalExam(BaseModel):
    vitals:   Optional[str] = None
    findings: Optional[str] = None

class ParsedDischargeResponse(BaseModel):
    patient:              str
    found:                bool
    condition_discharge:  Optional[str] = None
    chief_complaint:      Optional[str] = None
    admitting_dx:         Optional[str] = None
    final_dx:             Optional[str] = None
    hpi:                  Optional[str] = None
    pmh:                  Optional[str] = None
    physical_exam:        PhysicalExam  = PhysicalExam()
    labs:                 List[ParsedLabItem] = []
    raw_text:             Optional[str] = None




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


def get_extracted_text(data: dict, folder_filter: Optional[str] = None) -> str:
    """Extract raw text from backend response data, optionally filtering by file path."""
    files = data.get("files") or data.get("Files") or []
    if not isinstance(files, list):
        return ""

    pieces: List[str] = []
    for file in files:
        if not isinstance(file, dict):
            continue

        file_path = (file.get("filePath") or file.get("FilePath") or "")
        if folder_filter and folder_filter.lower() not in file_path.lower():
            continue

        text = file.get("text") or file.get("Text") or ""
        if text:
            pieces.append(text)

    return "\n".join(pieces)


@app.post("/categorize", response_model=ProcessResponse)
def categorize(request: LabRequest):
    """Categorize raw text from PDFs for the provided patient and labs type."""
    if request.labs != "labs":
        raise HTTPException(status_code=400, detail="Only 'labs' labs type is supported for categorization")

    # Call C# backend to get raw text from patient folder
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_text = get_extracted_text(data, folder_filter="labs")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch raw text from backend: {str(e)}")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No raw text found for the patient")

    # Categorize the raw text
    categorized = categorize_text(raw_text)
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


@app.post("/chemistry-results", response_model=LabResponse)
def chemistry_results(request: LabRequest):
    """Return structured chemistry lab results for the provided patient and labs type."""
    if request.labs != "chemistry":
        raise HTTPException(status_code=400, detail="Only 'chemistry' labs type is supported")

    # Call C# backend to get raw text from patient folder
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_text = get_extracted_text(data, folder_filter="labs")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch raw text from backend: {str(e)}")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No raw text found for the patient")

    # Categorize the raw text
    categorized = categorize_text(raw_text)
    chemistry_text = categorized["labs"]["chemistry"]

    # Extract chemistry results
    parsed = extract_chemistry_results(chemistry_text)
    return LabResponse(patient=request.patient, results=parsed)


@app.post("/hematology-results", response_model=LabResponse)
def hematology_results(request: LabRequest):
    """Return structured hematology lab results for the provided patient."""
    if request.labs != "hematology":
        raise HTTPException(status_code=400, detail="Only 'hematology' labs type is supported")

    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_text = get_extracted_text(data, folder_filter="labs")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch raw text from backend: {str(e)}")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No raw text found for the patient")

    categorized = categorize_text(raw_text)
    hematology_text = categorized["labs"]["hematology"]
    parsed = extract_hematology_results(hematology_text)
    return LabResponse(patient=request.patient, results=parsed)


@app.post("/microscopy-results", response_model=LabResponse)
def microscopy_results(request: LabRequest):
    """Return structured microscopy lab results for the provided patient."""
    if request.labs != "microscopy":
        raise HTTPException(status_code=400, detail="Only 'microscopy' labs type is supported")

    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_text = get_extracted_text(data, folder_filter="labs")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch raw text from backend: {str(e)}")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No raw text found for the patient")

    categorized = categorize_text(raw_text)
    microscopy_text = categorized["labs"]["microscopy"]
    parsed = extract_microscopy_results(microscopy_text)
    return LabResponse(patient=request.patient, results=parsed)


class TimelineRequest(BaseModel):
    patient: str
    lab_type: str  # "chemistry", "hematology", or "microscopy"

class DateLabResult(BaseModel):
    date: str
    results: List[LabResult]

class TimelineResponse(BaseModel):
    patient: str
    lab_type: str
    timeline: List[DateLabResult]  # sorted oldest → newest

def extract_date_from_path(file_path: str) -> Optional[str]:
    """
    Extract YYYY-MM-DD date from a file path like:
    .../labs/2025-01-15/chemistry.pdf
    Returns None if no date folder found.
    """
    match = _re.search(r'(\d{4}-\d{2}-\d{2})', file_path.replace('\\', '/'))
    return match.group(1) if match else None

@app.post("/labs-timeline", response_model=TimelineResponse)
def labs_timeline(request: TimelineRequest):
    """
    Return lab results grouped by date for a patient.
    Requires labs to be in date subfolders: labs/YYYY-MM-DD/chemistry.pdf
    """
    if request.lab_type not in ["chemistry", "hematology", "microscopy"]:
        raise HTTPException(status_code=400, detail="lab_type must be chemistry, hematology, or microscopy")

    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from backend: {str(e)}")

    files = data.get("files") or data.get("Files") or []

    # Group files by date — only files matching the lab_type and inside a date folder
    date_groups: dict[str, list[str]] = {}
    for file in files:
        file_path = file.get("filePath") or file.get("FilePath") or ""
        text      = file.get("text")     or file.get("Text")     or ""

        # Must be inside a labs folder
        if "labs" not in file_path.lower():
            continue

        # Must match the requested lab type by filename
        filename = file_path.replace("\\", "/").split("/")[-1].lower()
        if request.lab_type not in filename:
            continue

        date = extract_date_from_path(file_path)
        if not date:
            continue

        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(text)

    # Sort dates oldest → newest
    sorted_dates = sorted(date_groups.keys())

    # Extract lab values per date
    timeline = []
    for date in sorted_dates:
        combined_text = "\n".join(date_groups[date])
        categorized = categorize_text(combined_text)
        section_text = categorized["labs"].get(request.lab_type, "")

        if request.lab_type == "chemistry":
            parsed = extract_chemistry_results(section_text or combined_text)
        elif request.lab_type == "hematology":
            parsed = extract_hematology_results(section_text or combined_text)
        else:
            parsed = extract_microscopy_results(section_text or combined_text)

        if parsed:
            timeline.append(DateLabResult(date=date, results=parsed))

    if not timeline:
        raise HTTPException(
            status_code=404,
            detail=f"No dated {request.lab_type} results found. Make sure labs are in date subfolders (YYYY-MM-DD)."
        )

    return TimelineResponse(
        patient=request.patient,
        lab_type=request.lab_type,
        timeline=timeline
    )


class DischargeRequest(BaseModel):
    patient: str

class DischargeResponse(BaseModel):
    patient: str
    text: str
    found: bool

@app.post("/discharge-summary", response_model=DischargeResponse)
def discharge_summary(request: DischargeRequest):
    """Fetch and return discharge summary text for a patient."""
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(
            backend_url,
            json={"FolderName": request.patient},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch from backend: {str(e)}"
        )

    # Filter files to discharge folder only
    raw_text = get_extracted_text(data, folder_filter="discharge")

    if not raw_text.strip():
        return DischargeResponse(
            patient=request.patient,
            text="",
            found=False
        )

    # Normalize the text
    cleaned = normalize_text(raw_text)

    return DischargeResponse(
        patient=request.patient,
        text=cleaned,
        found=True
    )


"""
Add these imports and endpoint to medical_text_api.py.

Step 1 — add this import at the top of medical_text_api.py:
  from discharge_parser import parse_discharge

Step 2 — add these models and endpoint before the root() function.
"""

# ── Pydantic models ───────────────────────────────────────────────────────────

class ParsedLabItem(BaseModel):
    test: str
    date: Optional[str] = None
    val:  str
    unit: Optional[str] = None
    flag: Optional[str] = None   # "high" | "low" | "abnormal" | None

class PhysicalExam(BaseModel):
    vitals:   Optional[str] = None
    findings: Optional[str] = None

class ParsedDischargeResponse(BaseModel):
    patient:              str
    found:                bool
    condition_discharge:  Optional[str] = None
    chief_complaint:      Optional[str] = None
    admitting_dx:         Optional[str] = None
    final_dx:             Optional[str] = None
    hpi:                  Optional[str] = None
    pmh:                  Optional[str] = None
    physical_exam:        PhysicalExam  = PhysicalExam()
    labs:                 List[ParsedLabItem] = []
    raw_text:             Optional[str] = None   # included for debugging


# ── Endpoint ──────────────────────────────────────────────────────────────────

@app.post("/discharge-parsed", response_model=ParsedDischargeResponse)
def discharge_parsed(request: DischargeRequest):
    """
    Fetch discharge summary PDF text and return it fully parsed
    into structured JSON sections.
    """
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(
            backend_url,
            json={"FolderName": request.patient},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch from backend: {str(e)}"
        )

    raw_text = get_extracted_text(data, folder_filter="discharge")

    if not raw_text.strip():
        return ParsedDischargeResponse(patient=request.patient, found=False)

    parsed = parse_discharge(raw_text)

    return ParsedDischargeResponse(
        patient              = request.patient,
        found                = True,
        condition_discharge  = parsed.get("condition_discharge"),
        chief_complaint      = parsed.get("chief_complaint"),
        admitting_dx         = parsed.get("admitting_dx"),
        final_dx             = parsed.get("final_dx"),
        hpi                  = parsed.get("hpi"),
        pmh                  = parsed.get("pmh"),
        physical_exam        = PhysicalExam(
            vitals   = parsed["physical_exam"].get("vitals"),
            findings = parsed["physical_exam"].get("findings"),
        ),
        labs     = [ParsedLabItem(**lab) for lab in parsed.get("labs", [])],
        raw_text = raw_text[:500] + "..." if len(raw_text) > 500 else raw_text,
    )

@app.get("/")
def root():
    return {"message": "Medical text processing service is ready."}
