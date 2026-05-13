from __future__ import annotations

import os

from agents import AsyncOpenAI, set_default_openai_api, set_default_openai_client

from web_service.backend.rebalance_agent.llm_provider import DEFAULT_GEMINI_MODEL, GEMINI_OPENAI_BASE_URL


def configure_agent_model_provider() -> str:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return os.environ.get("AGENT_MODEL", "gpt-4o")

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        set_default_openai_client(
            AsyncOpenAI(api_key=gemini_key, base_url=GEMINI_OPENAI_BASE_URL),
            use_for_tracing=False,
        )
        set_default_openai_api("chat_completions")
        return os.environ.get("AGENT_MODEL", os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))

    return os.environ.get("AGENT_MODEL", "gpt-4o")
