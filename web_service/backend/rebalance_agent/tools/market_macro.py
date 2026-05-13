# yfinance와 LLM으로 글로벌 매크로 지표를 수집·해석하는 Tool
from __future__ import annotations

import json
import os
from typing import Any

from agents import function_tool

from web_service.backend.rebalance_agent.logger import guardrail_state, tool_result_recorder
from web_service.backend.rebalance_agent.llm_provider import DEFAULT_GEMINI_MODEL, chat_json, select_llm_provider
from web_service.backend.rebalance_agent.mocks.fixtures import PRICES


_MACRO_ALIASES = {"GLOBAL_MACRO", "MACRO", "GLOBAL", "거시", "매크로"}
_ETF_IMPACT_TICKERS = ["SPY", "QQQ", "XLK", "XLE", "XLF", "GLD", "TLT"]

_INDICATORS: dict[str, dict[str, Any]] = {
    "dxy": {"label": "달러 인덱스(DXY)", "ticker": "DX-Y.NYB", "axis": "currency"},
    "usd_krw": {"label": "원/달러 환율", "ticker": "KRW=X", "axis": "currency"},
    "us10y": {"label": "미국채 10년물 금리", "ticker": "^TNX", "axis": "rates"},
    "us2y": {"label": "미국채 2년물 금리", "ticker": "2YY=F", "axis": "rates"},
    "wti": {"label": "WTI유", "ticker": "CL=F", "axis": "commodities"},
    "natural_gas": {"label": "천연가스", "ticker": "NG=F", "axis": "commodities"},
    "gold": {"label": "금(Gold)", "ticker": "GC=F", "axis": "commodities"},
    "copper": {"label": "구리", "ticker": "HG=F", "axis": "commodities"},
    "vix": {"label": "VIX 지수", "ticker": "^VIX", "axis": "sentiment"},
}


def _pct_change(current: float | None, base: float | None) -> float | None:
    if current is None or base in (None, 0):
        return None
    return round(((current - base) / base) * 100, 4)


def _trend(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return "unknown"
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "flat"


def _fetch_yfinance(ticker: str, timeout: int = 5) -> dict[str, Any]:
    import yfinance as yf  # 런타임 import — 누락 시 ImportError로 fallback 진입

    info = yf.Ticker(ticker).fast_info
    current_price = getattr(info, "last_price", None) or getattr(info, "regular_market_price", None)
    if not current_price:
        raise ValueError(f"yfinance가 {ticker} 가격을 반환하지 않았습니다.")
    previous_close = getattr(info, "previous_close", None) or current_price
    return {
        "current_price": current_price,
        "previous_close": previous_close,
        "change_pct_1d": _pct_change(float(current_price), float(previous_close)),
        "trend": _trend(float(current_price), float(previous_close)),
    }


def _series_value_at(values: list[float], index: int) -> float | None:
    try:
        value = values[index]
    except IndexError:
        return None
    return float(value) if value is not None else None


def _fetch_yfinance_indicator(key: str, spec: dict[str, Any]) -> dict[str, Any]:
    import yfinance as yf

    history = yf.Ticker(spec["ticker"]).history(period="1mo", interval="1d")
    if history is None or history.empty or "Close" not in history:
        raise ValueError(f"yfinance가 {spec['ticker']} 1개월 가격을 반환하지 않았습니다.")

    closes = [float(value) for value in history["Close"].dropna().tolist()]
    if not closes:
        raise ValueError(f"yfinance가 {spec['ticker']} 종가를 반환하지 않았습니다.")

    scale = float(spec.get("scale", 1.0))
    current = _series_value_at(closes, -1)
    previous = _series_value_at(closes, -2) or current
    month_ago = _series_value_at(closes, 0)
    current = current * scale if current is not None else None
    previous = previous * scale if previous is not None else None
    month_ago = month_ago * scale if month_ago is not None else None

    return {
        "key": key,
        "label": spec["label"],
        "ticker": spec["ticker"],
        "axis": spec["axis"],
        "current_value": round(current, 4) if current is not None else None,
        "previous_close": round(previous, 4) if previous is not None else None,
        "month_ago": round(month_ago, 4) if month_ago is not None else None,
        "change_pct_1d": _pct_change(current, previous),
        "change_pct_1m": _pct_change(current, month_ago),
        "trend": _trend(current, previous),
        "status": "ok",
        "error": None,
    }


def _fetch_macro_indicators() -> dict[str, Any]:
    indicators: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key, spec in _INDICATORS.items():
        try:
            indicators[key] = _fetch_yfinance_indicator(key, spec)
        except Exception as exc:
            indicators[key] = {
                "key": key,
                "label": spec["label"],
                "ticker": spec["ticker"],
                "axis": spec["axis"],
                "current_value": None,
                "previous_close": None,
                "month_ago": None,
                "change_pct_1d": None,
                "change_pct_1m": None,
                "trend": "unknown",
                "status": "unavailable",
                "error": {"code": type(exc).__name__, "message": str(exc)},
            }
            errors[key] = str(exc)

    us10y = indicators.get("us10y", {}).get("current_value")
    us2y = indicators.get("us2y", {}).get("current_value")
    indicators["yield_spread_10y_2y"] = {
        "key": "yield_spread_10y_2y",
        "label": "미국채 10년-2년 금리차",
        "ticker": "computed",
        "axis": "rates",
        "current_value": round(us10y - us2y, 4) if us10y is not None and us2y is not None else None,
        "unit": "percentage_point",
        "status": "ok" if us10y is not None and us2y is not None else "unavailable",
        "error": None if us10y is not None and us2y is not None else {"code": "MISSING_YIELD", "message": "10년물 또는 2년물 금리 데이터가 없습니다."},
    }
    return {"indicators": indicators, "errors": errors}


def _fetch_cnn_fear_greed() -> dict[str, Any]:
    import fear_greed  # type: ignore

    data = fear_greed.get()
    score = data.get("score")
    if score is None:
        raise ValueError("fear-greed 라이브러리가 Fear & Greed score를 반환하지 않았습니다.")
    return {
        "label": "CNN Fear & Greed Index",
        "current_value": round(float(score), 2),
        "rating": data.get("rating"),
        "timestamp": data.get("timestamp"),
        "history": data.get("history") or {},
        "indicators": data.get("indicators") or {},
        "status": "ok",
        "source": "fear-greed",
        "error": None,
    }


def _unavailable_fear_greed(exc: Exception) -> dict[str, Any]:
    return {
        "label": "CNN Fear & Greed Index",
        "current_value": None,
        "rating": None,
        "timestamp": None,
        "history": {},
        "indicators": {},
        "status": "unavailable",
        "source": "fear-greed",
        "error": {"code": type(exc).__name__, "message": str(exc)},
    }


def _coerce_lines(value: Any, target_count: int) -> list[str]:
    if isinstance(value, list):
        lines = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        lines = [line.strip("-• 0123456789.").strip() for line in value.splitlines() if line.strip()]
    else:
        lines = []
    lines = lines[:target_count]
    while len(lines) < target_count:
        lines.append("수집된 지표만으로는 추가 판단을 확정하기 어렵습니다.")
    return lines


def _normalize_etf_impact(value: Any) -> dict[str, dict[str, str]]:
    impacts: dict[str, dict[str, str]] = {}
    if isinstance(value, dict):
        iterator = value.items()
    elif isinstance(value, list):
        iterator = ((item.get("ticker"), item) for item in value if isinstance(item, dict))
    else:
        iterator = []

    for ticker, payload in iterator:
        if ticker not in _ETF_IMPACT_TICKERS or not isinstance(payload, dict):
            continue
        stance = str(payload.get("impact") or payload.get("stance") or "neutral").lower()
        if stance not in {"positive", "neutral", "negative"}:
            stance = "neutral"
        impacts[ticker] = {"impact": stance, "reason": str(payload.get("reason") or "근거가 충분히 명시되지 않았습니다.")}

    for ticker in _ETF_IMPACT_TICKERS:
        impacts.setdefault(ticker, {"impact": "neutral", "reason": "수집된 지표만으로는 방향성을 단정하기 어렵습니다."})
    return impacts


def _heuristic_strategy(indicators: dict[str, Any], fear_greed: dict[str, Any]) -> dict[str, Any]:
    vix = indicators.get("vix", {})
    dxy = indicators.get("dxy", {})
    us10y = indicators.get("us10y", {})
    gold = indicators.get("gold", {})
    wti = indicators.get("wti", {})
    risk_off = (vix.get("current_value") or 0) >= 20 or dxy.get("trend") == "up"
    higher_rates = us10y.get("trend") == "up"

    qqq_impact = "negative" if risk_off or higher_rates else "neutral"
    tlt_impact = "negative" if higher_rates else "neutral"
    gld_impact = "positive" if gold.get("trend") == "up" or risk_off else "neutral"
    xle_impact = "positive" if wti.get("trend") == "up" else "neutral"

    return {
        "macro_summary": _coerce_lines(
            [
                "LLM 분석을 사용할 수 없어 규칙 기반 보조 판단을 제공합니다.",
                f"VIX는 {vix.get('current_value')} 수준이며 추세는 {vix.get('trend')}입니다.",
                f"달러 인덱스 추세는 {dxy.get('trend')}이고, 미국 10년물 금리 추세는 {us10y.get('trend')}입니다.",
                f"CNN Fear & Greed 상태는 {fear_greed.get('status')}입니다.",
            ],
            4,
        ),
        "correlation_analysis": _coerce_lines(
            [
                "달러와 VIX가 함께 상승하면 위험회피 심리가 강해졌다고 해석할 수 있습니다.",
                "장기 금리 상승은 성장주와 장기채 밸류에이션에 부담으로 작용할 수 있습니다.",
                "유가 상승은 에너지 섹터에는 우호적이지만 물가와 금리 부담을 키울 수 있습니다.",
            ],
            3,
        ),
        "etf_impact": {
            "SPY": {"impact": "neutral", "reason": "시장 전반 지수라 금리와 위험심리 영향을 동시에 받습니다."},
            "QQQ": {"impact": qqq_impact, "reason": "나스닥은 금리 상승과 위험회피 국면에 민감합니다."},
            "XLK": {"impact": qqq_impact, "reason": "기술주는 할인율 상승과 달러 강세에 부담을 받을 수 있습니다."},
            "XLE": {"impact": xle_impact, "reason": "유가 추세가 에너지 섹터 방향성을 크게 좌우합니다."},
            "XLF": {"impact": "neutral", "reason": "금리 상승은 마진에 우호적일 수 있지만 경기 우려는 부담입니다."},
            "GLD": {"impact": gld_impact, "reason": "안전자산 선호와 금 가격 추세를 함께 봐야 합니다."},
            "TLT": {"impact": tlt_impact, "reason": "장기 금리 상승은 장기채 가격에 직접 부담입니다."},
        },
        "portfolio_implications": _coerce_lines(
            [
                "성장주 쏠림 포트폴리오는 금리와 VIX가 동시에 높아지는 구간에서 변동성 관리가 필요합니다.",
                "원자재와 안전자산 신호가 강하면 일부 방어적 자산을 검토할 수 있습니다.",
                "이 판단은 LLM 실패 시 보조 로직이므로 실제 투자 결정 전 최신 지표를 재확인해야 합니다.",
            ],
            3,
        ),
    }


def _macro_strategy_with_llm(indicators: dict[str, Any], fear_greed: dict[str, Any]) -> dict[str, Any]:
    provider = select_llm_provider(
        openai_model=os.environ.get("MARKET_MACRO_MODEL", "gpt-4o-mini"),
        gemini_model=os.environ.get("GEMINI_MARKET_MACRO_MODEL", os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)),
        model_env="MARKET_MACRO_MODEL",
    )
    if provider is None:
        raise ValueError("OPENAI_API_KEY or GEMINI_API_KEY not set")

    parsed = chat_json(
        provider,
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 20년 경력의 글로벌 거시경제 전략가다. 금리, 환율, 원자재, "
                    "지정학적 리스크와 심리 지표를 연결해 주식 및 ETF 시장 영향을 판단한다. "
                    "반드시 valid JSON만 반환한다."
                ),
            },
            {
                "role": "user",
                "content": (
                    "아래 최신 지표를 바탕으로 한국어로 분석하라. 단순 수치 나열이 아니라 "
                    "지표 간 상관관계와 ETF별 영향을 판단하라.\n"
                    "schema: {"
                    "\"macro_summary\": [문자열 4개], "
                    "\"correlation_analysis\": [문자열 3개], "
                    "\"etf_impact\": {\"SPY|QQQ|XLK|XLE|XLF|GLD|TLT\": "
                    "{\"impact\": \"positive|neutral|negative\", \"reason\": \"문자열\"}}, "
                    "\"portfolio_implications\": [문자열 3개]"
                    "}\n\n"
                    f"INDICATORS:\n{json.dumps(indicators, ensure_ascii=False, default=str)}\n\n"
                    f"FEAR_GREED:\n{json.dumps(fear_greed, ensure_ascii=False, default=str)}"
                ),
            },
        ],
        max_tokens=1400,
    )
    return {
        "macro_summary": _coerce_lines(parsed.get("macro_summary"), 4),
        "correlation_analysis": _coerce_lines(parsed.get("correlation_analysis"), 3),
        "etf_impact": _normalize_etf_impact(parsed.get("etf_impact")),
        "portfolio_implications": _coerce_lines(parsed.get("portfolio_implications"), 3),
    }


def _do_global_macro() -> dict[str, Any]:
    macro = _fetch_macro_indicators()
    try:
        fear_greed = _fetch_cnn_fear_greed()
    except Exception as exc:
        fear_greed = _unavailable_fear_greed(exc)

    indicators = macro["indicators"]
    try:
        strategy = _macro_strategy_with_llm(indicators, fear_greed)
        analysis_source = "llm"
        analysis_error = None
    except Exception as exc:
        strategy = _heuristic_strategy(indicators, fear_greed)
        analysis_source = "heuristic"
        analysis_error = {"code": type(exc).__name__, "message": str(exc)}

    available_count = sum(1 for item in indicators.values() if item.get("status") == "ok")
    if available_count == 0:
        return {
            "ok": False,
            "data": None,
            "error": {"code": "MACRO_DATA_UNAVAILABLE", "message": "수집 가능한 매크로 지표가 없습니다."},
            "source": "api",
            "fallback_used": analysis_source == "heuristic",
            "fallback_reason": analysis_error["code"] if analysis_error else None,
            "original_error": {"indicator_errors": macro["errors"], "analysis_error": analysis_error},
        }

    return {
        "ok": True,
        "data": {
            "mode": "GLOBAL_MACRO",
            "indicators": indicators,
            "fear_greed": fear_greed,
            "analysis": strategy,
            "analysis_source": analysis_source,
            "analysis_error": analysis_error,
        },
        "error": None,
        "source": "api+fear_greed+llm" if analysis_source == "llm" else "api+fear_greed+heuristic",
        "fallback_used": analysis_source == "heuristic",
        "fallback_reason": analysis_error["code"] if analysis_error else None,
        "original_error": {"indicator_errors": macro["errors"], "analysis_error": analysis_error},
    }


def _do_single_ticker(ticker: str) -> dict[str, Any]:
    try:
        price_data = _fetch_yfinance(ticker)
        return {
            "ok": True,
            "data": {"ticker": ticker, **price_data},
            "error": None,
            "source": "api",
            "fallback_used": False,
            "fallback_reason": None,
            "original_error": None,
        }
    except Exception as exc:
        mock = PRICES.get(ticker)
        if mock:
            return {
                "ok": True,
                "data": {"ticker": ticker, **mock},
                "error": None,
                "source": "mock",
                "fallback_used": True,
                "fallback_reason": type(exc).__name__,
                "original_error": {"code": type(exc).__name__, "message": str(exc)},
            }
        return {
            "ok": False,
            "data": None,
            "error": {"code": "TICKER_NOT_FOUND", "message": f"ticker {ticker} not in mock data"},
            "source": "mock",
            "fallback_used": True,
            "fallback_reason": type(exc).__name__,
            "original_error": {"code": type(exc).__name__, "message": str(exc)},
        }


def _do_market_macro(ticker: str) -> dict[str, Any]:
    normalized = ticker.strip()
    inputs = {"ticker": normalized}
    guardrail_state.record_tool_call("market_macro", inputs)

    if normalized.upper() in _MACRO_ALIASES:
        result = _do_global_macro()
    else:
        result = _do_single_ticker(normalized)
    return tool_result_recorder.record("market_macro", inputs, result)


@function_tool(strict_mode=False)
def market_macro(ticker: str) -> dict[str, Any]:
    """특정 티커 가격 또는 글로벌 매크로 전략 분석을 반환한다.

    ticker: Yahoo Finance 티커(예: "^VIX", "NVDA") 또는 "GLOBAL_MACRO"/"macro"
    """
    return _do_market_macro(ticker)
