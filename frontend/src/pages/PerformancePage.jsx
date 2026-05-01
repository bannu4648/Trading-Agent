import { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    Area,
    AreaChart,
} from 'recharts';
import {
    getPaperHistory,
    getTop20History,
    startDailyPaper,
    startDailyPaperTop20,
    getJobStatus,
    JOB_STATUS_FIRST_POLL_MS,
    JOB_STATUS_POLL_INTERVAL_MS,
} from '../api';
import Spinner from '../components/Spinner';

function pctFmt(v) {
    if (v == null || Number.isNaN(v)) return '—';
    return `${(v * 100).toFixed(2)}%`;
}

function moneyFmt(v) {
    if (v == null || Number.isNaN(v)) return '—';
    return new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
    }).format(v);
}

function sourceLabel(source) {
    if (source === 'pnl_update') return 'PnL Update';
    if (source === 'live_rebalance') return 'Live Rebalance';
    if (source === 'mtm_backfill' || source === 'paper_backtest_mtm') return 'Backfill (no rebalance)';
    if (source === 'paper_backtest_rebalance') return 'Live Rebalance';
    return source || '—';
}

function bannerTextColor(kind) {
    switch (kind) {
        case 'running':
            return 'var(--accent-cyan)';
        case 'ok':
            return 'var(--accent-green)';
        case 'warn':
            return 'var(--text-muted)';
        case 'error':
            return 'var(--accent-red)';
        default:
            return 'var(--text-secondary)';
    }
}

export default function PerformancePage() {
    const STARTING_EQUITY = 100_000;
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [rows, setRows] = useState([]);
    const [dbPath, setDbPath] = useState('');
    const [jobRunning, setJobRunning] = useState(false);
    const [paperBanner, setPaperBanner] = useState({ kind: 'none', text: '' });
    const [viewMode, setViewMode] = useState('paper');
    const [top20Rows, setTop20Rows] = useState([]);
    const [top20DbPath, setTop20DbPath] = useState('');
    const [top20JobRunning, setTop20JobRunning] = useState(false);
    const [top20Banner, setTop20Banner] = useState({ kind: 'none', text: '' });

    const pollRef = useRef(null);

    const refreshAll = useCallback(async (opts = {}) => {
        const silent = opts.silent === true;
        if (!silent) setLoading(true);
        setError(null);
        try {
            const [hist, top20Hist] = await Promise.all([getPaperHistory(5000), getTop20History(5000)]);
            setRows(hist.rows || []);
            setDbPath(hist.database || '');
            setTop20Rows(top20Hist.rows || []);
            setTop20DbPath(top20Hist.database || '');
        } catch (e) {
            setError(e.message || String(e));
        } finally {
            if (!silent) setLoading(false);
        }
    }, []);

    const startTop20DailyRun = async () => {
        setTop20JobRunning(true);
        setTop20Banner({ kind: 'running', text: 'Refreshing…' });
        try {
            const { job_id } = await startDailyPaperTop20({});
            const poll = async () => {
                try {
                    const job = await getJobStatus(job_id);
                    if (job.status === 'completed') {
                        setTop20JobRunning(false);
                        const r = job.result || {};
                        if (r.reason === 'no_top20_history') {
                            setTop20Banner({
                                kind: 'warn',
                                text: 'No Top 20 history yet — run the Top 20 pipeline first.',
                            });
                        } else if (r.reason === 'already_current') {
                            setTop20Banner({
                                kind: 'ok',
                                text: 'Success: PnL already up to date for today (UTC).',
                            });
                        } else if (Number(r.days_processed) > 0 || r.updated === true) {
                            const n = Number(r.days_processed || 0);
                            setTop20Banner({
                                kind: 'ok',
                                text:
                                    n > 0
                                        ? `Success: PnL updated for ${n} trading day${n === 1 ? '' : 's'}.`
                                        : 'Success: PnL refreshed through today (UTC).',
                            });
                        } else {
                            const detail =
                                r.last_error_detail && typeof r.last_error_detail.reason === 'string'
                                    ? r.last_error_detail.reason
                                    : r.reason || 'PnL refresh did not complete.';
                            setTop20Banner({ kind: 'error', text: `Failed: ${detail}` });
                        }
                        await refreshAll({ silent: true });
                        return;
                    }
                    if (job.status === 'failed') {
                        setTop20JobRunning(false);
                        setTop20Banner({ kind: 'error', text: `Failed: ${job.error || 'Unknown error'}` });
                        return;
                    }
                    setTimeout(poll, JOB_STATUS_POLL_INTERVAL_MS);
                } catch (e) {
                    setTop20JobRunning(false);
                    setTop20Banner({ kind: 'error', text: e.message || String(e) });
                }
            };
            setTimeout(poll, JOB_STATUS_FIRST_POLL_MS);
        } catch (e) {
            setTop20JobRunning(false);
            setTop20Banner({ kind: 'error', text: e.message || String(e) });
        }
    };

    useEffect(() => {
        refreshAll();
    }, [refreshAll]);

    useEffect(
        () => () => {
            if (pollRef.current) clearTimeout(pollRef.current);
        },
        [],
    );

    const startDailyPaperRun = async () => {
        if (pollRef.current) {
            clearTimeout(pollRef.current);
            pollRef.current = null;
        }
        setJobRunning(true);
        setPaperBanner({ kind: 'running', text: 'Refreshing…' });
        try {
            const { job_id } = await startDailyPaper({});

            const poll = async () => {
                try {
                    const job = await getJobStatus(job_id);
                    const label = job.partial_result?.pipeline_step_label;
                    if (job.status === 'running') {
                        setPaperBanner({
                            kind: 'running',
                            text: typeof label === 'string' && label ? label : 'Refreshing…',
                        });
                    }

                    if (job.status === 'completed') {
                        setJobRunning(false);
                        const r = job.result;
                        if (r?.skipped) {
                            const d = r.trade_date || 'today (UTC)';
                            setPaperBanner({
                                kind: 'ok',
                                text: `Success: PnL already recorded for ${d}; nothing to refresh.`,
                            });
                        } else {
                            const bf = Number(r?.metadata?.backfilled_days ?? 0);
                            setPaperBanner({
                                kind: 'ok',
                                text:
                                    bf > 0
                                        ? `Success: PnL refreshed; ${bf} earlier weekday${bf === 1 ? '' : 's'} backfilled.`
                                        : 'Success: PnL refreshed through today (UTC).',
                            });
                        }
                        await refreshAll({ silent: true });
                        return;
                    }
                    if (job.status === 'failed') {
                        setJobRunning(false);
                        setPaperBanner({ kind: 'error', text: `Failed: ${job.error || 'Unknown error'}` });
                        return;
                    }
                    pollRef.current = setTimeout(poll, JOB_STATUS_POLL_INTERVAL_MS);
                } catch (e) {
                    setJobRunning(false);
                    setPaperBanner({ kind: 'error', text: e.message || String(e) });
                }
            };
            pollRef.current = setTimeout(poll, JOB_STATUS_FIRST_POLL_MS);
        } catch (e) {
            setJobRunning(false);
            setPaperBanner({ kind: 'error', text: e.message || String(e) });
        }
    };

    const chartData = useMemo(
        () =>
            rows.map((r) => ({
                date: r.as_of_date,
                equity: Number(r.equity_after),
                dailyPct: r.daily_return_pct != null ? Number(r.daily_return_pct) * 100 : null,
                cumPct: r.cumulative_return_pct != null ? Number(r.cumulative_return_pct) * 100 : null,
                grossLong: r.gross_long != null ? Number(r.gross_long) * 100 : null,
                // API stores gross_short as magnitude; plot shorts as negative % of NAV
                grossShort: r.gross_short != null ? -Number(r.gross_short) * 100 : null,
                trades: r.trades_count,
                source: r.source,
            })),
        [rows],
    );

    const latest = rows.length ? rows[rows.length - 1] : null;
    const totalReturn =
        latest && STARTING_EQUITY > 0
            ? Number(latest.equity_after) / STARTING_EQUITY - 1
            : null;

    const latestHoldings = useMemo(() => {
        const hw = latest?.holdings_weights;
        if (!hw || typeof hw !== 'object') return [];
        return Object.entries(hw)
            .map(([ticker, w]) => ({ ticker, weight: Number(w) }))
            .filter((x) => Number.isFinite(x.weight) && Math.abs(x.weight) >= 1e-5)
            .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
    }, [latest]);

    const impliedCashWeight =
        latestHoldings.length > 0
            ? 1 - latestHoldings.reduce((s, x) => s + x.weight, 0)
            : null;
    const top20ChartData = useMemo(
        () =>
            top20Rows.map((r) => ({
                date: r.as_of_date,
                equity: Number(r.equity_after),
                dailyPct: r.daily_return_pct != null ? Number(r.daily_return_pct) * 100 : null,
                cumPct: r.cumulative_return_pct != null ? Number(r.cumulative_return_pct) * 100 : null,
                grossLong: r.gross_long != null ? Number(r.gross_long) * 100 : null,
                grossShort: r.gross_short != null ? -Number(r.gross_short) * 100 : null,
                trades: r.trades_count,
                source: r.source,
            })),
        [top20Rows],
    );
    const top20Latest = top20Rows.length ? top20Rows[top20Rows.length - 1] : null;
    const top20TotalReturn =
        top20Latest && STARTING_EQUITY > 0 ? Number(top20Latest.equity_after) / STARTING_EQUITY - 1 : null;
    const top20LatestHoldings = useMemo(() => {
        const hw = top20Latest?.holdings_weights;
        if (!hw || typeof hw !== 'object') return [];
        return Object.entries(hw)
            .map(([ticker, w]) => ({ ticker, weight: Number(w) }))
            .filter((x) => Number.isFinite(x.weight) && Math.abs(x.weight) >= 1e-5)
            .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
    }, [top20Latest]);
    const top20ImpliedCashWeight =
        top20LatestHoldings.length > 0 ? 1 - top20LatestHoldings.reduce((s, x) => s + x.weight, 0) : null;

    if (loading) {
        return (
            <div>
                <div className="page-header">
                    <h2>Paper performance</h2>
                    <p>Loading S&amp;P screened and Top&nbsp;20 history…</p>
                </div>
                <Spinner text="Fetching data…" />
            </div>
        );
    }

    return (
        <div>
            <div className="page-header">
                <h2>Paper performance</h2>
                <p style={{ marginBottom: 0 }}>
                    Each tab is one book. Use <strong>Refresh PnL</strong> to advance daily history through today (
                    <strong>UTC</strong>). Missed weekdays are filled automatically where supported.
                </p>
            </div>

            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                <label id="perf-tabs-label" style={{ display: 'block', marginBottom: 'var(--sp-sm)', fontWeight: 600 }}>
                    Strategy
                </label>
                <div
                    role="tablist"
                    aria-labelledby="perf-tabs-label"
                    className="segment-switch"
                    style={{ marginBottom: 'var(--sp-md)' }}
                >
                    <button
                        type="button"
                        role="tab"
                        aria-selected={viewMode === 'paper'}
                        className={`segment-switch__btn ${viewMode === 'paper' ? 'segment-switch__btn--active' : ''}`}
                        onClick={() => setViewMode('paper')}
                    >
                        S&amp;P 500 screened
                    </button>
                    <button
                        type="button"
                        role="tab"
                        aria-selected={viewMode === 'top20'}
                        className={`segment-switch__btn ${viewMode === 'top20' ? 'segment-switch__btn--active' : ''}`}
                        onClick={() => setViewMode('top20')}
                    >
                        Top 20 long / short
                    </button>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.45 }}>
                    Charts and history follow the active tab.
                </p>
            </div>

            {viewMode === 'paper' ? (
                <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                    <div className="card-header">
                        <h3>S&amp;P 500 screened — daily P&amp;L</h3>
                    </div>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: 'var(--sp-md)' }}>
                        Syncs mark-to-market through today&apos;s UTC date and backfills any intermediate weekdays before
                        recording the latest close.
                    </p>
                    <button type="button" className="btn btn-primary" onClick={startDailyPaperRun} disabled={jobRunning}>
                        {jobRunning ? 'Refreshing…' : 'Refresh PnL'}
                    </button>
                    {paperBanner.kind !== 'none' ? (
                        <p
                            style={{
                                marginTop: 'var(--sp-md)',
                                fontSize: '0.85rem',
                                color: bannerTextColor(paperBanner.kind),
                                lineHeight: 1.5,
                            }}
                        >
                            {paperBanner.text}
                        </p>
                    ) : null}
                </div>
            ) : (
                <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                    <div className="card-header">
                        <h3>Top 20 long / short — daily P&amp;L</h3>
                    </div>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: 'var(--sp-md)' }}>
                        Replays saved Top&nbsp;20 weights, then applies one mark-to-market step per missed weekday through
                        today&apos;s UTC date.
                    </p>
                    <button type="button" className="btn btn-primary" onClick={startTop20DailyRun} disabled={top20JobRunning}>
                        {top20JobRunning ? 'Refreshing…' : 'Refresh PnL'}
                    </button>
                    {top20Banner.kind !== 'none' ? (
                        <p
                            style={{
                                marginTop: 'var(--sp-md)',
                                fontSize: '0.85rem',
                                color: bannerTextColor(top20Banner.kind),
                                lineHeight: 1.5,
                            }}
                        >
                            {top20Banner.text}
                        </p>
                    ) : null}
                </div>
            )}

            {viewMode === 'paper' ? (
                <>
                    {error && (
                        <p style={{ color: 'var(--accent-red)', marginBottom: 'var(--sp-lg)' }}>
                            {error} — is the API running?
                        </p>
                    )}

                    {dbPath && (
                        <p
                            style={{
                                fontSize: '0.75rem',
                                color: 'var(--text-muted)',
                                marginBottom: 'var(--sp-lg)',
                                wordBreak: 'break-all',
                            }}
                        >
                            Database: {dbPath}
                        </p>
                    )}

                    {!rows.length && !error && (
                        <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                            <p style={{ color: 'var(--text-secondary)' }}>
                                No S&amp;P screened history rows yet. Run <strong>daily P&amp;L update</strong> above (or
                                the CLI equivalent).
                            </p>
                        </div>
                    )}

                    {!!rows.length && (
                <>
                    <div
                        className="grid-3"
                        style={{ marginBottom: 'var(--sp-xl)' }}
                    >
                        <div className="card">
                            <div className="stat">
                                <span className="stat-label">Latest equity</span>
                                <span className="stat-value">{moneyFmt(latest?.equity_after)}</span>
                            </div>
                        </div>
                        <div className="card">
                            <div className="stat">
                                <span className="stat-label">Last day return</span>
                                <span
                                    className={`stat-value ${
                                        Number(latest?.daily_return_pct) >= 0 ? 'positive' : 'negative'
                                    }`}
                                >
                                    {pctFmt(latest?.daily_return_pct)}
                                </span>
                            </div>
                        </div>
                        <div className="card">
                            <div className="stat">
                                <span className="stat-label">Total return (from $100,000)</span>
                                <span
                                    className={`stat-value ${
                                        totalReturn != null && totalReturn >= 0 ? 'positive' : 'negative'
                                    }`}
                                >
                                    {pctFmt(totalReturn)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                        <div className="card-header">
                            <h3>Latest simulated holdings</h3>
                            {latest?.as_of_date && (
                                <span className="badge badge-info">After rebalance · {latest.as_of_date}</span>
                            )}
                        </div>
                        {!latestHoldings.length && (
                            <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                                No per-ticker weights on this row (older history entries). Run a new daily paper job or
                                paper rebalance to record weights.
                            </p>
                        )}
                        {!!latestHoldings.length && (
                            <>
                                <p
                                    style={{
                                        fontSize: '0.82rem',
                                        color: 'var(--text-muted)',
                                        marginBottom: 'var(--sp-md)',
                                        lineHeight: 1.45,
                                    }}
                                >
                                    Weights are shares × last close divided by equity after the rebalance (long
                                    positive, short negative). Implied cash weight:{' '}
                                    <strong style={{ fontFamily: 'var(--font-mono)' }}>
                                        {impliedCashWeight != null && Number.isFinite(impliedCashWeight)
                                            ? pctFmt(impliedCashWeight)
                                            : '—'}
                                    </strong>
                                    .
                                </p>
                                <div style={{ overflowX: 'auto' }}>
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>Ticker</th>
                                                <th>Weight</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {latestHoldings.map((row) => (
                                                <tr key={row.ticker}>
                                                    <td style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                                                        {row.ticker}
                                                    </td>
                                                    <td
                                                        style={{
                                                            fontFamily: 'var(--font-mono)',
                                                            color:
                                                                row.weight < 0
                                                                    ? 'var(--accent-red)'
                                                                    : 'var(--accent-green)',
                                                        }}
                                                    >
                                                        {pctFmt(row.weight)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        )}
                    </div>

                    <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                        <div className="card-header">
                            <h3>Equity curve</h3>
                        </div>
                        <div style={{ width: '100%', height: 320 }}>
                            <ResponsiveContainer>
                                <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.35} />
                                            <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                    <YAxis
                                        tick={{ fontSize: 11 }}
                                        stroke="var(--text-muted)"
                                        tickFormatter={(v) =>
                                            new Intl.NumberFormat(undefined, {
                                                notation: 'compact',
                                                maximumFractionDigits: 1,
                                            }).format(v)
                                        }
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'var(--bg-card)',
                                            border: '1px solid var(--border-color)',
                                            borderRadius: 8,
                                        }}
                                        formatter={(value, name, entry) => [
                                            moneyFmt(value),
                                            `${name} · ${sourceLabel(entry?.payload?.source)}`,
                                        ]}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="equity"
                                        name="Equity"
                                        stroke="var(--accent-blue)"
                                        fill="url(#eqFill)"
                                        strokeWidth={2}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                        <div className="card-header">
                            <h3>Cumulative return (%)</h3>
                        </div>
                        <div style={{ width: '100%', height: 280 }}>
                            <ResponsiveContainer>
                                <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                    <YAxis
                                        tick={{ fontSize: 11 }}
                                        stroke="var(--text-muted)"
                                        tickFormatter={(v) => `${v.toFixed(1)}%`}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'var(--bg-card)',
                                            border: '1px solid var(--border-color)',
                                            borderRadius: 8,
                                        }}
                                        formatter={(value, name, entry) => [
                                            `${Number(value).toFixed(2)}%`,
                                            `${name} · ${sourceLabel(entry?.payload?.source)}`,
                                        ]}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="cumPct"
                                        name="Cumulative %"
                                        stroke="var(--accent-green)"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                        <div className="card-header">
                            <h3>Daily return (%)</h3>
                        </div>
                        <div style={{ width: '100%', height: 280 }}>
                            <ResponsiveContainer>
                                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                    <YAxis
                                        tick={{ fontSize: 11 }}
                                        stroke="var(--text-muted)"
                                        tickFormatter={(v) => `${v.toFixed(1)}%`}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'var(--bg-card)',
                                            border: '1px solid var(--border-color)',
                                            borderRadius: 8,
                                        }}
                                        formatter={(value, name, entry) => {
                                            if (value == null) return '—';
                                            return [
                                                `${Number(value).toFixed(2)}%`,
                                                `${name} · ${sourceLabel(entry?.payload?.source)}`,
                                            ];
                                        }}
                                    />
                                    <Bar
                                        dataKey="dailyPct"
                                        name="Daily %"
                                        fill="var(--accent-cyan)"
                                        radius={[4, 4, 0, 0]}
                                    />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                        <div className="card-header">
                            <h3>Exposure (long + / short −, % of equity)</h3>
                        </div>
                        <div style={{ width: '100%', height: 280 }}>
                            <ResponsiveContainer>
                                <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                    <YAxis
                                        tick={{ fontSize: 11 }}
                                        stroke="var(--text-muted)"
                                        tickFormatter={(v) => `${v}%`}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'var(--bg-card)',
                                            border: '1px solid var(--border-color)',
                                            borderRadius: 8,
                                        }}
                                        formatter={(value, name) => [
                                            value == null ? '—' : `${Number(value).toFixed(1)}%`,
                                            name,
                                        ]}
                                    />
                                    <Legend />
                                    <Line
                                        type="monotone"
                                        dataKey="grossLong"
                                        name="Gross long"
                                        stroke="var(--accent-green)"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="grossShort"
                                        name="Gross short"
                                        stroke="var(--accent-red)"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <h3>Daily log</h3>
                            <span className="badge badge-info">{rows.length} rows</span>
                        </div>
                        <div style={{ overflowX: 'auto' }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Equity after</th>
                                        <th>Day PnL ($)</th>
                                        <th>Daily return</th>
                                        <th>Cumulative</th>
                                        <th>Trades</th>
                                        <th>Source</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {[...rows].reverse().map((r) => (
                                        <tr
                                            key={r.as_of_date}
                                            style={
                                                r.source === 'mtm_backfill' || r.source === 'paper_backtest_mtm'
                                                    ? { background: 'rgba(99,115,146,0.08)' }
                                                    : undefined
                                            }
                                        >
                                            <td style={{ fontFamily: 'var(--font-mono)' }}>{r.as_of_date}</td>
                                            <td>{moneyFmt(r.equity_after)}</td>
                                            <td
                                                style={{
                                                    color:
                                                        r.day_pnl_dollars == null
                                                            ? 'var(--text-muted)'
                                                            : Number(r.day_pnl_dollars) < 0
                                                              ? 'var(--accent-red)'
                                                              : 'var(--accent-green)',
                                                }}
                                            >
                                                {r.day_pnl_dollars == null ? '—' : moneyFmt(r.day_pnl_dollars)}
                                            </td>
                                            <td
                                                style={{
                                                    color:
                                                        Number(r.daily_return_pct) < 0
                                                            ? 'var(--accent-red)'
                                                            : 'var(--accent-green)',
                                                }}
                                            >
                                                {pctFmt(r.daily_return_pct)}
                                            </td>
                                            <td>{pctFmt(r.cumulative_return_pct)}</td>
                                            <td>{r.trades_count}</td>
                                            <td style={{ fontSize: '0.8rem' }}>
                                                {sourceLabel(r.source)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
                    )}
                </>
            ) : (
                <>
                    {top20DbPath && (
                        <p
                            style={{
                                fontSize: '0.75rem',
                                color: 'var(--text-muted)',
                                marginBottom: 'var(--sp-lg)',
                                wordBreak: 'break-all',
                            }}
                        >
                            Database: {top20DbPath}
                        </p>
                    )}
                    {!top20Rows.length && (
                        <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                            <p style={{ color: 'var(--text-secondary)' }}>
                                No rows yet — run a Top&nbsp;20 pipeline that saves <code>top20_longshort_*.json</code>, then
                                use daily P&amp;L above so SQLite can replay the book.
                            </p>
                        </div>
                    )}
                    {!!top20Rows.length && (
                        <>
                            <div className="grid-3" style={{ marginBottom: 'var(--sp-xl)' }}>
                                <div className="card">
                                    <div className="stat">
                                        <span className="stat-label">Latest equity</span>
                                        <span className="stat-value">{moneyFmt(top20Latest?.equity_after)}</span>
                                    </div>
                                </div>
                                <div className="card">
                                    <div className="stat">
                                        <span className="stat-label">Last day return</span>
                                        <span
                                            className={`stat-value ${
                                                Number(top20Latest?.daily_return_pct) >= 0 ? 'positive' : 'negative'
                                            }`}
                                        >
                                            {pctFmt(top20Latest?.daily_return_pct)}
                                        </span>
                                    </div>
                                </div>
                                <div className="card">
                                    <div className="stat">
                                        <span className="stat-label">Total return (from $100,000)</span>
                                        <span
                                            className={`stat-value ${
                                                top20TotalReturn != null && top20TotalReturn >= 0 ? 'positive' : 'negative'
                                            }`}
                                        >
                                            {pctFmt(top20TotalReturn)}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                                <div className="card-header">
                                    <h3>Latest simulated holdings</h3>
                                </div>
                                {!top20LatestHoldings.length && (
                                    <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                                        No holdings on the latest row.
                                    </p>
                                )}
                                {!!top20LatestHoldings.length && (
                                    <>
                                        <p
                                            style={{
                                                fontSize: '0.82rem',
                                                color: 'var(--text-muted)',
                                                marginBottom: 'var(--sp-md)',
                                                lineHeight: 1.45,
                                            }}
                                        >
                                            Simulated holdings vs equity. Implied cash:{' '}
                                            <strong style={{ fontFamily: 'var(--font-mono)' }}>
                                                {top20ImpliedCashWeight != null && Number.isFinite(top20ImpliedCashWeight)
                                                    ? pctFmt(top20ImpliedCashWeight)
                                                    : '—'}
                                            </strong>
                                            .
                                        </p>
                                        <div style={{ overflowX: 'auto' }}>
                                            <table className="data-table">
                                                <thead>
                                                    <tr>
                                                        <th>Ticker</th>
                                                        <th>Weight</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {top20LatestHoldings.map((row) => (
                                                        <tr key={row.ticker}>
                                                            <td style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                                                                {row.ticker}
                                                            </td>
                                                            <td
                                                                style={{
                                                                    fontFamily: 'var(--font-mono)',
                                                                    color:
                                                                        row.weight < 0 ? 'var(--accent-red)' : 'var(--accent-green)',
                                                                }}
                                                            >
                                                                {pctFmt(row.weight)}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </>
                                )}
                            </div>
                            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                                <div className="card-header">
                                    <h3>Equity curve</h3>
                                </div>
                                <div style={{ width: '100%', height: 320 }}>
                                    <ResponsiveContainer>
                                        <AreaChart data={top20ChartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                            <YAxis tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                            <Tooltip
                                                formatter={(value, name, entry) => [
                                                    moneyFmt(value),
                                                    `${name} · ${sourceLabel(entry?.payload?.source)}`,
                                                ]}
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="equity"
                                                name="Equity"
                                                stroke="var(--accent-blue)"
                                                fillOpacity={0.25}
                                                fill="var(--accent-blue)"
                                                strokeWidth={2}
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                                <div className="card-header">
                                    <h3>Cumulative return (%)</h3>
                                </div>
                                <div style={{ width: '100%', height: 280 }}>
                                    <ResponsiveContainer>
                                        <LineChart data={top20ChartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                            <YAxis tick={{ fontSize: 11 }} stroke="var(--text-muted)" tickFormatter={(v) => `${v.toFixed(1)}%`} />
                                            <Tooltip formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Cumulative %']} />
                                            <Line type="monotone" dataKey="cumPct" name="Cumulative %" stroke="var(--accent-green)" strokeWidth={2} dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                                <div className="card-header">
                                    <h3>Daily return (%)</h3>
                                </div>
                                <div style={{ width: '100%', height: 280 }}>
                                    <ResponsiveContainer>
                                        <BarChart data={top20ChartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                            <YAxis tick={{ fontSize: 11 }} stroke="var(--text-muted)" tickFormatter={(v) => `${v.toFixed(1)}%`} />
                                            <Tooltip formatter={(value) => (value == null ? '—' : [`${Number(value).toFixed(2)}%`, 'Daily %'])} />
                                            <Bar dataKey="dailyPct" name="Daily %" fill="var(--accent-cyan)" radius={[4, 4, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                                <div className="card-header">
                                    <h3>Exposure (long + / short −, % of equity)</h3>
                                </div>
                                <div style={{ width: '100%', height: 280 }}>
                                    <ResponsiveContainer>
                                        <LineChart data={top20ChartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,115,146,0.25)" />
                                            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--text-muted)" />
                                            <YAxis tick={{ fontSize: 11 }} stroke="var(--text-muted)" tickFormatter={(v) => `${v}%`} />
                                            <Tooltip formatter={(value, name) => [value == null ? '—' : `${Number(value).toFixed(1)}%`, name]} />
                                            <Legend />
                                            <Line type="monotone" dataKey="grossLong" name="Gross long" stroke="var(--accent-green)" strokeWidth={2} dot={false} />
                                            <Line type="monotone" dataKey="grossShort" name="Gross short" stroke="var(--accent-red)" strokeWidth={2} dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                            <div className="card">
                                <div className="card-header">
                                    <h3>Daily log</h3>
                                    <span className="badge badge-info">{top20Rows.length} rows</span>
                                </div>
                                <div style={{ overflowX: 'auto' }}>
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Equity after</th>
                                                <th>Day PnL ($)</th>
                                                <th>Daily return</th>
                                                <th>Cumulative</th>
                                                <th>Trades</th>
                                                <th>Source</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {[...top20Rows].reverse().map((r) => (
                                                <tr key={r.as_of_date}>
                                                    <td style={{ fontFamily: 'var(--font-mono)' }}>{r.as_of_date}</td>
                                                    <td>{moneyFmt(r.equity_after)}</td>
                                                    <td>{r.day_pnl_dollars == null ? '—' : moneyFmt(r.day_pnl_dollars)}</td>
                                                    <td>{pctFmt(r.daily_return_pct)}</td>
                                                    <td>{pctFmt(r.cumulative_return_pct)}</td>
                                                    <td>{r.trades_count}</td>
                                                    <td style={{ fontSize: '0.8rem' }}>{sourceLabel(r.source)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </>
                    )}
                </>
            )}
        </div>
    );
}
