import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { QueryResult } from '../types';

interface ResultsTableProps {
    result: QueryResult | null;
    error: string | null;
}

const PAGE_SIZE = 100;

export function ResultsTable({ result, error }: ResultsTableProps) {
    const [page, setPage] = useState(0);

    // Reset page when results change
    useEffect(() => {
        setPage(0);
    }, [result]);

    if (error) {
        return (
            <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/10 text-red-400">
                <strong className="font-semibold block mb-1 text-red-300">Error executing query:</strong>
                <pre className="font-mono text-xs whitespace-pre-wrap">{error}</pre>
            </div>
        );
    }

    if (!result) {
        return (
            <div className="flex flex-col border border-slate-700/50 bg-slate-800/20 rounded-xl h-48 items-center justify-center text-slate-500">
                <p>No results yet. Run a query to see data.</p>
            </div>
        );
    }

    const { columns, data } = result;

    if (data.length === 0) {
        return (
            <div className="p-4 rounded-xl border border-slate-700/50 bg-slate-800/50 text-slate-400 text-center">
                Query completed successfully but returned 0 rows.
            </div>
        );
    }

    const totalPages = Math.ceil(data.length / PAGE_SIZE);
    const startIdx = page * PAGE_SIZE;
    const pageData = data.slice(startIdx, startIdx + PAGE_SIZE);

    return (
        <div className="flex flex-col border border-slate-700/50 rounded-xl bg-slate-800/50 overflow-hidden shadow-lg transform transition-all">
            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm whitespace-nowrap">
                    <thead className="bg-slate-800/80 border-b border-slate-700/50 text-slate-300">
                        <tr>
                            {columns.map((col, i) => (
                                <th key={col + i} className="px-6 py-3 font-semibold tracking-wider">{col}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/30">
                        {pageData.map((row, i) => (
                            <tr key={i} className="hover:bg-slate-700/30 transition-colors">
                                {columns.map((col, j) => (
                                    <td key={col + j} className="px-6 py-3 text-slate-300 font-mono text-xs">
                                        {row[col] !== null ? String(row[col]) : <span className="text-slate-500 font-sans italic">null</span>}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-3 border-t border-slate-700/50 bg-slate-800/50">
                    <div className="text-sm text-slate-400">
                        Showing <span className="font-medium text-slate-200">{startIdx + 1}</span> to <span className="font-medium text-slate-200">{Math.min(startIdx + PAGE_SIZE, data.length)}</span> of <span className="font-medium text-slate-200">{data.length}</span> results
                    </div>
                    <div className="flex space-x-2">
                        <button
                            onClick={() => setPage(p => Math.max(0, p - 1))}
                            disabled={page === 0}
                            className="p-1.5 rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                            disabled={page === totalPages - 1}
                            className="p-1.5 rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
