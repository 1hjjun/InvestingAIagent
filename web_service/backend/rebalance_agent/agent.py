# Agent 정의 및 Runner 호출 래퍼 (OpenAI Agents SDK 0.16.x)
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from agents import Agent, MaxTurnsExceeded, RunErrorHandlerInput, RunErrorHandlerResult, Runner

from web_service.backend.rebalance_agent.logger import (
    AgentStopRequested,
    GuardrailState,
    JsonlLogger,
    LoggingAndGuardrailHooks,
    guardrail_state,
    trace_recorder,
    tool_result_recorder,
)
from web_service.backend.rebalance_agent.provider_config import configure_agent_model_provider
from web_service.backend.rebalance_agent.prompts import SYSTEM_INSTRUCTIONS
from web_service.backend.rebalance_agent.schema import AgentInput, AgentOutput
from web_service.backend.rebalance_agent.tools.etf_constituent import etf_constituent
from web_service.backend.rebalance_agent.tools.journal_db import journal_db
from web_service.backend.rebalance_agent.tools.market_macro import market_macro
from web_service.backend.rebalance_agent.tools.portfolio_allocation_calculator import portfolio_allocation_calculator
from web_service.backend.rebalance_agent.tools.true_exposure_calculator import true_exposure_calculator
from web_service.backend.rebalance_agent.tools.vision_extractor import vision_extractor
from web_service.backend.rebalance_agent.tools.youtube_sentiment import youtube_sentiment


# -------------------------------------------------------------------
# Agent 인스턴스 (모듈 레벨 — import 시 생성)
# -------------------------------------------------------------------
agent = Agent(
    name="ETF리밸런싱코치",
    instructions=SYSTEM_INSTRUCTIONS,
    tools=[
        vision_extractor,
        etf_constituent,
        market_macro,
        youtube_sentiment,
        journal_db,
        portfolio_allocation_calculator,
        true_exposure_calculator,
    ],
    model=configure_agent_model_provider(),
)


# -------------------------------------------------------------------
# max_turns 에러 핸들러
# -------------------------------------------------------------------
def _on_max_turns(inp: RunErrorHandlerInput) -> RunErrorHandlerResult:
    partial_text = guardrail_state.last_partial_output or "최대 턴 수에 도달했습니다. 현재까지 수집된 정보로 답변을 종료합니다."
    guardrail_state.stop_reason = "max_turns"
    return RunErrorHandlerResult(
        final_output=partial_text,
        include_in_history=False,
    )


# -------------------------------------------------------------------
# run_agent: 공개 진입점
# -------------------------------------------------------------------
async def run_agent(agent_input: AgentInput, run_id: str | None = None) -> AgentOutput:
    """Agent를 실행하고 AgentOutput을 반환한다. 예외를 외부로 노출하지 않는다."""
    guardrail_state.reset()

    logger = JsonlLogger(run_id=run_id)
    tool_result_recorder.start(logger.run_id)
    hooks = LoggingAndGuardrailHooks(logger=logger)

    prompt = _build_prompt(agent_input)
    logger.log("user_input", query=agent_input.user_query, image_url=agent_input.image_url)
    trace_recorder.start(
        trace_id=logger.run_id,
        request=agent_input.model_dump(),
        prompt=prompt,
        model=str(agent.model),
    )

    answer_text = ""
    chart_data: dict[str, Any] | None = None
    is_saved = False

    try:
        result = await Runner.run(
            agent,
            input=prompt,
            max_turns=7,
            hooks=hooks,
            error_handlers={"max_turns": _on_max_turns},
        )
        answer_text = str(result.final_output) if result.final_output is not None else ""
        chart_data = _extract_chart_data(answer_text)
        is_saved = _detect_journal_write(logger)
        logger.log("final_answer", answer_text=answer_text, chart_data=chart_data, is_saved=is_saved)

    except AgentStopRequested as e:
        guardrail_state.stop_reason = e.stop_reason
        logger.log("guardrail_stop", stop_reason=e.stop_reason, detail=e.detail)
        trace_recorder.fail(e.stop_reason, e.detail)
        partial = guardrail_state.last_partial_output or {}
        answer_text = partial.get("answer_text", f"실행이 중단되었습니다: {e.stop_reason}")
        chart_data = partial.get("chart_data")
        is_saved = partial.get("is_saved", False)
        logger.log("final_answer", answer_text=answer_text, chart_data=chart_data, is_saved=is_saved)

    except Exception as e:
        logger.log("run_error", error=str(e))
        trace_recorder.fail(type(e).__name__, str(e))
        answer_text = f"에러가 발생했습니다: {e}"
        chart_data = None
        is_saved = False
        logger.log("final_answer", answer_text=answer_text, chart_data=chart_data, is_saved=is_saved)

    summary = logger.summarize()
    logger.log("run_summary", **summary)
    trace_recorder.stop(
        final_answer=answer_text,
        chart_data=chart_data,
        is_saved=is_saved,
        stop_reason=guardrail_state.stop_reason,
    )
    tool_result_recorder.stop()

    return AgentOutput(
        answer_text=answer_text,
        chart_data=chart_data,
        is_saved=is_saved,
        stop_reason=guardrail_state.stop_reason,
        trace_id=logger.run_id,
    )


# -------------------------------------------------------------------
# 내부 헬퍼
# -------------------------------------------------------------------
def _build_prompt(agent_input: AgentInput) -> str:
    today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    parts: list[str] = [f"[오늘 날짜: {today}]"]
    if agent_input.profile_context:
        parts.append("[사용자 투자 프로필]\n" + _json_block(agent_input.profile_context))
    if agent_input.portfolio_context:
        parts.append("[현재 저장된 포트폴리오]\n" + _json_block(agent_input.portfolio_context))
        parts.append(
            "[포트폴리오 사용 규칙]\n"
            "- 이미지가 없어도 위 저장된 포트폴리오를 현재 포트폴리오로 사용한다.\n"
            "- analytics 값은 대시보드에 표시되는 현재 계산값이므로 총 시드, 10%, 현금비중, 테마비중 설명에 우선 사용한다.\n"
            "- 추가 비중 계산이 필요하면 저장된 positions/crypto_holdings/cash_krw를 바탕으로 portfolio_allocation_calculator를 호출한다.\n"
            "- 이미지가 함께 있으면 vision_extractor 결과와 저장 포트폴리오를 비교해서 더 최신 정보인지 확인한다."
        )
    if agent_input.image_url:
        parts.append(f"[이미지 경로: {agent_input.image_url}]")
    parts.append(agent_input.user_query)
    return "\n".join(parts)


def _json_block(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _extract_chart_data(text: str) -> dict[str, Any] | None:
    # 답변 텍스트에서 JSON 블록(chart_data)을 추출한다.
    try:
        start = text.find("{")
        if start == -1:
            return None
        data = json.loads(text[start:])
        if isinstance(data, dict) and "type" in data:
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _detect_journal_write(logger: JsonlLogger) -> bool:
    for rec in logger._tool_events:
        if rec.get("type") == "tool_result" and rec.get("tool") == "journal_db":
            return True
    return False
