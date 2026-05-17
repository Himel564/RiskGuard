import joblib
import pandas as pd
import json
import time
import os
from datetime import datetime

# ── ANSI colours ────────────────────────────────────────────────────────────
R  = "\033[91m"; G  = "\033[92m"; Y  = "\033[93m"; M  = "\033[95m"
C  = "\033[96m"; B  = "\033[1m";  D  = "\033[2m";  X  = "\033[0m"

# ── Config ───────────────────────────────────────────────────────────────────
HISTORY_FILE    = 'history.json'
FRAUD_LOG_FILE  = 'fraud_log.json'
BLOCKED_FILE    = 'blocked.json'
MAX_HISTORY     = 500
MAX_FRAUD_LOG   = 200

# Fraud confidence thresholds
THRESH_CRITICAL = 90.0   # ≥ 90 % confidence  →  CRITICAL
THRESH_HIGH     = 75.0   # ≥ 75 %             →  HIGH
THRESH_MEDIUM   = 50.0   # ≥ 50 %             →  MEDIUM
# below 50 %: flag as LOW (edge-case)

# Amount bands for risk amplification
AMOUNT_HIGH   = 500.0
AMOUNT_MEDIUM = 100.0

# ── Initialise persistent files ──────────────────────────────────────────────
for path, default in [(HISTORY_FILE, []), (FRAUD_LOG_FILE, []), (BLOCKED_FILE, [])]:
    if not os.path.exists(path):
        with open(path, 'w') as fh:
            json.dump(default, fh)

# ── Load model ────────────────────────────────────────────────────────────────
print(f"\n{B}{C}╔══════════════════════════════════════════════════════╗")
print("║        RiskGuard  ·  Fraud  Detector  Engine       ║")
print(f"╚══════════════════════════════════════════════════════╝{X}\n")

model = joblib.load('fraud_model.pkl')
print(f"  {G}✓{X} XGBoost model loaded from {D}fraud_model.pkl{X}")
print(f"  {G}✓{X} Persistent files initialised")
print(f"  {Y}⚡ Actions ENABLED — block · log · alert{X}")
print(f"\n{'─'*60}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def risk_level(confidence: float, amount: float) -> str:
    """Map model confidence + amount to a human risk label."""
    if confidence >= THRESH_CRITICAL or amount >= AMOUNT_HIGH:
        return "CRITICAL"
    if confidence >= THRESH_HIGH or amount >= AMOUNT_MEDIUM:
        return "HIGH"
    if confidence >= THRESH_MEDIUM:
        return "MEDIUM"
    return "LOW"


def risk_colour(level: str) -> str:
    return {
        "CRITICAL": R,
        "HIGH":     Y,
        "MEDIUM":   M,
        "LOW":      C,
    }.get(level, X)


def take_fraud_action(transaction_id, amount, confidence, level, features_dict):
    """
    Block · Log · Alert — three automated actions on every fraud hit.
    """
    timestamp = datetime.now().isoformat()
    col       = risk_colour(level)

    # ── 1. Block ────────────────────────────────────────────────────────
    with open(BLOCKED_FILE, 'r+') as f:
        blocked = json.load(f)
        if transaction_id not in blocked:
            blocked.append(transaction_id)
        f.seek(0); f.truncate(); json.dump(blocked, f)
    print(f"  {R}🔒 BLOCKED{X}    TX #{transaction_id}")

    # ── 2. Log to fraud ledger ───────────────────────────────────────────
    fraud_record = {
        "id":         transaction_id,
        "amount":     round(amount, 2),
        "confidence": confidence,
        "risk_level": level,
        "blocked_at": timestamp,
        "action":     "TRANSACTION_BLOCKED",
        "alert_sent": True,
        "features":   {k: round(v, 4) for k, v in list(features_dict.items())[:6]},
    }
    with open(FRAUD_LOG_FILE, 'r+') as f:
        log = json.load(f)
        log.insert(0, fraud_record)
        f.seek(0); f.truncate(); json.dump(log[:MAX_FRAUD_LOG], f)
    print(f"  {Y}📋 LOGGED{X}     fraud_log.json  ({D}{len(log)} events{X})")

    # ── 3. Simulated alert (replace print with requests.post() in prod) ──
    print(f"  {G}📧 ALERT{X}      {D}[SIMULATED]{X} "
          f"{col}{level}{X} fraud — ${amount:.2f}  conf: {confidence}%")

    return fraud_record


# ── Main detect loop ──────────────────────────────────────────────────────────

def detect():
    last_id    = None
    total_seen = 0
    fraud_seen = 0

    while True:
        if not os.path.exists('stream.json'):
            time.sleep(0.5)
            continue

        with open('stream.json', 'r') as f:
            data = json.load(f)

        current_id = data['Time']
        if current_id == last_id:
            time.sleep(0.5)
            continue

        # ── Run model ────────────────────────────────────────────────────
        features_df = pd.DataFrame([data]).drop('Class', axis=1, errors='ignore')
        prediction  = int(model.predict(features_df)[0])
        proba       = model.predict_proba(features_df)[0]
        confidence  = round(float(max(proba)) * 100, 2)
        is_fraud    = prediction == 1
        level       = risk_level(confidence, data['Amount']) if is_fraud else None

        total_seen += 1
        action = None

        if is_fraud:
            fraud_seen += 1
            col = risk_colour(level)
            print(f"\n{'═'*60}")
            print(f"  {R}{B}🚨 FRAUD DETECTED{X}  "
                  f"ID: {current_id}  |  ${data['Amount']:.2f}  |  "
                  f"Conf: {confidence}%  |  Risk: {col}{level}{X}")
            action = take_fraud_action(
                current_id, data['Amount'], confidence, level, data
            )
            rate = round(fraud_seen / total_seen * 100, 1)
            print(f"  {D}Session: {fraud_seen} fraud / {total_seen} total ({rate}%){X}")
            print(f"{'═'*60}\n")
            status = f"🚨 FRAUD [{level}]"
        else:
            print(f"  {G}✅ CLEAN{X}   ID: {current_id}  |  "
                  f"${data['Amount']:.2f}  |  Conf: {confidence}%")
            status = "✅ CLEAN"

        # ── Build history record ─────────────────────────────────────────
        result = {
            "id":         current_id,
            "amount":     round(data['Amount'], 2),
            "status":     status,
            "confidence": confidence,
            "risk_level": level or "NONE",
            "action":     action["action"] if action else "APPROVED",
            "time":       datetime.now().strftime("%H:%M:%S"),
        }

        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)

        history.insert(0, result)
        history = history[:MAX_HISTORY]

        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f)

        last_id = current_id
        time.sleep(0.5)


if __name__ == "__main__":
    detect()