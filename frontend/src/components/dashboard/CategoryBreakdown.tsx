import { motion } from 'framer-motion';
import type { CategorySpend } from '../../types';

interface CategoryBreakdownProps {
    data: CategorySpend[];
    title: string;
    subtitle?: string;
}

const CATEGORY_COLORS: Record<string, string> = {
    'Rent': '#818cf8',
    'Utilities': '#a78bfa',
    'Insurance': '#c084fc',
    'Subscriptions': '#e879f9',
    'Phone': '#f0abfc',
    'Internet': '#d946ef',
    'Groceries': '#34d399',
    'Dining': '#6ee7b7',
    'Coffee': '#a7f3d0',
    'Desserts': '#86efac',
    'Exercise': '#4ade80',
    'Personal Trainer': '#22c55e',
    'Therapy': '#16a34a',
    'Hobbies': '#fbbf24',
    'Travel': '#f59e0b',
    'Dental': '#fcd34d',
    'Health': '#fde68a',
    'Shopping': '#60a5fa',
    'Transport': '#93c5fd',
};

function getFallbackColor(index: number): string {
    const palette = [
        '#60a5fa','#34d399','#fbbf24','#f87171','#a78bfa',
        '#4ade80','#fb923c','#38bdf8','#e879f9','#a3e635',
    ];
    return palette[index % palette.length];
}

function formatCAD(val: number): string {
    return new Intl.NumberFormat('en-CA', {
        style: 'currency',
        currency: 'CAD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(val);
}

export function CategoryBreakdown({ data, title, subtitle }: CategoryBreakdownProps) {
    if (!data.length) return null;

    const max = Math.max(...data.map(d => d.total));

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
            className="rounded-xl border border-slate-700/50 bg-slate-800/60 backdrop-blur-sm p-5"
        >
            <div className="mb-5">
                <h3 className="text-sm font-semibold tracking-widest uppercase text-slate-400">{title}</h3>
                {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
            </div>

            <div className="space-y-3">
                {data.map((item, i) => {
                    const pct = (item.total / max) * 100;
                    const color = CATEGORY_COLORS[item.category] ?? getFallbackColor(i);
                    const label = item.subcategory
                        ? `${item.category} · ${item.subcategory}`
                        : item.category;

                    return (
                        <motion.div
                            key={`${item.category}-${item.subcategory}`}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.3, delay: 0.3 + i * 0.04 }}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-xs text-slate-300 font-medium truncate max-w-[55%]">{label}</span>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-slate-500">{item.transaction_count} txn</span>
                                    <span className="text-xs font-semibold text-slate-200 tabular-nums w-20 text-right">
                                        {formatCAD(item.total)}
                                    </span>
                                </div>
                            </div>
                            <div className="h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${pct}%` }}
                                    transition={{ duration: 0.5, delay: 0.35 + i * 0.04, ease: 'easeOut' }}
                                    className="h-full rounded-full"
                                    style={{ backgroundColor: color }}
                                />
                            </div>
                        </motion.div>
                    );
                })}
            </div>
        </motion.div>
    );
}
