"""Run HewsApp with deterministic fake data for shux visual checks."""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass

from hews.models import ItemType, Story
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
