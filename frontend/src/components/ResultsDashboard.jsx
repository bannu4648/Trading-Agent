import { useState } from 'react';
import PortfolioChart from './PortfolioChart';
import TickerCard from './TickerCard';
import RiskPanel from './RiskPanel';
import SignalBadge from './SignalBadge';

export default function ResultsDashboard({ results }) {
    const tickers = results?.metadata?.tickers || Object.keys(results?.results || {});
    const trader = results?.trader || {};
    const riskReport = results?.risk_report || null;

    const [activeTab, setActiveTab] = useState(tickers[0] || '');

    // Compute totals for summary stats
    let totalInvested = 0;
    for (const t of tickers) {
        const order = results?.results?.[t]?.trade_order || {};
        totalInvested += order.proposed_weight || 0;
    }
    const cashPct = Math.max(0, 1 - totalInvested);

    return (
        <div className="fade-in">
            {/* ── Portfolio Allocation Overview ── */}
            <div className="dashboard-section">
                <div className="card">
                    <div className="card-header">
                        <h3>💼 Portfolio Allocation</h3>
                        <div style={{ display: 'flex', gap: 'var(--sp-sm)', alignItems: 'center' }}>
                            {trader.sizing_method_chosen && (
                                <span className="badge badge-info">Method: {trader.sizing_method_chosen}</span>
                            )}
                            <span className="badge badge-info">Invested: {(totalInvested * 100).toFixed(1)}%</span>
                            <span className="badge" style={{
                                background: 'rgba(107,114,128,0.15)',
                                color: '#9ca3af',
                                border: '1px solid rgba(107,114,128,0.25)'
                            }}>
                                Cash: {(cashPct * 100).toFixed(1)}%
                            </span>
                        </div>
                    </div>

                    <div className="grid-2">
                        <PortfolioChart results={results} tickers={tickers} />
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
                                    {tickers.map(t => {
                                        const order = results?.results?.[t]?.trade_order || {};
                                        return (
                                            <tr key={t}>
                                                <td style={{ fontWeight: 600 }}>{t}</td>
                                                <td><SignalBadge signal={order.action || 'HOLD'} /></td>
                                                <td style={{ fontFamily: 'var(--font-mono)' }}>
                                                    {((order.proposed_weight || 0) * 100).toFixed(1)}%
                                                </td>
                                                <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                                                    {order.sizing_method_used || 'N/A'}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                            {trader.overall_rationale && (
                                <p style={{ marginTop: 'var(--sp-md)', fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                    {trader.overall_rationale}
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Per-Ticker Tabs ── */}
            <div className="dashboard-section">
                <h3 className="section-title">🔍 Per-Ticker Details</h3>
                <div className="tabs">
                    {tickers.map(t => (
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
                <h3 className="section-title">📋 Risk Validation</h3>
                <RiskPanel riskReport={riskReport} />
            </div>
        </div>
    );
}
