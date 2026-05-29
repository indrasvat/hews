"""Integration-style tests for CLI user flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from hews import Story
from hews.cli import cli
from hews.models import ItemType


@pytest.fixture
def runner() -> CliRunner:
    """Create an isolated Click test runner."""
    return CliRunner()


@pytest.fixture
def known_stories() -> list[Story]:
    """Return deterministic stories for printed CLI output assertions."""
    return [
        Story(
            id=101,
            type=ItemType.STORY,
            title="Deterministic Top Story",
            url="https://example.com/top",
            score=128,
            descendants=64,
            by="top-user",
        ),
        Story(
            id=202,
            type=ItemType.STORY,
            title="Second Known Story",
            url="https://example.com/second",
            score=32,
            descendants=8,
            by="second-user",
        ),
    ]


def _mock_hn_client(client: AsyncMock) -> Mock:
    """Build an HNClient class mock that works as an async context manager."""
    client.login_from_env.return_value = False
    client_class = Mock()
    client_class.return_value.__aenter__ = AsyncMock(return_value=client)
    client_class.return_value.__aexit__ = AsyncMock(return_value=None)
    return client_class


def test_section_print_outputs_mocked_top_stories(
    runner: CliRunner, known_stories: list[Story]
) -> None:
    """`hews --section top --print` prints section results without real API calls."""
    client = AsyncMock()
    client.fetch_stories.return_value = known_stories

    with patch("hews.cli.HNClient", _mock_hn_client(client)):
        result = runner.invoke(cli, ["--section", "top", "--print"])

    assert result.exit_code == 0
    assert "Fetching top stories" in result.output
    assert "Top Stories" in result.output
    assert "Deterministic Top Story" in result.output
    assert "Second Known Story" in result.output
    assert "Showing 2 stories" in result.output
    client.login_from_env.assert_awaited_once_with()
    client.fetch_stories.assert_awaited_once_with("top", limit=30)
    client.search.assert_not_called()


def test_search_print_outputs_mocked_results(
    runner: CliRunner, known_stories: list[Story]
) -> None:
    """`hews --search <query> --print` prints search results without real API calls."""
    client = AsyncMock()
    client.search.return_value = known_stories[:1]

    with patch("hews.cli.HNClient", _mock_hn_client(client)):
        result = runner.invoke(cli, ["--search", "textual", "--print"])

    assert result.exit_code == 0
    assert "Searching for 'textual'" in result.output
    assert "Search Results for 'textual'" in result.output
    assert "Deterministic Top Story" in result.output
    assert "Found 1 stories" in result.output
    client.login_from_env.assert_awaited_once_with()
    client.search.assert_awaited_once_with("textual", limit=30)
    client.fetch_stories.assert_not_called()


def test_no_arg_invocation_launches_tui(runner: CliRunner) -> None:
    """`hews` with no arguments starts the TUI entry point."""
    with patch("hews.cli.HewsApp") as app_class:
        result = runner.invoke(cli, [])

    assert result.exit_code == 0
    app_class.assert_called_once_with(
        initial_section=None,
        initial_search=None,
        show_banner=True,
    )
    app_class.return_value.run.assert_called_once_with()


def test_no_arg_invocation_honors_no_banner_env(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The no-arg user flow still passes environment banner preferences through."""
    monkeypatch.setenv("HEWS_NO_BANNER", "1")

    with patch("hews.cli.HewsApp") as app_class:
        result = runner.invoke(cli, [])

    assert result.exit_code == 0
    app_class.assert_called_once_with(
        initial_section=None,
        initial_search=None,
        show_banner=False,
    )
    app_class.return_value.run.assert_called_once_with()
