# 매매 일지를 로컬 JSON 파일에 읽고 쓰는 Tool
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from agents import function_tool

from web_service.backend.rebalance_agent.logger import guardrail_state, tool_result_recorder


_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_JOURNAL_PATH = _DATA_DIR / "journal.json"
_SEED_PATH = _DATA_DIR / "journal.seed.json"


def _ensure_journal() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _JOURNAL_PATH.exists():
        import shutil
        shutil.copy(_SEED_PATH, _JOURNAL_PATH)
    return _JOURNAL_PATH


def _read_all(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_all(path: Path, entries: list[dict[str, Any]]) -> None:
    tmp_fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _do_journal(
    mode: Literal["read", "write"],
    date: str | None = None,
    keywords: list[str] | None = None,
    entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inputs = {"mode": mode, "date": date, "keywords": keywords, "entry": entry}
    guardrail_state.record_tool_call("journal_db", {"mode": mode, "date": date})

    path = _ensure_journal()

    if mode == "read":
        entries = _read_all(path)
        results = entries
        if date:
            results = [e for e in results if e.get("date", "") == date]
        if keywords:
            def matches(e: dict[str, Any]) -> bool:
                text = " ".join([
                    e.get("reason", ""),
                    e.get("memo", ""),
                    " ".join(e.get("tags", [])),
                    e.get("ticker", ""),
                ]).lower()
                return any(k.lower() in text for k in keywords)
            results = [e for e in results if matches(e)]
        result = {
            "ok": True,
            "data": {"entries": results, "count": len(results)},
            "error": None,
            "source": "local",
            "fallback_used": False,
            "fallback_reason": None,
            "original_error": None,
        }
        return tool_result_recorder.record("journal_db", inputs, result)

    if mode == "write":
        if not entry:
            result = {
                "ok": False,
                "data": None,
                "error": {"code": "MISSING_ENTRY", "message": "write 모드에 entry가 없습니다."},
                "source": "local",
                "fallback_used": False,
                "fallback_reason": None,
                "original_error": None,
            }
            return tool_result_recorder.record("journal_db", inputs, result)
        entries = _read_all(path)
        new_entry = {
            "id": f"j{len(entries) + 1:03d}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            **entry,
        }
        entries.append(new_entry)
        _write_all(path, entries)
        result = {
            "ok": True,
            "data": {"saved_entry": new_entry},
            "error": None,
            "source": "local",
            "fallback_used": False,
            "fallback_reason": None,
            "original_error": None,
        }
        return tool_result_recorder.record("journal_db", inputs, result)

    result = {
        "ok": False,
        "data": None,
        "error": {"code": "INVALID_MODE", "message": f"지원하지 않는 mode: {mode}"},
        "source": "local",
        "fallback_used": False,
        "fallback_reason": None,
        "original_error": None,
    }
    return tool_result_recorder.record("journal_db", inputs, result)


@function_tool(strict_mode=False)
def journal_db(
    mode: str,
    date: str | None = None,
    keywords: list[str] | None = None,
    entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """매매 일지 DB를 읽거나 씁니다.

    mode: "read" | "write"
    date: (read) YYYY-MM-DD 형식 날짜 필터
    keywords: (read) 텍스트 검색 키워드 목록
    entry: (write) 저장할 일지 데이터 dict
    """
    return _do_journal(mode=mode, date=date, keywords=keywords, entry=entry)  # type: ignore[arg-type]
