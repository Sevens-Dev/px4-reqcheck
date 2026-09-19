import json
import sqlite3
from pathlib import Path

import pandas as pd

from px4reqcheck.benchmark import (
    BENCHMARK_QUERIES,
    benchmark_sql,
    render_benchmark_report,
)


def write_analytical_fixture(data_root: Path) -> None:
    partition = data_root / "log_id=a"
    partition.mkdir(parents=True)
    pd.DataFrame(
        [
            {"log_id": "a", "check": "gap", "count": 2, "detail": "position"},
            {"log_id": "a", "check": "duplicate", "count": 0, "detail": "position"},
        ]
    ).to_parquet(partition / "quality.parquet", index=False)
    pd.DataFrame([{"log_id": "a", "topic": "vehicle_local_position", "row_count": 3}]).to_parquet(
        partition / "topic_inventory.parquet", index=False
    )
    pd.DataFrame(
        [
            {"log_id": "a", "timestamp": 0, "z": 0.0},
            {"log_id": "a", "timestamp": 10_000_000, "z": -1.0},
            {"log_id": "a", "timestamp": 15_000_000, "z": -3.0},
        ]
    ).to_parquet(partition / "topic_vehicle_local_position.parquet", index=False)


def test_sql_benchmark_checks_equivalence_and_records_every_run(tmp_path) -> None:
    data_root = tmp_path / "parquet"
    write_analytical_fixture(data_root)

    result = benchmark_sql(data_root, tmp_path / "benchmark.sqlite", 2, "true")

    assert result["runs"] == 2
    assert set(result["queries"]) == set(BENCHMARK_QUERIES)
    for query in result["queries"].values():
        assert len(query["duckdb_seconds"]) == 2
        assert len(query["sqlite_seconds"]) == 2
        assert query["duckdb_median_seconds"] > 0
        assert query["sqlite_median_seconds"] > 0
    connection = sqlite3.connect(tmp_path / "benchmark.sqlite")
    assert connection.execute("SELECT count(*) FROM quality").fetchone() == (2,)
    connection.close()


def test_report_uses_preregistered_null_sentence(tmp_path) -> None:
    hardware = {
        "cpu": "test cpu",
        "ram": "1024 kB",
        "logical_cpus": "2",
        "platform": "test platform",
    }
    versions = {
        "python": "3.12",
        "duckdb": "1",
        "sqlite": "3",
        "pandas": "2",
        "pyarrow": "23",
    }
    ingest = {
        "runs": 10,
        "log_count": 20,
        "telemetry_rows": 100,
        "median_rows_per_second": 50.0,
        "median_duration_seconds": 2.0,
    }
    query = {
        "duckdb_median_seconds": 1.0,
        "sqlite_median_seconds": 2.0,
        "sqlite_over_duckdb": 2.0,
    }
    sql = {
        "runs": 10,
        "statistic": "median of 10 cold-cache runs",
        "timed_region": "test region",
        "cold_cache_command": "sudo scripts/drop-caches.sh",
        "hardware": hardware,
        "versions": versions,
        "run_identity": {
            "git_commit": "abc123",
            "github_run_id": "123",
            "github_repository": "owner/repo",
        },
        "queries": {name: query for name in BENCHMARK_QUERIES},
        "hypothesis_holds": False,
    }
    ingest_path = tmp_path / "ingest.json"
    sql_path = tmp_path / "sql.json"
    ingest_path.write_text(json.dumps(ingest), encoding="utf-8")
    sql_path.write_text(json.dumps(sql), encoding="utf-8")
    output = tmp_path / "report.md"

    render_benchmark_report(ingest_path, sql_path, output)

    report = output.read_text(encoding="utf-8")
    assert (
        "On the preregistered 20-log slice, DuckDB was not at least 5x faster than SQLite "
        "on all three analytical queries;"
    ) in report
    assert "Median of 10 cold-cache runs" in report
