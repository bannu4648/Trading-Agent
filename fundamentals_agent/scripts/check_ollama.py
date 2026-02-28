"""
Quick script to verify your Ollama setup before running the agent.
Run from project root: python scripts/check_ollama.py
"""
import sys
import os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

def main():
    print("=" * 50)
    print("Ollama setup check")
    print("=" * 50)

    # 1. Check Python
    print("\n1. Python version:", sys.version.split()[0])
    if sys.version_info < (3, 8):
        print("   Need Python 3.8 or higher.")
        return
    print("   OK")

    # 2. Check requests (used to talk to Ollama)
    try:
        import requests
        print("\n2. requests library: installed")
    except ImportError:
        print("\n2. requests library: NOT FOUND")
        print("   Run: pip install requests")
        return

    # 3. Check if Ollama is running
    print("\n3. Ollama server...")
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            print("   Ollama is running")
        else:
            print("   Unexpected response:", r.status_code)
            return
    except requests.exceptions.ConnectionError:
        print("   Ollama is NOT running.")
        print("   Start it: run 'Ollama' from Start Menu, or in a terminal: ollama serve")
        return
    except Exception as e:
        print("   Error:", e)
        return

    # 4. List models
    print("\n4. Installed models:")
    try:
        data = r.json()
        models = data.get("models", [])
        if not models:
            print("   No models found. Run: ollama pull llama3.2")
            return
        for m in models:
            name = m.get("name", "?")
            print("   -", name)
        print("   OK (use one of these in test_local.py)")
    except Exception as e:
        print("   Could not list models:", e)

    print("\n" + "=" * 50)
    print("Setup looks good. Run: python test_local.py")
    print("=" * 50)

if __name__ == "__main__":
    main()
