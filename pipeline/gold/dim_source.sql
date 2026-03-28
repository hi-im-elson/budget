INSERT OR REPLACE INTO gold.dim_source ("source", "last_transaction_date", "last_updated")
SELECT
    'amex-cobalt' AS "source",
    MAX(date) AS last_transaction_date,
    MAX(updated_at) AS "last_updated"
FROM silver.amex_cobalt
HAVING MAX(date) IS NOT NULL;

INSERT OR REPLACE INTO gold.dim_source ("source", "last_transaction_date", "last_updated")
SELECT
    'rbc-mastercard' AS "source",
    MAX(transaction_date) AS last_transaction_date,
    MAX(updated_at) AS "last_updated"
FROM silver.rbc_mastercard
HAVING MAX(transaction_date) IS NOT NULL;

INSERT OR REPLACE INTO gold.dim_source ("source", "last_transaction_date", "last_updated")
SELECT
    'wealthsimple-cash' AS "source",
    MAX(date) AS last_transaction_date,
    MAX(updated_at) AS "last_updated"
FROM silver.wealthsimple_cash
HAVING MAX(date) IS NOT NULL;
