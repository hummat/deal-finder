# Contributing to deal-finder

Thanks for your interest in contributing! This document covers development setup and guidelines.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Quick Start

```bash
# Clone the repository
git clone https://github.com/hummat/deal-finder.git
cd deal-finder

# Install development dependencies
uv sync --group dev

# Run all checks
uv run ruff format .
uv run ruff check .
uv run pyright
```

## Code Style

- Python 3.10+
- 120-character line limit
- Type hints encouraged
- Run `ruff format .` and `ruff check .` before committing
- Run `pyright` for type checking

## Pull Request Process

1. **Create an issue first** for non-trivial changes
2. **Fork and branch** from `main`
3. **Make your changes** following the style guide
4. **Run all checks** — format, lint, typecheck
5. **Submit PR** using the template

### Commit Messages

- Use present tense: "Add feature" not "Added feature"
- Keep the first line under 72 characters
- Reference issues: "Fix notification bug (#42)"

## Questions?

- Open a [Discussion](https://github.com/hummat/deal-finder/discussions) for questions
- Check existing [Issues](https://github.com/hummat/deal-finder/issues) for known problems
