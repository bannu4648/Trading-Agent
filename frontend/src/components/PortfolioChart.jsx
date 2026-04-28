export default function PortfolioChart({ results, tickers, weightOverrides = null, actionOverrides = null }) {
    const tw = results?.target_weights || {};

    const allocations = [];
    let totalInvested = 0;

    for (const ticker of tickers) {
        let weight = null;
        if (weightOverrides && Object.prototype.hasOwnProperty.call(weightOverrides, ticker)) {
            weight = Number(weightOverrides[ticker] || 0);
        } else {
            const order = results?.results?.[ticker]?.trade_order || {};
            weight = order.proposed_weight;
            if (weight == null || Math.abs(Number(weight)) < 1e-8) {
                const raw = Number(tw[ticker]);
                weight = Number.isFinite(raw) ? raw : 0;
            } else {
                weight = Number(weight);
            }
        }
        let action = actionOverrides?.[ticker] || (results?.results?.[ticker]?.trade_order?.action || 'HOLD');
        if (action === 'HOLD' && Math.abs(weight) >= 1e-8) {
            action = weight > 0 ? 'BUY' : 'SELL';
        }
        totalInvested += weight;
        allocations.push({ ticker, weight, action });
    }

    const cashPct = Math.max(0, 1 - totalInvested);
    allocations.push({ ticker: 'CASH', weight: cashPct, action: 'cash' });

    const maxWeight = Math.max(...allocations.map((a) => Math.abs(a.weight)), 0.01);

    return (
        <div className="portfolio-bar-chart">
            {allocations.map(({ ticker, weight, action }) => (
                <div key={ticker} className="bar-row">
                    <span className="bar-label">{ticker}</span>
                    <div className="bar-track">
                        <div
                            className={`bar-fill ${action === 'BUY' ? 'buy' : action === 'SELL' ? 'sell' : action === 'cash' ? 'cash' : 'hold'}`}
                            style={{
                                width: `${Math.max((Math.abs(weight) / Math.max(maxWeight * 1.2, 0.01)) * 100, Math.abs(weight) > 1e-8 ? 8 : 0)}%`,
                            }}
                        >
                            {Math.abs(weight) > 1e-8 ? `${(weight * 100).toFixed(1)}%` : ''}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}
