"""SQLite-backed cache for Hacker News items."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Union, cast

from .models import Comment, Story, item_from_json


CachedItem = Union[Story, Comment]


class CacheManager:
    """Persist fetched Hacker News items in a local SQLite database."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else self.default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def default_db_path() -> Path:
        """Return the default cache database path."""

        return Path.home() / ".cache" / "hews" / "cache.db"

    def get_item(self, item_id: int) -> CachedItem | None:
        """Return a cached item by ID, or None if it is not cached."""

        with self._connect() as conn:
            row = conn.execute(
                "SELECT json FROM items WHERE id = ?",
                (item_id,),
            ).fetchone()

        if row is None:
            return None

        data = json.loads(cast(str, row["json"]))
        return item_from_json(data)

    def save_item(self, item: CachedItem) -> None:
        """Insert or update an item in the cache."""

        payload = json.dumps(item.to_dict(), separators=(",", ":"))
        fetched_at = int(time.time())

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO items (id, type, json, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    json = excluded.json,
                    fetched_at = excluded.fetched_at
                """,
                (item.id, item.type.value, payload, fetched_at),
            )

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    json TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_items_type
                ON items(type)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
