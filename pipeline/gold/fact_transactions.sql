CREATE TABLE IF NOT EXISTS gold.fact_transactions (
    "id"               VARCHAR NOT NULL PRIMARY KEY,
    "transaction_date" DATE NOT NULL,
    "source"           VARCHAR NOT NULL,
    "merchant_id"      VARCHAR,
    "type_code"        VARCHAR NOT NULL,
    "description"      VARCHAR,
    "amount"           DECIMAL(10,2) NOT NULL,
    "direction"        VARCHAR(20) NOT NULL,
    "category_id"      INTEGER,
    "recipient_name"   VARCHAR,
    "currency"         VARCHAR(3) DEFAULT 'CAD',
    "source_id"        UBIGINT NOT NULL,
    "transfer_pair_id" VARCHAR                     -- populated by transfer_pairs.sql
);

DELETE FROM gold.fact_transactions;

-- ─── Amex Cobalt ─────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('amex-cobalt' || CAST(s.id AS VARCHAR)) AS id,
    s.date                                         AS transaction_date,
    'amex-cobalt'                                  AS source,
    dm.id                                          AS merchant_id,
    CASE
        WHEN s.merchant = 'PAYMENT RECEIVED - THANK YOU'   THEN 'cc_payment'
        WHEN s.merchant = 'MEMBERSHIP FEE INSTALLMENT'     THEN 'fee'
        WHEN s.merchant = 'Use Points for Purchases'       THEN 'cashback'
        WHEN s.merchant = 'Air Canada Pay with Points'     THEN 'cashback'
        WHEN s.amount < 0 AND s.merchant != 'PAYMENT RECEIVED - THANK YOU'
                                                           THEN 'refund'
        ELSE 'spending'
    END                                            AS type_code,
    s.description                                  AS description,
    ABS(s.amount)                                  AS amount,
    CASE
        WHEN s.merchant = 'PAYMENT RECEIVED - THANK YOU'   THEN 'transfer'
        WHEN s.merchant IN ('Use Points for Purchases', 'Air Canada Pay with Points')
                                                           THEN 'inbound'
        WHEN s.amount < 0 AND s.merchant != 'PAYMENT RECEIVED - THANK YOU'
                                                           THEN 'inbound'
        ELSE 'outbound'
    END                                            AS direction,
    dm.category_id                                 AS category_id,
    NULL                                           AS recipient_name,
    'CAD'                                          AS currency,
    s.id                                           AS source_id,
    NULL                                           AS transfer_pair_id
FROM silver.amex_cobalt s
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'amex-cobalt'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.merchant, '\s+', ' ', 'g'));

-- ─── RBC Mastercard ──────────────────────────────────────────────────────────
INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('rbc-mastercard' || CAST(s.id AS VARCHAR)) AS id,
    s.transaction_date                                AS transaction_date,
    'rbc-mastercard'                                  AS source,
    dm.id                                             AS merchant_id,
    CASE
        WHEN s.description = 'PAYMENT - THANK YOU / PAI EMENT - MERCI'
                                                      THEN 'cc_payment'
        WHEN s.cad > 0 AND s.description != 'PAYMENT - THANK YOU / PAI EMENT - MERCI'
                                                      THEN 'refund'
        ELSE 'spending'
    END                                               AS type_code,
    s.description                                     AS description,
    ABS(s.cad)                                        AS amount,
    CASE
        WHEN s.description = 'PAYMENT - THANK YOU / PAI EMENT - MERCI'
                                                      THEN 'transfer'
        WHEN s.cad > 0 AND s.description != 'PAYMENT - THANK YOU / PAI EMENT - MERCI'
                                                      THEN 'inbound'
        ELSE 'outbound'
    END                                               AS direction,
    dm.category_id                                    AS category_id,
    NULL                                              AS recipient_name,
    'CAD'                                             AS currency,
    s.id                                              AS source_id,
    NULL                                              AS transfer_pair_id
FROM silver.rbc_mastercard s
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'rbc-mastercard'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.description, '\s+', ' ', 'g'));

-- ─── RBC Chequing ────────────────────────────────────────────────────────────
-- Positive CAD = money IN. Negative CAD = money OUT.
INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('rbc-chequing' || CAST(s.id AS VARCHAR))    AS id,
    s.transaction_date                                  AS transaction_date,
    'rbc-chequing'                                      AS source,
    dm.id                                               AS merchant_id,
    CASE
        -- Outbound: credit card payments to own cards
        WHEN s.cad < 0
             AND (   LOWER(s.description) LIKE '%amex%'
                  OR LOWER(s.description) LIKE '%american express%'
                  OR LOWER(s.description) LIKE '%mastercard%'
                  OR LOWER(s.description) LIKE '%visa%'
                 )                                      THEN 'cc_payment'
        -- Outbound: transfers to Wealthsimple or own accounts
        WHEN s.cad < 0
             AND (   LOWER(s.description) LIKE '%wealthsimple%'
                  OR LOWER(s.description) LIKE '%wlthsimple%'
                  OR LOWER(s.description) LIKE '%transfer%'
                 )                                      THEN 'account_transfer'
        -- Outbound: e-Transfer sent
        WHEN s.cad < 0
             AND LOWER(s.description) LIKE '%e-transfer%'
                                                        THEN 'e_transfer_out'
        -- Outbound: bill payments
        WHEN s.cad < 0
             AND LOWER(s.description) LIKE '%bill payment%'
                                                        THEN 'bill_payment'
        -- Inbound: payroll / direct deposit
        WHEN s.cad > 0
             AND (   LOWER(s.description) LIKE '%themis%'
                  OR LOWER(s.description) LIKE '%payroll%'
                  OR LOWER(s.description) LIKE '%direct dep%'
                 )                                      THEN 'payroll'
        -- Inbound: e-Transfer received
        WHEN s.cad > 0
             AND LOWER(s.description) LIKE '%e-transfer%'
                                                        THEN 'e_transfer_in'
        -- Inbound: government / CRA deposits
        WHEN s.cad > 0
             AND (   LOWER(s.description) LIKE '%canada revenue%'
                  OR LOWER(s.description) LIKE '%cra%'
                  OR LOWER(s.description) LIKE '%tax refund%'
                  OR LOWER(s.description) LIKE '%government%'
                 )                                      THEN 'deposit'
        -- Inbound: generic deposit
        WHEN s.cad > 0                                  THEN 'deposit'
        -- Outbound: default
        ELSE 'spending'
    END                                                 AS type_code,
    s.description                                       AS description,
    ABS(s.cad)                                          AS amount,
    CASE
        -- Outbound transfers → direction = 'transfer' (not an expense)
        WHEN s.cad < 0
             AND (   LOWER(s.description) LIKE '%amex%'
                  OR LOWER(s.description) LIKE '%american express%'
                  OR LOWER(s.description) LIKE '%mastercard%'
                  OR LOWER(s.description) LIKE '%visa%'
                  OR LOWER(s.description) LIKE '%wealthsimple%'
                  OR LOWER(s.description) LIKE '%wlthsimple%'
                  OR LOWER(s.description) LIKE '%transfer%'
                 )                                      THEN 'transfer'
        WHEN s.cad > 0                                  THEN 'inbound'
        ELSE 'outbound'
    END                                                 AS direction,
    dm.category_id                                      AS category_id,
    NULL                                                AS recipient_name,
    'CAD'                                               AS currency,
    s.id                                                AS source_id,
    NULL                                                AS transfer_pair_id
FROM silver.rbc_chequing s
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'rbc-chequing'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.description, '\s+', ' ', 'g'));

-- ─── Wealthsimple Cash ───────────────────────────────────────────────────────
INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('wealthsimple-cash' || CAST(s.id AS VARCHAR)) AS id,
    s.date                                               AS transaction_date,
    'wealthsimple-cash'                                  AS source,
    dm.id                                                AS merchant_id,
    CASE
        WHEN s.transaction = 'SPEND'      THEN 'spending'
        WHEN s.transaction = 'OBP_OUT'    THEN 'bill_payment'
        WHEN s.transaction = 'E_TRFOUT'   THEN 'e_transfer_out'
        WHEN s.transaction = 'E_TRFIN'    THEN 'e_transfer_in'
        WHEN s.transaction = 'P2P_SENT'   THEN 'p2p'
        WHEN s.transaction = 'AFT_IN'     THEN
            CASE
                WHEN LOWER(s.description) LIKE '%themis%' THEN 'payroll'
                ELSE 'deposit'
            END
        WHEN s.transaction = 'AFT_OUT'    THEN 'pre_auth_debit'
        WHEN s.transaction = 'EFT'        THEN 'deposit'
        WHEN s.transaction = 'EFTOUT'     THEN 'account_transfer'
        WHEN s.transaction = 'TRFOUT'     THEN 'account_transfer'
        WHEN s.transaction = 'INT'        THEN 'interest_earned'
        WHEN s.transaction = 'CASHBACK'   THEN 'cashback'
        ELSE 'spending'
    END                                                  AS type_code,
    s.description                                        AS description,
    ABS(s.amount)                                        AS amount,
    CASE
        WHEN s.transaction IN ('E_TRFIN', 'AFT_IN', 'EFT', 'INT', 'CASHBACK')
                                                         THEN 'inbound'
        WHEN s.transaction IN ('TRFOUT', 'EFTOUT')       THEN 'transfer'
        WHEN s.transaction = 'OBP_OUT'
             AND LOWER(s.description) LIKE '%mastercard%'
                                                         THEN 'transfer'
        ELSE 'outbound'
    END                                                  AS direction,
    COALESCE(etr.category_id, dm.category_id)            AS category_id,
    etr.recipient_name                                   AS recipient_name,
    s.currency                                           AS currency,
    s.id                                                 AS source_id,
    NULL                                                 AS transfer_pair_id
FROM silver.wealthsimple_cash s
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'wealthsimple-cash'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.description, '\s+', ' ', 'g'))
LEFT JOIN mappings.etransfer_recipients etr
    ON s.date = etr.date
    AND ABS(s.amount) = ABS(etr.amount)
    AND s.transaction IN ('E_TRFOUT', 'E_TRFIN', 'P2P_SENT');
