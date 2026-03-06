"""
FastAPI backend for the Trading-Agent multi-agent stock analysis system.

Endpoints:
    POST /api/analyze           — launch a full analysis (background)
    GET  /api/status/{job_id}   — poll job progress
    GET  /api/results           — list past result JSON files
    GET  /api/results/{filename}— load a specific past result
    GET  /api/health            — health check
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Background job store (in-memory)
# ---------------------------------------------------------------------------
_jobs: Dict[str, Dict[str, Any]] = {}
_executor = ThreadPoolExecutor(max_workers=2)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, description="List of ticker symbols")
    start_date: str | None = None
    end_date: str | None = None
    interval: str = "1d"


class JobResponse(BaseModel):
    job_id: str
    status: str


class StatusResponse(BaseModel):
    job_id: str
    status: str  # "running" | "completed" | "failed"
    result: Dict[str, Any] | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ResultMeta(BaseModel):
    filename: str
    tickers: list[str]
    generated_at: str


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_analysis_job(job_id: str, tickers: list[str],
                      start_date: str | None, end_date: str | None,
                      interval: str) -> None:
    """Runs the full analysis pipeline in a thread."""
    # Import here to avoid circular imports and keep startup fast
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from run_analysis import run_full_analysis
    from technical_agent.shared.serialization import to_serializable

    try:
        logger.info(f"[job {job_id}] Starting analysis for {tickers}")
        result = run_full_analysis(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        # Ensure everything is JSON-serializable
        serializable = json.loads(json.dumps(result, default=to_serializable))

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = serializable
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[job {job_id}] Analysis completed successfully")

    except Exception as exc:
        logger.error(f"[job {job_id}] Analysis failed: {exc}", exc_info=True)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


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
        "error": None,
        "tickers": tickers,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    _executor.submit(
        _run_analysis_job, job_id, tickers,
        req.start_date, req.end_date, req.interval,
    )

    logger.info(f"[api] Started job {job_id} for {tickers}")
    return JobResponse(job_id=job_id, status="running")


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
