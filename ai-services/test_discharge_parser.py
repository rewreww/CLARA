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
BP: 130/80 mmHg, HR: 78 bpm, RR: 16/min, Temp: 36.8°C, SpO2: 98%

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


def run_tests():
    print("=" * 60)
    print("CLARA Discharge Parser — Test Suite")
    print("=" * 60)

    result = parse_discharge(SAMPLE)
    print("\nParsed output:\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("Field checks:")
    print("=" * 60)

    checks = [
        ("condition_discharge is not None",  result["condition_discharge"] is not None),
        ("chief_complaint is not None",       result["chief_complaint"]     is not None),
        ("admitting_dx is not None",          result["admitting_dx"]        is not None),
        ("final_dx is not None",              result["final_dx"]            is not None),
        ("hpi is not None",                   result["hpi"]                 is not None),
        ("pmh is not None",                   result["pmh"]                 is not None),
        ("vitals detected",                   result["physical_exam"]["vitals"] is not None),
        ("findings detected",                 result["physical_exam"]["findings"] is not None),
        ("labs extracted",                    len(result["labs"]) > 0),
        ("abnormal labs flagged",             any(l["flag"] for l in result["labs"])),
        ("SOB expanded",                      result["hpi"] and "shortness of breath" in result["hpi"].lower()),
        ("HTN expanded in final_dx",          result["final_dx"] and "hypertension" in result["final_dx"].lower()),
    ]

    passed = 0
    for label, ok in checks:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}  {label}")
        if ok:
            passed += 1

    print(f"\n{passed}/{len(checks)} checks passed")

    # Empty input test
    empty_result = parse_discharge("")
    assert empty_result["chief_complaint"] is None, "Empty input should return None fields"
    print("\n✓ PASS  Empty input handled gracefully")

    # Missing sections test
    minimal = "Patient presented with chest pain."
    minimal_result = parse_discharge(minimal)
    assert isinstance(minimal_result["labs"], list), "Labs should always be a list"
    print("✓ PASS  Minimal input handled gracefully")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    run_tests()