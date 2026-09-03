import json
import joblib
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

warnings.filterwarnings('ignore')

BASE  = Path(__file__).parent
MODEL = None
META  = None
CONFIG = None

FALLBACK_TARGET_LABELS = {
    "heart_failure_type": "Heart Failure Type",
    "myocardial_infarction": "Myocardial Infarction",
    "congestive_heart_failure": "Congestive Heart Failure",
    "death_28d":       "28-Day Mortality",
    "readmission_28d": "28-Day Readmission",
    "death_6mo":       "6-Month Mortality",
    "readmission_6mo": "6-Month Readmission",
    "ed_return_6mo":   "6-Month Emergency Department Return",
}


def load_model():
    global MODEL, META, CONFIG
    mp = BASE / "model.pkl"
    mm = BASE / "model_meta.json"
    cm = BASE / "column_config.json"
    if not mp.exists():
        print("  WARNING: model.pkl not found. Run train.py first.")
        return
    MODEL = joblib.load(mp)
    with open(mm) as f:
        META = json.load(f)
    if cm.exists():
        with open(cm) as f:
            CONFIG = json.load(f)
    print(f"  Model loaded | features: {len(META['feature_names'])}")
    print(f"  Targets ({len(META['target_names'])}): {META['target_names']}")


load_model()   # called here, before app starts


app = FastAPI(title="CLARA ML Service - Heart Failure Prognosis Predictor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    features: Optional[Dict[str, Any]] = None


class RiskPrediction(BaseModel):
    key:         str
    label:       str
    probability: float
    risk:        str
    prediction: Optional[str] = None
    class_probabilities: Optional[Dict[str, float]] = None
    target_type: str = "binary"


class PredictResponse(BaseModel):
    predictions:  List[RiskPrediction]
    overall_risk: float
    model_ready:  bool
    features_received: int
    missing_features: List[str]


def encode_categorical(csv_col: str, val) -> Optional[float]:
    if val is None:
        return None

    encodings = (CONFIG or {}).get("categorical_encodings", {})
    mapping = encodings.get(csv_col)
    if not mapping:
        return val

    if isinstance(val, (int, float)):
        return val

    text = str(val).strip()
    if text in mapping:
        return mapping[text]

    lowered = text.lower()
    for key, encoded in mapping.items():
        if str(key).lower() == lowered:
            return encoded
    return None


def coerce_number(val) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def request_payload(req: PredictRequest) -> Dict[str, Any]:
    payload = req.model_dump(exclude_none=True, exclude={"features"})
    payload.update(req.model_extra or {})
    if req.features:
        payload.update(req.features)
    return payload


def build_feature_row(req: PredictRequest, feature_names: List[str]):
    payload = request_payload(req)
    feature_map = (CONFIG or {}).get("feature_columns", {})
    values = {}
    missing = []

    for feature in feature_names:
        csv_col = feature_map.get(feature, feature)
        val = payload.get(feature)
        if val is None:
            val = payload.get(csv_col)
        val = encode_categorical(csv_col, val)
        numeric = coerce_number(val)
        values[feature] = numeric
        if numeric is None:
            missing.append(feature)

    row = pd.DataFrame([[values[f] for f in feature_names]], columns=feature_names)
    received = len(feature_names) - len(missing)
    return row, received, missing


def risk_label(p: float) -> str:
    return "high" if p >= 0.65 else "moderate" if p >= 0.35 else "low"


def target_class_label(target_name: str, value) -> str:
    target_map = (CONFIG or {}).get("target_columns", {})
    csv_col = target_map.get(target_name, target_name)
    mapping = ((CONFIG or {}).get("categorical_encodings", {}) or {}).get(csv_col, {})
    for label, encoded in mapping.items():
        if str(encoded) == str(value):
            return str(label)
    return str(value)


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if MODEL is None or META is None:
        raise HTTPException(503, "Model not loaded — run train.py first")

    feature_names = META["feature_names"]
    target_names  = META["target_names"]
    target_labels = {**FALLBACK_TARGET_LABELS, **META.get("target_labels", {})}
    row, features_received, missing_features = build_feature_row(req, feature_names)

    try:
        proba_list = MODEL.predict_proba(row)
    except Exception as e:
        raise HTTPException(500, f"Prediction failed: {e}")

    predictions = []
    binary_probabilities = []
    target_types = META.get("target_types", {})
    for i, name in enumerate(target_names):
        estimator = MODEL.named_steps["clf"].estimators_[i]
        classes = list(getattr(estimator, "classes_", []))
        probabilities = proba_list[i][0]
        target_type = target_types.get(name, "binary")
        if target_type == "multiclass" or len(classes) > 2:
            best_index = int(np.argmax(probabilities))
            prob = float(probabilities[best_index])
            predicted = target_class_label(name, classes[best_index])
            class_probs = {
                target_class_label(name, class_value): round(float(probabilities[index]), 4)
                for index, class_value in enumerate(classes)
            }
            predictions.append(RiskPrediction(
                key=name,
                label=target_labels.get(name, name.replace("_", " ").title()),
                probability=round(prob, 4),
                risk=risk_label(prob),
                prediction=predicted,
                class_probabilities=class_probs,
                target_type="multiclass",
            ))
        else:
            positive_index = classes.index(1) if 1 in classes else len(classes) - 1
            prob = float(probabilities[positive_index])
            binary_probabilities.append(prob)
            predictions.append(RiskPrediction(
                key=name,
                label=target_labels.get(name, name.replace("_", " ").title()),
                probability=round(prob, 4),
                risk=risk_label(prob),
                prediction="Yes" if prob >= 0.5 else "No",
                target_type="binary",
            ))

    predictions.sort(key=lambda x: x.probability, reverse=True)
    overall = round(float(np.mean(binary_probabilities)), 4) if binary_probabilities else 0.0

    return PredictResponse(
        predictions  = predictions,
        overall_risk = overall,
        model_ready  = True,
        features_received = features_received,
        missing_features  = missing_features,
    )


@app.get("/model-info")
def model_info():
    if META is None:
        return {"ready": False, "message": "Run train.py first"}
    return {
        "ready":    True,
        "features": META["feature_names"],
        "targets":  META["target_names"],
        "target_labels": {**FALLBACK_TARGET_LABELS, **META.get("target_labels", {})},
        "target_types": META.get("target_types", {}),
        "csv_file": META.get("csv_file"),
        "n_train":  META.get("n_train"),
        "metrics":  {k: v.get("auroc") for k, v in META.get("metrics", {}).items()},
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": MODEL is not None,
        "model_type": "heart_failure_prognosis",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8002)
