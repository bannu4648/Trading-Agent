import { useState, useEffect } from 'react';
import { listResults, getResult } from '../api';
import Spinner from '../components/Spinner';
import ResultsDashboard from '../components/ResultsDashboard';

export default function HistoryPage() {
    const [entries, setEntries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedResult, setSelectedResult] = useState(null);
    const [selectedFilename, setSelectedFilename] = useState(null);
    const [loadingResult, setLoadingResult] = useState(false);

    useEffect(() => {
        (async () => {
            try {
                const data = await listResults();
                setEntries(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    const handleSelect = async (filename) => {
        setLoadingResult(true);
        setSelectedFilename(filename);
        try {
            const data = await getResult(filename);
            setSelectedResult(data);
        } catch (err) {
            setError(`Failed to load ${filename}: ${err.message}`);
        } finally {
            setLoadingResult(false);
        }
    };

    const handleBack = () => {
        setSelectedResult(null);
        setSelectedFilename(null);
    };

    if (loading) return <Spinner text="Loading past results..." />;

    if (selectedResult) {
        return (
            <div>
                <div className="page-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-md)' }}>
                        <button className="btn btn-secondary" onClick={handleBack}>← Back</button>
                        <div>
                            <h2>📂 {selectedFilename}</h2>
                            <p>Viewing saved analysis result</p>
                        </div>
                    </div>
                </div>
                {loadingResult ? <Spinner text="Loading result..." /> : <ResultsDashboard results={selectedResult} />}
            </div>
        );
    }

    return (
        <div>
            <div className="page-header">
                <h2>📁 Past Results</h2>
                <p>Browse previously saved analysis runs</p>
            </div>

            {error && <p style={{ color: 'var(--accent-red)', marginBottom: 'var(--sp-md)' }}>{error}</p>}

            {entries.length === 0 ? (
                <div className="empty-state">
                    <div className="icon">📭</div>
                    <p>No past results found. Run a new analysis to get started.</p>
                </div>
            ) : (
                <div className="card">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Filename</th>
                                <th>Tickers</th>
                                <th>Generated At</th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.map((entry) => (
                                <tr
                                    key={entry.filename}
                                    className="clickable history-row"
                                    onClick={() => handleSelect(entry.filename)}
                                >
                                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)' }}>
                                        {entry.filename}
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 'var(--sp-xs)', flexWrap: 'wrap' }}>
                                            {entry.tickers.map(t => (
                                                <span key={t} className="badge badge-info">{t}</span>
                                            ))}
                                        </div>
                                    </td>
                                    <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                                        {entry.generated_at ? new Date(entry.generated_at).toLocaleString() : 'N/A'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
