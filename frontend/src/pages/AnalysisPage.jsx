import { useState, useRef, useCallback } from 'react';
import { startAnalysis, getJobStatus } from '../api';
import Spinner from '../components/Spinner';
import ResultsDashboard from '../components/ResultsDashboard';

export default function AnalysisPage() {
    const [tickerInput, setTickerInput] = useState('');
    const [status, setStatus] = useState('idle'); // idle | running | completed | failed
    const [statusMsg, setStatusMsg] = useState('');
    const [results, setResults] = useState(null);
    const pollRef = useRef(null);

    const handleRun = useCallback(async () => {
        const tickers = tickerInput
            .split(',')
            .map(t => t.trim().toUpperCase())
            .filter(Boolean);

        if (tickers.length === 0) {
            setStatusMsg('Please enter at least one ticker symbol.');
            return;
        }

        setStatus('running');
        setStatusMsg(`Running analysis for ${tickers.join(', ')}...`);
        setResults(null);

        try {
            const { job_id } = await startAnalysis(tickers);

            // Poll for completion
            const poll = async () => {
                try {
                    const job = await getJobStatus(job_id);

                    if (job.status === 'completed') {
                        setStatus('completed');
                        setResults(job.result);
                        setStatusMsg(`Analysis completed successfully.`);
                        return;
                    }

                    if (job.status === 'failed') {
                        setStatus('failed');
                        setStatusMsg(`Analysis failed: ${job.error || 'Unknown error'}`);
                        return;
                    }

                    // Still running — poll again
                    pollRef.current = setTimeout(poll, 3000);
                } catch (err) {
                    setStatus('failed');
                    setStatusMsg(`Error polling status: ${err.message}`);
                }
            };

            pollRef.current = setTimeout(poll, 2000);
        } catch (err) {
            setStatus('failed');
            setStatusMsg(`Failed to start analysis: ${err.message}`);
        }
    }, [tickerInput]);

    return (
        <div>
            <div className="page-header">
                <h2>📊 New Analysis</h2>
                <p>Run the full multi-agent pipeline: Technical → Sentiment → Fundamentals → Synthesis → Trader → Validation</p>
            </div>

            {/* Input Form */}
            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                <div className="analysis-form">
                    <div className="input-group" style={{ flex: 1 }}>
                        <label htmlFor="ticker-input">Ticker Symbols</label>
                        <input
                            id="ticker-input"
                            className="input-field"
                            type="text"
                            placeholder="e.g. AAPL, NVDA, GOOGL"
                            value={tickerInput}
                            onChange={e => setTickerInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && status !== 'running' && handleRun()}
                            disabled={status === 'running'}
                        />
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={handleRun}
                        disabled={status === 'running'}
                    >
                        {status === 'running' ? '⏳ Running...' : '🚀 Run Analysis'}
                    </button>
                </div>
                {statusMsg && (
                    <p style={{
                        marginTop: 'var(--sp-md)',
                        fontSize: '0.85rem',
                        color: status === 'failed' ? 'var(--accent-red)' :
                            status === 'completed' ? 'var(--accent-green)' :
                                'var(--accent-cyan)',
                    }}>
                        {statusMsg}
                    </p>
                )}
            </div>

            {/* Loading State */}
            {status === 'running' && (
                <Spinner text="Multi-agent analysis in progress — this may take a few minutes..." />
            )}

            {/* Results */}
            {results && <ResultsDashboard results={results} />}
        </div>
    );
}
