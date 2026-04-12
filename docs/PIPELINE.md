# Pipeline reference

This document describes **what runs, in what order**, for the main backend flows: **custom ticker analysis**, **top‑20 long/short**, and **S&P 500 screened**. It explains **methodologies** (technical, sentiment, adapter, allocator, screening, trader), the **Trader Agent** (ReAct vs allocator-backed path), **execution** (API vs local paper simulator), and common UI outcomes such as **“N/A” for sizing method**.

The **frontend** exposes all three as modes on **Run pipeline** (`frontend/src/pages/AnalysisPage.jsx`): Custom tickers, Top 20 long/short, and S&P 500 screened.

---

## 0. Three pipelines at a glance

| Aspect | Custom (`POST /api/analyze`) | Top 20 (`/api/analyze/top20-longshort`) | S&P 500 screened (`/api/analyze/sp500-screened`) |
|--------|------------------------------|----------------------------------------|---------------------------------------------------|
| **Ticker source** | User-supplied list | `universe/top20.py` (fixed ~20 names) | `universe/sp500.py` (~500), then **screen** |
| **Technical** | Batch on listed tickers | Batch on 20 | **Phase 1:** batch on full universe; LLM per ticker optional (`enable_llm_summary_technical`, default **off**) |
| **Sentiment / fundamentals / synthesis** | Every ticker in job | Every ticker in universe | **Only on screened candidates** (after formula rank) |
| **Research adapter** | `build_research_output`, optional LLM interpret | Same | Same (on candidate set only) |
| **Long/short allocator** | Not in default `run_full_analysis` job\* | `RiskPortfolioAgent.build_target_weights` | Same as Top 20 |
| **Trader** | **ReAct** + four BUY-only sizing tools | **Allocator-backed** (`run_trader_from_allocator_targets`) | Same as Top 20 |
| **Validation** | On trader orders | On allocator synthetic orders (aligned with trader) | Same as Top 20 |
| **Typical runtime** | Scales with N tickers | ~20 deep dives | **Long** (wide technicals + up to ~30 deep) |

\*The custom analysis path in `run_analysis.py` runs the trader and validator on the ReAct output; it does not run the long/short allocator unless you extend the orchestrator.

---

## 0b. Methodologies and implementations

### Technical analysis

- **Implementation:** `TechnicalAnalystAgent` (`backend/technical_agent/`): loads OHLCV (e.g. yfinance), computes indicators and rule-based signals, optionally calls an LLM **per ticker** for a narrative when `enable_llm_summary` is true (env / `AgentConfig`).
- **Role in pipelines:** Feeds structured fields into the **research adapter** (`trader_agent/adapter.py` → `StockRecommendation`: signal, conviction, expected return, volatility).

### Sentiment

- **Implementation:** `OrchestratorAgent` + LangGraph (`backend/sentiment_agent/`). With **`SENTIMENT_FAST_PIPELINE=true`**, a reduced subgraph runs (e.g. news + analyst only), which is recommended for large batches.
- **Role:** Produces scores/text merged into per-ticker `combined["results"][ticker]["sentiment"]` for synthesis and adapter.

### Fundamentals

- **Implementation:** In the main jobs, **`fetch_fundamentals_data`** (`fundamentals_agent/tools.py`) supplies a snapshot (yfinance-first), not necessarily the full LangGraph fundamentals agent.
- **Role:** Same merge path as sentiment before synthesis.

### Synthesis

- **Implementation:** `SummarizerAgent` (`summarizer_agent/`) — single Markdown string per ticker from technical + sentiment + fundamentals.
- **Role:** Primary qualitative input for the adapter’s LLM interpret step when enabled.

### Research adapter (`build_research_output`)

- **Formula path:** `use_llm=False` — deterministic mapping from technical (and any filled blocks) to `StockRecommendation` (used for **S&P 500 screening** before deep work).
- **LLM interpret path:** `use_llm=True` — model refines signals/conviction/returns using synthesis and structured inputs.

### S&P 500 screening

- **Implementation:** `select_candidates_by_expected_return` (`backend/universe/screen.py`): sort recommendations by **`expected_return`**, take the top **`pool_mult × (k_long + k_short)`** and the bottom pool of the same size, union (optional **`max_candidates`** cap). Shared with **`run_daily_paper_trade.py`**.
- **Intent:** Capture both **momentum-like** leaders and **weak** names for potential short leg consideration before paying for full sentiment/fundamentals on the whole index.

### Long/short allocation

- **Implementation:** `portfolio_longshort/allocator.py` via **`RiskPortfolioAgent.build_target_weights`**: deterministic ranking with **gross long / gross short** and **per-name caps**; **negative weights** for the short leg.
- **Scoring:** Uses adapter **signal** as direction (BUY → long side, SELL → short side, HOLD → no directional score).

### Trader (two implementations)

1. **ReAct (`run_trader_agent`):** Precomputes four methods in Python (`equal_weight`, `conviction_weight`, `volatility_adjusted_weight`, `kelly_criterion_weight` in `trader_agent/tools.py`); LLM picks one and calls **`generate_trade_orders`**. Those methods allocate **positive** weight only to **BUY** names.
2. **Allocator-aligned (`run_trader_from_allocator_targets`):** Passes signed allocator weights as `{"method": "risk_portfolio_agent", "weights": {…}}` into **`generate_trade_orders`**; **no ReAct**; shorts are **negative** `proposed_weight`. Used by **Top 20** and **S&P 500 screened**.

### `generate_trade_orders`

- **Implementation:** `trader_agent/tools.py` — for each ticker in the chosen weight map: `weight_delta = proposed − current_weight`, action from sign of delta; exposes **`gross_long_pct`** / **`gross_short_pct`** (and `total_invested_pct` as gross long in tool JSON).

### Portfolio validation

- **Implementation:** `portfolio_validator/validator.py` — consumes orders + recommendation metrics; emits **`risk_level`** and warnings. **Optional paper rebalance** skips when `risk_level == HIGH` unless **`paper_force`**.

### Paper execution (local simulator)

- **Implementation:** `paper_execution.py` loads/saves **`PortfolioState`**, pulls closes from technical payload, calls **`rebalance_to_target_weights`** (`paper_simulator/simulator.py`) toward allocator **`target_weights`** (signed). **No broker API** in-repo.

### Paper simulator — end-to-end data flow

Rebalancing, valuation, and PnL for the simulated book are **always computed in Python on the backend** when you run a job (daily paper, optional paper step on Top 20 / S&P 500 screened, or `paper_execution` after an API pipeline). **SQLite does not drive rebalance math**; it stores the **results** of each run for history and charts.

1. **Prices** — The technical phase loads **OHLCV** (e.g. via yfinance inside `TechnicalAnalystAgent`). For the chosen **as-of trade date**, the **close** is read from that payload (same pattern in `paper_execution.extract_close_prices_from_technical` for smaller universes). Those levels value the portfolio and price simulated trades.
2. **Targets** — The risk allocator produces **signed target weights** (long positive, short negative) from recommendations.
3. **Rebalance** — `rebalance_to_target_weights` takes **current `PortfolioState`** (cash + shares), the **price map**, and **targets**, applies instant trades with optional slippage, and **mutates state** (JSON file on disk, e.g. `results/paper_state.json`).
4. **Metrics** — `compute_daily_metrics` yields equity, gross long/short, position count, etc. The daily job records **equity before and after** the rebalance for that date.
5. **Persist** — A **snapshot JSON** may be written under `results/`; **`append_paper_daily_row`** writes one row into **`paper_daily`** (SQLite) with `equity_after`, `daily_return_pct` vs the **previous stored** trading day, trade count, source, and related fields.
6. **UI / API** — `GET /api/paper-history` reads **`paper_daily`** and returns rows used by the **Paper performance** charts and table. **`cumulative_return_pct`** and **`day_pnl_dollars`** (change in `equity_after` vs the prior row) are **derived when serving** from the stored series, so the UI reflects the same equities the simulator wrote.

### Daily paper history (SQLite + UI)

- **Table:** `paper_daily` in SQLite (default file **`results/paper_daily_history.sqlite`**). Override with env **`PAPER_HISTORY_DB`**.
- **Writes:**
  - **`run_daily_paper_trade.py`** — after each successful rebalance, appends one row per `--date` with `source=daily_cli` (manual CLI; you can wrap it in your own scheduler outside the repo if desired).
  - **Top 20 / S&P 500 screened** — when **execute_paper** is true and rebalance runs, appends a row with `as_of_date` = job `as_of_end_date` and `source=api_top20` or `api_sp500`.
- **Columns (conceptual):** `as_of_date`, equity before/after rebalance, **`daily_return_pct`** (vs previous row’s `equity_after`), cash, position count, gross long/short, trade count, source, `created_at`.
- **API:** `GET /api/paper-history?limit=2000` returns chronological rows plus **`cumulative_return_pct`** (vs first row in the returned window).
- **`GET /api/paper-daily-status`** — returns **`today_utc`** (YYYY-MM-DD), **`has_run_today`** (row exists for that date), and optional **`today_row`**.
- **`POST /api/analyze/daily-paper`** — background job calling the same logic as **`run_daily_paper_trade.py`**; history rows use **`source=daily_ui`**. Optional **`skip_if_already_run`** completes immediately if the date is already stored.
- **UI:** **Paper performance** (`/performance`) — shows **whether today (UTC) is already recorded**, **Start daily paper job**, refresh, and charts/table as before.

**Daily automation example** (from repo root, after `cd backend` and activating your venv):

`python run_daily_paper_trade.py --date $(date -u +%F) --no-llm`

(Add `--live-sentiment` / `--live-fundamentals` / `--live-synthesis` if you want full candidate enrichment; each run upserts that calendar date in `paper_daily`.)

You can instead use the **Paper performance** page: **Start daily paper job** (no terminal). **“Today”** is **UTC** to align with `trade_date` defaults.

---

## 1. Custom ticker analysis (`run_analysis.py`, `POST /api/analyze`)

**Entry:** `backend/run_analysis.py` → `run_full_analysis()`.

**Order of stages**

1. **Technical (batch)** — `TechnicalAnalystAgent` loads OHLCV for all requested tickers, computes indicators and rule-based signals, and (if enabled) runs an LLM **per ticker** for narrative summaries (`backend/technical_agent/`).
2. **Per ticker — Sentiment** — `OrchestratorAgent` runs the sentiment LangGraph (`backend/sentiment_agent/`). With `SENTIMENT_FAST_PIPELINE=true` (typical for long jobs), only news + analyst agents run; social, web, and debate are skipped.
3. **Per ticker — Fundamentals** — `fetch_fundamentals_data()` via `backend/fundamentals_agent/tools.py` (yfinance-first snapshot), not the full LangGraph fundamentals agent used elsewhere.
4. **Per ticker — Synthesis** — `SummarizerAgent` calls the shared LLM client to turn technical + sentiment + fundamentals into one Markdown synthesis.
5. **Trader** — `run_trader_for_pipeline()` builds `ResearchTeamOutput` from **all** tickers via `build_research_output()`, then runs the **ReAct trader** (`run_trader_agent` in `backend/trader_agent/agent.py`): four sizing methods are pre-computed in Python; the LLM picks one method and calls `generate_trade_orders` once. See **Trader Agent mechanics** (section 2b) below.
6. **Portfolio validation** — `PortfolioValidator` checks the proposed book.
7. **Persist** — JSON written under `results/`.

**Execution:** this path does **not** place orders. Output is recommendations + JSON only.

**Live UI:** FastAPI installs a **thread-local stream emitter** for the job. Token streams come from explicit `emit_llm_*` calls (technical summaries, sentiment `gemini_client`, synthesis, research adapter interpret, etc.). The trader uses an unwrapped LangChain model for LangGraph compatibility, so its internal steps are **not** mirrored token-by-token to SSE.

---

## 2. Top‑20 long/short (`run_top20_longshort_job.py`, `POST /api/analyze/top20-longshort`)

**Entry:** `backend/run_top20_longshort_job.py` → `run_top20_longshort()`.

**Universe:** `backend/universe/top20.py` → `get_top20_tickers()` (fixed list of large-cap names unless you pass `tickers` explicitly).

**Order of stages**

1. **Technical (batch)** — Same `_run_technical()` as the custom pipeline, for all ~20 names.
2. **Research loop (per ticker)** — For each name: sentiment → fundamentals → progress snapshot for the UI (`research_done` / `research_total`).
3. **Synthesis (per ticker)** — Same `SummarizerAgent` as above.
4. **Research adapter** — `build_research_output(combined, use_llm=…)` produces a `StockRecommendation` per ticker: signal (BUY/SELL/HOLD), conviction, expected return, volatility. Optional **LLM interpretation** streams under SSE as `research_adapter · interpret · {ticker}`.
5. **Risk portfolio allocator** — `RiskPortfolioAgent.build_target_weights()` calls `allocate_long_short()` (`backend/portfolio_longshort/allocator.py`). This is a **deterministic** layer: it ranks names by a risk-adjusted score, takes up to `k_long` long candidates and `k_short` short candidates, and builds weights subject to gross long/short and per-name caps (`RiskPortfolioConfig` in the job).
6. **Trader (subset, allocator-aligned)** — Only tickers with **non-zero** allocator weights (`abs(weight) ≥ 1e-4`) form `booked`. `ResearchTeamOutput` is built with **`subset_recs`** for those names, then **`run_trader_from_allocator_targets(sub, book_weights)`** runs. It calls `generate_trade_orders` once with `weights_json` `{"method": "risk_portfolio_agent", "weights": {…}}` (signed targets: long **positive**, short **negative**), so the **trader orders match the allocator book** (no ReAct “four methods” competition on this path). Per-order rationales are templated from signals and weights.
7. **Validation** — `PortfolioValidator` runs on **synthetic orders** derived from allocator `target_weights` (same book as the trader path above).
8. **Optional paper** — If `execute_paper` is true (API body or job kwargs), after validation **`paper_execution.run_paper_rebalance_optional`** loads/saves `PortfolioState` and calls `rebalance_to_target_weights` with allocator targets and close prices from technical output. Skipped when `risk_report.risk_level == HIGH` unless `paper_force` is true.
9. **Persist** — `results/top20_longshort_<timestamp>.json`.

**Metadata in the JSON:** `target_weights` = allocator output; `trader` = structured orders + rationales; `recommendations_snapshot` = full per-ticker signals before allocation; `paper_execution` = present when optional rebalance ran.

**Execution:** default API behaviour is still **no broker**. Optional **local paper** state is the only in-repo “trade” wiring for this endpoint.

---

## 2b. Trader Agent mechanics (shared concepts)

**Inputs:** `ResearchTeamOutput` — list of `StockRecommendation` (`signal`, `conviction_score`, `expected_return`, `volatility`, `current_weight`). In top‑20 / SP500 screened, the trader often receives only the **booked** subset, not the full universe.

**ReAct path** (`run_trader_agent`, used by custom analysis):

- **Deterministic precompute:** In Python, all four tools (`equal_weight`, `conviction_weight`, `volatility_adjusted_weight`, `kelly_criterion_weight`) produce a `weights` dict each. Those heuristics assign **positive** targets only to **BUY** names; **SELL** / **HOLD** get **0** in those methods.
- **LLM role:** Compare the four JSON blobs, pick one method, call **`generate_trade_orders(weights_json, recommendations_json)`** once with the chosen `weights`.
- **`generate_trade_orders`:** For each ticker in the chosen `weights`, `proposed_weight` is the target, `weight_delta = target - current_weight`, and `action` is BUY / SELL / HOLD from the sign of delta. **`total_invested_pct`** in the tool output is **gross long** (sum of positive targets). **`gross_short_pct`** is the sum of **−min(0, proposed_weight)** (short book as a positive magnitude).

**Allocator-backed path** (`run_trader_from_allocator_targets`, used by top‑20 and SP500 screened):

- Skips ReAct and the four BUY-only methods. **`weights_json`** carries signed **`risk_portfolio_agent`** targets so **shorts are negative** in the same schema as validation.

**Discrepancy note (historical):** Older top‑20 runs used ReAct on the booked subset while validation used allocator targets, so shorts could appear in validation but not in trader sizing. The current job uses the allocator-backed trader so **UI `trade_order` and validation stay consistent** for long/short.

---

## 2c. S&P 500 screened (`run_sp500_screened_job.py`, `POST /api/analyze/sp500-screened`)

**Universe:** `get_sp500_tickers()` (`backend/universe/sp500.py`).

**Stages**

1. **Technical (wide)** — Full list (~500). **`enable_llm_summary_technical`** defaults to **false** in the API to limit cost; set true only if you want per-ticker technical LLM narratives on the whole index.
2. **Screen** — Tradable names (positive close from technical payload) get a **technical-only** combined blob; `build_research_output(..., use_llm=False)`; **`select_candidates_by_expected_return`** (`backend/universe/screen.py`) returns the union of top and bottom pools: `pool_mult × (k_long + k_short)` from each tail, optionally capped by **`max_candidates`** (default 30).
3. **Deep research** — Sentiment, fundamentals, synthesis on **candidates only** (flags: `deep_sentiment`, `deep_fundamentals`, `deep_synthesis`).
4. **Adapter → allocator → allocator-backed trader → validation → optional paper → persist** — Same pattern as top‑20; output file `results/sp500_screened_<timestamp>.json`.

**Progress:** `metadata.pipeline_step` moves through `technical_wide`, `screen`, `research`, `synthesis`, `risk_portfolio`, `trader`, `validation`, `paper` (if enabled).

**Execution:** Same as top‑20 — JSON by default; optional **`execute_paper`** updates local simulator state via `backend/paper_execution.py`. There is **no live broker** in this repo.

---

## 3. Why you might see only one stock sized (e.g. JNJ at 40%, rest cash)

Several mechanisms stack together.

### 3.1 Allocator: HOLD names drop out of long and short legs

In `portfolio_longshort/allocator.py`, `_score()` uses the signal as a direction:

- **BUY** → positive direction → can enter the **long** leg if the combined score is **> 0**.
- **SELL** → negative direction → can enter the **short** leg if the score is **< 0**.
- **HOLD** → direction multiplier **0** → score is **0** → the name is **not** placed in the long list (`s > 0`) **or** the short list (`s < 0`).

So in a batch where the adapter marks **most** names **HOLD** (very common when synthesis says “Hold with caution”), **only names with clear BUY or SELL scores** remain in the allocator book. In your logs, **BRK-B** was **SELL** and **JNJ** was **BUY**; the rest were mostly **HOLD**, so they never received allocator weights.

### 3.2 Custom analysis ReAct trader: BUY-only sizing tools

On **`POST /api/analyze`** / `run_full_analysis`, the trader still uses **ReAct** and the four methods that only give **positive** weight to **BUY** names. If the booked mental model is “all names,” only **BUY**s get sized there.

**Top‑20 and S&P 500 screened** no longer use that path for the book: they use **`run_trader_from_allocator_targets`**, so **shorts** appear as **negative** `proposed_weight` in `trader.orders` when the allocator assigns them.

### 3.3 Allocator still drops most names if signals are HOLD

Top‑20 / screened jobs only **trade** (allocator + trader + validation) the names the allocator weights. **HOLD** names tend to score **0** in `portfolio_longshort/allocator.py` and fall out of the long/short legs, so a “only one or two names in the book” outcome is still common when the adapter is cautious.

---

## 4. Why the UI shows “N/A” for sizing method on most tickers

Per-ticker rows read `results[ticker].trade_order.sizing_method_used` (`frontend/src/components/TickerCard.jsx`, `ResultsDashboard.jsx`).

The backend only attaches `trade_order` when merging **trader `orders`**:

```python
for order in trader_dict.get("orders", []):
    if t in combined["results"]:
        combined["results"][t]["trade_order"] = { ... }
```

Tickers **without** an entry in `trader["orders"]` never get `trade_order`, so the UI falls back to **“N/A”**. That does **not** mean the stock was ignored by the whole pipeline; it usually means it was **not** in the trader’s order list (e.g. **0% target** from sizing tools, or **not** in `subset_recs`).

---

## 5. Related files (quick map)

| Concern | Location |
|--------|----------|
| Custom orchestration | `backend/run_analysis.py` |
| Top‑20 job | `backend/run_top20_longshort_job.py` |
| S&P 500 screened job | `backend/run_sp500_screened_job.py` |
| Universe screen | `backend/universe/screen.py` |
| Daily paper CLI | `backend/run_daily_paper_trade.py` |
| Optional API paper rebalance | `backend/paper_execution.py` |
| Daily paper SQLite history | `backend/portfolio_history/store.py`, `GET /api/paper-history` |
| Paper simulator | `backend/paper_simulator/simulator.py` |
| Adapter → `StockRecommendation` | `backend/trader_agent/adapter.py` |
| Long/short allocator | `backend/portfolio_longshort/allocator.py` |
| Risk wrapper | `backend/risk_portfolio_agent/agent.py` |
| Trader ReAct + allocator path + tools | `backend/trader_agent/agent.py`, `tools.py` |
| API + SSE queues | `backend/main.py` |
| Stream events | `backend/streaming_context.py` |

---

## 6. Environment knobs that affect behaviour

- **`SENTIMENT_FAST_PIPELINE`** — Fewer sentiment LLM calls per ticker (see `backend/sentiment_agent/config/settings.py`).
- **`LLM_PROVIDER` / API keys** — Resolved in `backend/llm_provider/resolver.py` (Mistral, Groq, Ollama, etc.).
- **Top‑20 POST body** — `k_long`, `k_short`, `gross_long`, `gross_short`, `max_single_long`, `max_single_short`, `use_llm_interpret`, plus optional **`execute_paper`**, **`paper_state_file`**, **`paper_force`**.
- **S&P 500 screened POST body** — `enable_llm_summary_technical` (default false), `candidate_pool_mult`, `max_candidates`, `limit_universe` (debug), same allocator fields as top‑20, optional paper flags as above.

For Mistral throttling on wrapped LangChain paths, see `MISTRAL_THROTTLE`, `MISTRAL_MIN_INTERVAL_SEC`, `MISTRAL_MAX_PER_MINUTE` (trader path uses an unthrottled model for LangGraph compatibility).
