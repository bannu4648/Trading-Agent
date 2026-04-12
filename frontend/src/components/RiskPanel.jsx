export default function RiskPanel({ riskReport }) {
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
