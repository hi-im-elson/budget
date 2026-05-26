CREATE OR REPLACE TABLE gold.bridge_transfer_pairs (
    pair_id         VARCHAR       NOT NULL PRIMARY KEY,
    outbound_id     VARCHAR       NOT NULL,
    inbound_id      VARCHAR       NOT NULL,
    outbound_source VARCHAR       NOT NULL,
    inbound_source  VARCHAR       NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    outbound_date   DATE          NOT NULL,
    inbound_date    DATE          NOT NULL,
    confidence      VARCHAR(10)   NOT NULL,
    match_reason    VARCHAR(255)  NOT NULL
);

DELETE FROM gold.bridge_transfer_pairs;

WITH transfer_eligible AS (
    SELECT
        id,
        source,
        transaction_date,
        amount,
        direction,
        type_code,
        description,
        CASE
            WHEN direction IN ('transfer') THEN 'both'
            WHEN direction = 'outbound'
                 AND type_code IN ('cc_payment','account_transfer','bill_payment',
                                   'e_transfer_out','pre_auth_debit','p2p')
                                          THEN 'outbound'
            WHEN direction = 'inbound'
                 AND type_code IN ('deposit','e_transfer_in','payroll',
                                   'cc_payment','account_transfer')
                                          THEN 'inbound'
            ELSE NULL
        END AS leg_role
    FROM gold.fact_transactions
),

outbound_legs AS (
    SELECT * FROM transfer_eligible
    WHERE leg_role IN ('outbound', 'both')
),

inbound_legs AS (
    SELECT * FROM transfer_eligible
    WHERE leg_role IN ('inbound', 'both')
),

candidate_pairs AS (
    SELECT
        o.id                AS outbound_id,
        o.source            AS outbound_source,
        o.transaction_date  AS outbound_date,
        o.description       AS outbound_desc,
        o.type_code         AS outbound_type,

        i.id                AS inbound_id,
        i.source            AS inbound_source,
        i.transaction_date  AS inbound_date,
        i.description       AS inbound_desc,
        i.type_code         AS inbound_type,

        o.amount            AS amount,

        ABS(DATEDIFF('day', o.transaction_date, i.transaction_date)) AS day_gap,

        CASE WHEN
            LOWER(o.description) LIKE '%wealthsimple%'
         OR LOWER(o.description) LIKE '%wlthsimple%'
         OR LOWER(o.description) LIKE '%ws investments%'
         OR LOWER(o.description) LIKE '%amex%'
         OR LOWER(o.description) LIKE '%american express%'
         OR LOWER(o.description) LIKE '%mastercard%'
         OR LOWER(o.description) LIKE '%visa%'
         OR LOWER(o.description) LIKE '%rbc%'
         OR LOWER(o.description) LIKE '%royal bank%'
         OR LOWER(o.description) LIKE '%transfer%'
        THEN TRUE ELSE FALSE END                AS outbound_names_dest,

        CASE WHEN
            LOWER(i.description) LIKE '%wealthsimple%'
         OR LOWER(i.description) LIKE '%wlthsimple%'
         OR LOWER(i.description) LIKE '%ws investments%'
         OR LOWER(i.description) LIKE '%rbc%'
         OR LOWER(i.description) LIKE '%royal bank%'
         OR LOWER(i.description) LIKE '%payment received%'
         OR LOWER(i.description) LIKE '%transfer%'
         OR i.type_code IN ('cc_payment', 'account_transfer')
        THEN TRUE ELSE FALSE END                AS inbound_names_source

    FROM outbound_legs o
    JOIN inbound_legs i
        ON  o.source            != i.source
        AND o.amount             = i.amount
        AND ABS(DATEDIFF('day', o.transaction_date, i.transaction_date)) <= 1
),

ranked_pairs AS (
    SELECT
        *,
        CASE
            WHEN outbound_names_dest OR inbound_names_source THEN 'high'
            ELSE 'medium'
        END AS confidence,

        CASE
            WHEN outbound_names_dest AND inbound_names_source
                THEN 'Both legs reference counterpart account'
            WHEN outbound_names_dest
                THEN 'Outbound description references destination account'
            WHEN inbound_names_source
                THEN 'Inbound description or type_code references source account'
            ELSE 'Amount + date match across sources. No explicit account reference'
        END AS match_reason,

        ROW_NUMBER() OVER (
            PARTITION BY inbound_id
            ORDER BY
                (CASE WHEN outbound_names_dest OR inbound_names_source THEN 0 ELSE 1 END),
                day_gap,
                outbound_source
        ) AS rank_by_inbound,

        ROW_NUMBER() OVER (
            PARTITION BY outbound_id
            ORDER BY
                (CASE WHEN outbound_names_dest OR inbound_names_source THEN 0 ELSE 1 END),
                day_gap,
                inbound_source
        ) AS rank_by_outbound
    FROM candidate_pairs
)

INSERT OR IGNORE INTO gold.bridge_transfer_pairs
SELECT
    SHA256(outbound_id || inbound_id) AS pair_id,
    outbound_id,
    inbound_id,
    outbound_source,
    inbound_source,
    amount,
    outbound_date,
    inbound_date,
    confidence,
    match_reason
FROM ranked_pairs
WHERE rank_by_inbound  = 1
  AND rank_by_outbound = 1;

UPDATE gold.fact_transactions
SET transfer_pair_id = tp.pair_id
FROM gold.bridge_transfer_pairs tp
WHERE gold.fact_transactions.id IN (tp.outbound_id, tp.inbound_id);
