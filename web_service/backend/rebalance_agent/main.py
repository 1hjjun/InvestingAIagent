# CLI 진입점 — argparse로 예시 실행 또는 커스텀 입력 처리
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _load_example(n: int) -> dict:
    path = Path(__file__).parent.parent / "examples" / f"input_{n}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_custom(path_str: str) -> dict:
    with open(path_str, encoding="utf-8") as f:
        return json.load(f)


async def _run(data: dict, force_loop: bool) -> None:
    from web_service.backend.rebalance_agent.agent import run_agent
    from web_service.backend.rebalance_agent.logger import guardrail_state
    from web_service.backend.rebalance_agent.schema import AgentInput

    if force_loop:
        # 실제 LLM 없이 repeated_tool_call 종료 경로를 deterministic하게 검증한다.
        from web_service.backend.rebalance_agent.logger import AgentStopRequested

        guardrail_state.reset()
        guardrail_state.record_tool_call("journal_db", {"mode": "write", "entry": "test"})
        try:
            guardrail_state.record_tool_call("journal_db", {"mode": "write", "entry": "test"})
        except AgentStopRequested as e:
            print(f"[force-loop] 종료 사유: {e.stop_reason}")
            print(f"[force-loop] 상세: {e.detail}")
            return

    agent_input = AgentInput(**data)
    result = await run_agent(agent_input)

    print("\n" + "=" * 60)
    print("[최종 답변]")
    print(result.answer_text)
    if result.chart_data:
        print("\n[차트 데이터]")
        print(json.dumps(result.chart_data, ensure_ascii=False, indent=2))
    print(f"\n[일지 저장]: {result.is_saved}")
    if result.stop_reason:
        print(f"[종료 사유]: {result.stop_reason}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI ETF 리밸런싱 코치 Agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--example", type=int, choices=[1, 2, 3], metavar="{1,2,3}", help="예시 입력 번호")
    group.add_argument("--input", metavar="PATH", help="커스텀 JSON 입력 파일 경로")
    parser.add_argument("--force-loop", action="store_true", help="LLM 없이 repeated_tool_call 종료 경로 검증")
    args = parser.parse_args()

    if args.example:
        data = _load_example(args.example)
    elif args.input:
        data = _load_custom(args.input)
    elif args.force_loop:
        data = {"user_query": "force-loop 테스트"}
    else:
        parser.print_help()
        sys.exit(0)

    asyncio.run(_run(data, force_loop=args.force_loop))


if __name__ == "__main__":
    main()
