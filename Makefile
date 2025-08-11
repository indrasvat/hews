# Makefile for Hews project
# Run 'make help' to see available commands

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ''
	@echo 'Common workflows:'
	@echo '  make check      - Run all checks before committing'
	@echo '  make fix        - Auto-fix all possible issues'
	@echo '  make test       - Run all tests'

.PHONY: install
install: ## Install all dependencies
	uv sync

.PHONY: install-dev
install-dev: ## Install all dependencies including dev
	uv sync --all-extras

# Linting and formatting
.PHONY: lint
lint: ## Run ruff linter
	uv run ruff check src/ tests/

.PHONY: format
format: ## Format code with ruff
	uv run ruff format src/ tests/

.PHONY: fix
fix: ## Auto-fix linting issues and format code
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

# Type checking
.PHONY: mypy
mypy: ## Run mypy type checker
	uv run mypy src/

.PHONY: typecheck
typecheck: mypy ## Alias for mypy

# Spell checking
.PHONY: spell
spell: ## Run codespell
	uv run codespell

.PHONY: spellfix
spellfix: ## Fix spelling errors interactively
	uv run codespell -i 3 -w

# Testing
.PHONY: test
test: ## Run all tests
	uv run -m pytest

.PHONY: test-verbose
test-verbose: ## Run tests with verbose output
	uv run -m pytest -v

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	uv run -m pytest --cov=src/hews --cov-report=term-missing

.PHONY: test-fast
test-fast: ## Run tests quickly (no sugar, quiet)
	uv run -m pytest -q

# Running the application
.PHONY: run
run: ## Run the application
	uv run hews

.PHONY: run-help
run-help: ## Show application help
	uv run hews --help

.PHONY: run-top
run-top: ## Fetch and display top stories
	uv run hews --section top --print

.PHONY: run-new
run-new: ## Fetch and display new stories
	uv run hews --section new --print

# Combined checks
.PHONY: check
check: lint typecheck spell test ## Run all checks (lint, typecheck, spell, test)
	@echo "✅ All checks passed!"

.PHONY: check-fast
check-fast: ## Run quick checks (no tests)
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck
	@$(MAKE) --no-print-directory spell
	@echo "✅ Quick checks passed!"

.PHONY: pre-commit
pre-commit: fix check ## Fix issues and run all checks (recommended before commit)
	@echo "✨ Ready to commit!"

.PHONY: ci
ci: ## Run CI checks (no auto-fix)
	uv run ruff check src/ tests/
	uv run mypy src/
	uv run codespell
	uv run -m pytest

# Cleaning
.PHONY: clean
clean: ## Clean up cache and build files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-all
clean-all: clean ## Clean everything including .venv
	rm -rf .venv

# Development utilities
.PHONY: shell
shell: ## Open Python shell with project context
	uv run python

.PHONY: repl
repl: shell ## Alias for shell

.PHONY: update
update: ## Update all dependencies to latest versions
	uv sync --upgrade

# Documentation
.PHONY: serve-docs
serve-docs: ## Serve documentation locally (when implemented)
	@echo "Documentation server not yet implemented"

# Default target
.DEFAULT_GOAL := help