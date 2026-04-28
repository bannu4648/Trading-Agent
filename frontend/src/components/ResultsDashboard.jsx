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

function LoadingCard({ title, badge = 'Loading', message }) {
    return (
        <div className="card fade-in" style={{ marginBottom: 'var(--sp-lg)' }}>
            <div className="card-header">
                <h3>{title}</h3>
                <span className="badge badge-info">{badge}</span>
            </div>
            <div className="placeholder-block">
                <div className="placeholder-line lg" />
                <div className="placeholder-line lg" />
                <div className="placeholder-line md" />
                <p className="placeholder-text">{message}</p>
            </div>
        </div>
    );
}

export default function ResultsDashboard({
    results,
    isPartial = false,
    errorMessage = null,
    latestSavedPortfolio = null,
}) {
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

    const kCap = (md.allocator_k_long ?? 10) + (md.allocator_k_short ?? 10);
    const showResearchCard = top20Explain || (sp500Explain && tickers.length > 0);
    const hasLatestPortfolio =
        latestSavedPortfolio &&
        latestSavedPortfolio.target_weights &&
        Object.keys(latestSavedPortfolio.target_weights).length > 0;
    const rebalanceRows = [];
    const currentPortfolioWeights = (latestSavedPortfolio && latestSavedPortfolio.target_weights) || {};
    // Custom ticker mode should preserve the existing book and only adjust tickers
    // explicitly analyzed in the current run.
    const resultWeights = bookStyleRun ? {} : { ...currentPortfolioWeights };
    for (const t of tickers) {
        const order = results?.results?.[t]?.trade_order || {};
        const action = order.action || 'HOLD';
        const currentWeight = Number(currentPortfolioWeights[t] || 0);
        let weight = order.proposed_weight;
        if (weight == null || Math.abs(Number(weight)) < 1e-8) {
            const raw = Number(tw[t]);
            weight = Number.isFinite(raw) ? raw : 0;
        } else {
            weight = Number(weight);
        }

        // For custom ticker runs, HOLD should preserve existing portfolio weight.
        // Without this, a HOLD implicitly looked like "sell down to 0", which is misleading.
        if (!bookStyleRun && action === 'HOLD') {
            weight = currentWeight;
        }

        if (action === 'SELL' && Math.abs(weight) < 1e-8) {
            weight = -0.03;
        }
        resultWeights[t] = weight;
    }
    const customNoRebalance = !bookStyleRun && tickers.every((t) => {
        const order = results?.results?.[t]?.trade_order || {};
        const action = order.action || 'HOLD';
        const from = Number(currentPortfolioWeights[t] || 0);
        const to = Number(resultWeights[t] || 0);
        const noWeightChange = Math.abs(to - from) <= 1e-6;
        return action === 'HOLD' && noWeightChange;
    });
    const allTickers = Array.from(
        new Set([...Object.keys(currentPortfolioWeights), ...Object.keys(resultWeights)]),
    );
    allTickers.forEach((t) => {
        const from = Number(currentPortfolioWeights[t] || 0);
        const to = Number(resultWeights[t] || 0);
        const delta = to - from;
        if (Math.abs(delta) > 1e-6) {
            rebalanceRows.push({ ticker: t, from, to, delta });
        }
    });
    if (customNoRebalance) {
        rebalanceRows.length = 0;
    }
    rebalanceRows.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
    const portfolioContextRows = rebalanceRows.filter((row) => tickers.includes(row.ticker)).slice(0, 8);
    const existingPortfolioTickers = Object.entries(currentPortfolioWeights)
        .filter(([, w]) => Math.abs(Number(w || 0)) > 1e-6)
        .map(([t]) => t);
    const analyzedTickersSet = new Set(tickers);
    const portfolioDisplayTickers = bookStyleRun
        ? bookedTickers
        : Array.from(new Set([...existingPortfolioTickers, ...tickers])).sort(
              (a, b) => {
                  const aPresent = Math.abs(Number(currentPortfolioWeights[a] || 0)) > 1e-6 ? 1 : 0;
                  const bPresent = Math.abs(Number(currentPortfolioWeights[b] || 0)) > 1e-6 ? 1 : 0;
                  const aAnalyzed = analyzedTickersSet.has(a) ? 1 : 0;
                  const bAnalyzed = analyzedTickersSet.has(b) ? 1 : 0;
                  if (aPresent !== bPresent) return bPresent - aPresent;
                  if (aAnalyzed !== bAnalyzed) return bAnalyzed - aAnalyzed;
                  return (
                      Math.abs(Number(resultWeights[b] ?? currentPortfolioWeights[b] ?? 0)) -
                      Math.abs(Number(resultWeights[a] ?? currentPortfolioWeights[a] ?? 0))
                  );
              },
          );
    const actionOverrides = {};
    portfolioDisplayTickers.forEach((t) => {
        const isAnalyzedNow = tickers.includes(t);
        if (isAnalyzedNow) {
            actionOverrides[t] = results?.results?.[t]?.trade_order?.action || 'HOLD';
        } else {
            actionOverrides[t] = 'HOLD';
        }
    });
    const displayTotalInvested = portfolioDisplayTickers.reduce((acc, t) => {
        if (!bookStyleRun) return acc + Number(resultWeights[t] ?? currentPortfolioWeights[t] ?? 0);
        const order = results?.results?.[t]?.trade_order || {};
        let w = order.proposed_weight;
        if (w == null || Math.abs(Number(w)) < 1e-8) {
            const raw = Number(tw[t]);
            w = Number.isFinite(raw) ? raw : 0;
        } else {
            w = Number(w);
        }
        return acc + w;
    }, 0);
    const displayCashPct = Math.max(0, 1 - displayTotalInvested);
    const runRecommendationRows = tickers.map((t) => {
        const order = results?.results?.[t]?.trade_order || {};
        let weight = order.proposed_weight;
        if (weight == null || Math.abs(Number(weight)) < 1e-8) {
            const raw = Number(tw[t]);
            weight = Number.isFinite(raw) ? raw : 0;
        } else {
            weight = Number(weight);
        }
        const action = order.action || 'HOLD';
        return { ticker: t, action, weight };
    });
    const showSp500Loading = sp500Explain && isPartial;
    const showPortfolioLoading = showSp500Loading && portfolioDisplayTickers.length === 0;
    const showPerTickerLoading = showSp500Loading && tickers.length === 0;
    const loadingResearchMessage =
        stepKey === 'screen' || stepKey === 'technical_wide'
            ? 'Scanning the S&P500 universe and preparing the candidate set.'
            : 'Building the shortlist and preparing full research coverage.';
    const loadingPortfolioMessage =
        stepKey === 'risk_portfolio' || stepKey === 'trader'
            ? 'Allocator and sizing are in progress. Portfolio weights will appear shortly.'
            : 'Portfolio weights appear after research and synthesis are ready.';

    return (
        <div className="fade-in">
            {errorMessage && (
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
                    {showSp500Loading && tickers.length === 0 && (
                        <div style={{ marginTop: 'var(--sp-md)' }}>
                            <div className="placeholder-block">
                                <div className="placeholder-line lg" />
                                <div className="placeholder-line md" />
                                <p className="placeholder-text">{loadingResearchMessage}</p>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {bookStyleRun && !isPartial && (
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
                        Once research is complete, the allocator turns each ticker into a portfolio score by combining
                        direction, conviction, and risk-adjusted return. It then keeps the strongest{' '}
                        <strong>{md.allocator_k_long ?? 10}</strong> long ideas and the strongest{' '}
                        <strong>{md.allocator_k_short ?? 10}</strong> short ideas, and sizes them into final target
                        weights. Only this selected set goes into the trading book, capped at <strong>{kCap}</strong>{' '}
                        positions in total.
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
                            <span className="badge badge-info">Invested: {(displayTotalInvested * 100).toFixed(1)}%</span>
                            <span
                                className="badge"
                                style={{
                                    background: 'rgba(107,114,128,0.15)',
                                    color: '#9ca3af',
                                    border: '1px solid rgba(107,114,128,0.25)',
                                }}
                            >
                                Cash: {(displayCashPct * 100).toFixed(1)}%
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
                    {!bookStyleRun && runRecommendationRows.length > 0 && (
                        <div
                            style={{
                                marginBottom: 'var(--sp-md)',
                                padding: 'var(--sp-md)',
                                borderRadius: '8px',
                                border: '1px solid rgba(59,130,246,0.25)',
                                background: 'rgba(59,130,246,0.08)',
                            }}
                        >
                            <p
                                style={{
                                    margin: '0 0 var(--sp-xs)',
                                    fontSize: '0.78rem',
                                    color: 'var(--text-secondary)',
                                }}
                            >
                                Current run recommendation
                            </p>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Ticker</th>
                                        <th>Action</th>
                                        <th>Weight</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {runRecommendationRows.map((row) => (
                                        <tr key={row.ticker}>
                                            <td style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                                                {row.ticker}
                                            </td>
                                            <td>
                                                <SignalBadge signal={row.action} />
                                            </td>
                                            <td style={{ fontFamily: 'var(--font-mono)' }}>
                                                {(Number(row.weight) * 100).toFixed(1)}%
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {showPortfolioLoading ? (
                        <div className="placeholder-block">
                            <div className="placeholder-line lg" />
                            <div className="placeholder-line lg" />
                            <div className="placeholder-line md" />
                            <p className="placeholder-text">{loadingPortfolioMessage}</p>
                        </div>
                    ) : (
                    <div className="grid-2">
                        {portfolioDisplayTickers.length > 0 ? (
                            <PortfolioChart
                                results={results}
                                tickers={portfolioDisplayTickers}
                                weightOverrides={!bookStyleRun ? resultWeights : null}
                                actionOverrides={!bookStyleRun ? actionOverrides : null}
                            />
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
                                    </tr>
                                </thead>
                                <tbody>
                                    {portfolioDisplayTickers.length === 0 ? (
                                        <tr>
                                            <td colSpan={3} style={{ color: 'var(--text-muted)' }}>
                                                {bookStyleRun ? 'No booked positions yet.' : 'No tickers in this result.'}
                                            </td>
                                        </tr>
                                    ) : (
                                        portfolioDisplayTickers.map((t) => {
                                            const order = results?.results?.[t]?.trade_order || {};
                                            const isAnalyzedNow = tickers.includes(t);
                                            let dispW = isAnalyzedNow
                                                ? Number(resultWeights[t] ?? 0)
                                                : Number(currentPortfolioWeights[t] ?? 0);
                                            let act = isAnalyzedNow ? (order.action || 'HOLD') : 'HOLD';
                                            if (act === 'HOLD' && Math.abs(dispW) >= 1e-8) {
                                                act = dispW > 0 ? 'BUY' : 'SELL';
                                            }
                                            const isPresentAlready =
                                                Math.abs(Number(currentPortfolioWeights[t] || 0)) > 1e-6;
                                            const showPresentAlreadyTag = isPresentAlready && isAnalyzedNow;
                                            return (
                                                <tr key={t}>
                                                    <td style={{ fontWeight: 600 }}>
                                                        {t}{' '}
                                                        {showPresentAlreadyTag && (
                                                            <span
                                                                className="badge"
                                                                style={{
                                                                    marginLeft: '0.35rem',
                                                                    background: 'rgba(59,130,246,0.12)',
                                                                    color: 'var(--accent-blue)',
                                                                    border: '1px solid rgba(59,130,246,0.25)',
                                                                }}
                                                            >
                                                                Present Already
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td>
                                                        <SignalBadge signal={act} />
                                                    </td>
                                                    <td style={{ fontFamily: 'var(--font-mono)' }}>
                                                        {(dispW * 100).toFixed(1)}%
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
                    )}
                    {!bookStyleRun && hasLatestPortfolio && (
                        <div style={{ marginTop: 'var(--sp-lg)' }}>
                            <div className="card-header">
                                <h3>Rebalance suggestion vs latest saved portfolio</h3>
                                <span className="badge badge-info">
                                    base: {latestSavedPortfolio.filename}
                                </span>
                            </div>
                            {rebalanceRows.length === 0 ? (
                                <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
                                    No rebalance needed from latest saved portfolio.
                                </p>
                            ) : (
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Ticker</th>
                                            <th>Current</th>
                                            <th>Suggested</th>
                                            <th>Delta</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {rebalanceRows.slice(0, 10).map((row) => (
                                            <tr key={row.ticker}>
                                                <td style={{ fontWeight: 600 }}>{row.ticker}</td>
                                                <td style={{ fontFamily: 'var(--font-mono)' }}>
                                                    {(row.from * 100).toFixed(1)}%
                                                </td>
                                                <td style={{ fontFamily: 'var(--font-mono)' }}>
                                                    {(row.to * 100).toFixed(1)}%
                                                </td>
                                                <td
                                                    style={{
                                                        fontFamily: 'var(--font-mono)',
                                                        color:
                                                            row.delta >= 0
                                                                ? 'var(--accent-green)'
                                                                : 'var(--accent-red)',
                                                    }}
                                                >
                                                    {(row.delta * 100).toFixed(1)}%
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* ── Per-ticker tabs ── */}
            <div className="dashboard-section">
                <h3 className="section-title">
                    {bookStyleRun ? '🔍 Per-ticker details (full research set)' : '🔍 Per-ticker details'}
                </h3>
                {showPerTickerLoading ? (
                    <LoadingCard
                        title="🔍 Per-ticker details"
                        badge="Queued"
                        message="Ticker-level cards will appear as each research packet is completed."
                    />
                ) : (
                    <>
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
                            <TickerCard
                                ticker={activeTab}
                                data={results.results[activeTab]}
                                isCustomView={!bookStyleRun}
                                isPartial={isPartial}
                            />
                        )}
                    </>
                )}
            </div>

            {/* ── Risk Report ── */}
            <div className="dashboard-section">
                <h3 className="section-title">📋 Risk validation</h3>
                <RiskPanel
                    riskReport={riskReport}
                    portfolioContext={!bookStyleRun ? portfolioContextRows : []}
                    isPartial={isPartial}
                />
            </div>
        </div>
    );
}
