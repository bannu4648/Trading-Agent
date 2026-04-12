import { useCallback, useEffect, useRef, useState } from 'react';

function streamKey(ev) {
    const t = ev.ticker != null ? String(ev.ticker) : '';
    const a = ev.agent != null ? String(ev.agent) : 'llm';
    const p = ev.pipeline != null ? String(ev.pipeline) : 'pipeline';
    return `${p}|${a}|${t}`;
}

/** Pixels from bottom; if user is within this, we treat them as "following" the stream. */
const PIN_THRESHOLD_PX = 72;

export default function LlmStreamPanel({ streamBlocks, stageLines, active }) {
    const scrollRef = useRef(null);
    const [stickToBottom, setStickToBottom] = useState(true);

    const onScroll = useCallback(() => {
        const el = scrollRef.current;
        if (!el) return;
        const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
        setStickToBottom(dist < PIN_THRESHOLD_PX);
    }, []);

    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return undefined;
        el.addEventListener('scroll', onScroll, { passive: true });
        return () => el.removeEventListener('scroll', onScroll);
    }, [onScroll]);

    useEffect(() => {
        if (active) setStickToBottom(true);
    }, [active]);

    useEffect(() => {
        if (!active || !stickToBottom) return;
        const el = scrollRef.current;
        if (!el) return;
        requestAnimationFrame(() => {
            el.scrollTop = el.scrollHeight;
        });
    }, [streamBlocks, stageLines, active, stickToBottom]);

    // Keep keys even when text is still empty (llm_start / waiting for first chunk).
    const keys = Object.keys(streamBlocks).sort();

    if (keys.length === 0 && (!stageLines || stageLines.length === 0)) {
        return null;
    }

    return (
        <div className="card" style={{ marginBottom: 'var(--sp-xl)' }}>
            <div className="card-header">
                <h3>⚡ Live LLM stream</h3>
                <span className="badge badge-info">
                    {active ? 'Streaming…' : 'Recorded'}
                </span>
            </div>
            {stageLines?.length > 0 && (
                <ul style={{
                    margin: '0 0 var(--sp-md) 0',
                    paddingLeft: '1.2rem',
                    fontSize: '0.82rem',
                    color: 'var(--text-muted)',
                }}>
                    {stageLines.map((s, i) => (
                        <li key={i}>{s}</li>
                    ))}
                </ul>
            )}
            <div
                ref={scrollRef}
                className="llm-stream-scroll"
                style={{
                    maxHeight: '320px',
                    overflowY: 'auto',
                    background: 'rgba(0,0,0,0.25)',
                    borderRadius: '8px',
                    padding: 'var(--sp-md)',
                    fontFamily: 'var(--font-mono, ui-monospace, monospace)',
                    fontSize: '0.78rem',
                    lineHeight: 1.45,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                }}
            >
                {keys.length === 0 && (
                    <span style={{ color: 'var(--text-muted)' }}>Waiting for tokens…</span>
                )}
                {keys.map(k => (
                    <div key={k} style={{ marginBottom: 'var(--sp-lg)' }}>
                        <div style={{
                            color: 'var(--accent-cyan)',
                            fontSize: '0.72rem',
                            marginBottom: 'var(--sp-xs)',
                            opacity: 0.9,
                        }}>
                            {k.replace(/\|/g, ' · ')}
                        </div>
                        <div>
                            {streamBlocks[k]
                                ? streamBlocks[k]
                                : (
                                    <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                        Waiting for first token…
                                    </span>
                                )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export { streamKey };
