from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"
MEMORY_PATH = MEMORY_DIR / "conversation_summary.json"
JOURNAL_PATH = MEMORY_DIR / "daily_journals.json"

DEFAULT_MEMORY: dict[str, Any] = {
    "summary": "아직 축적된 대화 메모리가 없습니다.",
    "updated_at": "",
}


def ensure_memory_file() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_PATH.exists():
        save_memory(DEFAULT_MEMORY)
    if not JOURNAL_PATH.exists():
        save_daily_journals([])


def load_memory() -> dict[str, Any]:
    ensure_memory_file()
    with MEMORY_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_memory(memory: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=MEMORY_PATH.parent,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(memory, temp_file, ensure_ascii=False, indent=2)
        temp_file.write("\n")
    temp_path.replace(MEMORY_PATH)


def load_daily_journals() -> list[dict[str, Any]]:
    ensure_memory_file()
    with JOURNAL_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, list):
        return data
    return []


def save_daily_journals(journals: list[dict[str, Any]]) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=JOURNAL_PATH.parent,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(journals, temp_file, ensure_ascii=False, indent=2)
        temp_file.write("\n")
    temp_path.replace(JOURNAL_PATH)


def update_memory(user_question: str, assistant_answer: str) -> dict[str, Any]:
    memory = load_memory()
    old_summary = memory.get("summary", "")
    if old_summary == DEFAULT_MEMORY["summary"]:
        old_summary = ""

    answer_brief = " ".join(assistant_answer.split())[:500]
    question_brief = " ".join(user_question.split())[:240]
    new_line = f"- 사용자는 '{question_brief}'에 대해 물었고, 답변은 '{answer_brief}' 흐름으로 제공했다."
    lines = [line for line in old_summary.splitlines() if line.strip()]
    lines.append(new_line)
    lines = lines[-12:]

    updated = {
        "summary": "\n".join(lines) if lines else DEFAULT_MEMORY["summary"],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_memory(updated)
    update_daily_journal(user_question, assistant_answer)
    return updated


def update_daily_journal(user_question: str, assistant_answer: str) -> dict[str, Any]:
    journals = load_daily_journals()
    now = datetime.now()
    today = now.date().isoformat()
    question_brief = compact_text(user_question, limit=180)
    answer_brief = compact_text(assistant_answer, limit=700)
    journal = next((item for item in journals if item.get("date") == today), None)

    if journal is None:
        journal = {
            "date": today,
            "title": make_journal_title(question_brief),
            "subtitle": "오늘 나눈 투자 대화의 흐름을 글처럼 정리한 노트",
            "conversation_count": 0,
            "questions": [],
            "key_takeaways": [],
            "article": "",
            "updated_at": "",
        }
        journals.insert(0, journal)

    journal["conversation_count"] = int(journal.get("conversation_count", 0)) + 1
    journal["questions"].append(question_brief)
    journal["questions"] = journal["questions"][-8:]
    journal["key_takeaways"].append(answer_brief)
    journal["key_takeaways"] = journal["key_takeaways"][-5:]
    journal["title"] = make_journal_title(journal["questions"][0])
    journal["article"] = build_journal_article(journal)
    journal["updated_at"] = now.isoformat(timespec="seconds")
    save_daily_journals(journals[:60])
    return journal


def build_journal_article(journal: dict[str, Any]) -> str:
    questions = journal.get("questions", [])
    takeaways = journal.get("key_takeaways", [])
    date = journal.get("date", "")

    question_lines = "\n".join(f"- {question}" for question in questions)
    takeaway_lines = "\n\n".join(
        f"### 장면 {index}\n{takeaway}"
        for index, takeaway in enumerate(takeaways, start=1)
    )
    return f"""# {journal.get("title", "투자 대화 노트")}

{date}의 대화는 아래 질문들에서 출발했다. 오늘의 흐름은 단순히 답을 찾는 것보다, 보유 포트폴리오와 시장 정보를 연결해서 투자 판단의 재료를 정리하는 데 가까웠다.

## 오늘의 질문
{question_lines}

## 대화에서 남긴 핵심 장면
{takeaway_lines}

## 오늘의 정리
오늘 대화의 핵심은 자료에서 확인되는 근거와 내 포트폴리오의 현재 위치를 함께 놓고 보는 것이었다. 단일 종목의 좋고 나쁨보다, 어떤 테마에 이미 노출되어 있고 어떤 리스크가 겹치는지 확인하는 쪽으로 관점이 이동했다.

## 다음에 이어볼 질문
- 이 판단이 내 전체 시드의 10% 기준금액과 비교했을 때 너무 큰 결정인지 확인하기
- 같은 테마 안에서 중복 노출이 심한 종목이 있는지 점검하기
- 확인된 자료와 AI의 해석이 섞이지 않았는지 다시 분리하기
"""


def make_journal_title(question: str) -> str:
    if not question:
        return "투자 대화 노트"
    title = question.strip().replace("\n", " ")
    return title[:34] + ("..." if len(title) > 34 else "")


def compact_text(text: str, limit: int) -> str:
    compacted = " ".join(str(text).split())
    if len(compacted) <= limit:
        return compacted
    return compacted[:limit].rstrip() + "..."
