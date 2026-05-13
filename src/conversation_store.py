from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "app" / "conversations.sqlite3"
DEFAULT_USER_ID = "default"
DEFAULT_CONVERSATION_ID = "rebalance-agent"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_schema(connection)
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            trace_id TEXT,
            image_name TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        """
    )
    connection.commit()


def ensure_default_conversation() -> None:
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO conversations (id, user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (DEFAULT_CONVERSATION_ID, DEFAULT_USER_ID, "리밸런싱 AI agent", now, now),
        )
        connection.commit()


def list_messages(
    conversation_id: str = DEFAULT_CONVERSATION_ID,
    limit: int = 80,
) -> list[dict[str, Any]]:
    ensure_default_conversation()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, role, content, trace_id, image_name, image_path, created_at
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

    return [message_from_row(row) for row in reversed(rows)]


def add_message(
    role: str,
    content: str,
    *,
    conversation_id: str = DEFAULT_CONVERSATION_ID,
    trace_id: str | None = None,
    image_name: str | None = None,
    image_path: str | None = None,
) -> dict[str, Any]:
    ensure_default_conversation()
    now = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO conversation_messages
                (conversation_id, role, content, trace_id, image_name, image_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (conversation_id, role, content, trace_id, image_name, image_path, now),
        )
        connection.execute(
            """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
            """,
            (now, conversation_id),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, role, content, trace_id, image_name, image_path, created_at
            FROM conversation_messages
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return message_from_row(row)


def clear_messages(conversation_id: str = DEFAULT_CONVERSATION_ID) -> None:
    ensure_default_conversation()
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM conversation_messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        connection.commit()


def message_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "role": row["role"],
        "content": row["content"],
        "trace_id": row["trace_id"],
        "image_name": row["image_name"],
        "image_path": row["image_path"],
        "created_at": row["created_at"],
    }


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
