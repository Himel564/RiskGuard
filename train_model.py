import pandas as pd
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, precision_score, recall_score, f1_score
)
import joblib
import json
import time

# ── ANSI colours ────────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"
B = "\033[1m";  D = "\033[2m";  X = "\033[0m"

print(f"\n{B}{C}╔══════════════════════════════════════════════════════╗")
print("║      RiskGuard  ·  Model  Training  Pipeline       ║")
print(f"╚══════════════════════════════════════════════════════╝{X}\n")


# ── 1. Load ────────────────────────────────────────────────────────────────
t0 = time.time()
print(f"  {D}[1/6]{X} Loading creditcard.csv …")
df = pd.read_csv('creditcard.csv')
fraud  = df[df['Class'] == 1]
clean  = df[df['Class'] == 0]
print(f"       {G}✓{X} {len(df):,} rows  |  "
      f"{len(fraud)} fraud  |  {len(clean):,} clean  "
      f"({D}imbalance ratio 1:{int(len(clean)/len(fraud))}{X})")


# ── 2. Features / target ────────────────────────────────────────────────────
print(f"\n  {D}[2/6]{X} Preparing features …")
X_raw = df.drop('Class', axis=1)
y_raw = df['Class']
print(f"       {G}✓{X} {X_raw.shape[1]} features,  {len(y_raw):,} samples")


# ── 3. SMOTE ────────────────────────────────────────────────────────────────
print(f"\n  {D}[3/6]{X} Applying SMOTE to balance classes …")
smote      = SMOTE(sampling_strategy='minority', random_state=42)
X_res, y_res = smote.fit_resample(X_raw, y_raw)
print(f"       {G}✓{X} Resampled  →  {len(X_res):,} rows "
      f"({sum(y_res==0):,} clean  |  {sum(y_res==1):,} fraud)")


# ── 4. Train / test split ────────────────────────────────────────────────────
print(f"\n  {D}[4/6]{X} Splitting 80/20 …")
X_train, X_test, y_train, y_test = train_test_split(
    X_res, y_res, test_size=0.2, random_state=42, stratify=y_res
)
print(f"       {G}✓{X} Train: {len(X_train):,}   Test: {len(X_test):,}")


# ── 5. Train XGBoost ────────────────────────────────────────────────────────
print(f"\n  {D}[5/6]{X} Training XGBoost (this may take a minute) …")
model = XGBClassifier(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    use_label_encoder=False,
    eval_metric='logloss',
    random_state=42,
    n_jobs=-1,
)
model.fit(X_train, y_train)
elapsed = time.time() - t0
print(f"       {G}✓{X} Training complete in {elapsed:.1f}s")


# ── 6. Evaluate ──────────────────────────────────────────────────────────────
print(f"\n  {D}[6/6]{X} Evaluating …\n")
y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)[:, 1]

prec  = precision_score(y_test, y_pred)
rec   = recall_score(y_test, y_pred)
f1    = f1_score(y_test, y_pred)
auc   = roc_auc_score(y_test, y_prob)

print(f"  {'─'*42}")
print(f"  {'Metric':<20}  {'Score':>10}")
print(f"  {'─'*42}")
print(f"  {'Precision':<20}  {G}{prec*100:>9.2f}%{X}")
print(f"  {'Recall':<20}  {G}{rec*100:>9.2f}%{X}")
print(f"  {'F1 Score':<20}  {G}{f1*100:>9.2f}%{X}")
print(f"  {'ROC-AUC':<20}  {G}{auc*100:>9.2f}%{X}")
print(f"  {'─'*42}")
print(f"\n{classification_report(y_test, y_pred, target_names=['Clean','Fraud'])}")

cm = confusion_matrix(y_test, y_pred)
tn, fp, fn, tp = cm.ravel()
print(f"  Confusion Matrix:")
print(f"    True  Negatives (clean correctly approved):  {tn:>7,}")
print(f"    False Positives (clean incorrectly blocked):  {fp:>7,}")
print(f"    False Negatives (fraud incorrectly approved): {fn:>7,}")
print(f"    True  Positives (fraud correctly blocked):   {tp:>7,}")

# Save metrics for the dashboard
metrics = {
    "precision":  round(prec * 100, 2),
    "recall":     round(rec  * 100, 2),
    "f1":         round(f1   * 100, 2),
    "roc_auc":    round(auc  * 100, 2),
    "train_time": round(elapsed, 1),
}
with open('model_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
print(f"\n  {G}✓{X} Metrics saved to model_metrics.json")

# ── 7. Save model ────────────────────────────────────────────────────────────
joblib.dump(model, 'fraud_model.pkl')
print(f"  {G}✓{X} Model saved to fraud_model.pkl\n")
print(f"{B}  Run python producer.py  +  python detector.py  to start streaming.{X}\n")