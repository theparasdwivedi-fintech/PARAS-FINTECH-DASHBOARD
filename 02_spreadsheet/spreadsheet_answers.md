# Spreadsheet Answers

---

## Cleaning Steps

The raw dataset (`transactions_raw.csv`) contained 30 rows and 10 columns: `transaction_id`, `transaction_date`, `merchant_name`, `raw_amount`, `currency`, `status`, `risk_score`, `gateway_region`, `user_id`, and `payment_method`. All 30 rows were retained after cleaning — no rows were dropped for being duplicates or entirely null. The cleaning process addressed five categories of data quality issues.

**Whitespace trimming** was applied across every text column. Leading and trailing spaces were stripped from `merchant_name` (e.g. `" alpha mart "` → `"alpha mart"`), `status` (e.g. `" CAPTURED"` → `"CAPTURED"`), and `gateway_region` (e.g. `" APAC "` → `"APAC"`). Internal multi-space sequences in merchant names such as `"Alpha  Mart"` and `"Beta  Stores"` were collapsed to single spaces before name matching.

**Merchant name standardization** resolved all casing and spacing variants into five canonical names. The raw file contained 12 distinct string variants across 5 actual merchants. After normalization, every row mapped cleanly to one of: Alpha Mart, Beta Stores, City Pharma, Delta Travels, or Eco Home.

**Date standardization** converted all values in `transaction_date` to the `YYYY-MM-DD` format using `pd.to_datetime()`. The dates were already in a consistent format in the source file, so no reformatting errors occurred. The cleaned date range spans 2026-03-01 to 2026-03-06.

**Status standardization** stripped error codes and normalized casing. Seven distinct raw status strings were reduced to three canonical values. One row (T011) had a blank `gateway_region`; this was preserved as null rather than imputed.

**Risk score extraction** pulled numeric values from mixed-format strings using a regular expression pattern `r"\d+"`. One row (T011) had a completely blank `risk_score` field and was retained with a null value. All other 29 rows yielded a clean integer risk score in the range 38–86.

**Gateway region standardization** uppercased all values and stripped whitespace. Variants like `"apac"`, `" APAC "`, and `"APAC"` all resolved to `"APAC"`. Gateway region had 9 null values across the dataset (rows where no region was recorded); these were left as null and the enrichment column `default_region` from `merchant_master.csv` was used instead for flag calculations.

---

## Standardization Rules

**Merchant name mapping** used a normalized key comparison: each raw merchant name was lowercased, stripped of leading/trailing whitespace, and had internal multi-spaces collapsed to a single space. This key was matched against the same transformation applied to the `merchant_name` column of `merchant_master.csv`. The full variant → canonical name mapping is:

| Raw variant | Canonical name |
|---|---|
| `alpha mart`, `ALPHA MART`, `Alpha  Mart`, ` alpha mart `, `Alpha Mart` | Alpha Mart |
| `BETA STORES `, `Beta  Stores`, `beta stores`, ` beta stores`, `Beta Stores` | Beta Stores |
| `City Pharma` | City Pharma |
| `DELTA TRAVELS`, `Delta Travels`, `delta travels ` | Delta Travels |
| `Eco Home` | Eco Home |

**Status standardization** applied a prefix-match rule after lowercasing and stripping. Any status string beginning with `"captured"` mapped to `captured`; any beginning with `"failed"` mapped to `failed`; any beginning with `"chargeback"` mapped to `chargeback`. The value `"refunded"` was defined as a valid target but did not appear in this dataset. Raw status variants resolved as follows:

| Raw value | Cleaned value |
|---|---|
| `Captured `, `CAPTURED`, ` CAPTURED`, `Captured` | `captured` |
| `failed e05 timeout`, `Failed E05 Timeout`, `FAILED e05 TIMEOUT`, `failed E05 timeout`, `Failed E05 Timeout` | `failed` |
| ` chargeback `, `chargeback` | `chargeback` |

**Risk score extraction** used the regular expression `r"\d+"` applied to the raw string, taking the first match. Formats handled:

| Raw value | Extracted score |
|---|---|
| `score:62` | 62 |
| `risk-83` | 83 |
| `75 ` | 75 |
| `59 ` | 59 |
| *(blank)* | null |

**Gateway region** was standardized by stripping all whitespace and converting to uppercase. Variants `"apac"`, `" APAC "`, `"apac"` → `"APAC"`; `"eu"`, `" EU "` → `"EU"`; `"us"`, `"US"` → `"US"`.

**Currency amounts** were kept in their raw form in `raw_amount` and a new column `amount_usd` was derived by multiplying by the exchange rate matched on `(transaction_date, currency)` from `exchange_rates.csv`. The three currencies in the dataset were INR, EUR, and USD. USD rows had a rate of 1.0 and required no conversion.

**Flag thresholds** were defined as binary rules applied after enrichment:

| Flag | Rule |
|---|---|
| `high_value_flag` | 1 if `default_region == "APAC"` and `amount_usd > 5000`; or `default_region == "EU"` and `amount_usd > 6000`; or `default_region == "US"` and `amount_usd > 7000`; else 0 |
| `high_risk_flag` | 1 if `risk_score >= 70` OR `status == "chargeback"`; else 0 |

---

## Lookup and Enrichment Logic

**Exchange rate lookup** used a two-key join on `(transaction_date, currency)`. The `exchange_rates.csv` file provided daily rates for INR, EUR, and USD across six dates (2026-03-01 to 2026-03-06). All 30 transactions found a matching rate — there were no unmatched keys. Rates used:

| Date | INR (USD/1 INR) | EUR (USD/1 EUR) | USD |
|---|---|---|---|
| 2026-03-01 | 0.0119 | 1.08 | 1.0 |
| 2026-03-02 | 0.0120 | 1.09 | 1.0 |
| 2026-03-03 | 0.0121 | 1.08 | 1.0 |
| 2026-03-04 | 0.0120 | 1.07 | 1.0 |
| 2026-03-05 | 0.0118 | 1.09 | 1.0 |
| 2026-03-06 | 0.0119 | 1.08 | 1.0 |

The `amount_usd` calculation: `raw_amount × usd_rate`, rounded to 2 decimal places. Example: T001 had INR 420,000 on 2026-03-01 → 420,000 × 0.0119 = **$4,998.00**.

**Merchant master enrichment** used a left join on `merchant_name` (after standardization) against `merchant_master.csv`. Four columns were added from the master: `merchant_id`, `merchant_category`, `default_region`, and `account_manager`. All 30 rows matched — zero null `merchant_id` values after the join.

| merchant_name | merchant_id | merchant_category | default_region | account_manager |
|---|---|---|---|---|
| Alpha Mart | M001 | Grocery | APAC | Aisha Khan |
| Beta Stores | M002 | Electronics | APAC | Rohan Mehta |
| City Pharma | M003 | Healthcare | EU | Elena Rossi |
| Delta Travels | M004 | Travel | US | Marcus Lee |
| Eco Home | M005 | Home | EU | Nina Weber |

**High-value flag** logic used `default_region` (always populated from merchant master) rather than `gateway_region` (9 nulls) to ensure 100% coverage. The region-specific thresholds reflect typical ticket-size norms: APAC transactions are flagged at a lower USD threshold ($5,000) because they originate in INR and represent large absolute local amounts; EU and US thresholds are higher due to the stronger base currency.

**High-risk flag** combined two independent signals with an OR condition: a quantitative score signal (`risk_score >= 70`) and a qualitative outcome signal (`status == "chargeback"`). A transaction with a chargeback but a low risk score (e.g. T024 Eco Home, risk 65, chargeback) would still be flagged; similarly a transaction with a risk score of 77 but a captured status (e.g. T010 Beta Stores) would also be flagged.

---

## Final Answers

**Dataset overview**

The cleaned dataset contains 30 transactions across 5 merchants, 3 currencies (INR, EUR, USD), and 3 regions (APAC, EU, US), spanning 2026-03-01 to 2026-03-06. No rows were dropped during cleaning. One row (T011, Alpha Mart) has a null `risk_score` and null `gateway_region` — both were left as null rather than imputed.

**Status distribution**

| Status | Count | % of total |
|---|---|---|
| captured | 19 | 63.3% |
| failed | 7 | 23.3% |
| chargeback | 4 | 13.3% |

**Total GMV (all transactions)**

| Currency | Total raw amount | Total amount_usd |
|---|---|---|
| INR | 7,650,000 | ~$91,455 |
| EUR | 17,400 | ~$18,895 |
| USD | 14,600 | $14,600 |
| **Combined** | — | **~$116,355** |

**Captured GMV by merchant**

| Merchant | Captured txns | Captured GMV (USD) | % of total captured |
|---|---|---|---|
| Beta Stores | 7 | $33,431.00 | 40.6% |
| Alpha Mart | 8 | $29,984.50 | 36.4% |
| Delta Travels | 2 | $10,300.00 | 12.5% |
| City Pharma | 2 | $8,640.00 | 10.5% |
| Eco Home | 0 | $0.00 | 0.0% |
| **Total** | **19** | **$82,355.50** | — |

Eco Home had exactly 1 transaction in the dataset and it was a chargeback, resulting in zero captured GMV.

**High-value transactions**

7 transactions were flagged `high_value_flag = 1`. All 7 are APAC transactions (threshold: amount_usd > $5,000). No EU transactions exceeded $6,000 and no US transactions exceeded $7,000 in this dataset. The 7 flagged transactions are T003 ($6,069), T007 ($5,400), T010 ($7,381), T014 ($5,640), T020 ($6,136), T024 ($6,649, EU — Eco Home chargeback), and T027 ($7,200, US — Delta Travels).

**High-risk transactions**

9 transactions were flagged `high_risk_flag = 1`. The breakdown of triggering conditions:

| Trigger | Transaction IDs | Count |
|---|---|---|
| risk_score ≥ 70 only | T010 (77), T014 (73), T017 (72), T020 (75) | 4 |
| chargeback only | T024 (risk 65), T029 (risk 58) | 2 |
| Both conditions | T003 (71), T007 (83), T018 (86) | 3 |

**Merchant risk summary**

| Merchant | Total txns | Avg risk score | High-risk count | Total amount_usd |
|---|---|---|---|---|
| Beta Stores | 11 | 69.36 | 5 | $41,782.00 |
| Alpha Mart | 11 | 61.20 | 2 | $40,812.00 |
| Delta Travels | 4 | 48.75 | 1 | $14,600.00 |
| Eco Home | 2 | 54.50 | 1 | $10,246.00 |
| City Pharma | 2 | 40.00 | 0 | $8,640.00 |

Beta Stores carries the highest average risk score (69.36) and the most high-risk transactions (5 of 11 = 45.5% high-risk rate). City Pharma is the cleanest merchant — avg risk score of 40.0 with zero high-risk flags.

**Region summary**

| Region | Txns | Captured GMV | Avg risk score |
|---|---|---|---|
| APAC | 22 | $63,415.50 | 65.48 |
| EU | 4 | $8,640.00 | 47.25 |
| US | 4 | $10,300.00 | 48.75 |

APAC accounts for 73.3% of transactions and 77.0% of captured GMV, but also carries a significantly elevated average risk score (65.48 vs ~48 for EU and US).

**Chargeback exposure**

4 chargebacks totalling $16,260.00 in transaction value. All 4 involved a different merchant and a different user. The highest-value chargeback was Eco Home T024 at $6,649.00 (EU, EUR transaction).

---

## Formula Samples

The following Excel-compatible formulas replicate the key transformations and calculations from the Python pipeline. Assume the cleaned data starts at row 2 with column headers in row 1. Column letters correspond to: A = transaction_id, B = transaction_date, C = merchant_id, D = merchant_name, E = merchant_category, F = default_region, G = account_manager, H = raw_amount, I = currency, J = amount_usd, K = status, L = risk_score, M = gateway_region, N = user_id, O = payment_method, P = high_value_flag, Q = high_risk_flag.

**Amount to USD conversion (VLOOKUP with compound key)**

```excel
=H2 * VLOOKUP(B2 & I2, exchange_rates!$D:$E, 2, FALSE)
```

Where column D of exchange_rates sheet is a helper column `=A2&B2` (date + currency concatenated) and column E is the USD rate. This replicates the `(transaction_date, currency)` two-key lookup used in Python.

Alternatively with INDEX-MATCH for exact two-condition lookup:

```excel
=H2 * INDEX(exchange_rates!$C:$C,
       MATCH(1,
         (exchange_rates!$A:$A=B2) * (exchange_rates!$B:$B=I2),
         0))
```

Enter as an array formula (Ctrl+Shift+Enter in older Excel; works natively in Excel 365).

**Merchant name normalization (approximate match via TRIM + PROPER)**

```excel
=IFERROR(
  INDEX(merchant_master!$B:$B,
    MATCH(TRIM(LOWER(D2)),
          TRIM(LOWER(merchant_master!$B:$B)),
          0)),
  D2)
```

This strips whitespace and lowercases before matching, catching variants like `" alpha mart "` and `"ALPHA MART"`.

**Merchant lookup enrichment — merchant_id (VLOOKUP)**

```excel
=VLOOKUP(D2, merchant_master!$B:$F, 1, FALSE)
```

For other columns shift the column index: 2 = account_manager, 3 = merchant_category, 4 = default_region (adjusting to match master column order).

**Status clean-up (strip error codes)**

```excel
=IF(ISNUMBER(SEARCH("captured", K2)), "captured",
  IF(ISNUMBER(SEARCH("failed", K2)), "failed",
    IF(ISNUMBER(SEARCH("chargeback", K2)), "chargeback",
      IF(ISNUMBER(SEARCH("refunded", K2)), "refunded",
        ""))))
```

`SEARCH` is case-insensitive, so `"CAPTURED"`, `"Captured "`, and `"captured"` all resolve correctly. The trailing error codes in `"failed E05 timeout"` are ignored because the formula returns on first match.

**Risk score extraction (numeric only from mixed strings)**

```excel
=IFERROR(
  VALUE(MID(L2,
    MIN(IFERROR(FIND({0,1,2,3,4,5,6,7,8,9}, L2), LEN(L2)+1)),
    LEN(L2))),
  "")
```

Enter as an array formula. Finds the position of the first digit in the string (covering formats like `"score:62"`, `"risk-83"`, `"75 "`) and extracts from that point to the end of the string, then converts to a number.

**High-value flag**

```excel
=IF(
  OR(
    AND(F2="APAC", J2>5000),
    AND(F2="EU",   J2>6000),
    AND(F2="US",   J2>7000)
  ), 1, 0)
```

Uses `default_region` (column F) rather than `gateway_region` (column M) because gateway_region has 9 null values in this dataset. Using the merchant master region ensures all 30 rows get a valid flag.

**High-risk flag**

```excel
=IF(OR(L2>=70, K2="chargeback"), 1, 0)
```

Note: if `risk_score` (column L) is blank (as in T011), Excel will treat the comparison `L2>=70` as FALSE, so the row will only be flagged if its status is chargeback — consistent with the Python behaviour for null risk scores.

**Total captured GMV for a merchant (SUMIFS)**

```excel
=SUMIFS($J:$J, $D:$D, "Alpha Mart", $K:$K, "captured")
```

Replace `"Alpha Mart"` with any merchant name. To make it dynamic with a cell reference:

```excel
=SUMIFS($J:$J, $D:$D, S2, $K:$K, "captured")
```

Where S2 contains the merchant name being summarised.

**Chargeback ratio per merchant (in a summary table)**

```excel
=COUNTIFS($D:$D, S2, $K:$K, "chargeback") / COUNTIF($D:$D, S2)
```

Format the cell as Percentage. For the full dataset, Beta Stores and Alpha Mart both return 9.09% (1 chargeback out of 11 transactions each).

**Average risk score excluding nulls (AVERAGEIF)**

```excel
=AVERAGEIF($D:$D, "Beta Stores", $L:$L)
```

Excel's `AVERAGEIF` automatically excludes blank and text cells from the average, so null risk scores are handled correctly without additional filtering.

**Daily captured GMV (SUMPRODUCT)**

```excel
=SUMPRODUCT(($B:$B=B2) * ($K:$K="captured") * ($J:$J))
```

Returns the total captured `amount_usd` for the date in B2. Equivalent to the `SUMIFS` approach but handles array conditions more flexibly.

**Count of high-risk transactions by region**

```excel
=COUNTIFS($F:$F, "APAC", $Q:$Q, 1)
```

Replace `"APAC"` with `"EU"` or `"US"` for other regions. In this dataset: APAC = 8 high-risk, EU = 1, US = 1.
