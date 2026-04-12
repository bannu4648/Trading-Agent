import { useState, useRef, useCallback, useEffect, useLayoutEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAnalysisSession } from '../context/AnalysisSessionContext';
import {
    startAnalysis,
    startTop20LongShort,
    startSp500Screened,
    getJobStatus,
    consumeJobStream,
    JOB_STATUS_FIRST_POLL_MS,
    JOB_STATUS_POLL_INTERVAL_MS,
} from '../api';
import Spinner from '../components/Spinner';
import ResultsDashboard from '../components/ResultsDashboard';
import LlmStreamPanel, { streamKey } from '../components/LlmStreamPanel';
import TickerCard from '../components/TickerCard';
import RiskPanel from '../components/RiskPanel';

const PIPELINE_MODES = {
    custom: {
        id: 'custom',
        label: 'Custom tickers',
        shortLabel: 'Custom',
        icon: '✏️',
        description:
            'Your symbols only: full stack with ReAct trader (four sizing methods). Best for a small watchlist.',
    },
    top20: {
        id: 'top20',
        label: 'Top 20 long / short',
        shortLabel: 'Top 20',
        icon: '⚖️',
        description:
            'Fixed 20 large-cap names: research all → risk allocator (default 10 long + 10 short slots) → trader on the book → validation.',
    },
    sp500: {
        id: 'sp500',
        label: 'S&P 500 screened',
        shortLabel: 'S&P 500',
        icon: '📈',
        description:
            'Technicals on ~500 names (formula screen) → deep research on your max-candidate pool → allocator books at most k_long + k_short names with non-zero weights (defaults 10+10). Long-running.',
    },
};

function attachStream(jobId, setStreamBlocks, setStageLines, setStreamError, streamAbortRef) {
    const ac = new AbortController();
    streamAbortRef.current = ac;
    consumeJobStream(
        jobId,
        (ev) => {
            if (!ev || typeof ev !== 'object') return;
            if (ev.type === 'llm_chunk' && ev.chunk) {
                const k = streamKey(ev);
                setStreamBlocks((prev) => ({
                    ...prev,
                    [k]: (prev[k] || '') + ev.chunk,
                }));
            } else if (ev.type === 'llm_start') {
                const k = streamKey(ev);
                setStreamBlocks((prev) => ({
                    ...prev,
                    [k]: (prev[k] ? `${prev[k]}\n` : ''),
                }));
            } else if (ev.type === 'stage' && ev.label) {
                const line = ev.ticker ? `${ev.label} (${ev.ticker})` : ev.label;
                setStageLines((prev) => [...prev, line]);
            } else if (ev.type === 'job_done') {
                streamAbortRef.current = null;
            }
        },
        ac.signal,
        (err) => setStreamError(err.message || String(err)),
    );
}

export default function AnalysisPage() {
    const { session, mergeSession, clearSession } = useAnalysisSession();
    const [searchParams, setSearchParams] = useSearchParams();
    const [pipelineMode, setPipelineMode] = useState(() => {
        const m = searchParams.get('mode');
        return m === 'top20' || m === 'sp500' ? m : 'custom';
    });

    const [tickerInput, setTickerInput] = useState('');
    const [endDate, setEndDate] = useState('');
    const [useLlmInterpret, setUseLlmInterpret] = useState(true);
    const [enableLlmSummaryTechnical, setEnableLlmSummaryTechnical] = useState(false);
    const [maxCandidates, setMaxCandidates] = useState(30);
    const [limitUniverse, setLimitUniverse] = useState(0);
    const [executePaper, setExecutePaper] = useState(false);
    const [paperForce, setPaperForce] = useState(false);

    const [mainTab, setMainTab] = useState('live');
    const [stockTab, setStockTab] = useState('');

    const [status, setStatus] = useState('idle');
    const [statusMsg, setStatusMsg] = useState('');
    const [results, setResults] = useState(null);
    const [partialResults, setPartialResults] = useState(null);
    const [failureError, setFailureError] = useState(null);
    const [streamBlocks, setStreamBlocks] = useState({});
    const [stageLines, setStageLines] = useState([]);
    const [streamError, setStreamError] = useState(null);
    const [activeJobId, setActiveJobId] = useState(null);

    const pollRef = useRef(null);
    const streamAbortRef = useRef(null);
    const hydratedFromSessionRef = useRef(false);
    const pipelineModeRef = useRef(pipelineMode);
    pipelineModeRef.current = pipelineMode;

    useLayoutEffect(() => {
        if (hydratedFromSessionRef.current || !session) return;
        const hasPayload =
            session.results != null ||
            session.partialResults != null ||
            (session.status && session.status !== 'idle');
        if (!hasPayload) return;
        hydratedFromSessionRef.current = true;

        if (session.pipelineMode === 'top20' || session.pipelineMode === 'sp500') {
            setSearchParams({ mode: session.pipelineMode });
        }
        if (session.pipelineMode) setPipelineMode(session.pipelineMode);
        if (session.tickerInput != null) setTickerInput(session.tickerInput);
        if (session.endDate != null) setEndDate(session.endDate);
        if (session.useLlmInterpret != null) setUseLlmInterpret(session.useLlmInterpret);
        if (session.enableLlmSummaryTechnical != null) {
            setEnableLlmSummaryTechnical(session.enableLlmSummaryTechnical);
        }
        if (session.maxCandidates != null) setMaxCandidates(session.maxCandidates);
        if (session.limitUniverse != null) setLimitUniverse(session.limitUniverse);
        if (session.executePaper != null) setExecutePaper(session.executePaper);
        if (session.paperForce != null) setPaperForce(session.paperForce);
        if (session.mainTab != null) setMainTab(session.mainTab);
        if (session.stockTab != null) setStockTab(session.stockTab);
        if (session.streamBlocks != null) setStreamBlocks(session.streamBlocks);
        if (session.stageLines != null) setStageLines(session.stageLines);
        if (session.streamError != null) setStreamError(session.streamError);

        if (session.status === 'running' && session.activeJobId) {
            setResults(session.results ?? null);
            setPartialResults(session.partialResults ?? null);
            setFailureError(session.failureError ?? null);
            setActiveJobId(session.activeJobId);
            setStatus('running');
            setStatusMsg(
                session.statusMsg ||
                    'Resuming status polls for a run that was in progress…',
            );
        } else if (session.status === 'running') {
            setResults(session.results ?? null);
            setPartialResults(session.partialResults ?? null);
            setFailureError(null);
            setStatus('failed');
            setActiveJobId(null);
            setStatusMsg(
                'Previous run was still in progress when you left this page; polling had stopped. Partial data may appear below — start a new run to finish.',
            );
        } else {
            setStatus(session.status ?? 'idle');
            setStatusMsg(session.statusMsg ?? '');
            setResults(session.results ?? null);
            setPartialResults(session.partialResults ?? null);
            setFailureError(session.failureError ?? null);
            setActiveJobId(null);
        }
    }, [session, setSearchParams]);

    useEffect(() => {
        const m = searchParams.get('mode');
        if ((m === 'top20' || m === 'sp500') && m !== pipelineMode && status === 'idle') {
            setPipelineMode(m);
        }
    }, [searchParams, pipelineMode, status]);

    useEffect(() => {
        mergeSession({
            pipelineMode,
            tickerInput,
            endDate,
            useLlmInterpret,
            enableLlmSummaryTechnical,
            maxCandidates,
            limitUniverse,
            executePaper,
            paperForce,
            mainTab,
            stockTab,
            status,
            statusMsg,
            results,
            partialResults,
            failureError,
            streamBlocks,
            stageLines,
            streamError,
            activeJobId,
        });
    }, [
        mergeSession,
        pipelineMode,
        tickerInput,
        endDate,
        useLlmInterpret,
        enableLlmSummaryTechnical,
        maxCandidates,
        limitUniverse,
        executePaper,
        paperForce,
        mainTab,
        stockTab,
        status,
        statusMsg,
        results,
        partialResults,
        failureError,
        streamBlocks,
        stageLines,
        streamError,
        activeJobId,
    ]);

    useEffect(
        () => () => {
            if (pollRef.current) clearTimeout(pollRef.current);
            if (streamAbortRef.current) streamAbortRef.current.abort();
        },
        [],
    );

    const selectMode = useCallback(
        (mode) => {
            if (status === 'running') return;
            setPipelineMode(mode);
            if (mode === 'custom') setSearchParams({});
            else setSearchParams({ mode });
        },
        [status, setSearchParams],
    );

    const isBookStyle = pipelineMode === 'top20' || pipelineMode === 'sp500';
    const displayData = status === 'completed' && results ? results : partialResults;
    const tickers = displayData?.metadata?.tickers || [];

    useEffect(() => {
        if (tickers.length && !stockTab) setStockTab(tickers[0]);
        if (tickers.length && stockTab && !tickers.includes(stockTab)) setStockTab(tickers[0]);
    }, [tickers, stockTab]);

    const formatPartialStatus = useCallback((job) => {
        const mode = pipelineModeRef.current;
        const pr = job.partial_result;
        if (!pr?.metadata) return 'Pipeline running… next status check in ~10s.';
        const m = pr.metadata;
        const label = m.pipeline_step_label || 'Running…';
        const rd = m.research_done;
        const rt = m.research_total;
        const researchExtra =
            rd != null && rt != null ? ` (${rd}/${rt} tickers)` : '';
        if (mode === 'sp500' && m.pipeline_step) {
            return `${label} [${m.pipeline_step}]${researchExtra} — next poll ~10s.`;
        }
        return `${label}${researchExtra} — next poll ~10s.`;
    }, []);

    const handleRun = useCallback(async () => {
        if (pollRef.current) {
            clearTimeout(pollRef.current);
            pollRef.current = null;
        }
        if (streamAbortRef.current) {
            streamAbortRef.current.abort();
            streamAbortRef.current = null;
        }

        if (pipelineMode === 'custom') {
            const tickers = tickerInput
                .split(',')
                .map((t) => t.trim().toUpperCase())
                .filter(Boolean);
            if (tickers.length === 0) {
                setStatusMsg('Please enter at least one ticker symbol.');
                return;
            }
        }

        setStatus('running');
        setResults(null);
        setPartialResults(null);
        setFailureError(null);
        setStreamBlocks({});
        setStageLines([]);
        setStreamError(null);
        setMainTab('live');
        setActiveJobId(null);

        const modeMeta = PIPELINE_MODES[pipelineMode];
        setStatusMsg(`Starting ${modeMeta.label}…`);

        try {
            let job_id;

            if (pipelineMode === 'custom') {
                const tickers = tickerInput
                    .split(',')
                    .map((t) => t.trim().toUpperCase())
                    .filter(Boolean);
                ({ job_id } = await startAnalysis(tickers));
            } else if (pipelineMode === 'top20') {
                ({ job_id } = await startTop20LongShort({
                    endDate: endDate.trim() || null,
                    useLlmInterpret: useLlmInterpret,
                    executePaper,
                    paperForce,
                }));
            } else {
                ({ job_id } = await startSp500Screened({
                    endDate: endDate.trim() || null,
                    useLlmInterpret: useLlmInterpret,
                    enableLlmSummaryTechnical,
                    maxCandidates: maxCandidates || 30,
                    limitUniverse: limitUniverse || 0,
                    executePaper,
                    paperForce,
                }));
            }

            setActiveJobId(job_id);
        } catch (err) {
            setStatus('failed');
            setStatusMsg(`Failed to start: ${err.message}`);
            setFailureError(err.message);
            setActiveJobId(null);
        }
    }, [
        pipelineMode,
        tickerInput,
        endDate,
        useLlmInterpret,
        enableLlmSummaryTechnical,
        maxCandidates,
        limitUniverse,
        executePaper,
        paperForce,
    ]);

    useEffect(() => {
        if (status !== 'running' || !activeJobId) return;

        attachStream(activeJobId, setStreamBlocks, setStageLines, setStreamError, streamAbortRef);

        const modeMeta = PIPELINE_MODES[pipelineModeRef.current];

        const poll = async () => {
            try {
                const job = await getJobStatus(activeJobId);

                if (job.status === 'completed') {
                    setStatus('completed');
                    setResults(job.result);
                    setPartialResults(null);
                    setFailureError(null);
                    setActiveJobId(null);
                    setStatusMsg(`${modeMeta.label} completed successfully.`);
                    if (streamAbortRef.current) {
                        streamAbortRef.current.abort();
                        streamAbortRef.current = null;
                    }
                    return;
                }

                if (job.status === 'failed') {
                    setStatus('failed');
                    setFailureError(job.error || 'Unknown error');
                    if (job.partial_result) setPartialResults(job.partial_result);
                    setActiveJobId(null);
                    setStatusMsg(`Failed: ${job.error || 'Unknown error'}`);
                    if (streamAbortRef.current) {
                        streamAbortRef.current.abort();
                        streamAbortRef.current = null;
                    }
                    return;
                }

                if (job.partial_result) {
                    setPartialResults(job.partial_result);
                    setStatusMsg(formatPartialStatus(job));
                }

                pollRef.current = setTimeout(poll, JOB_STATUS_POLL_INTERVAL_MS);
            } catch (err) {
                setStatus('failed');
                setActiveJobId(null);
                setStatusMsg(`Error polling status: ${err.message}`);
                setFailureError(err.message);
            }
        };

        pollRef.current = setTimeout(poll, JOB_STATUS_FIRST_POLL_MS);
        return () => {
            if (pollRef.current) {
                clearTimeout(pollRef.current);
                pollRef.current = null;
            }
            if (streamAbortRef.current) {
                streamAbortRef.current.abort();
                streamAbortRef.current = null;
            }
        };
    }, [status, activeJobId, formatPartialStatus]);

    const showLiveDashboard = status === 'running' && partialResults && !isBookStyle;
    const showFailedPartial = status === 'failed' && partialResults && !isBookStyle;
    const streamActive = status === 'running';

    const tw = displayData?.target_weights || {};
    const weightRows = Object.entries(tw)
        .filter(([, w]) => Math.abs(Number(w)) > 1e-6)
        .sort((a, b) => Math.abs(Number(b[1])) - Math.abs(Number(a[1])));

    const tabBtn = (id, label) => (
        <button
            type="button"
            className={`tab-btn ${mainTab === id ? 'active' : ''}`}
            onClick={() => setMainTab(id)}
            style={{ marginRight: 'var(--sp-sm)' }}
        >
            {label}
        </button>
    );

    const modeInfo = PIPELINE_MODES[pipelineMode];
    const runDisabled = status === 'running';
    const hasCachedRun = Boolean(results || partialResults || (status !== 'idle' && status !== 'running'));

    const clearCachedRun = useCallback(() => {
        if (pollRef.current) {
            clearTimeout(pollRef.current);
            pollRef.current = null;
        }
        if (streamAbortRef.current) {
            streamAbortRef.current.abort();
            streamAbortRef.current = null;
        }
        clearSession();
        hydratedFromSessionRef.current = false;
        setStatus('idle');
        setStatusMsg('');
        setResults(null);
        setPartialResults(null);
        setFailureError(null);
        setActiveJobId(null);
        setStreamBlocks({});
        setStageLines([]);
        setStreamError(null);
        setMainTab('live');
    }, [clearSession]);

    return (
        <div>
            <div className="page-header">
                <div
                    style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        gap: 'var(--sp-md)',
                    }}
                >
                    <div style={{ flex: '1 1 280px' }}>
                        <h2>Run pipeline</h2>
                        <p style={{ marginBottom: 0 }}>
                            Choose how the backend selects tickers: <strong>custom list</strong>,{' '}
                            <strong>Top 20</strong> curated book, or <strong>S&amp;P 500 screened</strong> at scale.
                            See <code>docs/PIPELINE.md</code> for stages and methodologies.
                        </p>
                    </div>
                    {hasCachedRun && (
                        <div style={{ flex: '0 0 auto' }}>
                            <button type="button" className="btn" onClick={clearCachedRun} disabled={runDisabled}>
                                Clear cached run
                            </button>
                            <p
                                style={{
                                    margin: '0.35rem 0 0',
                                    fontSize: '0.72rem',
                                    color: 'var(--text-muted)',
                                    maxWidth: '220px',
                                    lineHeight: 1.35,
                                }}
                            >
                                Results stay while you use other tabs; full page reload clears them.
                            </p>
                        </div>
                    )}
                </div>
            </div>

            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                <p
                    style={{
                        fontSize: '0.8rem',
                        color: 'var(--text-muted)',
                        marginBottom: 'var(--sp-md)',
                    }}
                >
                    Pipeline mode
                </p>
                <div className="pipeline-mode-selector">
                    {Object.values(PIPELINE_MODES).map((m) => (
                        <button
                            key={m.id}
                            type="button"
                            className={`pipeline-mode-btn ${pipelineMode === m.id ? 'active' : ''}`}
                            onClick={() => selectMode(m.id)}
                            disabled={runDisabled}
                        >
                            <span className="pipeline-mode-btn-icon">{m.icon}</span>
                            <span className="pipeline-mode-btn-title">{m.label}</span>
                            <span className="pipeline-mode-btn-desc">{m.description}</span>
                        </button>
                    ))}
                </div>

                <p
                    style={{
                        marginTop: 'var(--sp-lg)',
                        fontSize: '0.85rem',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.5,
                    }}
                >
                    <strong>{modeInfo.label}:</strong> {modeInfo.description}
                </p>

                <div style={{ marginTop: 'var(--sp-lg)' }}>
                    {pipelineMode === 'custom' && (
                        <div className="analysis-form">
                            <div className="input-group" style={{ flex: 1 }}>
                                <label htmlFor="ticker-input">Ticker symbols</label>
                                <input
                                    id="ticker-input"
                                    className="input-field"
                                    type="text"
                                    placeholder="e.g. AAPL, NVDA, GOOGL"
                                    value={tickerInput}
                                    onChange={(e) => setTickerInput(e.target.value)}
                                    onKeyDown={(e) =>
                                        e.key === 'Enter' && !runDisabled && handleRun()
                                    }
                                    disabled={runDisabled}
                                />
                            </div>
                            <button
                                type="button"
                                className="btn btn-primary"
                                onClick={handleRun}
                                disabled={runDisabled}
                            >
                                {runDisabled ? 'Running…' : 'Run analysis'}
                            </button>
                        </div>
                    )}

                    {(pipelineMode === 'top20' || pipelineMode === 'sp500') && (
                        <div
                            className="analysis-form"
                            style={{
                                flexWrap: 'wrap',
                                alignItems: 'flex-end',
                                gap: 'var(--sp-md)',
                            }}
                        >
                            <div className="input-group" style={{ minWidth: '200px' }}>
                                <label htmlFor="pipe-end">End date (optional)</label>
                                <input
                                    id="pipe-end"
                                    className="input-field"
                                    type="text"
                                    placeholder="YYYY-MM-DD — blank = today UTC"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    disabled={runDisabled}
                                />
                            </div>
                            <label
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    cursor: 'pointer',
                                    fontSize: '0.88rem',
                                }}
                            >
                                <input
                                    type="checkbox"
                                    checked={useLlmInterpret}
                                    onChange={(e) => setUseLlmInterpret(e.target.checked)}
                                    disabled={runDisabled}
                                />
                                LLM interpret (adapter)
                            </label>
                            {pipelineMode === 'sp500' && (
                                <>
                                    <label
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '0.5rem',
                                            cursor: 'pointer',
                                            fontSize: '0.88rem',
                                        }}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={enableLlmSummaryTechnical}
                                            onChange={(e) =>
                                                setEnableLlmSummaryTechnical(e.target.checked)
                                            }
                                            disabled={runDisabled}
                                        />
                                        Technical LLM on ~500 (expensive)
                                    </label>
                                    <div className="input-group" style={{ width: '140px' }}>
                                        <label htmlFor="max-cand">Max candidates</label>
                                        <input
                                            id="max-cand"
                                            className="input-field"
                                            type="number"
                                            min={5}
                                            max={200}
                                            value={maxCandidates}
                                            onChange={(e) =>
                                                setMaxCandidates(Number(e.target.value) || 30)
                                            }
                                            disabled={runDisabled}
                                        />
                                        <span
                                            style={{
                                                display: 'block',
                                                fontSize: '0.72rem',
                                                color: 'var(--text-muted)',
                                                marginTop: '0.35rem',
                                                lineHeight: 1.35,
                                            }}
                                        >
                                            Split across long/short ideas: best half by formula expected return
                                            (from technicals) and worst half. The allocator still caps booked names
                                            (k_long + k_short; see dashboard after the run).
                                        </span>
                                    </div>
                                    <div className="input-group" style={{ width: '140px' }}>
                                        <label htmlFor="lim-uni">Limit universe (debug)</label>
                                        <input
                                            id="lim-uni"
                                            className="input-field"
                                            type="number"
                                            min={0}
                                            max={503}
                                            value={limitUniverse}
                                            onChange={(e) =>
                                                setLimitUniverse(Number(e.target.value) || 0)
                                            }
                                            disabled={runDisabled}
                                        />
                                        <span
                                            style={{
                                                display: 'block',
                                                fontSize: '0.72rem',
                                                color: 'var(--text-muted)',
                                                marginTop: '0.35rem',
                                                lineHeight: 1.35,
                                            }}
                                        >
                                            Use <strong>0</strong> for the full list. Any N&gt;0 caps the pipeline to the
                                            first N S&amp;P tickers — you will see at most N candidates after screening.
                                        </span>
                                    </div>
                                </>
                            )}
                            <div
                                style={{
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    gap: 'var(--sp-md)',
                                    alignItems: 'center',
                                }}
                            >
                                <label
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.5rem',
                                        cursor: 'pointer',
                                        fontSize: '0.88rem',
                                    }}
                                >
                                    <input
                                        type="checkbox"
                                        checked={executePaper}
                                        onChange={(e) => setExecutePaper(e.target.checked)}
                                        disabled={runDisabled}
                                    />
                                    Paper rebalance after validation
                                </label>
                                <label
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.5rem',
                                        cursor: 'pointer',
                                        fontSize: '0.88rem',
                                        opacity: executePaper ? 1 : 0.5,
                                    }}
                                >
                                    <input
                                        type="checkbox"
                                        checked={paperForce}
                                        onChange={(e) => setPaperForce(e.target.checked)}
                                        disabled={runDisabled || !executePaper}
                                    />
                                    Force even if risk HIGH
                                </label>
                            </div>
                            <button
                                type="button"
                                className="btn btn-primary"
                                onClick={handleRun}
                                disabled={runDisabled}
                            >
                                {runDisabled
                                    ? 'Running…'
                                    : pipelineMode === 'top20'
                                      ? 'Run Top 20 long/short'
                                      : 'Run S&P 500 screened'}
                            </button>
                        </div>
                    )}
                </div>

                {statusMsg && (
                    <p
                        style={{
                            marginTop: 'var(--sp-md)',
                            fontSize: '0.85rem',
                            color:
                                status === 'failed'
                                    ? 'var(--accent-red)'
                                    : status === 'completed'
                                      ? 'var(--accent-green)'
                                      : 'var(--accent-cyan)',
                        }}
                    >
                        {statusMsg}
                    </p>
                )}
                {status === 'running' && (
                    <p
                        style={{
                            marginTop: 'var(--sp-sm)',
                            fontSize: '0.78rem',
                            color: 'var(--text-muted)',
                        }}
                    >
                        Live tokens stream below (SSE). Status polls every ~10s for partial JSON.
                    </p>
                )}
                {streamError && (
                    <p
                        style={{
                            marginTop: 'var(--sp-sm)',
                            fontSize: '0.8rem',
                            color: 'var(--accent-red)',
                        }}
                    >
                        Stream: {streamError}. Check API URL and backend.
                    </p>
                )}
            </div>

            {isBookStyle && (
                <div className="tabs" style={{ marginBottom: 'var(--sp-lg)' }}>
                    {tabBtn('live', 'Live run')}
                    {tabBtn('portfolio', 'Portfolio allocation')}
                    {tabBtn('stocks', 'Per stock')}
                </div>
            )}

            {isBookStyle && mainTab === 'live' && (
                <>
                    <LlmStreamPanel
                        streamBlocks={streamBlocks}
                        stageLines={stageLines}
                        active={streamActive}
                    />
                    {status === 'running' &&
                        !partialResults &&
                        Object.keys(streamBlocks).length === 0 && (
                            <Spinner text="Waiting for first partial snapshot…" />
                        )}
                    {displayData && (
                        <ResultsDashboard
                            results={displayData}
                            isPartial={status === 'running'}
                            errorMessage={status === 'failed' ? failureError : null}
                        />
                    )}
                </>
            )}

            {isBookStyle && mainTab === 'portfolio' && (
                <div className="fade-in">
                    {!displayData && (
                        <p className="text-muted">Run a job to see allocator targets and risk metrics.</p>
                    )}
                    {displayData && (
                        <>
                            <div className="card" style={{ marginBottom: 'var(--sp-lg)' }}>
                                <div className="card-header">
                                    <h3>Risk allocator targets</h3>
                                    {displayData.risk_portfolio && (
                                        <span className="badge badge-info">
                                            K_long={displayData.risk_portfolio.k_long} · K_short=
                                            {displayData.risk_portfolio.k_short}
                                        </span>
                                    )}
                                </div>
                                {weightRows.length === 0 ? (
                                    <p style={{ color: 'var(--text-muted)' }}>
                                        No non-zero weights yet.
                                    </p>
                                ) : (
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>Ticker</th>
                                                <th>Target weight</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {weightRows.map(([t, w]) => (
                                                <tr key={t}>
                                                    <td style={{ fontWeight: 600 }}>{t}</td>
                                                    <td
                                                        style={{
                                                            fontFamily: 'var(--font-mono)',
                                                            color:
                                                                Number(w) < 0
                                                                    ? 'var(--accent-red)'
                                                                    : 'var(--accent-green)',
                                                        }}
                                                    >
                                                        {(Number(w) * 100).toFixed(2)}%
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}
                                {displayData.metadata?.saved_path && (
                                    <p
                                        style={{
                                            marginTop: 'var(--sp-md)',
                                            fontSize: '0.78rem',
                                            color: 'var(--text-muted)',
                                        }}
                                    >
                                        Saved: {displayData.metadata.saved_path}
                                    </p>
                                )}
                                {displayData.paper_execution && (
                                    <p
                                        style={{
                                            marginTop: 'var(--sp-sm)',
                                            fontSize: '0.78rem',
                                            color: 'var(--accent-cyan)',
                                        }}
                                    >
                                        Paper:{' '}
                                        {displayData.paper_execution.executed
                                            ? `executed → ${displayData.paper_execution.state_path || 'state file'}`
                                            : displayData.paper_execution.skipped ||
                                              displayData.paper_execution.error ||
                                              JSON.stringify(displayData.paper_execution)}
                                    </p>
                                )}
                            </div>
                            <div className="card" style={{ marginBottom: 'var(--sp-lg)' }}>
                                <div className="card-header">
                                    <h3>Trader (book)</h3>
                                </div>
                                <pre
                                    style={{
                                        fontSize: '0.78rem',
                                        overflow: 'auto',
                                        maxHeight: '240px',
                                        background: 'rgba(0,0,0,0.2)',
                                        padding: 'var(--sp-md)',
                                        borderRadius: '8px',
                                    }}
                                >
                                    {JSON.stringify(displayData.trader || {}, null, 2)}
                                </pre>
                            </div>
                            <div className="dashboard-section">
                                <h3 className="section-title">Risk validation</h3>
                                <RiskPanel riskReport={displayData.risk_report} />
                            </div>
                        </>
                    )}
                </div>
            )}

            {isBookStyle && mainTab === 'stocks' && (
                <div className="fade-in">
                    {!displayData?.results && (
                        <p className="text-muted">Run a job to browse per-ticker research.</p>
                    )}
                    {displayData?.results && (
                        <>
                            <div className="tabs" style={{ marginBottom: 'var(--sp-md)' }}>
                                {tickers.map((t) => (
                                    <button
                                        key={t}
                                        type="button"
                                        className={`tab-btn ${stockTab === t ? 'active' : ''}`}
                                        onClick={() => setStockTab(t)}
                                    >
                                        {t}
                                    </button>
                                ))}
                            </div>
                            {stockTab && displayData.results[stockTab] && (
                                <TickerCard ticker={stockTab} data={displayData.results[stockTab]} />
                            )}
                        </>
                    )}
                </div>
            )}

            {!isBookStyle && (
                <>
                    <LlmStreamPanel
                        streamBlocks={streamBlocks}
                        stageLines={stageLines}
                        active={streamActive}
                    />
                    {status === 'running' &&
                        !partialResults &&
                        Object.keys(streamBlocks).length === 0 && (
                            <Spinner text="Waiting for first pipeline snapshot…" />
                        )}
                    {showLiveDashboard && (
                        <ResultsDashboard results={partialResults} isPartial />
                    )}
                    {showFailedPartial && (
                        <ResultsDashboard
                            results={partialResults}
                            isPartial
                            errorMessage={failureError}
                        />
                    )}
                    {status === 'completed' && results && (
                        <ResultsDashboard results={results} isPartial={false} />
                    )}
                </>
            )}
        </div>
    );
}
