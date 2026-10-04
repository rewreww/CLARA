"""Read-only audit. Writes aggregates to this task directory; never trains a model."""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r'C:\clara-system')
BASE = ROOT / 'ai-services/ml_service'
OUT = ROOT / 'tmp/pdfs/clara-paper-review'
config = json.loads((BASE / 'column_config.json').read_text())
meta = json.loads((BASE / 'model_meta.json').read_text())
df = pd.read_csv(BASE / 'data/dataset.csv', low_memory=False)
features = config['feature_columns']
targets = config['target_columns']

def numeric(col):
    series = df[col].copy()
    mapping = config['categorical_encodings'].get(col)
    if mapping:
        series = series.map(mapping).fillna(series)
    return pd.to_numeric(series, errors='coerce')

X = pd.DataFrame({key: numeric(col) for key, col in features.items()})
Y = pd.DataFrame({key: numeric(col) for key, col in targets.items()})
feature_audit = []
for key, col in features.items():
    s = X[key]
    feature_audit.append({
        'feature': key, 'csv_column': col, 'missing_count': int(s.isna().sum()),
        'missing_percent': round(float(s.isna().mean() * 100), 3),
        'unique_nonmissing': int(s.nunique()),
        'median': float(s.median()) if s.notna().any() else None,
        'min': float(s.min()) if s.notna().any() else None,
        'max': float(s.max()) if s.notna().any() else None,
        'coercion_losses': int((df[col].notna() & s.isna()).sum()),
    })

tree = ast.parse((ROOT / 'ai-services/llm_service/llm_client.py').read_text(encoding='utf-8'))
lab_map = {}
builder = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_ml_features')
for n in tree.body:
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ML_LAB_MAP' for t in n.targets):
        lab_map = ast.literal_eval(n.value)
supplied = set(lab_map.values())
for n in ast.walk(builder):
    if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == 'features' and isinstance(n.slice, ast.Constant):
        supplied.add(n.slice.value)
    if isinstance(n, ast.Dict):
        for k in n.keys:
            if isinstance(k, ast.Constant) and k.value in features:
                supplied.add(k.value)

saved_metrics = []
for target, m in meta['metrics'].items():
    cm = np.array(m['confusion_matrix'])
    support = cm.sum(axis=1)
    predicted = cm.sum(axis=0)
    diag = np.diag(cm)
    precision = np.divide(diag, predicted, out=np.zeros(len(diag), dtype=float), where=predicted != 0)
    recall = np.divide(diag, support, out=np.zeros(len(diag), dtype=float), where=support != 0)
    f1 = np.divide(2 * diag, support + predicted, out=np.zeros(len(diag), dtype=float), where=support + predicted != 0)
    item = {'target': target, 'label': m['label'], 'n_test': int(cm.sum()), 'accuracy': float(diag.sum()/cm.sum()),
            'majority_accuracy': float(support.max()/cm.sum()), 'macro_f1': float(f1.mean()),
            'weighted_f1': float((f1*support).sum()/cm.sum()), 'auroc': m['auroc'],
            'classes': meta['target_classes'][target], 'support': support.tolist(),
            'per_class_precision': precision.tolist(), 'per_class_recall': recall.tolist(), 'per_class_f1': f1.tolist(),
            'confusion_matrix': cm.tolist()}
    if len(cm) == 2:
        item.update({'precision':float(precision[1]), 'recall':float(recall[1]), 'f1':float(f1[1]),
                     'specificity':float(recall[0]), 'balanced_accuracy':float(recall.mean()),
                     'true_positive':int(cm[1,1]), 'false_negative':int(cm[1,0]), 'positive_support':int(support[1])})
    saved_metrics.append(item)

unused = [c for c in df.columns if c not in set(features.values()) | set(targets.values())]
summary = {
    'csv_sha256': hashlib.sha256((BASE/'data/dataset.csv').read_bytes()).hexdigest(),
    'shape': list(df.shape), 'feature_count':len(features), 'target_count':len(targets),
    'missing_any_target':int(Y.isna().any(axis=1).sum()),
    'target_counts':{t:{str(k):int(v) for k,v in df[c].value_counts(dropna=False).items()} for t,c in targets.items()},
    'duplicate_full_rows':int(df.duplicated().sum()),
    'duplicate_features':int(X.duplicated().sum()),
    'unused_columns':unused,
    'id_columns':{c:{'unique':int(df[c].nunique()),'missing':int(df[c].isna().sum())} for c in unused if 'id' in c.lower()},
    'missing_feature_cells_percent':float(X.isna().to_numpy().mean()*100),
    'features_over_50pct_missing':sum(f['missing_percent'] > 50 for f in feature_audit),
    'features_over_80pct_missing':sum(f['missing_percent'] > 80 for f in feature_audit),
    'constant_nonmissing_features':[f for f in feature_audit if f['unique_nonmissing'] <= 1],
    'feature_audit':feature_audit,
    'chat_max_supplied_feature_count':len(supplied),
    'chat_max_supplied_features':sorted(supplied),
    'chat_unmapped_features':sorted(set(features)-supplied),
    'saved_metrics':saved_metrics,
    'selected_value_counts': {c:{str(k):int(v) for k,v in df[c].value_counts(dropna=False).items()} for c in ['diabetes','liver.disease','oxygen.inhalation','respiratory.support.','ageCat']},
    'saved_n_train':meta['n_train'], 'saved_n_test':meta['n_test'],
}
(OUT/'clara-audit.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8')
compact = {k:v for k,v in summary.items() if k not in ['feature_audit','chat_unmapped_features','saved_metrics','chat_max_supplied_features']}
compact['worst_missing_features'] = sorted(feature_audit,key=lambda x:x['missing_percent'],reverse=True)[:12]
compact['metrics']=[{k:v for k,v in m.items() if k in ['target','accuracy','precision','recall','f1','macro_f1','auroc','majority_accuracy','positive_support']} for m in saved_metrics]
print(json.dumps(compact,indent=2,allow_nan=False))
