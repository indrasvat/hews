"""Textual application for browsing Hacker News stories."""

from __future__ import annotations

from typing import Optional

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header, Static
from loguru import logger

from hews import HNClient, Story


class HewsApp(App[None]):
    """Minimal Textual app for displaying HN story lists."""

    TITLE = "Hews"
    BINDINGS = [("r", "refresh", "Refresh"), ("q", "quit", "Quit")]

    def __init__(
        self,
        initial_section: Optional[str] = None,
        initial_search: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.initial_section = initial_section or "top"
        self.initial_search = initial_search

    def compose(self) -> ComposeResult:
        """Compose the story-list screen."""
        yield Header()
        yield Static("Loading...", id="status")
        yield DataTable(id="stories")
        yield Footer()

    async def on_mount(self) -> None:
        """Load the initial story set once Textual is ready."""
        table = self.query_one("#stories", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Title", "Points", "Comments", "Author", "Age")
        await self.load_stories()

    async def load_stories(self, force_refresh: bool = False) -> None:
        """Fetch and display either initial search results or a section."""
        status = self.query_one("#status", Static)
        table = self.query_one("#stories", DataTable)
        table.clear()

        try:
            async with HNClient() as client:
                logged_in = await client.login_from_env()
                if logged_in:
                    logger.info("Logged in to Hacker News")
                if self.initial_search:
                    status.update(f"Search results for '{self.initial_search}'")
                    stories = await client.search(self.initial_search, limit=30)
                else:
                    status.update(f"{self.initial_section.capitalize()} stories")
                    stories = await client.fetch_stories(
                        self.initial_section,
                        limit=30,
                        force_refresh=force_refresh,
                    )

            self.display_stories(stories)
            if not stories:
                status.update(f"{status.renderable} - no stories found")
            elif logged_in:
                status.update(f"{status.renderable} - logged in")
        except Exception as exc:
            status.update(f"Error loading stories: {exc}")

    async def action_refresh(self) -> None:
        """Refresh stories, bypassing the item cache."""

        await self.load_stories(force_refresh=True)

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
