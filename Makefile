.PHONY: all bench corpus figures format ingest lint test typecheck

all: lint typecheck test

corpus:
	uv run px4reqcheck corpus download --manifest corpus/manifest.json --destination data/raw

ingest:
	uv run px4reqcheck ingest --manifest corpus/manifest.json --raw-dir data/raw --output data/parquet

figures:
	uv run px4reqcheck analyze --data-root data/parquet --output reports/figures

bench:
	uv run px4reqcheck benchmark ingest --runs 10 --cold-cache-command 'sudo scripts/drop-caches.sh'
	$(MAKE) ingest
	uv run px4reqcheck benchmark sql --runs 10 --cold-cache-command 'sudo scripts/drop-caches.sh'
	uv run px4reqcheck benchmark report

format:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy src/px4reqcheck/requirements src/px4reqcheck/params src/px4reqcheck/cli.py

test:
	uv run pytest
