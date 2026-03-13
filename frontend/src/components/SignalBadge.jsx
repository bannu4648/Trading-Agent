export default function SignalBadge({ signal }) {
    const cls = signal === 'BUY' ? 'badge-buy' : signal === 'SELL' ? 'badge-sell' : 'badge-hold';
    return <span className={`badge ${cls}`}>{signal}</span>;
}
