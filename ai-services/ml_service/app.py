"""
CLARA ML Service — ECG Risk Prediction
Port 8002 | Separate from lab service (8000) and LLM service (8001)

DEMO NOTE: Uses dummy Filipino patients + EchoNext-trained model.
           This service is designed to be removable — it is fully isolated.
"""

import os
import json
import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(BASE_DIR, "model.pkl")
META_PATH   = os.path.join(BASE_DIR, "model_meta.json")
DUMMY_PATH  = os.path.join(BASE_DIR, "dummy_patients.json")

app = FastAPI(title="CLARA ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load model once at startup ────────────────────────────────────────────────

model = None
meta  = {}

try:
    model = joblib.load(MODEL_PATH)
    with open(META_PATH) as f:
        meta = json.load(f)
    print(f"Model loaded: {len(meta.get('targets', []))} targets")
except Exception as e:
    print(f"WARNING: Model not loaded — {e}. Run train.py first.")


FEATURES = [
    "age_at_ecg", "sex_encoded", "ventricular_rate", "atrial_rate",
    "pr_interval", "qrs_duration", "qt_corrected", "rate_difference", "pr_missing",
]

RISK_THRESHOLDS = {"low": 0.30, "moderate": 0.55}


def risk_level(prob: float) -> str:
    if prob >= RISK_THRESHOLDS["moderate"]:  return "high"
    if prob >= RISK_THRESHOLDS["low"]:       return "moderate"
    return "low"


class EcgInput(BaseModel):
    age:              int
    sex:              str
    ventricular_rate: float
    atrial_rate:      float
    pr_interval:      Optional[float] = None
    qrs_duration:     float
    qt_corrected:     float


class RiskPrediction(BaseModel):
    key:         str
    label:       str
    probability: float
    risk:        str


class PredictResponse(BaseModel):
    predictions:  list[RiskPrediction]
    overall_risk: float
    model_note:   str


@app.post("/predict", response_model=PredictResponse)
def predict(ecg: EcgInput):
    if model is None:
        raise HTTPException(status_code=503, detail="ML model not loaded. Run train.py first.")

    sex_enc         = 1 if ecg.sex.lower() == "male" else 0
    pr_missing      = 1 if ecg.pr_interval is None else 0
    rate_difference = ecg.atrial_rate - ecg.ventricular_rate
    pr_val          = ecg.pr_interval if ecg.pr_interval is not None else float("nan")

    row = [
        ecg.age, sex_enc, ecg.ventricular_rate, ecg.atrial_rate,
        pr_val, ecg.qrs_duration, ecg.qt_corrected, rate_difference, pr_missing,
    ]
    X = np.array(row, dtype=float).reshape(1, -1)

    targets       = meta.get("targets", [])
    target_labels = meta.get("target_labels", {})
    probas        = [est.predict_proba(X)[0, 1] for est in model.estimators_]

    predictions = [
        RiskPrediction(
            key         = targets[i],
            label       = target_labels.get(targets[i], targets[i]),
            probability = round(float(probas[i]), 3),
            risk        = risk_level(probas[i]),
        )
        for i in range(len(targets))
    ]

    return PredictResponse(
        predictions  = predictions,
        overall_risk = round(float(max(p.probability for p in predictions)), 3),
        model_note   = meta.get("note", ""),
    )


@app.get("/demo-patients")
def demo_patients():
    if not os.path.exists(DUMMY_PATH):
        raise HTTPException(status_code=404, detail="Run generate_dummy_patients.py first.")
    with open(DUMMY_PATH) as f:
        return json.load(f)


@app.get("/model-info")
def model_info():
    return {
        "loaded":   model is not None,
        "features": FEATURES,
        "targets":  meta.get("targets", []),
        "metrics":  meta.get("metrics", {}),
        "note":     meta.get("note", ""),
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "CLARA ML", "model_loaded": model is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
