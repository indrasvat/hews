# Top-level package for *Hews*.

"""Hews – a terminal-based Hacker News browser."""

from __future__ import annotations

# Re-export the primary domain models so that callers can simply do
# ``from hews import Story`` etc. without importing the sub-module directly.

from importlib import import_module as _import_module


_models = _import_module("hews.models")

Story = _models.Story  # noqa: N802 – keep PascalCase (public API)
Comment = _models.Comment  # noqa: N802

__all__: list[str] = [
    "Story",
    "Comment",
]

