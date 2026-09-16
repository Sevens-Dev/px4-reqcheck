.PHONY: all format lint test typecheck

all: lint typecheck test

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy src/px4reqcheck

test:
	uv run pytest
