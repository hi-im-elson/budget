export interface QueryResult {
    columns: string[];
    data: Record<string, any>[];
}

export interface SavedQuery {
    id: string;
    title: string;
    query: string;
}

// Dashboard types
export interface MonthlyOverview {
    month: string;          // e.g. "2025-04"
    month_label: string;    // e.g. "Apr 2025"
    income: number;
    spending: number;
    net: number;
}

export interface CategorySpend {
    category: string;
    subcategory: string | null;
    total: number;
    transaction_count: number;
}

export interface RecurringItem {
    merchant: string;
    category: string;
    avg_monthly: number;
    months_seen: number;
}

export type DashboardView = 'dashboard' | 'query';
