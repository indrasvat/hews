"""Command-line interface for Hews using Click."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.table import Table

from hews import HNClient


console = Console()


def setup_logging() -> None:
    """Configure logging with Loguru."""
    log_level = os.environ.get("HEWS_LOG_LEVEL", "INFO").upper()

    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    logger.debug(f"Logging initialized at level: {log_level}")


def load_environment() -> None:
    """Load environment variables from .env file if present."""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(f"Loaded environment from {env_path}")
    else:
        logger.debug("No .env file found, using system environment")


async def fetch_and_print_stories(
    client: HNClient, section: str, limit: int = 30
) -> None:
    """Fetch stories from a section and print them to stdout.

    Args:
        client: HNClient instance
        section: Section name (top, new, ask, show, jobs)
        limit: Number of stories to fetch and display
    """
    try:
        console.print(f"\n[bold cyan]Fetching {section} stories...[/bold cyan]\n")

        stories = await client.fetch_stories(section, limit=limit)

        if not stories:
            console.print(f"[yellow]No stories found in {section} section[/yellow]")
            return

        table = Table(title=f"{section.capitalize()} Stories", show_lines=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column("Points", justify="right", style="green")
        table.add_column("Comments", justify="right", style="yellow")
        table.add_column("Author", style="magenta")
        table.add_column("Age", style="dim")

        for idx, story in enumerate(stories, 1):
            table.add_row(
                str(idx),
                story.title or "Untitled",
                str(story.score or 0),
                str(story.descendants or 0),
                story.by or "unknown",
                story.age() if story.time else "unknown",
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(stories)} stories[/dim]")

    except Exception as e:
        console.print(f"[red]Error fetching stories: {e}[/red]")
        logger.exception("Failed to fetch stories")
        sys.exit(1)


async def search_and_print_stories(client: HNClient, query: str) -> None:
    """Search for stories and print them to stdout.

    Args:
        client: HNClient instance
        query: Search query string
    """
    console.print("\n[bold cyan]Search functionality not yet implemented[/bold cyan]")
    console.print(f"[dim]Would search for: '{query}'[/dim]\n")


async def run_print_mode(section: Optional[str], search: Optional[str]) -> None:
    """Run the CLI in print mode (non-interactive).

    Args:
        section: Section to fetch (if provided)
        search: Search query (if provided)
    """
    async with HNClient() as client:
        if search:
            await search_and_print_stories(client, search)
        elif section:
            await fetch_and_print_stories(client, section)
        else:
            console.print(
                "[red]Error: --print requires either --section or --search[/red]"
            )
            sys.exit(1)


def launch_tui(
    initial_section: Optional[str] = None, initial_search: Optional[str] = None
) -> None:
    """Launch the Textual TUI application.

    Args:
        initial_section: Initial section to display
        initial_search: Initial search query to execute
    """
    console.print("\n[bold yellow]TUI mode not yet implemented[/bold yellow]")
    console.print(
        "[dim]The interactive terminal UI will be available in a future update.[/dim]"
    )

    if initial_search:
        console.print(f"[dim]Would start with search: '{initial_search}'[/dim]")
    elif initial_section:
        console.print(f"[dim]Would start with section: {initial_section}[/dim]")
    else:
        console.print("[dim]Would start with default view (top stories)[/dim]")

    console.print("\n[cyan]For now, try using --print mode:[/cyan]")
    console.print("  hews --section top --print")
    console.print("  hews --section new --print")
    console.print()


@click.command()
@click.option(
    "--section",
    "-s",
    type=click.Choice(["top", "new", "ask", "show", "jobs"], case_sensitive=False),
    help="HN section to fetch (top, new, ask, show, jobs)",
)
@click.option(
    "--search",
    "-q",
    type=str,
    help="Search query (not yet implemented)",
)
@click.option(
    "--print",
    "-p",
    "print_mode",
    is_flag=True,
    help="Print stories to stdout instead of launching TUI",
)
@click.version_option(package_name="hews")
def cli(section: Optional[str], search: Optional[str], print_mode: bool) -> None:
    """Hews - A terminal-based Hacker News browser, searcher, and reader.

    When run without options, launches the interactive TUI (not yet implemented).
    Use --print with --section or --search to output stories to stdout.

    Examples:

        hews                          # Launch TUI (coming soon)

        hews --section top --print    # Print top stories

        hews --search "python" --print  # Search and print (coming soon)
    """
    load_environment()
    setup_logging()

    logger.info("Starting Hews CLI")

    if section and search:
        console.print("[red]Error: Cannot use both --section and --search[/red]")
        sys.exit(1)

    if print_mode:
        asyncio.run(run_print_mode(section, search))
    else:
        launch_tui(initial_section=section, initial_search=search)


def main() -> None:
    """Entry point for the hews command."""
    cli()


if __name__ == "__main__":
    main()
