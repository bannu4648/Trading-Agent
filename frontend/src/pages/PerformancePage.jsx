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
    getPaperDailyStatus,
    startDailyPaper,
    generateAprilPaperSimulation, // TODO: remove this later
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
    if (source === 'mtm_backfill') return 'Backfill (no rebalance)';
    if (source === 'paper_backtest_rebalance') return 'Live Rebalance';
    if (source === 'paper_backtest_mtm') return 'Backfill (no rebalance)';
    return source || '—';
}

export default function PerformancePage() {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [rows, setRows] = useState([]);
    const [dbPath, setDbPath] = useState('');
    const [dailyStatus, setDailyStatus] = useState(null);

    const [jobRunning, setJobRunning] = useState(false);
    const [jobMessage, setJobMessage] = useState('');
    const [tradeDateOverride, setTradeDateOverride] = useState('');
    const [skipIfAlreadyRun, setSkipIfAlreadyRun] = useState(false);
    const [noLlm, setNoLlm] = useState(true);
    const [simulationRunning, setSimulationRunning] = useState(false); // TODO: remove this later
    const [simulationMessage, setSimulationMessage] = useState(''); // TODO: remove this later

    const pollRef = useRef(null);

    const refreshAll = useCallback(async (opts = {}) => {
        const silent = opts.silent === true;
        if (!silent) setLoading(true);
        setError(null);
        try {
            const [hist, st] = await Promise.all([getPaperHistory(5000), getPaperDailyStatus()]);
            setRows(hist.rows || []);
            setDbPath(hist.database || '');
            setDailyStatus(st);
        } catch (e) {
            setError(e.message || String(e));
        } finally {
            if (!silent) setLoading(false);
        }
    }, []);

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
        setJobMessage('Starting job…');
        try {
            const { job_id } = await startDailyPaper({
                tradeDate: tradeDateOverride.trim() || null,
                skipIfAlreadyRun,
                noLlm,
            });

            const poll = async () => {
                try {
                    const job = await getJobStatus(job_id);
                    const label = job.partial_result?.pipeline_step_label;
                    if (label) setJobMessage(label);
                    else if (job.status === 'running') setJobMessage('Running…');

                    if (job.status === 'completed') {
                        setJobRunning(false);
                        if (job.result?.skipped) {
                            setJobMessage(
                                `No run: already recorded for ${job.result.trade_date || dailyStatus?.today_utc}.`,
                            );
                        } else {
                            setJobMessage('Daily run finished successfully.');
                        }
                        await refreshAll({ silent: true });
                        return;
                    }
                    if (job.status === 'failed') {
                        setJobRunning(false);
                        setJobMessage(`Failed: ${job.error || 'Unknown error'}`);
                        return;
                    }
                    pollRef.current = setTimeout(poll, JOB_STATUS_POLL_INTERVAL_MS);
                } catch (e) {
                    setJobRunning(false);
                    setJobMessage(e.message || String(e));
                }
            };
            pollRef.current = setTimeout(poll, JOB_STATUS_FIRST_POLL_MS);
        } catch (e) {
            setJobRunning(false);
            setJobMessage(e.message || String(e));
        }
    };
// TODO: remove this later
    const runAprilSimulation = async () => {
        setSimulationRunning(true);
        setSimulationMessage('Generating April simulation…');
        setError(null);
        try {
            const payload = await generateAprilPaperSimulation();
            const rows = payload?.summary?.history_rows;
            const files = payload?.summary?.result_files;
            setSimulationMessage(
                `April simulation regenerated${rows ? ` (${rows} rows` : ''}${files ? `, ${files} result files` : ''}.`,
            );
            await refreshAll({ silent: true });
        } catch (e) {
            setSimulationMessage(`Failed: ${e.message || String(e)}`);
        } finally {
            setSimulationRunning(false);
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
                grossShort: r.gross_short != null ? Number(r.gross_short) * 100 : null,
                trades: r.trades_count,
                source: r.source,
            })),
        [rows],
    );

    const latest = rows.length ? rows[rows.length - 1] : null;
    const first = rows.length ? rows[0] : null;
    const totalReturn =
        first && latest && Number(first.equity_after) > 0
            ? Number(latest.equity_after) / Number(first.equity_after) - 1
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

    if (loading) {
        return (
            <div>
                <div className="page-header">
                    <h2>Paper portfolio performance</h2>
                    <p>Loading history and today&apos;s run status…</p>
                </div>
                <Spinner text="Fetching data…" />
            </div>
        );
    }

    const todayUtc = dailyStatus?.today_utc;
    const hasToday = dailyStatus?.has_run_today;

    return (
        <div>
{/* TODO: start removing from here later */}
            <div
                style={{
                    position: 'fixed',
                    right: '24px',
                    bottom: '24px',
                    zIndex: 50,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-end',
                    gap: 'var(--sp-xs)',
                }}
            >
                {simulationMessage && (
                    <div
                        style={{
                            maxWidth: '280px',
                            padding: '8px 12px',
                            borderRadius: '8px',
                            background: 'rgba(15,23,42,0.92)',
                            border: '1px solid rgba(148,163,184,0.25)',
                            color: simulationMessage.startsWith('Failed') ? 'var(--accent-red)' : 'var(--text-secondary)',
                            fontSize: '0.78rem',
                            boxShadow: 'var(--shadow-md)',
                        }}
                    >
                        {simulationMessage}
                    </div>
                )}
                <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={runAprilSimulation}
                    disabled={simulationRunning || jobRunning}
                    style={{
                        boxShadow: 'var(--shadow-lg)',
                        border: '1px solid rgba(59,130,246,0.35)',
                    }}
                >
                    {simulationRunning ? 'Generating April…' : 'Generate April simulation'}
                </button>
            </div>
{/* remove till here later */}
            <div className="page-header">
                <h2>Paper portfolio performance</h2>
                <p>
                    Track the simulated paper book over time. Run the <strong>full daily S&amp;P 500 pipeline</strong>{' '}
                    from this page (same as <code>run_daily_paper_trade.py</code>), or use the CLI. Status uses{' '}
                    <strong>UTC calendar date</strong> to match the backend.
                </p>
            </div>

            <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
                <div className="card-header">
                    <h3>Daily paper run</h3>
                    {todayUtc && (
                        <span
                            className={`badge ${hasToday ? 'badge-info' : ''}`}
                            style={
                                hasToday
                                    ? {
                                          background: 'var(--accent-green-soft)',
                                          color: 'var(--accent-green)',
                                      }
                                    : {
                                          background: 'var(--accent-yellow-soft)',
                                          color: 'var(--accent-yellow)',
                                      }
                            }
                        >
                            {hasToday
                                ? `Recorded for ${todayUtc} (UTC)`
                                : `Not yet run for ${todayUtc} (UTC)`}
                        </span>
                    )}
                </div>
                {hasToday && dailyStatus?.today_row && (
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 'var(--sp-md)' }}>
                        Last equity (after rebalance):{' '}
                        <strong>{moneyFmt(dailyStatus.today_row.equity_after)}</strong> · source{' '}
                        <code>{dailyStatus.today_row.source}</code> · trades{' '}
                        {dailyStatus.today_row.trades_count}
                    </p>
                )}
                <div
                    style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 'var(--sp-md)',
                        alignItems: 'flex-end',
                        marginBottom: 'var(--sp-md)',
                    }}
                >
                    <div className="input-group" style={{ minWidth: '160px' }}>
                        <label htmlFor="daily-date">Trade date (optional)</label>
                        <input
                            id="daily-date"
                            className="input-field"
                            type="text"
                            placeholder={`Blank = ${todayUtc || 'UTC today'}`}
                            value={tradeDateOverride}
                            onChange={(e) => setTradeDateOverride(e.target.value)}
                            disabled={jobRunning}
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
                            checked={skipIfAlreadyRun}
                            onChange={(e) => setSkipIfAlreadyRun(e.target.checked)}
                            disabled={jobRunning}
                        />
                        Skip if this date already in table
                    </label>
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
                            checked={noLlm}
                            onChange={(e) => setNoLlm(e.target.checked)}
                            disabled={jobRunning}
                        />
                        Formula only (no LLM) — recommended for daily
                    </label>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-md)', alignItems: 'center' }}>
                    <button
                        type="button"
                        className="btn btn-primary"
                        onClick={startDailyPaperRun}
                        disabled={jobRunning}
                    >
                        {jobRunning ? 'Running…' : 'Start daily paper job'}
                    </button>
                    <button
                        type="button"
                        className="btn"
                        onClick={() => refreshAll({ silent: true })}
                        disabled={jobRunning}
                    >
                        Refresh status &amp; charts
                    </button>
                </div>
                {jobMessage && (
                    <p
                        style={{
                            marginTop: 'var(--sp-md)',
                            fontSize: '0.85rem',
                            color: 'var(--accent-cyan)',
                        }}
                    >
                        {jobMessage}
                    </p>
                )}
                <p
                    style={{
                        marginTop: 'var(--sp-md)',
                        fontSize: '0.75rem',
                        color: 'var(--text-muted)',
                        lineHeight: 1.5,
                    }}
                >
                    <strong>No automatic schedule</strong> — this only runs when you click the button (or use the CLI).
                    The server runs the pipeline and writes one row per trade date to SQLite (<code>paper_daily</code>);
                    charts and the table below read from that database (returns and dollar day-PnL are derived from
                    stored equity). Large universes can take many minutes; the UI polls job status until it finishes.
                    Re-running the same UTC date overwrites that row.
                </p>
            </div>

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
                        No history rows yet. Start a <strong>Daily paper run</strong> above, or use the CLI / Top 20
                        paper rebalance.
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
                                <span className="stat-label">Total return (series)</span>
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
                            <h3>Exposure (gross long / short % of equity)</h3>
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
        </div>
    );
}
