"""
CLARA ML Training — Heart Failure Prognosis Dataset
===================================================
1. Copy CSV to:  ai-services/ml_service/data/
2. Run:          python train.py [optional/path/to/dataset.csv]
3. Output:       model.pkl + model_meta.json + confusion_matrices.png
"""

import argparse
import json
import joblib
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline

warnings.filterwarnings('ignore')

BASE = Path(__file__).parent

# Human-readable labels for the UI and evaluation outputs.
TARGET_LABELS = {
    "heart_failure_type": "Heart Failure Type",
    "myocardial_infarction": "Myocardial Infarction",
    "congestive_heart_failure": "Congestive Heart Failure",
    "death_28d":       "28-Day Mortality",
    "readmission_28d": "28-Day Readmission",
    "death_6mo":       "6-Month Mortality",
    "readmission_6mo": "6-Month Readmission",
    "ed_return_6mo":   "6-Month Emergency Department Return",
}


def load_config(config_path=None):
    path = Path(config_path) if config_path else BASE / "column_config.json"
    if not path.is_absolute():
        path = BASE / path
    with open(path) as f:
        return json.load(f)


def resolve_csv_path(config, csv_override=None):
    if csv_override:
        path = Path(csv_override)
        if path.is_absolute():
            return path

        cwd_relative = Path.cwd() / path
        if cwd_relative.exists():
            return cwd_relative
        return BASE / path

    return BASE / config["csv_file"]


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

    # Encode categorical columns configured in column_config.json.
    encodings = config.get("categorical_encodings", {})
    for std_name, csv_col in feature_map.items():
        if csv_col in encodings:
            df[csv_col] = df[csv_col].map(encodings[csv_col]).fillna(df[csv_col])

    X = pd.DataFrame()
    for std_name, csv_col in feature_map.items():
        X[std_name] = pd.to_numeric(df[csv_col], errors="coerce")

    Y = pd.DataFrame()
    for std_name, csv_col in target_map.items():
        target_values = df[csv_col]
        if csv_col in encodings:
            target_values = target_values.map(encodings[csv_col]).fillna(target_values)
        Y[std_name] = pd.to_numeric(target_values, errors="coerce")

    # A missing target cannot be learned. Drop only those rows, per target,
    # during fitting/evaluation rather than silently converting them to class 0.
    Y = Y.fillna(-1).astype(int)

    return X, Y, list(feature_map.keys()), list(target_map.keys())


def save_confusion_matrices(y_true, y_pred, target_names, target_labels):
    import matplotlib.pyplot as plt

    n_targets = len(target_names)
    n_cols = 3
    n_rows = int(np.ceil(n_targets / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    axes = np.array(axes).reshape(-1)

    matrices = {}
    for i, name in enumerate(target_names):
        ax = axes[i]
        classes = sorted(set(y_true.iloc[:, i].values) | set(y_pred[:, i]))
        cm = confusion_matrix(y_true.iloc[:, i].values, y_pred[:, i], labels=classes)
        matrices[name] = cm.astype(int).tolist()

        im = ax.imshow(cm, cmap="Blues")
        ax.set_title(target_labels.get(name, name), fontsize=10)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_xticks(range(len(classes)), labels=[str(c) for c in classes])
        ax.set_yticks(range(len(classes)), labels=[str(c) for c in classes])

        threshold = cm.max() / 2 if cm.max() else 0
        for row in range(len(classes)):
            for col in range(len(classes)):
                color = "white" if cm[row, col] > threshold else "black"
                ax.text(col, row, str(cm[row, col]), ha="center", va="center", color=color)

        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    for ax in axes[n_targets:]:
        ax.axis("off")

    output_path = BASE / "confusion_matrices.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path, matrices


def parse_args():
    parser = argparse.ArgumentParser(description="Train the CLARA prognosis model.")
    parser.add_argument(
        "csv_file",
        nargs="?",
        help="Optional CSV path. If omitted, column_config.json csv_file is used.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional column mapping JSON path. Defaults to column_config.json.",
    )
    return parser.parse_args()


def train(csv_file=None, config_path=None):
    config = load_config(config_path)

    csv_path = resolve_csv_path(config, csv_file)
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

    if split_col and split_col in df.columns:
        train_df = df[df[split_col] == train_val]
        test_df  = df[df[split_col] != train_val]
        print(f"  Train: {len(train_df):,}  |  Test: {len(test_df):,}  (using '{split_col}' column)")
    else:
        from sklearn.model_selection import train_test_split
        train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
        print(f"  Train: {len(train_df):,}  |  Test: {len(test_df):,}  (random split)")

    X_train, Y_train, feature_names, target_names = prepare_data(train_df.copy(), config)
    X_test,  Y_test,  _,             _            = prepare_data(test_df.copy(),  config)

    train_valid = ~(Y_train < 0).any(axis=1)
    test_valid  = ~(Y_test < 0).any(axis=1)
    X_train, Y_train = X_train.loc[train_valid], Y_train.loc[train_valid]
    X_test,  Y_test  = X_test.loc[test_valid],  Y_test.loc[test_valid]

    print(f"\n  Features ({len(feature_names)}): {feature_names}")
    print(f"  Targets  ({len(target_names)}): {target_names}")

    # ── Class balance info ─────────────────────────────────────────────────
    print("\n  Class balance (% positive):")
    for t in target_names:
        classes = sorted(Y_train[t].unique())
        if len(classes) > 2:
            counts = ", ".join(f"{int(c)}={int((Y_train[t] == c).sum())}" for c in classes)
            print(f"    {t}: multiclass ({counts})")
        else:
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
    print("\n-- Evaluation ----------------------------------")
    proba_list = pipeline.predict_proba(X_test)
    y_pred     = pipeline.predict(X_test)
    confusion_path, confusion_matrices = save_confusion_matrices(
        Y_test,
        y_pred,
        target_names,
        TARGET_LABELS,
    )

    metrics = {}
    for i, name in enumerate(target_names):
        true  = Y_test.iloc[:, i].values
        pred  = y_pred[:, i]
        classes = getattr(pipeline.named_steps["clf"].estimators_[i], "classes_", [])
        probs = proba_list[i]

        try:
            if len(classes) == 2:
                auroc = float(roc_auc_score(true, probs[:, 1]))
            elif len(classes) > 2:
                auroc = float(roc_auc_score(true, probs, multi_class="ovr", labels=classes))
            else:
                auroc = None
        except Exception:
            auroc = None

        label = TARGET_LABELS.get(name, name)
        print(f"\n  [{label}]")
        print(classification_report(true, pred, zero_division=0, digits=3))
        if auroc:
            print(f"  AUROC: {auroc:.4f}")
        metrics[name] = {
            "auroc": auroc,
            "label": label,
            "confusion_matrix": confusion_matrices[name],
        }

    # ── Save ───────────────────────────────────────────────────────────────
    joblib.dump(pipeline, BASE / "model.pkl")


    target_types = config.get("target_types", {})
    target_classes = {
        name: [int(value) for value in getattr(pipeline.named_steps["clf"].estimators_[i], "classes_", [])]
        for i, name in enumerate(target_names)
    }
    meta = {
        "csv_file":      str(csv_path),
        "feature_names": feature_names,
        "target_names":  target_names,
        "target_labels": {n: TARGET_LABELS.get(n, n) for n in target_names},
        "target_types": {n: target_types.get(n, "binary") for n in target_names},
        "target_classes": target_classes,
        "metrics":       metrics,
        "n_train":       len(X_train),
        "n_test":        len(X_test),
    }
    with open(BASE / "model_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n[OK] model.pkl        saved")
    print(f"[OK] model_meta.json  saved")
    print(f"[OK] {confusion_path.name} saved")
    print("\n-- Summary -------------------------------------")
    for name, m in metrics.items():
        auroc_str = f"{m['auroc']:.4f}" if m['auroc'] else "N/A"
        print(f"  {m['label']:<50} AUROC: {auroc_str}")
    print("\nDone. Start the service: python app.py")


if __name__ == "__main__":
    args = parse_args()
    train(csv_file=args.csv_file, config_path=args.config)
