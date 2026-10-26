"""Behavior and rendering checks for the live stats screen."""

import asyncio
import datetime as dt
from unittest.mock import AsyncMock

import pytest
from rich.text import Text
from textual.widgets import ListView, Static

from hews.models import ItemType, Story
from hews.tui import (
    CommentsScreen,
    HewsApp,
    StatsChart,
    StatsScreen,
    StatsStoryItem,
    StoryListScreen,
)


@pytest.mark.asyncio
async def test_stats_live_ranking_bars_bubbles_and_navigation() -> None:
    """The s screen fetches fresh data and keeps bars proportional when sorted."""
    now = dt.datetime.now(dt.timezone.utc)
    stories = [
        Story(
            id=1,
            type=ItemType.STORY,
            title="Half [bold] 中文",
            score=50,
            descendants=60,
            time=now - dt.timedelta(hours=1),
        ),
        Story(
            id=2,
            type=ItemType.STORY,
            title="Leader",
            score=100,
            descendants=10,
            time=now - dt.timedelta(hours=3),
        ),
        Story(
            id=3,
            type=ItemType.STORY,
            title="Yesterday",
            score=999,
            time=now - dt.timedelta(hours=25),
        ),
    ]
    client = AsyncMock(is_offline=False)
    client.fetch_stories.return_value = stories
    app = HewsApp(hn_client=client, show_banner=False)
    async with app.run_test(size=(100, 28)) as pilot:
        original = app.screen
        await pilot.press("s")
        await app.workers.wait_for_complete()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, StatsScreen)
        client.fetch_stories.assert_awaited_with("top", limit=100, force_refresh=True)
        assert [story.id for story in screen.stories] == [2, 1]
        rows = list(screen.query(StatsStoryItem))
        leader = rows[0].query_one(StatsChart).render()
        half = rows[1].query_one(StatsChart).render()
        leader_bar = leader.plain.splitlines()[1].count("▓")
        half_bar = half.plain.splitlines()[1].count("▓")
        assert abs(half_bar - leader_bar / 2) <= 1
        assert leader.plain.splitlines()[0].endswith("◯ 10")
        assert half.plain.splitlines()[0].endswith("◯ 60")
        assert "Half [bold] 中文" in half.plain
        assert (
            len(
                {
                    Text(line).cell_len
                    for line in [
                        leader.plain.splitlines()[0],
                        half.plain.splitlines()[0],
                    ]
                }
            )
            == 1
        )
        assert any(span.style == "#ff8700" for span in half.spans)
        assert all(span.style != "#ff8700" for span in leader.spans)
        await pilot.press("c")
        assert [story.id for story in screen.stories] == [1, 2]
        assert (
            screen.query_one("#stats-heading", Static).renderable
            == "top today · by comments"
        )
        assert (
            screen.query_one("#stats-stories", ListView).highlighted_child.story.id == 2
        )
        assert (
            screen.query(StatsStoryItem)[1]
            .query_one(StatsChart)
            .render()
            .plain.splitlines()[1]
            .count("▓")
            == leader_bar
        )
        await pilot.press("p", "j", "enter")
        assert isinstance(app.screen, CommentsScreen)
        assert app.screen.story.id == 1
        await pilot.press("escape")
        assert app.screen is screen
        await pilot.press("r")
        await app.workers.wait_for_complete()
        await pilot.press("escape")
        assert app.screen is original
        await pilot.press("S")
        assert isinstance(app.screen, StoryListScreen)
        assert app.screen.section == "show"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["empty", "error", "offline"])
async def test_stats_loading_states(mode: str) -> None:
    """Empty, failed, and cached API responses are clearly disclosed."""
    client = AsyncMock(is_offline=(mode == "offline"))
    client.fetch_stories.return_value = []
    app = HewsApp(hn_client=client, show_banner=False)
    async with app.run_test() as pilot:
        if mode == "error":
            client.fetch_stories.side_effect = RuntimeError("network failed")
        await pilot.press("s")
        await app.workers.wait_for_complete()
        screen = app.screen
        assert isinstance(screen, StatsScreen)
        status = screen.query_one("#stats-status", Static)
        expected = {
            "empty": "No stories",
            "error": "Unable to load",
            "offline": "[offline]",
        }
        assert expected[mode] in str(status.renderable)
        assert status.display
        await pilot.press("enter", "q")
        assert not app.is_running


@pytest.mark.asyncio
async def test_stats_age_boundary_zero_scores_and_narrow_resize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two hours is excluded from orange; zero scores and narrow panes render safely."""
    now = dt.datetime.now(dt.timezone.utc)

    class FrozenDateTime(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:
            return now

    monkeypatch.setattr("hews.tui.dt.datetime", FrozenDateTime)
    client = AsyncMock(is_offline=False)
    client.fetch_stories.return_value = [
        Story(
            id=1,
            type=ItemType.STORY,
            title="界" * 100,
            score=0,
            time=now - dt.timedelta(hours=2),
        ),
        Story(
            id=2,
            type=ItemType.STORY,
            title="Fresh",
            score=None,
            time=now - dt.timedelta(hours=2) + dt.timedelta(seconds=1),
        ),
    ]
    app = HewsApp(hn_client=client, show_banner=False)
    async with app.run_test(size=(40, 15)) as pilot:
        await pilot.press("s")
        await app.workers.wait_for_complete()
        await pilot.pause()
        charts = list(app.screen.query(StatsChart))
        for chart in charts:
            rendered = chart.render()
            assert "▓" not in rendered.plain
            assert all(
                Text(line).cell_len <= chart.content_size.width
                for line in rendered.plain.splitlines()
            )
        assert all(span.style != "#ff8700" for span in charts[0].render().spans)
        assert any(span.style == "#ff8700" for span in charts[1].render().spans)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "title,score,width", [("Huge", 10**30, 20), ("first\nsecond\nthird", 5, 40)]
)
async def test_stats_hostile_titles_and_counts_fit_two_lines(
    title: str, score: int, width: int
) -> None:
    """Large numbers and embedded newlines cannot displace the chart's bar."""
    client = AsyncMock(is_offline=False)
    client.fetch_stories.return_value = [
        Story(id=1, type=ItemType.STORY, title=title, score=score, descendants=score)
    ]
    app = HewsApp(hn_client=client, show_banner=False)
    async with app.run_test(size=(width, 24)) as pilot:
        await pilot.press("s")
        await app.workers.wait_for_complete()
        await pilot.pause()
        chart = app.screen.query_one(StatsChart)
        lines = chart.render().plain.splitlines()
        assert len(lines) == 2
        assert all(Text(line).cell_len <= chart.content_size.width for line in lines)


@pytest.mark.asyncio
async def test_stats_refresh_overlapping_sort_has_no_duplicate_rows() -> None:
    """A refresh worker finishing during a sort renders every story once."""
    client = AsyncMock(is_offline=False)
    client.fetch_stories.return_value = [
        Story(
            id=i, type=ItemType.STORY, title=f"Story {i}", score=100 - i, descendants=i
        )
        for i in range(10)
    ]
    app = HewsApp(hn_client=client, show_banner=False)
    async with app.run_test() as pilot:
        await pilot.press("s")
        await app.workers.wait_for_complete()
        screen = app.screen
        assert isinstance(screen, StatsScreen)
        await asyncio.gather(screen.load_stories(), screen.action_sort_by("comments"))
        rows = list(screen.query(StatsStoryItem))
        assert len(rows) == len(screen.stories)
        assert [row.story.id for row in rows] == [story.id for story in screen.stories]
