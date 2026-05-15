"""HNClient - Hacker News API client for fetching stories and items."""

from __future__ import annotations

import asyncio
import datetime
import os
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Union

import httpx
from loguru import logger

from .cache import CacheManager
from .models import Comment, Story, ItemType, item_from_json


class HNClientError(Exception):
    """Base exception for HNClient errors."""


class _HiddenInputParser(HTMLParser):
    """Collect hidden values from the form that accepts HN credentials."""

    def __init__(self) -> None:
        super().__init__()
        self._current_form: tuple[Dict[str, str], set[str]] | None = None
        self.values: Dict[str, str] = {}

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "form":
            self._current_form = ({}, set())
            return

        if tag != "input":
            return
        attr_map = {name: value or "" for name, value in attrs}
        name = attr_map.get("name")
        if not name or self._current_form is None:
            return

        hidden_values, input_names = self._current_form
        input_names.add(name)
        if attr_map.get("type") == "hidden":
            hidden_values[name] = attr_map.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag != "form" or self._current_form is None:
            return

        hidden_values, input_names = self._current_form
        if (
            {"acct", "pw"}.issubset(input_names)
            and "creating" not in hidden_values
            and not self.values
        ):
            self.values = hidden_values
        self._current_form = None


class HNClient:
    """Asynchronous client for fetching data from the Hacker News API.

    This client handles fetching stories from different HN sections (top, new, etc.),
    individual items (stories/comments) with concurrent requests for performance,
    and search functionality via the Algolia API.
    """

    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    ALGOLIA_BASE_URL = "https://hn.algolia.com/api/v1"
    HN_WEB_BASE_URL = "https://news.ycombinator.com"
    CACHE_TTL_SECONDS = 30 * 60

    # HN API endpoints for different story sections
    SECTION_ENDPOINTS = {
        "top": "/topstories.json",
        "new": "/newstories.json",
        "best": "/beststories.json",
        "ask": "/askstories.json",
        "show": "/showstories.json",
        "job": "/jobstories.json",
        "jobs": "/jobstories.json",  # alias
    }

    def __init__(
        self,
        http_client: Optional[httpx.AsyncClient] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        """Initialize HNClient.

        Args:
            http_client: Optional httpx.AsyncClient instance. If None, a new one
                        will be created with appropriate settings.
            cache_manager: Optional CacheManager instance. If None, a default
                           SQLite cache will be created.
        """
        self._http_client = http_client
        self._algolia_client: Optional[httpx.AsyncClient] = None
        self._owned_client = http_client is None
        self._cache_manager = cache_manager or CacheManager()
        self.is_authenticated = False

    async def __aenter__(self) -> "HNClient":
        """Async context manager entry."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        if self._algolia_client is None:
            self._algolia_client = httpx.AsyncClient(
                base_url=self.ALGOLIA_BASE_URL,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self

    async def login(self, username: str, password: str) -> bool:
        """Authenticate with Hacker News and keep the session cookie in memory.

        Args:
            username: Hacker News username.
            password: Hacker News password.

        Returns:
            True when HN sets a session cookie, otherwise False.

        Raises:
            HNClientError: If the client has not been initialized.
        """
        if not self._http_client:
            raise HNClientError("Client not initialized. Use as async context manager.")

        if not username or not password:
            return False

        try:
            login_url = f"{self.HN_WEB_BASE_URL}/login"
            login_page = await self._http_client.get(login_url)
            login_page.raise_for_status()

            hidden_fields = self._parse_hidden_inputs(login_page.text)
            fnid = hidden_fields.get("fnid")
            if not fnid:
                logger.debug("HN login form did not include fnid")
                return False

            form_data = {
                **hidden_fields,
                "acct": username,
                "pw": password,
                "goto": hidden_fields.get("goto", "news"),
            }
            response = await self._http_client.post(login_url, data=form_data)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.debug("HN login request failed: {}", exc)
            self.is_authenticated = False
            return False

        self.is_authenticated = self._has_hn_user_cookie()
        if not self.is_authenticated:
            logger.debug("HN login failed for user {}", username)
        return self.is_authenticated

    async def login_from_env(self) -> bool:
        """Log in with HN_USERNAME/HN_PASSWORD when both are present."""
        username = os.environ.get("HN_USERNAME")
        password = os.environ.get("HN_PASSWORD")
        if not username or not password:
            return False
        return await self.login(username, password)

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._owned_client:
            if self._http_client:
                await self._http_client.aclose()
            if self._algolia_client:
                await self._algolia_client.aclose()

    def _parse_hidden_inputs(self, html: str) -> Dict[str, str]:
        parser = _HiddenInputParser()
        parser.feed(html)
        return parser.values

    def _has_hn_user_cookie(self) -> bool:
        if not self._http_client:
            return False
        return self._http_client.cookies.get("user") is not None

    async def fetch_stories(
        self, section: str, limit: int = 30, force_refresh: bool = False
    ) -> List[Story]:
        """Fetch stories from a specific HN section.

        Args:
            section: HN section name ("top", "new", "ask", "show", "jobs")
            limit: Maximum number of stories to fetch (default: 30)
            force_refresh: Bypass cached item details when fetching stories

        Returns:
            List of Story objects sorted by rank

        Raises:
            HNClientError: If the API request fails or section is invalid
        """
        if not self._http_client:
            raise HNClientError("Client not initialized. Use as async context manager.")

        # Validate section
        if section not in self.SECTION_ENDPOINTS:
            valid_sections = ", ".join(self.SECTION_ENDPOINTS.keys())
            raise HNClientError(
                f"Invalid section '{section}'. Valid sections: {valid_sections}"
            )

        endpoint = self.SECTION_ENDPOINTS[section]

        try:
            response = await self._http_client.get(endpoint)
            response.raise_for_status()

            story_ids = response.json()
            if not story_ids:
                return []

            self._save_section_story_ids(section, story_ids)
            story_ids = story_ids[:limit]

            stories = await self._fetch_items_concurrent(
                story_ids, force_refresh=force_refresh
            )

            # Filter to only Story objects and preserve order
            story_objects = []
            for item in stories:
                if isinstance(item, Story):
                    story_objects.append(item)

            return story_objects

        except httpx.HTTPStatusError as e:
            raise HNClientError(
                f"HTTP error fetching {section} stories: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            logger.debug("Falling back to cached {} stories: {}", section, e)
            cached_stories = self._get_cached_section_stories(section, limit)
            if cached_stories:
                return cached_stories
            raise HNClientError(f"Network error fetching {section} stories: {e}") from e
        except Exception as e:
            raise HNClientError(
                f"Unexpected error fetching {section} stories: {e}"
            ) from e

    async def fetch_item(
        self, item_id: int, force_refresh: bool = False
    ) -> Union[Story, Comment]:
        """Fetch a single item (story or comment) by ID.

        Args:
            item_id: HN item ID
            force_refresh: Bypass the cache and fetch from the API

        Returns:
            Story or Comment object based on the item type

        Raises:
            HNClientError: If the API request fails or item doesn't exist
        """
        if not self._http_client:
            raise HNClientError("Client not initialized. Use as async context manager.")

        cached_item = self._get_cached_item(item_id)
        if not force_refresh:
            fresh_item = self._get_fresh_cached_item(item_id)
            if fresh_item is not None:
                return fresh_item

        try:
            response = await self._http_client.get(f"/item/{item_id}.json")
            response.raise_for_status()

            item_data = response.json()
            if not item_data:
                raise HNClientError(f"Item {item_id} not found")

            item = item_from_json(item_data)
            try:
                self._cache_manager.save_item(item)
                logger.debug("Saved item {} to cache", item_id)
            except Exception:
                # A local cache problem must not turn a successful API fetch into
                # a failed item load.
                pass
            return item

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HNClientError(f"Item {item_id} not found") from e
            raise HNClientError(
                f"HTTP error fetching item {item_id}: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            if cached_item is not None:
                logger.debug(
                    "Serving stale cached item {} after network error", item_id
                )
                return cached_item
            raise HNClientError(f"Network error fetching item {item_id}: {e}") from e
        except HNClientError:
            raise
        except Exception as e:
            raise HNClientError(f"Unexpected error fetching item {item_id}: {e}") from e

    async def _fetch_items_concurrent(
        self, item_ids: List[int], force_refresh: bool = False
    ) -> List[Union[Story, Comment]]:
        """Fetch multiple items concurrently.

        Args:
            item_ids: List of HN item IDs

        Returns:
            List of Story/Comment objects in the same order as item_ids
        """

        async def fetch_single_item(item_id: int) -> Optional[Union[Story, Comment]]:
            """Fetch a single item, returning None if it fails."""
            try:
                return await self.fetch_item(item_id, force_refresh=force_refresh)
            except HNClientError:
                # Log the error but don't fail the entire batch
                return None

        # Fetch all items concurrently
        tasks = [fetch_single_item(item_id) for item_id in item_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Filter out None results while preserving order
        return [item for item in results if item is not None]

    def _get_cached_item(self, item_id: int) -> Union[Story, Comment] | None:
        try:
            return self._cache_manager.get_item(item_id)
        except Exception as exc:
            logger.debug("Failed to read item {} from cache: {}", item_id, exc)
            return None

    def _get_fresh_cached_item(self, item_id: int) -> Union[Story, Comment] | None:
        try:
            item = self._cache_manager.get_fresh_item(item_id, self.CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.debug("Failed to read fresh item {} from cache: {}", item_id, exc)
            return None
        if item is not None:
            logger.debug("Serving item {} from cache", item_id)
        return item

    def _save_section_story_ids(self, section: str, story_ids: List[int]) -> None:
        cache_key = self._section_cache_key(section)
        try:
            self._cache_manager.save_story_ids(cache_key, story_ids)
            logger.debug(
                "Saved {} story IDs for {} to cache", len(story_ids), cache_key
            )
        except Exception as exc:
            logger.debug("Failed to cache story IDs for {}: {}", cache_key, exc)

    def _get_cached_section_stories(self, section: str, limit: int) -> List[Story]:
        cache_key = self._section_cache_key(section)
        try:
            story_ids = self._cache_manager.get_story_ids(cache_key)[:limit]
        except Exception as exc:
            logger.debug("Failed to read cached story IDs for {}: {}", cache_key, exc)
            return []

        stories: List[Story] = []
        for story_id in story_ids:
            item = self._get_cached_item(story_id)
            if isinstance(item, Story):
                stories.append(item)
        if stories:
            logger.debug("Serving {} cached {} stories", len(stories), cache_key)
        return stories

    def _section_cache_key(self, section: str) -> str:
        if section == "jobs":
            return "job"
        return section

    async def search(self, query: str, limit: int = 30) -> List[Story]:
        """Search for stories using the Algolia Search API.

        Args:
            query: Search query string
            limit: Maximum number of stories to return (default: 30)

        Returns:
            List of Story objects matching the search query

        Raises:
            HNClientError: If the API request fails
        """
        if not self._algolia_client:
            raise HNClientError("Client not initialized. Use as async context manager.")

        if not query or not query.strip():
            return []

        try:
            # Build query parameters
            params = {
                "query": query,
                "tags": "story",  # Only search for stories, not comments
                "hitsPerPage": str(limit),
            }

            # Make the search request
            response = await self._algolia_client.get("/search", params=params)
            response.raise_for_status()

            data = response.json()
            hits = data.get("hits", [])

            # Convert Algolia hits to Story objects
            stories = []
            for hit in hits:
                story = self._algolia_hit_to_story(hit)
                if story:
                    stories.append(story)

            return stories

        except httpx.HTTPStatusError as e:
            raise HNClientError(
                f"HTTP error searching for '{query}': {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise HNClientError(f"Network error searching for '{query}': {e}") from e
        except Exception as e:
            raise HNClientError(f"Unexpected error searching for '{query}': {e}") from e

    def _algolia_hit_to_story(self, hit: Dict[str, Any]) -> Optional[Story]:
        """Convert an Algolia search hit to a Story object.

        Args:
            hit: Algolia search hit dictionary

        Returns:
            Story object or None if conversion fails
        """
        try:
            # Extract the story ID from objectID
            story_id = int(hit.get("objectID", 0))
            if not story_id:
                return None

            # Parse timestamp
            created_at = hit.get("created_at_i")
            if created_at:
                time = datetime.datetime.fromtimestamp(
                    created_at, datetime.timezone.utc
                )
            else:
                time = datetime.datetime.now(datetime.timezone.utc)

            # Create Story object with available fields
            return Story(
                id=story_id,
                type=ItemType.STORY,
                by=hit.get("author"),
                time=time,
                title=hit.get("title"),
                url=hit.get("url"),
                score=hit.get("points"),
                descendants=hit.get("num_comments"),
                kids=[],  # Algolia doesn't provide kids in search results
                text=hit.get("story_text"),  # May be None
            )
        except (ValueError, TypeError, KeyError):
            # Log error but don't fail the entire search
            return None
