"""HNClient - Hacker News API client for fetching stories and items."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Union

import httpx

from .models import Comment, Story, item_from_json


class HNClientError(Exception):
    """Base exception for HNClient errors."""


class HNClient:
    """Asynchronous client for fetching data from the Hacker News API.

    This client handles fetching stories from different HN sections (top, new, etc.)
    and individual items (stories/comments) with concurrent requests for performance.
    """

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

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

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """Initialize HNClient.

        Args:
            http_client: Optional httpx.AsyncClient instance. If None, a new one
                        will be created with appropriate settings.
        """
        self._http_client = http_client
        self._owned_client = http_client is None

    async def __aenter__(self) -> "HNClient":
        """Async context manager entry."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._owned_client and self._http_client:
            await self._http_client.aclose()

    async def fetch_stories(self, section: str, limit: int = 30) -> List[Story]:
        """Fetch stories from a specific HN section.

        Args:
            section: HN section name ("top", "new", "ask", "show", "jobs")
            limit: Maximum number of stories to fetch (default: 30)

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

        try:
            # Fetch the list of story IDs for this section
            endpoint = self.SECTION_ENDPOINTS[section]
            response = await self._http_client.get(endpoint)
            response.raise_for_status()

            story_ids = response.json()
            if not story_ids:
                return []

            # Limit the number of stories to fetch
            story_ids = story_ids[:limit]

            # Fetch story details concurrently
            stories = await self._fetch_items_concurrent(story_ids)

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
            raise HNClientError(f"Network error fetching {section} stories: {e}") from e
        except Exception as e:
            raise HNClientError(
                f"Unexpected error fetching {section} stories: {e}"
            ) from e

    async def fetch_item(self, item_id: int) -> Union[Story, Comment]:
        """Fetch a single item (story or comment) by ID.

        Args:
            item_id: HN item ID

        Returns:
            Story or Comment object based on the item type

        Raises:
            HNClientError: If the API request fails or item doesn't exist
        """
        if not self._http_client:
            raise HNClientError("Client not initialized. Use as async context manager.")

        try:
            response = await self._http_client.get(f"/item/{item_id}.json")
            response.raise_for_status()

            item_data = response.json()
            if not item_data:
                raise HNClientError(f"Item {item_id} not found")

            return item_from_json(item_data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HNClientError(f"Item {item_id} not found") from e
            raise HNClientError(
                f"HTTP error fetching item {item_id}: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise HNClientError(f"Network error fetching item {item_id}: {e}") from e
        except Exception as e:
            raise HNClientError(f"Unexpected error fetching item {item_id}: {e}") from e

    async def _fetch_items_concurrent(
        self, item_ids: List[int]
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
                return await self.fetch_item(item_id)
            except HNClientError:
                # Log the error but don't fail the entire batch
                return None

        # Fetch all items concurrently
        tasks = [fetch_single_item(item_id) for item_id in item_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Filter out None results while preserving order
        return [item for item in results if item is not None]
