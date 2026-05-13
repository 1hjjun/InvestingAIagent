# gpt-4o multimodal로 포트폴리오 이미지에서 자산 목록을 추출하는 Tool
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from agents import function_tool

from web_service.backend.rebalance_agent.logger import guardrail_state, tool_result_recorder
from web_service.backend.rebalance_agent.llm_provider import DEFAULT_GEMINI_MODEL, LLMProvider, make_openai_compatible_client
from web_service.backend.rebalance_agent.mocks.fixtures import SAMPLE_ASSETS
from web_service.backend.rebalance_agent.tool_cache import file_sha256, read_cache, text_sha256, write_cache


_SYSTEM_PROMPT = (
    "You are a financial portfolio parser. "
    "Extract ALL asset positions from the provided image. "
    'Return a JSON object with key "assets" containing an array of all positions. '
    "Each item must have: ticker (string), asset_type (string: stock|etf|bond|cash|other), "
    "amount (number of shares/units), value (total holding market value in the account display currency), "
    "currency (string, e.g. KRW or USD), and unit_price when visible. "
    "For Korean brokerage tables, do not confuse the current unit price column with total holding value. "
    "If the table shows amount and current price but not evaluation amount, calculate value = amount * unit_price. "
    "Ticker text usually appears after a separator like '| QQQM'. "
    'Example: {"assets": [{"ticker": "QQQM", "asset_type": "etf", "amount": 14, "unit_price": 415755.0, "value": 5820570.0, "currency": "KRW"}]}'
)


def _allow_mock_fallback() -> bool:
    return os.environ.get("ALLOW_MOCK_FALLBACK", "false").lower() in {"1", "true", "yes", "y"}


def _failure_result(code: str, message: str, fallback_reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {"code": code, "message": message},
        "source": "api",
        "fallback_used": False,
        "fallback_reason": fallback_reason,
        "original_error": {"code": code, "message": message},
    }


def _mock_result(fallback_reason: str, code: str, message: str) -> dict[str, Any]:
    return {
        "ok": True,
        "data": {"assets": SAMPLE_ASSETS},
        "error": None,
        "source": "mock",
        "fallback_used": True,
        "fallback_reason": fallback_reason,
        "original_error": {"code": code, "message": message},
    }


def _image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    ext = path.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def _call_openai_vision(image_url: str, api_key: str) -> list[dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    if image_url.startswith(("http://", "https://")):
        content_part: dict[str, Any] = {"type": "image_url", "image_url": {"url": image_url}}
    else:
        data_url = _image_to_data_url(image_url)
        content_part = {"type": "image_url", "image_url": {"url": data_url}}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Parse this portfolio screenshot into positions. "
                            "Use only visible rows. For each row, extract the ticker, share quantity, "
                            "current unit price, and total holding market value."
                        ),
                    },
                    content_part,
                ],
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=1024,
    )
    raw = response.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return parsed
    # response_format=json_object는 항상 dict를 반환하므로 assets 키를 찾는다
    for key in ("assets", "positions", "holdings", "data"):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
    # 모델이 단일 자산 객체를 반환한 경우 리스트로 감싼다
    if "ticker" in parsed:
        return [parsed]
    return []


def _parse_assets_payload(raw: str) -> list[dict[str, Any]]:
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return parsed
    for key in ("assets", "positions", "holdings", "data"):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
    if isinstance(parsed, dict) and "ticker" in parsed:
        return [parsed]
    return []


def _call_gemini_vision(image_url: str, api_key: str) -> list[dict[str, Any]]:
    provider = LLMProvider(
        name="gemini",
        api_key=api_key,
        model=os.environ.get("GEMINI_VISION_MODEL", os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    client = make_openai_compatible_client(provider)
    if image_url.startswith(("http://", "https://")):
        content_part: dict[str, Any] = {"type": "image_url", "image_url": {"url": image_url}}
    else:
        content_part = {"type": "image_url", "image_url": {"url": _image_to_data_url(image_url)}}

    response = client.chat.completions.create(
        model=provider.model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Parse this portfolio screenshot into positions. "
                            "Use only visible rows and return only a JSON object with an assets array."
                        ),
                    },
                    content_part,
                ],
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=1024,
    )
    return _parse_assets_payload(response.choices[0].message.content or "{}")


def _do_vision_extractor(image_url: str) -> dict[str, Any]:
    inputs = {"image_url": image_url}
    guardrail_state.record_tool_call("vision_extractor", inputs)

    cache_key: str | None = None
    try:
        if image_url.startswith(("http://", "https://")):
            cache_key = text_sha256(image_url)
        else:
            cache_key = file_sha256(image_url)
        cached = read_cache("vision_extractor", cache_key)
        if cached:
            result = {**cached, "source": "cache", "fallback_used": False, "fallback_reason": None}
            return tool_result_recorder.record("vision_extractor", {**inputs, "cache_key": cache_key}, result)
    except Exception:
        cache_key = None

    api_key = os.environ.get("OPENAI_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key and not gemini_key:
        message = "OPENAI_API_KEY or GEMINI_API_KEY not set"
        if _allow_mock_fallback():
            result = _mock_result("MISSING_API_KEY", "MISSING_ENV", message)
            return tool_result_recorder.record("vision_extractor", inputs, result)
        result = _failure_result("MISSING_ENV", message, "MISSING_API_KEY")
        return tool_result_recorder.record("vision_extractor", inputs, result)

    try:
        assets = _call_openai_vision(image_url, api_key) if api_key else _call_gemini_vision(image_url, gemini_key)
        result = {
            "ok": True,
            "data": {"assets": assets},
            "error": None,
            "source": "api",
            "fallback_used": False,
            "fallback_reason": None,
            "original_error": None,
        }
        if cache_key:
            write_cache("vision_extractor", cache_key, result)
        return tool_result_recorder.record("vision_extractor", inputs, result)
    except json.JSONDecodeError as exc:
        if _allow_mock_fallback():
            result = _mock_result("JSON_PARSE_ERROR", "JSON_PARSE_ERROR", str(exc))
            return tool_result_recorder.record("vision_extractor", inputs, result)
        result = _failure_result("JSON_PARSE_ERROR", str(exc), "JSON_PARSE_ERROR")
        return tool_result_recorder.record("vision_extractor", inputs, result)
    except Exception as exc:
        code = type(exc).__name__
        if _allow_mock_fallback():
            result = _mock_result(code, code, str(exc))
            return tool_result_recorder.record("vision_extractor", inputs, result)
        result = _failure_result(code, str(exc), code)
        return tool_result_recorder.record("vision_extractor", inputs, result)


@function_tool(strict_mode=False)
def vision_extractor(image_url: str) -> dict[str, Any]:
    """포트폴리오 스크린샷에서 자산 목록을 추출한다.

    image_url: 로컬 파일 경로 또는 HTTP URL
    반환: assets=[{ticker, asset_type, amount, value}]
    """
    return _do_vision_extractor(image_url)
