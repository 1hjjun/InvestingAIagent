# Tool 결과 + Agent I/O Pydantic 스키마
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ToolError(BaseModel):
    code: str
    message: str


class ToolResult(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    error: ToolError | None = None
    source: Literal["api", "mock", "local"]
    fallback_used: bool = False
    fallback_reason: str | None = None
    original_error: dict[str, Any] | None = None


class AgentInput(BaseModel):
    user_query: str
    image_url: str | None = None
    profile_context: dict[str, Any] | None = None
    portfolio_context: dict[str, Any] | None = None


class AgentOutput(BaseModel):
    answer_text: str
    chart_data: dict[str, Any] | None = None
    is_saved: bool = False
    stop_reason: str | None = None
    trace_id: str | None = None
