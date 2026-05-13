# Tool 결과 캐시를 JSON 파일로 읽고 쓰는 유틸리티
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


def read_cache(namespace: str, key: str) -> dict[str, Any] | None:
    path = _cache_path(namespace, key)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_cache(namespace: str, key: str, value: dict[str, Any]) -> None:
    path = _cache_path(namespace, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=str)


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_path(namespace: str, key: str) -> Path:
    safe_key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in key)
    return CACHE_DIR / namespace / f"{safe_key}.json"
