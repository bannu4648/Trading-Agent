import { useState } from 'react';
import PortfolioChart from './PortfolioChart';
import TickerCard from './TickerCard';
import RiskPanel from './RiskPanel';
import SignalBadge from './SignalBadge';

function chipStyle(longSide) {
    return {
        display: 'inline-block',
        padding: '0.2rem 0.55rem',
        borderRadius: '6px',
        fontSize: '0.78rem',
        fontFamily: 'var(--font-mono)',
        fontWeight: 600,
        background: longSide ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
        color: longSide ? 'var(--accent-green)' : 'var(--accent-red)',
        border: `1px solid ${longSide ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.35)'}`,
    };
}

const chipRowStyle = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.35rem',
    alignItems: 'center',
    lineHeight: 1.5,
};

export default function ResultsDashboard({ results, isPartial = false, errorMessage = null }) {
    const tickers = results?.metadata?.tickers || Object.keys(results?.results || {});
    const trader = results?.trader || {};
    const riskReport = results?.risk_report || null;
    const stepLabel = results?.metadata?.pipeline_step_label || '';
    const stepKey = results?.metadata?.pipeline_step || '';
    const md = results?.metadata || {};
    const sp500Explain = md.universe === 'sp500_screened';
    const top20Explain = md.universe === 'top20_longshort';
    const bookStyleRun = sp500Explain || top20Explain;
    const tw = results?.target_weights || {};

    const bookedTickersRaw = bookStyleRun
        ? Array.isArray(md.booked_tickers) && md.booked_tickers.length > 0
            ? md.booked_tickers
            : tickers.filter((t) => Math.abs(Number(tw[t] || 0)) >= 1e-4)
        : tickers;
    const bookedTickers = bookStyleRun
        ? [...bookedTickersRaw].sort(
              (a, b) => Math.abs(Number(tw[b] || 0)) - Math.abs(Number(tw[a] || 0)),
          )
        : tickers;

    const longScreen = md.screened_long_tickers;
    const shortScreen = md.screened_short_tickers;
    const hl = Math.ceil(tickers.length / 2);
    const longIdeas =
        Array.isArray(longScreen) && longScreen.length > 0
            ? longScreen
            : sp500Explain && tickers.length
              ? tickers.slice(0, hl)
              : [];
    const shortIdeas =
        Array.isArray(shortScreen) && shortScreen.length > 0
            ? shortScreen
            : sp500Explain && tickers.length
              ? tickers.slice(hl)
              : [];

    const [activeTab, setActiveTab] = useState(tickers[0] || '');

    let totalInvested = 0;
    const investedTickers = bookStyleRun ? bookedTickers : tickers;
    for (const t of investedTickers) {
        const order = results?.results?.[t]?.trade_order || {};
        let w = order.proposed_weight;
        if (w == null || Math.abs(Number(w)) < 1e-8) {
            const raw = Number(tw[t]);
            w = Number.isFinite(raw) ? raw : 0;
        } else {
            w = Number(w);
        }
        totalInvested += w;
    }
    const cashPct = Math.max(0, 1 - totalInvested);

    const kCap = (md.allocator_k_long ?? 10) + (md.allocator_k_short ?? 10);
    const showResearchCard = top20Explain || (sp500Explain && tickers.length > 0);

    return (
        <div className="fade-in">
            {(isPartial || errorMessage) && (
                <div
                    className="card"
                    style={{
                        marginBottom: 'var(--sp-lg)',
                        borderColor: errorMessage ? 'rgba(239,68,68,0.45)' : 'rgba(34,211,238,0.35)',
                        background: errorMessage ? 'rgba(239,68,68,0.08)' : 'rgba(34,211,238,0.06)',
                    }}
                >
                    <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.5 }}>
                        {errorMessage && (
                            <>
                                <strong style={{ color: 'var(--accent-red)' }}>Run failed.</strong>{' '}
                                {errorMessage}
                                {stepLabel && (
                                    <>
                                        <br />
                                        <span style={{ color: 'var(--text-muted)' }}>
                                            Last pipeline step: {stepLabel}
                                            {stepKey ? ` (${stepKey})` : ''}
                                        </span>
                                    </>
                                )}
                            </>
                        )}
                        {!errorMessage && isPartial && (
                            <>
                                <strong style={{ color: 'var(--accent-cyan)' }}>Live partial results</strong>
                                {' — pipeline still running. '}
                                {stepLabel ? (
                                    <span style={{ color: 'var(--text-muted)' }}>
                                        Current stage: {stepLabel}
                                        {stepKey ? ` (${stepKey})` : ''}
                                    </span>
                                ) : (
                                    <span style={{ color: 'var(--text-muted)' }}>
                                        Sections fill in as each agent finishes; the UI refreshes about every 10 seconds.
                                    </span>
                                )}
                            </>
                        )}
                    </p>
                </div>
            )}

            {showResearchCard && (
                <div className="card" style={{ marginBottom: 'var(--sp-lg)' }}>
                    <div className="card-header">
                        <h3>Research universe</h3>
                        <span className="badge badge-info">{tickers.length} names</span>
                    </div>
                    {sp500Explain && (
                        <p
                            style={{
                                margin: '0 0 var(--sp-sm)',
                                fontSize: '0.75rem',
                                color: 'var(--text-muted)',
                                fontFamily: 'var(--font-mono)',
                            }}
                        >
                            screen universe={md.screen_universe_count ?? md.tickers_universe?.length ?? '—'} ·
                            max_candidates={md.max_candidates ?? '—'} · usable close (pricing)={md.tradable_count ?? '—'}
                            {(md.limit_universe ?? 0) > 0 ? (
                                <>
                                    {' '}
                                    · limit_universe={md.limit_universe}
                                </>
                            ) : null}
                        </p>
                    )}
                    {sp500Explain && md.pricing_note && (
                        <p
                            style={{
                                margin: '0 0 var(--sp-sm)',
                                fontSize: '0.78rem',
                                color: 'var(--text-muted)',
                                lineHeight: 1.45,
                            }}
                        >
                            {md.pricing_note}
                        </p>
                    )}
                    {sp500Explain &&
                        Array.isArray(md.candidate_pool_shortfall_messages) &&
                        md.candidate_pool_shortfall_messages.length > 0 && (
                            <div
                                style={{
                                    marginBottom: 'var(--sp-md)',
                                    padding: 'var(--sp-md)',
                                    borderRadius: '8px',
                                    background: 'rgba(251,191,36,0.1)',
                                    border: '1px solid rgba(251,191,36,0.35)',
                                }}
                            >
                                {md.candidate_pool_shortfall_messages.map((msg, i) => (
                                    <p
                                        key={i}
                                        style={{
                                            margin: i ? '0.5rem 0 0' : 0,
                                            fontSize: '0.84rem',
                                            lineHeight: 1.5,
                                            color: 'var(--text-secondary)',
                                        }}
                                    >
                                        <strong style={{ color: 'var(--accent-yellow)' }}>Screening note:</strong> {msg}
                                    </p>
                                ))}
                            </div>
                        )}
                    {sp500Explain && (
                        <p
                            style={{
                                margin: '0 0 var(--sp-md)',
                                fontSize: '0.86rem',
                                lineHeight: 1.55,
                                color: 'var(--text-secondary)',
                            }}
                        >
                            After wide technicals, the formula ranks by expected return. Your <strong>max candidates</strong>{' '}
                            setting takes the <strong>best half</strong> (long-idea tail) and <strong>worst half</strong>{' '}
                            (short-idea tail). <strong>Every</strong> name below runs sentiment, fundamentals, and
                            synthesis — not only the allocator book.
                        </p>
                    )}
                    {top20Explain && (
                        <p
                            style={{
                                margin: '0 0 var(--sp-md)',
                                fontSize: '0.86rem',
                                lineHeight: 1.55,
                                color: 'var(--text-secondary)',
                            }}
                        >
                            Fixed large-cap list: <strong>all {tickers.length} tickers</strong> receive the full research
                            stack. The risk allocator then chooses up to <strong>k_long + k_short</strong> names for
                            non-zero weights (defaults {kCap}).
                        </p>
                    )}
                    {sp500Explain && tickers.length > 0 ? (
                        <>
                            <p
                                style={{
                                    margin: '0 0 0.35rem',
                                    fontSize: '0.78rem',
                                    fontWeight: 600,
                                    color: 'var(--accent-green)',
                                }}
                            >
                                Long-idea side (higher formula ER) — {longIdeas.length}
                            </p>
                            <div style={{ ...chipRowStyle, marginBottom: 'var(--sp-md)' }}>
                                {longIdeas.map((t) => (
                                    <span key={t} style={chipStyle(true)}>
                                        {t}
                                    </span>
                                ))}
                            </div>
                            <p
                                style={{
                                    margin: '0 0 0.35rem',
                                    fontSize: '0.78rem',
                                    fontWeight: 600,
                                    color: 'var(--accent-red)',
                                }}
                            >
                                Short-idea side (lower formula ER) — {shortIdeas.length}
                            </p>
                            <div style={chipRowStyle}>
                                {shortIdeas.map((t) => (
                                    <span key={t} style={chipStyle(false)}>
                                        {t}
                                    </span>
                                ))}
                            </div>
                        </>
                    ) : (
                        top20Explain && (
                            <div style={chipRowStyle}>
                                {tickers.map((t) => (
                                    <span key={t} style={chipStyle(true)}>
                                        {t}
                                    </span>
                                ))}
                            </div>
                        )
                    )}
                </div>
            )}

            {bookStyleRun && (
                <div
                    className="card"
                    style={{
                        marginBottom: 'var(--sp-lg)',
                        borderColor: 'rgba(99,102,241,0.35)',
                        background: 'rgba(99,102,241,0.06)',
                    }}
                >
                    <div className="card-header">
                        <h3>Allocator book</h3>
                        {bookedTickers.length > 0 && (
                            <span className="badge badge-info">{bookedTickers.length} non-zero weights</span>
                        )}
                    </div>
                    <p style={{ margin: '0 0 var(--sp-md)', fontSize: '0.86rem', lineHeight: 1.55, color: 'var(--text-secondary)' }}>
                        After research, <strong>RiskPortfolioAgent</strong> scores each recommendation (direction ×
                        conviction × risk-adjusted expected return), takes the top <strong>k_long</strong> positive scores
                        for longs and the most negative <strong>k_short</strong> for shorts, then sizes weights. Only
                        those names get target weights; the trader runs on that subset. Default cap is{' '}
                        <strong>{kCap}</strong> positions ({md.allocator_k_long ?? 10} long + {md.allocator_k_short ?? 10}{' '}
                        short).
                    </p>
                    {isPartial && bookedTickers.length === 0 && (
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            Waiting for allocator (step <code>risk_portfolio</code>)…
                        </p>
                    )}
                    {!isPartial && bookedTickers.length === 0 && (
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            No non-zero weights in this run.
                        </p>
                    )}
                    {bookedTickers.length > 0 && (
                        <div style={{ ...chipRowStyle, marginBottom: 'var(--sp-md)' }}>
                            {bookedTickers.map((t) => {
                                const w = Number(tw[t]);
                                const longSide = Number.isFinite(w) ? w >= 0 : true;
                                return (
                                    <span key={t} style={chipStyle(longSide)}>
                                        {t}{' '}
                                        {Number.isFinite(w) ? `(${(w * 100).toFixed(1)}%)` : ''}
                                    </span>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* ── Portfolio allocation ── */}
            <div className="dashboard-section">
                <div className="card">
                    <div className="card-header">
                        <h3>{bookStyleRun ? '💼 Portfolio allocation (book)' : '💼 Portfolio allocation'}</h3>
                        <div style={{ display: 'flex', gap: 'var(--sp-sm)', alignItems: 'center' }}>
                            {trader.sizing_method_chosen && (
                                <span className="badge badge-info">Method: {trader.sizing_method_chosen}</span>
                            )}
                            <span className="badge badge-info">Invested: {(totalInvested * 100).toFixed(1)}%</span>
                            <span
                                className="badge"
                                style={{
                                    background: 'rgba(107,114,128,0.15)',
                                    color: '#9ca3af',
                                    border: '1px solid rgba(107,114,128,0.25)',
                                }}
                            >
                                Cash: {(cashPct * 100).toFixed(1)}%
                            </span>
                        </div>
                    </div>
                    {bookStyleRun ? (
                        <p
                            style={{
                                fontSize: '0.8rem',
                                color: 'var(--text-muted)',
                                marginBottom: 'var(--sp-md)',
                                lineHeight: 1.45,
                            }}
                        >
                            Chart and table list <strong>allocator-sized names</strong> only. Other researched tickers
                            stay in the per-ticker tabs with <strong>HOLD / 0%</strong> because they were not in the
                            book.
                        </p>
                    ) : null}

                    <div className="grid-2">
                        {bookedTickers.length > 0 ? (
                            <PortfolioChart results={results} tickers={bookedTickers} />
                        ) : (
                            <div
                                style={{
                                    padding: 'var(--sp-lg)',
                                    color: 'var(--text-muted)',
                                    fontSize: '0.88rem',
                                    alignSelf: 'center',
                                }}
                            >
                                {bookStyleRun
                                    ? 'No allocator weights to chart yet.'
                                    : 'Nothing to chart for this result.'}
                            </div>
                        )}
                        <div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Ticker</th>
                                        <th>Action</th>
                                        <th>Weight</th>
                                        <th>Method</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {bookedTickers.length === 0 ? (
                                        <tr>
                                            <td colSpan={4} style={{ color: 'var(--text-muted)' }}>
                                                {bookStyleRun ? 'No booked positions yet.' : 'No tickers in this result.'}
                                            </td>
                                        </tr>
                                    ) : (
                                        bookedTickers.map((t) => {
                                            const order = results?.results?.[t]?.trade_order || {};
                                            let dispW = order.proposed_weight;
                                            if (dispW == null || Math.abs(Number(dispW)) < 1e-8) {
                                                const raw = Number(tw[t]);
                                                dispW = Number.isFinite(raw) ? raw : 0;
                                            } else {
                                                dispW = Number(dispW);
                                            }
                                            let act = order.action || 'HOLD';
                                            if (act === 'HOLD' && Math.abs(dispW) >= 1e-8) {
                                                act = dispW > 0 ? 'BUY' : 'SELL';
                                            }
                                            return (
                                                <tr key={t}>
                                                    <td style={{ fontWeight: 600 }}>{t}</td>
                                                    <td>
                                                        <SignalBadge signal={act} />
                                                    </td>
                                                    <td style={{ fontFamily: 'var(--font-mono)' }}>
                                                        {(dispW * 100).toFixed(1)}%
                                                    </td>
                                                    <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                                                        {order.sizing_method_used || 'N/A'}
                                                    </td>
                                                </tr>
                                            );
                                        })
                                    )}
                                </tbody>
                            </table>
                            {trader.overall_rationale && (
                                <p
                                    style={{
                                        marginTop: 'var(--sp-md)',
                                        fontSize: '0.82rem',
                                        color: 'var(--text-muted)',
                                        fontStyle: 'italic',
                                    }}
                                >
                                    {trader.overall_rationale}
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Per-ticker tabs ── */}
            <div className="dashboard-section">
                <h3 className="section-title">
                    {bookStyleRun ? '🔍 Per-ticker details (full research set)' : '🔍 Per-ticker details'}
                </h3>
                <div className="tabs">
                    {tickers.map((t) => (
                        <button
                            key={t}
                            className={`tab-btn ${t === activeTab ? 'active' : ''}`}
                            onClick={() => setActiveTab(t)}
                        >
                            {t}
                        </button>
                    ))}
                </div>
                {activeTab && results?.results?.[activeTab] && (
                    <TickerCard ticker={activeTab} data={results.results[activeTab]} />
                )}
            </div>

            {/* ── Risk Report ── */}
            <div className="dashboard-section">
                <h3 className="section-title">📋 Risk validation</h3>
                <RiskPanel riskReport={riskReport} />
            </div>
        </div>
    );
}
