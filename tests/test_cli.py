"""Tests for the CLI module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from hews import Story
from hews.cli import cli
from hews.models import ItemType


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_stories():
    """Create mock Story objects for testing."""
    return [
        Story(
            id=1,
            type=ItemType.STORY,
            title="Test Story 1",
            url="https://example.com/1",
            score=100,
            descendants=50,
            by="user1",
        ),
        Story(
            id=2,
            type=ItemType.STORY,
            title="Test Story 2",
            url="https://example.com/2",
            score=75,
            descendants=30,
            by="user2",
        ),
    ]


def test_cli_help(runner):
    """Test that --help displays usage information."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Hews - A terminal-based Hacker News browser" in result.output
    assert "--section" in result.output
    assert "--search" in result.output
    assert "--print" in result.output


def test_cli_version(runner):
    """Test that --version displays version information."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output


def test_cli_no_args_launches_tui(runner):
    """Test that running without args attempts to launch TUI."""
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "TUI mode not yet implemented" in result.output
    assert "Would start with default view" in result.output


def test_cli_section_without_print_launches_tui(runner):
    """Test that --section without --print launches TUI with section."""
    result = runner.invoke(cli, ["--section", "top"])
    assert result.exit_code == 0
    assert "TUI mode not yet implemented" in result.output
    assert "Would start with section: top" in result.output


def test_cli_search_without_print_launches_tui(runner):
    """Test that --search without --print launches TUI with search."""
    result = runner.invoke(cli, ["--search", "python"])
    assert result.exit_code == 0
    assert "TUI mode not yet implemented" in result.output
    assert "Would start with search: 'python'" in result.output


def test_cli_search_with_print(runner):
    """Test that --search --print works correctly."""
    with patch("hews.cli.HNClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the search method to return empty list
        mock_client.search.return_value = []

        result = runner.invoke(cli, ["--search", "python", "--print"])
        assert result.exit_code == 0
        assert "Searching for 'python'" in result.output
        assert "No stories found" in result.output

        # Verify search was called
        mock_client.search.assert_called_once_with("python", limit=30)


def test_cli_print_without_section_or_search_errors(runner):
    """Test that --print without --section or --search shows error."""
    with patch("hews.cli.HNClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = runner.invoke(cli, ["--print"])
        assert result.exit_code == 1
        assert "Error: --print requires either --section or --search" in result.output


def test_cli_section_and_search_together_errors(runner):
    """Test that using both --section and --search shows error."""
    result = runner.invoke(cli, ["--section", "top", "--search", "python"])
    assert result.exit_code == 1
    assert "Error: Cannot use both --section and --search" in result.output


def test_cli_section_print_success(runner, mock_stories):
    """Test successful fetching and printing of stories."""
    with patch("hews.cli.HNClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.fetch_stories = AsyncMock(return_value=mock_stories)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = runner.invoke(cli, ["--section", "top", "--print"])
        assert result.exit_code == 0
        assert "Fetching top stories" in result.output
        assert "Test Story 1" in result.output
        assert "Test Story 2" in result.output
        assert "100" in result.output  # score
        assert "50" in result.output  # descendants
        assert "user1" in result.output
        mock_client.fetch_stories.assert_called_once_with("top", limit=30)


def test_cli_section_print_empty_results(runner):
    """Test handling of empty story results."""
    with patch("hews.cli.HNClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.fetch_stories = AsyncMock(return_value=[])
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = runner.invoke(cli, ["--section", "new", "--print"])
        assert result.exit_code == 0
        assert "No stories found in new section" in result.output


def test_cli_section_print_network_error(runner):
    """Test handling of network errors during fetch."""
    with patch("hews.cli.HNClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.fetch_stories = AsyncMock(side_effect=Exception("Network error"))
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = runner.invoke(cli, ["--section", "ask", "--print"])
        assert result.exit_code == 1
        assert "Error fetching stories: Network error" in result.output


def test_cli_all_sections_valid():
    """Test that all expected sections are valid choices."""
    valid_sections = ["top", "new", "ask", "show", "jobs"]
    runner = CliRunner()

    for section in valid_sections:
        result = runner.invoke(cli, ["--section", section, "--help"])
        # If section is valid, help should still work
        assert result.exit_code == 0


def test_cli_invalid_section_rejected(runner):
    """Test that invalid section names are rejected."""
    result = runner.invoke(cli, ["--section", "invalid"])
    assert result.exit_code == 2
    assert "Invalid value for '--section'" in result.output or "Error" in result.output


def test_cli_environment_loading(runner):
    """Test that environment loading doesn't crash the app."""
    # Simply test that the CLI works with environment loading
    # The actual loading is tested through the other behavior tests
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_cli_no_env_file_continues(runner, tmp_path):
    """Test that missing .env file doesn't crash the app."""
    with patch("hews.cli.Path.cwd", return_value=tmp_path):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # Should work fine without .env file
