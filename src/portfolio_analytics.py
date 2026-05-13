from __future__ import annotations

from collections import defaultdict
from typing import Any


THEME_LABELS = {
    "cash": "현금",
    "broad_us_growth": "미국 성장 ETF",
    "ai_platform": "AI 플랫폼/빅테크",
    "ev_robotics": "전기차/로보틱스",
    "semiconductor_photonics": "반도체/광전자",
    "energy_electrical": "전력/에너지 인프라",
    "space": "우주/항공",
    "fintech": "핀테크",
    "ai_infra_crypto": "AI 인프라/크립토",
    "crypto": "가상자산",
    "other": "기타",
}


def get_position_value(position: dict[str, Any]) -> float:
    explicit_value = to_float(position.get("holding_value_krw"))
    if explicit_value:
        return explicit_value

    approx_value = to_float(position.get("approx_holding_value_krw"))
    quantity = to_float(position.get("quantity"))
    current_price = to_float(position.get("current_price_krw"))
    if quantity and current_price:
        return quantity * current_price
    if approx_value:
        return approx_value
    return 0.0


def get_position_theme(position: dict[str, Any]) -> str:
    theme = str(position.get("theme", "")).strip()
    if theme:
        return theme

    ticker = str(position.get("ticker", "")).upper()
    target_role = str(position.get("target_role", "")).lower()
    asset_type = str(position.get("asset_type", "")).lower()

    if ticker in {"QQQM", "QLD"}:
        return "broad_us_growth"
    if ticker == "GOOGL" or "platform" in target_role:
        return "ai_platform"
    if ticker == "TSLA" or "ev" in target_role or "robot" in target_role:
        return "ev_robotics"
    if ticker == "6965" or "semiconductor" in target_role or "photonics" in target_role:
        return "semiconductor_photonics"
    if ticker in {"GEV", "ETN"} or "energy" in target_role or "electrical" in target_role:
        return "energy_electrical"
    if ticker in {"RKLB", "UFO"} or "space" in target_role:
        return "space"
    if ticker == "HOOD" or "fintech" in target_role:
        return "fintech"
    if ticker == "IREN" or "crypto" in target_role:
        return "ai_infra_crypto"
    if asset_type == "crypto":
        return "crypto"
    return "other"


def calculate_portfolio_analytics(portfolio: dict[str, Any]) -> dict[str, Any]:
    cash_krw = to_float(portfolio.get("cash_krw"))
    total_seed = cash_krw
    theme_values: dict[str, float] = defaultdict(float)
    position_values = []

    if cash_krw:
        theme_values["cash"] += cash_krw

    for position in portfolio.get("positions", []):
        value = get_position_value(position)
        theme = get_position_theme(position)
        total_seed += value
        theme_values[theme] += value
        position_values.append(
            {
                "ticker": position.get("ticker", ""),
                "name": position.get("name", ""),
                "theme": theme,
                "theme_label": THEME_LABELS.get(theme, THEME_LABELS["other"]),
                "value_krw": round(value),
            }
        )

    crypto_values = []
    for crypto in portfolio.get("crypto_holdings", []):
        value = to_float(crypto.get("holding_value_krw"))
        total_seed += value
        theme_values["crypto"] += value
        crypto_values.append(
            {
                "ticker": crypto.get("ticker", ""),
                "name": crypto.get("name", ""),
                "theme": "crypto",
                "theme_label": THEME_LABELS["crypto"],
                "value_krw": round(value),
            }
        )

    theme_allocation = []
    for theme, value in sorted(theme_values.items(), key=lambda item: item[1], reverse=True):
        allocation_pct = (value / total_seed * 100) if total_seed else 0
        theme_allocation.append(
            {
                "theme": theme,
                "theme_label": THEME_LABELS.get(theme, THEME_LABELS["other"]),
                "value_krw": round(value),
                "allocation_pct": round(allocation_pct, 2),
            }
        )

    return {
        "total_seed_krw": round(total_seed),
        "ten_percent_seed_krw": round(total_seed * 0.1),
        "cash_krw": round(cash_krw),
        "cash_ratio_pct": round(cash_krw / total_seed * 100, 2) if total_seed else 0,
        "theme_allocation": theme_allocation,
        "position_values": position_values,
        "crypto_values": crypto_values,
    }


def to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
