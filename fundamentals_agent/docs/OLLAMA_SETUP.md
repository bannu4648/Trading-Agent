# How to Set Up Ollama (Step by Step)

This guide walks you through setting up Ollama on **Windows** so you can run the Fundamentals Agent locally with no API keys.

---

## What You’re Installing

- **Ollama** – Runs AI models on your PC (free, no account needed).
- **A model** – The actual “brain” (e.g. Llama). Ollama downloads it once, then runs it locally.

---

## Step 1: Download and Install Ollama

1. Open your browser and go to: **https://ollama.ai/download**
2. Click **Download for Windows**.
3. Run the installer (e.g. `OllamaSetup.exe`).
4. Follow the prompts (Next → Install → Finish).
5. After install, Ollama usually starts in the background. You may see an Ollama icon in the system tray (bottom-right near the clock).

**Check it’s running:**  
Open a new **PowerShell** or **Command Prompt** and run:

```powershell
ollama --version
```

If you see a version number, Ollama is installed and available.

---

## Step 2: Download a Model

Ollama doesn’t do anything until you “pull” (download) at least one model.

1. Open **PowerShell** or **Command Prompt**.
2. Run:

```powershell
ollama pull llama3.2
```

- First time: it downloads the model (can be 1–2 GB). Wait until it says “success”.
- Later: it will just say the model is already present.

**Other models you can try later:**

| Command                 | Size (approx) | Use case              |
|-------------------------|----------------|------------------------|
| `ollama pull llama3.2`  | ~2 GB          | Good balance (recommended) |
| `ollama pull mistral`   | ~1 GB          | Smaller, faster        |
| `ollama pull qwen2.5`   | ~2 GB          | Good for analysis      |

To see what you have installed:

```powershell
ollama list
```

---

## Step 3: Install Python Dependencies for the Agent

1. Open **PowerShell** or **Command Prompt**.
2. Go to the project folder:

```powershell
cd "C:\Users\abhat\Downloads\Final Year Project\fundamentals_agent"
```

3. Create a virtual environment (recommended):

```powershell
python -m venv venv
.\venv\Scripts\Activate
```

You should see `(venv)` in your prompt.

4. Install the required packages:

```powershell
pip install -r requirements.txt
```

Wait until everything installs without errors.

---

## Step 4: Run the Fundamentals Agent

Still in the same terminal (with `venv` active and in `fundamentals_agent`):

```powershell
python test_local.py
```

What should happen:

1. The script checks if Ollama is running.
2. It checks if you have a model (e.g. `llama3.2`).
3. It runs the agent (it may take 1–2 minutes the first time).
4. You’ll see a fundamentals report for a sample stock (e.g. AAPL).

If anything fails, the script will print a short message; the next section helps with that.

---

## Quick Troubleshooting

### “Ollama is not running”

- **Option A:** Start it from the Start Menu: search for **Ollama** and open it. Wait a few seconds, then run `python test_local.py` again.
- **Option B:** In a terminal run:
  ```powershell
  ollama serve
  ```
  Leave that window open and run `python test_local.py` in another terminal.

### “No models found” or model not found

- Pull a model:
  ```powershell
  ollama pull llama3.2
  ```
- Check:
  ```powershell
  ollama list
  ```

### `ollama` command not found

- Restart the terminal after installing Ollama.
- If it still doesn’t work, close all terminals, open a new one, and try again. Ollama’s installer adds itself to the system PATH.

### Python or pip not found

- Install Python from https://www.python.org/downloads/ and make sure “Add Python to PATH” is checked.
- Use the same terminal where you ran `pip install -r requirements.txt` and `python test_local.py`.

### Script is very slow

- First run is slow (model loads into memory). Later runs are faster.
- For quicker tests, use a smaller model: `ollama pull mistral` and in `test_local.py` set `config["model"] = "mistral"`.

---

## Summary Checklist

- [ ] Ollama installed from https://ollama.ai/download  
- [ ] `ollama --version` works in a terminal  
- [ ] At least one model pulled: `ollama pull llama3.2`  
- [ ] In `fundamentals_agent` folder: `pip install -r requirements.txt`  
- [ ] Run: `python test_local.py`  

Once all steps work, you’re set up to use Ollama with this project. For more detail (other OS, config options), see **LOCAL_SETUP.md**.
