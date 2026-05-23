"""
CLARA ML Training — EchoNext ECG-to-Echo Dataset
=================================================
1. Copy CSV to:  ai-services/ml_service/data/
2. Run:          python train.py
3. Output:       model.pkl  +  model_meta.json
"""

import json
import joblib
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline

warnings.filterwarnings('ignore')

BASE = Path(__file__).parent

# ── Human-readable labels for the UI ──────────────────────────────────────────
TARGET_LABELS = {
    "lvef_lte_45_flag":                                "Reduced Ejection Fraction (LVEF ≤ 45%)",
    "shd_moderate_or_greater_flag":                    "Structural Heart Disease",
    "lvwt_gte_13_flag":                                "LV Hypertrophy (Wall ≥ 13 mm)",
    "pasp_gte_45_flag":                                "Pulmonary Hypertension (PASP ≥ 45 mmHg)",
    "rv_systolic_dysfunction_moderate_or_greater_flag":"RV Systolic Dysfunction",
    "mitral_regurgitation_moderate_or_greater_flag":   "Mitral Regurgitation (Moderate+)",
    "aortic_stenosis_moderate_or_greater_flag":        "Aortic Stenosis (Moderate+)",
    "pericardial_effusion_moderate_large_flag":        "Pericardial Effusion (Moderate/Large)",
}


def load_config():
    with open(BASE / "column_config.json") as f:
        return json.load(f)


def prepare_data(df, config):
    feature_map = {
        std: csv for std, csv in config["feature_columns"].items()
        if csv and csv in df.columns
    }
    target_map = {
        std: csv for std, csv in config["target_columns"].items()
        if csv and csv in df.columns
    }

    if not feature_map:
        raise ValueError("No feature columns matched — check column_config.json")
    if not target_map:
        raise ValueError("No target columns matched — check column_config.json")

    # Encode sex
    encodings = config.get("categorical_encodings", {})
    for std_name, csv_col in feature_map.items():
        if csv_col in encodings:
            df[csv_col] = df[csv_col].map(encodings[csv_col]).fillna(df[csv_col])

    X = pd.DataFrame()
    for std_name, csv_col in feature_map.items():
        X[std_name] = pd.to_numeric(df[csv_col], errors="coerce")

    Y = pd.DataFrame()
    for std_name, csv_col in target_map.items():
        Y[std_name] = pd.to_numeric(df[csv_col], errors="coerce").fillna(0).astype(int)

    return X, Y, list(feature_map.keys()), list(target_map.keys())


def train():
    config = load_config()

    csv_path = BASE / config["csv_file"]
    if not csv_path.exists():
        raise FileNotFoundError(
            f"\nCSV not found at: {csv_path}"
            f"\nCopy your file to: {BASE / 'data/'}"
        )

    print(f"Loading {csv_path.name} ...")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"  Total rows: {len(df):,}  |  Columns: {len(df.columns)}")

    # ── Use predefined split ───────────────────────────────────────────────
    split_col = config.get("split_column", "split")
    train_val = config.get("split_train_value", "train")

    if split_col in df.columns:
        train_df = df[df[split_col] == train_val]
        test_df  = df[df[split_col] != train_val]
        print(f"  Train: {len(train_df):,}  |  Test: {len(test_df):,}  (using '{split_col}' column)")
    else:
        from sklearn.model_selection import train_test_split
        train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
        print(f"  Train: {len(train_df):,}  |  Test: {len(test_df):,}  (random split)")

    X_train, Y_train, feature_names, target_names = prepare_data(train_df.copy(), config)
    X_test,  Y_test,  _,             _            = prepare_data(test_df.copy(),  config)

    print(f"\n  Features ({len(feature_names)}): {feature_names}")
    print(f"  Targets  ({len(target_names)}): {target_names}")

    # ── Class balance info ─────────────────────────────────────────────────
    print("\n  Class balance (% positive):")
    for t in target_names:
        pct = Y_train[t].mean() * 100
        print(f"    {t}: {pct:.1f}%")

    # ── Model: XGBoost preferred, GradientBoosting fallback ───────────────
    try:
        from xgboost import XGBClassifier
        base = XGBClassifier(
            n_estimators    = 300,
            max_depth       = 6,
            learning_rate   = 0.05,
            subsample       = 0.8,
            colsample_bytree= 0.8,
            eval_metric     = "logloss",
            verbosity        = 1, 
            n_jobs          = -1,
            random_state    = 42,
        )
        print("\nUsing XGBoost")
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        base = GradientBoostingClassifier(
            n_estimators=200, max_depth=4,
            learning_rate=0.05, subsample=0.8, random_state=42,
        )
        print("\nXGBoost not installed — using GradientBoosting (add xgboost to requirements.txt for better results)")

    from sklearn.multioutput import MultiOutputClassifier
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf",     MultiOutputClassifier(base, n_jobs=-1)),
    ])

    print("Training ...")
    pipeline.fit(X_train, Y_train)

    # ── Evaluation ─────────────────────────────────────────────────────────
    print("\n── Evaluation ─────────────────────────────────")
    proba_list = pipeline.predict_proba(X_test)
    y_pred     = pipeline.predict(X_test)

    metrics = {}
    for i, name in enumerate(target_names):
        true  = Y_test.iloc[:, i].values
        pred  = y_pred[:, i]
        probs = proba_list[i][:, 1]

        try:
            auroc = float(roc_auc_score(true, probs))
        except Exception:
            auroc = None

        label = TARGET_LABELS.get(name, name)
        print(f"\n  [{label}]")
        print(classification_report(true, pred, zero_division=0, digits=3))
        if auroc:
            print(f"  AUROC: {auroc:.4f}")
        metrics[name] = {"auroc": auroc, "label": label}

    # ── Save ───────────────────────────────────────────────────────────────
    joblib.dump(pipeline, BASE / "model.pkl")


    meta = {
        "feature_names": feature_names,
        "target_names":  target_names,
        "target_labels": {n: TARGET_LABELS.get(n, n) for n in target_names},
        "metrics":       metrics,
        "n_train":       len(X_train),
        "n_test":        len(X_test),
    }
    with open(BASE / "model_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n✓ model.pkl        saved")
    print(f"✓ model_meta.json  saved")
    print("\n── Summary ─────────────────────────────────────")
    for name, m in metrics.items():
        auroc_str = f"{m['auroc']:.4f}" if m['auroc'] else "N/A"
        print(f"  {m['label']:<50} AUROC: {auroc_str}")
    print("\nDone. Start the service: python app.py")


if __name__ == "__main__":
    train()