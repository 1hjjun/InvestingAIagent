from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "investment_assistant_system.txt"

FALLBACK_SYSTEM_PROMPT = """너는 사용자의 개인 투자 리서치 파트너다.
제공된 PDF 근거, 사용자 투자 프로필, 포트폴리오, 대화 메모리를 함께 고려한다.
매수/매도 지시는 하지 않고, 사용자가 스스로 판단할 수 있도록 돕는다.
"""


def load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        return FALLBACK_SYSTEM_PROMPT
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def format_user_profile(profile: dict[str, Any]) -> str:
    return json.dumps(profile, ensure_ascii=False, indent=2)


def format_portfolio(portfolio: dict[str, Any]) -> str:
    return json.dumps(portfolio, ensure_ascii=False, indent=2)


def format_memory(memory: dict[str, Any]) -> str:
    summary = str(memory.get("summary", "")).strip()
    updated_at = str(memory.get("updated_at", "")).strip()
    if updated_at:
        return f"updated_at: {updated_at}\nsummary:\n{summary}"
    return f"summary:\n{summary}"


def build_personal_context(
    profile: dict[str, Any],
    portfolio: dict[str, Any],
    memory: dict[str, Any],
    include_portfolio: bool = True,
) -> str:
    parts = [
        "[사용자 투자 프로필]",
        format_user_profile(profile),
        "",
        "[대화 메모리]",
        format_memory(memory),
    ]
    if include_portfolio:
        parts.extend(["", "[현재 포트폴리오]", format_portfolio(portfolio)])
    return "\n".join(parts).strip()


def build_answer_option_prompt(
    pdf_only: bool,
    include_portfolio: bool,
    conservative_view: bool,
) -> str:
    options = ["[답변 옵션]"]
    if pdf_only:
        options.append("- PDF 근거만 사용한다. 프로필/포트폴리오는 답변 톤과 질문 이해에만 참고하고, 새로운 투자 판단 근거로 쓰지 않는다.")
    else:
        options.append("- PDF 근거를 우선하되, 사용자 프로필/포트폴리오에 대한 해석과 적용 관점을 함께 제시할 수 있다.")
    if include_portfolio:
        options.append("- 포트폴리오 관점을 포함한다. 현재 비중, 역할, 집중도, 리스크 영향을 설명한다.")
    else:
        options.append("- 포트폴리오 관점은 사용자가 직접 요청하지 않는 한 간단히만 언급한다.")
    if conservative_view:
        options.append("- 보수적 관점으로 답변한다. 리스크, 검증 부족, 손실 가능성, 대안 시나리오를 더 강조한다.")
    return "\n".join(options)
