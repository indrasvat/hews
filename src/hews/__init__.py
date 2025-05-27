# Top-level package for *Hews*.

"""Hews – a terminal-based Hacker News browser."""

from __future__ import annotations

# Re-export the primary domain models and API client so that callers can simply do
# ``from hews import Story, HNClient`` etc. without importing the sub-modules directly.

from importlib import import_module as _import_module


_models = _import_module("hews.models")
_client = _import_module("hews.client")

Story = _models.Story  # noqa: N802 – keep PascalCase (public API)
Comment = _models.Comment  # noqa: N802
HNClient = _client.HNClient  # noqa: N802

__all__: list[str] = [
    "Story",
    "Comment", 
    "HNClient",
]

