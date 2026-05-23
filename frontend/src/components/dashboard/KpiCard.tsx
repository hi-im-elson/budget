import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface KpiCardProps {
    label: string;
    value: number;
    previousValue?: number;
    format?: 'currency' | 'number';
    variant?: 'default' | 'positive' | 'negative' | 'neutral';
    subtitle?: string;
    index?: number;
}

function formatCurrency(val: number): string {
    return new Intl.NumberFormat('en-CA', {
        style: 'currency',
        currency: 'CAD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(val);
}

export function KpiCard({
    label,
    value,
    previousValue,
    format = 'currency',
    variant = 'default',
    subtitle,
    index = 0,
}: KpiCardProps) {
    const displayValue = format === 'currency' ? formatCurrency(value) : value.toLocaleString();

    let momDelta: number | null = null;
    let momPct: number | null = null;
    if (previousValue != null && previousValue !== 0) {
        momDelta = value - previousValue;
        momPct = (momDelta / Math.abs(previousValue)) * 100;
    }

    const accentColor =
        variant === 'positive' ? 'text-emerald-400'
        : variant === 'negative' ? 'text-rose-400'
        : variant === 'neutral' ? 'text-sky-400'
        : 'text-blue-400';

    const borderColor =
        variant === 'positive' ? 'border-emerald-500/20'
        : variant === 'negative' ? 'border-rose-500/20'
        : variant === 'neutral' ? 'border-sky-500/20'
        : 'border-slate-700/50';

    const glowColor =
        variant === 'positive' ? 'from-emerald-500/5'
        : variant === 'negative' ? 'from-rose-500/5'
        : variant === 'neutral' ? 'from-sky-500/5'
        : 'from-blue-500/5';

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: index * 0.07, ease: 'easeOut' }}
            className={`relative rounded-xl border ${borderColor} bg-slate-800/60 backdrop-blur-sm overflow-hidden p-5`}
        >
            {/* subtle glow */}
            <div className={`absolute inset-0 bg-gradient-to-br ${glowColor} to-transparent pointer-events-none`} />

            <div className="relative">
                <p className="text-xs font-semibold tracking-widest uppercase text-slate-400 mb-3">{label}</p>
                <p className={`text-3xl font-bold tracking-tight ${accentColor} tabular-nums`}>
                    {displayValue}
                </p>

                <div className="mt-2 flex items-center gap-2 min-h-[20px]">
                    {momPct != null && momDelta != null ? (
                        <>
                            {momPct > 1 ? (
                                <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
                            ) : momPct < -1 ? (
                                <TrendingDown className="w-3.5 h-3.5 text-slate-400" />
                            ) : (
                                <Minus className="w-3.5 h-3.5 text-slate-400" />
                            )}
                            <span className="text-xs text-slate-400">
                                {momPct > 0 ? '+' : ''}{momPct.toFixed(1)}% vs prior month
                            </span>
                        </>
                    ) : subtitle ? (
                        <span className="text-xs text-slate-500">{subtitle}</span>
                    ) : null}
                </div>
            </div>
        </motion.div>
    );
}
