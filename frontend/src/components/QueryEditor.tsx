import Editor from '@monaco-editor/react';
import { Play, Bookmark } from 'lucide-react';

interface QueryEditorProps {
    value: string;
    onChange: (value: string | undefined) => void;
    onSubmit: () => void;
    onSave: () => void;
    isLoading: boolean;
}

export function QueryEditor({ value, onChange, onSubmit, onSave, isLoading }: QueryEditorProps) {
    return (
        <div className="flex flex-col rounded-xl overflow-hidden border border-slate-700/50 bg-slate-800/50 shadow-lg">
            <div className="h-[300px]">
                <Editor
                    height="100%"
                    defaultLanguage="sql"
                    theme="vs-dark"
                    value={value}
                    onChange={onChange}
                    options={{
                        minimap: { enabled: false },
                        fontSize: 14,
                        padding: { top: 16, bottom: 16 },
                        scrollBeyondLastLine: false,
                        roundedSelection: false,
                        formatOnPaste: true,
                        suggestOnTriggerCharacters: true,
                    }}
                />
            </div>
            <div className="p-4 border-t border-slate-700/50 bg-slate-800 flex justify-end space-x-3">
                <button
                    onClick={onSave}
                    disabled={!value.trim()}
                    className="flex items-center px-6 py-2.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500/50 border border-slate-600/50"
                >
                    <Bookmark className="w-4 h-4 mr-2 text-emerald-400" />
                    Save Query
                </button>
                <button
                    onClick={onSubmit}
                    disabled={isLoading || !value.trim()}
                    className="flex items-center px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                >
                    {isLoading ? (
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                    ) : (
                        <Play className="w-4 h-4 mr-2" fill="currentColor" />
                    )}
                    Run Query
                </button>
            </div>
        </div>
    );
}
