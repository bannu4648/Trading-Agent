"""
Simple test script for the Fundamentals Agent.
"""
import sys
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from agent import FundamentalsAgent
from config import get_llm_client, DEFAULT_CONFIG


def test_agent():
    """Test the fundamentals agent with a simple example."""
    print("Testing Fundamentals Agent...")
    
    # Check for API key
    provider = DEFAULT_CONFIG.get("llm_provider", "openai")
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not set. Using mock mode.")
        return
    
    try:
        # Create LLM
        llm = get_llm_client(DEFAULT_CONFIG)
        
        # Create agent
        agent = FundamentalsAgent(
            llm=llm,
            max_iterations=3,  # Limit iterations for testing
            vendor="yfinance",
            debug=True,
        )
        
        # Test with a simple ticker
        print("\nRunning analysis for NVDA...")
        state = agent.analyze(
            ticker="NVDA",
            trade_date="2026-01-15",
        )
        
        # Get report
        report = agent.get_report(state)
        
        print("\n" + "="*60)
        print("REPORT GENERATED:")
        print("="*60)
        print(report[:500] + "..." if len(report) > 500 else report)
        print("="*60)
        
        print(f"\n✓ Test completed successfully!")
        print(f"  Iterations: {state.get('iteration_count', 0)}")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_agent()
