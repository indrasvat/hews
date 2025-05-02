"""Basic unit tests for hews.models.* classes."""

from __future__ import annotations

import datetime as dt

import pytest

from hews.models import Comment, ItemType, Story, item_from_json


# ---------------------------------------------------------------------------
# Fixtures (representative, trimmed-down HN API responses)
# ---------------------------------------------------------------------------


STORY_JSON = {
    "id": 123,
    "type": "story",
    "by": "alice",
    "time": 1_700_000_000,  # Fri Nov 10 2023 03:20:00 GMT+0000
    "title": "Example story",
    "url": "https://example.com",
    "score": 42,
    "kids": [456, 789],
    "descendants": 2,
}


COMMENT_JSON = {
    "id": 456,
    "type": "comment",
    "by": "bob",
    "time": 1_700_000_100,  # +100 seconds
    "text": "<p>Nice!<p>",
    "parent": 123,
    "kids": [],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_story_from_json():
    story = Story.from_hn_json(STORY_JSON)
    assert story.id == 123
    assert story.type == ItemType.STORY
    assert story.by == "alice"
    assert story.url == "https://example.com"
    assert story.score == 42
    assert story.descendants == 2


def test_comment_from_json():
    comment = Comment.from_hn_json(COMMENT_JSON)
    assert comment.parent == 123
    assert comment.type == ItemType.COMMENT


def test_item_from_json_helper():
    assert isinstance(item_from_json(STORY_JSON), Story)
    assert isinstance(item_from_json(COMMENT_JSON), Comment)


def test_age_helper():
    # Force *time* to exactly now minus 3600 seconds for deterministic check.
    one_hour_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    story = Story(
        id=1,
        type=ItemType.STORY,
        time=one_hour_ago,
    )
    assert story.age().endswith("h ago")


def test_to_dict_roundtrip():
    story = Story.from_hn_json(STORY_JSON)
    data = story.to_dict()
    # Numeric fields survive round-trip
    assert data["id"] == STORY_JSON["id"]
    assert data["type"] == "story"
    assert data["time"] == STORY_JSON["time"]


def test_validation_missing_id():
    bad_json = STORY_JSON.copy()
    bad_json.pop("id")
    with pytest.raises(KeyError):
        Story.from_hn_json(bad_json)  # type: ignore[arg-type]
