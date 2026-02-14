# Technical Analyst Agent (LangGraph)

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

## Quick start

```bash
python -m technical_agent.cli \
  --tickers AAPL,MSFT \
  --start 2023-01-01 \
  --end 2024-01-01 \
  --interval 1d
```

## Environment variables

```
LLM_PROVIDER=ollama | gemini
OLLAMA_MODEL=llama3:3b
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_MODEL=gemini-1.5-flash
GEMINI_API_KEY=your_api_key
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=512
```

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
uvicorn technical_agent.server:app --reload
```

Open: `http://localhost:8000`

The UI posts to `/api/chat` and returns the full structured JSON response.
