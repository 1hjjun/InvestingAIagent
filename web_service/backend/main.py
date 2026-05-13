from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from investment_assistant import answer_question
from src.conversation_store import add_message, clear_messages, list_messages
from src.memory_store import load_daily_journals, load_memory
from src.portfolio_analytics import calculate_portfolio_analytics
from src.profile_store import load_portfolio, load_profile, save_portfolio, save_profile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_BACKEND_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = WEB_BACKEND_DIR / "uploads"
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(WEB_BACKEND_DIR / ".env")

from web_service.backend.rebalance_agent.agent import run_agent
from web_service.backend.rebalance_agent.logger import TRACE_DIR
from web_service.backend.rebalance_agent.schema import AgentInput


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=3, ge=1, le=5)
    use_vision: bool = False
    max_images: int = Field(default=2, ge=1, le=5)
    answer_style: str = "해석/코칭 모드"
    pdf_only: bool = False
    include_portfolio: bool = True
    conservative_view: bool = False
    conversation_history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    chunks: list[dict[str, Any]]
    image_review: str = ""
    memory: dict[str, Any] | None = None


class SaveProfileRequest(BaseModel):
    profile: dict[str, Any]


class SavePortfolioRequest(BaseModel):
    portfolio: dict[str, Any]


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


app = FastAPI(title="Mind Investing AI Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.get("/api/conversations/rebalance-agent/messages")
def get_rebalance_messages() -> dict[str, Any]:
    return {"messages": list_messages()}


@app.delete("/api/conversations/rebalance-agent/messages")
def delete_rebalance_messages() -> dict[str, bool]:
    clear_messages()
    return {"ok": True}


def _trace_files() -> list[Path]:
    if not TRACE_DIR.exists():
        return []
    return sorted(TRACE_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def _read_trace(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


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
    saved_path = UPLOAD_DIR / f"{uuid4().hex}{suffix}"

    try:
        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    finally:
        await image.close()

    return str(saved_path)


@app.post("/api/runs", response_model=RunResponse)
async def create_agent_run(payload: RunRequest) -> RunResponse:
    profile_context, portfolio_context = _agent_context()
    add_message("user", _compose_query(payload))
    result = await run_agent(
        AgentInput(
            user_query=_compose_query(payload),
            image_url=payload.image_url,
            profile_context=profile_context,
            portfolio_context=portfolio_context,
        )
    )
    add_message("assistant", result.answer_text, trace_id=result.trace_id)
    return _run_response(result)


@app.post("/api/runs/upload")
async def create_agent_run_upload(
    user_query: str = Form(..., min_length=1),
    youtube_url: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
) -> RunResponse:
    image_path = await _save_upload(image)
    query = _compose_query_text(user_query, youtube_url)
    add_message(
        "user",
        query,
        image_name=image.filename if image else None,
        image_path=image_path,
    )
    profile_context, portfolio_context = _agent_context()
    result = await run_agent(
        AgentInput(
            user_query=query,
            image_url=image_path,
            profile_context=profile_context,
            portfolio_context=portfolio_context,
        )
    )
    add_message("assistant", result.answer_text, trace_id=result.trace_id)
    return _run_response(result)


@app.get("/api/runs")
def list_agent_runs() -> dict[str, Any]:
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
def get_agent_run(trace_id: str) -> dict[str, Any]:
    path = TRACE_DIR / f"{trace_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Trace not found")
    return _read_trace(path)


@app.post("/api/pdf-chat", response_model=ChatResponse)
def pdf_chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = answer_question(
            payload.question,
            top_k=payload.top_k,
            use_vision=payload.use_vision,
            max_images=payload.max_images,
            conversation_history=payload.conversation_history,
            answer_style=payload.answer_style,
            pdf_only=payload.pdf_only,
            include_portfolio=payload.include_portfolio,
            conservative_view=payload.conservative_view,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        answer=result.get("answer", ""),
        chunks=result.get("chunks", []),
        image_review=result.get("image_review", ""),
        memory=result.get("memory"),
    )


@app.get("/api/profile")
def get_profile() -> dict[str, Any]:
    return load_profile()


@app.put("/api/profile")
def put_profile(payload: SaveProfileRequest) -> dict[str, Any]:
    save_profile(payload.profile)
    return load_profile()


@app.get("/api/portfolio")
def get_portfolio() -> dict[str, Any]:
    portfolio = load_portfolio()
    portfolio["analytics"] = calculate_portfolio_analytics(portfolio)
    return portfolio


@app.put("/api/portfolio")
def put_portfolio(payload: SavePortfolioRequest) -> dict[str, Any]:
    portfolio = dict(payload.portfolio)
    portfolio.pop("analytics", None)
    save_portfolio(portfolio)
    portfolio["analytics"] = calculate_portfolio_analytics(portfolio)
    return portfolio


@app.get("/api/portfolio/analytics")
def get_portfolio_analytics() -> dict[str, Any]:
    return calculate_portfolio_analytics(load_portfolio())


@app.get("/api/memory")
def get_memory() -> dict[str, Any]:
    return load_memory()


@app.get("/api/journals")
def get_journals() -> dict[str, Any]:
    return {"journals": load_daily_journals()}
