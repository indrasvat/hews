"""Domain model classes for Hacker News items.

This module defines strongly-typed in-memory representations for Hacker News
*stories* (regular stories, Ask HN, Show HN, Job postings) and *comments*.

The rest of the application (API client, caching layer, UI) should exclusively
deal with these types – never raw JSON dictionaries – to gain the benefits of
static typing and a consistent helper API (``age()``, ``to_dict()`` …).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import List, Optional, TypedDict, Union

__all__ = [
    "ItemType",
    "Story",
    "Comment",
    "item_from_json",
]


class ItemType(str, Enum):
    """Hacker News item types we care about."""

    STORY = "story"  # regular story – including Show/Ask HN
    JOB = "job"  # job posting (top-level, no score)
    COMMENT = "comment"

    # NOTE: The HN API returns "story", "comment", or "job".  Ask/Show HN posts
    # are *also* type="story"; we don’t distinguish them at the model level –
    # the UI can decide based on the title prefix.


_T = _dt.datetime


class _BaseJson(TypedDict, total=False):
    """Subset of the official HN JSON schema we parse/write back."""

    id: int
    type: str
    by: str
    time: int
    text: str
    url: str
    score: int
    descendants: int
    kids: List[int]
    parent: int
    dead: bool
    deleted: bool


@dataclass(slots=True)
class ItemBase:
    """Common attributes shared by all HN items."""

    id: int
    type: ItemType
    by: Optional[str] = None
    time: _T = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc))
    text: Optional[str] = None
    kids: List[int] = field(default_factory=list)
    dead: bool = False
    deleted: bool = False

    # ---------------------------------------------------------------------
    # Convenience helpers
    # ---------------------------------------------------------------------
    def age(self) -> str:  # noqa: D401 – short imperative OK here
        """Return a short human-friendly *age* string (e.g. "3h ago")."""

        now = _dt.datetime.now(_dt.timezone.utc)
        delta = now - self.time
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"

    # ------------------------------------------------------------------
    # (De)serialisation helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> _BaseJson:
        """Convert to a dict that is JSON-serialisable for caching."""

        data = asdict(self)
        # dataclasses.asdict turns Enums into Enum objects – convert to value
        data["type"] = self.type.value
        # Convert datetime back to Unix epoch seconds
        data["time"] = int(self.time.replace(tzinfo=_dt.timezone.utc).timestamp())
        return data  # type: ignore[return-value]


@dataclass(slots=True)
class Story(ItemBase):
    """Top-level Hacker News post."""

    url: Optional[str] = None
    score: Optional[int] = None
    descendants: Optional[int] = None  # number of comments

    # --------------------------------- Constructors ----------------------
    @classmethod
    def from_hn_json(cls, data: _BaseJson) -> "Story":
        """Create *Story* instance from raw HN JSON item dict."""

        return cls(
            id=data["id"],
            type=ItemType(data.get("type", "story")),
            by=data.get("by"),
            time=_dt.datetime.fromtimestamp(data["time"], _dt.timezone.utc)
            if "time" in data
            else _dt.datetime.now(_dt.timezone.utc),
            text=data.get("text"),
            kids=data.get("kids", []),
            dead=data.get("dead", False),
            deleted=data.get("deleted", False),
            url=data.get("url"),
            score=data.get("score"),
            descendants=data.get("descendants"),
        )


@dataclass(slots=True)
class Comment(ItemBase):
    """Comment on a story or another comment."""

    parent: int = 0

    @classmethod
    def from_hn_json(cls, data: _BaseJson) -> "Comment":
        """Create *Comment* instance from raw HN JSON item dict."""

        return cls(
            id=data["id"],
            type=ItemType.COMMENT,
            by=data.get("by"),
            time=_dt.datetime.fromtimestamp(data["time"], _dt.timezone.utc)
            if "time" in data
            else _dt.datetime.now(_dt.timezone.utc),
            text=data.get("text"),
            kids=data.get("kids", []),
            dead=data.get("dead", False),
            deleted=data.get("deleted", False),
            parent=data.get("parent", 0),
        )


# -------------------------------------------------------------------------
# Public helper
# -------------------------------------------------------------------------


def item_from_json(data: _BaseJson) -> Union[Story, Comment]:
    """Smart constructor that returns *Story* or *Comment* depending on data."""

    item_type = data.get("type")
    if item_type == ItemType.COMMENT.value:
        return Comment.from_hn_json(data)
    return Story.from_hn_json(data)
