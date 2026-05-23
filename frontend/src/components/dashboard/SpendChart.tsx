import { motion } from 'framer-motion';
import {
    ComposedChart,
    Bar,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    ReferenceLine,
} from 'recharts';
import type { MonthlyOverview } from '../../types';

interface SpendChartProps {
    data: MonthlyOverview[];
}

function formatCAD(val: number): string {
    if (Math.abs(val) >= 1000) {
        return `$${(val / 1000).toFixed(1)}k`;
    }
    return `$${val.toFixed(0)}`;
}

const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;

    const income = payload.find((p: any) => p.dataKey === 'income')?.value ?? 0;
    const spending = payload.find((p: any) => p.dataKey === 'spending')?.value ?? 0;
    const net = payload.find((p: any) => p.dataKey === 'net')?.value ?? 0;

    return (
        <div className="bg-slate-800 border border-slate-700/60 rounded-xl p-3 shadow-xl text-xs space-y-1.5 min-w-[160px]">
            <p className="font-semibold text-slate-200 mb-2">{label}</p>
            <div className="flex justify-between gap-4">
                <span className="text-emerald-400">Income</span>
                <span className="text-slate-200 font-medium tabular-nums">
                    {new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(income)}
                </span>
            </div>
            <div className="flex justify-between gap-4">
                <span className="text-rose-400">Spending</span>
                <span className="text-slate-200 font-medium tabular-nums">
                    {new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(spending)}
                </span>
            </div>
            <div className="border-t border-slate-700/50 pt-1.5 flex justify-between gap-4">
                <span className={net >= 0 ? 'text-sky-400' : 'text-amber-400'}>Net</span>
                <span className={`font-bold tabular-nums ${net >= 0 ? 'text-sky-300' : 'text-amber-300'}`}>
                    {net >= 0 ? '+' : ''}{new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(net)}
                </span>
            </div>
        </div>
    );
};

export function SpendChart({ data }: SpendChartProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.25 }}
            className="rounded-xl border border-slate-700/50 bg-slate-800/60 backdrop-blur-sm p-5"
        >
            <div className="mb-5">
                <h3 className="text-sm font-semibold tracking-widest uppercase text-slate-400">
                    Monthly Cash Flow
                </h3>
                <p className="text-xs text-slate-500 mt-1">Income vs spending, with net surplus line</p>
            </div>

            <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis
                        dataKey="month_label"
                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                    />
                    <YAxis
                        tickFormatter={formatCAD}
                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        width={48}
                    />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(148,163,184,0.05)' }} />
                    <Legend
                        wrapperStyle={{ fontSize: 11, paddingTop: 12 }}
                        formatter={(value) => (
                            <span style={{ color: '#94a3b8', textTransform: 'capitalize' }}>{value}</span>
                        )}
                    />
                    <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
                    <Bar dataKey="income" name="Income" fill="#34d399" radius={[3, 3, 0, 0]} maxBarSize={36} opacity={0.85} />
                    <Bar dataKey="spending" name="Spending" fill="#fb7185" radius={[3, 3, 0, 0]} maxBarSize={36} opacity={0.85} />
                    <Line
                        dataKey="net"
                        name="Net"
                        type="monotone"
                        stroke="#38bdf8"
                        strokeWidth={2}
                        dot={{ fill: '#38bdf8', r: 3, strokeWidth: 0 }}
                        activeDot={{ r: 5, strokeWidth: 0 }}
                    />
                </ComposedChart>
            </ResponsiveContainer>
        </motion.div>
    );
}
