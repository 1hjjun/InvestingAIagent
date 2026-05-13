# yfinance로 ETF 구성 종목 비중을 조회하고 실패 시 mock fallback하는 Tool
from __future__ import annotations

import os
from typing import Any

from agents import function_tool

from web_service.backend.rebalance_agent.logger import guardrail_state, tool_result_recorder
from web_service.backend.rebalance_agent.mocks.fixtures import ETF_HOLDINGS


def _allow_mock_fallback() -> bool:
    return os.environ.get("ALLOW_MOCK_FALLBACK", "false").lower() in {"1", "true", "yes", "y"}


def _normalize_weight(value: Any) -> float:
    weight = float(value)
    return weight / 100 if weight > 1 else weight


def _fetch_yfinance_holdings(etf_ticker: str) -> list[dict[str, Any]]:
    import yfinance as yf

    top_holdings = yf.Ticker(etf_ticker).funds_data.top_holdings
    if top_holdings is None or top_holdings.empty:
        raise ValueError(f"yfinance가 {etf_ticker} 구성 종목을 반환하지 않았습니다.")

    holdings: list[dict[str, Any]] = []
    for symbol, row in top_holdings.iterrows():
        ticker = str(symbol).strip()
        if not ticker or ticker.lower() == "nan":
            continue
        weight = _normalize_weight(row["Holding Percent"])
        holdings.append({"ticker": ticker, "weight": weight})

    if not holdings:
        raise ValueError(f"yfinance가 {etf_ticker} 구성 종목을 파싱할 수 없는 형태로 반환했습니다.")
    return holdings


def _do_etf_constituent(etf_ticker: str) -> dict[str, Any]:
    inputs = {"etf_ticker": etf_ticker}
    guardrail_state.record_tool_call("etf_constituent", inputs)

    try:
        holdings = _fetch_yfinance_holdings(etf_ticker)
        result = {
            "ok": True,
            "data": {"etf_ticker": etf_ticker, "holdings": holdings},
            "error": None,
            "source": "api",
            "fallback_used": False,
            "fallback_reason": None,
            "original_error": None,
        }
        return tool_result_recorder.record("etf_constituent", inputs, result)
    except Exception as exc:
        mock = ETF_HOLDINGS.get(etf_ticker)
        if mock and _allow_mock_fallback():
            result = {
                "ok": True,
                "data": {"etf_ticker": etf_ticker, "holdings": mock},
                "error": None,
                "source": "mock",
                "fallback_used": True,
                "fallback_reason": type(exc).__name__,
                "original_error": {"code": type(exc).__name__, "message": str(exc)},
            }
            return tool_result_recorder.record("etf_constituent", inputs, result)
        result = {
            "ok": False,
            "data": None,
            "error": {"code": "YFINANCE_HOLDINGS_UNAVAILABLE", "message": str(exc)},
            "source": "api",
            "fallback_used": False,
            "fallback_reason": type(exc).__name__,
            "original_error": {"code": type(exc).__name__, "message": str(exc)},
        }
        return tool_result_recorder.record("etf_constituent", inputs, result)


@function_tool(strict_mode=False)
def etf_constituent(etf_ticker: str) -> dict[str, Any]:
    """ETF/펀드의 구성 종목과 비중(weight 0~1)을 반환한다. 개별 주식 티커에는 사용하지 않는다.

    etf_ticker: Yahoo Finance ETF/펀드 티커 (예: "QQQM", "QQQ", "SPY", "QLD")
    """
    return _do_etf_constituent(etf_ticker)
