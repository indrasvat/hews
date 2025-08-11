"""Tests for hews.client.HNClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from hews.client import HNClient, HNClientError
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


class TestHNClient:
    """Test suite for HNClient class."""

    @pytest.fixture
    def mock_client(self):
        """Create an HNClient with a mocked httpx client."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        client = HNClient(http_client=mock_http)
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

        mock_client._http_client.get.assert_called_with("/item/123.json")

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
