from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = PROJECT_ROOT / "data" / "user_profile"
PROFILE_PATH = PROFILE_DIR / "profile.json"
PORTFOLIO_PATH = PROFILE_DIR / "portfolio.json"

DEFAULT_PROFILE: dict[str, Any] = {
    "investment_style": "long_term",
    "risk_tolerance": "moderate",
    "preferred_assets": ["QQQ", "SCHD", "SOXX"],
    "interests": ["AI", "semiconductor", "US ETF"],
    "base_currency": "KRW",
    "notes": "사용자는 장기투자 성향이며 미국 ETF 중심의 포트폴리오를 선호한다.",
}

DEFAULT_PORTFOLIO: dict[str, Any] = {
    "cash_ratio": 20,
    "positions": [
        {
            "ticker": "QQQ",
            "asset_type": "ETF",
            "target_role": "growth_core",
            "weight": 40,
            "notes": "성장 코어",
        },
        {
            "ticker": "SCHD",
            "asset_type": "ETF",
            "target_role": "dividend_defensive",
            "weight": 25,
            "notes": "배당/방어",
        },
        {
            "ticker": "SOXX",
            "asset_type": "ETF",
            "target_role": "semiconductor_tilt",
            "weight": 15,
            "notes": "반도체 비중",
        },
    ],
}


def ensure_profile_files() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        save_json(PROFILE_PATH, DEFAULT_PROFILE)
    if not PORTFOLIO_PATH.exists():
        save_json(PORTFOLIO_PATH, DEFAULT_PORTFOLIO)


def load_profile() -> dict[str, Any]:
    ensure_profile_files()
    return read_json(PROFILE_PATH)


def save_profile(profile: dict[str, Any]) -> None:
    save_json(PROFILE_PATH, profile)


def load_portfolio() -> dict[str, Any]:
    ensure_profile_files()
    return read_json(PORTFOLIO_PATH)


def save_portfolio(portfolio: dict[str, Any]) -> None:
    save_json(PORTFOLIO_PATH, portfolio)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(data, temp_file, ensure_ascii=False, indent=2)
        temp_file.write("\n")
    temp_path.replace(path)
