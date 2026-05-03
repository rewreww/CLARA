import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple, Union

from lab_extractors import (
    normalize_text,
    extract_chemistry_results,
    extract_hematology_results,
    extract_microscopy_results,
)

app = FastAPI()


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


@app.get("/")
def root():
    return {"message": "Medical text processing service is ready."}
