"""
FastAPI backend for the Trading-Agent multi-agent stock analysis system.

Endpoints:
    POST /api/analyze              — launch a full analysis (background)
    POST /api/analyze/top20-longshort — top-20 long/short pilot (background)
    POST /api/analyze/sp500-screened — S&P 500 screen then deep research (background)
    POST /api/analyze/daily-paper      — S&P 500 daily paper rebalance (background)
    GET  /api/paper-daily-status      — whether today's UTC row exists in paper_daily
    GET  /api/stream/{job_id}   — SSE: LLM token chunks + stage markers + job_done
    GET  /api/status/{job_id}   — poll job progress
    GET  /api/results           — list past result JSON files
    GET  /api/results/{filename}— load a specific past result
    GET  /api/paper-history     — daily simulated paper portfolio time series (SQLite)
    GET  /api/health            — health check
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from streaming_context import reset_stream_emitter, set_stream_emitter

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backend")

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="Trading-Agent API", version="1.0.0")

import os as _os
_extra_origins = [o.strip() for o in _os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        *_extra_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Background job store (in-memory)
# ---------------------------------------------------------------------------
_jobs: Dict[str, Dict[str, Any]] = {}
_stream_queues: Dict[str, "queue.Queue[Dict[str, Any] | None]"] = {}
_executor = ThreadPoolExecutor(max_workers=2)

_STREAM_QUEUE_MAX = 50_000


def _stream_put(job_id: str, item: Dict[str, Any] | None) -> None:
    q = _stream_queues.get(job_id)
    if q is None:
        return
    try:
        q.put_nowait(item)
    except queue.Full:
        logger.warning(f"[stream {job_id}] queue full; dropping event")


def _blocking_stream_get(q: "queue.Queue", timeout: float) -> Dict[str, Any] | None | str:
    """Return item, or 'empty' on timeout."""
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return "empty"

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, description="List of ticker symbols")
    start_date: str | None = None
    end_date: str | None = None
    interval: str = "1d"


class Top20LongShortRequest(BaseModel):
    """Top-20 curated universe: research → allocator → trader on the book → validation."""

    end_date: str | None = Field(None, description="As-of end date YYYY-MM-DD (default: UTC today)")
    start_date: str | None = Field(None, description="OHLCV window start; derived from lookback if omitted")
    lookback_days: int = Field(365, ge=30, le=3650)
    interval: str = "1d"
    use_llm_interpret: bool = True
    k_long: int = Field(10, ge=1, le=20)
    k_short: int = Field(10, ge=1, le=20)
    gross_long: float = Field(1.0, gt=0)
    gross_short: float = Field(0.5, ge=0)
    max_single_long: float = Field(0.05, gt=0)
    max_single_short: float = Field(0.03, gt=0)
    execute_paper: bool = Field(False, description="After validation, rebalance local paper portfolio state")
    paper_state_file: str | None = Field(None, description="JSON path for PortfolioState (default: results/paper_state.json)")
    paper_initial_cash: float = Field(100_000.0, gt=0)
    paper_force: bool = Field(False, description="Rebalance even when validator risk_level is HIGH")


class Sp500ScreenedRequest(BaseModel):
    """S&P 500: technicals on full list → formula screen → full research on candidates."""

    end_date: str | None = Field(None, description="As-of end date YYYY-MM-DD (default: UTC today)")
    start_date: str | None = Field(None, description="OHLCV window start; derived from lookback if omitted")
    lookback_days: int = Field(365, ge=30, le=3650)
    interval: str = "1d"
    enable_llm_summary_technical: bool = Field(
        False,
        description="Per-ticker technical LLM summaries on ~500 names (expensive; default off)",
    )
    candidate_pool_mult: int = Field(3, ge=1, le=10)
    max_candidates: int | None = Field(30, ge=1, le=200)
    k_long: int = Field(10, ge=1, le=50)
    k_short: int = Field(10, ge=1, le=50)
    gross_long: float = Field(1.0, gt=0)
    gross_short: float = Field(0.5, ge=0)
    max_single_long: float = Field(0.05, gt=0)
    max_single_short: float = Field(0.03, gt=0)
    use_llm_interpret: bool = True
    deep_sentiment: bool = True
    deep_fundamentals: bool = True
    deep_synthesis: bool = True
    limit_universe: int = Field(0, ge=0, le=503, description="Debug: only first N S&P tickers")
    execute_paper: bool = False
    paper_state_file: str | None = None
    paper_initial_cash: float = Field(100_000.0, gt=0)
    paper_force: bool = False


class DailyPaperRequest(BaseModel):
    """CLI-equivalent daily S&P 500 paper run (see ``run_daily_paper_trade.py``)."""

    trade_date: str | None = Field(None, description="YYYY-MM-DD; default UTC today")
    skip_if_already_run: bool = Field(
        False,
        description="If true, complete immediately when paper_daily already has trade_date",
    )
    no_llm: bool = Field(True, description="Formula adapter + no per-ticker technical LLM (cheaper default)")
    live_sentiment: bool = False
    live_fundamentals: bool = False
    live_synthesis: bool = False
    k_long: int = Field(25, ge=1, le=100)
    k_short: int = Field(25, ge=1, le=100)
    gross_long: float = Field(1.0, gt=0)
    gross_short: float = Field(0.5, ge=0)
    max_single_long: float = Field(0.05, gt=0)
    max_single_short: float = Field(0.03, gt=0)
    lookback_days: int = Field(365, ge=30, le=3650)
    initial_cash: float = Field(100_000.0, gt=0)
    candidate_pool_mult: int = Field(3, ge=1, le=10)
    limit_universe: int = Field(0, ge=0, le=503)
    state_file: str | None = Field(
        None,
        description="Portfolio state JSON path; default results/paper_state.json under project root",
    )


class JobResponse(BaseModel):
    job_id: str
    status: str


class StatusResponse(BaseModel):
    job_id: str
    status: str  # "running" | "completed" | "failed"
    result: Dict[str, Any] | None = None
    """Latest pipeline snapshot while status is ``running`` (technical → … → validation)."""
    partial_result: Dict[str, Any] | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ResultMeta(BaseModel):
    filename: str
    tickers: list[str]
    generated_at: str


class PaperHistoryResponse(BaseModel):
    rows: list[dict[str, Any]]
    count: int
    database: str


class PaperDailyStatusResponse(BaseModel):
    today_utc: str
    has_run_today: bool
    today_row: dict[str, Any] | None = None
    database: str


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_analysis_job(job_id: str, tickers: list[str],
                      start_date: str | None, end_date: str | None,
                      interval: str) -> None:
    """Runs the full analysis pipeline in a thread."""
    # Add backend/ dir to sys.path so agent modules resolve
    import sys as _sys
    if _BACKEND_DIR not in _sys.path:
        _sys.path.insert(0, _BACKEND_DIR)
    from run_analysis import run_full_analysis
    from technical_agent.shared.serialization import to_serializable

    def _on_progress(snapshot: Dict[str, Any]) -> None:
        _jobs[job_id]["partial_result"] = snapshot

    stream_q = _stream_queues.get(job_id)
    emit_token = None
    job_ctx_token = None
    if stream_q is not None:
        emit_token, job_ctx_token = set_stream_emitter(
            lambda ev: _stream_put(job_id, ev),
            job_id=job_id,
        )

    try:
        logger.info(f"[job {job_id}] Starting analysis for {tickers}")
        result = run_full_analysis(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            progress_callback=_on_progress,
        )

        # Ensure everything is JSON-serializable
        serializable = json.loads(json.dumps(result, default=to_serializable))

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = serializable
        _jobs[job_id]["partial_result"] = None
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[job {job_id}] Analysis completed successfully")

    except Exception as exc:
        logger.error(f"[job {job_id}] Analysis failed: {exc}", exc_info=True)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        if emit_token is not None:
            reset_stream_emitter(emit_token, job_ctx_token)
        _stream_put(
            job_id,
            {
                "type": "job_done",
                "status": _jobs[job_id].get("status", "unknown"),
                "error": _jobs[job_id].get("error"),
            },
        )


def _run_top20_longshort_job(job_id: str, req: Top20LongShortRequest) -> None:
    import sys as _sys
    if _BACKEND_DIR not in _sys.path:
        _sys.path.insert(0, _BACKEND_DIR)
    from run_top20_longshort_job import run_top20_longshort
    from technical_agent.shared.serialization import to_serializable

    def _on_progress(snapshot: Dict[str, Any]) -> None:
        _jobs[job_id]["partial_result"] = snapshot

    stream_q = _stream_queues.get(job_id)
    emit_token = None
    job_ctx_token = None
    if stream_q is not None:
        emit_token, job_ctx_token = set_stream_emitter(
            lambda ev: _stream_put(job_id, ev),
            job_id=job_id,
        )

    try:
        logger.info(f"[job {job_id}] Starting top-20 long/short run")
        result = run_top20_longshort(
            end_date=req.end_date,
            start_date=req.start_date,
            lookback_days=req.lookback_days,
            interval=req.interval,
            use_llm_interpret=req.use_llm_interpret,
            k_long=req.k_long,
            k_short=req.k_short,
            gross_long=req.gross_long,
            gross_short=req.gross_short,
            max_single_long=req.max_single_long,
            max_single_short=req.max_single_short,
            progress_callback=_on_progress,
            execute_paper=req.execute_paper,
            paper_state_file=req.paper_state_file,
            paper_initial_cash=req.paper_initial_cash,
            paper_force=req.paper_force,
        )
        serializable = json.loads(json.dumps(result, default=to_serializable))
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = serializable
        _jobs[job_id]["partial_result"] = None
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[job {job_id}] Top-20 long/short completed")
    except Exception as exc:
        logger.error(f"[job {job_id}] Top-20 long/short failed: {exc}", exc_info=True)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        if emit_token is not None:
            reset_stream_emitter(emit_token, job_ctx_token)
        _stream_put(
            job_id,
            {
                "type": "job_done",
                "status": _jobs[job_id].get("status", "unknown"),
                "error": _jobs[job_id].get("error"),
            },
        )


def _run_sp500_screened_job(job_id: str, req: Sp500ScreenedRequest) -> None:
    import sys as _sys
    if _BACKEND_DIR not in _sys.path:
        _sys.path.insert(0, _BACKEND_DIR)
    from run_sp500_screened_job import run_sp500_screened
    from technical_agent.shared.serialization import to_serializable

    def _on_progress(snapshot: Dict[str, Any]) -> None:
        _jobs[job_id]["partial_result"] = snapshot

    stream_q = _stream_queues.get(job_id)
    emit_token = None
    job_ctx_token = None
    if stream_q is not None:
        emit_token, job_ctx_token = set_stream_emitter(
            lambda ev: _stream_put(job_id, ev),
            job_id=job_id,
        )

    try:
        logger.info(f"[job {job_id}] Starting S&P 500 screened run")
        result = run_sp500_screened(
            end_date=req.end_date,
            start_date=req.start_date,
            lookback_days=req.lookback_days,
            interval=req.interval,
            enable_llm_summary_technical=req.enable_llm_summary_technical,
            candidate_pool_mult=req.candidate_pool_mult,
            max_candidates=req.max_candidates,
            k_long=req.k_long,
            k_short=req.k_short,
            gross_long=req.gross_long,
            gross_short=req.gross_short,
            max_single_long=req.max_single_long,
            max_single_short=req.max_single_short,
            use_llm_interpret=req.use_llm_interpret,
            deep_sentiment=req.deep_sentiment,
            deep_fundamentals=req.deep_fundamentals,
            deep_synthesis=req.deep_synthesis,
            limit_universe=req.limit_universe,
            progress_callback=_on_progress,
            execute_paper=req.execute_paper,
            paper_state_file=req.paper_state_file,
            paper_initial_cash=req.paper_initial_cash,
            paper_force=req.paper_force,
        )
        serializable = json.loads(json.dumps(result, default=to_serializable))
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = serializable
        _jobs[job_id]["partial_result"] = None
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[job {job_id}] S&P 500 screened completed")
    except Exception as exc:
        logger.error(f"[job {job_id}] S&P 500 screened failed: {exc}", exc_info=True)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        if emit_token is not None:
            reset_stream_emitter(emit_token, job_ctx_token)
        _stream_put(
            job_id,
            {
                "type": "job_done",
                "status": _jobs[job_id].get("status", "unknown"),
                "error": _jobs[job_id].get("error"),
            },
        )


def _run_daily_paper_job(job_id: str, req: DailyPaperRequest) -> None:
    import sys as _sys

    if _BACKEND_DIR not in _sys.path:
        _sys.path.insert(0, _BACKEND_DIR)
    from portfolio_history import get_row_for_date
    from run_daily_paper_trade import run_daily_paper_trade_job
    from technical_agent.shared.serialization import to_serializable

    def _on_progress(snapshot: Dict[str, Any]) -> None:
        _jobs[job_id]["partial_result"] = snapshot

    stream_q = _stream_queues.get(job_id)
    emit_token = None
    job_ctx_token = None
    if stream_q is not None:
        emit_token, job_ctx_token = set_stream_emitter(
            lambda ev: _stream_put(job_id, ev),
            job_id=job_id,
        )

    try:
        trade_date = (req.trade_date or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if req.skip_if_already_run:
            existing = get_row_for_date(trade_date)
            if existing is not None:
                skip_result = {
                    "skipped": True,
                    "reason": "already_recorded_for_date",
                    "trade_date": trade_date,
                    "existing_row": existing,
                }
                serializable = json.loads(json.dumps(skip_result, default=to_serializable))
                _jobs[job_id]["status"] = "completed"
                _jobs[job_id]["result"] = serializable
                _jobs[job_id]["partial_result"] = None
                _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                logger.info("[job %s] Daily paper skipped (row exists for %s)", job_id, trade_date)
                return

        state_rel = req.state_file or "results/paper_state.json"
        logger.info("[job %s] Starting daily paper run for %s", job_id, trade_date)
        result = run_daily_paper_trade_job(
            trade_date=trade_date,
            k_long=req.k_long,
            k_short=req.k_short,
            gross_long=req.gross_long,
            gross_short=req.gross_short,
            max_single_long=req.max_single_long,
            max_single_short=req.max_single_short,
            lookback_days=req.lookback_days,
            initial_cash=req.initial_cash,
            state_file=state_rel,
            no_llm=req.no_llm,
            live_sentiment=req.live_sentiment,
            live_fundamentals=req.live_fundamentals,
            live_synthesis=req.live_synthesis,
            candidate_pool_mult=req.candidate_pool_mult,
            limit_universe=req.limit_universe,
            history_source="daily_ui",
            progress_callback=_on_progress,
        )
        serializable = json.loads(json.dumps(result, default=to_serializable))
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = serializable
        _jobs[job_id]["partial_result"] = None
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("[job %s] Daily paper completed", job_id)
    except Exception as exc:
        logger.error("[job %s] Daily paper failed: %s", job_id, exc, exc_info=True)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        if emit_token is not None:
            reset_stream_emitter(emit_token, job_ctx_token)
        _stream_put(
            job_id,
            {
                "type": "job_done",
                "status": _jobs[job_id].get("status", "unknown"),
                "error": _jobs[job_id].get("error"),
            },
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/paper-history", response_model=PaperHistoryResponse)
def get_paper_history(limit: int = 2000):
    """
    Chronological daily rows from the simulated paper portfolio (``paper_daily`` table).

    Populated by ``run_daily_paper_trade.py`` and by API jobs when **execute_paper** is true.
    Set **PAPER_HISTORY_DB** to override the default ``results/paper_daily_history.sqlite`` path.
    """
    from portfolio_history import get_database_path, list_paper_daily_rows

    cap = max(1, min(int(limit), 50_000))
    rows = list_paper_daily_rows(limit=cap)
    return PaperHistoryResponse(
        rows=rows,
        count=len(rows),
        database=str(get_database_path().resolve()),
    )


@app.get("/api/paper-daily-status", response_model=PaperDailyStatusResponse)
def get_paper_daily_status():
    """Whether ``paper_daily`` already has a row for today's UTC calendar date."""
    from portfolio_history import get_database_path, get_row_for_date

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = get_row_for_date(today)
    return PaperDailyStatusResponse(
        today_utc=today,
        has_run_today=row is not None,
        today_row=row,
        database=str(get_database_path().resolve()),
    )


@app.post("/api/analyze", response_model=JobResponse)
def start_analysis(req: AnalyzeRequest):
    """Launch analysis in the background, return a job ID to poll."""
    tickers = [t.strip().upper() for t in req.tickers if t.strip()]
    if not tickers:
        raise HTTPException(status_code=400, detail="No valid tickers provided")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running",
        "result": None,
        "partial_result": None,
        "error": None,
        "tickers": tickers,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    _stream_queues[job_id] = queue.Queue(maxsize=_STREAM_QUEUE_MAX)

    _executor.submit(
        _run_analysis_job, job_id, tickers,
        req.start_date, req.end_date, req.interval,
    )

    logger.info(f"[api] Started job {job_id} for {tickers}")
    return JobResponse(job_id=job_id, status="running")


@app.post("/api/analyze/top20-longshort", response_model=JobResponse)
def start_top20_longshort(req: Top20LongShortRequest):
    """Launch top-20 long/short pilot (fixed universe) in the background."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running",
        "result": None,
        "partial_result": None,
        "error": None,
        "tickers": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "job_kind": "top20_longshort",
    }
    _stream_queues[job_id] = queue.Queue(maxsize=_STREAM_QUEUE_MAX)
    _executor.submit(_run_top20_longshort_job, job_id, req)
    logger.info(f"[api] Started top-20 long/short job {job_id}")
    return JobResponse(job_id=job_id, status="running")


@app.post("/api/analyze/sp500-screened", response_model=JobResponse)
def start_sp500_screened(req: Sp500ScreenedRequest):
    """Launch S&P 500 screened pipeline (wide technicals → screen → deep dive) in the background."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running",
        "result": None,
        "partial_result": None,
        "error": None,
        "tickers": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "job_kind": "sp500_screened",
    }
    _stream_queues[job_id] = queue.Queue(maxsize=_STREAM_QUEUE_MAX)
    _executor.submit(_run_sp500_screened_job, job_id, req)
    logger.info(f"[api] Started S&P 500 screened job {job_id}")
    return JobResponse(job_id=job_id, status="running")


@app.post("/api/analyze/daily-paper", response_model=JobResponse)
def start_daily_paper(req: DailyPaperRequest):
    """Background run: same flow as ``run_daily_paper_trade.py`` (S&P 500 → screen → rebalance → history)."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running",
        "result": None,
        "partial_result": None,
        "error": None,
        "tickers": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "job_kind": "daily_paper",
    }
    _stream_queues[job_id] = queue.Queue(maxsize=_STREAM_QUEUE_MAX)
    _executor.submit(_run_daily_paper_job, job_id, req)
    logger.info("[api] Started daily paper job %s", job_id)
    return JobResponse(job_id=job_id, status="running")


@app.get("/api/stream/{job_id}")
async def stream_job_events(job_id: str) -> StreamingResponse:
    """
    Server-Sent Events of LLM chunks and stage markers for a running (or recent) job.
    Connect immediately after POST /api/analyze with the returned job_id.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    q = _stream_queues.get(job_id)
    if q is None:
        raise HTTPException(status_code=404, detail="No stream for this job")

    logger.info(f"[api] SSE client subscribed job_id={job_id}")

    async def event_gen() -> AsyncIterator[str]:
        while True:
            item = await asyncio.to_thread(_blocking_stream_get, q, 25.0)
            if item == "empty":
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(item)}\n\n"
            if isinstance(item, dict) and item.get("type") == "job_done":
                break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str):
    """Poll job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        result=job["result"],
        partial_result=job.get("partial_result")
        if job["status"] in ("running", "failed")
        else None,
        error=job["error"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
    )


@app.get("/api/results", response_model=list[ResultMeta])
def list_results():
    """List all saved result JSON files."""
    if not RESULTS_DIR.exists():
        return []

    entries = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            meta = data.get("metadata", {})
            entries.append(ResultMeta(
                filename=f.name,
                tickers=meta.get("tickers", []),
                generated_at=meta.get("generated_at", ""),
            ))
        except Exception:
            continue

    return entries


@app.get("/api/results/{filename}")
def get_result(filename: str):
    """Load a specific past result file."""
    filepath = RESULTS_DIR / filename
    if not filepath.exists() or not filepath.suffix == ".json":
        raise HTTPException(status_code=404, detail="Result file not found")

    # Prevent path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    with open(filepath, "r", encoding="utf-8") as fh:
        return json.load(fh)
# test
