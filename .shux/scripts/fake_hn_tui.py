"""Run HewsApp with deterministic fake data for shux visual checks."""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass

from hews.models import Comment, ItemType, Story
from hews.tui import HewsApp


@dataclass
class FakeHNClient:
    """Small async test double used by shux visual automation."""

    logged_in: bool = False
    search_calls: int = 0

    async def fetch_stories(
        self,
        section: str,
        limit: int = 30,
        force_refresh: bool = False,
    ) -> list[Story]:
        suffix = "refreshed" if force_refresh else section
        return _stories(f"Top fixture story ({suffix})")[:limit]

    async def search(self, query: str, limit: int = 30) -> list[Story]:
        self.search_calls += 1
        suffix = " refreshed" if self.search_calls > 1 else ""
        return _stories(f"Search fixture story for {query}{suffix}")[:limit]

    async def login_from_env(self) -> bool:
        self.logged_in = True
        return True

    async def fetch_item(self, item_id: int) -> Comment:
        comments = _comments()
        return comments[item_id]

    async def upvote(self, item_id: int, is_comment: bool) -> bool:
        return self.logged_in and item_id in {1001, 1101, 1102}

    async def post_comment(self, parent_id: int, text: str) -> bool:
        return self.logged_in and parent_id in {1001, 1101, 1102} and bool(text.strip())


def _stories(first_title: str) -> list[Story]:
    now = dt.datetime.now(dt.timezone.utc)
    return [
        Story(
            id=1001,
            type=ItemType.STORY,
            title=first_title,
            score=128,
            descendants=42,
            by="visual-user",
            time=now - dt.timedelta(hours=2),
            kids=[1101, 1102],
        ),
        Story(
            id=1002,
            type=ItemType.STORY,
            title="Second deterministic story",
            score=64,
            descendants=12,
            by="fixture-bot",
            time=now - dt.timedelta(hours=5),
        ),
    ]


def _comments() -> dict[int, Comment]:
    now = dt.datetime.now(dt.timezone.utc)
    return {
        1101: Comment(
            id=1101,
            type=ItemType.COMMENT,
            parent=1001,
            by="alice",
            time=now - dt.timedelta(minutes=35),
            text="<p>This deterministic comment can be upvoted and replied to.</p>",
        ),
        1102: Comment(
            id=1102,
            type=ItemType.COMMENT,
            parent=1001,
            by="visual-user",
            time=now - dt.timedelta(minutes=20),
            text="<p>Original poster follow-up for visual verification.</p>",
        ),
    }


def main() -> None:
    """Run the fake-data TUI."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", default=None)
    parser.add_argument("--section", default="top")
    args = parser.parse_args()

    HewsApp(
        initial_section=args.section,
        initial_search=args.search,
        hn_client=FakeHNClient(),
    ).run()


if __name__ == "__main__":
    main()
