-- ============================================================
-- analysis_queries.sql
-- Table: transactions
-- All monetary amounts in USD (amount_usd column)
-- ============================================================

-- Q1
-- Count transactions by status
SELECT
    status,
    COUNT(*) AS transaction_count
FROM transactions
GROUP BY status
ORDER BY transaction_count DESC;

-- Q2
-- Calculate total captured GMV by merchant
SELECT
    merchant_name,
    ROUND(SUM(amount_usd), 2) AS total_captured_gmv_usd
FROM transactions
WHERE status = 'captured'
GROUP BY merchant_name
ORDER BY total_captured_gmv_usd DESC;

-- Q3
-- Top 10 merchants by captured GMV
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

-- Q4
-- Daily GMV and successful (captured) transaction count
SELECT
    transaction_date,
    COUNT(CASE WHEN status = 'captured' THEN 1 END) AS captured_txn_count,
    ROUND(SUM(CASE WHEN status = 'captured' THEN amount_usd ELSE 0 END), 2) AS daily_captured_gmv_usd,
    ROUND(SUM(amount_usd), 2) AS daily_total_gmv_usd
FROM transactions
GROUP BY transaction_date
ORDER BY transaction_date;

-- Q5
-- Merchants with chargeback ratio above 1%
-- (chargeback_count / total_transactions > 0.01)
SELECT
    merchant_name,
    COUNT(*)                                                          AS total_transactions,
    COUNT(CASE WHEN status = 'chargeback' THEN 1 END)                AS chargeback_count,
    ROUND(
        100.0 * COUNT(CASE WHEN status = 'chargeback' THEN 1 END)
              / COUNT(*),
        2
    )                                                                 AS chargeback_ratio_pct
FROM transactions
GROUP BY merchant_name
HAVING chargeback_ratio_pct > 1
ORDER BY chargeback_ratio_pct DESC;

-- Q6
-- Regions with average risk score above 50 AND more than 20 transactions
-- Note: uses default_region (always populated) rather than gateway_region (sparse)
SELECT
    default_region,
    COUNT(*)                          AS total_transactions,
    ROUND(AVG(risk_score), 2)         AS avg_risk_score
FROM transactions
WHERE risk_score IS NOT NULL
GROUP BY default_region
HAVING avg_risk_score > 50
   AND total_transactions > 20;

-- Q7
-- Users with 3 or more failed or chargeback transactions on the same day
SELECT
    user_id,
    transaction_date,
    COUNT(*) AS bad_txn_count
FROM transactions
WHERE status IN ('failed', 'chargeback')
GROUP BY user_id, transaction_date
HAVING bad_txn_count >= 3
ORDER BY bad_txn_count DESC, transaction_date;

-- Q8
-- Chargeback count, unique affected users, and chargeback amount by merchant
SELECT
    merchant_name,
    merchant_category,
    COUNT(*)                          AS chargeback_count,
    COUNT(DISTINCT user_id)           AS unique_affected_users,
    ROUND(SUM(amount_usd), 2)         AS total_chargeback_amount_usd
FROM transactions
WHERE status = 'chargeback'
GROUP BY merchant_name, merchant_category
ORDER BY total_chargeback_amount_usd DESC;
