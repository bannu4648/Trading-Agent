export default function RiskPanel({ riskReport, portfolioContext = [], isPartial = false }) {
    if (!riskReport && isPartial) {
        return (
            <div className="card fade-in">
                <div className="card-header">
                    <h3>📋 Portfolio Validation</h3>
                    <span className="badge badge-info">Generating…</span>
                </div>
                <div className="placeholder-block">
                    <div className="placeholder-line lg" />
                    <div className="placeholder-line lg" />
                    <div className="placeholder-line md" />
                    <p className="placeholder-text">
                        Risk validation metrics and warnings will appear after the validation stage completes.
                    </p>
                </div>
            </div>
        );
    }
    if (!riskReport) return null;

    const level = riskReport.risk_level || 'UNKNOWN';
    const warnings = riskReport.warnings || [];
    const metrics = riskReport.metrics || {};
    const lsMode = Boolean(metrics.has_short_positions);

    const levelClass = level === 'LOW' ? 'badge-risk-low' : level === 'MEDIUM' ? 'badge-risk-medium' : 'badge-risk-high';

    return (
        <div className="card fade-in">
            <div className="card-header">
                <h3>📋 Portfolio Validation</h3>
                <span className={`badge ${levelClass}`}>{level} RISK</span>
            </div>

            <div className="grid-4" style={{ marginBottom: 'var(--sp-lg)' }}>
                <div className="stat">
                    <span className="stat-label">{lsMode ? 'Gross long' : 'Total invested'}</span>
                    <span className="stat-value">
                        {(((lsMode ? metrics.gross_long : metrics.total_invested) || 0) * 100).toFixed(1)}%
                    </span>
                </div>
                <div className="stat">
                    <span className="stat-label">{lsMode ? 'Gross short' : 'Cash buffer'}</span>
                    <span className="stat-value positive">
                        {(((lsMode ? metrics.gross_short : metrics.cash_buffer) || 0) * 100).toFixed(1)}%
                    </span>
                </div>
                <div className="stat">
                    <span className="stat-label">Portfolio Vol</span>
                    <span className="stat-value">{((metrics.weighted_portfolio_volatility || 0) * 100).toFixed(1)}%</span>
                </div>
                <div className="stat">
                    <span className="stat-label">Positions</span>
                    <span className="stat-value">{metrics.num_positions || 0}</span>
                </div>
            </div>

            {portfolioContext.length > 0 && (
                <div style={{ marginBottom: 'var(--sp-md)' }}>
                    <h4 style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)', marginBottom: 'var(--sp-sm)' }}>
                        Current position context
                    </h4>
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
                            {portfolioContext.map((row) => (
                                <tr key={row.ticker}>
                                    <td style={{ fontWeight: 600 }}>{row.ticker}</td>
                                    <td style={{ fontFamily: 'var(--font-mono)' }}>{(row.from * 100).toFixed(1)}%</td>
                                    <td style={{ fontFamily: 'var(--font-mono)' }}>{(row.to * 100).toFixed(1)}%</td>
                                    <td
                                        style={{
                                            fontFamily: 'var(--font-mono)',
                                            color: row.delta >= 0 ? 'var(--accent-green)' : 'var(--accent-red)',
                                        }}
                                    >
                                        {(row.delta * 100).toFixed(1)}%
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {warnings.length > 0 ? (
                <>
                    <h4 style={{ fontSize: '0.85rem', color: 'var(--accent-yellow)', marginBottom: 'var(--sp-sm)' }}>
                        ⚠️ Warnings
                    </h4>
                    <ul className="warning-list">
                        {warnings.map((w, i) => (
                            <li key={i} className="warning-item">⚠ {w}</li>
                        ))}
                    </ul>
                </>
            ) : (
                <p style={{ color: 'var(--accent-green)', fontSize: '0.9rem' }}>✅ All checks passed — no warnings</p>
            )}
        </div>
    );
}
