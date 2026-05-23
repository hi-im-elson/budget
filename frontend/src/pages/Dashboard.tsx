import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { RefreshCcw, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { KpiCard } from '../components/dashboard/KpiCard';
import { SpendChart } from '../components/dashboard/SpendChart';
import { CategoryBreakdown } from '../components/dashboard/CategoryBreakdown';
import type { MonthlyOverview, CategorySpend } from '../types';

const API_URL = 'http://localhost:8000/api/query';

async function runQuery<T>(query: string): Promise<T[]> {
    const { data } = await axios.post(API_URL, { query });
    return data.data as T[];
}

// ─── SQL queries ──────────────────────────────────────────────────────────────

const MONTHLY_OVERVIEW_SQL = `
SELECT
    strftime(date_trunc('month', transaction_date), '%Y-%m')       AS month,
    strftime(date_trunc('month', transaction_date), '%b %Y')       AS month_label,
    SUM(CASE WHEN direction = 'inbound'  AND type_code NOT IN ('cashback','refund')
             THEN amount ELSE 0 END)                               AS income,
    SUM(CASE WHEN direction = 'outbound' AND type_code NOT IN ('cc_payment','account_transfer','pre_auth_debit')
             THEN amount ELSE 0 END)                               AS spending
FROM gold.fact_transactions
WHERE transaction_date >= date_trunc('month', current_date) - INTERVAL 6 MONTH
  AND direction != 'transfer'
GROUP BY 1, 2
ORDER BY 1 ASC;
`;

const CURRENT_MONTH_INCOME_SQL = `
SELECT
    COALESCE(SUM(amount), 0) AS income
FROM gold.fact_transactions
WHERE direction = 'inbound'
  AND type_code NOT IN ('cashback', 'refund')
  AND transaction_date >= date_trunc('month', current_date)
  AND transaction_date <  date_trunc('month', current_date) + INTERVAL 1 MONTH;
`;

const PRIOR_MONTH_INCOME_SQL = `
SELECT
    COALESCE(SUM(amount), 0) AS income
FROM gold.fact_transactions
WHERE direction = 'inbound'
  AND type_code NOT IN ('cashback', 'refund')
  AND transaction_date >= date_trunc('month', current_date) - INTERVAL 1 MONTH
  AND transaction_date <  date_trunc('month', current_date);
`;

const CURRENT_MONTH_SPEND_SQL = `
SELECT
    COALESCE(SUM(amount), 0) AS spending
FROM gold.fact_transactions
WHERE direction = 'outbound'
  AND type_code NOT IN ('cc_payment', 'account_transfer', 'pre_auth_debit')
  AND transaction_date >= date_trunc('month', current_date)
  AND transaction_date <  date_trunc('month', current_date) + INTERVAL 1 MONTH;
`;

const PRIOR_MONTH_SPEND_SQL = `
SELECT
    COALESCE(SUM(amount), 0) AS spending
FROM gold.fact_transactions
WHERE direction = 'outbound'
  AND type_code NOT IN ('cc_payment', 'account_transfer', 'pre_auth_debit')
  AND transaction_date >= date_trunc('month', current_date) - INTERVAL 1 MONTH
  AND transaction_date <  date_trunc('month', current_date);
`;

// Recurring: subscriptions + merchants flagged is_subscription, last 3 months
const RECURRING_SPEND_SQL = `
SELECT
    COALESCE(dc.category, 'Uncategorised') AS category,
    NULL                                   AS subcategory,
    SUM(ft.amount) / 3.0                   AS total,
    COUNT(*)                               AS transaction_count
FROM gold.fact_transactions ft
LEFT JOIN gold.dim_merchant dm  ON dm.id = ft.merchant_id
LEFT JOIN gold.dim_category  dc ON dc.id = ft.category_id
WHERE ft.direction  = 'outbound'
  AND ft.type_code NOT IN ('cc_payment', 'account_transfer', 'pre_auth_debit')
  AND (dm.is_subscription = TRUE OR ft.type_code IN ('bill_payment'))
  AND ft.transaction_date >= date_trunc('month', current_date) - INTERVAL 3 MONTH
  AND ft.transaction_date <  date_trunc('month', current_date)
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 15;
`;

// Discretionary: non-recurring outbound, categorised, last full month
const DISCRETIONARY_SPEND_SQL = `
SELECT
    COALESCE(dc.category,    'Uncategorised') AS category,
    dc.subcategory                            AS subcategory,
    SUM(ft.amount)                            AS total,
    COUNT(*)                                  AS transaction_count
FROM gold.fact_transactions ft
LEFT JOIN gold.dim_merchant dm  ON dm.id  = ft.merchant_id
LEFT JOIN gold.dim_category  dc ON dc.id  = ft.category_id
WHERE ft.direction  = 'outbound'
  AND ft.type_code NOT IN ('cc_payment', 'account_transfer', 'pre_auth_debit', 'bill_payment')
  AND COALESCE(dm.is_subscription, FALSE) = FALSE
  AND ft.transaction_date >= date_trunc('month', current_date) - INTERVAL 1 MONTH
  AND ft.transaction_date <  date_trunc('month', current_date)
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 15;
`;

// ─── Component ────────────────────────────────────────────────────────────────

interface DashboardState {
    monthly: MonthlyOverview[];
    currentIncome: number;
    priorIncome: number;
    currentSpend: number;
    priorSpend: number;
    recurring: CategorySpend[];
    discretionary: CategorySpend[];
}

const EMPTY_STATE: DashboardState = {
    monthly: [],
    currentIncome: 0,
    priorIncome: 0,
    currentSpend: 0,
    priorSpend: 0,
    recurring: [],
    discretionary: [],
};

export function Dashboard() {
    const [state, setState] = useState<DashboardState>(EMPTY_STATE);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [
                monthlyRaw,
                currentIncomeRaw,
                priorIncomeRaw,
                currentSpendRaw,
                priorSpendRaw,
                recurringRaw,
                discretionaryRaw,
            ] = await Promise.all([
                runQuery<any>(MONTHLY_OVERVIEW_SQL),
                runQuery<any>(CURRENT_MONTH_INCOME_SQL),
                runQuery<any>(PRIOR_MONTH_INCOME_SQL),
                runQuery<any>(CURRENT_MONTH_SPEND_SQL),
                runQuery<any>(PRIOR_MONTH_SPEND_SQL),
                runQuery<any>(RECURRING_SPEND_SQL),
                runQuery<any>(DISCRETIONARY_SPEND_SQL),
            ]);

            const monthly: MonthlyOverview[] = monthlyRaw.map((r: any) => ({
                month: r.month,
                month_label: r.month_label,
                income: parseFloat(r.income) || 0,
                spending: parseFloat(r.spending) || 0,
                net: (parseFloat(r.income) || 0) - (parseFloat(r.spending) || 0),
            }));

            setState({
                monthly,
                currentIncome: parseFloat(currentIncomeRaw[0]?.income) || 0,
                priorIncome: parseFloat(priorIncomeRaw[0]?.income) || 0,
                currentSpend: parseFloat(currentSpendRaw[0]?.spending) || 0,
                priorSpend: parseFloat(priorSpendRaw[0]?.spending) || 0,
                recurring: recurringRaw.map((r: any) => ({
                    category: r.category,
                    subcategory: r.subcategory ?? null,
                    total: parseFloat(r.total) || 0,
                    transaction_count: parseInt(r.transaction_count) || 0,
                })),
                discretionary: discretionaryRaw.map((r: any) => ({
                    category: r.category,
                    subcategory: r.subcategory ?? null,
                    total: parseFloat(r.total) || 0,
                    transaction_count: parseInt(r.transaction_count) || 0,
                })),
            });
        } catch (e: any) {
            console.error(e);
            setError(e.response?.data?.detail || e.message || 'Failed to load dashboard data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const currentNet = state.currentIncome - state.currentSpend;
    const priorNet   = state.priorIncome  - state.priorSpend;

    const currentMonthLabel = new Date().toLocaleString('en-CA', { month: 'long', year: 'numeric' });

    return (
        <main className="flex-1 flex flex-col h-full overflow-y-auto w-full">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/20 via-slate-900 to-slate-900 -z-10 pointer-events-none" />

            <div className="max-w-7xl mx-auto w-full p-8 md:p-12 space-y-8 pb-32">

                {/* Header */}
                <header className="flex items-start justify-between">
                    <div>
                        <h2 className="text-3xl font-bold tracking-tight text-white mb-2">Dashboard</h2>
                        <p className="text-slate-400">{currentMonthLabel} — financial overview</p>
                    </div>
                    <button
                        onClick={fetchAll}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700/50 text-slate-300 text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                </header>

                {/* Error state */}
                {error && (
                    <div className="flex items-start gap-3 p-4 rounded-xl bg-rose-950/30 border border-rose-900/50 text-rose-300 text-sm">
                        <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-400" />
                        <div>
                            <p className="font-semibold mb-1">Failed to load dashboard</p>
                            <p className="text-rose-400/80 text-xs font-mono">{error}</p>
                        </div>
                    </div>
                )}

                {/* KPI row */}
                {loading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        {[0,1,2].map(i => (
                            <div key={i} className="rounded-xl border border-slate-700/50 bg-slate-800/60 h-28 animate-pulse" />
                        ))}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <KpiCard
                            label="Income this month"
                            value={state.currentIncome}
                            previousValue={state.priorIncome}
                            variant="positive"
                            index={0}
                        />
                        <KpiCard
                            label="Spending this month"
                            value={state.currentSpend}
                            previousValue={state.priorSpend}
                            variant="negative"
                            index={1}
                        />
                        <KpiCard
                            label="Net surplus"
                            value={currentNet}
                            previousValue={priorNet}
                            variant={currentNet >= 0 ? 'neutral' : 'negative'}
                            index={2}
                        />
                    </div>
                )}

                {/* Monthly chart */}
                {!loading && state.monthly.length > 0 && (
                    <SpendChart data={state.monthly} />
                )}

                {/* Category breakdowns — side by side on wide screens */}
                {!loading && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <CategoryBreakdown
                            data={state.recurring}
                            title="Recurring Committed Costs"
                            subtitle="Avg. monthly over last 3 months (subscriptions & bills)"
                        />
                        <CategoryBreakdown
                            data={state.discretionary}
                            title="Discretionary Spending"
                            subtitle="Last full month — variable, non-subscription expenses"
                        />
                    </div>
                )}

            </div>
        </main>
    );
}
