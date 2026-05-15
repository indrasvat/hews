"""Tests for hews.client.HNClient."""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from hews.client import HNClient, HNClientError
from hews.cache import CacheManager
from hews.models import Comment, ItemType, Story


# Test data fixtures
STORY_IDS_RESPONSE = [123, 456, 789]

STORY_JSON_RESPONSE = {
    "id": 123,
    "type": "story",
    "by": "testuser",
    "time": 1700000000,
    "title": "Test Story",
    "url": "https://example.com",
    "score": 42,
    "descendants": 10,
    "kids": [456],
}

COMMENT_JSON_RESPONSE = {
    "id": 456,
    "type": "comment",
    "by": "commenter",
    "time": 1700000100,
    "text": "Test comment",
    "parent": 123,
    "kids": [],
}

ALGOLIA_SEARCH_RESPONSE = {
    "hits": [
        {
            "objectID": "123",
            "title": "Python is great",
            "url": "https://example.com/python",
            "author": "pythonista",
            "points": 100,
            "num_comments": 25,
            "created_at_i": 1700000000,
            "story_text": None,
        },
        {
            "objectID": "456",
            "title": "Learning Python",
            "url": "https://example.org/learn",
            "author": "teacher",
            "points": 50,
            "num_comments": 10,
            "created_at_i": 1700000100,
            "story_text": "A guide to learning Python",
        },
    ],
    "nbHits": 2,
    "page": 0,
    "hitsPerPage": 30,
}


class TestHNClient:
    """Test suite for HNClient class."""

    @pytest.fixture
    def mock_client(self, tmp_path):
        """Create an HNClient with a mocked httpx client."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        client = HNClient(
            http_client=mock_http,
            cache_manager=CacheManager(tmp_path / "cache.db"),
        )
        client._http_client = mock_http
        return client

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test that HNClient works as async context manager."""
        async with HNClient() as client:
            assert client._http_client is not None
            assert isinstance(client._http_client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_fetch_stories_success(self, mock_client):
        """Test successful story fetching."""
        # Mock the story IDs response
        ids_response = Mock()
        ids_response.json.return_value = STORY_IDS_RESPONSE
        ids_response.raise_for_status.return_value = None

        # Mock individual story responses
        story_response = Mock()
        story_response.json.return_value = STORY_JSON_RESPONSE
        story_response.raise_for_status.return_value = None

        mock_client._http_client.get.side_effect = [
            ids_response,  # First call for story IDs
            story_response,  # Subsequent calls for story details
            story_response,
            story_response,
        ]

        stories = await mock_client.fetch_stories("top", limit=3)

        assert len(stories) == 3
        assert all(isinstance(story, Story) for story in stories)
        assert stories[0].id == 123
        assert stories[0].title == "Test Story"

        # Verify correct API calls were made
        mock_client._http_client.get.assert_any_call("/topstories.json")
        mock_client._http_client.get.assert_any_call("/item/123.json")

    @pytest.mark.asyncio
    async def test_fetch_stories_uses_cached_story_details(self, mock_client):
        """Fresh cached story details avoid per-item network calls."""
        story = Story(
            id=123,
            type=ItemType.STORY,
            by="testuser",
            title="Cached Story",
            score=42,
            descendants=10,
        )
        mock_client._cache_manager.save_item(story)

        ids_response = Mock()
        ids_response.json.return_value = [123]
        ids_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = ids_response

        stories = await mock_client.fetch_stories("top", limit=1)

        assert len(stories) == 1
        assert stories[0].id == story.id
        assert stories[0].title == story.title
        mock_client._http_client.get.assert_called_once_with("/topstories.json")

    @pytest.mark.asyncio
    async def test_fetch_stories_falls_back_to_cached_section_when_offline(
        self, mock_client
    ):
        """Cached section IDs and items are used if latest IDs cannot load."""
        story = Story(id=123, type=ItemType.STORY, title="Cached Story")
        mock_client._cache_manager.save_story_ids("top", [123])
        mock_client._cache_manager.save_item(story)
        mock_client._http_client.get.side_effect = httpx.RequestError(
            "Connection failed"
        )

        stories = await mock_client.fetch_stories("top", limit=1)

        assert len(stories) == 1
        assert stories[0].id == story.id
        assert stories[0].title == story.title

    @pytest.mark.asyncio
    async def test_fetch_stories_invalid_section(self, mock_client):
        """Test fetch_stories with invalid section name."""
        with pytest.raises(HNClientError, match="Invalid section 'invalid'"):
            await mock_client.fetch_stories("invalid")

    @pytest.mark.asyncio
    async def test_fetch_stories_http_error(self, mock_client):
        """Test fetch_stories with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=AsyncMock(), response=AsyncMock(status_code=404)
        )
        mock_client._http_client.get.return_value = mock_response

        with pytest.raises(HNClientError, match="HTTP error fetching top stories: 404"):
            await mock_client.fetch_stories("top")

    @pytest.mark.asyncio
    async def test_fetch_stories_network_error(self, mock_client):
        """Test fetch_stories with network error."""
        mock_client._http_client.get.side_effect = httpx.RequestError(
            "Connection failed"
        )

        with pytest.raises(HNClientError, match="Network error fetching top stories"):
            await mock_client.fetch_stories("top")

    @pytest.mark.asyncio
    async def test_fetch_item_story_success(self, mock_client):
        """Test successful single item (story) fetching."""
        mock_response = Mock()
        mock_response.json.return_value = STORY_JSON_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = mock_response

        item = await mock_client.fetch_item(123)

        assert isinstance(item, Story)
        assert item.id == 123
        assert item.title == "Test Story"
        assert mock_client._cache_manager.get_item(123) == item

        mock_client._http_client.get.assert_called_with("/item/123.json")

    @pytest.mark.asyncio
    async def test_fetch_item_uses_fresh_cache(self, mock_client):
        """Fresh cached items are returned without a network request."""
        story = Story(id=123, type=ItemType.STORY, title="Cached Story")
        mock_client._cache_manager.save_item(story)

        item = await mock_client.fetch_item(123)

        assert isinstance(item, Story)
        assert item.id == story.id
        assert item.title == story.title
        mock_client._http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_item_refetches_stale_cache(self, mock_client, tmp_path):
        """Stale cached items are refreshed from the API."""
        story = Story(id=123, type=ItemType.STORY, title="Cached Story")
        mock_client._cache_manager.save_item(story)
        with sqlite3.connect(tmp_path / "cache.db") as conn:
            conn.execute(
                "UPDATE items SET fetched_at = ? WHERE id = 123",
                (int(time.time()) - HNClient.CACHE_TTL_SECONDS - 1,),
            )

        mock_response = Mock()
        mock_response.json.return_value = STORY_JSON_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = mock_response

        item = await mock_client.fetch_item(123)

        assert isinstance(item, Story)
        assert item.title == "Test Story"
        mock_client._http_client.get.assert_called_once_with("/item/123.json")

    @pytest.mark.asyncio
    async def test_fetch_item_force_refresh_bypasses_cache(self, mock_client):
        """force_refresh fetches from the API even when cache is fresh."""
        story = Story(id=123, type=ItemType.STORY, title="Cached Story")
        mock_client._cache_manager.save_item(story)
        mock_response = Mock()
        mock_response.json.return_value = STORY_JSON_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = mock_response

        item = await mock_client.fetch_item(123, force_refresh=True)

        assert isinstance(item, Story)
        assert item.title == "Test Story"
        mock_client._http_client.get.assert_called_once_with("/item/123.json")

    @pytest.mark.asyncio
    async def test_fetch_item_returns_stale_cache_when_offline(
        self, mock_client, tmp_path
    ):
        """Network failures fall back to stale cached items."""
        story = Story(id=123, type=ItemType.STORY, title="Cached Story")
        mock_client._cache_manager.save_item(story)
        with sqlite3.connect(tmp_path / "cache.db") as conn:
            conn.execute("UPDATE items SET fetched_at = 1 WHERE id = 123")
        mock_client._http_client.get.side_effect = httpx.RequestError(
            "Connection failed"
        )

        item = await mock_client.fetch_item(123)

        assert isinstance(item, Story)
        assert item.id == story.id
        assert item.title == story.title

    @pytest.mark.asyncio
    async def test_fetch_item_returns_item_when_cache_write_fails(self, mock_client):
        """Test cache write failures do not fail successful item fetches."""
        mock_response = Mock()
        mock_response.json.return_value = STORY_JSON_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = mock_response
        mock_client._cache_manager.save_item = Mock(
            side_effect=sqlite3.OperationalError("database is locked")
        )

        item = await mock_client.fetch_item(123)

        assert isinstance(item, Story)
        assert item.id == 123
        mock_client._cache_manager.save_item.assert_called_once_with(item)

    @pytest.mark.asyncio
    async def test_fetch_item_comment_success(self, mock_client):
        """Test successful single item (comment) fetching."""
        mock_response = Mock()
        mock_response.json.return_value = COMMENT_JSON_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = mock_response

        item = await mock_client.fetch_item(456)

        assert isinstance(item, Comment)
        assert item.id == 456
        assert item.parent == 123

    @pytest.mark.asyncio
    async def test_fetch_item_not_found(self, mock_client):
        """Test fetch_item with non-existent item."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=AsyncMock(), response=AsyncMock(status_code=404)
        )
        mock_client._http_client.get.return_value = mock_response

        with pytest.raises(HNClientError, match="Item 999 not found"):
            await mock_client.fetch_item(999)

    @pytest.mark.asyncio
    async def test_fetch_item_empty_response(self, mock_client):
        """Test fetch_item with empty/null response."""
        mock_response = Mock()
        mock_response.json.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = mock_response

        with pytest.raises(HNClientError, match="Item 123 not found"):
            await mock_client.fetch_item(123)

    @pytest.mark.asyncio
    async def test_client_not_initialized_error(self):
        """Test operations on uninitialized client."""
        client = HNClient()

        with pytest.raises(HNClientError, match="Client not initialized"):
            await client.fetch_stories("top")

        with pytest.raises(HNClientError, match="Client not initialized"):
            await client.fetch_item(123)

    @pytest.mark.asyncio
    async def test_section_aliases(self, mock_client):
        """Test that section aliases work correctly."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_client._http_client.get.return_value = mock_response

        # Test that "jobs" alias works the same as "job"
        await mock_client.fetch_stories("jobs")
        mock_client._http_client.get.assert_called_with("/jobstories.json")

    @pytest.mark.asyncio
    async def test_concurrent_fetching_with_failures(self, mock_client):
        """Test that concurrent fetching handles individual item failures gracefully."""
        # Mock story IDs response
        ids_response = Mock()
        ids_response.json.return_value = [123, 456, 789]  # 3 items
        ids_response.raise_for_status.return_value = None

        # Mock individual item responses - one success, one failure, one success
        success_response = Mock()
        success_response.json.return_value = STORY_JSON_RESPONSE
        success_response.raise_for_status.return_value = None

        failure_response = Mock()
        failure_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=AsyncMock(), response=AsyncMock(status_code=404)
        )

        mock_client._http_client.get.side_effect = [
            ids_response,  # Story IDs
            success_response,  # Item 123 - success
            failure_response,  # Item 456 - failure
            success_response,  # Item 789 - success
        ]

        stories = await mock_client.fetch_stories("top", limit=3)

        # Should return 2 stories (failures filtered out)
        assert len(stories) == 2
        assert all(isinstance(story, Story) for story in stories)

    @pytest.mark.asyncio
    async def test_search_success(self, mock_client):
        """Test successful story search via Algolia."""
        # Setup Algolia client mock
        mock_algolia = AsyncMock(spec=httpx.AsyncClient)
        mock_client._algolia_client = mock_algolia

        # Mock the search response
        mock_response = Mock()
        mock_response.json.return_value = ALGOLIA_SEARCH_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_algolia.get.return_value = mock_response

        # Perform search
        stories = await mock_client.search("python", limit=30)

        # Verify results
        assert len(stories) == 2
        assert all(isinstance(story, Story) for story in stories)

        # Check first story
        assert stories[0].id == 123
        assert stories[0].title == "Python is great"
        assert stories[0].by == "pythonista"
        assert stories[0].score == 100
        assert stories[0].descendants == 25

        # Check second story
        assert stories[1].id == 456
        assert stories[1].text == "A guide to learning Python"

        # Verify correct API call
        mock_algolia.get.assert_called_once_with(
            "/search",
            params={"query": "python", "tags": "story", "hitsPerPage": "30"},
        )

    @pytest.mark.asyncio
    async def test_search_empty_query(self, mock_client):
        """Test search with empty query."""
        mock_client._algolia_client = AsyncMock(spec=httpx.AsyncClient)

        # Empty query should return empty list without making API call
        stories = await mock_client.search("")
        assert stories == []

        stories = await mock_client.search("   ")
        assert stories == []

        # Should not have made any API calls
        mock_client._algolia_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_no_results(self, mock_client):
        """Test search with no results."""
        mock_algolia = AsyncMock(spec=httpx.AsyncClient)
        mock_client._algolia_client = mock_algolia

        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {"hits": [], "nbHits": 0}
        mock_response.raise_for_status.return_value = None
        mock_algolia.get.return_value = mock_response

        stories = await mock_client.search("xyzabc123unlikely")
        assert stories == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, mock_client):
        """Test search with HTTP error."""
        mock_algolia = AsyncMock(spec=httpx.AsyncClient)
        mock_client._algolia_client = mock_algolia

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=AsyncMock(), response=AsyncMock(status_code=400)
        )
        mock_algolia.get.return_value = mock_response

        with pytest.raises(HNClientError, match="HTTP error searching"):
            await mock_client.search("test")

    @pytest.mark.asyncio
    async def test_search_network_error(self, mock_client):
        """Test search with network error."""
        mock_algolia = AsyncMock(spec=httpx.AsyncClient)
        mock_client._algolia_client = mock_algolia

        mock_algolia.get.side_effect = httpx.RequestError("Connection failed")

        with pytest.raises(HNClientError, match="Network error searching"):
            await mock_client.search("test")

    @pytest.mark.asyncio
    async def test_search_not_initialized(self):
        """Test search on uninitialized client."""
        client = HNClient()

        with pytest.raises(HNClientError, match="Client not initialized"):
            await client.search("test")

    @pytest.mark.asyncio
    async def test_search_invalid_hit_data(self, mock_client):
        """Test search with malformed hit data."""
        mock_algolia = AsyncMock(spec=httpx.AsyncClient)
        mock_client._algolia_client = mock_algolia

        # Mock response with one valid and one invalid hit
        mock_response = Mock()
        mock_response.json.return_value = {
            "hits": [
                {
                    "objectID": "123",
                    "title": "Valid story",
                    "author": "user1",
                    "points": 10,
                    "num_comments": 5,
                    "created_at_i": 1700000000,
                },
                {
                    # Missing objectID - should be skipped
                    "title": "Invalid story",
                },
                {
                    "objectID": "not_a_number",  # Invalid ID format
                    "title": "Another invalid",
                },
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_algolia.get.return_value = mock_response

        stories = await mock_client.search("test")

        # Should only return the valid story
        assert len(stories) == 1
        assert stories[0].id == 123
        assert stories[0].title == "Valid story"


class TestHNClientIntegration:
    """Integration tests with real HN API calls."""

    @pytest.mark.asyncio
    async def test_fetch_real_top_stories(self):
        """Test fetching real top stories from HN API."""
        async with HNClient() as client:
            # Fetch just 3 stories to minimize API load
            stories = await client.fetch_stories("top", limit=3)

            assert len(stories) <= 3  # May be fewer if some items fail
            assert all(isinstance(story, Story) for story in stories)

            # Verify stories have expected fields
            for story in stories:
                assert story.id > 0
                assert story.type in [ItemType.STORY, ItemType.JOB]
                assert story.by is not None  # Should have an author

    @pytest.mark.asyncio
    async def test_fetch_real_item(self):
        """Test fetching a real item from HN API."""
        async with HNClient() as client:
            # Item #1 is the first HN story - should always exist
            item = await client.fetch_item(1)

            assert isinstance(item, Story)
            assert item.id == 1
            assert item.type == ItemType.STORY
            assert item.by == "pg"  # Paul Graham posted the first story

    @pytest.mark.asyncio
    async def test_fetch_nonexistent_item(self):
        """Test fetching a non-existent item from real API."""
        async with HNClient() as client:
            # Use a very high ID that's unlikely to exist
            with pytest.raises(HNClientError, match="not found"):
                await client.fetch_item(99999999)

    @pytest.mark.asyncio
    async def test_search_real_stories(self):
        """Test searching for real stories via Algolia API."""
        async with HNClient() as client:
            # Search for Python stories
            stories = await client.search("Python", limit=5)

            assert len(stories) <= 5
            assert all(isinstance(story, Story) for story in stories)

            # Verify stories have expected fields
            for story in stories:
                assert story.id > 0
                assert story.type == ItemType.STORY
                # Title should contain Python (case-insensitive)
                if story.title:
                    assert "python" in story.title.lower() or "Python" in story.title

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search with query that returns no results."""
        async with HNClient() as client:
            # Use a very unlikely search term
            stories = await client.search("xyzabc123456789unlikely", limit=5)
            assert stories == []
