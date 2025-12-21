# Contributing to etrade-client

Thank you for your interest in contributing! This guide covers the development setup, code standards, and contribution process.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Structure](#project-structure)
3. [Code Standards](#code-standards)
4. [Testing](#testing)
5. [Type Checking](#type-checking)
6. [Adding New Features](#adding-new-features)
7. [Pull Request Process](#pull-request-process)

## Development Setup

### Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager

### Clone and Install

```bash
git clone https://github.com/reiktar/etrade-client.git
cd etrade-client

# Install with all development dependencies
uv sync --all-extras
```

### Verify Installation

```bash
# Run tests
uv run pytest

# Run type checks
uv run mypy src/
uv run ty check src/

# Run linter
uv run ruff check src/
```

## Project Structure

```
etrade-client/
├── src/etrade_client/
│   ├── __init__.py          # Public API exports
│   ├── client.py             # Main ETradeClient class
│   ├── config.py             # Configuration handling
│   ├── auth.py               # OAuth authentication
│   ├── builders.py           # Order builders
│   ├── exceptions.py         # Exception classes
│   ├── api/                  # API module implementations
│   │   ├── base.py           # Base API class
│   │   ├── accounts.py       # Accounts API
│   │   ├── alerts.py         # Alerts API
│   │   ├── market.py         # Market Data API
│   │   └── orders.py         # Orders API
│   ├── models/               # Pydantic models
│   │   ├── accounts.py
│   │   ├── alerts.py
│   │   ├── auth.py
│   │   ├── market.py
│   │   ├── orders.py
│   │   └── transactions.py
│   └── cli/                  # Command-line interface
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       ├── formatters.py
│       └── commands/
│           ├── accounts.py
│           ├── alerts.py
│           ├── auth.py
│           ├── market.py
│           ├── orders.py
│           └── transactions.py
├── tests/
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests (sandbox)
├── docs/
│   ├── api/                  # Library documentation
│   └── cli/                  # CLI documentation
└── pyproject.toml
```

## Code Standards

### Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.

```bash
# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check --fix .

# Check without fixing
uv run ruff check .
```

### Key Style Rules

- Line length: 100 characters
- Quotes: Double quotes
- Imports: Sorted with isort rules
- Type hints: Required on all public APIs

### Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ETradeClient` |
| Functions/methods | snake_case | `get_balance()` |
| Constants | UPPER_SNAKE_CASE | `MAX_SYMBOLS` |
| Private | Leading underscore | `_parse_response()` |

## Testing

### Test Structure

```
tests/
├── unit/                  # Fast, no external deps
│   ├── test_client.py
│   ├── test_builders.py
│   └── test_models.py
└── integration/           # Require sandbox credentials
    ├── test_accounts.py
    ├── test_market.py
    └── test_orders.py
```

### Running Tests

```bash
# Unit tests only (default)
uv run pytest

# Include integration tests (requires sandbox credentials)
uv run pytest -m integration

# All tests
uv run pytest -m ""

# Specific test file
uv run pytest tests/unit/test_builders.py

# With coverage
uv run pytest --cov=etrade_client
```

### Integration Tests

Integration tests require E\*Trade sandbox credentials:

```bash
# Set credentials
export ETRADE_CONSUMER_KEY="your_sandbox_key"
export ETRADE_CONSUMER_SECRET="your_sandbox_secret"

# Run integration tests
uv run pytest -m integration
```

### Writing Tests

```python
import pytest
from etrade_client import EquityOrderBuilder

class TestEquityOrderBuilder:
    def test_build_limit_buy(self):
        order = (
            EquityOrderBuilder("AAPL")
            .buy(100)
            .limit(150.00)
            .build()
        )

        assert order["orderType"] == "EQ"
        assert order["Order"][0]["priceType"] == "LIMIT"
        assert order["Order"][0]["limitPrice"] == 150.00

    def test_missing_action_raises(self):
        with pytest.raises(ValueError, match="Order action required"):
            EquityOrderBuilder("AAPL").build()
```

## Type Checking

We use two type checkers for comprehensive coverage:

### mypy (Strict Mode)

```bash
uv run mypy src/
```

Configuration in `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.14"
strict = true
plugins = ["pydantic.mypy"]
```

### ty (Rust-based)

```bash
uv run ty check src/
```

### Resolving Type Checker Conflicts

When mypy and ty disagree, use targeted ignores:

```python
from typing import cast

# Cast for ty, ignore redundant-cast warning from mypy
data = cast(dict[str, Any], value)  # type: ignore[redundant-cast]
```

## Adding New Features

### Adding a New API Endpoint

1. **Add the model** in `src/etrade_client/models/`:

```python
# models/example.py
from pydantic import BaseModel, Field

class ExampleResponse(BaseModel):
    items: list[ExampleItem] = Field(default_factory=list, alias="Items")
```

2. **Add the API method** in `src/etrade_client/api/`:

```python
# api/example.py
async def get_example(self, param: str) -> ExampleResponse:
    """Get example data.

    Args:
        param: Description of parameter

    Returns:
        ExampleResponse with items
    """
    response = await self._request("GET", f"/example/{param}")
    return ExampleResponse.model_validate(response)
```

3. **Export from client** if needed in `client.py`

4. **Add tests** in `tests/unit/`

5. **Update documentation** in `docs/api/`

### Adding a CLI Command

1. **Create or update command file** in `src/etrade_client/cli/commands/`:

```python
@app.command("new-command")
@async_command
async def new_command(
    ctx: typer.Context,
    param: str = typer.Argument(..., help="Parameter description"),
) -> None:
    """Command description."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        result = await client.api.method(param)
        format_output(result, output, title="Title")
```

2. **Register in `cli/__init__.py`** if new module

3. **Update CLI documentation** in `docs/cli/`

## Pull Request Process

### Before Submitting

1. **Run all checks:**
   ```bash
   uv run ruff format .
   uv run ruff check --fix .
   uv run mypy src/
   uv run ty check src/
   uv run pytest
   ```

2. **Add tests** for new functionality

3. **Update documentation** if needed

4. **Keep commits focused** - one logical change per commit

### PR Guidelines

- Use descriptive PR titles
- Reference related issues
- Describe what changed and why
- Include test results

### Commit Messages

Follow conventional commit format:

```
type: short description

Longer description if needed.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

**Examples:**
```
feat: add option chain filtering by strike range
fix: handle null values in portfolio response
docs: update authentication guide
refactor: extract common API error handling
test: add unit tests for order builders
```

## Questions?

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
