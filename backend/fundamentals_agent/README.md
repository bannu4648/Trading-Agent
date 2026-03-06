# Fundamentals Agent

Generate a **fundamentals report** for any US stock by typing the ticker. Same structure and metrics for every company; no API key required by default.

## Quick start

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run**
   ```bash
   python main.py AAPL
   ```
   Or run without arguments and enter the ticker when prompted:
   ```bash
   python main.py
   Ticker symbol: NVDA
   ```

The report is printed in the terminal. You can then save it to the `reports/` folder (Y when prompted).

## Usage

```bash
# Report for one stock (ticker as argument)
python main.py MSFT

# Report for one stock (ticker at prompt)
python main.py
```

- **Data:** yfinance (free). Optional: set `ALPHA_VANTAGE_API_KEY` for fallback when data is missing.
- **Output:** Identical sections and metrics for every ticker (Company Overview, Key Financial Metrics, Balance Sheet, Income Statement, Cash Flow, Growth and Valuation, Summary Table). Missing data appears as N/A.

## Project layout

```
fundamentals_agent/
├── main.py              # Entry point: run with a ticker
├── agent.py             # LangGraph agent (optional LLM mode)
├── config.py            # LLM and provider config
├── state.py             # Agent state schema
├── tools.py             # Data tools + structured fetchers
├── report_builder.py    # Canonical report (no LLM)
├── report_schema.py    # Report sections and metric lists
├── requirements.txt
├── README.md
├── reports/             # Saved reports (optional)
├── scripts/             # Batch runs, tests, comparison (see scripts/README.md)
└── docs/                # Setup and architecture (see docs/README.md)
```

## Optional: local LLM (Ollama)

For an LLM-based report instead of the canonical one, use the scripts and Ollama:

1. Install [Ollama](https://ollama.ai/download) and run `ollama pull llama3.2`
2. See **docs/OLLAMA_SETUP.md** for details
3. Use `python scripts/test_local.py` and choose “N” for canonical to use the LLM agent

## Optional: Alpha Vantage

To fill in missing data (e.g. some cash flow or balance sheet items), set:

```bash
set ALPHA_VANTAGE_API_KEY=your_key
```

(Use `export` on Mac/Linux.)

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## License

Based on the TradingAgents framework (Apache 2.0).  
Original: https://github.com/TauricResearch/TradingAgents
