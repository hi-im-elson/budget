import { useState, useEffect } from 'react';
import axios from 'axios';
import { RefreshCcw, AlertTriangle, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';

const API_URL = 'http://localhost:8000/api';

interface RefreshPipelineProps {
    onRefreshComplete?: () => void;
}

export function RefreshPipeline({ onRefreshComplete }: RefreshPipelineProps) {
    const [isConfirming, setIsConfirming] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const fetchLastRefresh = async () => {
        try {
            const { data } = await axios.get(`${API_URL}/last-refresh`);
            if (data.last_refresh) {
                setLastRefresh(data.last_refresh);
            }
        } catch (e) {
            console.error("Failed to fetch last refresh", e);
        }
    };

    useEffect(() => {
        fetchLastRefresh();
        // Refresh the relative time every minute
        const interval = setInterval(() => {
            setLastRefresh(prev => prev); // force re-render for date-fns
        }, 60000);
        return () => clearInterval(interval);
    }, []);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        setError(null);
        try {
            await axios.post(`${API_URL}/refresh`);
            await fetchLastRefresh();
            if (onRefreshComplete) onRefreshComplete();
            setIsConfirming(false);
        } catch (e: any) {
            console.error(e);
            setError(e.response?.data?.detail || e.message || "An error occurred during refresh");
        } finally {
            setIsRefreshing(false);
        }
    };

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between text-xs text-slate-400 px-1 py-0.5">
                <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Last Refresh:</span>
                </div>
                <span className="font-medium text-slate-300">
                    {lastRefresh ? formatDistanceToNow(new Date(lastRefresh), { addSuffix: true }) : 'Never'}
                </span>
            </div>

            <AnimatePresence mode="wait">
                {!isConfirming ? (
                    <motion.button
                        key="refresh-btn"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        onClick={() => setIsConfirming(true)}
                        className="flex items-center justify-center w-full px-4 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 text-slate-200 font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500/50"
                    >
                        <RefreshCcw className="w-4 h-4 mr-2" />
                        Refresh Pipeline
                    </motion.button>
                ) : (
                    <motion.div
                        key="confirm-box"
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        className="flex flex-col gap-3 p-4 bg-red-950/30 border border-red-900/50 rounded-xl"
                    >
                        <div className="flex gap-3 text-red-200 text-sm">
                            <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
                            <p>Are you sure you want to completely reset and reload all database tables? This action cannot be undone.</p>
                        </div>

                        {error && (
                            <div className="text-xs text-red-400 bg-red-950/50 p-2 rounded border border-red-900/50">
                                {error}
                            </div>
                        )}

                        <div className="flex gap-2 mt-1">
                            <button
                                onClick={() => {
                                    setIsConfirming(false);
                                    setError(null);
                                }}
                                disabled={isRefreshing}
                                className="flex-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleRefresh}
                                disabled={isRefreshing}
                                className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center"
                            >
                                {isRefreshing ? (
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                ) : (
                                    "Confirm Reset"
                                )}
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
