# Contributing to Hews

Thank you for taking the time to contribute!  This document outlines the
basic workflow we expect for every pull-request.

## Development environment

Hews uses **uv** for dependency management and **Python 3.12** as the
baseline interpreter.

```bash
# Install all dependencies and generate uv.lock
uv sync

# Activate shell with the same interpreter (optional)
uv venv
```

Committing **uv.lock** is mandatory; it guarantees deterministic builds
across all machines and CI.

## Linting & tests

Run these two commands locally before opening a PR:

```bash
ruff check src/ tests/          # static analysis & formatting
uv run -m pytest  # test suite (pretty output via pytest-sugar)
```

The upcoming CI workflow (issue #49) will execute the exact same steps.

## Commit conventions

Follow the Conventional Commits style (e.g., `feat: …`, `fix: …`,
`docs: …`, `chore: …`).  The dynamic versioning plug-in derives
release numbers from Git tags, so clear commit messages help maintain a
clean history.

## File-system etiquette

Any feature that needs to persist data **must** use the OS-specific
locations provided by the `platformdirs` library.  Writing into the
repository directory or the user’s CWD is not allowed.

## Questions?

Open an issue or start a Discussion in the GitHub repo.  Happy hacking!
