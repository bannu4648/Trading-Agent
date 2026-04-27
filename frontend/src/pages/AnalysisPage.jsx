import { useState, useRef, useCallback, useEffect, useLayoutEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAnalysisSession } from '../context/AnalysisSessionContext';
import {
    startAnalysis,
    startTop20LongShort,
    startSp500Screened,
    getJobStatus,
    consumeJobStream,
    listResults,
    getResult,
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
            'Run analysis on your own tickers and review the recommendation in detail. Best for focused research.',
    },
    top20: {
        id: 'top20',
        label: 'Top 20 long / short',
        shortLabel: 'Top 20',
        icon: '⚖️',
        description:
            'Use a fixed large-cap universe and build a balanced long/short book with risk checks.',
    },
    sp500: {
        id: 'sp500',
        label: 'S&P 500 screened',
        shortLabel: 'S&P 500',
        icon: '📈',
        description:
            'Screen the S&P 500, shortlist candidates, and run deep analysis before allocation and validation.',
    },
};

const PIPELINE_PHASES = [
    { key: 'technical', label: 'Technical analysis' },
    { key: 'research', label: 'Sentiment and fundamentals' },
    { key: 'synthesis', label: 'Synthesis' },
    { key: 'trader', label: 'Trader sizing' },
    { key: 'validation', label: 'Risk validation' },
];

const STEP_INDEX = {
    init: 0,
    technical: 0,
    technical_wide: 0,
    screen: 0,
    research: 1,
    synthesis: 2,
    risk_portfolio: 3,
    trader: 3,
    validation: 4,
    paper: 4,
};

function emptyFlowViewState() {
    return {
        status: 'idle',
        statusMsg: '',
        results: null,
        partialResults: null,
        failureError: null,
        streamBlocks: {},
        stageLines: [],
        streamError: null,
        activeJobId: null,
        latestJobId: null,
        mainTab: 'live',
        stockTab: '',
        rawEvents: [],
    };
}

export default function AnalysisPage() {
    const { session, mergeSession, clearSession } = useAnalysisSession();
    const [searchParams, setSearchParams] = useSearchParams();
    const modeParam = searchParams.get('mode');
    const quickRunParam = searchParams.get('quickrun');
    const quickRunView = quickRunParam === '1';
    const [pipelineMode, setPipelineMode] = useState(() => {
        const m = modeParam;
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
    const [latestJobId, setLatestJobId] = useState(null);
    const [developerMode, setDeveloperMode] = useState(false);
    const [optionalOpen, setOptionalOpen] = useState(false);
    const [rawEvents, setRawEvents] = useState([]);
    const [latestSavedPortfolio, setLatestSavedPortfolio] = useState(null);

    const pollRef = useRef(null);
    const streamAbortRef = useRef(null);
    const hydratedFromSessionRef = useRef(false);
    const quickRunTriggeredRef = useRef(false);
    const flowViewsRef = useRef({
        custom: emptyFlowViewState(),
        top20: emptyFlowViewState(),
        sp500: emptyFlowViewState(),
    });
    const prevModeRef = useRef(pipelineMode);
    const pipelineModeRef = useRef(pipelineMode);
    pipelineModeRef.current = pipelineMode;

    const applyFlowView = useCallback((view) => {
        setStatus(view.status);
        setStatusMsg(view.statusMsg);
        setResults(view.results);
        setPartialResults(view.partialResults);
        setFailureError(view.failureError);
        setStreamBlocks(view.streamBlocks);
        setStageLines(view.stageLines);
        setStreamError(view.streamError);
        setActiveJobId(view.activeJobId);
        setLatestJobId(view.latestJobId);
        setMainTab(view.mainTab);
        setStockTab(view.stockTab);
        setRawEvents(view.rawEvents);
    }, []);

    const snapshotFlowView = useCallback(() => ({
        status,
        statusMsg,
        results,
        partialResults,
        failureError,
        streamBlocks,
        stageLines,
        streamError,
        activeJobId,
        latestJobId,
        mainTab,
        stockTab,
        rawEvents,
    }), [
        status,
        statusMsg,
        results,
        partialResults,
        failureError,
        streamBlocks,
        stageLines,
        streamError,
        activeJobId,
        latestJobId,
        mainTab,
        stockTab,
        rawEvents,
    ]);

    const switchPipelineMode = useCallback((nextMode) => {
        if (!nextMode || nextMode === pipelineMode) return;
        flowViewsRef.current[pipelineMode] = snapshotFlowView();
        const nextView = flowViewsRef.current[nextMode] || emptyFlowViewState();
        applyFlowView(nextView);
        setPipelineMode(nextMode);
        prevModeRef.current = nextMode;
    }, [pipelineMode, snapshotFlowView, applyFlowView]);

    useLayoutEffect(() => {
        if (hydratedFromSessionRef.current) return;
        hydratedFromSessionRef.current = true;
        const routeMode = modeParam;
        const isRouteModeValid = routeMode === 'custom' || routeMode === 'top20' || routeMode === 'sp500';
        if (!session) return;
        const hasPayload =
            session.results != null ||
            session.partialResults != null ||
            (session.status && session.status !== 'idle') ||
            (session.flowViews &&
                ['custom', 'top20', 'sp500'].some((mode) => {
                    const view = session.flowViews?.[mode];
                    return Boolean(
                        view &&
                            (view.results != null ||
                                view.partialResults != null ||
                                (view.status && view.status !== 'idle')),
                    );
                }));
        if (!hasPayload) return;

        const baseFlowViews = {
            custom: emptyFlowViewState(),
            top20: emptyFlowViewState(),
            sp500: emptyFlowViewState(),
        };
        const sessionFlowViews = session.flowViews && typeof session.flowViews === 'object'
            ? session.flowViews
            : {};
        flowViewsRef.current = { ...baseFlowViews, ...sessionFlowViews };

        if (isRouteModeValid) {
            setPipelineMode(routeMode);
            prevModeRef.current = routeMode;
        } else if (session.pipelineMode) {
            setPipelineMode(session.pipelineMode);
            prevModeRef.current = session.pipelineMode;
        }
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
        if (session.developerMode != null) setDeveloperMode(Boolean(session.developerMode));
        if (session.streamBlocks != null) setStreamBlocks(session.streamBlocks);
        if (session.stageLines != null) setStageLines(session.stageLines);
        if (session.rawEvents != null) setRawEvents(session.rawEvents);
        if (session.streamError != null) setStreamError(session.streamError);

        const targetMode = isRouteModeValid
            ? routeMode
            : session.pipelineMode === 'custom' || session.pipelineMode === 'top20' || session.pipelineMode === 'sp500'
              ? session.pipelineMode
              : 'custom';
        const flowView = flowViewsRef.current[targetMode];
        if (flowView) {
            applyFlowView({
                ...emptyFlowViewState(),
                ...flowView,
            });
            return;
        }

        const resumeJobId = session.activeJobId || session.latestJobId || null;
        if (session.status === 'running' && resumeJobId) {
            setResults(session.results ?? null);
            setPartialResults(session.partialResults ?? null);
            setFailureError(session.failureError ?? null);
            setActiveJobId(resumeJobId);
            setLatestJobId(resumeJobId);
            setStatus('running');
            setStatusMsg(
                session.statusMsg ||
                    'Resuming status polls for a run that was in progress…',
            );
        } else if (session.status === 'running') {
            setResults(session.results ?? null);
            setPartialResults(session.partialResults ?? null);
            setFailureError(null);
            setActiveJobId(null);
            // Avoid a false "failed" state if navigation happened before job_id was persisted.
            // Keep whatever partial snapshot exists, but let users start a fresh run.
            setStatus('idle');
            setStatusMsg(
                session.partialResults || session.results
                    ? 'A previous run snapshot was restored. If needed, start a new run to continue.'
                    : '',
            );
        } else {
            setStatus(session.status ?? 'idle');
            setStatusMsg(session.statusMsg ?? '');
            setResults(session.results ?? null);
            setPartialResults(session.partialResults ?? null);
            setFailureError(session.failureError ?? null);
            setActiveJobId(null);
            setLatestJobId(session.latestJobId ?? null);
        }
    }, [session, modeParam, applyFlowView]);

    useEffect(() => {
        const m = modeParam;
        if ((m === 'custom' || m === 'top20' || m === 'sp500') && m !== pipelineMode) {
            switchPipelineMode(m);
        }
    }, [modeParam, pipelineMode, switchPipelineMode]);

    useEffect(() => {
        if (prevModeRef.current !== pipelineMode) {
            flowViewsRef.current[prevModeRef.current] = snapshotFlowView();
            const nextView = flowViewsRef.current[pipelineMode] || emptyFlowViewState();
            applyFlowView(nextView);
            prevModeRef.current = pipelineMode;
        }
    }, [pipelineMode, snapshotFlowView, applyFlowView]);

    useEffect(() => {
        // Developer route defaults for manual S&P500 run (no quickrun):
        // keep these aligned with landing-page quick run defaults.
        if (modeParam !== 'sp500' || quickRunParam === '1') return;
        setUseLlmInterpret(true);
        setEnableLlmSummaryTechnical(false);
        setExecutePaper(true);
        setPaperForce(true);
        setMaxCandidates(30);
        setLimitUniverse(0);
    }, [modeParam, quickRunParam]);

    useEffect(() => {
        const currentFlowSnapshot = snapshotFlowView();
        flowViewsRef.current[pipelineMode] = currentFlowSnapshot;
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
            developerMode,
            status,
            statusMsg,
            results,
            partialResults,
            failureError,
            streamBlocks,
            stageLines,
            rawEvents,
            streamError,
            activeJobId,
            latestJobId,
            flowViews: {
                ...flowViewsRef.current,
                [pipelineMode]: currentFlowSnapshot,
            },
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
        developerMode,
        status,
        statusMsg,
        results,
        partialResults,
        failureError,
        streamBlocks,
        stageLines,
        rawEvents,
        streamError,
        activeJobId,
        latestJobId,
        snapshotFlowView,
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
            switchPipelineMode(mode);
            setSearchParams({ mode });
        },
        [status, setSearchParams, switchPipelineMode],
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
        const step = m.pipeline_step || '';
        const rd = m.research_done;
        const rt = m.research_total;
        const researchExtra =
            rd != null && rt != null ? ` (${rd}/${rt} tickers)` : '';
        if (mode === 'sp500' && m.pipeline_step) {
            const statusByStep = {
                screen: 'Screening the S&P500 universe and ranking candidates.',
                technical_wide: 'Running wide technical pass to build the shortlist.',
                technical: 'Running technical analysis on shortlisted names.',
                research: `Collecting sentiment and fundamentals${researchExtra}.`,
                synthesis: 'Synthesizing ticker research into strategy-ready summaries.',
                risk_portfolio: 'Sizing the allocator book and preparing target weights.',
                trader: 'Preparing trader sizing and final execution outputs.',
                validation: 'Running portfolio risk checks and compliance guards.',
                paper: 'Writing paper portfolio state and finishing the run.',
            };
            return `${statusByStep[step] || `${label} [${step}]`} Next update in ~10s.`;
        }
        return `${label}${researchExtra} — next poll ~10s.`;
    }, []);

    const handleRun = useCallback(async (overrides = {}) => {
        if (pollRef.current) {
            clearTimeout(pollRef.current);
            pollRef.current = null;
        }
        if (streamAbortRef.current) {
            streamAbortRef.current.abort();
            streamAbortRef.current = null;
        }

        const effectiveMode = overrides.mode || pipelineMode;
        const effectiveTickerInput = overrides.tickerInput ?? tickerInput;
        const effectiveEndDate = overrides.endDate ?? endDate;
        const effectiveUseLlmInterpret = overrides.useLlmInterpret ?? useLlmInterpret;
        const effectiveEnableLlmSummaryTechnical =
            overrides.enableLlmSummaryTechnical ?? enableLlmSummaryTechnical;
        const effectiveMaxCandidates = overrides.maxCandidates ?? maxCandidates;
        const effectiveLimitUniverse = overrides.limitUniverse ?? limitUniverse;
        const effectiveExecutePaper = overrides.executePaper ?? executePaper;
        const effectivePaperForce = overrides.paperForce ?? paperForce;

        if (effectiveMode === 'custom') {
            const tickers = effectiveTickerInput
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
        setRawEvents([]);
        setStreamError(null);
        setMainTab('live');
        setActiveJobId(null);
        setLatestJobId(null);

        const modeMeta = PIPELINE_MODES[effectiveMode];
        setStatusMsg(`Starting ${modeMeta.label}…`);

        try {
            let job_id;

            if (effectiveMode === 'custom') {
                const tickers = effectiveTickerInput
                    .split(',')
                    .map((t) => t.trim().toUpperCase())
                    .filter(Boolean);
                ({ job_id } = await startAnalysis(tickers));
            } else if (effectiveMode === 'top20') {
                ({ job_id } = await startTop20LongShort({
                    endDate: effectiveEndDate.trim() || null,
                    useLlmInterpret: effectiveUseLlmInterpret,
                    executePaper: effectiveExecutePaper,
                    paperForce: effectivePaperForce,
                }));
            } else {
                ({ job_id } = await startSp500Screened({
                    endDate: effectiveEndDate.trim() || null,
                    useLlmInterpret: effectiveUseLlmInterpret,
                    enableLlmSummaryTechnical: effectiveEnableLlmSummaryTechnical,
                    maxCandidates: effectiveMaxCandidates || 30,
                    limitUniverse: effectiveLimitUniverse || 0,
                    executePaper: effectiveExecutePaper,
                    paperForce: effectivePaperForce,
                }));
            }

            setActiveJobId(job_id);
            setLatestJobId(job_id);
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
        const quickRun = quickRunParam;
        const mode = modeParam;
        if (quickRun !== '1' || mode !== 'sp500' || quickRunTriggeredRef.current) return;
        if (status !== 'idle') return;
        quickRunTriggeredRef.current = true;

        // Quick launcher defaults
        setPipelineMode('sp500');
        setMaxCandidates(30);
        setUseLlmInterpret(true);
        setExecutePaper(true);
        setPaperForce(true);
        setStatusMsg('Starting quick S&P500 screened run...');

        handleRun({
            mode: 'sp500',
            maxCandidates: 30,
            useLlmInterpret: true,
            executePaper: true,
            paperForce: true,
        });
    }, [quickRunParam, modeParam, status, handleRun]);

    useEffect(() => {
        (async () => {
            try {
                const entries = await listResults();
                const candidates = (entries || [])
                    .filter((entry) => /^(sp500_screened_|top20_longshort_)/.test(entry.filename))
                    .sort((a, b) => String(b.generated_at || '').localeCompare(String(a.generated_at || '')));
                if (candidates.length === 0) {
                    setLatestSavedPortfolio(null);
                    return;
                }
                const latest = await getResult(candidates[0].filename);
                const weights = latest?.target_weights || {};
                if (Object.keys(weights).length === 0) {
                    setLatestSavedPortfolio(null);
                    return;
                }
                setLatestSavedPortfolio({
                    filename: candidates[0].filename,
                    generated_at: candidates[0].generated_at,
                    target_weights: weights,
                });
            } catch {
                setLatestSavedPortfolio(null);
            }
        })();
    }, []);

    useEffect(() => {
        if (status !== 'running' || !activeJobId) return;

        const streamEventHandler = (ev) => {
            if (!ev || typeof ev !== 'object') return;
            setRawEvents((prev) => [...prev, ev].slice(-200));
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
        };
        const ac = new AbortController();
        streamAbortRef.current = ac;
        consumeJobStream(
            activeJobId,
            streamEventHandler,
            ac.signal,
            (err) => setStreamError(err.message || String(err)),
        );

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
    const currentStepKey = displayData?.metadata?.pipeline_step || null;
    const currentStepIndex = STEP_INDEX[currentStepKey] ?? -1;
    const phaseDetails = PIPELINE_PHASES.map((phase, index) => {
        let state = 'pending';
        if (status === 'completed' || index < currentStepIndex) state = 'done';
        else if (index === currentStepIndex && status === 'running') state = 'running';
        return { ...phase, state };
    });
    const runningPhase = phaseDetails.find((phase) => phase.state === 'running') || null;
    const doneCount = phaseDetails.filter((phase) => phase.state === 'done').length;
    const progressPercent =
        status === 'completed'
            ? 100
            : Math.round(
                  ((doneCount + (runningPhase ? 0.5 : 0)) / Math.max(PIPELINE_PHASES.length, 1)) * 100,
              );
    const currentStageText =
        status === 'running'
            ? runningPhase
                ? `${runningPhase.label} in progress`
                : displayData?.metadata?.pipeline_step_label || 'Pipeline running...'
            : displayData?.metadata?.pipeline_step_label || '';
    const canClearStream = Object.keys(streamBlocks).length > 0 || stageLines.length > 0 || rawEvents.length > 0;

    const clearLlmOnly = useCallback(() => {
        setStreamBlocks({});
        setStageLines([]);
        setRawEvents([]);
        setStreamError(null);
    }, []);

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
        setLatestJobId(null);
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
                            Choose a flow and run it. Use the optional settings only when you need finer control.
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
                                Clears the current run view.
                            </p>
                        </div>
                    )}
                </div>
            </div>

            {!quickRunView && (
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
                <div className="pipeline-mode-section active">
                    <p className="pipeline-mode-section-title">
                        <span className="pipeline-mode-btn-icon">{modeInfo.icon}</span> {modeInfo.label}
                    </p>
                    <p className="pipeline-mode-section-desc">{modeInfo.description}</p>
                </div>

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

                    {pipelineMode === 'top20' && (
                        <div
                            className="analysis-form book-form"
                        >
                            <div className="input-group" style={{ minWidth: '220px' }}>
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
                            <label className="option-check">
                                <input
                                    type="checkbox"
                                    checked={useLlmInterpret}
                                    onChange={(e) => setUseLlmInterpret(e.target.checked)}
                                    disabled={runDisabled}
                                />
                                LLM interpret (adapter)
                            </label>
                            <label className="option-check">
                                <input
                                    type="checkbox"
                                    checked={executePaper}
                                    onChange={(e) => setExecutePaper(e.target.checked)}
                                    disabled={runDisabled}
                                />
                                Paper rebalance after validation
                            </label>
                            <label className="option-check" style={{ opacity: executePaper ? 1 : 0.5 }}>
                                <input
                                    type="checkbox"
                                    checked={paperForce}
                                    onChange={(e) => setPaperForce(e.target.checked)}
                                    disabled={runDisabled || !executePaper}
                                />
                                Force even if risk HIGH
                            </label>
                            <button
                                type="button"
                                className="btn btn-primary"
                                onClick={handleRun}
                                disabled={runDisabled}
                            >
                                {runDisabled ? 'Running…' : 'Run Top 20 long/short'}
                            </button>
                        </div>
                    )}
                    {pipelineMode === 'sp500' && (
                        <div className="analysis-form sp500-priority-form">
                            <div className="input-group">
                                <label htmlFor="max-cand">Max candidates</label>
                                <input
                                    id="max-cand"
                                    className="input-field"
                                    type="number"
                                    min={5}
                                    max={200}
                                    value={maxCandidates}
                                    onChange={(e) => setMaxCandidates(Number(e.target.value) || 30)}
                                    disabled={runDisabled}
                                />
                            </div>
                            <div className="sp500-check-grid">
                                <label className="option-check">
                                    <input
                                        type="checkbox"
                                        checked={useLlmInterpret}
                                        onChange={(e) => setUseLlmInterpret(e.target.checked)}
                                        disabled={runDisabled}
                                    />
                                    Use LLM interpretation (richer reasoning)
                                </label>
                                <label className="option-check">
                                    <input
                                        type="checkbox"
                                        checked={executePaper}
                                        onChange={(e) => setExecutePaper(e.target.checked)}
                                        disabled={runDisabled}
                                    />
                                    Apply paper rebalance after validation
                                </label>
                                <label className="option-check" style={{ opacity: executePaper ? 1 : 0.5 }}>
                                    <input
                                        type="checkbox"
                                        checked={paperForce}
                                        onChange={(e) => setPaperForce(e.target.checked)}
                                        disabled={runDisabled || !executePaper}
                                    />
                                    Run rebalance even when risk is HIGH
                                </label>
                            </div>
                            <div className="sp500-run-action">
                                <button
                                    type="button"
                                    className="btn btn-primary"
                                    onClick={handleRun}
                                    disabled={runDisabled}
                                >
                                    {runDisabled ? 'Running…' : 'Run S&P 500 screened'}
                                </button>
                            </div>

                            <div className="sp500-optional-wrap">
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setOptionalOpen((v) => !v)}
                                    disabled={runDisabled}
                                >
                                    {optionalOpen ? 'Hide optional settings' : 'Show optional settings'}
                                </button>
                                {optionalOpen && (
                                    <div className="sp500-optional-panel">
                                        <div className="input-group">
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
                                        <div className="input-group">
                                            <label htmlFor="lim-uni">Limit universe (debug)</label>
                                            <input
                                                id="lim-uni"
                                                className="input-field"
                                                type="number"
                                                min={0}
                                                max={503}
                                                value={limitUniverse}
                                                onChange={(e) => setLimitUniverse(Number(e.target.value) || 0)}
                                                disabled={runDisabled}
                                            />
                                            <span className="input-help">
                                                Use <strong>0</strong> for full list.
                                            </span>
                                        </div>
                                        <label className="option-check">
                                            <input
                                                type="checkbox"
                                                checked={developerMode}
                                                onChange={(e) => setDeveloperMode(e.target.checked)}
                                                disabled={runDisabled}
                                            />
                                            Developer mode (show live raw JSON stream)
                                        </label>
                                        <label className="option-check">
                                            <input
                                                type="checkbox"
                                                checked={enableLlmSummaryTechnical}
                                                onChange={(e) => setEnableLlmSummaryTechnical(e.target.checked)}
                                                disabled={runDisabled}
                                            />
                                            Technical LLM on ~500 (expensive)
                                        </label>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {statusMsg && status !== 'running' && (
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
            )}

            {(status === 'running' || status === 'completed' || status === 'failed') && (
                <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                    <div className="card-header">
                        <h3>Pipeline journey</h3>
                        {currentStepKey && <span className="badge badge-info">{currentStepKey}</span>}
                    </div>
                    {status === 'running' && (
                        <p
                            style={{
                                marginBottom: 'var(--sp-md)',
                                fontSize: '0.85rem',
                                color: 'var(--text-secondary)',
                            }}
                        >
                            <strong>Current stage:</strong> {currentStageText}
                        </p>
                    )}
                    {status === 'running' && (
                        <div className="journey-progress-wrap" aria-label="Pipeline progress">
                            <div className="journey-progress-track">
                                <div
                                    className="journey-progress-fill"
                                    style={{ width: `${Math.max(progressPercent, 5)}%` }}
                                />
                            </div>
                            <span className="journey-progress-text">{progressPercent}%</span>
                        </div>
                    )}
                    {status === 'failed' && displayData?.metadata?.pipeline_step_label && (
                        <p
                            style={{
                                marginBottom: 'var(--sp-md)',
                                fontSize: '0.85rem',
                                color: 'var(--accent-red)',
                            }}
                        >
                            <strong>Last stage:</strong> {displayData.metadata.pipeline_step_label}
                        </p>
                    )}
                    <div className="phase-track">
                        {phaseDetails.map((phase, idx) => (
                            <div key={phase.key} className={`phase-step ${phase.state}`}>
                                <span className="phase-dot">{idx + 1}</span>
                                <span className="phase-label">{phase.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {isBookStyle && (
                <div className="tabs" style={{ marginBottom: 'var(--sp-lg)' }}>
                    {tabBtn('live', 'Live run')}
                    {tabBtn('portfolio', 'Portfolio allocation')}
                    {tabBtn('stocks', 'Per stock')}
                </div>
            )}

            {isBookStyle && mainTab === 'live' && (
                <>
                    {developerMode && (
                        <LlmStreamPanel
                            streamBlocks={streamBlocks}
                            stageLines={stageLines}
                            active={streamActive}
                            onClear={clearLlmOnly}
                            canClear={canClearStream}
                            developerMode={developerMode}
                            rawJson={displayData}
                            rawEvents={rawEvents}
                        />
                    )}
                    {status === 'running' &&
                        !partialResults &&
                        Object.keys(streamBlocks).length === 0 &&
                        !developerMode && (
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
                                <RiskPanel
                                    riskReport={displayData.risk_report}
                                    isPartial={status === 'running'}
                                />
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
                                    (() => {
                                        const w = Number(displayData?.target_weights?.[t] ?? 0);
                                        const isLong = w > 1e-6;
                                        const isShort = w < -1e-6;
                                        const tickerStyle =
                                            status === 'running' && (isLong || isShort)
                                                ? {
                                                      border: `1px solid ${
                                                          isLong ? 'rgba(16,185,129,0.65)' : 'rgba(239,68,68,0.65)'
                                                      }`,
                                                      borderRadius: '8px',
                                                      background: isLong
                                                          ? 'rgba(16,185,129,0.12)'
                                                          : 'rgba(239,68,68,0.12)',
                                                  }
                                                : {};
                                        return (
                                    <button
                                        key={t}
                                        type="button"
                                        className={`tab-btn ${stockTab === t ? 'active' : ''}`}
                                        onClick={() => setStockTab(t)}
                                        style={tickerStyle}
                                    >
                                        {t}
                                    </button>
                                        );
                                    })()
                                ))}
                            </div>
                            {stockTab && displayData.results[stockTab] && (
                                <TickerCard
                                    ticker={stockTab}
                                    data={displayData.results[stockTab]}
                                    isCustomView={false}
                                    isPartial={status === 'running'}
                                />
                            )}
                        </>
                    )}
                </div>
            )}

            {!isBookStyle && (
                <>
                    {developerMode && (
                        <LlmStreamPanel
                            streamBlocks={streamBlocks}
                            stageLines={stageLines}
                            active={streamActive}
                            onClear={clearLlmOnly}
                            canClear={canClearStream}
                            developerMode={developerMode}
                            rawJson={displayData}
                            rawEvents={rawEvents}
                        />
                    )}
                    {status === 'running' &&
                        !partialResults &&
                        Object.keys(streamBlocks).length === 0 &&
                        !developerMode && (
                            <Spinner text="Waiting for first pipeline snapshot…" />
                        )}
                    {showLiveDashboard && (
                        <ResultsDashboard
                            results={partialResults}
                            isPartial
                            latestSavedPortfolio={latestSavedPortfolio}
                        />
                    )}
                    {showFailedPartial && (
                        <ResultsDashboard
                            results={partialResults}
                            isPartial
                            errorMessage={failureError}
                            latestSavedPortfolio={latestSavedPortfolio}
                        />
                    )}
                    {status === 'completed' && results && (
                        <ResultsDashboard
                            results={results}
                            isPartial={false}
                            latestSavedPortfolio={latestSavedPortfolio}
                        />
                    )}
                </>
            )}
        </div>
    );
}
