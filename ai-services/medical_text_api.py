import requests
import re as _re
import os
import io

from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from collections import Counter
from typing import Any, Dict, List, Optional, Union
from fastapi.middleware.cors import CORSMiddleware
from discharge_parser import parse_discharge

from lab_extractors import (
    normalize_text,
    extract_chemistry_results,
    extract_hematology_results,
    extract_microscopy_results,
    extract_ecg_values,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic models ───────────────────────────────────────────────────────────

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

class PatientFileItem(BaseModel):
    file_path: str
    file_name: str
    section: str
    lab_type: Optional[str] = None
    date: Optional[str] = None

class PatientSummary(BaseModel):
    id: str
    name: str
    age: Optional[str] = None
    sex: Optional[str] = None
    available_sections: List[str] = []
    files: List[PatientFileItem] = []

class PatientsResponse(BaseModel):
    patients: List[PatientSummary]

class ParsedLabItem(BaseModel):
    test: str
    date: Optional[str] = None
    val:  str
    unit: Optional[str] = None
    flag: Optional[str] = None

class PhysicalExam(BaseModel):
    vitals:   Optional[str] = None
    findings: Optional[str] = None

class HospitalCourseItem(BaseModel):
    label: Optional[str] = None
    date:  Optional[str] = None
    content: Optional[str] = None

class DischargeHeader(BaseModel):
    facility:            Optional[str] = None
    document_title:      Optional[str] = None
    patient_name:        Optional[str] = None
    age:                 Optional[str] = None
    sex:                 Optional[str] = None
    civil_status:        Optional[str] = None
    hospital_no:         Optional[str] = None
    service:             Optional[str] = None
    room_ward:           Optional[str] = None
    attending_physician: Optional[str] = None
    referral_doctors:    Optional[str] = None
    date_admitted:       Optional[str] = None
    time_admitted:       Optional[str] = None
    date_discharged:     Optional[str] = None
    time_discharged:     Optional[str] = None

class ParsedDischargeResponse(BaseModel):
    patient:             str
    found:               bool
    header:              DischargeHeader = DischargeHeader()
    condition_discharge: Optional[str] = None
    chief_complaint:     Optional[str] = None
    admitting_dx:        Optional[str] = None
    final_dx:            Optional[str] = None
    hpi:                 Optional[str] = None
    pmh:                 Optional[str] = None
    allergies:           Optional[str] = None
    medications:         List[str] = []
    instructions:        List[str] = []
    followup:            Optional[str] = None
    physical_exam:       PhysicalExam = PhysicalExam()
    laboratory_data:     Optional[str] = None
    labs:                List[ParsedLabItem] = []
    hospital_course:     List[HospitalCourseItem] = []
    raw_text:            Optional[str] = None

class DischargeRequest(BaseModel):
    patient: str
    file_name: Optional[str] = None

class DischargeResponse(BaseModel):
    patient: str
    text: str
    found: bool

class DischargeFileItem(BaseModel):
    file_name: str
    date_label: str

class DischargeListResponse(BaseModel):
    patient: str
    files: List[DischargeFileItem]

class TimelineRequest(BaseModel):
    patient: str
    lab_type: str

class DateLabResult(BaseModel):
    date: str
    results: List[LabResult]

class TimelineResponse(BaseModel):
    patient: str
    lab_type: str
    timeline: List[DateLabResult]

class VitalEntry(BaseModel):
    value:   str
    numeric: Optional[float] = None
    status:  str
    label:   str

class VitalsResponse(BaseModel):
    patient: str
    found:   bool
    raw:     Optional[str] = None
    bp:      Optional[VitalEntry] = None
    hr:      Optional[VitalEntry] = None
    rr:      Optional[VitalEntry] = None
    temp:    Optional[VitalEntry] = None
    o2:      Optional[VitalEntry] = None

class VitalsTimelinePoint(BaseModel):
    date: str
    bp:   Optional[float] = None
    hr:   Optional[float] = None
    rr:   Optional[float] = None
    temp: Optional[float] = None
    o2:   Optional[float] = None

class VitalsTimelineResponse(BaseModel):
    patient:  str
    timeline: List[VitalsTimelinePoint]

class PdfExtractResponse(BaseModel):
    filename:   str
    pages:      int
    char_count: int
    text:       str

class DiagnosePrepRequest(BaseModel):
    chief_complaint: Optional[str] = None
    lab_text:        Optional[str] = None
    discharge_text:  Optional[str] = None
    imaging_text:    Optional[str] = None

class DiagnosePrepResponse(BaseModel):
    chief_complaint:    Optional[str]        = None
    chemistry_results:  List[Dict[str, Any]] = []
    hematology_results: List[Dict[str, Any]] = []
    microscopy_results: List[Dict[str, Any]] = []
    discharge_parsed:   Optional[Dict]       = None
    imaging_text:       Optional[str]        = None
    ecg_values:         Optional[Dict]       = None

# ── Helpers ───────────────────────────────────────────────────────────────────

def compact_text(text: str) -> str:
    return _re.sub(r"\s+", " ", text or "").strip()

def title_case_name(name: str) -> str:
    cleaned = compact_text(name).strip(" :")
    if not cleaned:
        return cleaned
    if cleaned.upper() != cleaned:
        return cleaned
    return " ".join(part.capitalize() for part in cleaned.split(" "))

def extract_date_from_path(file_path: str) -> Optional[str]:
    match = _re.search(r'(\d{4}-\d{2}-\d{2})', file_path.replace('\\', '/'))
    return match.group(1) if match else None

def parse_date_label_from_filename(filename: str) -> str:
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    m = _re.search(r'(\d{4})_(\d{2})_(\d{2})', filename)
    if m:
        try:
            from datetime import datetime
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return dt.strftime('%b %d, %Y')
        except ValueError:
            pass
    m = _re.search(r'(\d{4})_(\d{2})', filename)
    if m:
        try:
            year, month = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12:
                return f"{MONTHS[month - 1]} {year}"
        except ValueError:
            pass
    return _re.sub(r'[_\-]', ' ', filename.rsplit('.', 1)[0]).title()

def get_extracted_text(data: dict, folder_filter: Optional[str] = None) -> str:
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

def get_text_for_file(data: dict, file_key: str) -> str:
    files = data.get("files") or data.get("Files") or []
    key_norm = file_key.replace("\\", "/").lower()
    for file in files:
        if not isinstance(file, dict):
            continue
        file_path = (file.get("filePath") or file.get("FilePath") or "")
        path_norm = file_path.replace("\\", "/").lower()
        if path_norm.endswith(key_norm):
            return file.get("text") or file.get("Text") or ""
    return ""

def extract_metadata_value(text: str, labels: List[str], stop_labels: List[str]) -> Optional[str]:
    label_pattern = "|".join(labels)
    stop_pattern = "|".join(stop_labels)
    match = _re.search(
        rf"(?:{label_pattern})\s*:?\s*(.*?)(?=\s+(?:{stop_pattern})\s*:?\s|$)",
        text, flags=_re.IGNORECASE,
    )
    return compact_text(match.group(1)) if match else None

def extract_patient_metadata(text: str) -> Dict[str, Optional[str]]:
    compact = compact_text(text)
    stop_labels = [
        r"date\s+requested", r"date\s+rendered", r"date\s+performed", r"date\s+released",
        r"age", r"gender", r"sex", r"birth\s*date", r"birthdate", r"time\s+released",
        r"requesting\s+physician", r"physician", r"clinical\s+chemistry",
        r"hematology", r"clinical\s+microscopy", r"urinalysis", r"test",
    ]
    name = extract_metadata_value(compact, [r"patient(?:'s)?\s+name", r"name"], stop_labels)
    age  = extract_metadata_value(compact, [r"age"], stop_labels)
    sex  = extract_metadata_value(compact, [r"gender", r"sex"], stop_labels)
    if sex:
        normalized_sex = sex.upper()
        if normalized_sex.startswith("MALE"):
            sex = "M"
        elif normalized_sex.startswith("FEMALE"):
            sex = "F"
        else:
            sex = normalized_sex[:1]
    return {"name": title_case_name(name or ""), "age": age, "sex": sex}

def classify_patient_file(file_path: str) -> PatientFileItem:
    normalized = file_path.replace("\\", "/")
    lower = normalized.lower()
    file_name = normalized.split("/")[-1]
    section = "other"
    lab_type = None
    for candidate in ["discharge", "encounters", "imaging", "prescriptions"]:
        if f"/{candidate}/" in lower:
            section = candidate
            break
    if "/labs/" in lower:
        section = "labs"
        for candidate in ["chemistry", "hematology", "microscopy"]:
            if candidate in lower:
                lab_type = candidate
                break
    return PatientFileItem(
        file_path=file_path, file_name=file_name,
        section=section, lab_type=lab_type,
        date=extract_date_from_path(file_path),
    )

def list_patient_folder_names(backend_base_url: str) -> List[str]:
    try:
        response = requests.get(f"{backend_base_url}/patients", timeout=10)
        response.raise_for_status()
        data = response.json()
        patients = data.get("patients") or data.get("Patients") or []
        if isinstance(patients, list):
            return [str(p) for p in patients]
    except requests.RequestException:
        pass
    patients_path = os.path.join(os.path.expanduser("~"), "Desktop", "Patients")
    if not os.path.isdir(patients_path):
        return []
    return sorted(
        f for f in os.listdir(patients_path)
        if os.path.isdir(os.path.join(patients_path, f))
    )

def categorize_text(clean_text: str) -> Dict[str, object]:
    sections = {
        "demographics": [], "discharge": [], "encounters": [], "imaging": [],
        "labs": {"chemistry": [], "hematology": [], "microscopy": []},
        "prescriptions": [],
    }
    current_section = "demographics"
    current_lab_section = None
    for line in clean_text.split("\n"):
        upper = line.upper()
        if "DISCHARGE SUMMARY" in upper:
            current_section = "discharge"; current_lab_section = None
            sections[current_section].append(line); continue
        if "CLINICAL CHEMISTRY" in upper:
            current_section = "labs"; current_lab_section = "chemistry"
            sections["labs"][current_lab_section].append(line); continue
        if "HEMATOLOGY" in upper:
            current_section = "labs"; current_lab_section = "hematology"
            sections["labs"][current_lab_section].append(line); continue
        if "URINALYSIS" in upper or "MICROSCOPY" in upper:
            current_section = "labs"; current_lab_section = "microscopy"
            sections["labs"][current_lab_section].append(line); continue
        if "IMAGING" in upper or "RADIOLOGY" in upper:
            current_section = "imaging"; current_lab_section = None
            sections[current_section].append(line); continue
        if "PRESCRIPTIONS" in upper or "MEDICATION" in upper:
            current_section = "prescriptions"; current_lab_section = None
            sections[current_section].append(line); continue
        if "ENCOUNTERS" in upper or "VISITS" in upper or "ADMISSIONS" in upper:
            current_section = "encounters"; current_lab_section = None
            sections[current_section].append(line); continue
        if "DEMOGRAPHICS" in upper:
            current_section = "demographics"; current_lab_section = None
            sections[current_section].append(line); continue
        if current_section == "labs" and current_lab_section is not None:
            sections["labs"][current_lab_section].append(line)
        else:
            sections[current_section].append(line)
    return {
        "demographics": "\n".join(sections["demographics"]).strip(),
        "discharge":    "\n".join(sections["discharge"]).strip(),
        "encounters":   "\n".join(sections["encounters"]).strip(),
        "imaging":      "\n".join(sections["imaging"]).strip(),
        "labs": {
            "chemistry":  "\n".join(sections["labs"]["chemistry"]).strip(),
            "hematology": "\n".join(sections["labs"]["hematology"]).strip(),
            "microscopy": "\n".join(sections["labs"]["microscopy"]).strip(),
        },
        "prescriptions": "\n".join(sections["prescriptions"]).strip(),
    }

# ── Vitals helpers ────────────────────────────────────────────────────────────

def _to_num(v: str) -> Optional[float]:
    try:
        return float(_re.sub(r'[^\d.]', '', v.strip()))
    except (ValueError, AttributeError):
        return None

def _bp_status(sys: float, dia: float) -> str:
    if sys < 90 or dia < 60:    return "critical"
    if sys >= 140 or dia >= 90: return "critical"
    if sys >= 130 or dia >= 80: return "warning"
    return "normal"

def _bp_label(sys: float, dia: float) -> str:
    if sys < 90:                return "Hypotensive"
    if sys >= 160 or dia >= 100: return "HTN Crisis"
    if sys >= 140 or dia >= 90: return "Hypertensive"
    if sys >= 130 or dia >= 80: return "Elevated"
    return "Normal"

def _hr_status(v: float) -> str:
    if v < 50 or v > 150:  return "critical"
    if v < 60 or v > 100:  return "warning"
    return "normal"

def _hr_label(v: float) -> str:
    if v < 50:   return "Bradycardic"
    if v > 150:  return "Severe Tachy"
    if v > 100:  return "Tachycardic"
    if v < 60:   return "Bradycardic"
    return "Normal"

def _rr_status(v: float) -> str:
    if v < 8 or v > 30:   return "critical"
    if v < 12 or v > 20:  return "warning"
    return "normal"

def _rr_label(v: float) -> str:
    if v < 8:   return "Apneic"
    if v > 30:  return "Severe Tachypnea"
    if v > 20:  return "Tachypnea"
    if v < 12:  return "Bradypnea"
    return "Normal"

def _temp_status(v: float) -> str:
    if v < 35.0 or v >= 39.5: return "critical"
    if v < 36.5 or v >= 38.0: return "warning"
    return "normal"

def _temp_label(v: float) -> str:
    if v < 35.0:  return "Hypothermic"
    if v >= 39.5: return "High Fever"
    if v >= 38.0: return "Febrile"
    if v < 36.5:  return "Subnormal"
    return "Afebrile"

def _o2_status(v: float) -> str:
    if v < 90: return "critical"
    if v < 95: return "warning"
    return "normal"

def _o2_label(v: float) -> str:
    if v < 90: return "Severe Hypoxia"
    if v < 95: return "Hypoxic"
    return "Normal"

def _parse_vitals_string(text: str) -> dict:
    parts = [p.strip() for p in _re.split(r'[>\|,;]', text) if p.strip()]
    result = {"bp": None, "hr": None, "rr": None, "temp": None, "o2": None}
    bp_i = o2_i = temp_i = -1
    for i, p in enumerate(parts):
        if '/' in p and _re.search(r'\d+/\d+', p):
            bp_i = i
        elif '%' in p:
            o2_i = i
        elif '.' in p and _to_num(p) is not None:
            temp_i = i
    assigned  = {bp_i, o2_i, temp_i}
    remaining = [i for i in range(len(parts)) if i not in assigned]
    hr_i = remaining[0] if len(remaining) > 0 else -1
    rr_i = remaining[1] if len(remaining) > 1 else -1
    if bp_i >= 0:
        m = _re.search(r'(\d+)\s*/\s*(\d+)', parts[bp_i])
        if m:
            s, d = float(m.group(1)), float(m.group(2))
            result["bp"] = {"value": f"{int(s)}/{int(d)}", "numeric": s,
                            "status": _bp_status(s, d), "label": _bp_label(s, d)}
    if hr_i >= 0:
        v = _to_num(parts[hr_i])
        if v: result["hr"] = {"value": str(int(v)), "numeric": v,
                               "status": _hr_status(v), "label": _hr_label(v)}
    if rr_i >= 0:
        v = _to_num(parts[rr_i])
        if v: result["rr"] = {"value": str(int(v)), "numeric": v,
                               "status": _rr_status(v), "label": _rr_label(v)}
    if temp_i >= 0:
        v = _to_num(parts[temp_i])
        if v: result["temp"] = {"value": f"{v:.1f}", "numeric": v,
                                 "status": _temp_status(v), "label": _temp_label(v)}
    if o2_i >= 0:
        v = _to_num(parts[o2_i])
        if v: result["o2"] = {"value": str(int(v)), "numeric": v,
                               "status": _o2_status(v), "label": _o2_label(v)}
    return result

# ── Discharge helpers ─────────────────────────────────────────────────────────

def _extract_allergies(text: str) -> Optional[str]:
    match = _re.search(
        r'(?:drug\s+)?allergi(?:es|c\s+to|a)\s*:?\s*([^\n\r]{2,80})',
        text, flags=_re.IGNORECASE
    )
    if match:
        val = compact_text(match.group(1))
        return val if val else None
    if _re.search(r'\bNKDA\b', text, flags=_re.IGNORECASE):
        return 'NKDA (No Known Drug Allergies)'
    return None

def _extract_condition_upon_discharge(text: str) -> Optional[str]:
    CONDITIONS = ['recovered', 'improved', 'unimproved', 'others']
    match = _re.search(
        r'condition\s+(?:upon|on|at|of)\s+discharge\s*:?\s*([^\n\r]{2,40})',
        text, flags=_re.IGNORECASE
    )
    if match:
        val = match.group(1).strip()
        for c in CONDITIONS:
            if c in val.lower():
                return c.capitalize()
    match = _re.search(
        r'(?:\(x\)|\[x\]|✓|✗|\/)\s*(recovered|improved|unimproved|others)',
        text, flags=_re.IGNORECASE
    )
    if match:
        return match.group(1).capitalize()
    for c in CONDITIONS:
        match = _re.search(rf'{c}\s*(?:\(x\)|\[x\]|✓|:?\s*yes|\*)', text, flags=_re.IGNORECASE)
        if match:
            return c.capitalize()
    match = _re.search(
        r'discharged?\s+(?:as\s+)?:?\s*(recovered|improved|unimproved)',
        text, flags=_re.IGNORECASE
    )
    if match:
        return match.group(1).capitalize()
    return None

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/patients", response_model=PatientsResponse)
def patients():
    backend_base_url = "http://localhost:5000/api/pdfingestion"
    folder_names = list_patient_folder_names(backend_base_url)
    summaries: List[PatientSummary] = []
    for folder_name in folder_names:
        try:
            response = requests.post(
                f"{backend_base_url}/extract",
                json={"FolderName": folder_name}, timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            summaries.append(PatientSummary(id=folder_name, name=folder_name))
            continue
        files = data.get("files") or data.get("Files") or []
        file_items: List[PatientFileItem] = []
        lab_metadata: List[Dict[str, Optional[str]]] = []
        fallback_metadata: List[Dict[str, Optional[str]]] = []
        for file in files:
            if not isinstance(file, dict):
                continue
            file_path = file.get("filePath") or file.get("FilePath") or ""
            text = file.get("text") or file.get("Text") or ""
            if not file_path:
                continue
            item = classify_patient_file(file_path)
            file_items.append(item)
            metadata = extract_patient_metadata(text)
            if metadata.get("name"):
                if item.section == "labs":
                    lab_metadata.append(metadata)
                else:
                    fallback_metadata.append(metadata)
        metadata_source = lab_metadata or fallback_metadata
        name_counts = Counter(item["name"] for item in metadata_source if item.get("name"))
        name = name_counts.most_common(1)[0][0] if name_counts else folder_name
        age  = next((item.get("age") for item in metadata_source if item.get("age")), None)
        sex  = next((item.get("sex") for item in metadata_source if item.get("sex")), None)
        available_sections = sorted({
            file_item.lab_type or file_item.section
            for file_item in file_items if file_item.section != "other"
        })
        summaries.append(PatientSummary(
            id=folder_name, name=name, age=age, sex=sex,
            available_sections=available_sections, files=file_items,
        ))
    return PatientsResponse(patients=summaries)


@app.post("/categorize", response_model=ProcessResponse)
def categorize(request: LabRequest):
    if request.labs != "labs":
        raise HTTPException(status_code=400, detail="Only 'labs' labs type is supported for categorization")
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
    return ProcessResponse(
        demographics=categorized["demographics"], discharge=categorized["discharge"],
        encounters=categorized["encounters"], imaging=categorized["imaging"],
        labs=LabsResponse(
            chemistry=categorized["labs"]["chemistry"],
            hematology=categorized["labs"]["hematology"],
            microscopy=categorized["labs"]["microscopy"],
        ),
        prescriptions=categorized["prescriptions"],
    )


@app.post("/chemistry-results", response_model=LabResponse)
def chemistry_results(request: LabRequest):
    if request.labs != "chemistry":
        raise HTTPException(status_code=400, detail="Only 'chemistry' labs type is supported")
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
    parsed = extract_chemistry_results(categorized["labs"]["chemistry"])
    return LabResponse(patient=request.patient, results=parsed)


@app.post("/hematology-results", response_model=LabResponse)
def hematology_results(request: LabRequest):
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
    parsed = extract_hematology_results(categorized["labs"]["hematology"])
    return LabResponse(patient=request.patient, results=parsed)


@app.post("/microscopy-results", response_model=LabResponse)
def microscopy_results(request: LabRequest):
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
    parsed = extract_microscopy_results(categorized["labs"]["microscopy"])
    return LabResponse(patient=request.patient, results=parsed)


@app.post("/labs-timeline", response_model=TimelineResponse)
def labs_timeline(request: TimelineRequest):
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
    date_groups: dict[str, list[str]] = {}
    for file in files:
        file_path = file.get("filePath") or file.get("FilePath") or ""
        text      = file.get("text")     or file.get("Text")     or ""
        if "labs" not in file_path.lower():
            continue
        filename = file_path.replace("\\", "/").split("/")[-1].lower()
        if request.lab_type not in filename:
            continue
        date = extract_date_from_path(file_path)
        if not date:
            continue
        date_groups.setdefault(date, []).append(text)
    sorted_dates = sorted(date_groups.keys())
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
        raise HTTPException(status_code=404,
            detail=f"No dated {request.lab_type} results found. Make sure labs are in date subfolders (YYYY-MM-DD).")
    return TimelineResponse(patient=request.patient, lab_type=request.lab_type, timeline=timeline)


@app.post("/discharge-summary", response_model=DischargeResponse)
def discharge_summary(request: DischargeRequest):
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from backend: {str(e)}")
    if request.file_name:
        raw_text = get_text_for_file(data, request.file_name)
    else:
        raw_text = get_extracted_text(data, folder_filter="discharge")
    if not raw_text.strip():
        return DischargeResponse(patient=request.patient, text="", found=False)
    return DischargeResponse(patient=request.patient, text=normalize_text(raw_text), found=True)


@app.post("/discharge-parsed", response_model=ParsedDischargeResponse)
def discharge_parsed(request: DischargeRequest):
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from backend: {str(e)}")
    if request.file_name:
        raw_text = get_text_for_file(data, request.file_name)
    else:
        raw_text = get_extracted_text(data, folder_filter="discharge")
    if not raw_text.strip():
        return ParsedDischargeResponse(patient=request.patient, found=False)
    parsed = parse_discharge(raw_text)
    return ParsedDischargeResponse(
        patient             = request.patient,
        found               = True,
        header              = DischargeHeader(**(parsed.get("header") or {})),
        condition_discharge = _extract_condition_upon_discharge(raw_text),
        chief_complaint     = parsed.get("chief_complaint"),
        admitting_dx        = parsed.get("admitting_dx"),
        final_dx            = parsed.get("final_dx"),
        hpi                 = parsed.get("hpi"),
        pmh                 = parsed.get("pmh"),
        allergies           = _extract_allergies(raw_text),
        medications         = parsed.get("medications", []),
        instructions        = parsed.get("instructions", []),
        followup            = parsed.get("followup"),
        physical_exam       = PhysicalExam(
            vitals   = parsed["physical_exam"].get("vitals"),
            findings = parsed["physical_exam"].get("findings"),
        ),
        laboratory_data     = parsed.get("laboratory_data"),
        labs                = [ParsedLabItem(**lab) for lab in parsed.get("labs", [])],
        hospital_course     = [HospitalCourseItem(**item) for item in parsed.get("hospital_course", [])],
        raw_text            = raw_text,
    )


@app.post("/discharge-list", response_model=DischargeListResponse)
def discharge_list(request: DischargeRequest):
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from backend: {str(e)}")
    files = data.get("files") or data.get("Files") or []
    result = []
    for file in files:
        if not isinstance(file, dict):
            continue
        raw_path  = (file.get("filePath") or file.get("FilePath") or "").replace("\\", "/")
        file_name = raw_path.split("/")[-1]
        parts     = raw_path.rstrip("/").split("/")
        date_folder = parts[-2] if len(parts) >= 2 else ""
        if "discharge" not in file_name.lower() and "discharge" not in raw_path.lower():
            continue
        file_key   = f"{date_folder}/{file_name}" if date_folder else file_name
        date_label = parse_date_label_from_filename(date_folder) if date_folder else parse_date_label_from_filename(file_name)
        result.append(DischargeFileItem(file_name=file_key, date_label=date_label))
    result.sort(key=lambda x: x.file_name)
    return DischargeListResponse(patient=request.patient, files=result)


@app.post("/vitals", response_model=VitalsResponse)
def vitals_endpoint(request: DischargeRequest):
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
    files = data.get("files") or data.get("Files") or []
    discharge_files = []
    for f in files:
        if not isinstance(f, dict):
            continue
        fp   = (f.get("filePath") or f.get("FilePath") or "").replace("\\", "/")
        text = f.get("text") or f.get("Text") or ""
        if "discharge" in fp.lower():
            discharge_files.append((fp, text))
    discharge_files.sort(key=lambda x: x[0])
    raw_text = discharge_files[-1][1] if discharge_files else ""
    if not raw_text.strip():
        return VitalsResponse(patient=request.patient, found=False)
    parsed = parse_discharge(raw_text)
    vitals_text = (parsed.get("physical_exam") or {}).get("vitals") if parsed else None
    if not vitals_text:
        return VitalsResponse(patient=request.patient, found=False)
    v = _parse_vitals_string(vitals_text)
    return VitalsResponse(
        patient=request.patient, found=True, raw=vitals_text,
        bp=VitalEntry(**v["bp"])   if v["bp"]   else None,
        hr=VitalEntry(**v["hr"])   if v["hr"]   else None,
        rr=VitalEntry(**v["rr"])   if v["rr"]   else None,
        temp=VitalEntry(**v["temp"]) if v["temp"] else None,
        o2=VitalEntry(**v["o2"])   if v["o2"]   else None,
    )


@app.post("/vitals-timeline", response_model=VitalsTimelineResponse)
def vitals_timeline(request: DischargeRequest):
    backend_url = "http://localhost:5000/api/pdfingestion/extract"
    try:
        response = requests.post(backend_url, json={"FolderName": request.patient}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
    files = data.get("files") or data.get("Files") or []
    points = []
    for f in files:
        if not isinstance(f, dict):
            continue
        fp   = (f.get("filePath") or f.get("FilePath") or "").replace("\\", "/")
        text = f.get("text") or f.get("Text") or ""
        if "discharge" not in fp.lower() or not text.strip():
            continue
        parts  = fp.rstrip("/").split("/")
        folder = parts[-2] if len(parts) >= 2 else ""
        m = _re.match(r'(\d{4})[_\-](\d{2})[_\-](\d{2})$', folder)
        if m:
            date_key = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        else:
            m = _re.match(r'(\d{4})[_\-](\d{2})$', folder)
            date_key = f"{m.group(1)}-{m.group(2)}" if m else folder
        parsed = parse_discharge(text)
        vitals_text = (parsed.get("physical_exam") or {}).get("vitals") if parsed else None
        if not vitals_text:
            continue
        v = _parse_vitals_string(vitals_text)
        points.append(VitalsTimelinePoint(
            date=date_key,
            bp=v["bp"]["numeric"]     if v.get("bp")   else None,
            hr=v["hr"]["numeric"]     if v.get("hr")   else None,
            rr=v["rr"]["numeric"]     if v.get("rr")   else None,
            temp=v["temp"]["numeric"] if v.get("temp") else None,
            o2=v["o2"]["numeric"]     if v.get("o2")   else None,
        ))
    points.sort(key=lambda x: x.date)
    return VitalsTimelineResponse(patient=request.patient, timeline=points)


@app.post("/extract-pdf", response_model=PdfExtractResponse)
async def extract_pdf_upload(file: UploadFile = File(...)):
    try:
        import pypdf
    except ImportError:
        raise HTTPException(500, "pypdf not installed — run: pip install pypdf")
    data   = await file.read()
    reader = pypdf.PdfReader(io.BytesIO(data))
    pages  = [p.extract_text() or "" for p in reader.pages]
    text   = "\n\n".join(pages)
    return PdfExtractResponse(
        filename=file.filename or "upload.pdf",
        pages=len(reader.pages),
        char_count=len(text),
        text=text,
    )


@app.post("/diagnose-prep", response_model=DiagnosePrepResponse)
def diagnose_prep(req: DiagnosePrepRequest):
    out = DiagnosePrepResponse(chief_complaint=req.chief_complaint)
    if req.lab_text and req.lab_text.strip():
        clean = normalize_text(req.lab_text)
        out.chemistry_results  = extract_chemistry_results(clean)  or []
        out.hematology_results = extract_hematology_results(clean) or []
        out.microscopy_results = extract_microscopy_results(clean) or []
        out.ecg_values         = extract_ecg_values(clean)
    if req.discharge_text and req.discharge_text.strip():
        clean = normalize_text(req.discharge_text)
        out.discharge_parsed = parse_discharge(clean)
        if not out.ecg_values:
            out.ecg_values = extract_ecg_values(clean)
    if req.imaging_text and req.imaging_text.strip():
        out.imaging_text = req.imaging_text.strip()
    return out


@app.get("/")
def root():
    return {"message": "Medical text processing service is ready."}