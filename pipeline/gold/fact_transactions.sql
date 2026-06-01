-- =============================================================================
-- gold.fact_transactions
-- =============================================================================
-- Classification priority (highest → lowest):
--   1. Structural rules  — hard signals that never change (cc_payment, refund,
--                          account_transfer for known internal flows, etc.)
--   2. classification_rules table  — keyword-based payroll / insurer / gov
--                                    overrides, keyed by source + description
--   3. etransfer_rules table  — recurring e-transfer payee/sender name patterns
--   4. dim_merchant lookup  — merchant-level category override
--   5. dim_type_category default  — fallback category for the type_code
--
-- To add a new payroll source, insurer, or government payment: add a row to
-- data/mappings/classification_rules.csv and re-run the pipeline.
-- To classify a recurring e-transfer: add a row to
-- data/mappings/etransfer_rules.csv.
-- No SQL changes are required for new individual vendors or employers.
-- =============================================================================

CREATE OR REPLACE TABLE gold.fact_transactions (
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
    "transfer_pair_id" VARCHAR
);

DELETE FROM gold.fact_transactions;

-- ─────────────────────────────────────────────────────────────────────────────
-- AMEX COBALT
-- Classification is purely structural (payment/fee/cashback/refund/spend).
-- No classification_rules lookup needed — Amex has no payroll deposits.
-- ─────────────────────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('amex-cobalt' || CAST(s.id AS VARCHAR)) AS id,
    s.date                                         AS transaction_date,
    'amex-cobalt'                                  AS source,
    dm.id                                          AS merchant_id,
    CASE
        WHEN s.merchant = 'PAYMENT RECEIVED - THANK YOU'                     THEN 'cc_payment'
        WHEN s.merchant = 'MEMBERSHIP FEE INSTALLMENT'                       THEN 'fee'
        WHEN s.merchant IN ('Use Points for Purchases',
                            'Air Canada Pay with Points')                    THEN 'cashback'
        WHEN s.amount < 0
             AND s.merchant != 'PAYMENT RECEIVED - THANK YOU'                THEN 'refund'
        ELSE 'spending'
    END                                            AS type_code,
    s.description                                  AS description,
    ABS(s.amount)                                  AS amount,
    CASE
        WHEN s.merchant = 'PAYMENT RECEIVED - THANK YOU'                     THEN 'transfer'
        WHEN s.merchant IN ('Use Points for Purchases',
                            'Air Canada Pay with Points')                    THEN 'inbound'
        WHEN s.amount < 0
             AND s.merchant != 'PAYMENT RECEIVED - THANK YOU'                THEN 'inbound'
        ELSE 'outbound'
    END                                            AS direction,
    COALESCE(dm.category_id, dtc.default_category_id)                        AS category_id,
    NULL                                           AS recipient_name,
    'CAD'                                          AS currency,
    s.id                                           AS source_id,
    NULL                                           AS transfer_pair_id
FROM silver.amex_cobalt s
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'amex-cobalt'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.merchant, '\s+', ' ', 'g'))
LEFT JOIN gold.dim_type_category dtc
    ON dtc.type_code = CASE
        WHEN s.merchant = 'PAYMENT RECEIVED - THANK YOU'                     THEN 'cc_payment'
        WHEN s.merchant = 'MEMBERSHIP FEE INSTALLMENT'                       THEN 'fee'
        WHEN s.merchant IN ('Use Points for Purchases',
                            'Air Canada Pay with Points')                    THEN 'cashback'
        WHEN s.amount < 0
             AND s.merchant != 'PAYMENT RECEIVED - THANK YOU'                THEN 'refund'
        ELSE 'spending'
    END;

-- ─────────────────────────────────────────────────────────────────────────────
-- RBC MASTERCARD
-- Classification is structural (payment/refund/spend). No deposits on a CC.
-- ─────────────────────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('rbc-mastercard' || CAST(s.id AS VARCHAR)) AS id,
    s.transaction_date                                AS transaction_date,
    'rbc-mastercard'                                  AS source,
    dm.id                                             AS merchant_id,
    CASE
        WHEN s.description = 'PAYMENT - THANK YOU / PAI EMENT - MERCI'      THEN 'cc_payment'
        WHEN s.cad > 0
             AND s.description != 'PAYMENT - THANK YOU / PAI EMENT - MERCI' THEN 'refund'
        ELSE 'spending'
    END                                               AS type_code,
    s.description                                     AS description,
    ABS(s.cad)                                        AS amount,
    CASE
        WHEN s.description = 'PAYMENT - THANK YOU / PAI EMENT - MERCI'      THEN 'transfer'
        WHEN s.cad > 0
             AND s.description != 'PAYMENT - THANK YOU / PAI EMENT - MERCI' THEN 'inbound'
        ELSE 'outbound'
    END                                               AS direction,
    COALESCE(dm.category_id, dtc.default_category_id)                        AS category_id,
    NULL                                              AS recipient_name,
    'CAD'                                             AS currency,
    s.id                                              AS source_id,
    NULL                                              AS transfer_pair_id
FROM silver.rbc_mastercard s
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'rbc-mastercard'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.description, '\s+', ' ', 'g'))
LEFT JOIN gold.dim_type_category dtc
    ON dtc.type_code = CASE
        WHEN s.description = 'PAYMENT - THANK YOU / PAI EMENT - MERCI'      THEN 'cc_payment'
        WHEN s.cad > 0
             AND s.description != 'PAYMENT - THANK YOU / PAI EMENT - MERCI' THEN 'refund'
        ELSE 'spending'
    END;

-- ─────────────────────────────────────────────────────────────────────────────
-- RBC CHEQUING
--
-- Uses classification_rules CTE to resolve type_code for inbound transactions
-- without hardcoding any employer or insurer name.
--
-- Resolution order for inbound (cad > 0):
--   1. Structural internal-transfer signals (Wealthsimple, own-bank references)
--   2. classification_rules keyword match (payroll, insurance_reimbursement,
--      government_deposit) — lowest priority value wins
--   3. E-transfer in (e_transfer_in) if description contains 'e-transfer'
--   4. Generic deposit fallback
--
-- Resolution order for outbound (cad < 0):
--   1. CC payment (amex / mastercard / visa keywords)
--   2. E-transfer out
--   3. Account transfer (wealthsimple / transfer keywords)
--   4. Bill payment
--   5. Spending fallback
-- ─────────────────────────────────────────────────────────────────────────────
WITH rbc_chq_inbound_rule AS (
    -- For each rbc-chequing inbound row, find the highest-priority
    -- classification_rules match (lowest priority number).
    SELECT
        s.id                                                    AS source_id,
        cr.type_code                                            AS matched_type_code
    FROM silver.rbc_chequing s
    JOIN mappings.classification_rules cr
        ON  cr.source      = 'rbc-chequing'
        AND cr.match_field = 'description'
        AND LOWER(s.description) LIKE '%' || cr.keyword || '%'
    WHERE s.cad > 0
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY s.id
        ORDER BY cr.priority ASC, cr.id ASC
    ) = 1
),

rbc_chq_classified AS (
    SELECT
        s.id,
        s.transaction_date,
        s.description,
        s.cad,
        -- ── Outbound type_code ──────────────────────────────────────────────
        CASE
            WHEN s.cad < 0
                 AND (   LOWER(s.description) LIKE '%amex%'
                      OR LOWER(s.description) LIKE '%american express%'
                      OR LOWER(s.description) LIKE '%mastercard%'
                      OR LOWER(s.description) LIKE '%visa%'
                     )                                          THEN 'cc_payment'
            WHEN s.cad < 0
                 AND LOWER(s.description) LIKE '%e-transfer%'  THEN 'e_transfer_out'
            WHEN s.cad < 0
                 AND (   LOWER(s.description) LIKE '%wealthsimple%'
                      OR LOWER(s.description) LIKE '%wlthsimple%'
                      OR LOWER(s.description) LIKE '%ws investments%'
                      OR (    LOWER(s.description) LIKE '%transfer%'
                           AND LOWER(s.description) NOT LIKE '%e-transfer%')
                     )                                          THEN 'account_transfer'
            WHEN s.cad < 0
                 AND LOWER(s.description) LIKE '%bill payment%' THEN 'bill_payment'
            -- ── Inbound: internal transfers first ───────────────────────────
            WHEN s.cad > 0
                 AND (   LOWER(s.description) LIKE '%wealthsimple%'
                      OR LOWER(s.description) LIKE '%wlthsimple%'
                      OR LOWER(s.description) LIKE '%ws investments%'
                      OR LOWER(s.description) LIKE '%investment%'
                     )                                          THEN 'account_transfer'
            -- ── Inbound: classification_rules keyword match ─────────────────
            WHEN s.cad > 0
                 AND r.matched_type_code IS NOT NULL             THEN r.matched_type_code
            -- ── Inbound: e-transfer catch-all ───────────────────────────────
            WHEN s.cad > 0
                 AND LOWER(s.description) LIKE '%e-transfer%'   THEN 'e_transfer_in'
            -- ── Inbound: generic fallback ────────────────────────────────────
            WHEN s.cad > 0                                       THEN 'deposit'
            ELSE 'spending'
        END                                                     AS type_code,

        -- ── Direction ───────────────────────────────────────────────────────
        CASE
            -- Internal transfer signals for outbound
            WHEN s.cad < 0
                 AND (   LOWER(s.description) LIKE '%amex%'
                      OR LOWER(s.description) LIKE '%american express%'
                      OR LOWER(s.description) LIKE '%mastercard%'
                      OR LOWER(s.description) LIKE '%visa%'
                      OR LOWER(s.description) LIKE '%wealthsimple%'
                      OR LOWER(s.description) LIKE '%wlthsimple%'
                      OR LOWER(s.description) LIKE '%ws investments%'
                     )                                          THEN 'transfer'
            WHEN s.cad < 0
                 AND LOWER(s.description) LIKE '%transfer%'
                 AND LOWER(s.description) NOT LIKE '%e-transfer%' THEN 'transfer'
            -- Internal transfer signals for inbound
            WHEN s.cad > 0
                 AND (   LOWER(s.description) LIKE '%wealthsimple%'
                      OR LOWER(s.description) LIKE '%wlthsimple%'
                      OR LOWER(s.description) LIKE '%ws investments%'
                      OR LOWER(s.description) LIKE '%investment%'
                     )                                          THEN 'transfer'
            WHEN s.cad > 0                                       THEN 'inbound'
            ELSE 'outbound'
        END                                                     AS direction

    FROM silver.rbc_chequing s
    LEFT JOIN rbc_chq_inbound_rule r ON r.source_id = s.id
)

INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('rbc-chequing' || CAST(s.id AS VARCHAR))   AS id,
    s.transaction_date                                 AS transaction_date,
    'rbc-chequing'                                     AS source,
    dm.id                                              AS merchant_id,
    c.type_code                                        AS type_code,
    s.description                                      AS description,
    ABS(s.cad)                                         AS amount,
    c.direction                                        AS direction,
    COALESCE(dm.category_id, dtc.default_category_id)  AS category_id,
    NULL                                               AS recipient_name,
    'CAD'                                              AS currency,
    s.id                                               AS source_id,
    NULL                                               AS transfer_pair_id
FROM silver.rbc_chequing s
JOIN rbc_chq_classified c ON c.id = s.id
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'rbc-chequing'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.description, '\s+', ' ', 'g'))
LEFT JOIN gold.dim_type_category dtc ON dtc.type_code = c.type_code;

-- ─────────────────────────────────────────────────────────────────────────────
-- WEALTHSIMPLE CASH
--
-- The transaction field provides a strong structural signal for most rows.
-- AFT_IN (Automated Funds Transfer inbound) can be:
--   - Payroll       → matched by classification_rules keyword
--   - Reimbursement from insurer → matched by classification_rules keyword
--   - Own-bank transfer (RBC top-up, GIC proceeds) → generic "Deposit" → account_transfer
--
-- E-transfers (E_TRFOUT, E_TRFIN, P2P_SENT) are further classified via
-- etransfer_rules name-pattern matching to catch recurring payees (rent,
-- parking) and external senders (family transfers).
--
-- Wealthsimple generic "Deposit" (AFT_IN with no keyword match) = internal
-- transfer from RBC or another own account.  direction = 'transfer'.
-- ─────────────────────────────────────────────────────────────────────────────
WITH ws_aft_in_rule AS (
    -- Resolve type_code for AFT_IN rows via classification_rules
    SELECT
        s.id                                                    AS source_id,
        (
            SELECT cr.type_code
            FROM   mappings.classification_rules cr
            WHERE  cr.source      = 'wealthsimple-cash'
            AND    cr.match_field = 'description'
            AND    LOWER(s.description) LIKE '%' || cr.keyword || '%'
            ORDER  BY cr.priority ASC, cr.id ASC
            LIMIT  1
        )                                                       AS matched_type_code
    FROM silver.wealthsimple_cash s
    WHERE s.transaction = 'AFT_IN'
),

ws_etransfer_rule AS (
    -- Resolve type_code + category for e-transfer rows via etransfer_rules
    -- name-pattern matching.  direction guard prevents inbound rules from
    -- being applied to outbound transactions and vice versa.
    SELECT
        s.id                                                    AS source_id,
        er.type_code                                            AS matched_type_code,
        er.category_id                                          AS matched_category_id,
        er.name_pattern                                         AS matched_pattern
    FROM silver.wealthsimple_cash s
    -- Derive the natural direction for the transaction type so we can guard correctly
    JOIN mappings.etransfer_rules er
        ON LOWER(s.description) LIKE '%' || er.name_pattern || '%'
        AND er.direction = CASE
            WHEN s.transaction IN ('E_TRFOUT', 'P2P_SENT') THEN 'outbound'
            WHEN s.transaction = 'E_TRFIN'                 THEN 'inbound'
            ELSE 'unknown'
        END
    WHERE s.transaction IN ('E_TRFOUT', 'E_TRFIN', 'P2P_SENT')
    QUALIFY ROW_NUMBER() OVER (PARTITION BY s.id ORDER BY LENGTH(er.name_pattern) DESC) = 1
),

ws_classified AS (
    SELECT
        s.id,
        s.date,
        s.transaction,
        s.description,
        s.amount,
        s.currency,

        -- ── type_code ───────────────────────────────────────────────────────
        CASE
            WHEN s.transaction = 'SPEND'     THEN 'spending'
            WHEN s.transaction = 'OBP_OUT'   THEN 'bill_payment'
            WHEN s.transaction = 'AFT_OUT'   THEN 'pre_auth_debit'
            WHEN s.transaction = 'INT'       THEN 'interest_earned'
            WHEN s.transaction = 'CASHBACK'  THEN 'cashback'
            WHEN s.transaction IN ('EFT', 'EFTOUT', 'TRFOUT') THEN 'account_transfer'

            -- E-transfers: etransfer_rules name match takes precedence
            WHEN s.transaction IN ('E_TRFOUT', 'P2P_SENT')
                 AND etr_rule.matched_type_code IS NOT NULL     THEN etr_rule.matched_type_code
            WHEN s.transaction IN ('E_TRFOUT', 'P2P_SENT')     THEN 'e_transfer_out'

            WHEN s.transaction = 'E_TRFIN'
                 AND etr_rule.matched_type_code IS NOT NULL     THEN etr_rule.matched_type_code
            WHEN s.transaction = 'E_TRFIN'                     THEN 'reimbursement'

            -- AFT_IN: classification_rules keyword match → payroll or insurance_reimbursement
            -- Generic "Deposit" (no keyword) = own-account transfer
            WHEN s.transaction = 'AFT_IN'
                 AND aft_rule.matched_type_code IS NOT NULL     THEN aft_rule.matched_type_code
            WHEN s.transaction = 'AFT_IN'                      THEN 'account_transfer'

            ELSE 'spending'
        END                                                     AS type_code,

        -- ── direction ───────────────────────────────────────────────────────
        CASE
            -- All internal transfers
            WHEN s.transaction IN ('AFT_IN', 'EFT', 'EFTOUT', 'TRFOUT') THEN 'transfer'
            -- AFT_IN with payroll/insurance keyword → inbound income
            WHEN s.transaction = 'AFT_IN'
                 AND aft_rule.matched_type_code IS NOT NULL     THEN 'inbound'
            -- OBP_OUT to a credit card = transfer
            WHEN s.transaction = 'OBP_OUT'
                 AND (   LOWER(s.description) LIKE '%mastercard%'
                      OR LOWER(s.description) LIKE '%visa%'
                      OR LOWER(s.description) LIKE '%amex%'
                     )                                          THEN 'transfer'
            -- Received money (interest, cashback, e-transfers in)
            WHEN s.transaction IN ('INT', 'CASHBACK', 'E_TRFIN') THEN 'inbound'
            -- E-transfers out classified as rent/parking = still outbound
            WHEN s.transaction IN ('E_TRFOUT', 'P2P_SENT')     THEN 'outbound'
            ELSE 'outbound'
        END                                                     AS direction,

        -- Carry through matched category from etransfer_rules (overrides defaults)
        etr_rule.matched_category_id                            AS etransfer_category_id

    FROM silver.wealthsimple_cash s
    LEFT JOIN ws_aft_in_rule   aft_rule ON aft_rule.source_id = s.id
    LEFT JOIN ws_etransfer_rule etr_rule ON etr_rule.source_id = s.id
)

INSERT OR IGNORE INTO gold.fact_transactions
SELECT
    SHA256('wealthsimple-cash' || CAST(s.id AS VARCHAR))        AS id,
    s.date                                                       AS transaction_date,
    'wealthsimple-cash'                                          AS source,
    dm.id                                                        AS merchant_id,
    c.type_code                                                  AS type_code,
    s.description                                                AS description,
    ABS(s.amount)                                                AS amount,
    c.direction                                                  AS direction,
    COALESCE(
        c.etransfer_category_id,   -- etransfer_rules name-match (rent, parking, external)
        etr_exact.category_id,     -- etransfer_recipients exact date+amount match
        dm.category_id,            -- merchant-level override
        dtc.default_category_id    -- type_code default
    )                                                            AS category_id,
    etr_exact.recipient_name                                     AS recipient_name,
    s.currency                                                   AS currency,
    s.id                                                         AS source_id,
    NULL                                                         AS transfer_pair_id
FROM silver.wealthsimple_cash s
JOIN ws_classified c ON c.id = s.id
LEFT JOIN gold.dim_merchant dm
    ON dm.source = 'wealthsimple-cash'
    AND TRIM(dm.merchant) = TRIM(REGEXP_REPLACE(s.description, '\s+', ' ', 'g'))
LEFT JOIN mappings.etransfer_recipients etr_exact
    ON s.date = etr_exact.date
    AND ABS(s.amount) = ABS(etr_exact.amount)
    AND s.transaction IN ('E_TRFOUT', 'E_TRFIN', 'P2P_SENT')
LEFT JOIN gold.dim_type_category dtc ON dtc.type_code = c.type_code;
