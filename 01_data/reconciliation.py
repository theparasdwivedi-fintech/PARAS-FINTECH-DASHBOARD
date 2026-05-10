"""
reconciliation.py
Fintech Ledger ↔ Gateway Reconciliation Pipeline

Outputs
───────
~/Desktop/01_data/processed/
  missing_in_gateway.csv
  missing_in_ledger.csv
  amount_mismatches.csv
  status_mismatches.csv
  reconciliation_report.csv

~/Desktop/04_python/
  summary_metrics.json
"""

import pandas as pd
import numpy as np
import json
import os

# ── Paths ──────────────────────────────────────────────────────────────────
UPLOADS   = "/sessions/wonderful-kind-wright/mnt/uploads/"
PROCESSED = os.path.expanduser("~/Desktop/01_data/processed/")
PY_DIR    = os.path.expanduser("~/Desktop/04_python/")
os.makedirs(PROCESSED, exist_ok=True)
os.makedirs(PY_DIR,    exist_ok=True)

SEP = "=" * 62

# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — Load both files, print shape and preview
# ══════════════════════════════════════════════════════════════════════════
print(SEP)
print("STEP 1 · Loading files")
print(SEP)

ledger  = pd.read_csv(UPLOADS + "ledger.csv")
gateway = pd.read_csv(UPLOADS + "gateway.csv")

print(f"\nledger.csv  — shape : {ledger.shape}")
print(ledger.to_string(index=False))

print(f"\ngateway.csv — shape : {gateway.shape}")
print(gateway.to_string(index=False))

# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — Duplicates and nulls in both files
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 2 · Duplicate & null check")
print(SEP)

for label, df in [("LEDGER", ledger), ("GATEWAY", gateway)]:
    dup_count  = df.duplicated(subset="transaction_id").sum()
    null_count = df.isnull().sum()
    print(f"\n{label}")
    print(f"  Duplicate transaction_ids : {dup_count}")
    print("  Null counts per column:")
    for col, cnt in null_count.items():
        print(f"    {col:20s} : {cnt}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — Records in ledger NOT in gateway
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 3 · Missing in gateway (ledger rows not found in gateway)")
print(SEP)

ledger_ids  = set(ledger["transaction_id"])
gateway_ids = set(gateway["transaction_id"])

missing_in_gateway = ledger[ledger["transaction_id"].isin(ledger_ids - gateway_ids)].copy()
print(f"\n  Count : {len(missing_in_gateway)}")
print(missing_in_gateway.to_string(index=False))

path = PROCESSED + "missing_in_gateway.csv"
missing_in_gateway.to_csv(path, index=False)
print(f"  ✓ Saved → {path}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 4 — Records in gateway NOT in ledger
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 4 · Missing in ledger (gateway rows not found in ledger)")
print(SEP)

missing_in_ledger = gateway[gateway["transaction_id"].isin(gateway_ids - ledger_ids)].copy()
print(f"\n  Count : {len(missing_in_ledger)}")
print(missing_in_ledger.to_string(index=False))

path = PROCESSED + "missing_in_ledger.csv"
missing_in_ledger.to_csv(path, index=False)
print(f"  ✓ Saved → {path}")

# ══════════════════════════════════════════════════════════════════════════
# Build merged view for steps 5, 6, 7
# (only rows present in BOTH sources)
# ══════════════════════════════════════════════════════════════════════════
common_ids = ledger_ids & gateway_ids

ledger_common  = ledger[ledger["transaction_id"].isin(common_ids)].set_index("transaction_id")
gateway_common = gateway[gateway["transaction_id"].isin(common_ids)].set_index("transaction_id")

merged = ledger_common[["amount_usd", "status"]].join(
    gateway_common[["amount_usd", "status"]],
    lsuffix="_ledger",
    rsuffix="_gateway"
).reset_index()

# ══════════════════════════════════════════════════════════════════════════
# STEP 5 — Amount mismatches
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 5 · Amount mismatches (same transaction_id, different amount_usd)")
print(SEP)

amount_mismatches = merged[
    merged["amount_usd_ledger"] != merged["amount_usd_gateway"]
][["transaction_id", "amount_usd_ledger", "amount_usd_gateway"]].copy()
amount_mismatches["difference_usd"] = (
    amount_mismatches["amount_usd_gateway"] - amount_mismatches["amount_usd_ledger"]
).round(2)

print(f"\n  Count : {len(amount_mismatches)}")
print(amount_mismatches.to_string(index=False))

path = PROCESSED + "amount_mismatches.csv"
amount_mismatches.to_csv(path, index=False)
print(f"  ✓ Saved → {path}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 6 — Status mismatches
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 6 · Status mismatches (same transaction_id, different status)")
print(SEP)

status_mismatches = merged[
    merged["status_ledger"] != merged["status_gateway"]
][["transaction_id", "status_ledger", "status_gateway"]].copy()

print(f"\n  Count : {len(status_mismatches)}")
print(status_mismatches.to_string(index=False))

path = PROCESSED + "status_mismatches.csv"
status_mismatches.to_csv(path, index=False)
print(f"  ✓ Saved → {path}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 7 — reconciliation_report.csv
#   One row per transaction_id (union of both sources)
#   reconciliation_status:
#     matched            — present in both, amount and status agree
#     amount_mismatch    — present in both, amount differs
#     status_mismatch    — present in both, status differs
#     both_mismatch      — present in both, amount AND status differ
#     missing_in_gateway — in ledger only
#     missing_in_ledger  — in gateway only
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 7 · Building reconciliation_report.csv")
print(SEP)

all_ids = sorted(ledger_ids | gateway_ids)

def make_report_row(tid):
    in_ledger  = tid in ledger_ids
    in_gateway = tid in gateway_ids

    if in_ledger:
        lrow = ledger.set_index("transaction_id").loc[tid]
        l_amt = lrow["amount_usd"]
        l_sts = lrow["status"]
    else:
        l_amt, l_sts = None, None

    if in_gateway:
        grow = gateway.set_index("transaction_id").loc[tid]
        g_amt = grow["amount_usd"]
        g_sts = grow["status"]
    else:
        g_amt, g_sts = None, None

    if in_ledger and not in_gateway:
        recon = "missing_in_gateway"
    elif in_gateway and not in_ledger:
        recon = "missing_in_ledger"
    else:
        amt_ok = (l_amt == g_amt)
        sts_ok = (l_sts == g_sts)
        if amt_ok and sts_ok:
            recon = "matched"
        elif not amt_ok and not sts_ok:
            recon = "amount_mismatch"   # amount takes priority; flag amount first
        elif not amt_ok:
            recon = "amount_mismatch"
        else:
            recon = "status_mismatch"

    return {
        "transaction_id"       : tid,
        "ledger_amount"        : l_amt,
        "gateway_amount"       : g_amt,
        "ledger_status"        : l_sts,
        "gateway_status"       : g_sts,
        "reconciliation_status": recon,
    }

report = pd.DataFrame([make_report_row(tid) for tid in all_ids])

print(f"\n  Total rows : {len(report)}")
print(report.to_string(index=False))

path = PROCESSED + "reconciliation_report.csv"
report.to_csv(path, index=False)
print(f"\n  ✓ Saved → {path}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 8 — summary_metrics.json
#   amount_at_risk = sum of ledger amounts for all non-matched rows
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 8 · Generating summary_metrics.json")
print(SEP)

non_matched_ids = set(report.loc[report["reconciliation_status"] != "matched", "transaction_id"])

# amount_at_risk: ledger amount where available, else gateway amount
amount_at_risk = 0.0
for _, row in report[report["reconciliation_status"] != "matched"].iterrows():
    amt = row["ledger_amount"] if pd.notna(row["ledger_amount"]) else row["gateway_amount"]
    amount_at_risk += float(amt)

metrics = {
    "total_ledger_rows"           : int(len(ledger)),
    "total_gateway_rows"          : int(len(gateway)),
    "missing_in_gateway_count"    : int(len(missing_in_gateway)),
    "missing_in_ledger_count"     : int(len(missing_in_ledger)),
    "amount_mismatch_count"       : int(len(amount_mismatches)),
    "status_mismatch_count"       : int(len(status_mismatches)),
    "reconciliation_issue_count"  : int(len(report[report["reconciliation_status"] != "matched"])),
    "ledger_total_amount"         : round(float(ledger["amount_usd"].sum()), 2),
    "gateway_total_amount"        : round(float(gateway["amount_usd"].sum()), 2),
    "amount_at_risk"              : round(amount_at_risk, 2),
}

json_path = PY_DIR + "summary_metrics.json"
with open(json_path, "w") as f:
    json.dump(metrics, f, indent=2)

print("\n  summary_metrics.json:")
print(json.dumps(metrics, indent=2))
print(f"\n  ✓ Saved → {json_path}")

# ══════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("ALL DONE — output files")
print(SEP)
print(f"  {PROCESSED}missing_in_gateway.csv")
print(f"  {PROCESSED}missing_in_ledger.csv")
print(f"  {PROCESSED}amount_mismatches.csv")
print(f"  {PROCESSED}status_mismatches.csv")
print(f"  {PROCESSED}reconciliation_report.csv")
print(f"  {PY_DIR}summary_metrics.json")
