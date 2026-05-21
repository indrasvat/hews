"""Textual application for browsing Hacker News stories."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional, cast
from urllib.parse import urlparse

from loguru import logger
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from hews import HNClient, Comment, Story
from hews.models import ItemType

HEWS_BANNER_LINES = (
    " _   _  _____ __        __ ____  ",
    "| | | || ____|\\ \\      / // ___| ",
    "| |_| ||  _|   \\ \\ /\\ / / \\___ \\ ",
    "|  _  || |___   \\ V  V /   ___) |",
    "|_| |_||_____|   \\_/\\_/   |____/ ",
)
HEWS_BANNER_WIDTH = len(HEWS_BANNER_LINES[0])
MIN_BANNER_SCREEN_WIDTH = HEWS_BANNER_WIDTH + 4
MIN_BANNER_SCREEN_HEIGHT = 16


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
    local_by_user: bool = False


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
        if self.node.local_by_user:
            marker = f"{marker} (You)"
        state = " [dead]" if comment.dead else " [deleted]" if comment.deleted else ""
        return f"{toggle}{author}{marker} | {age}{state}"

    def _body_text(self) -> str:
        comment = self.node.comment
        if comment.deleted:
            return "[deleted]"
        if comment.dead:
            return "[dead]"
        return html_to_plain_text(comment.text or "").strip() or "[no text]"


class SearchDialog(ModalScreen[str | None]):
    """Modal prompt for entering a Hacker News search query."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        """Compose the search prompt."""
        yield Static("Search HN", id="search-title")
        yield Input(placeholder="Search HN: ", id="search-query")

    def on_mount(self) -> None:
        """Focus the query input when the dialog opens."""
        self.query_one("#search-query", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Close with a trimmed query, or cancel if it is empty."""
        event.stop()
        query = event.value.strip()
        self.dismiss(query or None)

    def action_cancel(self) -> None:
        """Dismiss the dialog without running a search."""
        self.dismiss(None)


class ReplyDialog(ModalScreen[str | None]):
    """Modal prompt for composing a Hacker News reply."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, target_label: str) -> None:
        super().__init__()
        self.target_label = target_label

    def compose(self) -> ComposeResult:
        """Compose the reply prompt."""
        yield Static(f"Reply to {self.target_label}", id="reply-title")
        yield Input(placeholder="Comment text: ", id="reply-text")

    def on_mount(self) -> None:
        """Focus the reply input when the dialog opens."""
        self.query_one("#reply-text", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Close with trimmed reply text, or cancel if it is empty."""
        event.stop()
        text = event.value.strip()
        self.dismiss(text or None)

    def action_cancel(self) -> None:
        """Dismiss the dialog without posting."""
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    """Modal reference for Hews keyboard shortcuts."""

    BINDINGS = [
        Binding("?", "close_help", "Close", priority=True),
        Binding("escape", "close_help", "Close", priority=True),
        Binding("q", "close_help", "Close", priority=True),
    ]

    HELP_TEXT = """Hews keyboard help

Navigation
  Up/Down or j/k        Move selection
  Enter or Right        Open story, expand/collapse comment thread
  Left, Esc, or b       Go back
  q                     Quit app

Sections
  t                     Top stories
  n                     New stories
  a                     Ask HN
  s                     Show HN
  Shift+j               Jobs
  r                     Refresh current section

Search
  /                     Search stories
  Esc                   Cancel search prompt

Interactions
  u                     Upvote selected story/comment (login required)
  c                     Comment on selected story/comment (login required)

Help
  ?                     Open or close this help
  Esc or q              Close this help
"""

    def compose(self) -> ComposeResult:
        """Compose the help dialog."""
        yield Static(self.HELP_TEXT, id="help-content")

    def action_close_help(self) -> None:
        """Close the help dialog."""
        self.dismiss(None)


class CommentsScreen(Screen[None]):
    """Story-detail screen with a nested Hacker News comment thread."""

    _interaction_in_progress: bool
    _pending_comment_id: int

    BINDINGS = [
        Binding("escape", "back", "Back", priority=True),
        Binding("left", "back", "Back", priority=True),
        Binding("b", "back", "Back", priority=True),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("u", "upvote_selected", "Upvote"),
        ("c", "comment_selected", "Comment"),
        Binding("enter", "toggle_comment", "Collapse/Expand", priority=True),
        Binding("right", "toggle_comment", "Collapse/Expand", priority=True),
    ]

    def __init__(self, story: Story) -> None:
        super().__init__()
        self.story = story
        self.comment_nodes: list[CommentNode] = []
        self.collapsed_comment_ids: set[int] = set()
        self._interaction_in_progress = False
        self._pending_comment_id = -1

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

    async def action_upvote_selected(self) -> None:
        """Upvote the selected comment, or the story when no comment is selected."""
        if self._interaction_in_progress:
            return
        if not self.hews_app.is_authenticated:
            self._show_action_status("Login required to upvote.")
            self.app.notify("Login required to upvote.", title="Hews")
            return

        selected = self._selected_comment_item()
        is_comment = selected is not None
        item_id = selected.node.comment.id if selected else self.story.id
        label = "comment" if is_comment else "story"

        self._interaction_in_progress = True
        self._show_action_status(f"Upvoting {label}...")
        try:
            upvoted = await self.hews_app.hn_client.upvote(item_id, is_comment)
        except Exception as exc:
            logger.debug("Failed to upvote {} {}: {}", label, item_id, exc)
            upvoted = False
        finally:
            self._interaction_in_progress = False

        if upvoted:
            self._show_action_status(f"Upvoted {label}.")
            self.app.notify(f"Upvoted {label}.", title="Hews")
        else:
            self._show_action_status(f"Failed to upvote {label}.")
            self.app.notify(f"Failed to upvote {label}.", title="Hews")

    async def action_comment_selected(self) -> None:
        """Open a reply prompt for the selected comment or story."""
        if self._interaction_in_progress:
            return
        if not self.hews_app.is_authenticated:
            self._show_action_status("Login required to comment.")
            self.app.notify("Login required to comment.", title="Hews")
            return

        selected = self._selected_comment_item()
        target_label = (
            f"comment by {selected.node.comment.by or 'unknown'}"
            if selected
            else "story"
        )
        await self.app.push_screen(
            ReplyDialog(target_label),
            lambda text: self._handle_reply_text(
                text,
                selected.node if selected else None,
            ),
        )

    async def _handle_reply_text(
        self,
        text: str | None,
        parent_node: CommentNode | None,
    ) -> None:
        """Post submitted reply text and update the local thread."""
        if text is None or self._interaction_in_progress:
            return

        parent_id = parent_node.comment.id if parent_node else self.story.id
        self._interaction_in_progress = True
        self._show_action_status("Posting comment...")
        try:
            posted = await self.hews_app.hn_client.post_comment(parent_id, text)
        except Exception as exc:
            logger.debug("Failed to post comment to {}: {}", parent_id, exc)
            posted = False
        finally:
            self._interaction_in_progress = False

        if not posted:
            self._show_action_status("Failed to post comment.")
            self.app.notify("Failed to post comment.", title="Hews")
            return

        new_node = self._new_pending_comment(parent_id, text)
        if parent_node:
            parent_node.replies.append(new_node)
            parent_node.comment.kids.append(new_node.comment.id)
            self.collapsed_comment_ids.discard(parent_node.comment.id)
        else:
            self.comment_nodes.append(new_node)
            self.story.kids.append(new_node.comment.id)

        self.story.descendants = (self.story.descendants or 0) + 1
        self.query_one("#story-header", Static).update(self._story_header())

        await self._rerender_and_select(new_node.comment.id)
        self._show_action_status("Comment posted.")
        self.app.notify("Comment posted.", title="Hews")

    async def _rerender_and_select(self, comment_id: int) -> None:
        """Rerender visible comments and select a specific comment."""
        comments_view = self.query_one("#comments", ListView)
        visible_comments = list(self._visible_comments())
        await self._render_comments(comments_view, visible_comments)
        index = next(
            (
                idx
                for idx, (node, _depth) in enumerate(visible_comments)
                if node.comment.id == comment_id
            ),
            None,
        )
        if index is not None:
            comments_view.index = index

    def _new_pending_comment(self, parent_id: int, text: str) -> CommentNode:
        """Create a local comment node after HN accepts the submitted text."""
        comment_id = self._pending_comment_id
        self._pending_comment_id -= 1
        username = os.environ.get("HN_USERNAME") or "You"
        return CommentNode(
            comment=Comment(
                id=comment_id,
                type=ItemType.COMMENT,
                parent=parent_id,
                by=username,
                text=text,
                time=dt.datetime.now(dt.timezone.utc),
            ),
            replies=[],
            local_by_user=True,
        )

    def _selected_comment_item(self) -> CommentListItem | None:
        """Return the highlighted comment row, if any."""
        comments_view = self.query_one("#comments", ListView)
        selected = comments_view.highlighted_child
        return selected if isinstance(selected, CommentListItem) else None

    def _show_action_status(self, message: str) -> None:
        """Update the comments status line with action feedback."""
        self.query_one("#comments-status", Static).update(message)

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
        ("escape", "back", "Back"),
        ("left", "back", "Back"),
        ("b", "back", "Back"),
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
        show_banner: bool = True,
    ) -> None:
        super().__init__()
        self.section = section
        self.search_query = search_query
        self.show_banner = show_banner
        self.stories: list[Story] = []
        self._load_id: object = None

    def compose(self) -> ComposeResult:
        """Compose the story-list screen."""
        yield Header()
        if self.show_banner:
            yield Static(render_startup_banner(), id="startup-banner")
        yield Static("Loading...", id="status")
        yield ListView(id="stories")
        yield Footer()

    async def on_mount(self) -> None:
        """Load the initial story set once the screen is ready."""
        self._sync_banner_visibility()
        await self.load_stories()

    def on_resize(self, _event: events.Resize) -> None:
        """Hide the banner before it can wrap or crowd small terminals."""
        self._sync_banner_visibility()

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
            if self.search_query:
                status.update(f"No results found for '{self.search_query}'")
            else:
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

    async def action_search(self) -> None:
        """Prompt for a query and push a search-results screen."""
        await self.app.push_screen(SearchDialog(), self._handle_search_query)

    async def _handle_search_query(self, query: str | None) -> None:
        """Open search results after the modal submits a non-empty query."""
        if query:
            await self.app.push_screen(
                StoryListScreen(
                    search_query=query,
                    show_banner=False,
                )
            )

    def action_back(self) -> None:
        """Return from search results, or exit when search is the only screen."""
        previous_screen = (
            self.app.screen_stack[-2] if len(self.app.screen_stack) > 1 else None
        )
        if isinstance(previous_screen, StoryListScreen):
            self.app.pop_screen()
        elif self.search_query:
            self.app.exit()

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

    def _sync_banner_visibility(self) -> None:
        """Keep the logo opt-in only when the pane can display it cleanly."""
        if not self.show_banner:
            return

        banner = self.query_one("#startup-banner", Static)
        banner.display = (
            self.size.width >= MIN_BANNER_SCREEN_WIDTH
            and self.size.height >= MIN_BANNER_SCREEN_HEIGHT
        )

    @property
    def hews_app(self) -> "HewsApp":
        """Return the concrete Hews app instance for typed access."""
        return cast("HewsApp", self.app)


class HewsApp(App[None]):
    """Main Textual app for Hews."""

    CSS_PATH = "hews.tcss"
    TITLE = "Hews - Hacker News TUI"
    BINDINGS = [Binding("?", "help", "Help"), Binding("q", "quit", "Quit")]

    def __init__(
        self,
        initial_section: Optional[str] = None,
        initial_search: Optional[str] = None,
        hn_client: Optional[HNClient] = None,
        show_banner: bool = True,
    ) -> None:
        super().__init__()
        self.initial_section = initial_section or "top"
        self.initial_search = initial_search
        self.hn_client = hn_client or HNClient()
        self.show_banner = show_banner
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
                show_banner=self.show_banner,
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

    async def action_help(self) -> None:
        """Show the keyboard shortcut reference."""
        await self.push_screen(HelpScreen())


def _short_domain(url: str | None) -> str:
    """Return a compact display domain for a story URL."""
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def render_startup_banner() -> Text:
    """Return the startup logo with scoped Rich spans and fixed-width rows."""
    banner = Text(no_wrap=True, overflow="crop")
    for index, line in enumerate(HEWS_BANNER_LINES):
        if index > 0:
            banner.append("\n")
        banner.append(line[:10], style="bold #ff6600")
        banner.append(line[10:26], style="bold white")
        banner.append(line[26:], style="bold #ff6600")
    banner.append("\n  Hacker News, distilled.", style="italic bright_black")
    return banner


def html_to_plain_text(html: str) -> str:
    """Convert Hacker News item/comment HTML to readable plain text."""
    parser = PlainTextHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.text()
