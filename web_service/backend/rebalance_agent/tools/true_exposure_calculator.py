# 포트폴리오 내 특정 티커의 실질 노출도를 결정론적으로 계산하는 Tool
from __future__ import annotations

from typing import Any

from agents import function_tool

from web_service.backend.rebalance_agent.logger import guardrail_state, tool_result_recorder


def _calc_exposure(
    assets: list[dict[str, Any]],
    etf_holdings: dict[str, list[dict[str, Any]]],
    target_ticker: str,
) -> dict[str, Any]:
    inputs = {
        "assets": assets,
        "etf_holdings": etf_holdings,
        "target_ticker": target_ticker,
    }
    guardrail_state.record_tool_call(
        "true_exposure_calculator",
        {"target_ticker": target_ticker},
    )

    total_value = sum(a.get("value", 0) for a in assets)
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
        return tool_result_recorder.record("true_exposure_calculator", inputs, result)

    direct_value = sum(
        a.get("value", 0) for a in assets if a.get("ticker") == target_ticker
    )

    etf_exposure_value = 0.0
    for asset in assets:
        ticker = asset.get("ticker", "")
        if ticker == target_ticker:
            continue
        for holding in etf_holdings.get(ticker, []):
            if holding.get("ticker") == target_ticker:
                etf_exposure_value += asset.get("value", 0) * holding.get("weight", 0.0)

    true_exposure_value = direct_value + etf_exposure_value
    true_exposure_pct = (true_exposure_value / total_value) * 100

    breakdown: list[dict[str, Any]] = []
    if direct_value > 0:
        breakdown.append({
            "label": f"{target_ticker} 직접 보유",
            "value": direct_value,
            "pct": (direct_value / total_value) * 100,
        })
    for asset in assets:
        ticker = asset.get("ticker", "")
        if ticker == target_ticker:
            continue
        for holding in etf_holdings.get(ticker, []):
            if holding.get("ticker") == target_ticker:
                v = asset.get("value", 0) * holding.get("weight", 0.0)
                if v > 0:
                    breakdown.append({
                        "label": f"{ticker} via {target_ticker}",
                        "value": v,
                        "pct": (v / total_value) * 100,
                    })

    result = {
        "ok": True,
        "data": {
            "target_ticker": target_ticker,
            "true_exposure_pct": round(true_exposure_pct, 4),
            "true_exposure_value": round(true_exposure_value, 4),
            "total_portfolio_value": round(total_value, 4),
            "chart_data": {
                "type": "pie",
                "title": f"{target_ticker} 실질 노출도 분석",
                "breakdown": breakdown,
            },
        },
        "error": None,
        "source": "local",
        "fallback_used": False,
        "fallback_reason": None,
        "original_error": None,
    }
    return tool_result_recorder.record("true_exposure_calculator", inputs, result)


@function_tool(strict_mode=False)
def true_exposure_calculator(
    assets: list[dict[str, Any]],
    etf_holdings: dict[str, list[dict[str, Any]]],
    target_ticker: str,
) -> dict[str, Any]:
    """포트폴리오 내 target_ticker의 실질 노출도(%)를 계산한다.

    assets: [{ticker, asset_type, value, ...}] — 각 자산의 현재 가치(USD 단위)
    etf_holdings: {etf_ticker: [{ticker, weight (0~1)}, ...]} — ETF 구성 종목 비중
    target_ticker: 노출도를 계산할 목표 티커 (예: "NVDA")
    """
    return _calc_exposure(assets, etf_holdings, target_ticker)
