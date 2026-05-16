"""Textual application for browsing Hacker News stories."""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Optional, cast

from loguru import logger
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from hews import HNClient, Story


class StoryListScreen(Screen[None]):
    """Screen that displays either a Hacker News section or search results."""

    BINDINGS = [("r", "refresh", "Refresh")]

    def __init__(
        self,
        section: str = "top",
        search_query: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.section = section
        self.search_query = search_query
        self.stories: list[Story] = []

    def compose(self) -> ComposeResult:
        """Compose the story-list screen."""
        yield Header()
        yield Static("Loading...", id="status")
        yield DataTable(id="stories")
        yield Footer()

    async def on_mount(self) -> None:
        """Load the initial story set once the screen is ready."""
        table = self.query_one("#stories", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Title", "Points", "Comments", "Author", "Age")
        await self.load_stories()

    async def action_refresh(self) -> None:
        """Refresh stories, bypassing the item cache."""
        await self.load_stories(force_refresh=True)

    async def load_stories(self, force_refresh: bool = False) -> None:
        """Fetch and display either search results or a section."""
        status = self.query_one("#status", Static)
        table = self.query_one("#stories", DataTable)
        table.clear()
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
            status.update(f"Error loading stories: {exc}")
            logger.debug("Failed to load TUI stories: {}", exc)
            return

        self.stories = stories
        self.display_stories(stories)
        if not stories:
            status.update(f"{status.renderable} - no stories found")
        elif self.hews_app.is_authenticated:
            status.update(f"{status.renderable} - logged in")

    def display_stories(self, stories: list[Story]) -> None:
        """Populate the table with stories."""
        table = self.query_one("#stories", DataTable)

        for idx, story in enumerate(stories, 1):
            table.add_row(
                str(idx),
                story.title or "Untitled",
                str(story.score or 0),
                str(story.descendants or 0),
                story.by or "unknown",
                story.age() if story.time else "unknown",
            )

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
