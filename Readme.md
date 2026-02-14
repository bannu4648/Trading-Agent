# Trading-Agent (Technical Analyst Agent)

Standalone technical analyst agent using LangGraph, yfinance, and pandas-ta.

## Features

- Fetches OHLCV data via yfinance
- Computes a suite of technical indicators
- Includes intraday indicator presets and VWAP
- Generates multiple rule-based signals
- Produces an integration handoff schema for other agents
- Optional LLM summaries (Ollama or Gemini)
- Plugin-style registry for custom signals
- Optional FastAPI UI to chat with the agent

## Dependency management (uv)

This project uses `uv` with `pyproject.toml` (instead of `requirements.txt`).
Use Python `3.12` or `3.13`.

```bash
uv sync
```

Run commands inside the managed environment with:

```bash
uv run <command>
```

## Quick start

```bash
uv run python -m technical_agent.cli \
  --tickers AAPL,MSFT \
  --start 2023-01-01 \
  --end 2024-01-01 \
  --interval 1d
```

## Environment variables

Create and edit `.env` at the project root. It is loaded automatically by the app.

```
LLM_PROVIDER=ollama | gemini
OLLAMA_MODEL=llama3:3b
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_MODEL=gemini-1.5-flash
GEMINI_API_KEY=your_api_key
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=512

# Langfuse tracing (self-hosted/local supported)
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PROJECT=technical-agent
LANGFUSE_SESSION_ID=local-dev
LANGFUSE_USER_ID=dev-user
LANGFUSE_RELEASE=dev
```

## Tracing (Langfuse)

When `LANGFUSE_ENABLED=true`, the agent sends traces for:

- LangGraph run execution
- Indicator/signals pipeline spans
- Each LLM summary call

The integration uses the official open-source Langfuse Python SDK and LangChain callback handler.

## Custom signals

Add your own signals in `technical_agent/signals/expand.py` or create a new module.
Then pass `--extra-signal-module your.module.path` or set
`AgentConfig.extra_signal_modules` programmatically.

## Integration schema

The agent emits a `handoff` payload inside the output, and the JSON schema is stored at:

```
technical_agent/schema/technical_handoff.schema.json
```

## UI (chat)

Run the API server:

```bash
uv run uvicorn technical_agent.server:app --reload
```

Open: `http://localhost:8000`

The UI posts to `/api/chat` and returns the full structured JSON response.
