# SQL Answers

---

## Q1

### Query

```sql
SELECT
    status,
    COUNT(*) AS transaction_count
FROM transactions
GROUP BY status
ORDER BY transaction_count DESC;
```

### Result Summary

| status | transaction_count |
|---|---|
| captured | 19 |
| failed | 7 |
| chargeback | 4 |

**30 total transactions.** The majority (63%) were successfully captured. Failed transactions account for 23%, and chargebacks represent 13% of volume — a notably high ratio worth monitoring across all merchants.

---

## Q2

### Query

```sql
SELECT
    merchant_name,
    ROUND(SUM(amount_usd), 2) AS total_captured_gmv_usd
FROM transactions
WHERE status = 'captured'
GROUP BY merchant_name
ORDER BY total_captured_gmv_usd DESC;
```

### Result Summary

| merchant_name | total_captured_gmv_usd |
|---|---|
| Beta Stores | $33,431.00 |
| Alpha Mart | $29,984.50 |
| Delta Travels | $10,300.00 |
| City Pharma | $8,640.00 |

**Total captured GMV: $82,355.50.** Beta Stores and Alpha Mart together drive ~77% of captured revenue. Eco Home had no captured transactions (its only transaction was a chargeback).

---

## Q3

### Query

```sql
SELECT
    merchant_name,
    merchant_category,
    default_region,
    COUNT(*)                   AS captured_txn_count,
    ROUND(SUM(amount_usd), 2)  AS captured_gmv_usd
FROM transactions
WHERE status = 'captured'
GROUP BY merchant_name, merchant_category, default_region
ORDER BY captured_gmv_usd DESC
LIMIT 10;
```

### Result Summary

| merchant_name | merchant_category | default_region | captured_txn_count | captured_gmv_usd |
|---|---|---|---|---|
| Beta Stores | Electronics | APAC | 7 | $33,431.00 |
| Alpha Mart | Grocery | APAC | 8 | $29,984.50 |
| Delta Travels | Travel | US | 2 | $10,300.00 |
| City Pharma | Healthcare | EU | 2 | $8,640.00 |

Only 4 merchants exist in this dataset (all 4 appear in the top 10). APAC dominates both by transaction count and GMV, contributing $63,415.50 (77%) of total captured revenue.

---

## Q4

### Query

```sql
SELECT
    transaction_date,
    COUNT(CASE WHEN status = 'captured' THEN 1 END)                          AS captured_txn_count,
    ROUND(SUM(CASE WHEN status = 'captured' THEN amount_usd ELSE 0 END), 2)  AS daily_captured_gmv_usd,
    ROUND(SUM(amount_usd), 2)                                                 AS daily_total_gmv_usd
FROM transactions
GROUP BY transaction_date
ORDER BY transaction_date;
```

### Result Summary

| transaction_date | captured_txn_count | daily_captured_gmv_usd | daily_total_gmv_usd |
|---|---|---|---|
| 2026-03-01 | 5 | $26,382.00 | $26,382.00 |
| 2026-03-02 | 3 | $11,080.00 | $25,049.00 |
| 2026-03-03 | 4 | $16,031.50 | $18,391.00 |
| 2026-03-04 | 4 | $13,920.00 | $16,420.00 |
| 2026-03-05 | 1 | $6,136.00 | $19,232.00 |
| 2026-03-06 | 2 | $8,806.00 | $10,606.00 |

**March 1 was the strongest day** with $26,382 in captured GMV and 100% capture rate (all 5 transactions captured). March 5 had the largest gap between total and captured GMV ($19,232 total vs $6,136 captured) — U008 drove 4 failed/chargeback transactions on that day.

---

## Q5

### Query

```sql
SELECT
    merchant_name,
    COUNT(*)                                                           AS total_transactions,
    COUNT(CASE WHEN status = 'chargeback' THEN 1 END)                 AS chargeback_count,
    ROUND(
        100.0 * COUNT(CASE WHEN status = 'chargeback' THEN 1 END)
              / COUNT(*),
        2
    )                                                                  AS chargeback_ratio_pct
FROM transactions
GROUP BY merchant_name
HAVING chargeback_ratio_pct > 1
ORDER BY chargeback_ratio_pct DESC;
```

### Result Summary

| merchant_name | total_transactions | chargeback_count | chargeback_ratio_pct |
|---|---|---|---|
| Eco Home | 2 | 1 | 50.00% |
| Delta Travels | 4 | 1 | 25.00% |
| Beta Stores | 11 | 1 | 9.09% |
| Alpha Mart | 11 | 1 | 9.09% |

**All 4 merchants exceed the 1% chargeback threshold.** Eco Home (50%) and Delta Travels (25%) are the most alarming, though their small transaction counts inflate the ratio. With higher volumes, Beta Stores and Alpha Mart's 9.09% ratios remain significantly above industry norms (~0.5–1%).

---

## Q6

### Query

```sql
SELECT
    default_region,
    COUNT(*)                  AS total_transactions,
    ROUND(AVG(risk_score), 2) AS avg_risk_score
FROM transactions
WHERE risk_score IS NOT NULL
GROUP BY default_region
HAVING avg_risk_score > 50
   AND total_transactions > 20;
```

### Result Summary

| default_region | total_transactions | avg_risk_score |
|---|---|---|
| APAC | 21 | 65.48 |

**Only APAC meets both criteria** (avg risk 65.48, 21 qualifying transactions). EU (2 txns) and US (4 txns) fall below the 20-transaction threshold. APAC's elevated average risk score is primarily driven by Beta Stores transactions with scores in the 70–86 range.

---

## Q7

### Query

```sql
SELECT
    user_id,
    transaction_date,
    COUNT(*) AS bad_txn_count
FROM transactions
WHERE status IN ('failed', 'chargeback')
GROUP BY user_id, transaction_date
HAVING bad_txn_count >= 3
ORDER BY bad_txn_count DESC, transaction_date;
```

### Result Summary

| user_id | transaction_date | bad_txn_count |
|---|---|---|
| U008 | 2026-03-05 | 4 |

**User U008 triggered 4 failed/chargeback transactions in a single day (2026-03-05).** This is a strong fraud signal — the breakdown was: 2 failed (T016 Beta Stores, T017 Beta Stores), 1 chargeback (T018 Beta Stores), and 1 failed (T019 Alpha Mart). All four transactions occurred on the same date across two merchants.

---

## Q8

### Query

```sql
SELECT
    merchant_name,
    merchant_category,
    COUNT(*)                     AS chargeback_count,
    COUNT(DISTINCT user_id)      AS unique_affected_users,
    ROUND(SUM(amount_usd), 2)    AS total_chargeback_amount_usd
FROM transactions
WHERE status = 'chargeback'
GROUP BY merchant_name, merchant_category
ORDER BY total_chargeback_amount_usd DESC;
```

### Result Summary

| merchant_name | merchant_category | chargeback_count | unique_affected_users | total_chargeback_amount_usd |
|---|---|---|---|---|
| Eco Home | Home | 1 | 1 | $6,649.00 |
| Alpha Mart | Grocery | 1 | 1 | $5,400.00 |
| Delta Travels | Travel | 1 | 1 | $2,500.00 |
| Beta Stores | Electronics | 1 | 1 | $1,711.00 |

**Total chargeback exposure: $16,260.00 across 4 merchants.** Eco Home carries the highest single-chargeback dollar amount ($6,649) despite only 2 total transactions — its chargeback was a large EUR purchase. Each merchant has exactly 1 chargeback affecting 1 unique user. Combined, chargebacks represent 13.8% of total processed volume ($117,880).
