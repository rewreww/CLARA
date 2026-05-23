import json
import pickle
import warnings
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

warnings.filterwarnings('ignore')

BASE  = Path(__file__).parent
MODEL = None
META  = None


def load_model():
    global MODEL, META
    mp, mm = BASE / "model.pkl", BASE / "model_meta.json"
    if not mp.exists():
        print("  ⚠  model.pkl not found — run train.py first")
        return
    with open(mp, "rb") as f:
        MODEL = pickle.load(f)
    with open(mm) as f:
        META = json.load(f)
    print(f"  ✓ Model loaded | features: {META['feature_names']}")
    print(f"  ✓ Targets ({len(META['target_names'])}): {META['target_names']}")


load_model()

app = FastAPI(title="CLARA ML Service — EchoNext ECG Predictor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PredictRequest(BaseModel):
    # Core ECG features — matches training data
    age_at_ecg:      Optional[float] = None
    sex:             Optional[str]   = None   # M/F
    ventricular_rate:Optional[float] = None
    atrial_rate:     Optional[float] = None
    pr_interval:     Optional[float] = None
    qrs_duration:    Optional[float] = None
    qt_corrected:    Optional[float] = None

    # Legacy field names (from DiagnosticTool ECG text extraction)
    age:             Optional[float] = None   # fallback for age_at_ecg
    heart_rate:      Optional[float] = None   # fallback for ventricular_rate


class RiskPrediction(BaseModel):
    key:         str
    label:       str
    probability: float
    risk:        str   # low / moderate / high


class PredictResponse(BaseModel):
    predictions:  List[RiskPrediction]
    overall_risk: float
    model_ready:  bool


def sex_encode(val) -> Optional[float]:
    if val is None:
        return None
    m = {"m": 1, "male": 1, "f": 0, "female": 0}
    return m.get(str(val).lower().strip())


def risk_label(p: float) -> str:
    return "high" if p >= 0.65 else "moderate" if p >= 0.35 else "low"


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if MODEL is None or META is None:
        raise HTTPException(503, "Model not loaded — run train.py first")

    feature_names = META["feature_names"]
    target_labels = META.get("target_labels", {})

    # Resolve aliases
    age  = req.age_at_ecg or req.age
    vr   = req.ventricular_rate or req.heart_rate
    sex  = sex_encode(req.sex)

    raw = {
        "age_at_ecg":       age,
        "sex":              sex,
        "ventricular_rate": vr,
        "atrial_rate":      req.atrial_rate,
        "pr_interval":      req.pr_interval,
        "qrs_duration":     req.qrs_duration,
        "qt_corrected":     req.qt_corrected,
    }

    row = pd.DataFrame([[raw.get(f) for f in feature_names]], columns=feature_names)

    try:
        proba_list = MODEL.predict_proba(row)
    except Exception as e:
        raise HTTPException(500, f"Prediction failed: {e}")

    predictions = []
    for i, name in enumerate(META["target_names"]):
        prob = float(proba_list[i][0][1])   # probability of positive class
        predictions.append(RiskPrediction(
            key         = name,
            label       = target_labels.get(name, name.replace("_", " ").title()),
            probability = round(prob, 4),
            risk        = risk_label(prob),
        ))

    # Sort by probability descending
    predictions.sort(key=lambda x: x.probability, reverse=True)
    overall = round(float(np.mean([p.probability for p in predictions])), 4)

    return PredictResponse(
        predictions  = predictions,
        overall_risk = overall,
        model_ready  = True,
    )


@app.get("/model-info")
def model_info():
    if META is None:
        return {"ready": False, "message": "Run train.py first"}
    return {
        "ready":    True,
        "features": META["feature_names"],
        "targets":  META["target_names"],
        "n_train":  META.get("n_train"),
        "metrics":  {k: v.get("auroc") for k, v in META.get("metrics", {}).items()},
    }


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": MODEL is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)