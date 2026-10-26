"""Audit a synthetic request against the saved model; no patient data or writes."""
import importlib.util
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("clara_ml_audit", root / "ai-services/ml_service/app.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
print(json.dumps({"health": service.health()}))
request = service.PredictRequest(features={
    "gender": "Female", "pulse": 80, "systolic_blood_pressure": 120,
    "diastolic_blood_pressure": 80, "body_temperature": 37,
})
result = service.predict(request)
assert result.model_ready
assert len(result.predictions) == len(service.META["target_names"])
assert all(0 <= p.probability <= 1 for p in result.predictions)
print(json.dumps({
    "synthetic_prediction": "PASS",
    "target_count": len(result.predictions),
    "features_received": result.features_received,
    "missing_features": len(result.missing_features),
}))
