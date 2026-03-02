import { useState } from 'react';
import axios from 'axios';
import { Sidebar } from './components/Sidebar';
import { QueryEditor } from './components/QueryEditor';
import { ResultsTable } from './components/ResultsTable';
import { SavedQueries } from './components/SavedQueries';
import type { QueryResult, SavedQuery } from './types';

// Connect to API on port 8000. 
const API_URL = 'http://localhost:8000/api/query';

import { DEFAULT_QUERIES } from './assets/default-queries';

function App() {
  const [query, setQuery] = useState<string>('-- Write your SQL query here\nSELECT * FROM silver.amex LIMIT 10;');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>(() => {
    const saved = localStorage.getItem('budgetSavedQueries');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) return parsed;
      } catch (e) {
        // Fallthrough to defaults on error
      }
    }
    localStorage.setItem('budgetSavedQueries', JSON.stringify(DEFAULT_QUERIES));
    return DEFAULT_QUERIES;
  });

  const handleSaveQuery = () => {
    if (!query.trim()) return;

    const title = window.prompt("Enter a title for this saved query:");
    if (!title) return;

    const newQuery: SavedQuery = {
      id: Math.random().toString(36).substring(7),
      title: title.trim(),
      query: query.trim()
    };

    // Prevent duplicate exact queries from being saved consecutively if needed,
    // but a user might want to save same query. We will just save it.

    const newSaved = [newQuery, ...savedQueries];
    setSavedQueries(newSaved);
    localStorage.setItem('budgetSavedQueries', JSON.stringify(newSaved));
  };

  const handleRestoreDefaults = () => {
    if (window.confirm("Are you sure you want to restore default queries? This will overwrite your current saved queries.")) {
      setSavedQueries(DEFAULT_QUERIES);
      localStorage.setItem('budgetSavedQueries', JSON.stringify(DEFAULT_QUERIES));
    }
  };

  const handleDeleteQuery = (id: string) => {
    const newSaved = savedQueries.filter(q => q.id !== id);
    setSavedQueries(newSaved);
    localStorage.setItem('budgetSavedQueries', JSON.stringify(newSaved));
  };

  const handleRunQuery = async (overrideQuery?: string) => {
    const q = overrideQuery || query;
    if (!q.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.post<QueryResult>(API_URL, { query: q });
      setResult(response.data);
    } catch (err: any) {
      console.error(err);
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError(err.message || 'An network error occurred connecting to the backend API.');
      }
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-900 text-slate-200">
      <Sidebar />
      <main className="flex-1 flex flex-col h-full overflow-y-auto w-full">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/20 via-slate-900 to-slate-900 -z-10 pointer-events-none" />

        <div className="max-w-7xl mx-auto w-full p-8 md:p-12 space-y-8 pb-32">

          <header className="mb-8">
            <h2 className="text-3xl font-bold tracking-tight text-white mb-2">Query Editor</h2>
            <p className="text-slate-400">Write, lint, and execute SQL queries against your central DuckDB database.</p>
          </header>

          <section className="pb-6">
            <SavedQueries
              queries={savedQueries}
              onLoad={(q) => setQuery(q)}
              onRun={(q) => {
                setQuery(q);
                handleRunQuery(q);
              }}
              onDelete={handleDeleteQuery}
              onRestoreDefaults={handleRestoreDefaults}
            />
          </section>

          <section className="space-y-2">
            <QueryEditor
              value={query}
              onChange={(val) => setQuery(val || '')}
              onSubmit={() => handleRunQuery()}
              onSave={handleSaveQuery}
              isLoading={isLoading}
            />
          </section>

          <section className="py-2">
            <ResultsTable result={result} error={error} />
          </section>

        </div>
      </main>
    </div>
  );
}

export default App;
