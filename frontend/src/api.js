// Set VITE_API_BASE in your deployment environment (Render/Netlify env vars)
// For local dev, falls back to localhost automatically
const API_BASE = import.meta.env.VITE_API_BASE
  ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

/** First status check after starting a job (quick initial partial snapshot). */
export const JOB_STATUS_FIRST_POLL_MS = 3_000;
/** Interval between `/api/status` polls while a job is running. */
export const JOB_STATUS_POLL_INTERVAL_MS = 10_000;

export async function startAnalysis(tickers, interval = '1d') {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers, interval }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

/** Top-20 long/short pilot: fixed universe, risk allocator + trader on the book. */
export async function startTop20LongShort(options = {}) {
  const body = {
    end_date: options.endDate ?? null,
    start_date: options.startDate ?? null,
    lookback_days: options.lookbackDays ?? 365,
    interval: options.interval ?? '1d',
    use_llm_interpret: options.useLlmInterpret !== false,
    k_long: options.kLong ?? 10,
    k_short: options.kShort ?? 10,
    gross_long: options.grossLong ?? 1.0,
    gross_short: options.grossShort ?? 0.5,
    max_single_long: options.maxSingleLong ?? 0.05,
    max_single_short: options.maxSingleShort ?? 0.03,
    execute_paper: options.executePaper === true,
    paper_state_file: options.paperStateFile ?? null,
    paper_initial_cash: options.paperInitialCash ?? 100_000,
    paper_force: options.paperForce === true,
  };
  const res = await fetch(`${API_BASE}/api/analyze/top20-longshort`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

/** S&P 500: wide technicals → screen → deep research on candidates (see docs/PIPELINE.md). */
export async function startSp500Screened(options = {}) {
  const body = {
    end_date: options.endDate ?? null,
    start_date: options.startDate ?? null,
    lookback_days: options.lookbackDays ?? 365,
    interval: options.interval ?? '1d',
    enable_llm_summary_technical: options.enableLlmSummaryTechnical === true,
    candidate_pool_mult: options.candidatePoolMult ?? 3,
    max_candidates: options.maxCandidates ?? 30,
    k_long: options.kLong ?? 10,
    k_short: options.kShort ?? 10,
    gross_long: options.grossLong ?? 1.0,
    gross_short: options.grossShort ?? 0.5,
    max_single_long: options.maxSingleLong ?? 0.05,
    max_single_short: options.maxSingleShort ?? 0.03,
    use_llm_interpret: options.useLlmInterpret !== false,
    deep_sentiment: options.deepSentiment !== false,
    deep_fundamentals: options.deepFundamentals !== false,
    deep_synthesis: options.deepSynthesis !== false,
    limit_universe: options.limitUniverse ?? 0,
    execute_paper: options.executePaper === true,
    paper_state_file: options.paperStateFile ?? null,
    paper_initial_cash: options.paperInitialCash ?? 100_000,
    paper_force: options.paperForce === true,
  };
  const res = await fetch(`${API_BASE}/api/analyze/sp500-screened`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/api/status/${jobId}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function listResults() {
  const res = await fetch(`${API_BASE}/api/results`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getResult(filename) {
  const res = await fetch(`${API_BASE}/api/results/${filename}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

/** Daily simulated paper portfolio rows (SQLite); see Performance page. */
export async function getPaperHistory(limit = 2000) {
  const q = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(`${API_BASE}/api/paper-history?${q}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

/** UTC calendar date + whether paper_daily already has a row for today. */
export async function getPaperDailyStatus() {
  const res = await fetch(`${API_BASE}/api/paper-daily-status`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
// TODO: remove this later
/** Local/report helper: regenerate the labeled April historical paper simulation dataset. */
export async function generateAprilPaperSimulation() {
  const res = await fetch(`${API_BASE}/api/dev/generate-april-paper-simulation`, {
    method: 'POST',
  });
  if (!res.ok) {
    let detail = '';
    try {
      const payload = await res.json();
      detail = payload?.detail ? `: ${JSON.stringify(payload.detail)}` : '';
    } catch {
      detail = '';
    }
    throw new Error(`API error: ${res.status}${detail}`);
  }
  return res.json();
}

/**
 * Background job: full S&P 500 daily paper pipeline (same as run_daily_paper_trade.py).
 * Poll getJobStatus(job_id) until completed / failed.
 */
export async function startDailyPaper(options = {}) {
  const body = {
    trade_date: options.tradeDate ?? null,
    skip_if_already_run: options.skipIfAlreadyRun === true,
    no_llm: options.noLlm !== false,
    live_sentiment: options.liveSentiment === true,
    live_fundamentals: options.liveFundamentals === true,
    live_synthesis: options.liveSynthesis === true,
    k_long: options.kLong ?? 25,
    k_short: options.kShort ?? 25,
    gross_long: options.grossLong ?? 1.0,
    gross_short: options.grossShort ?? 0.5,
    max_single_long: options.maxSingleLong ?? 0.05,
    max_single_short: options.maxSingleShort ?? 0.03,
    lookback_days: options.lookbackDays ?? 365,
    initial_cash: options.initialCash ?? 100_000,
    candidate_pool_mult: options.candidatePoolMult ?? 3,
    limit_universe: options.limitUniverse ?? 0,
    state_file: options.stateFile ?? null,
  };
  const res = await fetch(`${API_BASE}/api/analyze/daily-paper`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

/**
 * Subscribe to SSE-style events from GET /api/stream/{jobId} (token chunks, stages, job_done).
 * @param {string} jobId
 * @param {(ev: Record<string, unknown>) => void} onEvent
 * @param {AbortSignal} [signal]
 * @param {(err: Error) => void} [onError] non-abort failures (e.g. network, 404)
 */
export function consumeJobStream(jobId, onEvent, signal, onError) {
  const url = `${API_BASE}/api/stream/${jobId}`;
  (async () => {
    try {
      const res = await fetch(url, { signal });
      if (!res.ok) throw new Error(`stream ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
        let sep;
        while ((sep = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, sep).trim();
          buffer = buffer.slice(sep + 2);
          if (!block || block.startsWith(':')) continue;
          const lines = block.split('\n');
          for (const line of lines) {
            if (line.startsWith('data:')) {
              const raw = line.startsWith('data: ') ? line.slice(6) : line.slice(5);
              try {
                onEvent(JSON.parse(raw.trim()));
              } catch {
                /* ignore malformed */
              }
            }
          }
        }
      }
    } catch (e) {
      if (signal?.aborted || e?.name === 'AbortError') return;
      console.warn('Job stream:', e);
      if (typeof onError === 'function') {
        onError(e instanceof Error ? e : new Error(String(e)));
      }
    }
  })();
}
