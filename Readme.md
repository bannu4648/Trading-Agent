# Trading-Agent

Trading-Agent is a full-stack multi-agent system for stock research, portfolio construction, and local paper-trading evaluation. It combines quantitative technical analysis, sentiment analysis, fundamental snapshots, LLM synthesis, long/short allocation, trade-order generation, portfolio validation, and a React dashboard for running and reviewing jobs.

The application is designed for analysis and simulated execution. It does not place real brokerage orders.

## Current Capabilities

- Three run modes in the web app: custom ticker analysis, Top 20 long/short, and S&P 500 screened analysis.
- Wide-universe S&P 500 screening that runs technical analysis first, selects a smaller candidate set, then performs deeper sentiment, fundamentals, synthesis, allocation, trading, and validation.
- Long/short allocator support for Top 20 and S&P 500 screened runs, including signed target weights for short positions.
- Live job status and Server-Sent Events streaming for stage updates, LLM output chunks, and completion events.
- Results dashboard with portfolio allocation charts, per-ticker research tabs, trade orders, risk reports, and partial loading states for long-running jobs.
- Local paper-trading support using JSON portfolio state plus SQLite daily history.
- Paper performance page with status, daily paper job launch, refresh controls, equity charts, return charts, and historical rows.
- Persistent frontend session state so pipeline progress and results survive navigation between pages.

For a deeper architecture guide, see [`docs/PROJECT_README.md`](docs/PROJECT_README.md). For stage-by-stage pipeline details and troubleshooting, see [`docs/PIPELINE.md`](docs/PIPELINE.md).

## Quick Start

### 1. Backend Setup

Create and activate a Python environment from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the FastAPI backend:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. Frontend Setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### 3. Optional CLI Runs

Run a custom ticker analysis:

```bash
python backend/run_analysis.py --tickers AAPL,NVDA,MSFT
```

Run the daily local paper workflow:

```bash
python backend/run_daily_paper_trade.py --date $(date -u +%F) --no-llm
```

## Application Pages

| Page | Route | Purpose |
|------|-------|---------|
| Launch | `/` | Landing page for selecting the main workflow. |
| Custom Ticker | `/run/developer?mode=custom` | Analyze user-supplied tickers with the full research stack and ReAct trader. |
| Top 20 Long/Short | `/run/developer?mode=top20` | Run a curated large-cap universe through research, allocator, trader, and validation. |
| S&P 500 Screened | `/run/developer?mode=sp500` | Screen the S&P 500, research selected candidates, then build a long/short book. |
| Results History | `/history` | Browse saved JSON run artifacts from `results/`. |
| Long/Short | `/longshort` | Review long/short-oriented outputs. |
| Paper Performance | `/performance` | View local paper-trading equity history, daily status, and performance charts. |

## Repository Layout

```text
Trading-Agent/
├── backend/
│   ├── main.py                     # FastAPI app, job lifecycle, stream/status endpoints
│   ├── run_analysis.py             # Custom ticker pipeline
│   ├── run_top20_longshort_job.py   # Top 20 long/short pipeline
│   ├── run_sp500_screened_job.py    # S&P 500 screened pipeline
│   ├── run_daily_paper_trade.py     # Local daily paper workflow
│   ├── technical_agent/             # OHLCV indicators and technical signals
│   ├── sentiment_agent/             # LangGraph sentiment workflow
│   ├── fundamentals_agent/          # Financial snapshot tools
│   ├── summarizer_agent/            # LLM synthesis layer
│   ├── trader_agent/                # Recommendation adapter and trader logic
│   ├── portfolio_longshort/         # Deterministic long/short allocator
│   ├── portfolio_validator/         # Risk validation
│   ├── paper_simulator/             # Local rebalance and portfolio metrics
│   └── portfolio_history/           # SQLite paper history storage
├── frontend/
│   ├── src/pages/                   # Launch, pipeline, history, long/short, performance pages
│   ├── src/components/              # Dashboards, charts, stream panels, ticker cards
│   └── package.json
├── docs/
│   ├── PROJECT_README.md
│   └── PIPELINE.md
├── results/                         # JSON results, paper_state.json, SQLite history
├── requirements.txt
├── pyproject.toml
└── .env
```

## Main Pipeline Modes

### Custom Ticker Analysis

Custom mode accepts a user-supplied ticker list. The backend runs technical analysis, sentiment, fundamentals, synthesis, recommendation normalization, the ReAct trader, and portfolio validation. This path is best for focused research on a small set of names.

### Top 20 Long/Short

Top 20 mode uses a curated large-cap universe. Every ticker receives full research coverage, then the long/short allocator selects and sizes the strongest long and short candidates. The trader follows allocator target weights so the displayed orders and portfolio chart stay aligned.

### S&P 500 Screened

S&P 500 screened mode is optimized for larger universes. It performs a wide technical pass across the index, ranks candidates using formula-based recommendation scores, then performs deeper sentiment, fundamentals, synthesis, allocation, trading, and validation only on the selected candidate set.

## Agent Stack

| Component | Role |
|-----------|------|
| Technical Analyst | Loads price data, computes indicators, and emits rule-based technical signals. |
| Sentiment Agent | Uses a LangGraph workflow to combine news, analyst, social, and web context where enabled. |
| Fundamentals Layer | Retrieves financial metrics such as valuation, profitability, leverage, growth, and quality indicators. |
| Summarizer Agent | Produces a human-readable synthesis from technical, sentiment, and fundamental evidence. |
| Research Adapter | Converts heterogeneous agent output into structured recommendations: signal, conviction, expected return, volatility, and rationale. |
| Risk Portfolio Agent | Builds signed target weights for long/short books. |
| Trader Agent | Converts recommendations or allocator targets into actionable simulated orders. |
| Portfolio Validator | Checks the proposed book for concentration, exposure, and risk warnings. |
| Paper Simulator | Rebalances a local simulated portfolio and records daily performance history. |

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Backend health check. |
| `POST` | `/api/analyze` | Start a custom ticker analysis job. |
| `POST` | `/api/analyze/top20-longshort` | Start a Top 20 long/short job. |
| `POST` | `/api/analyze/sp500-screened` | Start an S&P 500 screened job. |
| `POST` | `/api/analyze/daily-paper` | Start the local daily paper workflow. |
| `GET` | `/api/status/{job_id}` | Poll job state and partial results. |
| `GET` | `/api/stream/{job_id}` | Stream stage and LLM events over SSE. |
| `GET` | `/api/results` | List saved result JSON files. |
| `GET` | `/api/results/{filename}` | Load a saved result file. |
| `GET` | `/api/paper-history` | Return paper performance history from SQLite. |
| `GET` | `/api/paper-daily-status` | Report whether today's paper row exists. |

## Configuration

Create a `.env` file in the project root. Values depend on which providers and data sources you want to enable:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.3-70b-versatile

GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash

MISTRAL_API_KEY=your_mistral_key
FINNHUB_API_KEY=your_finnhub_key
ALPHAVANTAGE_API_KEY=your_alphavantage_key

SENTIMENT_FAST_PIPELINE=true
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your_langsmith_key
```

Most jobs can still run in reduced mode when some optional data or LLM providers are unavailable, but richer sentiment and synthesis require valid provider keys.

## Outputs

Saved analysis runs are written to `results/*.json`. Local paper-trading state is stored in `results/paper_state.json`, and daily performance history is stored in `results/paper_daily_history.sqlite` unless overridden by configuration.

The React UI reads these artifacts through the FastAPI API and renders allocation charts, ticker-level research, trade orders, validation reports, and paper-performance history.
