from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class LLMProvider:
    name: str
    api_key: str
    model: str
    base_url: str | None = None


def select_llm_provider(
    openai_model: str,
    gemini_model: str | None = None,
    model_env: str | None = None,
) -> LLMProvider | None:
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if openai_key:
        return LLMProvider(
            name="openai",
            api_key=openai_key,
            model=os.environ.get(model_env, openai_model) if model_env else openai_model,
        )
    if gemini_key:
        return LLMProvider(
            name="gemini",
            api_key=gemini_key,
            model=gemini_model or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            base_url=GEMINI_OPENAI_BASE_URL,
        )
    return None


def make_openai_compatible_client(provider: LLMProvider):
    from openai import OpenAI

    if provider.base_url:
        return OpenAI(api_key=provider.api_key, base_url=provider.base_url)
    return OpenAI(api_key=provider.api_key)


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM did not return a JSON object")
    return parsed


def chat_json(provider: LLMProvider, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
    client = make_openai_compatible_client(provider)
    response = client.chat.completions.create(
        model=provider.model,
        messages=messages,
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    )
    return extract_json_object(response.choices[0].message.content or "{}")
