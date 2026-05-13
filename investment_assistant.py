from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

from src.memory_store import load_memory, update_memory
from src.profile_store import load_portfolio, load_profile
from src.prompt_builder import (
    build_answer_option_prompt,
    build_personal_context,
    load_system_prompt,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks" / "chunks.jsonl"
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma_db"

ANSWER_STYLE_PROMPTS = {
    "자료 엄격 모드": """답변 스타일: 자료 엄격 모드
- 제공된 참고자료 안에서 확인되는 내용만 답변한다.
- 자료에 없는 해석, 예시, 확장 아이디어는 말하지 않는다.
- 불확실하면 근거가 부족하다고 말한다.""",
    "해석/코칭 모드": """답변 스타일: 해석/코칭 모드
- 제공된 참고자료를 핵심 근거로 삼는다.
- 사용자가 이해하고 적용할 수 있도록 구조화, 비교, 체크리스트, 단계별 설명을 만들 수 있다.
- 단, 자료에 없는 사실을 사실처럼 말하지 않는다.
- 자료 기반 내용과 네 해석을 자연스럽게 구분한다.""",
    "아이디어 확장 모드": """답변 스타일: 아이디어 확장 모드
- 참고자료를 기반으로 가능한 응용 아이디어, 점검 질문, 시나리오, 학습 방향을 제안할 수 있다.
- 반드시 '자료에서 확인된 내용'과 'AI의 추가 아이디어'를 구분한다.
- 자료 밖의 내용은 가능성/아이디어로만 표현하고 사실처럼 단정하지 않는다.
- 매수/매도 지시는 하지 않는다.""",
}

IMAGE_REVIEW_PROMPT = """아래 질문에 답하기 위해 검색된 원본 투자자료 이미지를 확인합니다.
이미지에서 질문과 관련 있는 차트, 표, 수치, 종목명, 날짜, 축, 범례, 강조 표시만 보강하세요.
보이지 않는 내용은 추측하지 마세요.
투자 조언은 하지 말고, 자료에서 확인되는 사실만 정리하세요.
"""


def load_settings() -> dict[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError(".env에 OPENAI_API_KEY를 입력하세요.")

    return {
        "api_key": api_key,
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "answer_model": os.getenv("OPENAI_ANSWER_MODEL", "gpt-5.4"),
        "vision_model": os.getenv("OPENAI_ON_DEMAND_VISION_MODEL", "gpt-5.4"),
        "collection_name": os.getenv("CHROMA_COLLECTION_NAME", "investment_pdf_chunks"),
    }


def get_openai_client() -> OpenAI:
    settings = load_settings()
    return OpenAI(api_key=settings["api_key"])


def get_collection() -> chromadb.Collection:
    settings = load_settings()
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(name=settings["collection_name"])


def image_to_data_url(path: Path) -> str:
    with Image.open(path) as image:
        image.verify()

    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }[path.suffix.lower()]
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def embed_texts(client: OpenAI, texts: list[str], model: str) -> list[list[float]]:
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def query_chunks(question: str, top_k: int = 5) -> list[dict[str, Any]]:
    settings = load_settings()
    client = get_openai_client()
    collection = get_collection()
    query_embedding = embed_texts(client, [question], settings["embedding_model"])[0]
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    vector_chunks: list[dict[str, Any]] = []
    for index, chunk_id in enumerate(result.get("ids", [[]])[0]):
        metadata = result.get("metadatas", [[]])[0][index] or {}
        vector_chunks.append(
            {
                "chunk_id": chunk_id,
                "text": result.get("documents", [[]])[0][index],
                "metadata": metadata,
                "distance": result.get("distances", [[]])[0][index],
            }
        )

    lexical_chunks = query_chunks_by_topic_name(question)
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for chunk in lexical_chunks + vector_chunks:
        if chunk["chunk_id"] in seen_ids:
            continue
        merged.append(chunk)
        seen_ids.add(chunk["chunk_id"])
        if len(merged) >= top_k:
            break
    return merged


def query_chunks_by_topic_name(question: str) -> list[dict[str, Any]]:
    normalized_question = recompact(question)
    matches = []
    for chunk in read_jsonl(CHUNKS_PATH):
        topic = str(chunk.get("topic", ""))
        section = str(chunk.get("section", ""))
        normalized_topic = recompact(topic)
        normalized_section = recompact(section)
        if not normalized_topic:
            continue

        score = 0
        if normalized_topic and normalized_topic in normalized_question:
            score += 100
        if normalized_section and normalized_section in normalized_question:
            score += 20
        for token in normalized_topic.split("_"):
            if len(token) >= 2 and token in normalized_question:
                score += 3

        if score:
            matches.append((score, chunk))

    matches.sort(key=lambda item: (-item[0], item[1].get("page_start", item[1].get("page", 0))))
    return [
        {
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "metadata": {
                "page": chunk.get("page"),
                "page_start": chunk.get("page_start", chunk.get("page")),
                "page_end": chunk.get("page_end", chunk.get("page")),
                "pages": chunk.get("pages", str(chunk.get("page", ""))),
                "source_path": chunk.get("source_path"),
                "source_paths": chunk.get("source_paths", chunk.get("source_path", "")),
                "section": chunk.get("section", ""),
                "topic": chunk.get("topic", ""),
                "topic_path": chunk.get("topic_path", ""),
                "chunk_type": chunk.get("chunk_type", "topic_summary"),
                "visual_review_needed": chunk.get("visual_review_needed", False),
            },
            "distance": None,
        }
        for _, chunk in matches
    ]


def recompact(text: str) -> str:
    return "".join(str(text).lower().split())


def should_review_image(chunk: dict[str, Any]) -> bool:
    metadata = chunk.get("metadata", {})
    if metadata.get("visual_review_needed") in (True, "true", "True", 1, "1"):
        return True

    text = chunk.get("text", "")
    visual_keywords = [
        "차트",
        "그래프",
        "표",
        "캔들",
        "거래량",
        "이동평균",
        "HTS",
        "TradingView",
        "증권앱",
        "종목 리스트",
        "축",
        "범례",
    ]
    return any(keyword in text for keyword in visual_keywords)


def review_source_images(
    question: str,
    chunks: list[dict[str, Any]],
    max_images: int = 2,
) -> str:
    selected: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for chunk in chunks:
        if chunk.get("metadata", {}).get("chunk_type") == "topic_summary":
            continue
        source_path = str(chunk.get("metadata", {}).get("source_path", ""))
        if not source_path or source_path in seen_paths:
            continue
        if should_review_image(chunk):
            selected.append(chunk)
            seen_paths.add(source_path)
        if len(selected) >= max_images:
            break

    if not selected:
        return ""

    settings = load_settings()
    client = get_openai_client()
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": f"{IMAGE_REVIEW_PROMPT}\n\n질문: {question}",
        }
    ]

    for chunk in selected:
        metadata = chunk["metadata"]
        source_path = str(metadata["source_path"])
        image_path = PROJECT_ROOT / source_path
        if not image_path.exists():
            continue
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"\n참고 이미지: page {metadata.get('page')} / {source_path}\n"
                    f"1차 OCR 요약:\n{chunk.get('text', '')[:1800]}"
                ),
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(image_path),
                "detail": "high",
            }
        )

    if len(content) == 1:
        return ""

    response = client.responses.create(
        model=settings["vision_model"],
        input=[{"role": "user", "content": content}],
    )
    return response.output_text.strip()


def format_context(chunks: list[dict[str, Any]]) -> str:
    blocks = []
    for number, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]
        chunk_type = metadata.get("chunk_type", "detail")
        page_label = metadata.get("pages") if chunk_type == "topic_summary" else metadata.get("page")
        source_label = (
            metadata.get("source_paths")
            if chunk_type == "topic_summary"
            else metadata.get("source_path")
        )
        blocks.append(
            "\n".join(
                [
                    f"[참고자료 {number}]",
                    f"type: {chunk_type}",
                    f"page: {page_label}",
                    f"section: {metadata.get('section', '')}",
                    f"topic: {metadata.get('topic', '')}",
                    f"source_path: {source_label}",
                    f"text:\n{chunk.get('text', '')}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def answer_question(
    question: str,
    top_k: int = 5,
    use_vision: bool = False,
    max_images: int = 2,
    conversation_history: list[dict[str, str]] | None = None,
    answer_style: str = "해석/코칭 모드",
    pdf_only: bool = False,
    include_portfolio: bool = True,
    conservative_view: bool = False,
) -> dict[str, Any]:
    chunks = query_chunks(question, top_k=top_k)
    if not chunks:
        return {
            "answer": "검색된 참고자료가 없습니다. 먼저 벡터 DB를 생성했는지 확인해 주세요.",
            "chunks": [],
            "image_review": "",
        }

    image_review = review_source_images(question, chunks, max_images=max_images) if use_vision else ""
    settings = load_settings()
    client = get_openai_client()
    profile = load_profile()
    portfolio = load_portfolio()
    memory = load_memory()
    context = format_context(chunks)
    image_context = f"\n\n[원본 이미지 재확인 결과]\n{image_review}" if image_review else ""
    style_prompt = ANSWER_STYLE_PROMPTS.get(answer_style, ANSWER_STYLE_PROMPTS["해석/코칭 모드"])
    personal_context = build_personal_context(
        profile=profile,
        portfolio=portfolio,
        memory=memory,
        include_portfolio=include_portfolio,
    )
    option_prompt = build_answer_option_prompt(
        pdf_only=pdf_only,
        include_portfolio=include_portfolio,
        conservative_view=conservative_view,
    )
    history_context = ""
    if conversation_history:
        recent_history = conversation_history[-6:]
        history_lines = []
        for message in recent_history:
            role = "사용자" if message.get("role") == "user" else "비서"
            content = str(message.get("content", "")).strip()
            if content:
                history_lines.append(f"{role}: {content[:1200]}")
        if history_lines:
            history_context = "\n\n[최근 대화 맥락]\n" + "\n\n".join(history_lines)

    user_prompt = f"""질문:
{question}
{history_context}

아래 사용자 정보와 대화 메모리를 참고하세요.
{personal_context}

아래 참고자료만 사용해서 답변하세요.
{context}
{image_context}

{style_prompt}
{option_prompt}

답변 형식:
## 핵심 요약
...

## PDF 근거
- p.00
  근거 요약:
  1. 참고자료에서 확인되는 핵심 내용을 최소 3줄로 요약합니다.
  2. 숫자, 시기, 조건, 비교 대상이 있으면 빠뜨리지 않습니다.
  3. 질문과 직접 연결되는 의미를 중심으로 정리합니다.
  해설:
  - 위 근거가 질문에 어떤 의미인지 2줄 정도로 설명합니다.
  - PDF 근거와 AI의 해석이 섞이지 않게 구분해서 씁니다.

## 포트폴리오 관점
...

## 긍정 시나리오
...

## 리스크 시나리오
...

## 내가 내릴 수 있는 결론 후보
1. ...
2. ...
3. ...

## 참고 페이지
p.00 / images/000.png

주의:
PDF 근거와 AI의 해석/아이디어를 구분하고, 매수/매도 지시는 하지 마세요.
"""

    response = client.responses.create(
        model=settings["answer_model"],
        input=[
            {"role": "system", "content": load_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
    )
    answer = response.output_text.strip()
    updated_memory = update_memory(question, answer)
    return {
        "answer": answer,
        "chunks": chunks,
        "image_review": image_review,
        "memory": updated_memory,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]
