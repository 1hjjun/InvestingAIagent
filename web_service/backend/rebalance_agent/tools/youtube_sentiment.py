# youtube-transcript-api와 LLM으로 영상 전체 자막을 요약·판단하는 Tool
from __future__ import annotations

import json
import os
import re
from typing import Any

from agents import function_tool

from web_service.backend.rebalance_agent.logger import guardrail_state, tool_result_recorder
from web_service.backend.rebalance_agent.llm_provider import DEFAULT_GEMINI_MODEL, chat_json, select_llm_provider
from web_service.backend.rebalance_agent.mocks.fixtures import YOUTUBE_SENTIMENTS
from web_service.backend.rebalance_agent.tool_cache import read_cache, write_cache


_MAX_LLM_TRANSCRIPT_CHARS = 60_000
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _allow_mock_fallback() -> bool:
    return os.environ.get("ALLOW_MOCK_FALLBACK", "false").lower() in {"1", "true", "yes", "y"}


def _extract_video_id(video_ref: str) -> str | None:
    text = video_ref.strip()
    if _VIDEO_ID_RE.match(text):
        return text

    patterns = [
        r"(?:youtube\.com/watch\?[^ ]*v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _fetch_transcript(video_ref: str) -> dict[str, Any]:
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

    video_id = _extract_video_id(video_ref)
    if not video_id:
        raise ValueError("youtube-transcript-api는 키워드 검색을 지원하지 않습니다. YouTube 영상 URL 또는 video_id가 필요합니다.")

    transcript = YouTubeTranscriptApi().fetch(video_id, languages=["ko", "en"])
    snippets = []
    for item in transcript:
        text = getattr(item, "text", None)
        if text is None and isinstance(item, dict):
            text = item.get("text")
        if text:
            snippets.append(text)
    full_text = " ".join(snippets)
    if not full_text:
        raise ValueError(f"{video_id} 영상에서 자막 텍스트를 찾지 못했습니다.")

    return {"video_id": video_id, "transcript": full_text, "transcript_char_count": len(full_text)}


def _coerce_lines(value: Any, target_count: int) -> list[str]:
    if isinstance(value, list):
        lines = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        lines = [line.strip("-• 0123456789.").strip() for line in value.splitlines() if line.strip()]
    else:
        lines = []

    lines = lines[:target_count]
    while len(lines) < target_count:
        lines.append("자막 내용만으로는 추가 근거를 충분히 확정하기 어렵습니다.")
    return lines


def _summarize_transcript_with_llm(transcript: str, video_id: str) -> dict[str, Any]:
    provider = select_llm_provider(
        openai_model=os.environ.get("YOUTUBE_SUMMARY_MODEL", "gpt-4o-mini"),
        gemini_model=os.environ.get("GEMINI_YOUTUBE_SUMMARY_MODEL", os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)),
        model_env="YOUTUBE_SUMMARY_MODEL",
    )
    if provider is None:
        raise ValueError("OPENAI_API_KEY or GEMINI_API_KEY not set")

    transcript_for_llm = transcript[:_MAX_LLM_TRANSCRIPT_CHARS]
    parsed = chat_json(
        provider,
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze YouTube transcripts for an ETF rebalancing assistant. "
                    "Read the transcript as a whole, avoid keyword-count sentiment shortcuts, "
                    "and return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"video_id: {video_id}\n\n"
                    "아래 자막 전체를 읽고 한국어로 답하세요.\n"
                    "반드시 JSON object만 반환하세요.\n"
                    "schema: {\"summary_lines\": [정확히 10개 문자열], "
                    "\"judgment_lines\": [정확히 5개 문자열]}\n"
                    "summary_lines는 영상의 핵심 내용을 흐름이 보이게 10줄로 요약하세요.\n"
                    "judgment_lines는 투자자가 이 영상을 어떻게 해석해야 하는지 5줄로 판단하세요.\n\n"
                    f"TRANSCRIPT:\n{transcript_for_llm}"
                ),
            },
        ],
        max_tokens=1200,
    )
    return {
        "summary_lines": _coerce_lines(parsed.get("summary_lines"), 10),
        "judgment_lines": _coerce_lines(parsed.get("judgment_lines"), 5),
        "transcript_chars_used": len(transcript_for_llm),
    }


def _analyze_video_transcript(video_ref: str) -> dict[str, Any]:
    transcript_result = _fetch_transcript(video_ref)
    analysis = _summarize_transcript_with_llm(
        transcript_result["transcript"],
        transcript_result["video_id"],
    )
    return {
        "video_id": transcript_result["video_id"],
        "transcript_char_count": transcript_result["transcript_char_count"],
        **analysis,
    }


def _do_youtube_sentiment(keyword: str) -> dict[str, Any]:
    inputs = {"keyword": keyword}
    guardrail_state.record_tool_call("youtube_sentiment", inputs)

    video_id = _extract_video_id(keyword)
    if video_id:
        cached = read_cache("youtube_sentiment", video_id)
        if cached:
            output = {
                "ok": True,
                "data": {"keyword": keyword, **cached},
                "error": None,
                "source": "cache",
                "fallback_used": False,
                "fallback_reason": None,
                "original_error": None,
            }
            return tool_result_recorder.record("youtube_sentiment", {**inputs, "cache_key": video_id}, output)

    try:
        result = _analyze_video_transcript(keyword)
        output = {
            "ok": True,
            "data": {"keyword": keyword, **result},
            "error": None,
            "source": "api",
            "fallback_used": False,
            "fallback_reason": None,
            "original_error": None,
        }
        write_cache("youtube_sentiment", result["video_id"], result)
        return tool_result_recorder.record("youtube_sentiment", inputs, output)
    except Exception as exc:
        mock = _lookup_mock(keyword)
        if _allow_mock_fallback():
            output = {
                "ok": True,
                "data": {"keyword": keyword, **mock},
                "error": None,
                "source": "mock",
                "fallback_used": True,
                "fallback_reason": type(exc).__name__,
                "original_error": {"code": type(exc).__name__, "message": str(exc)},
            }
            return tool_result_recorder.record("youtube_sentiment", inputs, output)
        output = {
            "ok": False,
            "data": None,
            "error": {"code": "TRANSCRIPT_UNAVAILABLE", "message": str(exc)},
            "source": "api",
            "fallback_used": False,
            "fallback_reason": type(exc).__name__,
            "original_error": {"code": type(exc).__name__, "message": str(exc)},
        }
        return tool_result_recorder.record("youtube_sentiment", inputs, output)


def _mock_analysis(summary: str) -> dict[str, list[str]]:
    return {
        "summary_lines": [
            summary,
            "외부 자막 또는 LLM 요약을 사용할 수 없어 사전 정의된 보조 데이터를 사용했습니다.",
            "영상의 전체 논리 전개와 세부 근거는 이 mock 결과에 포함되지 않습니다.",
            "실제 실행에서는 transcript_char_count와 transcript_chars_used를 함께 확인해야 합니다.",
            "이 값은 테스트와 fallback 동작 확인용입니다.",
            "요약 줄 수는 실제 LLM 결과와 같은 10줄 형식을 맞추기 위해 채워졌습니다.",
            "mock 데이터는 키워드 단위의 짧은 문장만 포함합니다.",
            "영상의 발언 순서, 뉘앙스, 조건부 판단은 반영되지 않을 수 있습니다.",
            "외부 의존성 실패 원인은 original_error에서 확인해야 합니다.",
            "실사용 판단은 반드시 api source 결과를 우선해야 합니다.",
        ],
        "judgment_lines": [
            "이 결과는 실제 영상 이해가 아니라 fallback입니다.",
            "ALLOW_MOCK_FALLBACK=false 환경에서 다시 실행하는 편이 안전합니다.",
            "mock 판단을 근거로 리밸런싱 결정을 내리면 안 됩니다.",
            "영상 전체 맥락을 반영하지 못하므로 보조 신호로만 취급해야 합니다.",
            "실제 투자 판단 전 YouTube 자막과 LLM 판단 결과를 재확인해야 합니다.",
        ],
    }


def _lookup_mock(keyword: str) -> dict[str, list[str]]:
    # 정확 일치 먼저, 없으면 부분 일치
    if keyword in YOUTUBE_SENTIMENTS:
        return _mock_analysis(YOUTUBE_SENTIMENTS[keyword]["summary"])
    lower = keyword.lower()
    for k, v in YOUTUBE_SENTIMENTS.items():
        if k.lower() in lower or lower in k.lower():
            return _mock_analysis(v["summary"])
    return _mock_analysis("관련 mock 데이터가 없어 영상 전체 요약을 생성하지 못했습니다.")


@function_tool(strict_mode=False)
def youtube_sentiment(keyword: str) -> dict[str, Any]:
    """YouTube 영상 전체 자막을 LLM으로 요약하고 투자 해석을 반환한다.

    keyword: YouTube 영상 URL 또는 11자리 video_id. 키워드 검색은 지원하지 않는다.
    """
    return _do_youtube_sentiment(keyword)
