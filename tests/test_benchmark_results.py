import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).parents[1]
BENCHMARKS = ROOT / "docs" / "benchmarks"


def test_committed_benchmark_artifacts_match_recorded_hashes() -> None:
    entries = (BENCHMARKS / "SHA256SUMS").read_text(encoding="utf-8").splitlines()

    for entry in entries:
        expected, filename = entry.split("  ", 1)
        actual = hashlib.sha256((BENCHMARKS / filename).read_bytes()).hexdigest()
        assert actual == expected


def test_committed_results_recompute_and_preregistration_is_complete() -> None:
    ingest = json.loads((BENCHMARKS / "ingest.json").read_text(encoding="utf-8"))
    sql = json.loads((BENCHMARKS / "sql.json").read_text(encoding="utf-8"))
    preregistration = (ROOT / "docs" / "preregistration" / "duckdb-vs-sqlite.md").read_text(
        encoding="utf-8"
    )

    assert ingest["median_duration_seconds"] == statistics.median(ingest["duration_seconds"])
    assert ingest["median_rows_per_second"] == statistics.median(ingest["rows_per_second"])
    assert len(ingest["duration_seconds"]) == ingest["runs"] == 10
    for result in sql["queries"].values():
        assert result["duckdb_median_seconds"] == statistics.median(result["duckdb_seconds"])
        assert result["sqlite_median_seconds"] == statistics.median(result["sqlite_seconds"])
    assert sql["hypothesis_holds"] is False
    for heading in (
        "## Hypothesis",
        "## Statistic and decision rule",
        "## Null-result sentence",
        "## Minimum meaningful difference",
        "## Minimum detectable difference given N",
    ):
        assert heading in preregistration
