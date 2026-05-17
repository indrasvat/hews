"""Textual application for browsing Hacker News stories."""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Optional, cast
from urllib.parse import urlparse

from loguru import logger
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from hews import HNClient, Story


class StoryListItem(ListItem):
    """Selectable list row for a Hacker News story."""

    def __init__(self, story: Story, rank: int) -> None:
        super().__init__()
        self.story = story
        self.rank = rank

    def compose(self) -> ComposeResult:
        """Render title and metadata for the story row."""
        yield Label(self._title_text(), classes="story-title")
        yield Label(self._metadata_text(), classes="story-meta")

    def _title_text(self) -> str:
        title = self.story.title or "Untitled"
        domain = _short_domain(self.story.url)
        if domain:
            title = f"{title} ({domain})"
        return f"{self.rank}. {title}"

    def _metadata_text(self) -> str:
        score = self.story.score or 0
        comments = self.story.descendants or 0
        author = self.story.by or "unknown"
        age = self.story.age() if self.story.time else "unknown"
        return f"{score} points by {author} | {comments} comments | {age}"


class CommentsScreen(Screen[None]):
    """Placeholder story-detail screen until full comments support lands."""

    BINDINGS = [("escape", "back", "Back"), ("b", "back", "Back")]

    def __init__(self, story: Story) -> None:
        super().__init__()
        self.story = story

    def compose(self) -> ComposeResult:
        """Compose the placeholder comments screen."""
        yield Header()
        yield Static(self.story.title or "Untitled", id="story-title")
        yield Static(self._story_details(), id="story-details")
        yield Footer()

    def action_back(self) -> None:
        """Return to the story list."""
        self.app.pop_screen()

    def _story_details(self) -> str:
        score = self.story.score or 0
        comments = self.story.descendants or 0
        author = self.story.by or "unknown"
        return (
            f"{score} points by {author} | {comments} comments\n"
            "Full comments view will be implemented in issue #41."
        )


class StoryListScreen(Screen[None]):
    """Screen that displays either a Hacker News section or search results."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("enter", "open_selected", "Open", priority=True),
        Binding("right", "open_selected", "Open", priority=True),
        ("t", "switch_section('top')", "Top"),
        ("n", "switch_section('new')", "New"),
        ("a", "switch_section('ask')", "Ask"),
        ("s", "switch_section('show')", "Show"),
        ("J", "switch_section('jobs')", "Jobs"),
        ("/", "search", "Search"),
    ]

    def __init__(
        self,
        section: str = "top",
        search_query: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.section = section
        self.search_query = search_query
        self.stories: list[Story] = []
        self._load_id: object = None

    def compose(self) -> ComposeResult:
        """Compose the story-list screen."""
        yield Header()
        yield Static("Loading...", id="status")
        yield ListView(id="stories")
        yield Footer()

    async def on_mount(self) -> None:
        """Load the initial story set once the screen is ready."""
        await self.load_stories()

    async def action_refresh(self) -> None:
        """Refresh stories, bypassing the item cache."""
        await self.load_stories(force_refresh=True)

    async def load_stories(self, force_refresh: bool = False) -> None:
        """Fetch and display either search results or a section."""
        load_id = object()
        self._load_id = load_id

        status = self.query_one("#status", Static)
        stories_view = self.query_one("#stories", ListView)
        await stories_view.clear()
        self.stories = []

        try:
            if self.search_query:
                status.update(f"Search results for '{self.search_query}'")
                stories = await self.hews_app.hn_client.search(
                    self.search_query,
                    limit=30,
                )
            else:
                status.update(f"{self.section.capitalize()} stories")
                stories = await self.hews_app.hn_client.fetch_stories(
                    self.section,
                    limit=30,
                    force_refresh=force_refresh,
                )
        except Exception as exc:
            if self._load_id is load_id:
                status.update(f"Error loading stories: {exc}")
                logger.debug("Failed to load TUI stories: {}", exc)
            return

        if self._load_id is not load_id:
            return

        self.stories = stories
        await self.display_stories(stories)
        if not stories:
            status.update(f"{status.renderable} - no stories to show")
        elif self.hews_app.is_authenticated:
            status.update(f"{status.renderable} - logged in")

    async def display_stories(self, stories: list[Story]) -> None:
        """Populate the list with stories."""
        list_view = self.query_one("#stories", ListView)
        for idx, story in enumerate(stories, 1):
            await list_view.append(StoryListItem(story, idx))
        if stories:
            list_view.index = 0

    def selected_story(self) -> Story | None:
        """Return the currently highlighted story, if any."""
        list_view = self.query_one("#stories", ListView)
        if list_view.index is None:
            return None
        try:
            return self.stories[list_view.index]
        except IndexError:
            return None

    async def action_cursor_down(self) -> None:
        """Move the selection down."""
        self.query_one("#stories", ListView).action_cursor_down()

    async def action_cursor_up(self) -> None:
        """Move the selection up."""
        self.query_one("#stories", ListView).action_cursor_up()

    async def action_open_selected(self) -> None:
        """Open the selected story in the placeholder comments screen."""
        story = self.selected_story()
        if story is None:
            self.app.notify("No story selected.", title="Hews")
            return
        await self.app.push_screen(CommentsScreen(story))

    async def action_switch_section(self, section: str) -> None:
        """Switch the current list to another Hacker News section."""
        self.section = section
        self.search_query = None
        await self.load_stories(force_refresh=False)

    def action_search(self) -> None:
        """Notify that search UI will be handled by a later issue."""
        self.app.notify("Search UI coming soon.", title="Hews")

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Open a story when activated through keyboard or mouse."""
        event.stop()
        if isinstance(event.item, StoryListItem):
            await self.app.push_screen(CommentsScreen(event.item.story))

    def show_authenticated_status(self) -> None:
        """Reflect successful background login in the visible status line."""
        if not self.stories:
            return

        status = self.query_one("#status", Static)
        current = str(status.renderable)
        if "logged in" not in current and not current.startswith("Error "):
            status.update(f"{current} - logged in")

    @property
    def hews_app(self) -> "HewsApp":
        """Return the concrete Hews app instance for typed access."""
        return cast("HewsApp", self.app)


class HewsApp(App[None]):
    """Main Textual app for Hews."""

    CSS_PATH = "hews.tcss"
    TITLE = "Hews - Hacker News TUI"
    BINDINGS = [("?", "help", "Help"), ("q", "quit", "Quit")]

    def __init__(
        self,
        initial_section: Optional[str] = None,
        initial_search: Optional[str] = None,
        hn_client: Optional[HNClient] = None,
    ) -> None:
        super().__init__()
        self.initial_section = initial_section or "top"
        self.initial_search = initial_search
        self.hn_client = hn_client or HNClient()
        self._owns_client = hn_client is None
        self._login_task: asyncio.Task[None] | None = None
        self.is_authenticated = False

    async def on_mount(self) -> None:
        """Open the API client, start login if configured, and show the first view."""
        self.title = self.TITLE
        if self._owns_client:
            await self.hn_client.__aenter__()

        if os.environ.get("HN_USERNAME") and os.environ.get("HN_PASSWORD"):
            self._login_task = asyncio.create_task(self._login_from_env())

        await self.push_screen(
            StoryListScreen(
                section=self.initial_section,
                search_query=self.initial_search,
            )
        )

    async def on_unmount(self) -> None:
        """Close resources owned by the app."""
        if self._login_task and not self._login_task.done():
            self._login_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._login_task
        if self._owns_client:
            await self.hn_client.__aexit__(None, None, None)

    async def _login_from_env(self) -> None:
        """Authenticate from environment without blocking initial rendering."""
        try:
            self.is_authenticated = await self.hn_client.login_from_env()
            if self.is_authenticated:
                logger.info("Logged in to Hacker News")
                self._show_authenticated_status()
        except Exception as exc:
            self.is_authenticated = False
            logger.debug("Hacker News TUI login failed: {}", exc)

    def _show_authenticated_status(self) -> None:
        """Update the active story-list screen after background login completes."""
        active_screen = self.screen
        if isinstance(active_screen, StoryListScreen):
            active_screen.show_authenticated_status()

    def action_help(self) -> None:
        """Show a placeholder help message until the help overlay exists."""
        self.notify("Help overlay coming soon.", title="Hews")


def _short_domain(url: str | None) -> str:
    """Return a compact display domain for a story URL."""
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host
