"""Tests for the Textual TUI application."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from textual.widgets import Input, ListView, Static

from hews.client import HNClientError
from hews.models import Comment, ItemType, Story
from hews.tui import (
    CommentListItem,
    CommentsScreen,
    HEWS_BANNER_LINES,
    HEWS_BANNER_WIDTH,
    HelpScreen,
    HewsApp,
    ReplyDialog,
    SearchDialog,
    StoryListItem,
    StoryListScreen,
    html_to_plain_text,
    render_startup_banner,
)


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
    client.upvote.return_value = True
    client.post_comment.return_value = True
    return client


def test_startup_banner_is_fixed_width_ascii_art() -> None:
    """The startup logo has stable ASCII rows for clean terminal rendering."""
    assert all(line.isascii() for line in HEWS_BANNER_LINES)
    assert {len(line) for line in HEWS_BANNER_LINES} == {HEWS_BANNER_WIDTH}

    rendered = render_startup_banner()
    assert rendered.plain.startswith(HEWS_BANNER_LINES[0])
    assert "Hacker News, distilled." in rendered.plain
    assert "\x1b" not in rendered.plain


@pytest.mark.asyncio
async def test_tui_starts_on_top_stories_by_default(fake_client: AsyncMock) -> None:
    """The app pushes a story-list screen for top stories by default."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        assert screen.section == "top"
        assert screen.search_query is None
        assert screen.query_one("#startup-banner", Static).display is True

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
async def test_tui_can_start_without_banner(fake_client: AsyncMock) -> None:
    """The startup banner can be disabled for quiet TUI launches."""
    app = HewsApp(hn_client=fake_client, show_banner=False)

    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        assert len(screen.query("#startup-banner")) == 0


@pytest.mark.asyncio
async def test_tui_hides_banner_on_small_terminal(fake_client: AsyncMock) -> None:
    """Narrow panes hide the banner instead of wrapping the ASCII art."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test(size=(36, 12)):
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        assert screen.query_one("#startup-banner", Static).display is False


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
        assert screen.query_one("#startup-banner", Static).display is True

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
        assert str(status.renderable) == "Error: Unable to load stories."


@pytest.mark.asyncio
async def test_tui_offline_start_shows_cached_data_status(
    fake_client: AsyncMock,
) -> None:
    """Cached stories remain browsable when the initial fetch detects offline mode."""
    fake_client.is_offline = True
    app = HewsApp(hn_client=fake_client)

    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        status = screen.query_one("#status", Static)
        list_view = screen.query_one("#stories", ListView)

        assert str(status.renderable) == (
            "Network unavailable - showing cached data [offline]"
        )
        assert len(list_view.children) == 1


@pytest.mark.asyncio
async def test_tui_offline_search_is_blocked_but_refresh_can_retry(
    fake_client: AsyncMock,
) -> None:
    """Known offline mode blocks search while refresh can retry the network."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        fake_client.is_offline = True
        screen = app.screen
        assert isinstance(screen, StoryListScreen)

        await pilot.press("r")
        await pilot.pause()
        assert fake_client.fetch_stories.await_count == 2

        await pilot.press("/")
        await pilot.pause()

        status = screen.query_one("#status", Static)
        assert str(status.renderable) == "Cannot fetch new data while offline."
        assert app.screen is screen

    fake_client.search.assert_not_called()


@pytest.mark.asyncio
async def test_tui_client_errors_use_generic_load_message(
    fake_client: AsyncMock,
) -> None:
    """Non-network client failures are not mislabeled as offline."""
    fake_client.fetch_stories.side_effect = HNClientError("bad response")
    app = HewsApp(hn_client=fake_client)

    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, StoryListScreen)

        status = screen.query_one("#status", Static)
        assert str(status.renderable) == "Error: Unable to load stories."


@pytest.mark.asyncio
async def test_tui_help_binding_opens_and_dismisses_overlay(
    fake_client: AsyncMock,
) -> None:
    """The global help action opens a dismissible shortcut reference."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        story_screen = app.screen
        assert isinstance(story_screen, StoryListScreen)
        stories = story_screen.query_one("#stories", ListView)
        assert stories.index == 0

        await pilot.press("?")
        await pilot.pause()

        assert isinstance(app.screen, HelpScreen)
        content = app.screen.query_one("#help-content", Static)
        help_text = str(content.renderable)
        assert "Navigation" in help_text
        assert "Up/Down or j/k" in help_text
        assert "t                     Top stories" in help_text
        assert "Shift+j               Jobs" in help_text
        assert "u                     Upvote" in help_text
        assert "c                     Comment" in help_text

        await pilot.press("j")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        assert stories.index == 0

        await pilot.press("?")
        await pilot.pause()

        assert app.screen is story_screen
        assert stories.index == 0


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
async def test_comments_screen_loads_story_and_nested_comments() -> None:
    """The comments screen renders story details and nested comment rows."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        score=99,
        descendants=3,
        by="alice",
        text="<p>Story body</p>",
        kids=[11, 12],
    )
    comments = {
        11: Comment(
            id=11,
            type=ItemType.COMMENT,
            parent=10,
            by="bob",
            text="<p>First comment</p>",
            kids=[13],
        ),
        12: Comment(
            id=12,
            type=ItemType.COMMENT,
            parent=10,
            by="alice",
            text="<p>OP follow-up</p>",
        ),
        13: Comment(
            id=13,
            type=ItemType.COMMENT,
            parent=11,
            by="carol",
            text="<p>Nested reply</p>",
        ),
    }
    client = AsyncMock()
    client.fetch_item.side_effect = lambda item_id: comments[item_id]
    app = HewsApp(hn_client=client)

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        comments_view = screen.query_one("#comments", ListView)
        assert len(comments_view.children) == 3
        assert comments_view.index == 0
        assert all(
            isinstance(child, CommentListItem) for child in comments_view.children
        )

        first, nested, op_comment = comments_view.children
        assert isinstance(first, CommentListItem)
        assert isinstance(nested, CommentListItem)
        assert isinstance(op_comment, CommentListItem)
        assert first.depth == 0
        assert nested.depth == 1
        assert first._metadata_text().startswith("[-] bob")
        assert not nested._metadata_text().startswith(("[+]", "[-]"))
        assert op_comment._metadata_text().startswith("alice [OP]")


@pytest.mark.asyncio
async def test_comments_screen_collapses_and_expands_selected_thread() -> None:
    """Enter hides and restores descendants for a comment thread."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        score=99,
        descendants=4,
        by="alice",
        kids=[11, 12],
    )
    comments = {
        11: Comment(
            id=11,
            type=ItemType.COMMENT,
            parent=10,
            by="bob",
            text="First comment",
            kids=[13],
        ),
        12: Comment(
            id=12,
            type=ItemType.COMMENT,
            parent=10,
            by="dana",
            text="Second comment",
            kids=[14],
        ),
        13: Comment(
            id=13,
            type=ItemType.COMMENT,
            parent=11,
            by="carol",
            text="Nested reply",
        ),
        14: Comment(
            id=14,
            type=ItemType.COMMENT,
            parent=12,
            by="erin",
            text="Another nested reply",
        ),
    }
    client = AsyncMock()
    client.fetch_item.side_effect = lambda item_id: comments[item_id]
    app = HewsApp(hn_client=client)

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        comments_view = screen.query_one("#comments", ListView)
        assert len(comments_view.children) == 4

        await pilot.press("enter")
        await pilot.pause()

        visible_ids = [
            child.node.comment.id
            for child in comments_view.children
            if isinstance(child, CommentListItem)
        ]
        assert visible_ids == [11, 12, 14]
        assert comments_view.index == 0
        selected = comments_view.children[0]
        assert isinstance(selected, CommentListItem)
        assert selected._metadata_text().startswith("[+] bob")

        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

        visible_ids = [
            child.node.comment.id
            for child in comments_view.children
            if isinstance(child, CommentListItem)
        ]
        assert visible_ids == [11, 12]
        assert comments_view.index == 1
        selected = comments_view.children[1]
        assert isinstance(selected, CommentListItem)
        assert selected._metadata_text().startswith("[+] dana")

        await pilot.press("right")
        await pilot.pause()

        visible_ids = [
            child.node.comment.id
            for child in comments_view.children
            if isinstance(child, CommentListItem)
        ]
        assert visible_ids == [11, 12, 14]
        assert comments_view.index == 1
        selected = comments_view.children[1]
        assert isinstance(selected, CommentListItem)
        assert selected._metadata_text().startswith("[-] dana")


@pytest.mark.asyncio
async def test_comments_screen_back_binding_returns_to_story_list(
    fake_client: AsyncMock,
) -> None:
    """The comments screen supports the issue's keyboard back binding."""
    fake_client.fetch_stories.return_value = [
        Story(
            id=10,
            type=ItemType.STORY,
            title="Story",
            kids=[],
        )
    ]
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, CommentsScreen)

        await pilot.press("left")
        await pilot.pause()
        assert isinstance(app.screen, StoryListScreen)


@pytest.mark.asyncio
async def test_comments_screen_upvotes_selected_comment() -> None:
    """Pressing u upvotes the highlighted comment when logged in."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        kids=[11],
    )
    comment = Comment(
        id=11,
        type=ItemType.COMMENT,
        parent=10,
        by="bob",
        text="First comment",
    )
    client = AsyncMock()
    client.fetch_item.return_value = comment
    client.upvote.return_value = True
    app = HewsApp(hn_client=client)
    app.is_authenticated = True

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        await pilot.press("u")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        status = screen.query_one("#comments-status", Static)
        assert str(status.renderable) == "Upvoted comment."

    client.upvote.assert_awaited_once_with(11, True)


@pytest.mark.asyncio
async def test_comments_screen_upvotes_story_when_no_comment_selected() -> None:
    """Pressing u falls back to the story when the thread has no selection."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        kids=[],
    )
    client = AsyncMock()
    client.upvote.return_value = True
    app = HewsApp(hn_client=client)
    app.is_authenticated = True

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        await pilot.press("u")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        status = screen.query_one("#comments-status", Static)
        assert str(status.renderable) == "Upvoted story."

    client.upvote.assert_awaited_once_with(10, False)


@pytest.mark.asyncio
async def test_comments_screen_upvote_requires_login() -> None:
    """Unauthenticated upvotes show feedback and do not call the client."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        kids=[],
    )
    client = AsyncMock()
    app = HewsApp(hn_client=client)

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        await pilot.press("u")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        status = screen.query_one("#comments-status", Static)
        assert str(status.renderable) == "Login required to upvote."

    client.upvote.assert_not_called()


@pytest.mark.asyncio
async def test_comments_screen_blocks_write_actions_while_offline() -> None:
    """Offline mode prevents voting and replying even when a login is present."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        kids=[],
    )
    client = AsyncMock()
    client.is_offline = True
    app = HewsApp(hn_client=client)
    app.is_authenticated = True

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        await pilot.press("u")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        status = screen.query_one("#comments-status", Static)
        assert str(status.renderable) == "Cannot vote while offline."

        await pilot.press("c")
        await pilot.pause()

        assert app.screen is screen
        assert str(status.renderable) == "Cannot comment while offline."

    client.upvote.assert_not_called()
    client.post_comment.assert_not_called()


@pytest.mark.asyncio
async def test_comments_screen_reply_posts_and_inserts_child_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Submitting a reply posts it and inserts it under the highlighted comment."""
    monkeypatch.setenv("HN_USERNAME", "testuser")
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        descendants=1,
        kids=[11],
    )
    comment = Comment(
        id=11,
        type=ItemType.COMMENT,
        parent=10,
        by="bob",
        text="First comment",
    )
    client = AsyncMock()
    client.fetch_item.return_value = comment
    client.post_comment.return_value = True
    app = HewsApp(hn_client=client)
    app.is_authenticated = True

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, ReplyDialog)

        await pilot.press(*list("Thanks for the context"), "enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        comments_view = screen.query_one("#comments", ListView)
        assert len(comments_view.children) == 2
        assert comments_view.index == 1

        inserted = comments_view.children[1]
        assert isinstance(inserted, CommentListItem)
        assert inserted.depth == 1
        assert inserted.node.comment.parent == 11
        assert inserted.node.comment.by == "testuser"
        assert inserted.node.comment.text == "Thanks for the context"

        status = screen.query_one("#comments-status", Static)
        assert str(status.renderable) == "Comment posted."
        story_header = screen.query_one("#story-header", Static)
        assert "2 comments" in str(story_header.renderable)

    client.post_comment.assert_awaited_once_with(11, "Thanks for the context")


@pytest.mark.asyncio
async def test_comments_screen_reply_requires_login() -> None:
    """Unauthenticated reply attempts show feedback and skip the dialog."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        kids=[],
    )
    client = AsyncMock()
    app = HewsApp(hn_client=client)

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        status = screen.query_one("#comments-status", Static)
        assert str(status.renderable) == "Login required to comment."

    client.post_comment.assert_not_called()


@pytest.mark.asyncio
async def test_comments_screen_ignores_duplicate_interactions() -> None:
    """A pending comment action prevents repeated submissions."""
    story = Story(
        id=10,
        type=ItemType.STORY,
        title="Ask HN: Testing",
        kids=[],
    )
    client = AsyncMock()
    client.post_comment.return_value = True
    app = HewsApp(hn_client=client)
    app.is_authenticated = True

    async with app.run_test() as pilot:
        await app.push_screen(CommentsScreen(story))
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, CommentsScreen)
        screen._interaction_in_progress = True
        await screen._handle_reply_text("duplicate", None)

    client.post_comment.assert_not_called()


def test_html_to_plain_text_formats_common_hn_markup() -> None:
    """HN HTML is converted to readable terminal text."""
    text = html_to_plain_text(
        "<p>Hello&nbsp;<b>world</b> &lt;not-a-tag&gt;</p><p>Line<br>two</p>"
        "<pre>code\nblock</pre>"
    )

    assert "Hello world <not-a-tag>" in text
    assert "Line\ntwo" in text
    assert "code\nblock" in text


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
    assert (
        fake_client.fetch_stories.await_args_list[-1].kwargs["force_refresh"] is False
    )


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
async def test_story_list_search_binding_opens_input_dialog(
    fake_client: AsyncMock,
) -> None:
    """The search trigger opens a focused query prompt."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.pause()

        assert isinstance(app.screen, SearchDialog)
        search_input = app.screen.query_one("#search-query", Input)
        assert search_input.has_focus


@pytest.mark.asyncio
async def test_story_list_search_dialog_pushes_results_screen(
    fake_client: AsyncMock,
) -> None:
    """Submitting a query opens a reusable story-list screen for results."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.press(*list("database"), "enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, StoryListScreen)
        assert screen.search_query == "database"
        assert len(screen.query("#startup-banner")) == 0
        status = screen.query_one("#status", Static)
        assert str(status.renderable) == "Search results for 'database'"

    fake_client.search.assert_awaited_once_with("database", limit=30)


@pytest.mark.asyncio
async def test_story_list_search_dialog_cancel_keeps_current_list(
    fake_client: AsyncMock,
) -> None:
    """Escape closes the search prompt without changing the active list."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        original_screen = app.screen
        await pilot.press("/")
        await pilot.press("escape")
        await pilot.pause()

        assert app.screen is original_screen

    fake_client.search.assert_not_called()


@pytest.mark.asyncio
async def test_story_list_search_dialog_empty_submit_keeps_current_list(
    fake_client: AsyncMock,
) -> None:
    """Blank searches are ignored instead of pushing an empty results screen."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        original_screen = app.screen
        await pilot.press("/")
        await pilot.press("enter")
        await pilot.pause()

        assert app.screen is original_screen

    fake_client.search.assert_not_called()


@pytest.mark.asyncio
async def test_story_list_search_results_back_returns_to_previous_list(
    fake_client: AsyncMock,
) -> None:
    """Back from pushed search results returns to the invoking story list."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        original_screen = app.screen
        await pilot.press("/")
        await pilot.press(*list("database"), "enter")
        await pilot.pause()
        assert isinstance(app.screen, StoryListScreen)
        assert app.screen.search_query == "database"

        await pilot.press("left")
        await pilot.pause()

        assert app.screen is original_screen
        assert isinstance(app.screen, StoryListScreen)
        assert app.screen.search_query is None


@pytest.mark.asyncio
async def test_initial_search_results_back_exits_app(fake_client: AsyncMock) -> None:
    """Back exits when an initial search result is the only screen."""
    app = HewsApp(initial_search="database", hn_client=fake_client)

    async with app.run_test() as pilot:
        assert isinstance(app.screen, StoryListScreen)
        assert app.screen.search_query == "database"

        await pilot.press("left")
        await pilot.pause()

        assert not app.is_running


@pytest.mark.asyncio
async def test_empty_search_results_show_friendly_status(
    fake_client: AsyncMock,
) -> None:
    """Empty result sets use explicit no-results copy."""
    fake_client.search.return_value = []
    app = HewsApp(initial_search="unlikely-query", hn_client=fake_client)

    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, StoryListScreen)

        status = screen.query_one("#status", Static)
        list_view = screen.query_one("#stories", ListView)
        assert str(status.renderable) == "No results found for 'unlikely-query'"
        assert len(list_view.children) == 0


@pytest.mark.asyncio
async def test_tui_quit_binding_exits(fake_client: AsyncMock) -> None:
    """The global quit key exits the app."""
    app = HewsApp(hn_client=fake_client)

    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running
