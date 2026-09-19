.PHONY: all bench check corpus figures format ingest lint report test typecheck

all: check report

check: lint typecheck test

corpus:
	uv run px4reqcheck corpus download --manifest corpus/manifest.json --destination data/raw

ingest:
	uv run px4reqcheck ingest --manifest corpus/manifest.json --raw-dir data/raw --output data/parquet

figures:
	uv run px4reqcheck analyze --data-root data/parquet --output reports/figures

report:
	uv run px4reqcheck requirements evaluate --data-root data/parquet --output docs/report

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
