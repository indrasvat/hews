# Hews Code-Style & Conventions

This short guide lists guidelines to follow when working on this code-base.

## 1. Python version

Python **3.12** is the minimum supported version – enforced via the
`.python-version` file and the CI matrix.

## 2. Dependency management

* Use **uv** exclusively:

  ```bash
  uv sync          # install using pyproject.toml + uv.lock
  ```

* Always commit the generated **uv.lock** file.

## 3. Linting & Formatting

* Run `ruff check src/ tests/` before every commit/push.  The CI workflow
  (issue #49) will enforce the same command.
* Adopt Ruff’s default rules; project-specific tweaks belong in
  `pyproject.toml` under `[tool.ruff]`.

## 4. Tests

* Use **pytest** with the **pytest-sugar** plug-in for clean output.
* Run tests via:

  ```bash
  uv run -m pytest -q
  ```

## 5. File system locations

* **Never** write cache, logs, or other artefacts into the repository tree
  or the user’s current working directory.
* Resolve platform-correct paths with the **platformdirs** library:

  ```python
  from platformdirs import PlatformDirs

  dirs = PlatformDirs("hews", "Hews")
  cache_path = dirs.user_cache_dir  # e.g. ~/Library/Caches/hews on macOS
  ```
