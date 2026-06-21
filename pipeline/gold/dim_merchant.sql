-- P2-07: Simplified dim_merchant — derives from gold.fact_transactions
-- Removed all four source-specific hardcoded INSERT blocks
-- Schema now depends on: gold.fact_transactions (populated by fact_transactions.py)

CREATE OR REPLACE TABLE gold.dim_merchant (
    "merchant_key"    VARCHAR(255) NOT NULL PRIMARY KEY,
    "merchant_name"   VARCHAR(255),
    "default_category" VARCHAR(255),
    "transaction_count" BIGINT,
    "last_seen"       DATE
);

DELETE FROM gold.dim_merchant;

-- Populate from gold.fact_transactions: one row per distinct normalised merchant
-- (no source-specific knowledge, clean aggregation over the fact table)
INSERT INTO gold.dim_merchant (merchant_key, merchant_name, default_category, transaction_count, last_seen)
SELECT
    md5(lower(trim(description)))     AS merchant_key,
    trim(description)                  AS merchant_name,
    mode() WITHIN GROUP (ORDER BY category_name) AS default_category,
    count(*)                           AS transaction_count,
    max(transaction_date)              AS last_seen
FROM gold.fact_transactions
WHERE direction = 'outbound'
  AND category_name NOT IN ('cc_payment', 'transfers')
GROUP BY merchant_key, merchant_name;

-- ─── Apply explicit merchant-to-category overrides ────────────────────────────
UPDATE gold.dim_merchant dm
SET default_category = c.category
FROM mappings.merchant_to_category mc
JOIN mappings.categories c ON c.id = mc.category_id
WHERE TRIM(dm.merchant_name) = TRIM(mc.merchant_name);

-- ─── Apply recurring vendor rules via keyword match ───────────────────────────
UPDATE gold.dim_merchant dm
SET default_category = rvr.category
FROM (
    SELECT
        dm2.merchant_key,
        c2.category,
        ROW_NUMBER() OVER (
            PARTITION BY dm2.merchant_key
            ORDER BY LENGTH(rvr2.keyword) DESC
        ) AS rn
    FROM gold.dim_merchant dm2
    JOIN mappings.recurring_vendor_rules rvr2
        ON LOWER(dm2.merchant_name) LIKE '%' || rvr2.keyword || '%'
    JOIN mappings.categories c2 ON c2.id = rvr2.category_id
    WHERE dm2.default_category IS NULL
) rvr
WHERE dm.merchant_key = rvr.merchant_key
AND   rvr.rn = 1;
