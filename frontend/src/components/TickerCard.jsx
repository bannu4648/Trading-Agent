import SignalBadge from './SignalBadge';
import ReactMarkdown from 'react-markdown';

function parseSynthesisPayload(raw) {
    if (!raw) return null;
    if (typeof raw === 'object') return raw;
    if (typeof raw !== 'string') return null;

    const trimmed = raw.trim();
    const fenced = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
    const candidate = fenced ? fenced[1] : trimmed;
    try {
        return JSON.parse(candidate);
    } catch {
        return null;
    }
}

function humanizeKey(key) {
    return String(key)
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/[_-]+/g, ' ')
        .trim()
        .replace(/\s+/g, ' ')
        .replace(/^./, (c) => c.toUpperCase());
}

function isPrimitive(v) {
    return v == null || ['string', 'number', 'boolean'].includes(typeof v);
}

function isTrendKey(key) {
    return /over\s*all\s*[_\-\s]*trend|over\s*trend/i.test(String(key));
}

function renderStructuredValue(value, depth = 0) {
    if (value == null) return <span style={{ color: 'var(--text-muted)' }}>N/A</span>;
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') return Number.isFinite(value) ? value.toString() : 'N/A';
    if (typeof value === 'string') {
        return (
            <ReactMarkdown
                components={{
                    p: ({ children }) => <span>{children}</span>,
                    ul: ({ children }) => <ul style={{ paddingLeft: '1.1rem', margin: '0.2rem 0' }}>{children}</ul>,
                    ol: ({ children }) => <ol style={{ paddingLeft: '1.1rem', margin: '0.2rem 0' }}>{children}</ol>,
                    li: ({ children }) => <li style={{ marginBottom: '0.25rem' }}>{children}</li>,
                    strong: ({ children }) => <strong style={{ color: 'var(--text-primary)' }}>{children}</strong>,
                }}
            >
                {value}
            </ReactMarkdown>
        );
    }

    if (Array.isArray(value)) {
        if (value.length === 0) return <span style={{ color: 'var(--text-muted)' }}>N/A</span>;
        return (
            <ul style={{ paddingLeft: depth <= 1 ? '1.1rem' : '1.35rem', marginBottom: 'var(--sp-sm)' }}>
                {value.map((item, idx) => (
                    <li key={idx} style={{ marginBottom: '0.25rem', color: 'var(--text-secondary)' }}>
                        {isPrimitive(item) ? (
                            renderStructuredValue(item, depth + 1)
                        ) : (
                            <div>{renderStructuredObject(item, depth + 1)}</div>
                        )}
                    </li>
                ))}
            </ul>
        );
    }

    if (typeof value === 'object') {
        return renderStructuredObject(value, depth + 1);
    }

    return String(value);
}

function renderStructuredObject(obj, depth = 0) {
    const entries = Object.entries(obj || {}).filter(([, v]) => v !== undefined);
    if (entries.length === 0) return <span style={{ color: 'var(--text-muted)' }}>N/A</span>;

    const headingStyle = {
        fontSize: depth === 0 ? '1rem' : '0.86rem',
        marginBottom: '0.25rem',
        color: depth === 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
    };

    const primitiveEntries = entries.filter(([, val]) => isPrimitive(val));
    const nestedEntries = entries.filter(([, val]) => !isPrimitive(val));

    return (
        <div>
            {primitiveEntries.length > 0 && (
                <ol style={{ paddingLeft: '1.1rem', marginBottom: nestedEntries.length ? 'var(--sp-sm)' : 0 }}>
                    {primitiveEntries.map(([key, val]) => (
                        <li key={key} style={{ marginBottom: '0.25rem', color: 'var(--text-secondary)' }}>
                            <strong>{humanizeKey(key)}:</strong> {renderStructuredValue(val, depth + 1)}
                        </li>
                    ))}
                </ol>
            )}
            {nestedEntries.map(([key, val]) => (
                <div key={key} style={{ marginBottom: '0.8rem' }}>
                    <h5 style={headingStyle}>{humanizeKey(key)}</h5>
                    {typeof val === 'object' && !Array.isArray(val) ? (
                        <ul style={{ paddingLeft: '1.1rem', marginBottom: 0 }}>
                            {Object.entries(val).map(([subKey, subVal]) => (
                                <li
                                    key={subKey}
                                    style={{ marginBottom: '0.35rem', color: 'var(--text-secondary)' }}
                                >
                                    <strong>{humanizeKey(subKey)}:</strong>{' '}
                                    {renderStructuredValue(subVal, depth + 2)}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        renderStructuredValue(val, depth + 1)
                    )}
                </div>
            ))}
        </div>
    );
}

export default function TickerCard({ ticker, data, isCustomView = false, isPartial = false }) {
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
    const sourceBreakdown = sent.sources || {};
    const synthesisPayload = parseSynthesisPayload(synth);
    const sentimentRows = Object.entries(sourceBreakdown).filter(([, detail]) => Number(detail?.score) > 0);
    const indicatorValues = tech?.indicators?.values || {};
    const indicatorRows = [
        ['Close', indicatorValues.close],
        ['RSI 14', indicatorValues.rsi_14],
        ['MACD', indicatorValues.macd],
        ['MACD Signal', indicatorValues.macd_signal],
        ['Stoch K', indicatorValues.stoch_k],
        ['Stoch D', indicatorValues.stoch_d],
        ['ATR 14', indicatorValues.atr_14],
        ['Supertrend', indicatorValues.supertrend],
        ['Supertrend Direction', indicatorValues.supertrend_direction],
        ['VWAP', indicatorValues.vwap],
        ['SMA 20', indicatorValues.sma_20],
        ['EMA 12', indicatorValues.ema_12],
    ].filter(([, value]) => value !== null && value !== undefined && value !== '');

    const formatIndicatorValue = (value) => {
        const n = Number(value);
        if (!Number.isFinite(n)) return String(value);
        if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
        return n.toFixed(3);
    };
    const hasStructuredSynthesisContent = Boolean(
        synthesisPayload &&
            typeof synthesisPayload === 'object' &&
            Object.keys(synthesisPayload).length > 0,
    );
    const synthesisEntries = hasStructuredSynthesisContent
        ? Object.entries(synthesisPayload).filter(([, v]) => v !== undefined)
        : [];
    const trendEntry = synthesisEntries.find(([k]) => isTrendKey(k));
    const nonTrendEntries = synthesisEntries.filter(([k]) => !isTrendKey(k));

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
            {/* Three column details */}
            <div className="grid-3" style={{ marginBottom: 'var(--sp-lg)' }}>
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
                            {fundKeys.map((k) => (
                                <tr key={k}>
                                    <td>{k}</td>
                                    <td style={{ fontFamily: 'var(--font-mono)' }}>
                                        {fund[k] != null ? String(fund[k]) : 'N/A'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

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
                    ) : null}
                    {indicatorRows.length > 0 && (
                        <table className="data-table" style={{ marginTop: 'var(--sp-md)' }}>
                            <thead>
                                <tr>
                                    <th>Indicator</th>
                                    <th>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                {indicatorRows.map(([name, value]) => (
                                    <tr key={name}>
                                        <td>{name}</td>
                                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                                            {formatIndicatorValue(value)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                    {!isCustomView && tech.summary && (
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
                    {sentimentRows.length > 0 && (
                        <div style={{ marginTop: 'var(--sp-md)' }}>
                            <h5
                                style={{
                                    fontSize: '0.8rem',
                                    color: 'var(--text-secondary)',
                                    marginBottom: 'var(--sp-xs)',
                                }}
                            >
                                Source split
                            </h5>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Source</th>
                                        <th>Label</th>
                                        <th>Score</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sentimentRows.map(([source, detail]) => (
                                        <tr key={source}>
                                            <td>{source.replace('_', ' ')}</td>
                                            <td>{detail?.label || 'N/A'}</td>
                                            <td style={{ fontFamily: 'var(--font-mono)' }}>
                                                {Number.isFinite(Number(detail?.score))
                                                    ? Number(detail.score).toFixed(3)
                                                    : 'N/A'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
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
            {!isPartial && (
                <div className="card" style={{ marginTop: 'var(--sp-lg)' }}>
                    <div className="card-header">
                        <h3>🎯 Strategy: {ticker}</h3>
                        {order && <SignalBadge signal={order.action || 'HOLD'} />}
                    </div>
                    <div className="synthesis-content">
                        {hasStructuredSynthesisContent ? (
                            <div>
                                {trendEntry && (
                                    <div
                                        style={{
                                            marginBottom: 'var(--sp-md)',
                                            padding: 'var(--sp-md)',
                                            borderRadius: '10px',
                                            background: 'rgba(59,130,246,0.08)',
                                            border: '1px solid rgba(59,130,246,0.25)',
                                        }}
                                    >
                                        <h4 style={{ marginBottom: '0.35rem' }}>
                                            {humanizeKey(trendEntry[0])}
                                        </h4>
                                        <p style={{ margin: 0 }}>{renderStructuredValue(trendEntry[1], 1)}</p>
                                    </div>
                                )}

                                {nonTrendEntries.map(([key, val]) => (
                                    <div key={key} style={{ marginBottom: 'var(--sp-md)' }}>
                                        <h4 style={{ marginBottom: '0.35rem' }}>{humanizeKey(key)}</h4>
                                        {typeof val === 'object' && val && !Array.isArray(val) ? (
                                            <div>{renderStructuredObject(val, 1)}</div>
                                        ) : (
                                            <div>{renderStructuredValue(val, 1)}</div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : synth ? (
                            <ReactMarkdown>{synth}</ReactMarkdown>
                        ) : (
                            <p style={{ color: 'var(--text-muted)' }}>No strategy output available.</p>
                        )}
                    </div>
                </div>
            )}
            {isPartial && (
                <div className="card" style={{ marginTop: 'var(--sp-lg)' }}>
                    <div className="card-header">
                        <h3>🎯 Strategy: {ticker}</h3>
                        <span className="badge badge-info">Generating…</span>
                    </div>
                    <div className="placeholder-block">
                        <div className="placeholder-line lg" />
                        <div className="placeholder-line lg" />
                        <div className="placeholder-line md" />
                        <p className="placeholder-text">
                            Strategy summary will update here once synthesis is generated.
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
