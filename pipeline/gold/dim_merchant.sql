CREATE TABLE IF NOT EXISTS gold.dim_merchant (
    "id" VARCHAR(255) NOT NULL PRIMARY KEY,
    "source" VARCHAR(255) NOT NULL,
    "merchant" VARCHAR(255),
    "is_subscription" BOOLEAN NOT NULL DEFAULT FALSE,
    "category_id" INTEGER,
    "parent_id" VARCHAR(255)
);

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
    SHA256('wealthsimple-cash' || TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g'))) AS id,
    'wealthsimple-cash' AS source,
    TRIM(REGEXP_REPLACE(description, '\s+', ' ', 'g')) AS merchant
FROM silver.wealthsimple_cash;

UPDATE gold.dim_merchant dm
SET category_id = mc.category_id
FROM mappings.merchant_to_category mc
WHERE TRIM(dm.merchant) = TRIM(mc.merchant_name);

UPDATE gold.dim_merchant dm
SET parent_id = parent.id
FROM mappings.merchant_to_parent_merchant mp
JOIN gold.dim_merchant parent ON TRIM(parent.merchant) = TRIM(mp.parent_merchant_name)
WHERE TRIM(dm.merchant) = TRIM(mp.merchant_name);
