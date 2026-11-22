from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
import aiosqlite
from config import DB_PATH

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TEXT NOT NULL
);
"""

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    target_date TEXT NOT NULL,
    target_time TEXT,
    target_datetime TEXT NOT NULL,
    has_time INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 0,
    notified_final INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);
"""

CREATE_INDEX_EVENTS = """
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, is_completed);
CREATE INDEX IF NOT EXISTS idx_events_due ON events(target_datetime, notified_final);
"""


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    async with get_db() as conn:
        await conn.execute(CREATE_USERS_TABLE)
        await conn.execute(CREATE_EVENTS_TABLE)
        await conn.executescript(CREATE_INDEX_EVENTS)
        await conn.commit()


async def add_or_update_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    now_iso = datetime.now().isoformat()
    query = """
    INSERT INTO users (telegram_id, username, first_name, created_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(telegram_id) DO UPDATE SET
        username = excluded.username,
        first_name = excluded.first_name;
    """
    async with get_db() as conn:
        await conn.execute(query, (telegram_id, username or "", first_name or "", now_iso))
        await conn.commit()


def compute_target_datetime(target_date: str, target_time: Optional[str], has_time: bool) -> str:
    cleaned_date = target_date.strip()
    if has_time and target_time and target_time.strip():
        cleaned_time = target_time.strip()
        if len(cleaned_time) == 5:
            cleaned_time += ":00"
        return f"{cleaned_date}T{cleaned_time}"
    return f"{cleaned_date}T23:59:59"


async def create_event(
    user_id: int,
    title: str,
    target_date: str,
    target_time: Optional[str] = None,
    has_time: bool = False
) -> Dict[str, Any]:
    now_iso = datetime.now().isoformat()
    target_dt_iso = compute_target_datetime(target_date, target_time, has_time)
    has_time_int = 1 if has_time else 0

    query = """
    INSERT INTO events (
        user_id, title, target_date, target_time, target_datetime,
        has_time, created_at, is_completed, notified_final
    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0);
    """
    async with get_db() as conn:
        cursor = await conn.execute(
            query,
            (user_id, title.strip(), target_date.strip(), (target_time or "").strip(), target_dt_iso, has_time_int, now_iso)
        )
        await conn.commit()
        event_id = cursor.lastrowid

    event = await get_event_by_id(event_id, user_id)
    return event or {}


async def get_user_events(user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    query = "SELECT * FROM events WHERE user_id = ?"
    params: List[Any] = [user_id]
    if active_only:
        query += " AND is_completed = 0"
    query += " ORDER BY target_datetime ASC"

    async with get_db() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_event_by_id(event_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    query = "SELECT * FROM events WHERE id = ?"
    params: List[Any] = [event_id]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    async with get_db() as conn:
        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_event(
    event_id: int,
    user_id: int,
    title: str,
    target_date: str,
    target_time: Optional[str] = None,
    has_time: bool = False
) -> Optional[Dict[str, Any]]:
    target_dt_iso = compute_target_datetime(target_date, target_time, has_time)
    has_time_int = 1 if has_time else 0

    query = """
    UPDATE events
    SET title = ?,
        target_date = ?,
        target_time = ?,
        target_datetime = ?,
        has_time = ?
    WHERE id = ? AND user_id = ?;
    """
    async with get_db() as conn:
        cursor = await conn.execute(
            query,
            (title.strip(), target_date.strip(), (target_time or "").strip(), target_dt_iso, has_time_int, event_id, user_id)
        )
        await conn.commit()
        if cursor.rowcount == 0:
            return None

    return await get_event_by_id(event_id, user_id)


async def delete_event(event_id: int, user_id: int) -> bool:
    query = "DELETE FROM events WHERE id = ? AND user_id = ?;"
    async with get_db() as conn:
        cursor = await conn.execute(query, (event_id, user_id))
        await conn.commit()
        return cursor.rowcount > 0


async def get_all_active_events_for_digest() -> List[Dict[str, Any]]:
    query = """
    SELECT e.*, u.first_name, u.username
    FROM events e
    JOIN users u ON u.telegram_id = e.user_id
    WHERE e.is_completed = 0
    ORDER BY e.user_id, e.target_datetime ASC;
    """
    async with get_db() as conn:
        cursor = await conn.execute(query)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_due_events(current_iso: str) -> List[Dict[str, Any]]:
    query = """
    SELECT * FROM events
    WHERE is_completed = 0
      AND notified_final = 0
      AND target_datetime <= ?;
    """
    async with get_db() as conn:
        cursor = await conn.execute(query, (current_iso,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_event_completed(event_id: int) -> None:
    query = "UPDATE events SET is_completed = 1, notified_final = 1 WHERE id = ?;"
    async with get_db() as conn:
        await conn.execute(query, (event_id,))
        await conn.commit()
