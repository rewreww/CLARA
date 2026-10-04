"""Reconstruct current test split and evaluate existing model without refitting."""
import importlib.util
import json
from pathlib import Path
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(r'C:\clara-system')
BASE = ROOT/'ai-services/ml_service'
OUT = ROOT/'tmp/pdfs/clara-paper-review'
spec = importlib.util.spec_from_file_location('clara_training_audit', BASE/'train.py')
training = importlib.util.module_from_spec(spec)
spec.loader.exec_module(training)
audit = json.loads((OUT/'clara-audit.json').read_text())
meta = json.loads((BASE/'model_meta.json').read_text())
config = training.load_config()
df = pd.read_csv(BASE/'data/dataset.csv',low_memory=False)
train_df, test_df = train_test_split(df,test_size=0.2,random_state=42)
X_train,Y_train,features,targets = training.prepare_data(train_df.copy(),config)
X_test,Y_test,_,_ = training.prepare_data(test_df.copy(),config)
train_valid = ~(Y_train < 0).any(axis=1)
test_valid = ~(Y_test < 0).any(axis=1)
X_train,Y_train = X_train.loc[train_valid],Y_train.loc[train_valid]
X_test,Y_test = X_test.loc[test_valid],Y_test.loc[test_valid]
model = joblib.load(BASE/'model.pkl')
model.named_steps['clf'].n_jobs = 1
for estimator in model.named_steps['clf'].estimators_:
    estimator.set_params(n_jobs=2)
pred = model.predict(X_test)
probabilities = model.predict_proba(X_test)
masked = X_test.astype(float).copy()
masked.loc[:,audit['chat_unmapped_features']] = np.nan
masked_predictions = model.predict(masked)
masked_probabilities = model.predict_proba(masked)
rows = []
for i,target in enumerate(targets):
    truth = Y_test[target].to_numpy()
    classes = model.named_steps['clf'].estimators_[i].classes_
    cm = confusion_matrix(truth,pred[:,i],labels=classes)
    row = {'target':target,'saved_confusion_matches':cm.tolist() == meta['metrics'][target]['confusion_matrix'],
           'train_class_counts':{str(k):int(v) for k,v in Y_train[target].value_counts().items()}}
    if len(classes) == 2:
        pos = list(classes).index(1)
        p = probabilities[i][:,pos]
        mp = masked_probabilities[i][:,pos]
        row.update({'average_precision':float(average_precision_score(truth,p)),
                    'ap_baseline_test_prevalence':float(truth.mean()),
                    'brier':float(brier_score_loss(truth,p)),
                    'constant_training_prevalence_brier':float(brier_score_loss(truth,np.full(len(truth),Y_train[target].mean()))),
                    'auroc':float(roc_auc_score(truth,p)),
                    'f1':float(f1_score(truth,pred[:,i],zero_division=0)),
                    'masked_average_precision':float(average_precision_score(truth,mp)),
                    'masked_f1':float(f1_score(truth,masked_predictions[:,i],zero_division=0)),
                    'masked_auroc':float(roc_auc_score(truth,mp))})
    rows.append(row)
print(json.dumps({'n_train':len(X_train),'n_test':len(X_test),'estimator':type(model.named_steps['clf'].estimators_[0]).__name__,
                  'train_test_inpatient_number_overlap':len(set(train_df['inpatient.number']) & set(test_df['inpatient.number'])),
                  'inpatient_number_unique':int(df['inpatient.number'].nunique()),'rows':rows},indent=2))
(OUT/'verified-model-metrics.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
