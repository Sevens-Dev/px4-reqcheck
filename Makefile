.PHONY: all bench check corpus cpp-agreement cpp-build cpp-check cpp-configure export-checks figures format golden-ci ingest lint report test typecheck

all: check cpp-check report cpp-agreement

check: lint typecheck test

corpus:
	uv run px4reqcheck corpus download --manifest corpus/manifest.json --destination data/raw

ingest:
	uv run px4reqcheck ingest --manifest corpus/manifest.json --raw-dir data/raw --output data/parquet

figures:
	uv run px4reqcheck analyze --data-root data/parquet --output reports/figures

report:
	uv run px4reqcheck requirements evaluate --data-root data/parquet --output docs/report

cpp-configure:
	cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release

cpp-build: cpp-configure
	cmake --build cpp/build --parallel 2

cpp-check: cpp-build
	ctest --test-dir cpp/build --output-on-failure

export-checks:
	uv run px4reqcheck export-checks --data-root data/parquet --output export/checks.json

cpp-agreement: export-checks cpp-build
	cpp/build/px4-reqcheck-cpp export/checks.json export/cpp_verdicts.json
	uv run px4reqcheck compare-cpp --python-verdicts docs/report/verdicts.json --cpp-verdicts export/cpp_verdicts.json

golden-ci:
	uv run pytest tests/test_golden_ci.py

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
