# 포트폴리오 자산별·섹터별 비중을 결정론적으로 계산하는 Tool
from __future__ import annotations

from typing import Any

from agents import function_tool

from web_service.backend.rebalance_agent.logger import guardrail_state, tool_result_recorder


def _calc_portfolio_allocation(
    assets: list[dict[str, Any]],
    sector_by_ticker: dict[str, str] | None = None,
) -> dict[str, Any]:
    inputs = {"assets": assets, "sector_by_ticker": sector_by_ticker or {}}
    guardrail_state.record_tool_call("portfolio_allocation_calculator", {"asset_count": len(assets)})

    total_value = sum(float(asset.get("value", 0) or 0) for asset in assets)
    if total_value <= 0:
        result = {
            "ok": False,
            "data": None,
            "error": {"code": "ZERO_PORTFOLIO", "message": "포트폴리오 총 가치가 0 이하입니다."},
            "source": "local",
            "fallback_used": False,
            "fallback_reason": None,
            "original_error": None,
        }
        return tool_result_recorder.record("portfolio_allocation_calculator", inputs, result)

    sector_map = sector_by_ticker or {}
    asset_allocations: list[dict[str, Any]] = []
    sector_totals: dict[str, float] = {}

    for asset in assets:
        ticker = str(asset.get("ticker", "")).upper()
        value = float(asset.get("value", 0) or 0)
        sector = sector_map.get(ticker) or asset.get("sector") or "Unclassified"
        pct = (value / total_value) * 100
        asset_allocations.append(
            {
                "ticker": ticker,
                "asset_type": asset.get("asset_type"),
                "value": round(value, 4),
                "pct": round(pct, 4),
                "sector": sector,
            }
        )
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value

    sector_allocations = [
        {
            "sector": sector,
            "value": round(value, 4),
            "pct": round((value / total_value) * 100, 4),
        }
        for sector, value in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    result = {
        "ok": True,
        "data": {
            "total_portfolio_value": round(total_value, 4),
            "asset_allocations": asset_allocations,
            "sector_allocations": sector_allocations,
        },
        "error": None,
        "source": "local",
        "fallback_used": False,
        "fallback_reason": None,
        "original_error": None,
    }
    return tool_result_recorder.record("portfolio_allocation_calculator", inputs, result)


@function_tool(strict_mode=False)
def portfolio_allocation_calculator(
    assets: list[dict[str, Any]],
    sector_by_ticker: dict[str, str] | None = None,
) -> dict[str, Any]:
    """자산별 평가금액 비중과 LLM이 분류한 섹터별 비중을 계산한다.

    assets: [{ticker, asset_type, value, ...}]
    sector_by_ticker: {ticker: S&P500 GICS sector name}
    """
    return _calc_portfolio_allocation(assets, sector_by_ticker)
