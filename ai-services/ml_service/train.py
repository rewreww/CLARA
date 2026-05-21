"""
CLARA ML Training Script
========================
Trains a multi-output XGBoost classifier on the EchoNext 100k dataset.
Predicts 4 key cardiovascular risk flags from ECG + demographics.

Targets:
  lvef_lte_45_flag         — Reduced ejection fraction (heart failure risk)
  shd_moderate_or_greater_flag — Any significant structural heart disease
  lvwt_gte_13_flag         — LV hypertrophy
  pasp_gte_45_flag         — Pulmonary hypertension

Run:  python train.py <path_to_csv>
"""

import sys
import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import (
    roc_auc_score, classification_report, average_precision_score
)
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

CSV_PATH    = sys.argv[1] if len(sys.argv) > 1 else "echonext_metadata_100k.csv"
OUTPUT_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(OUTPUT_DIR, "model.pkl")
META_PATH   = os.path.join(OUTPUT_DIR, "model_meta.json")

FEATURES = [
    "age_at_ecg",
    "sex_encoded",        # male=1 female=0
    "ventricular_rate",
    "atrial_rate",
    "pr_interval",
    "qrs_duration",
    "qt_corrected",
    "rate_difference",    # atrial_rate - ventricular_rate (AF indicator)
    "pr_missing",         # 1 if pr_interval is NaN (common in AF)
]

TARGETS = [
    "lvef_lte_45_flag",
    "shd_moderate_or_greater_flag",
    "lvwt_gte_13_flag",
    "pasp_gte_45_flag",
]

TARGET_LABELS = {
    "lvef_lte_45_flag":              "Reduced Ejection Fraction (LVEF ≤ 45%)",
    "shd_moderate_or_greater_flag":  "Structural Heart Disease",
    "lvwt_gte_13_flag":              "LV Hypertrophy (wall ≥ 13 mm)",
    "pasp_gte_45_flag":              "Pulmonary Hypertension (PASP ≥ 45 mmHg)",
}


def load_and_prepare(csv_path: str) -> pd.DataFrame:
    print(f"Loading {csv_path} ...")
    df = pd.read_csv(csv_path)
    print(f"  {len(df):,} rows, {df.shape[1]} columns")

    # Encode sex
    df["sex_encoded"] = (df["sex"].str.lower().str.strip() == "male").astype(int)

    # AF/flutter indicator: atrial rate much higher than ventricular
    df["rate_difference"] = df["atrial_rate"] - df["ventricular_rate"]

    # PR interval missingness (marker for AF where P waves absent)
    df["pr_missing"] = df["pr_interval"].isna().astype(int)

    # Drop rows where ALL targets are NaN
    df = df.dropna(subset=TARGETS, how="all")
    print(f"  {len(df):,} rows after dropping missing-label rows")

    return df


def split_data(df: pd.DataFrame):
    # Use the dataset's own split column
    train = df[df["split"] == "train"]
    val   = df[df["split"] == "val"]
    test  = df[df["split"] == "test"]

    # Fallback: if no split column values match, do 80/10/10
    if len(val) == 0 or len(test) == 0:
        print("  WARNING: split column missing val/test — using 80/10/10 random split")
        from sklearn.model_selection import train_test_split
        train, temp = train_test_split(df, test_size=0.2, random_state=42)
        val, test   = train_test_split(temp, test_size=0.5, random_state=42)

    print(f"  Train: {len(train):,}  Val: {len(val):,}  Test: {len(test):,}")
    return train, val, test


def prepare_xy(df: pd.DataFrame):
    X = df[FEATURES].copy()
    Y = df[TARGETS].copy()
    # XGBoost handles NaN natively — no imputation needed
    return X, Y


def train_model(X_train, Y_train):
    print("\nTraining XGBoost multi-output classifier ...")
    base = xgb.XGBClassifier(
        n_estimators     = 300,
        max_depth        = 6,
        learning_rate    = 0.05,
        subsample        = 0.8,
        colsample_bytree = 0.8,
        use_label_encoder= False,
        eval_metric      = "logloss",
        random_state     = 42,
        n_jobs           = -1,
        tree_method      = "hist",
    )
    model = MultiOutputClassifier(base, n_jobs=-1)
    model.fit(X_train.values, Y_train.fillna(0).values)
    print("  Training complete.")
    return model


def evaluate(model, X_test, Y_test):
    print("\n── Test Set Evaluation ─────────────────────────────────────────")
    Y_pred_proba = np.array([
        est.predict_proba(X_test.values)[:, 1]
        for est in model.estimators_
    ]).T

    metrics = {}
    for i, target in enumerate(TARGETS):
        mask  = Y_test[target].notna()
        y_true = Y_test[target][mask].values
        y_prob = Y_pred_proba[mask, i]

        if len(np.unique(y_true)) < 2:
            print(f"  {target}: skipped (single class in test set)")
            continue

        auroc = roc_auc_score(y_true, y_prob)
        auprc = average_precision_score(y_true, y_prob)
        prev  = y_true.mean()

        print(f"  {TARGET_LABELS[target]}")
        print(f"    AUROC: {auroc:.3f}  |  AUPRC: {auprc:.3f}  |  Prevalence: {prev:.1%}")
        metrics[target] = {"auroc": round(auroc, 4), "auprc": round(auprc, 4), "prevalence": round(float(prev), 4)}

    return metrics


def save(model, metrics):
    joblib.dump(model, MODEL_PATH)
    print(f"\nModel saved → {MODEL_PATH}")

    meta = {
        "features":      FEATURES,
        "targets":       TARGETS,
        "target_labels": TARGET_LABELS,
        "metrics":       metrics,
        "note":          "Trained on EchoNext 100k dataset. For research/demo use only.",
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Metadata saved → {META_PATH}")


def main():
    df              = load_and_prepare(CSV_PATH)
    train, val, test = split_data(df)
    X_train, Y_train = prepare_xy(train)
    X_test,  Y_test  = prepare_xy(test)

    model   = train_model(X_train, Y_train)
    metrics = evaluate(model, X_test, Y_test)
    save(model, metrics)
    print("\nDone.")


if __name__ == "__main__":
    main()
