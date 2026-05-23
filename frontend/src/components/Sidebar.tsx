import { Database, LayoutDashboard } from 'lucide-react';
import { clsx } from 'clsx';
import { RefreshPipeline } from './RefreshPipeline';
import type { DashboardView } from '../types';

interface SidebarProps {
    activeView: DashboardView;
    onNavigate: (view: DashboardView) => void;
    onRefreshComplete?: () => void;
}

export function Sidebar({ activeView, onNavigate, onRefreshComplete }: SidebarProps) {
    const navItems: { view: DashboardView; label: string; icon: React.ReactNode }[] = [
        {
            view: 'dashboard',
            label: 'Dashboard',
            icon: <LayoutDashboard className="w-5 h-5 mr-3 shrink-0" />,
        },
        {
            view: 'query',
            label: 'Query Database',
            icon: <Database className="w-5 h-5 mr-3 shrink-0" />,
        },
    ];

    return (
        <div className="w-64 bg-slate-800 border-r border-slate-700/50 flex flex-col h-full shrink-0">
            <div className="h-16 flex items-center px-6 border-b border-slate-700/50">
                <Database className="w-6 h-6 text-blue-500 mr-3" />
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-sky-400 bg-clip-text text-transparent truncate">
                    My Budget
                </h1>
            </div>
            <nav className="flex-1 py-4 px-3 space-y-1">
                {navItems.map(({ view, label, icon }) => (
                    <button
                        key={view}
                        onClick={() => onNavigate(view)}
                        className={clsx(
                            "flex items-center w-full px-3 py-2.5 text-sm font-medium rounded-lg transition-colors text-left",
                            activeView === view
                                ? "bg-blue-500/10 text-blue-400"
                                : "text-slate-400 hover:bg-slate-700/50 hover:text-slate-200"
                        )}
                    >
                        {icon}
                        {label}
                    </button>
                ))}
            </nav>
            <div className="p-4 border-t border-slate-700/50">
                <RefreshPipeline onRefreshComplete={onRefreshComplete} />
            </div>
        </div>
    );
}
