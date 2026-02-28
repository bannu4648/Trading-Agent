"""
Local test script using Ollama (free, no API key required).
Make sure Ollama is installed and running before using this script.
"""
import sys
import os
from datetime import date, datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from agent import FundamentalsAgent
from config import get_llm_client, DEFAULT_CONFIG


def save_report_md(report: str, ticker: str, trade_date: str, out_dir: str = "reports", data_retrieved_at: str = None) -> str:
    """Save report as a formatted Markdown file. Returns path to saved file."""
    os.makedirs(out_dir, exist_ok=True)
    safe_ticker = ticker.replace(" ", "_")
    filename = f"fundamentals_report_{safe_ticker}_{trade_date}.md"
    filepath = os.path.join(out_dir, filename)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    retrieved = data_retrieved_at if data_retrieved_at else now

    md_content = f"""# Fundamentals Analysis Report

| Field | Value |
|-------|--------|
| **Ticker** | {ticker} |
| **Report Date** | {trade_date} |
| **Report generated** | {now} |
| **Data retrieved at** | {retrieved} |

---

{report}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)
    return filepath


def save_report_pdf(report: str, ticker: str, trade_date: str, out_dir: str = "reports") -> str:
    """Save report as PDF (requires markdown and weasyprint). Returns path or raises."""
    try:
        import markdown
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError as e:
        raise ImportError(
            "PDF export requires: pip install markdown weasyprint\n"
            "Alternatively, save as Markdown and open the .md file to print/export as PDF."
        ) from e

    os.makedirs(out_dir, exist_ok=True)
    safe_ticker = ticker.replace(" ", "_")
    filename = f"fundamentals_report_{safe_ticker}_{trade_date}.pdf"
    filepath = os.path.join(out_dir, filename)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    md_doc = f"""# Fundamentals Analysis Report

| Field | Value |
|-------|--------|
| **Ticker** | {ticker} |
| **Report Date** | {trade_date} |
| **Report generated** | {now} |
| **Data retrieved at** | {now} |

---

{report}
"""
    html_str = markdown.markdown(
        md_doc,
        extensions=["tables", "nl2br"],
        output_format="html5",
    )
    full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Fundamentals Report - {ticker}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2em; line-height: 1.5; color: #333; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
    h2, h3 {{ margin-top: 1.2em; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5em 0.75em; text-align: left; }}
    th {{ background: #f5f5f5; font-weight: bold; }}
    tr:nth-child(even) {{ background: #fafafa; }}
  </style>
</head>
<body>
{html_str}
</body>
</html>
"""
    HTML(string=full_html).write_pdf(filepath)
    return filepath


def check_ollama_running():
    """Check if Ollama is running."""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def main():
    """Test the fundamentals agent with Ollama (local, free)."""
    
    print("="*60)
    print("Fundamentals Agent - Local Test (Ollama)")
    print("="*60)
    
    # Check if Ollama is running
    print("\n1. Checking if Ollama is running...")
    if not check_ollama_running():
        print("[X] Ollama is not running!")
        print("\nPlease install and start Ollama:")
        print("  1. Install: https://ollama.ai/download")
        print("  2. Pull a model: ollama pull llama3.2")
        print("  3. Make sure Ollama is running (it should start automatically)")
        print("\nOr use: ollama serve")
        return
    print("[OK] Ollama is running")
    
    # Check if model is available
    print("\n2. Checking for available models...")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags")
        models = [m['name'] for m in response.json().get('models', [])]
        if not models:
            print("[!] No models found. Please pull a model:")
            print("  ollama pull llama3.2")
            print("\nTrying anyway...")
        else:
            print(f"[OK] Found models: {', '.join(models)}")
    except Exception as e:
        print(f"[!] Could not check models: {e}")
        print("Trying anyway...")
    
    # Configuration for Ollama
    print("\n3. Configuring agent...")
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "ollama"
    config["model"] = "llama3.2"  # You can change this to any Ollama model
    config["debug"] = True
    config["max_iterations"] = 3  # Limit iterations for testing
    
    try:
        # Create LLM client
        print("   Creating LLM client...")
        llm = get_llm_client(config)
        print(f"[OK] LLM client created (model: {config['model']})")
        
        # Create agent
        print("   Creating Fundamentals Agent...")
        agent = FundamentalsAgent(
            llm=llm,
            max_iterations=config["max_iterations"],
            vendor="yfinance",  # yfinance is free, no API key needed
            debug=config["debug"],
        )
        print("[OK] Agent created")
        
        # Get ticker and report mode
        print("\n4. Running analysis...")
        use_canonical = input("Use identical (canonical) report? Same metrics for all tickers, no LLM. (Y/N) [Y]: ").strip().upper()
        if use_canonical == "N":
            use_canonical = False
        else:
            use_canonical = True
        ticker = input("Enter ticker symbol (e.g. AAPL, NVDA, MSFT): ").strip().upper()
        if not ticker:
            ticker = "AAPL"
            print(f"   No ticker entered, using default: {ticker}")
        trade_date = date.today().strftime("%Y-%m-%d")  # Today's date
        
        print(f"   Ticker: {ticker}")
        print(f"   Date: {trade_date}")
        if use_canonical:
            print(f"   Building canonical report (identical structure)...\n")
            from report_builder import build_canonical_report
            report = build_canonical_report(ticker, trade_date)
            state = {"iteration_count": 0, "tool_calls_made": []}
        else:
            print(f"   This may take a minute...\n")
            state = agent.analyze(
                ticker=ticker,
                trade_date=trade_date,
            )
            report = agent.get_report(state)
        
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        print(f"\nIterations used: {state.get('iteration_count', 0)}")
        if state.get("tool_calls_made") is not None:
            print(f"Tools called: {len(state.get('tool_calls_made', []))}")
        
        print("\n" + "="*60)
        print("FUNDAMENTALS REPORT")
        print("="*60)
        # Show full report
        if report:
            print(report)
            print(f"\n(Total length: {len(report)} characters)")
        else:
            print("No report generated. Check the messages in the state.")
        
        print("\n" + "="*60)
        print("[OK] Test completed successfully!")
        print("="*60)

        # Optional: save report to file
        if report:
            while True:
                save_choice = input("\nSave report to file? (Y/N): ").strip().upper()
                if save_choice in ("Y", "N", ""):
                    break
                print("Please enter Y or N.")
            if save_choice == "Y":
                while True:
                    fmt = input("Format: (1) Markdown (.md)  (2) PDF  (3) Both [1]: ").strip() or "1"
                    if fmt in ("1", "2", "3"):
                        break
                    print("Please enter 1, 2, or 3.")
                try:
                    if fmt in ("1", "3"):
                        path_md = save_report_md(report, ticker, trade_date)
                        print(f"[OK] Markdown saved: {path_md}")
                    if fmt in ("2", "3"):
                        path_pdf = save_report_pdf(report, ticker, trade_date)
                        print(f"[OK] PDF saved: {path_pdf}")
                except ImportError as e:
                    print(f"[!] {e}")
                    if fmt in ("2", "3"):
                        path_md = save_report_md(report, ticker, trade_date)
                        print(f"[OK] Markdown saved instead: {path_md}")
                except Exception as e:
                    print(f"[X] Could not save file: {e}")
        
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Make sure Ollama is running: ollama serve")
        print("2. Make sure you have a model: ollama pull llama3.2")
        print("3. Check if the model name is correct")
        print("4. Try a different model: ollama pull mistral")


if __name__ == "__main__":
    main()
