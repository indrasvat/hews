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

**MANDATORY**: Run these checks locally before opening a PR:

```bash
make check  # Runs all required checks
```

This single command runs:
- `ruff` - static analysis & formatting
- `mypy` - type checking  
- `codespell` - spell checking
- `pytest` - test suite

Alternative workflow for auto-fixing:
```bash
make pre-commit  # Auto-fixes issues then runs all checks
```

The CI workflow will execute these exact same checks and will fail if any check doesn't pass.

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
