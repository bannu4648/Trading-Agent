# Trading-Agent (Technical + Sentiment Analysis)

A unified stock analysis platform that combines **Technical Analysis** (LangGraph-based indicators and signals) with **Multi-Agent Sentiment Analysis** (News, Social Media, Analyst Consenus, and Web Search).

## 🚀 Quick Start

1. **Install Dependencies**
   Ensure you have Python 3.12+ installed.
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install -r pyproject.toml # or just use the pre-installed venv
   ```

2. **Run Full Analysis**
   The unified orchestrator runs both technical and sentiment agents and saves a combined JSON report.
   ```bash
   PYTHONPATH=. ./venv/bin/python3 run_analysis.py --tickers AAPL,MSFT
   ```

3. **Run the Dashboard (UI)**
   Launch the visual interface to perform analysis and view recommendations.
   ```bash
   PYTHONPATH=. ./venv/bin/python3 dashboard.py
   ```
   Open `http://localhost:8050` in your browser.

## 🛠️ Components

### 1. Technical Analyst Agent
- Fetches OHLCV data and computes 60+ indicators (RSI, MACD, Bollinger Bands, etc.).
- Generates rule-based signals and optional LLM-driven summaries.
- Supports **Ollama**, **Gemini**, and **Groq**.

### 2. Multi-Agent Sentiment Agent
- A sequential LangGraph pipeline that scrapes and analyzes:
  - **News**: Recent headlines from Finviz/Yahoo.
  - **Social**: Reddit buzz via ApeWisdom.
  - **Analysts**: Institutional consensus via Finnhub.
  - **Web**: Recent articles via DuckDuckGo.
- Uses a weighted aggregator and a Bull vs. Bear debate agent to reach a final sentiment score.

### 3. Summarizer Agent
- A high-level synthesis agent that takes the technical and sentiment results and provides a final natural-language recommendation (Buy/Hold/Sell) using the LLM.

### 4. Dash UI
- A premium, dark-mode dashboard built with Dash and Bootstrap.
- Allows ticker-based analysis triggering and visual result inspection.


## ⚙️ Configuration (LLM Setup)

Create a `.env` file in the project root. Both agents share these settings.

### Possible LLM Providers
| Provider | `LLM_PROVIDER` Value | Required Key | Default Model |
|----------|----------------------|--------------|---------------|
| **Groq** | `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| **Gemini** | `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| **Ollama** | `ollama` | (None) | `llama3.1:8b` |

### Example `.env`
```env
# --- LLM Provider ---
LLM_PROVIDER=groq

# --- API Keys ---
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
FINNHUB_API_KEY=your_finnhub_key

# --- Model Names ---
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_MODEL=gemini-2.0-flash
OLLAMA_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434

# --- Sentiment Agent Weights ---
WEIGHT_NEWS=0.35
WEIGHT_SOCIAL=0.25
WEIGHT_ANALYST=0.25
WEIGHT_WEB=0.15
```

## 📊 Output
Results are saved as JSON files in the `./results/` directory with the following structure:
```json
{
  "results": {
    "AAPL": {
      "technical": { "indicators": {...}, "signals": [...], "summary": "..." },
      "sentiment": { "sentiment_score": 0.42, "sentiment_label": "POSITIVE", ... }
    }
  }
}
```

## 🧪 Advanced Usage
You can still run components individually:
- **Technical Agent CLI**: `python3 -m technical_agent.cli --tickers AAPL`
- **Sentiment Agent CLI**: `python3 sentiment_agent/main.py --ticker AAPL`
