import type { SavedQuery } from '../types';

export const DEFAULT_QUERIES: SavedQuery[] = [
    {
        id: 'default-1',
        title: "Last month's purchases",
        query: `
SELECT *
FROM silver.amex_cobalt
WHERE date >= date_trunc('month', current_date - INTERVAL 1 MONTH)
  AND date < date_trunc('month', current_date)
ORDER BY date DESC;
`
    },
    {
        id: 'default-2',
        title: "Monthly spend summary",
        query: `
SELECT 
  STRFTIME(DATE(year(date)||'-'||month(date)||'-'||01), '%Y %B') AS transaction_month,
  COUNT(id) AS transaction_count,
  SUM(amount) AS total_spend
FROM silver.amex_cobalt
WHERE 
    LOWER(description) NOT LIKE 'payment received%'
GROUP BY DATE(year(date)||'-'||month(date)||'-'||01)
ORDER BY DATE(year(date)||'-'||month(date)||'-'||01) DESC;
`
    },
    {
        id: 'default-3',
        title: "Search by merchant",
        query: `
SELECT *
FROM silver.amex_cobalt
WHERE lower(merchant) LIKE '%coffee%'
ORDER BY date DESC;
`
    },
    {
        id: 'audit-income',
        title: "Audit: all inbound transactions",
        query: `
-- Shows every inbound transaction grouped by source, type, and description.
-- Use this to spot self-transfers wrongly counted as income.
-- Rows with a transfer_pair_id are already reconciled and excluded from P&L.
SELECT
    source,
    type_code,
    description,
    transfer_pair_id IS NOT NULL   AS is_reconciled_transfer,
    SUM(amount)                    AS total,
    COUNT(*)                       AS txn_count,
    MIN(transaction_date)          AS first_seen,
    MAX(transaction_date)          AS last_seen
FROM gold.fact_transactions
WHERE direction = 'inbound'
GROUP BY source, type_code, description, is_reconciled_transfer
ORDER BY source, is_reconciled_transfer, total DESC;
`
    },
    {
        id: 'audit-transfer-pairs',
        title: "Audit: matched transfer pairs",
        query: `
-- Inspect every reconciled transfer pair. 
-- confidence = 'high'   → description explicitly named the counterpart account.
-- confidence = 'medium' → matched on amount + date only; verify manually.
SELECT
    pair_id,
    outbound_source,
    inbound_source,
    amount,
    outbound_date,
    inbound_date,
    confidence,
    match_reason,
    o.description  AS outbound_desc,
    i.description  AS inbound_desc
FROM gold.transfer_pairs tp
JOIN gold.fact_transactions o ON o.id = tp.outbound_id
JOIN gold.fact_transactions i ON i.id = tp.inbound_id
ORDER BY confidence, outbound_date DESC;
`
    },
    {
        id: 'audit-unmatched-deposits',
        title: "Audit: unmatched deposits (possible missed transfers)",
        query: `
-- Deposits and inbound AFT_IN / EFT rows with no matched transfer pair.
-- Review these to ensure no self-transfers are leaking into income.
SELECT
    source,
    type_code,
    transaction_date,
    amount,
    description
FROM gold.fact_transactions
WHERE direction  = 'inbound'
  AND type_code IN ('deposit', 'e_transfer_in')
  AND transfer_pair_id IS NULL
ORDER BY amount DESC, transaction_date DESC;
`
    },
];
