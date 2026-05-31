CREATE OR REPLACE TABLE gold.dim_merchant (
    "id"              VARCHAR(255) NOT NULL PRIMARY KEY,
    "source"          VARCHAR(255) NOT NULL,
    "merchant"        VARCHAR(255),
    "is_subscription" BOOLEAN      NOT NULL DEFAULT FALSE,
    "category_id"     INTEGER,
    "parent_id"       VARCHAR(255)
);

DELETE FROM gold.dim_merchant;

-- ─── Populate merchants from each silver source ───────────────────────────────

INSERT OR IGNORE INTO gold.dim_merchant (id, source, merchant)
SELECT DISTINCT
    SHA256('amex-cobalt' || TRIM(REGEXP_REPLACE(merchant, '\s+', ' ', 'g'))) AS id,
    'amex-cobalt' AS source,
    TRIM(REGEXP_REPLACE(merchant, '\s+', ' ', 'g')) AS merchant
FROM silver.amex_cobalt
WHERE TRIM(REGEXP_REPLACE(merchant, '\s+', ' ', 'g')) NOT IN (
    'MEMBERSHIP FEE INSTALLMENT',
    'PAYMENT RECEIVED - THANK YOU',
    'Use Points for Purchases'
);

INSERT OR IGNORE INTO gold.dim_merchant (id, source, merchant)
SELECT DISTINCT
    SHA256('rbc-mastercard' || TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g'))) AS id,
    'rbc-mastercard' AS source,
    TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g')) AS merchant
FROM silver.rbc_mastercard
WHERE TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g')) NOT IN (
    'PAYMENT - THANK YOU / PAI EMENT - MERCI'
);

INSERT OR IGNORE INTO gold.dim_merchant (id, source, merchant)
SELECT DISTINCT
    SHA256('rbc-chequing' || TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g'))) AS id,
    'rbc-chequing' AS source,
    TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g')) AS merchant
FROM silver.rbc_chequing;

INSERT OR IGNORE INTO gold.dim_merchant (id, source, merchant)
SELECT DISTINCT
    SHA256('wealthsimple-cash' || TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g'))) AS id,
    'wealthsimple-cash' AS source,
    TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g')) AS merchant
FROM silver.wealthsimple_cash
WHERE transaction = 'SPEND';

-- ─── Apply explicit merchant-to-category overrides ────────────────────────────
UPDATE gold.dim_merchant dm
SET category_id = mc.category_id
FROM mappings.merchant_to_category mc
WHERE TRIM(dm.merchant) = TRIM(mc.merchant_name);

-- ─── Apply recurring vendor rules via keyword match ───────────────────────────
-- Matches the highest-priority (longest) keyword for each merchant and sets
-- category_id + is_subscription=true.  This automatically categorises known
-- recurring vendors (utilities, phone, insurance, subscriptions) without
-- requiring individual merchant_to_category entries.
UPDATE gold.dim_merchant dm
SET
    category_id      = rvr.category_id,
    is_subscription  = TRUE
FROM (
    SELECT
        dm2.id,
        rvr2.category_id,
        ROW_NUMBER() OVER (
            PARTITION BY dm2.id
            ORDER BY LENGTH(rvr2.keyword) DESC
        ) AS rn
    FROM gold.dim_merchant dm2
    JOIN mappings.recurring_vendor_rules rvr2
        ON LOWER(dm2.merchant) LIKE '%' || rvr2.keyword || '%'
    WHERE dm2.category_id IS NULL   -- don't overwrite explicit merchant_to_category
) rvr
WHERE dm.id = rvr.id
AND   rvr.rn = 1;

-- ─── Apply parent merchant grouping ──────────────────────────────────────────
UPDATE gold.dim_merchant dm
SET parent_id = parent.id
FROM mappings.merchant_to_parent_merchant mp
JOIN gold.dim_merchant parent ON TRIM(parent.merchant) = TRIM(mp.parent_merchant_name)
WHERE TRIM(dm.merchant) = TRIM(mp.merchant_name);
