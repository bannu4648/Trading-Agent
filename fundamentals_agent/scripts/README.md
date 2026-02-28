# Scripts

Non-essential scripts for testing, batch runs, and comparison.

| Script | Description |
|--------|-------------|
| `test_local.py` | Interactive test with Ollama; optional canonical vs LLM report |
| `test_agent.py` | Quick agent test (requires API key or Ollama) |
| `example.py` | Example usage with cloud LLM |
| `run_batch.py` | Run reports for AAPL, NVDA, MSFT |
| `run_batch_top10.py` | Run reports for top 10 US stocks by market cap |
| `compare_reports.py` | Check report structure for AAPL, NVDA, MSFT |
| `compare_reports_top10.py` | Check report structure for top 10 |
| `check_ollama.py` | Verify Ollama is running and models are available |

Run from the **project root** (fundamentals_agent):

```bash
python scripts/run_batch_top10.py
python scripts/compare_reports_top10.py
```

Or from inside `scripts/`:

```bash
cd scripts
python run_batch_top10.py
```
(Imports may require `sys.path` or running from parent.)
