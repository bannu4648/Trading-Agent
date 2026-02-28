# Setup Guide

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**

   For OpenAI (recommended for testing):
   ```bash
   export OPENAI_API_KEY=your_key_here
   ```

   For Anthropic:
   ```bash
   export ANTHROPIC_API_KEY=your_key_here
   ```

   For Google:
   ```bash
   export GOOGLE_API_KEY=your_key_here
   ```

   Optional - for Alpha Vantage data:
   ```bash
   export ALPHA_VANTAGE_API_KEY=your_key_here
   ```

3. **Run Example**
   ```bash
   python example.py
   ```

## Project Structure

```
fundamentals_agent/
├── __init__.py          # Package initialization
├── agent.py             # Main LangGraph agent implementation
├── state.py             # State schema definition
├── tools.py             # Data retrieval tools
├── config.py            # LLM configuration
├── example.py           # Example usage script
├── test_agent.py        # Test script
├── requirements.txt     # Python dependencies
├── README.md            # Documentation
└── SETUP.md             # This file
```

## Usage Examples

### Basic Usage

```python
from fundamentals_agent import FundamentalsAgent, get_llm_client, DEFAULT_CONFIG

# Initialize
llm = get_llm_client(DEFAULT_CONFIG)
agent = FundamentalsAgent(llm=llm)

# Analyze
state = agent.analyze("NVDA", "2026-01-15")
report = agent.get_report(state)
print(report)
```

### Custom Configuration

```python
config = {
    "llm_provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "vendor": "alpha_vantage",  # or "yfinance"
}

llm = get_llm_client(config)
agent = FundamentalsAgent(
    llm=llm,
    max_iterations=10,
    vendor=config["vendor"],
    debug=True,
)
```

## Troubleshooting

### Import Errors
- Make sure you're running from the `fundamentals_agent` directory or have it in your Python path
- Check that all dependencies are installed: `pip install -r requirements.txt`

### API Key Errors
- Verify your API key is set: `echo $OPENAI_API_KEY`
- For Windows PowerShell: `$env:OPENAI_API_KEY="your_key"`

### Data Retrieval Errors
- yfinance is free and doesn't require an API key
- Alpha Vantage requires an API key (free tier available)
- Some tickers may have limited data availability

### LLM Errors
- Check your API key is valid
- Verify you have sufficient API credits/quota
- Try a different model if one doesn't work

## Next Steps

1. Read the full [README.md](README.md) for detailed documentation
2. Try the example script: `python example.py`
3. Customize the agent for your use case
4. Integrate into your trading system
