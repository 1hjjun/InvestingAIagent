from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from web_service.backend.rebalance_agent.agent import run_agent
from web_service.backend.rebalance_agent.logger import TRACE_DIR
from web_service.backend.rebalance_agent.schema import AgentInput
from src.portfolio_analytics import calculate_portfolio_analytics
from src.profile_store import load_portfolio, load_profile


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class RunRequest(BaseModel):
    user_query: str = Field(..., min_length=1)
    image_url: str | None = None
    youtube_url: str | None = None


class RunResponse(BaseModel):
    trace_id: str
    answer_text: str
    chart_data: dict[str, Any] | None = None
    is_saved: bool = False
    stop_reason: str | None = None


app = FastAPI(title="ETF Rebalancing Agent API", version="0.8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _trace_files() -> list[Path]:
    if not TRACE_DIR.exists():
        return []
    return sorted(TRACE_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def _read_trace(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _compose_query_text(user_query: str, youtube_url: str | None) -> str:
    query = user_query.strip()
    if youtube_url:
        query = f"{query}\nYouTube URL: {youtube_url.strip()}"
    return query


def _compose_query(payload: RunRequest) -> str:
    return _compose_query_text(payload.user_query, payload.youtube_url)


def _agent_context() -> tuple[dict[str, Any], dict[str, Any]]:
    profile = load_profile()
    portfolio = dict(load_portfolio())
    portfolio["analytics"] = calculate_portfolio_analytics(portfolio)
    return profile, portfolio


def _run_response(result: Any) -> RunResponse:
    return RunResponse(
        trace_id=result.trace_id or "",
        answer_text=result.answer_text,
        chart_data=result.chart_data,
        is_saved=result.is_saved,
        stop_reason=result.stop_reason,
    )


async def _save_upload(image: UploadFile | None) -> str | None:
    if image is None:
        return None

    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_SUFFIXES))
        raise HTTPException(status_code=400, detail=f"Unsupported image extension. Allowed: {allowed}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"

    try:
        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    finally:
        await image.close()

    return str(saved_path)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.post("/api/runs", response_model=RunResponse)
async def create_run(payload: RunRequest) -> RunResponse:
    profile_context, portfolio_context = _agent_context()
    result = await run_agent(
        AgentInput(
            user_query=_compose_query(payload),
            image_url=payload.image_url,
            profile_context=profile_context,
            portfolio_context=portfolio_context,
        )
    )
    return _run_response(result)


@app.post("/api/runs/upload", response_model=RunResponse)
async def create_run_upload(
    user_query: str = Form(..., min_length=1),
    youtube_url: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
) -> RunResponse:
    image_path = await _save_upload(image)
    profile_context, portfolio_context = _agent_context()
    result = await run_agent(
        AgentInput(
            user_query=_compose_query_text(user_query, youtube_url),
            image_url=image_path,
            profile_context=profile_context,
            portfolio_context=portfolio_context,
        )
    )
    return _run_response(result)


@app.get("/api/runs")
def list_runs() -> dict[str, Any]:
    runs = []
    for path in _trace_files():
        try:
            trace = _read_trace(path)
        except json.JSONDecodeError:
            continue
        runs.append(
            {
                "trace_id": trace.get("trace_id", path.stem),
                "started_at": trace.get("started_at"),
                "ended_at": trace.get("ended_at"),
                "stop_reason": trace.get("stop_reason"),
                "metrics": trace.get("metrics", {}),
                "request": trace.get("request", {}),
            }
        )
    return {"runs": runs}


@app.get("/api/runs/{trace_id}")
def get_run(trace_id: str) -> dict[str, Any]:
    path = TRACE_DIR / f"{trace_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Trace not found")
    return _read_trace(path)
