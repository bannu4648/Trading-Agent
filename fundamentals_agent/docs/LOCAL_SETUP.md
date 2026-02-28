# Local Setup Guide (Free - No API Keys Required)

This guide will help you run the Fundamentals Agent locally using **Ollama**, which is completely free and doesn't require any API keys.

## Quick Start

### Step 1: Install Ollama

**Windows:**
1. Download from: https://ollama.ai/download
2. Run the installer
3. Ollama will start automatically

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Step 2: Pull a Model

Open a terminal and run:

```bash
ollama pull llama3.2
```

This downloads a free, open-source LLM model (~2GB). Other good options:
- `ollama pull mistral` (smaller, faster)
- `ollama pull llama3.1` (larger, more capable)
- `ollama pull qwen2.5` (good for analysis)

### Step 3: Install Python Dependencies

```bash
cd fundamentals_agent
pip install -r requirements.txt
```

### Step 4: Run the Local Test

```bash
python test_local.py
```

That's it! No API keys needed.

## How It Works

- **Ollama**: Runs LLM models locally on your machine (free, private)
- **yfinance**: Free stock data (no API key needed)
- **LangGraph**: Orchestrates the agent workflow

## Troubleshooting

### Ollama Not Running

If you get "Ollama is not running":
```bash
# Start Ollama manually
ollama serve
```

### Model Not Found

If you get model errors:
```bash
# List available models
ollama list

# Pull a model if needed
ollama pull llama3.2
```

### Slow Performance

Local models are slower than cloud APIs. Options:
1. Use a smaller model: `ollama pull mistral`
2. Reduce iterations in config: `max_iterations=2`
3. Use a GPU if available (Ollama will use it automatically)

### Port Already in Use

If port 11434 is busy:
```bash
# Change Ollama port
export OLLAMA_HOST=localhost:11435
ollama serve
```

Then update config:
```python
config["base_url"] = "http://localhost:11435"
```

## Configuration

Edit `test_local.py` to customize:

```python
config["model"] = "mistral"  # Change model
config["max_iterations"] = 5  # More iterations = more thorough
config["vendor"] = "yfinance"  # Data source
```

## Available Models

Check what's available:
```bash
ollama list
```

Popular models for analysis:
- `llama3.2` - Good balance (recommended)
- `mistral` - Fast, smaller
- `qwen2.5` - Good for financial analysis
- `llama3.1` - More capable but slower

## Performance Tips

1. **First run is slow**: Model needs to load into memory
2. **Subsequent runs faster**: Model stays in memory
3. **Use smaller models**: For faster testing
4. **Reduce iterations**: For quicker results

## Next Steps

Once you've verified it works locally:
1. Test with different tickers
2. Experiment with different models
3. Adjust `max_iterations` for depth vs speed
4. When ready, switch to cloud APIs (OpenAI, etc.) for production

## Example Output

```
============================================================
Fundamentals Agent - Local Test (Ollama)
============================================================

1. Checking if Ollama is running...
✓ Ollama is running

2. Checking for available models...
✓ Found models: llama3.2

3. Configuring agent...
   Creating LLM client...
✓ LLM client created (model: llama3.2)
   Creating Fundamentals Agent...
✓ Agent created

4. Running analysis...
   Ticker: AAPL
   Date: 2026-01-15
   This may take a minute...

[Agent runs...]

============================================================
ANALYSIS COMPLETE
============================================================

Iterations used: 3
Tools called: 4

============================================================
FUNDAMENTALS REPORT
============================================================
[Your analysis report here...]
```

## Switching to Cloud APIs Later

When you're ready to use cloud APIs (faster, more capable):

1. Get an API key (OpenAI, Anthropic, etc.)
2. Set environment variable: `export OPENAI_API_KEY=your_key`
3. Update config: `config["llm_provider"] = "openai"`
4. Run: `python example.py`

The code structure stays the same - just change the provider!
