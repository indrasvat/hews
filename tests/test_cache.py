"""Tests for hews.cache.CacheManager."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hews.cache import CacheManager
from hews.models import Comment, ItemType, Story


def test_save_and_get_story(tmp_path: Path) -> None:
    """CacheManager saves and restores story data."""

    cache = CacheManager(tmp_path / "cache.db")
    story = Story(
        id=123,
        type=ItemType.STORY,
        by="testuser",
        title="Test Story",
        url="https://example.com",
        score=42,
        descendants=10,
        kids=[456],
    )

    cache.save_item(story)
    cached = cache.get_item(123)

    assert isinstance(cached, Story)
    assert cached.id == story.id
    assert cached.title == story.title
    assert cached.url == story.url
    assert cached.kids == story.kids


def test_save_and_get_comment(tmp_path: Path) -> None:
    """CacheManager saves and restores comment data."""

    cache = CacheManager(tmp_path / "cache.db")
    comment = Comment(
        id=456,
        type=ItemType.COMMENT,
        by="commenter",
        text="Test comment",
        parent=123,
    )

    cache.save_item(comment)
    cached = cache.get_item(456)

    assert isinstance(cached, Comment)
    assert cached.id == comment.id
    assert cached.text == comment.text
    assert cached.parent == comment.parent


def test_cache_schema_has_fetched_timestamp(tmp_path: Path) -> None:
    """Cache rows include the freshness timestamp needed by integration code."""

    cache_path = tmp_path / "cache.db"
    cache = CacheManager(cache_path)
    cache.save_item(Story(id=1, type=ItemType.STORY, title="First"))

    with sqlite3.connect(cache_path) as conn:
        row = conn.execute("SELECT fetched_at FROM items WHERE id = 1").fetchone()

    assert row is not None
    assert isinstance(row[0], int)


def test_get_fresh_item_returns_only_fresh_items(tmp_path: Path) -> None:
    """CacheManager can reject stale entries by fetched timestamp."""

    cache_path = tmp_path / "cache.db"
    cache = CacheManager(cache_path)
    cache.save_item(Story(id=1, type=ItemType.STORY, title="First"))

    assert cache.get_fresh_item(1, max_age_seconds=60) is not None

    with sqlite3.connect(cache_path) as conn:
        conn.execute("UPDATE items SET fetched_at = 1 WHERE id = 1")

    assert cache.get_fresh_item(1, max_age_seconds=60) is None


def test_save_and_get_section_story_ids(tmp_path: Path) -> None:
    """CacheManager saves and restores ordered section story IDs."""

    cache = CacheManager(tmp_path / "cache.db")

    cache.save_story_ids("top", [123, 456, 789])

    assert cache.get_story_ids("top") == [123, 456, 789]
    assert cache.get_story_ids("new") == []
