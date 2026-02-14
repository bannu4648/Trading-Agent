"""FastAPI server to chat with the technical analyst agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import TechnicalAnalystAgent

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"

app = FastAPI(title="Technical Analyst Agent")
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

_agent = TechnicalAnalystAgent()


class ChatRequest(BaseModel):
    message: str = Field("", description="Freeform user prompt")
    tickers: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    interval: Optional[str] = None


def _parse_from_message(message: str) -> dict:
    message = (message or "").strip()
    if not message:
        return {}

    if message.startswith("{"):
        try:
            payload = json.loads(message)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", message)
    interval_match = re.search(r"\b\d+(?:m|h|d)\b", message, flags=re.IGNORECASE)
    interval = interval_match.group(0).lower() if interval_match else None

    ticker_candidates = re.findall(r"\b[A-Z][A-Z0-9\.\-]{0,6}\b", message)
    tickers = [t for t in ticker_candidates if len(t) >= 1]

    return {
        "tickers": tickers,
        "start_date": dates[0] if len(dates) > 0 else None,
        "end_date": dates[1] if len(dates) > 1 else None,
        "interval": interval,
    }


def _merge_request(chat: ChatRequest) -> dict:
    parsed = _parse_from_message(chat.message)
    tickers = chat.tickers or parsed.get("tickers") or []
    start_date = chat.start_date or parsed.get("start_date")
    end_date = chat.end_date or parsed.get("end_date")
    interval = chat.interval or parsed.get("interval") or "1d"
    return {
        "tickers": tickers,
        "start_date": start_date,
        "end_date": end_date,
        "interval": interval,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/api/schema")
def schema() -> FileResponse:
    return FileResponse(BASE_DIR / "schema" / "technical_handoff.schema.json")


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    request = _merge_request(req)
    if not request["tickers"]:
        raise HTTPException(status_code=400, detail="At least one ticker is required.")

    result = _agent.run(
        tickers=request["tickers"],
        start_date=request["start_date"],
        end_date=request["end_date"],
        interval=request["interval"],
    )

    summaries = []
    for symbol, payload in result.get("tickers", {}).items():
        summary = payload.get("summary", "")
        summaries.append(f"{symbol}: {summary}")

    return {
        "assistant_message": "\n".join(summaries).strip(),
        "request": request,
        "payload": result,
    }
