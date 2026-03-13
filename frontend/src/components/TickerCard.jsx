import SignalBadge from './SignalBadge';

export default function TickerCard({ ticker, data }) {
    const tech = data?.technical || {};
    const sent = data?.sentiment || {};
    const fund = data?.fundamentals || {};
    const synth = data?.synthesis || 'No synthesis available.';
    const order = data?.trade_order || null;

    const techSignals = tech.signals || [];
    const sentLabel = sent.sentiment_label || 'NEUTRAL';
    const sentScore = sent.sentiment_score || 0;
    const sentConf = sent.confidence || 0;
    const debate = sent.debate || {};

    // Key fundamentals to display
    const fundKeys = [
        'Company Name', 'Sector', 'Share Price', 'Market Cap',
        'P/E Ratio', 'Forward P/E', 'PEG Ratio',
        'Profit Margin', 'Operating Margin', 'ROE', 'ROA',
        'Current Ratio', 'Debt/Equity',
        'Revenue Growth', 'Earnings Growth', 'Piotroski F-Score',
    ];

    return (
        <div className="slide-in">
            {/* Synthesis */}
            <div className="card" style={{ marginBottom: 'var(--sp-lg)' }}>
                <div className="card-header">
                    <h3>🎯 Strategy: {ticker}</h3>
                    {order && <SignalBadge signal={order.action || 'HOLD'} />}
                </div>
                <div className="synthesis-content">{synth}</div>
            </div>

            {/* Three column details */}
            <div className="grid-3" style={{ marginBottom: 'var(--sp-lg)' }}>
                {/* Technical */}
                <div className="card">
                    <h4 className="card-title">📈 Technical Indicators</h4>
                    {techSignals.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Signal</th>
                                    <th>Direction</th>
                                    <th>Strength</th>
                                </tr>
                            </thead>
                            <tbody>
                                {techSignals.map((s, i) => (
                                    <tr key={i}>
                                        <td>{s.name}</td>
                                        <td>
                                            <span style={{
                                                color: s.direction === 'bullish' ? 'var(--accent-green)' :
                                                    s.direction === 'bearish' ? 'var(--accent-red)' :
                                                        'var(--accent-yellow)'
                                            }}>
                                                {(s.direction || '').toUpperCase()}
                                            </span>
                                        </td>
                                        <td style={{ fontFamily: 'var(--font-mono)' }}>{(s.strength || 0).toFixed(2)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No structured signals</p>
                    )}
                    {tech.summary && (
                        <p style={{ marginTop: 'var(--sp-md)', fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            {tech.summary}
                        </p>
                    )}
                </div>

                {/* Sentiment */}
                <div className="card">
                    <h4 className="card-title">💬 Market Sentiment</h4>
                    <div style={{ marginBottom: 'var(--sp-md)' }}>
                        <span className={`badge ${sentLabel === 'POSITIVE' ? 'badge-buy' : sentLabel === 'NEGATIVE' ? 'badge-sell' : 'badge-hold'}`}
                            style={{ fontSize: '0.85rem', padding: '5px 14px' }}>
                            {sentLabel}
                        </span>
                        <span style={{ marginLeft: 'var(--sp-md)', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>
                            Score: {sentScore.toFixed(3)}
                        </span>
                        <span style={{ marginLeft: 'var(--sp-md)', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                            Conf: {(sentConf * 100).toFixed(0)}%
                        </span>
                    </div>
                    {debate.resolution && (
                        <>
                            <h5 style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 'var(--sp-xs)' }}>Bull vs Bear Consensus</h5>
                            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{debate.resolution}</p>
                        </>
                    )}
                </div>

                {/* Fundamentals */}
                <div className="card">
                    <h4 className="card-title">📊 Fundamentals</h4>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {fundKeys.map(k => (
                                <tr key={k}>
                                    <td>{k}</td>
                                    <td style={{ fontFamily: 'var(--font-mono)' }}>{fund[k] != null ? String(fund[k]) : 'N/A'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Trade Order */}
            {order && (
                <div className="card">
                    <div className="card-header">
                        <h3>🤖 Trader Agent Order</h3>
                        <div style={{ display: 'flex', gap: 'var(--sp-sm)', alignItems: 'center' }}>
                            <SignalBadge signal={order.action || 'HOLD'} />
                            <span className="badge badge-info">{order.sizing_method_used || 'N/A'}</span>
                        </div>
                    </div>
                    <div className="grid-3">
                        <div className="stat">
                            <span className="stat-label">Target Weight</span>
                            <span className="stat-value">{((order.proposed_weight || 0) * 100).toFixed(1)}%</span>
                        </div>
                        <div className="stat">
                            <span className="stat-label">Weight Delta</span>
                            <span className={`stat-value ${(order.weight_delta || 0) >= 0 ? 'positive' : 'negative'}`}>
                                {((order.weight_delta || 0) * 100).toFixed(1)}%
                            </span>
                        </div>
                        <div className="stat">
                            <span className="stat-label">Sizing Method</span>
                            <span className="stat-value" style={{ fontSize: '0.95rem' }}>{order.sizing_method_used || 'N/A'}</span>
                        </div>
                    </div>
                    {order.rationale && (
                        <p style={{ marginTop: 'var(--sp-md)', fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            {order.rationale}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}
