"""
Generate dummy Filipino ECG patients for CLARA demo.
Predictions are generated from the trained model — not hardcoded.
Run this after train.py.
"""

import json, os, joblib, numpy as np, pandas as pd

MODEL_PATH  = os.path.join(os.path.dirname(__file__), "model.pkl")
META_PATH   = os.path.join(os.path.dirname(__file__), "model_meta.json")
OUT_PATH    = os.path.join(os.path.dirname(__file__), "dummy_patients.json")

FEATURES = [
    "age_at_ecg", "sex_encoded", "ventricular_rate", "atrial_rate",
    "pr_interval", "qrs_duration", "qt_corrected", "rate_difference", "pr_missing",
]

# Each patient profile — ECG values chosen to produce clinically varied predictions
# Sources: normal ranges from AHA ECG guidelines
PROFILES = [
    {
        "id": "ECG-001",
        "name": "Juan dela Cruz",
        "age": 45, "sex": "Male",
        "ward": "Cardiology", "status": "stable",
        "clinical_note": "Routine check-up, no complaints",
        "ecg": {
            "age_at_ecg": 45, "sex_encoded": 1,
            "ventricular_rate": 78, "atrial_rate": 78,
            "pr_interval": 156, "qrs_duration": 88, "qt_corrected": 420,
            "rate_difference": 0, "pr_missing": 0,
        }
    },
    {
        "id": "ECG-002",
        "name": "Maria Santos",
        "age": 62, "sex": "Female",
        "ward": "Cardiology", "status": "review",
        "clinical_note": "Hypertension x 10 years, dyspnea on exertion",
        "ecg": {
            "age_at_ecg": 62, "sex_encoded": 0,
            "ventricular_rate": 88, "atrial_rate": 88,
            "pr_interval": 174, "qrs_duration": 118, "qt_corrected": 470,
            "rate_difference": 0, "pr_missing": 0,
        }
    },
    {
        "id": "ECG-003",
        "name": "Roberto Reyes",
        "age": 71, "sex": "Male",
        "ward": "ICU", "status": "critical",
        "clinical_note": "Admitted for palpitations, irregular pulse, known CAD",
        "ecg": {
            "age_at_ecg": 71, "sex_encoded": 1,
            "ventricular_rate": 94, "atrial_rate": 380,   # Atrial fibrillation
            "pr_interval": None, "qrs_duration": 102, "qt_corrected": 490,
            "rate_difference": 286, "pr_missing": 1,
        }
    },
    {
        "id": "ECG-004",
        "name": "Anita Bautista",
        "age": 58, "sex": "Female",
        "ward": "Cardiology", "status": "critical",
        "clinical_note": "Progressive dyspnea, bilateral leg edema, dilated cardiomyopathy",
        "ecg": {
            "age_at_ecg": 58, "sex_encoded": 0,
            "ventricular_rate": 112, "atrial_rate": 112,
            "pr_interval": None, "qrs_duration": 168, "qt_corrected": 560,
            "rate_difference": 0, "pr_missing": 1,
        }
    },
    {
        "id": "ECG-005",
        "name": "Carlos Mendoza",
        "age": 67, "sex": "Male",
        "ward": "Pulmonology", "status": "review",
        "clinical_note": "Cor pulmonale, COPD, increasing DOB",
        "ecg": {
            "age_at_ecg": 67, "sex_encoded": 1,
            "ventricular_rate": 102, "atrial_rate": 102,
            "pr_interval": 148, "qrs_duration": 96, "qt_corrected": 510,
            "rate_difference": 0, "pr_missing": 0,
        }
    },
    {
        "id": "ECG-006",
        "name": "Ligaya Garcia",
        "age": 34, "sex": "Female",
        "ward": "General", "status": "stable",
        "clinical_note": "Annual cardiac screening, asymptomatic",
        "ecg": {
            "age_at_ecg": 34, "sex_encoded": 0,
            "ventricular_rate": 68, "atrial_rate": 68,
            "pr_interval": 142, "qrs_duration": 76, "qt_corrected": 398,
            "rate_difference": 0, "pr_missing": 0,
        }
    },
]

TARGET_LABELS = {
    "lvef_lte_45_flag":             "Reduced Ejection Fraction (LVEF ≤ 45%)",
    "shd_moderate_or_greater_flag": "Structural Heart Disease",
    "lvwt_gte_13_flag":             "LV Hypertrophy",
    "pasp_gte_45_flag":             "Pulmonary Hypertension",
}

RISK_THRESHOLDS = {"low": 0.30, "moderate": 0.55}


def risk_level(prob: float) -> str:
    if prob >= RISK_THRESHOLDS["moderate"]:
        return "high"
    if prob >= RISK_THRESHOLDS["low"]:
        return "moderate"
    return "low"


def main():
    model = joblib.load(MODEL_PATH)
    targets = list(TARGET_LABELS.keys())

    patients = []
    for p in PROFILES:
        row = [p["ecg"].get(f) for f in FEATURES]
        X   = np.array(row, dtype=float).reshape(1, -1)

        probas = [est.predict_proba(X)[0, 1] for est in model.estimators_]

        predictions = [
            {
                "key":        targets[i],
                "label":      TARGET_LABELS[targets[i]],
                "probability": round(float(probas[i]), 3),
                "risk":       risk_level(probas[i]),
            }
            for i in range(len(targets))
        ]

        overall_risk = max(pred["probability"] for pred in predictions)

        patients.append({
            "id":           p["id"],
            "name":         p["name"],
            "age":          p["age"],
            "sex":          p["sex"],
            "ward":         p["ward"],
            "status":       p["status"],
            "clinical_note": p["clinical_note"],
            "ecg_values": {
                "ventricular_rate": p["ecg"]["ventricular_rate"],
                "atrial_rate":      p["ecg"]["atrial_rate"],
                "pr_interval":      p["ecg"]["pr_interval"],
                "qrs_duration":     p["ecg"]["qrs_duration"],
                "qt_corrected":     p["ecg"]["qt_corrected"],
            },
            "predictions":  predictions,
            "overall_risk": round(float(overall_risk), 3),
        })

        print(f"{p['name']} ({p['age']}{'M' if p['sex']=='Male' else 'F'})")
        for pred in predictions:
            bar = "█" * int(pred["probability"] * 20)
            print(f"  {pred['label'][:40]:<40} {bar:<20} {pred['probability']:.1%} [{pred['risk'].upper()}]")
        print()

    with open(OUT_PATH, "w") as f:
        json.dump(patients, f, indent=2)
    print(f"Saved {len(patients)} dummy patients → {OUT_PATH}")


if __name__ == "__main__":
    main()
