export default function PortfolioChart({ results, tickers }) {
    // Build allocation data from results
    const allocations = [];
    let totalInvested = 0;

    for (const ticker of tickers) {
        const order = results?.results?.[ticker]?.trade_order || {};
        const weight = order.proposed_weight || 0;
        const action = order.action || 'HOLD';
        totalInvested += weight;
        allocations.push({ ticker, weight, action });
    }

    const cashPct = Math.max(0, 1 - totalInvested);
    allocations.push({ ticker: 'CASH', weight: cashPct, action: 'cash' });

    const maxWeight = Math.max(...allocations.map(a => a.weight), 0.01);

    return (
        <div className="portfolio-bar-chart">
            {allocations.map(({ ticker, weight, action }) => (
                <div key={ticker} className="bar-row">
                    <span className="bar-label">{ticker}</span>
                    <div className="bar-track">
                        <div
                            className={`bar-fill ${action === 'BUY' ? 'buy' : action === 'SELL' ? 'sell' : action === 'cash' ? 'cash' : 'hold'}`}
                            style={{ width: `${Math.max((weight / Math.max(maxWeight * 1.2, 0.01)) * 100, weight > 0 ? 8 : 0)}%` }}
                        >
                            {weight > 0 ? `${(weight * 100).toFixed(1)}%` : ''}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}
