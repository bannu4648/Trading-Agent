"""
Example usage of the Fundamentals Agent.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from agent import FundamentalsAgent
from config import get_llm_client, DEFAULT_CONFIG


def main():
    """Example usage of the Fundamentals Agent."""
    
    # Configuration
    config = DEFAULT_CONFIG.copy()
    config["debug"] = True  # Enable debug mode to see progress
    
    # Create LLM client
    print("Initializing LLM client...")
    llm = get_llm_client(config)
    
    # Create Fundamentals Agent
    print("Creating Fundamentals Agent...")
    agent = FundamentalsAgent(
        llm=llm,
        max_iterations=5,
        vendor=config["vendor"],
        debug=config["debug"],
    )
    
    # Run analysis
    ticker = "NVDA"  # NVIDIA
    trade_date = "2026-01-15"
    
    print(f"\n{'='*60}")
    print(f"Analyzing fundamentals for {ticker} as of {trade_date}")
    print(f"{'='*60}\n")
    
    # Run the analysis
    final_state = agent.analyze(
        ticker=ticker,
        trade_date=trade_date,
    )
    
    # Extract and display report
    report = agent.get_report(final_state)
    
    print("\n" + "="*60)
    print("FUNDAMENTALS ANALYSIS REPORT")
    print("="*60)
    print(report)
    print("="*60)
    
    # Display metadata
    print(f"\nIterations used: {final_state.get('iteration_count', 0)}")
    print(f"Tools called: {final_state.get('tool_calls_made', [])}")
    
    return final_state


if __name__ == "__main__":
    # Check for required environment variables
    required_vars = []
    
    config = DEFAULT_CONFIG.copy()
    provider = config.get("llm_provider", "openai").lower()
    
    if provider == "openai":
        required_vars.append("OPENAI_API_KEY")
    elif provider == "anthropic":
        required_vars.append("ANTHROPIC_API_KEY")
    elif provider == "google":
        required_vars.append("GOOGLE_API_KEY")
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set the required API keys:")
        for var in missing_vars:
            print(f"  export {var}=your_api_key_here")
        exit(1)
    
    # Run example
    main()
