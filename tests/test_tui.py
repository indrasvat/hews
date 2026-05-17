"""Tests for the Textual TUI application."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from textual.widgets import ListView, Static

from hews.models import ItemType, Story
from hews.tui import CommentsScreen, HewsApp, StoryListItem, StoryListScreen


@pytest.fixture
def tui_stories() -> list[Story]:
    """Create sample stories for TUI tests."""
    return [
        Story(
            id=1,
            type=ItemType.STORY,
            title="Visible Story",
            url="https://example.com/visible",
            score=42,
            descendants=7,
            by="hnuser",
        )
    ]


@pytest.fixture
def fake_client(tui_stories: list[Story]) -> AsyncMock:
    """Create an async HN client test double."""
    client = AsyncMock()
    client.fetch_stories.return_value = tui_stories
    client.search.return_value = tui_stories
    client.login_from_env.return_value = True
    return client


@pytest.mark.asyncio
async def test_tui_starts_on_top_stories_by_default(fake_client: AsyncMock) -> None:
    """The app pushes a story-list screen for top stories by default."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        assert screen.section == "top"
        assert screen.search_query is None

        status = screen.query_one("#status", Static)
        list_view = screen.query_one("#stories", ListView)
        assert str(status.renderable) == "Top stories"
        assert len(list_view.children) == 1
        assert list_view.index == 0

        fake_client.fetch_stories.assert_awaited_once_with(
            "top",
            limit=30,
            force_refresh=False,
        )
        fake_client.search.assert_not_called()

        await pilot.pause()


@pytest.mark.asyncio
async def test_story_list_item_displays_title_domain_and_metadata() -> None:
    """Story rows include rank, compact domain, and useful metadata."""
    story = Story(
        id=2,
        type=ItemType.STORY,
        title="Domain Story",
        url="https://www.example.org/path",
        score=13,
        descendants=4,
        by="alice",
    )
    item = StoryListItem(story, rank=3)

    assert item._title_text() == "3. Domain Story (example.org)"
    assert "13 points by alice | 4 comments" in item._metadata_text()


@pytest.mark.asyncio
async def test_tui_starts_on_search_results_when_query_is_supplied(
    fake_client: AsyncMock,
) -> None:
    """A search query directs startup to the search-results view."""
    app = HewsApp(initial_search="python", hn_client=fake_client)

    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        assert screen.search_query == "python"

        status = screen.query_one("#status", Static)
        assert str(status.renderable) == "Search results for 'python'"
        fake_client.search.assert_awaited_once_with("python", limit=30)
        fake_client.fetch_stories.assert_not_called()


@pytest.mark.asyncio
async def test_tui_attempts_background_login_when_credentials_exist(
    fake_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured HN credentials start a non-blocking login task."""
    monkeypatch.setenv("HN_USERNAME", "testuser")
    monkeypatch.setenv("HN_PASSWORD", "secret")
    app = HewsApp(hn_client=fake_client)

    async with app.run_test():
        assert app._login_task is not None
        await app._login_task

    fake_client.login_from_env.assert_awaited_once_with()
    assert app.is_authenticated is True


@pytest.mark.asyncio
async def test_tui_updates_status_when_background_login_finishes(
    fake_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A delayed login completion updates the already-rendered story screen."""
    monkeypatch.setenv("HN_USERNAME", "testuser")
    monkeypatch.setenv("HN_PASSWORD", "secret")
    login_started = asyncio.Event()
    finish_login = asyncio.Event()

    async def login_from_env() -> bool:
        login_started.set()
        await finish_login.wait()
        return True

    fake_client.login_from_env.side_effect = login_from_env
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await login_started.wait()
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        status = screen.query_one("#status", Static)
        assert str(status.renderable) == "Top stories"

        finish_login.set()
        assert app._login_task is not None
        await app._login_task
        await pilot.pause()

        assert str(status.renderable) == "Top stories - logged in"


@pytest.mark.asyncio
async def test_tui_refresh_bypasses_item_cache(fake_client: AsyncMock) -> None:
    """The screen refresh action forces story refetching."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("r")

    assert fake_client.fetch_stories.await_args_list[-1].kwargs["force_refresh"] is True


@pytest.mark.asyncio
async def test_tui_refresh_error_clears_stale_story_state(
    fake_client: AsyncMock,
) -> None:
    """A refresh failure clears stale screen story state consistently."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        assert len(screen.stories) == 1

        fake_client.fetch_stories.side_effect = RuntimeError("offline")
        await pilot.press("r")
        await pilot.pause()

        list_view = screen.query_one("#stories", ListView)
        status = screen.query_one("#status", Static)
        assert screen.stories == []
        assert len(list_view.children) == 0
        assert str(status.renderable) == "Error loading stories: offline"


@pytest.mark.asyncio
async def test_tui_help_binding_notifies_user(fake_client: AsyncMock) -> None:
    """The global help action exists as a placeholder for the future overlay."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        with patch.object(app, "notify") as notify:
            await pilot.press("?")
            await pilot.pause()

    notify.assert_called_once_with("Help overlay coming soon.", title="Hews")


@pytest.mark.asyncio
async def test_story_list_j_and_k_move_selection(fake_client: AsyncMock) -> None:
    """Vim-style movement keys move through the story list."""
    fake_client.fetch_stories.return_value = [
        Story(id=1, type=ItemType.STORY, title="First"),
        Story(id=2, type=ItemType.STORY, title="Second"),
    ]
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        list_view = screen.query_one("#stories", ListView)
        assert list_view.index == 0

        await pilot.press("j")
        assert list_view.index == 1
        await pilot.press("k")
        assert list_view.index == 0


@pytest.mark.asyncio
async def test_story_list_arrow_keys_move_selection(fake_client: AsyncMock) -> None:
    """Arrow keys retain native ListView navigation."""
    fake_client.fetch_stories.return_value = [
        Story(id=1, type=ItemType.STORY, title="First"),
        Story(id=2, type=ItemType.STORY, title="Second"),
    ]
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        list_view = screen.query_one("#stories", ListView)

        await pilot.press("down")
        assert list_view.index == 1
        await pilot.press("up")
        assert list_view.index == 0


@pytest.mark.asyncio
async def test_story_list_section_shortcut_loads_new_section(
    fake_client: AsyncMock,
) -> None:
    """Section shortcuts reload the same screen with the requested section."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        await pilot.press("a")
        await pilot.pause()

        assert screen.section == "ask"
        assert screen.search_query is None

    assert fake_client.fetch_stories.await_args_list[-1].args == ("ask",)
    assert fake_client.fetch_stories.await_args_list[-1].kwargs["force_refresh"] is False


@pytest.mark.asyncio
async def test_story_list_jobs_shortcut_uses_shift_j(fake_client: AsyncMock) -> None:
    """Jobs section is reachable without stealing j from down navigation."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        await pilot.press("J")
        await pilot.pause()

        assert screen.section == "jobs"

    assert fake_client.fetch_stories.await_args_list[-1].args == ("jobs",)


@pytest.mark.asyncio
async def test_story_list_enter_opens_comments_placeholder(
    fake_client: AsyncMock,
) -> None:
    """Enter opens the selected story in the placeholder comments screen."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, CommentsScreen)
        assert app.screen.story.title == "Visible Story"


@pytest.mark.asyncio
async def test_story_list_right_opens_comments_placeholder(
    fake_client: AsyncMock,
) -> None:
    """Right arrow opens the selected story."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("right")
        await pilot.pause()

        assert isinstance(app.screen, CommentsScreen)


@pytest.mark.asyncio
async def test_story_list_empty_open_notifies(fake_client: AsyncMock) -> None:
    """Opening an empty list is handled gracefully."""
    fake_client.fetch_stories.return_value = []
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        with patch.object(app, "notify") as notify:
            await pilot.press("enter")
            await pilot.pause()

    notify.assert_called_once_with("No story selected.", title="Hews")


@pytest.mark.asyncio
async def test_story_list_search_binding_notifies_user(fake_client: AsyncMock) -> None:
    """The search trigger is wired for the future search UI task."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        with patch.object(app, "notify") as notify:
            await pilot.press("/")
            await pilot.pause()

    notify.assert_called_once_with("Search UI coming soon.", title="Hews")


@pytest.mark.asyncio
async def test_tui_quit_binding_exits(fake_client: AsyncMock) -> None:
    """The global quit key exits the app."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running
