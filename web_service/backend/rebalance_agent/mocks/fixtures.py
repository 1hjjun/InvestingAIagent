# Tool fallback 시 사용하는 결정적 mock 데이터
from __future__ import annotations

from typing import Any


# ETF 편입 비중 (weight는 0~1 비율). yfinance 실패 fallback용 샘플 데이터.
ETF_HOLDINGS: dict[str, list[dict[str, Any]]] = {
    "QQQ": [
        {"ticker": "NVDA", "weight": 0.0854},
        {"ticker": "AAPL", "weight": 0.0801},
        {"ticker": "MSFT", "weight": 0.0772},
        {"ticker": "AMZN", "weight": 0.0530},
        {"ticker": "META", "weight": 0.0498},
        {"ticker": "GOOGL", "weight": 0.0312},
    ],
    "QLD": [
        # ProShares Ultra QQQ — QQQ 2배 레버리지. 실제로는 swap이지만 검증을 위해
        # 동일 holdings를 사용하고 노출도 계산은 호출 측 leverage_factor로 처리한다.
        {"ticker": "NVDA", "weight": 0.0854},
        {"ticker": "AAPL", "weight": 0.0801},
        {"ticker": "MSFT", "weight": 0.0772},
        {"ticker": "AMZN", "weight": 0.0530},
    ],
    "SPY": [
        {"ticker": "AAPL", "weight": 0.0712},
        {"ticker": "MSFT", "weight": 0.0680},
        {"ticker": "NVDA", "weight": 0.0670},
        {"ticker": "AMZN", "weight": 0.0398},
        {"ticker": "GOOGL", "weight": 0.0220},
    ],
}


# 시장 지표 / 주가 mock. yfinance 차단 환경에서 사용.
PRICES: dict[str, dict[str, Any]] = {
    "^VIX": {"current_price": 25.4, "trend": "up"},
    "NVDA": {"current_price": 140.2, "trend": "down"},
    "QQQ": {"current_price": 480.0, "trend": "down"},
    "QLD": {"current_price": 100.0, "trend": "down"},
    "SPY": {"current_price": 590.0, "trend": "flat"},
    "AAPL": {"current_price": 230.0, "trend": "flat"},
    "MSFT": {"current_price": 420.0, "trend": "flat"},
}


# 키워드 기반 mock sentiment. YouTube API 키 없을 때 사용.
YOUTUBE_SENTIMENTS: dict[str, dict[str, str]] = {
    "나스닥 전망": {
        "sentiment": "Bearish",
        "summary": "단기 조정 우려가 강함. VIX 상승과 금리 변수에 주목.",
    },
    "엔비디아": {
        "sentiment": "Neutral",
        "summary": "AI 성장은 견조하지만 단기 모멘텀 정체. 실적 가이던스 대기.",
    },
    "FOMC": {
        "sentiment": "Bearish",
        "summary": "매파적 발언 우려. 단기 변동성 확대 가능.",
    },
    "QQQ": {
        "sentiment": "Neutral",
        "summary": "기술주 비중 높은 ETF. 거시 변수에 따라 단기 흔들림 예상.",
    },
}


# Vision_Extractor fallback용 합성 포트폴리오.
SAMPLE_ASSETS: list[dict[str, Any]] = [
    {"ticker": "NVDA", "asset_type": "stock", "amount": 10, "value": 1402.0},
    {"ticker": "QQQ", "asset_type": "etf", "amount": 12, "value": 5760.0},
    {"ticker": "QLD", "asset_type": "etf", "amount": 30, "value": 3000.0},
]
