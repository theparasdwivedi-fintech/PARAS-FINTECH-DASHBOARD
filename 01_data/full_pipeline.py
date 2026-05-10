"""
full_pipeline.py
────────────────
Part A — Flatten API JSON → api_normalized.csv
Part B — Build 4 dashboard CSVs from cleaned_transactions.csv

Outputs → ~/Desktop/01_data/processed/
"""

import json
import os
import pandas as pd
import numpy as np

UPLOADS   = "/sessions/wonderful-kind-wright/mnt/uploads/"
DESKTOP   = os.path.expanduser("~/Desktop/01_data/processed/")
os.makedirs(DESKTOP, exist_ok=True)

SEP  = "=" * 62
SEP2 = "-" * 62

# ══════════════════════════════════════════════════════════════
# PART A — JSON FLATTEN
# ══════════════════════════════════════════════════════════════
print(SEP)
print("PART A · Flatten API JSON")
print(SEP)

# ── Step 1: Read JSON ──────────────────────────────────────────
with open(UPLOADS + "api_response_sample.json", "r") as f:
    api_data = json.load(f)

print(f"\nSource   : {api_data['source']}")
print(f"Generated: {api_data['generated_at']}")
print(f"Batches  : {len(api_data['batches'])}")
total_settlements = sum(len(b["settlements"]) for b in api_data["batches"])
print(f"Settlements: {total_settlements}")

# ── Step 2: Flatten ───────────────────────────────────────────
rows = []
for batch in api_data["batches"]:
    batch_id      = batch["batch_id"]
    merchant_id   = batch["merchant"]["merchant_id"]
    merchant_name = batch["merchant"]["merchant_name"]
    region        = batch["merchant"]["region"]

    for s in batch["settlements"]:
        rows.append({
            "batch_id"      : batch_id,
            "merchant_id"   : merchant_id,
            "merchant_name" : merchant_name,
            "region"        : region,
            "settlement_id" : s["settlement_id"],
            "amount_usd"    : s["amount_usd"],
            "status"        : s["status"],
            "processed_at"  : s["processed_at"],
            "bank_name"     : s["bank"]["name"],
            "bank_country"  : s["bank"]["country"],
        })

api_df = pd.DataFrame(rows)

# ── Step 3: Ensure correct column names + datetime ────────────
api_df.columns = [c.lower().replace(" ", "_") for c in api_df.columns]
api_df["processed_at"] = pd.to_datetime(api_df["processed_at"], utc=True)

# ── Step 4: Print ──────────────────────────────────────────────
print(f"\nShape: {api_df.shape}")
print(SEP2)
print(api_df.to_string(index=False))
print(SEP2)
print(f"\ndtypes:\n{api_df.dtypes.to_string()}")

# ── Step 5: Save ──────────────────────────────────────────────
path = DESKTOP + "api_normalized.csv"
api_df.to_csv(path, index=False)
print(f"\n✓ Saved api_normalized.csv → {path}")


# ══════════════════════════════════════════════════════════════
# PART B — DASHBOARD CSVs from cleaned_transactions.csv
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("PART B · Dashboard CSVs from cleaned_transactions.csv")
print(SEP)

txn = pd.read_csv(DESKTOP + "cleaned_transactions.csv")
print(f"\nLoaded cleaned_transactions.csv — shape: {txn.shape}")

# Captured-only view (for GMV cols)
cap = txn[txn["status"] == "captured"].copy()
print(f"Captured rows: {len(cap)}  |  Non-captured: {len(txn) - len(cap)}")

# ── daily_summary.csv ─────────────────────────────────────────
print(f"\n{SEP2}")
print("daily_summary.csv")
print(SEP2)

daily_summary = (
    txn.groupby("transaction_date", as_index=False)
    .agg(
        total_gmv_usd    =("amount_usd",       lambda x: round(
                                cap.loc[cap["transaction_date"] == x.name, "amount_usd"].sum(), 2
                            )),
        transaction_count=("transaction_id",    "count"),
        successful_count =("status",            lambda x: (x == "captured").sum()),
    )
    .sort_values("transaction_date")
)

# Cleaner: compute properly per date
daily_gmv = cap.groupby("transaction_date")["amount_usd"].sum().round(2).rename("total_gmv_usd")
daily_cnt = txn.groupby("transaction_date")["transaction_id"].count().rename("transaction_count")
daily_suc = txn[txn["status"] == "captured"].groupby("transaction_date")["transaction_id"].count().rename("successful_count")

daily_summary = (
    pd.concat([daily_gmv, daily_cnt, daily_suc], axis=1)
    .fillna(0)
    .astype({"transaction_count": int, "successful_count": int})
    .reset_index()
    .rename(columns={"transaction_date": "transaction_date"})
    .sort_values("transaction_date")
)

print(daily_summary.to_string(index=False))
path = DESKTOP + "daily_summary.csv"
daily_summary.to_csv(path, index=False)
print(f"✓ Saved → {path}")

# ── payment_method_breakdown.csv ──────────────────────────────
print(f"\n{SEP2}")
print("payment_method_breakdown.csv")
print(SEP2)

pm_gmv = (
    cap.groupby("payment_method")["amount_usd"]
    .sum().round(2).rename("total_gmv_usd")
)
pm_cnt = (
    txn.groupby("payment_method")["transaction_id"]
    .count().rename("transaction_count")
)

payment_method_breakdown = (
    pd.concat([pm_gmv, pm_cnt], axis=1)
    .fillna(0)
    .reset_index()
    .sort_values("total_gmv_usd", ascending=False)
)

print(payment_method_breakdown.to_string(index=False))
path = DESKTOP + "payment_method_breakdown.csv"
payment_method_breakdown.to_csv(path, index=False)
print(f"✓ Saved → {path}")

# ── region_breakdown.csv ──────────────────────────────────────
print(f"\n{SEP2}")
print("region_breakdown.csv")
print(SEP2)

reg_gmv = (
    cap.groupby("default_region")["amount_usd"]
    .sum().round(2).rename("total_gmv_usd")
)
reg_cnt = (
    txn.groupby("default_region")["transaction_id"]
    .count().rename("transaction_count")
)
reg_risk = (
    txn.groupby("default_region")["risk_score"]
    .mean().round(2).rename("avg_risk_score")
)

region_breakdown = (
    pd.concat([reg_gmv, reg_cnt, reg_risk], axis=1)
    .fillna(0)
    .reset_index()
    .rename(columns={"default_region": "region"})
    .sort_values("total_gmv_usd", ascending=False)
)

print(region_breakdown.to_string(index=False))
path = DESKTOP + "region_breakdown.csv"
region_breakdown.to_csv(path, index=False)
print(f"✓ Saved → {path}")

# ── merchant_performance_summary.csv ──────────────────────────
print(f"\n{SEP2}")
print("merchant_performance_summary.csv")
print(SEP2)

merch_total    = txn.groupby("merchant_name")["amount_usd"].sum().round(2).rename("total_gmv_usd")
merch_captured = cap.groupby("merchant_name")["amount_usd"].sum().round(2).rename("captured_gmv_usd")
merch_cb       = (txn[txn["status"] == "chargeback"]
                  .groupby("merchant_name")["transaction_id"].count().rename("chargeback_count"))
merch_hr       = (txn[txn["high_risk_flag"] == 1]
                  .groupby("merchant_name")["transaction_id"].count().rename("high_risk_count"))

merchant_performance_summary = (
    pd.concat([merch_total, merch_captured, merch_cb, merch_hr], axis=1)
    .fillna(0)
    .astype({"chargeback_count": int, "high_risk_count": int})
    .reset_index()
    .sort_values("total_gmv_usd", ascending=False)
)

print(merchant_performance_summary.to_string(index=False))
path = DESKTOP + "merchant_performance_summary.csv"
merchant_performance_summary.to_csv(path, index=False)
print(f"✓ Saved → {path}")

# ══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("ALL FILES WRITTEN")
print(SEP)
outputs = [
    "api_normalized.csv",
    "daily_summary.csv",
    "payment_method_breakdown.csv",
    "region_breakdown.csv",
    "merchant_performance_summary.csv",
]
for f in outputs:
    full = DESKTOP + f
    size = os.path.getsize(full)
    print(f"  ✓  {f:40s}  {size:>6} bytes")
