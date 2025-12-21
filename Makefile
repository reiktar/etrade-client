.PHONY: test integration integration-auth lint format check

# Run unit tests (default, excludes integration tests)
test:
	uv run pytest tests/

# Run integration tests (requires sandbox credentials)
# First authenticates, then runs the tests
integration: integration-auth
	uv run pytest tests/integration -m integration -v

# Run OAuth flow to obtain/refresh tokens
integration-auth:
	uv run python -m tests.integration.auth_helper

# Run only integration tests (skip auth, assumes tokens exist)
integration-only:
	uv run pytest tests/integration -m integration -v

# Lint code
lint:
	uv run ruff check src/ tests/

# Format code
format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Run all checks (lint + tests)
check: lint test
