# hews
*Hews* is a terminal-based Hacker News browser, searcher, and reader.

---

## Quick start (for contributors)

```bash
# 1. Clone & enter repo
git clone https://github.com/hews-tui/hews.git
cd hews

# 2. Install all dependencies (honours the lock-file)
uv sync

# 3. Run the app (placeholder until CLI/TUI is built)
uv run --python 3.12 -m hews  # currently a no-op

# 4. Lint & test
ruff check src/ tests/
uv run --python 3.12 -m pytest -q
```

`uv sync` will create or update **uv.lock** – commit that file whenever it changes so CI and other developers get identical dependency versions.

---
