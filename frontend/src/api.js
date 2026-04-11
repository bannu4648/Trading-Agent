const API_BASE = import.meta.env.VITE_API_BASE
  ?? (import.meta.env.DEV ? 'http://localhost:8000' : 'https://trading-agent-backend.onrender.com');

export async function startAnalysis(tickers, interval = '1d') {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers, interval }),
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
