"""Textual application for browsing Hacker News stories."""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional, cast
from urllib.parse import urlparse

from loguru import logger
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from hews import HNClient, Comment, Story


class PlainTextHTMLParser(HTMLParser):
    """Convert the small HTML subset used by HN items into readable text."""

    _BLOCK_TAGS = {"p", "div", "pre", "tr", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record spacing and useful link targets for supported tags."""
        if tag == "pre":
            self._newline()
            self._in_pre = True
        elif tag in self._BLOCK_TAGS:
            self._newline()
            if tag == "li":
                self._parts.append("- ")
        elif tag == "br":
            self._newline()
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._parts.append(" ")
                self._parts.append(f"<{href}>")

    def handle_endtag(self, tag: str) -> None:
        """Close block tags with a visual break."""
        if tag in self._BLOCK_TAGS or tag == "br":
            self._newline()
        if tag == "pre":
            self._in_pre = False

    def handle_data(self, data: str) -> None:
        """Append text content, preserving preformatted spacing where useful."""
        if self._in_pre:
            self._parts.append(data)
            return

        collapsed = " ".join(data.split())
        if collapsed:
            if self._parts and not self._parts[-1].endswith(("\n", " ", "/")):
                self._parts.append(" ")
            self._parts.append(collapsed)

    def text(self) -> str:
        """Return normalized plain text."""
        lines = [line.rstrip() for line in "".join(self._parts).splitlines()]
        compact: list[str] = []
        previous_blank = False
        for line in lines:
            blank = not line.strip()
            if blank and previous_blank:
                continue
            compact.append(line)
            previous_blank = blank
        return "\n".join(compact).strip()

    def _newline(self) -> None:
        if self._parts and not self._parts[-1].endswith("\n"):
            self._parts.append("\n")


@dataclass(slots=True)
class CommentNode:
    """A fetched comment with its nested replies."""

    comment: Comment
    replies: list["CommentNode"]


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


class CommentListItem(ListItem):
    """Focusable nested comment row."""

    def __init__(
        self,
        node: CommentNode,
        depth: int,
        story_author: str | None,
        collapsed: bool = False,
    ) -> None:
        super().__init__()
        self.node = node
        self.depth = depth
        self.story_author = story_author
        self.collapsed = collapsed

    def compose(self) -> ComposeResult:
        """Render comment metadata and body."""
        self.styles.padding = (0, 1, 0, min(self.depth * 4, 24))
        yield Label(self._metadata_text(), classes="comment-meta")
        yield Static(self._body_text(), classes="comment-body")

    def _metadata_text(self) -> str:
        comment = self.node.comment
        author = comment.by or "unknown"
        age = comment.age() if comment.time else "unknown"
        toggle = ""
        if self.node.replies:
            toggle = "[+] " if self.collapsed else "[-] "
        marker = " [OP]" if author == self.story_author else ""
        state = " [dead]" if comment.dead else " [deleted]" if comment.deleted else ""
        return f"{toggle}{author}{marker} | {age}{state}"

    def _body_text(self) -> str:
        comment = self.node.comment
        if comment.deleted:
            return "[deleted]"
        if comment.dead:
            return "[dead]"
        return html_to_plain_text(comment.text or "").strip() or "[no text]"


class CommentsScreen(Screen[None]):
    """Story-detail screen with a nested Hacker News comment thread."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("left", "back", "Back"),
        ("b", "back", "Back"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("enter", "toggle_comment", "Collapse/Expand", priority=True),
        Binding("right", "toggle_comment", "Collapse/Expand", priority=True),
    ]

    def __init__(self, story: Story) -> None:
        super().__init__()
        self.story = story
        self.comment_nodes: list[CommentNode] = []
        self.collapsed_comment_ids: set[int] = set()

    def compose(self) -> ComposeResult:
        """Compose the comments screen."""
        yield Header()
        yield Static(self._story_header(), id="story-header")
        if self.story.text:
            yield Static(html_to_plain_text(self.story.text), id="story-text")
        yield Static("Loading comments...", id="comments-status")
        yield ListView(id="comments")
        yield Footer()

    async def on_mount(self) -> None:
        """Fetch and display comments after the screen is mounted."""
        await self.load_comments()

    async def load_comments(self) -> None:
        """Fetch all comments recursively and populate the list."""
        status = self.query_one("#comments-status", Static)
        comments_view = self.query_one("#comments", ListView)
        await comments_view.clear()

        if not self.story.kids:
            status.update("No comments.")
            return

        try:
            self.comment_nodes = await self._fetch_comment_nodes(self.story.kids)
        except Exception as exc:
            status.update(f"Error loading comments: {exc}")
            logger.debug("Failed to load comments for story {}: {}", self.story.id, exc)
            return

        flattened = list(self._visible_comments())
        await self._render_comments(comments_view, flattened)

        status.update(f"{len(flattened)} comments loaded")
        if flattened:
            comments_view.index = 0

    async def action_cursor_down(self) -> None:
        """Move the comment selection down."""
        self.query_one("#comments", ListView).action_cursor_down()

    async def action_cursor_up(self) -> None:
        """Move the comment selection up."""
        self.query_one("#comments", ListView).action_cursor_up()

    async def action_toggle_comment(self) -> None:
        """Collapse or expand the selected comment when it has replies."""
        comments_view = self.query_one("#comments", ListView)
        selected = comments_view.highlighted_child
        if not isinstance(selected, CommentListItem) or not selected.node.replies:
            return

        comment_id = selected.node.comment.id
        if comment_id in self.collapsed_comment_ids:
            self.collapsed_comment_ids.remove(comment_id)
        else:
            self.collapsed_comment_ids.add(comment_id)

        visible_comments = list(self._visible_comments())
        new_index = next(
            (
                index
                for index, (node, _depth) in enumerate(visible_comments)
                if node.comment.id == comment_id
            ),
            0,
        )
        await self._render_comments(comments_view, visible_comments)
        if visible_comments:
            comments_view.index = new_index

    def action_back(self) -> None:
        """Return to the story list."""
        self.app.pop_screen()

    async def _render_comments(
        self,
        comments_view: ListView,
        comments: list[tuple[CommentNode, int]],
    ) -> None:
        """Replace the list contents with the currently visible comments."""
        await comments_view.clear()
        for node, depth in comments:
            await comments_view.append(
                CommentListItem(
                    node,
                    depth,
                    self.story.by,
                    collapsed=node.comment.id in self.collapsed_comment_ids,
                )
            )

    async def _fetch_comment_nodes(self, comment_ids: list[int]) -> list[CommentNode]:
        """Fetch comment IDs and their children, preserving Hacker News order."""
        results = await asyncio.gather(
            *(self._fetch_comment_node(comment_id) for comment_id in comment_ids)
        )
        return [node for node in results if node is not None]

    async def _fetch_comment_node(self, comment_id: int) -> CommentNode | None:
        """Fetch a single comment and its replies."""
        try:
            item = await self.hews_app.hn_client.fetch_item(comment_id)
        except Exception as exc:
            logger.debug("Skipping comment {} after fetch error: {}", comment_id, exc)
            return None

        if not isinstance(item, Comment):
            return None

        replies = await self._fetch_comment_nodes(item.kids) if item.kids else []
        return CommentNode(comment=item, replies=replies)

    def _flatten_comments(
        self, nodes: list[CommentNode], depth: int = 0
    ) -> list[tuple[CommentNode, int]]:
        """Return comments in depth-first display order."""
        flattened: list[tuple[CommentNode, int]] = []
        for node in nodes:
            flattened.append((node, depth))
            flattened.extend(self._flatten_comments(node.replies, depth + 1))
        return flattened

    def _visible_comments(
        self, nodes: list[CommentNode] | None = None, depth: int = 0
    ) -> list[tuple[CommentNode, int]]:
        """Return comments in display order, excluding collapsed descendants."""
        visible: list[tuple[CommentNode, int]] = []
        for node in self.comment_nodes if nodes is None else nodes:
            visible.append((node, depth))
            if node.comment.id not in self.collapsed_comment_ids:
                visible.extend(self._visible_comments(node.replies, depth + 1))
        return visible

    @property
    def hews_app(self) -> "HewsApp":
        """Return the concrete Hews app instance for typed access."""
        return cast("HewsApp", self.app)

    def _story_header(self) -> str:
        score = self.story.score or 0
        comments = self.story.descendants or 0
        author = self.story.by or "unknown"
        age = self.story.age() if self.story.time else "unknown"
        title = self.story.title or "Untitled"
        domain = _short_domain(self.story.url)
        if domain:
            title = f"{title} ({domain})"
        return (
            f"{title}\n"
            f"{score} points by {author} | {comments} comments | {age}"
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


def html_to_plain_text(html: str) -> str:
    """Convert Hacker News item/comment HTML to readable plain text."""
    parser = PlainTextHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.text()
