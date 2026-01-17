# Repository Guidelines

This file provides guidance to AI coding agents when working with code in this repository.

## Conventions

Read relevant `docs/agent/` files before proceeding:
- `workflow.md` — **read before starting any feature** (issues, branching, PRs)

---

## Project Overview

**deal-finder** is a minimal Kleinanzeigen deal finder with email and ntfy notifications. It scrapes listings and alerts you when new deals matching your criteria appear.

## Commands

```bash
# Run
deal-finder --help

# Dev
uv sync --group dev
uv run ruff format .
uv run ruff check .
uv run pyright
```

## Project Structure

- `deal_finder/kleinanzeigen.py` — main scraper and notification logic
- `pyproject.toml` — project config (ruff, pyright settings)

## Code Style

- Python 3.10+
- 120-character line limit
- Type hints encouraged
- Run `ruff format` + `ruff check` before committing

## Code Workflow

1. **Before editing**: read files first; understand existing code
2. **After code changes**: `ruff format .` → `ruff check .` → `pyright`
3. **Commits**: short imperative summary; use `feat:`/`fix:`/`docs:` prefixes
