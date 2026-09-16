.PHONY: all corpus figures format ingest lint test typecheck

all: lint typecheck test

corpus:
	uv run px4reqcheck corpus download --manifest corpus/manifest.json --destination data/raw

ingest:
	uv run px4reqcheck ingest --manifest corpus/manifest.json --raw-dir data/raw --output data/parquet

figures:
	uv run px4reqcheck analyze --data-root data/parquet --output reports/figures

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy src/px4reqcheck/cli.py

test:
	uv run pytest
