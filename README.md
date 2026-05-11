# hews

![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

*Hews* is a terminal-based Hacker News browser, searcher, and reader.

---

## Quick start (for contributors)

```bash
# 1. Clone & enter repo
git clone https://github.com/indrasvat/hews.git
cd hews

# 2. Install all dependencies (honours the lock-file)
uv sync

# 3. Run the app
uv run hews --help  # Show available commands
uv run hews --section top --print  # Fetch and display top stories

# 4. Run code quality checks (REQUIRED before committing)
make check  # Runs all checks: ruff, mypy, codespell, and tests

# Or run individual checks:
make lint       # Run ruff linter
make typecheck  # Run mypy type checking  
make spell      # Run codespell spell checking
make test       # Run pytest tests

# Quick fix before committing:
make pre-commit  # Auto-fix issues and run all checks
```

**⚠️ IMPORTANT:** Always run `make check` before committing/pushing code. This ensures:
- Code follows project style (ruff)
- Type annotations are correct (mypy)
- No spelling mistakes (codespell)
- All tests pass (pytest)

`uv sync` will create or update **uv.lock** – commit that file whenever it changes so CI and other developers get identical dependency versions.

---
