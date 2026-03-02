import { useState } from 'react';
import { Bookmark, ChevronDown, ChevronRight, Play, Trash2, Edit } from 'lucide-react';
import type { SavedQuery } from '../types';
import { motion, AnimatePresence } from 'framer-motion';

interface SavedQueriesProps {
    queries: SavedQuery[];
    onLoad: (query: string) => void;
    onRun: (query: string) => void;
    onDelete: (id: string) => void;
    onRestoreDefaults: () => void;
}

export function SavedQueries({ queries, onLoad, onRun, onDelete, onRestoreDefaults }: SavedQueriesProps) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="border border-slate-700/50 rounded-xl bg-slate-800/30 overflow-hidden shadow-sm">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-between w-full px-5 py-4 bg-slate-800/50 hover:bg-slate-800 transition-colors focus:outline-none"
            >
                <div className="flex items-center text-slate-200 font-medium">
                    <Bookmark className="w-5 h-5 mr-3 text-emerald-400" />
                    Saved Queries {queries.length > 0 && <span className="ml-2 bg-slate-700 text-slate-300 text-xs py-0.5 px-2 rounded-full">{queries.length}</span>}
                </div>
                {isOpen ? <ChevronDown className="w-5 h-5 text-slate-400" /> : <ChevronRight className="w-5 h-5 text-slate-400" />}
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="p-3 border-t border-slate-700/50 max-h-72 overflow-y-auto space-y-2">
                            {queries.length === 0 ? (
                                <div className="text-center py-6 text-sm text-slate-500">No saved queries yet. Save a query to see it here!</div>
                            ) : (
                                queries.map((q) => (
                                    <div key={q.id} className="w-full flex flex-col p-3 rounded-lg bg-slate-900/40 border border-slate-700 hover:border-slate-500 transition-all group">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="font-semibold text-sm text-slate-200 pr-4">
                                                {q.title}
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between mt-auto">
                                            <span className="font-mono text-xs text-slate-400 line-clamp-1 italic max-w-[70%]">
                                                {q.query}
                                            </span>
                                            <div className="flex items-center space-x-2">
                                                <button
                                                    onClick={() => onLoad(q.query)}
                                                    className="p-1.5 text-slate-400 hover:text-blue-400 hover:bg-blue-400/10 rounded transition-colors"
                                                    title="Load into Editor"
                                                >
                                                    <Edit className="w-3.5 h-3.5" />
                                                </button>
                                                <button
                                                    onClick={() => onRun(q.query)}
                                                    className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-emerald-400/10 rounded transition-colors"
                                                    title="Run Query"
                                                >
                                                    <Play className="w-3.5 h-3.5" />
                                                </button>
                                                <button
                                                    onClick={() => onDelete(q.id)}
                                                    className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-400/10 rounded transition-colors"
                                                    title="Delete Query"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                            <div className="pt-2 mt-2 border-t border-slate-700/50 flex justify-end">
                                <button
                                    onClick={onRestoreDefaults}
                                    className="text-xs text-slate-400 hover:text-slate-200 transition-colors focus:outline-none"
                                >
                                    Restore Defaults
                                </button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
