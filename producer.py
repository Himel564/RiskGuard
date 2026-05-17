import pandas as pd
import time
import json
import random
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
FRAUD_RATE       = 0.15   # 15 % of streams will be fraud  (demo realism)
STREAM_INTERVAL  = 2.0    # seconds between transactions
JITTER           = 0.4    # ± seconds of random timing variance

# ── ANSI colours ────────────────────────────────────────────────────────────
R  = "\033[91m"; G  = "\033[92m"; Y  = "\033[93m"
C  = "\033[96m"; B  = "\033[1m";  D  = "\033[2m";  X = "\033[0m"

BANNER = f"""
{B}{C}╔══════════════════════════════════════════════════════╗
║      RiskGuard  ·  Transaction Stream  Producer     ║
║         Real-Time ML Fraud Detection Pipeline       ║
╚══════════════════════════════════════════════════════╝{X}
"""
print(BANNER)

# ── Load & split dataset ─────────────────────────────────────────────────────
print(f"  {D}Loading creditcard.csv …{X}")
df        = pd.read_csv('creditcard.csv')
fraud_df  = df[df['Class'] == 1].reset_index(drop=True)
clean_df  = df[df['Class'] == 0].reset_index(drop=True)

print(f"  {G}✓{X} Dataset loaded — "
      f"{len(df):,} total  |  {R}{len(fraud_df)}{X} fraud  |  {G}{len(clean_df):,}{X} clean")
print(f"  {Y}⚡ Demo fraud-injection rate: {int(FRAUD_RATE*100)}%  "
      f"(real dataset rate: {len(fraud_df)/len(df)*100:.2f}%){X}")
print(f"  {D}Streaming 1 transaction every ~{STREAM_INTERVAL}s …{X}\n")
print("─" * 60)

# ── Stream ───────────────────────────────────────────────────────────────────
tx_count    = 0
fraud_count = 0

def stream_transactions():
    global tx_count, fraud_count

    while True:
        tx_count += 1

        # Weighted sampling — force fraud at FRAUD_RATE for a realistic demo
        inject_fraud = random.random() < FRAUD_RATE
        pool = fraud_df if inject_fraud else clean_df
        tx   = pool.sample(1).to_dict(orient='records')[0]

        ts    = datetime.now().strftime('%H:%M:%S')
        label = f"{R}🚨 FRAUD {X}" if inject_fraud else f"{G}📡 CLEAN {X}"

        print(f"  {label}  #{tx_count:04d}  |  "
              f"ID: {int(tx['Time']):>6}  |  "
              f"${tx['Amount']:>8.2f}  {D}[{ts}]{X}", end="")

        if inject_fraud:
            fraud_count += 1
            print(f"  {Y}← injected fraud #{fraud_count}{X}")
        else:
            print()

        with open('stream.json', 'w') as f:
            json.dump(tx, f)

        # Slight random jitter so the feed looks organic
        sleep_time = STREAM_INTERVAL + random.uniform(-JITTER, JITTER)
        time.sleep(max(0.5, sleep_time))


if __name__ == "__main__":
    stream_transactions()