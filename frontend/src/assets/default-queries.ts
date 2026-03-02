import type { SavedQuery } from '../types';

export const DEFAULT_QUERIES: SavedQuery[] = [
    {
        id: 'default-1',
        title: "Last month's purchases",
        query: `
SELECT *
FROM silver.amex
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
FROM silver.amex
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
FROM silver.amex
WHERE lower(merchant) LIKE '%coffee%'
ORDER BY date DESC;
`
    }
];
