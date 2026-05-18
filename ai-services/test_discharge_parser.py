"""
Run from ai-services directory:
  python test_discharge_parser.py
"""

import json
from discharge_parser import parse_discharge


SAMPLE = """
DISCHARGE SUMMARY

Patient: Juan dela Cruz
Date of Admission: January 15, 2025
Date of Discharge: January 20, 2025

CONDITION UPON DISCHARGE:
Patient was discharged in stable condition, ambulatory, afebrile, with BP controlled.

CHIEF COMPLAINT:
C/O chest pain and SOB for 3 days PTA.

ADMITTING DIAGNOSIS:
Acute MI, HTN Stage 2

FINAL DIAGNOSIS:
1. Acute myocardial infarction, anterior wall
2. HTN, Stage 2
3. DM2 with poor control

HISTORY OF PRESENT ILLNESS:
Patient is a 58-year-old male w/ known HTN and DM who presented to ER c/o chest pain
radiating to the left arm, associated with SOB, diaphoresis, and nausea for 3 days PTA.
BP on admission was 180/110 mmHg. HR was 98 bpm. Troponin was significantly elevated.
ECG showed ST elevation in V1-V4. Patient was admitted to the CCU for monitoring.

PAST MEDICAL HISTORY:
HTN - 10 years
DM2 - 5 years
No prior hospitalizations. NKDA.

PHYSICAL EXAMINATION:
BP: 130/80 mmHg, HR: 78 bpm, RR: 16/min, Temp: 36.8 C, SpO2: 98%

General: Patient is conscious, coherent, not in cardiorespiratory distress.
Cardiovascular: Regular rate and rhythm, no murmurs.
Respiratory: Clear breath sounds bilaterally.
Abdomen: Soft, non-tender, non-distended.
Extremities: No edema noted.

LABORATORY RESULTS:
Troponin I: 12.5 ng/mL (High)
Creatinine: 1.8 mg/dL (High)
FBS: 220 mg/dL (High)
Hemoglobin: 118 g/L (Low)
Sodium: 138 mmol/L
Potassium: 3.8 mmol/L
WBC: 11.2 x10^9/L (High)
Total Cholesterol: 245 mg/dL (High)
"""


ABDOMINAL_SAMPLE = """
FINAL DIAGNOSIS:
ACUTE ABDOMEN

CHIEF COMPLAINT:
ABDOMINAL PAIN

HISTORY OF PRESENT ILLNESS:
3 DAYS prior to admission, PATIENT NOTED ABDOMINAL PAIN, LEFT UPPER QUADRANT PAIN, THEN GRADUALLY TO RIGHT LOWER QUADRANT, WITH NO OTHER SYMPTOMS NOTED SUCH AS FEVER, CHEST PAIN, DYSURIA, VOMITING. SELF MEDICATED WITH HNBB AFFORDING TEMPORARY RELIEF. RECURRENCE OF SYMPTOMS PROMPTED CONSULT.

PAST MEDICAL HISTORY:
HYPERTENSION (2015) - MAINTAINED ON ENALAPRIL 5MG/TAB OD, ISMN 30MG/TAB OD, ASA 80MG/TAB OD, CLOPIDOGREL 75MG/TAB OD; CHRONIC CVD INFARCT (2015) - S/P DECOMPRESSIVE HEMICRANIECTOMY (2015, QMMC)

PHYSICAL EXAMINATION:
130/80 > 100 > 20 > 36.7 > 98%. AWAKE, COHERENT, NOT IN CARDIORESPIRATORY DISTRESS. ANICTERIC SCLERAE, PINK PALPEBRAL CONJUNCTIVAE, NO CERVICAL LYMPHADENOPATHIES. SYMMETRIC CHEST EXPANSION, NO RETRACTIONS, CLEAR BREATH SOUNDS. ADYNAMIC PRECORDIUM, NO MURMURS. ABDOMEN FLABBY, SOFT, DIRECT AND REBOUND TENDERNESS RLQ.

LABORATORY DATA:
CBC (04/15): 145/0.43/6.9/9.6/0.74/0.22/227. TROP I (04/15): 1.05 (H). CKMB (04/15): 18. ECG (04/15): NSR, T WAVE INVERSION V1-V3. WAB ULTRASOUND (04/15): NEGATIVE FOR APPENDICITIS. WAB CT SCAN (04/17): NO EVIDENCE OF ACUTE APPENDICITIS OR ANY ACUTE INTRA-ABDOMINAL PROCESS. REPEAT TROP I (04/16): 0.89.

COURSE IN THE WARD:
ON THE DAY OF ADMISSION (04/15) Patient was admitted. 1ST HOSPITAL DAY (04/16) Repeat troponin was done.
"""


def check(label, ok):
    status = "PASS" if ok else "FAIL"
    print(f"  {status}  {label}")
    assert ok, label


def run_tests():
    print("=" * 60)
    print("CLARA Discharge Parser - Test Suite")
    print("=" * 60)

    result = parse_discharge(SAMPLE)
    print("\nParsed output:\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\nField checks:")
    check("condition_discharge is not None", result["condition_discharge"] is not None)
    check("chief_complaint is not None", result["chief_complaint"] is not None)
    check("admitting_dx is not None", result["admitting_dx"] is not None)
    check("final_dx is not None", result["final_dx"] is not None)
    check("hpi is not None", result["hpi"] is not None)
    check("pmh is not None", result["pmh"] is not None)
    check("physical exam vitals detected", result["physical_exam"]["vitals"] is not None)
    check("physical exam findings detected", result["physical_exam"]["findings"] is not None)
    check("laboratory_data is not None", result["laboratory_data"] is not None)
    check("labs extracted", len(result["labs"]) > 0)
    check("abnormal labs flagged", any(l["flag"] for l in result["labs"]))
    check("raw abbreviation preserved", "SOB" in result["hpi"])
    check("final diagnosis does not contain HPI", "HISTORY OF PRESENT ILLNESS" not in result["final_dx"])

    abdominal = parse_discharge(ABDOMINAL_SAMPLE)
    check("abdominal final diagnosis is bounded", abdominal["final_dx"] == "ACUTE ABDOMEN")
    check("abdominal chief complaint is separate", abdominal["chief_complaint"] == "ABDOMINAL PAIN")
    check("abdominal HPI is separate", "3 DAYS prior to admission" in abdominal["hpi"])
    check("abdominal PMH is separate", "ENALAPRIL" in abdominal["pmh"])
    check("abdominal PE is separate", "AWAKE, COHERENT" in abdominal["physical_exam"]["findings"])
    check("abdominal lab text is separate", "CBC (04/15)" in abdominal["laboratory_data"])
    check("hospital course timeline extracted", len(abdominal["hospital_course"]) == 2)

    empty_result = parse_discharge("")
    check("empty input handled gracefully", empty_result["chief_complaint"] is None)

    minimal_result = parse_discharge("Patient presented with chest pain.")
    check("minimal input keeps labs as list", isinstance(minimal_result["labs"], list))

    print("\nDone.")


if __name__ == "__main__":
    run_tests()
