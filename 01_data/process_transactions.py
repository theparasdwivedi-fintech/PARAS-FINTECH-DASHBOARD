"""
Transaction Data Cleaning & Enrichment Pipeline
Outputs to: ~/Desktop/01_data/processed/
"""

import pandas as pd
import numpy as np
import re
import os

# ── Paths ──────────────────────────────────────────────────────────────────
UPLOADS   = "/sessions/wonderful-kind-wright/mnt/uploads/"
OUT_DIR   = os.path.expanduser("~/Desktop/01_data/processed/")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Load raw data ──────────────────────────────────────────────────────────
print("Loading files...")
txn  = pd.read_csv(UPLOADS + "transactions_raw.csv")
fx   = pd.read_csv(UPLOADS + "exchange_rates.csv")
merch = pd.read_csv(UPLOADS + "merchant_master.csv")

print(f"  transactions_raw : {len(txn)} rows")
print(f"  exchange_rates   : {len(fx)} rows")
print(f"  merchant_master  : {len(merch)} rows")

# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — Trim whitespace from all text fields
# ══════════════════════════════════════════════════════════════════════════
print("\nStep 1 · Trimming whitespace...")
for col in txn.select_dtypes(include="object").columns:
    txn[col] = txn[col].str.strip()
for col in merch.select_dtypes(include="object").columns:
    merch[col] = merch[col].str.strip()
for col in fx.select_dtypes(include="object").columns:
    fx[col] = fx[col].str.strip()

# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — Standardize merchant names
# ══════════════════════════════════════════════════════════════════════════
print("Step 2 · Standardizing merchant names...")

def normalize_key(s):
    """Collapse to lowercase with single spaces — used for fuzzy matching."""
    return re.sub(r"\s+", " ", str(s).strip().lower())

# Build lookup: normalized_key → canonical name
canonical_map = {normalize_key(name): name for name in merch["merchant_name"]}

def map_merchant(raw_name):
    key = normalize_key(raw_name)
    if key in canonical_map:
        return canonical_map[key]
    # Try partial / prefix match as fallback
    for k, v in canonical_map.items():
        if key.startswith(k) or k.startswith(key):
            return v
    return raw_name  # keep original if no match

txn["merchant_name"] = txn["merchant_name"].apply(map_merchant)
print(f"  Unique merchants after mapping: {txn['merchant_name'].unique().tolist()}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — Standardize dates → YYYY-MM-DD
# ══════════════════════════════════════════════════════════════════════════
print("Step 3 · Standardizing dates...")
txn["transaction_date"] = pd.to_datetime(txn["transaction_date"], errors="coerce").dt.strftime("%Y-%m-%d")
fx["rate_date"]         = pd.to_datetime(fx["rate_date"],         errors="coerce").dt.strftime("%Y-%m-%d")
print(f"  Date range: {txn['transaction_date'].min()} → {txn['transaction_date'].max()}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 4 — Standardize status
#   Valid values: captured | failed | chargeback | refunded
# ══════════════════════════════════════════════════════════════════════════
print("Step 4 · Standardizing status...")
VALID_STATUSES = {"captured", "failed", "chargeback", "refunded"}

def clean_status(s):
    if pd.isna(s):
        return np.nan
    s = s.strip().lower()
    for v in VALID_STATUSES:
        if s.startswith(v):
            return v
    return np.nan

txn["status"] = txn["status"].apply(clean_status)
print(f"  Status distribution:\n{txn['status'].value_counts().to_string()}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 5 — Standardize risk_score (extract numeric only)
#   "score:62" → 62 | "risk-83" → 83 | "75 " → 75 | NaN → NaN
# ══════════════════════════════════════════════════════════════════════════
print("Step 5 · Standardizing risk_score...")

def extract_risk_score(s):
    if pd.isna(s):
        return np.nan
    nums = re.findall(r"\d+", str(s))
    return float(nums[0]) if nums else np.nan

txn["risk_score"] = txn["risk_score"].apply(extract_risk_score)
print(f"  risk_score range: {txn['risk_score'].min()} – {txn['risk_score'].max()}  |  nulls: {txn['risk_score'].isna().sum()}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 6 — Standardize gateway_region (strip, uppercase)
# ══════════════════════════════════════════════════════════════════════════
print("Step 6 · Standardizing gateway_region...")
txn["gateway_region"] = txn["gateway_region"].str.strip().str.upper()
print(f"  Unique regions: {sorted(txn['gateway_region'].dropna().unique().tolist())}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 7 — Convert amount to USD
#   Match on transaction_date + currency
# ══════════════════════════════════════════════════════════════════════════
print("Step 7 · Converting amounts to USD...")
fx_lookup = fx.set_index(["rate_date", "currency"])["usd_rate"]

def to_usd(row):
    key = (row["transaction_date"], row["currency"])
    rate = fx_lookup.get(key, np.nan)
    return round(row["raw_amount"] * rate, 2) if not np.isnan(rate) else np.nan

txn["amount_usd"] = txn.apply(to_usd, axis=1)
print(f"  Converted {txn['amount_usd'].notna().sum()}/{len(txn)} rows. Sample USD amounts: {txn['amount_usd'].head(3).tolist()}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 8 — Enrich with merchant_master
#   Add: merchant_id, merchant_category, default_region, account_manager
# ══════════════════════════════════════════════════════════════════════════
print("Step 8 · Enriching with merchant metadata...")
merch_lookup = merch.set_index("merchant_name")[["merchant_id", "merchant_category", "default_region", "account_manager"]]
txn = txn.join(merch_lookup, on="merchant_name", how="left")
print(f"  Null merchant_id count: {txn['merchant_id'].isna().sum()}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 9 — high_value_flag
#   APAC & amount_usd > 5000 → 1
#   EU   & amount_usd > 6000 → 1
#   US   & amount_usd > 7000 → 1
#   else 0
# ══════════════════════════════════════════════════════════════════════════
print("Step 9 · Creating high_value_flag...")

def high_value_flag(row):
    region = row["default_region"]
    amt    = row["amount_usd"]
    if pd.isna(amt) or pd.isna(region):
        return 0
    thresholds = {"APAC": 5000, "EU": 6000, "US": 7000}
    threshold = thresholds.get(region.upper(), None)
    if threshold is None:
        return 0
    return 1 if amt > threshold else 0

txn["high_value_flag"] = txn.apply(high_value_flag, axis=1)
print(f"  high_value_flag=1 count: {txn['high_value_flag'].sum()}")

# ══════════════════════════════════════════════════════════════════════════
# STEP 10 — high_risk_flag
#   risk_score >= 70 OR status == "chargeback" → 1, else 0
# ══════════════════════════════════════════════════════════════════════════
print("Step 10 · Creating high_risk_flag...")

def high_risk_flag(row):
    score_flag  = (not pd.isna(row["risk_score"])) and (row["risk_score"] >= 70)
    status_flag = row["status"] == "chargeback"
    return 1 if (score_flag or status_flag) else 0

txn["high_risk_flag"] = txn.apply(high_risk_flag, axis=1)
print(f"  high_risk_flag=1 count: {txn['high_risk_flag'].sum()}")

# ══════════════════════════════════════════════════════════════════════════
# SAVE cleaned_transactions.csv
# ══════════════════════════════════════════════════════════════════════════
# Reorder / rename for clarity
output_cols = [
    "transaction_id", "transaction_date", "merchant_id", "merchant_name",
    "merchant_category", "default_region", "account_manager",
    "raw_amount", "currency", "amount_usd",
    "status", "risk_score", "gateway_region",
    "user_id", "payment_method",
    "high_value_flag", "high_risk_flag"
]
out_txn = txn[output_cols]
cleaned_path = OUT_DIR + "cleaned_transactions.csv"
out_txn.to_csv(cleaned_path, index=False)
print(f"\n✓ Saved cleaned_transactions.csv → {cleaned_path}  ({len(out_txn)} rows)")

# ══════════════════════════════════════════════════════════════════════════
# SAVE merchant_risk_summary.csv
# ══════════════════════════════════════════════════════════════════════════
print("\nBuilding merchant_risk_summary...")
summary = (
    txn.groupby("merchant_name", as_index=False)
    .agg(
        total_transactions=("transaction_id", "count"),
        avg_risk_score    =("risk_score",     lambda x: round(x.mean(), 2)),
        high_risk_count   =("high_risk_flag", "sum"),
        total_amount_usd  =("amount_usd",     lambda x: round(x.sum(), 2)),
    )
    .sort_values("total_transactions", ascending=False)
)

summary_path = OUT_DIR + "merchant_risk_summary.csv"
summary.to_csv(summary_path, index=False)
print(f"✓ Saved merchant_risk_summary.csv → {summary_path}  ({len(summary)} rows)")

# ══════════════════════════════════════════════════════════════════════════
# PRINT FINAL SUMMARIES
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("CLEANED TRANSACTIONS — sample (5 rows)")
print("="*60)
print(out_txn.head(5).to_string(index=False))

print("\n" + "="*60)
print("MERCHANT RISK SUMMARY")
print("="*60)
print(summary.to_string(index=False))

print("\n" + "="*60)
print("DATA QUALITY SUMMARY")
print("="*60)
print(f"  Total transactions     : {len(out_txn)}")
print(f"  Null amount_usd        : {out_txn['amount_usd'].isna().sum()}")
print(f"  Null status            : {out_txn['status'].isna().sum()}")
print(f"  Null risk_score        : {out_txn['risk_score'].isna().sum()}")
print(f"  high_value_flag = 1    : {out_txn['high_value_flag'].sum()}")
print(f"  high_risk_flag  = 1    : {out_txn['high_risk_flag'].sum()}")
print(f"\nAll files written to: {OUT_DIR}")
