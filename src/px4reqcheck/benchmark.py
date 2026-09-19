"""Reproducible ingest and analytical benchmark harnesses."""

from __future__ import annotations

import json
import math
import os
import platform
import shlex
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

import duckdb

from px4reqcheck.analytics.queries import query_text, register_views
from px4reqcheck.ingest.pipeline import ingest_manifest

BENCHMARK_QUERIES = (
    "full_scan_quality",
    "per_log_topic_rows",
    "time_window_local_position",
)

SQLITE_QUERIES = {
    "full_scan_quality": """
        SELECT
            "check" AS check_name,
            count(DISTINCT CASE WHEN "count" > 0 THEN log_id END) AS logs_reported,
            sum("count") AS total_findings
        FROM quality
        GROUP BY "check"
        ORDER BY "check";
    """,
    "per_log_topic_rows": """
        SELECT log_id, sum(row_count) AS telemetry_rows, count(*) AS topic_count
        FROM topic_inventory
        GROUP BY log_id
        ORDER BY log_id;
    """,
    "time_window_local_position": """
        WITH starts AS (
            SELECT log_id, min("timestamp") AS start_us
            FROM local_position
            GROUP BY log_id
        )
        SELECT
            samples.log_id,
            count(*) AS samples_in_window,
            avg(samples.z) AS mean_z_m
        FROM local_position AS samples
        JOIN starts USING (log_id)
        WHERE samples."timestamp" >= starts.start_us + 10000000
          AND samples."timestamp" < starts.start_us + 20000000
        GROUP BY samples.log_id
        ORDER BY samples.log_id;
    """,
}


def _hardware() -> dict[str, str]:
    cpu = platform.processor() or "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    ram = "unknown"
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                ram = line.split(":", 1)[1].strip()
                break
    return {
        "cpu": cpu,
        "ram": ram,
        "logical_cpus": str(os.cpu_count() or "unknown"),
        "platform": platform.platform(),
    }


def _versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "duckdb": version("duckdb"),
        "pandas": version("pandas"),
        "pyarrow": version("pyarrow"),
        "sqlite": sqlite3.sqlite_version,
    }


def _run_identity() -> dict[str, str]:
    return {
        "git_commit": os.environ.get("GITHUB_SHA", "unknown"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
        "github_repository": os.environ.get("GITHUB_REPOSITORY", "unknown"),
    }


def _drop_caches(command: str) -> None:
    arguments = shlex.split(command)
    if not arguments:
        raise ValueError("cold-cache command must not be empty")
    subprocess.run(arguments, check=True)


def _timed(call: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter_ns()
    result = call()
    duration_s = (time.perf_counter_ns() - started) / 1_000_000_000
    return duration_s, result


def prepare_sqlite(data_root: Path, database: Path) -> None:
    """Materialize the three preregistered logical inputs into SQLite."""
    database.parent.mkdir(parents=True, exist_ok=True)
    source = duckdb.connect()
    register_views(
        source,
        data_root,
        views=("quality", "topic_inventory", "local_position"),
    )
    destination = sqlite3.connect(database)
    try:
        projections = {
            "quality": 'log_id, "check", "count"',
            "topic_inventory": "log_id, row_count",
            "local_position": 'log_id, "timestamp", z',
        }
        for table, columns in projections.items():
            source.execute(f"SELECT {columns} FROM {table}").fetchdf().to_sql(
                table,
                destination,
                if_exists="replace",
                index=False,
                chunksize=10_000,
            )
        destination.execute(
            "CREATE INDEX local_position_log_time ON local_position(log_id, timestamp)"
        )
        destination.execute('CREATE INDEX quality_check_log ON quality("check", log_id)')
        destination.execute("CREATE INDEX topic_inventory_log ON topic_inventory(log_id)")
        destination.commit()
    finally:
        destination.close()
        source.close()


def _duckdb_once(data_root: Path, name: str) -> list[tuple[Any, ...]]:
    connection = duckdb.connect()
    try:
        required = {
            "full_scan_quality": ("quality",),
            "per_log_topic_rows": ("topic_inventory",),
            "time_window_local_position": ("local_position",),
        }
        register_views(connection, data_root, views=required[name])
        return connection.execute(query_text(name)).fetchall()
    finally:
        connection.close()


def _sqlite_once(database: Path, name: str) -> list[tuple[Any, ...]]:
    connection = sqlite3.connect(database)
    try:
        return connection.execute(SQLITE_QUERIES[name]).fetchall()
    finally:
        connection.close()


def _rows_equivalent(left: list[tuple[Any, ...]], right: list[tuple[Any, ...]]) -> bool:
    if len(left) != len(right):
        return False
    for left_row, right_row in zip(left, right, strict=True):
        if len(left_row) != len(right_row):
            return False
        for left_value, right_value in zip(left_row, right_row, strict=True):
            if isinstance(left_value, float) and isinstance(right_value, float):
                if not math.isclose(left_value, right_value, rel_tol=1e-12, abs_tol=1e-12):
                    return False
            elif left_value != right_value:
                return False
    return True


def benchmark_sql(
    data_root: Path,
    database: Path,
    runs: int,
    cold_cache_command: str,
) -> dict[str, Any]:
    """Benchmark the preregistered queries after verifying result equivalence."""
    if runs < 1:
        raise ValueError("runs must be positive")
    prepare_sqlite(data_root, database)
    results: dict[str, Any] = {}
    for name in BENCHMARK_QUERIES:
        duckdb_rows = _duckdb_once(data_root, name)
        sqlite_rows = _sqlite_once(database, name)
        if not _rows_equivalent(duckdb_rows, sqlite_rows):
            raise ValueError(f"engine results differ for {name}")
        timings: dict[str, list[float]] = {"duckdb": [], "sqlite": []}
        for engine in ("duckdb", "sqlite"):
            for _ in range(runs):
                _drop_caches(cold_cache_command)
                operation = (
                    (lambda name=name: _duckdb_once(data_root, name))
                    if engine == "duckdb"
                    else (lambda name=name: _sqlite_once(database, name))
                )
                elapsed, rows = _timed(operation)
                if not _rows_equivalent(rows, duckdb_rows):
                    raise ValueError(f"{engine} result changed for {name}")
                timings[engine].append(elapsed)
        duckdb_median = statistics.median(timings["duckdb"])
        sqlite_median = statistics.median(timings["sqlite"])
        results[name] = {
            "duckdb_seconds": timings["duckdb"],
            "sqlite_seconds": timings["sqlite"],
            "duckdb_median_seconds": duckdb_median,
            "sqlite_median_seconds": sqlite_median,
            "sqlite_over_duckdb": sqlite_median / duckdb_median,
        }
    return {
        "schema_version": 1,
        "benchmark": "duckdb_vs_sqlite",
        "runs": runs,
        "statistic": f"median of {runs} cold-cache runs",
        "cold_cache_command": cold_cache_command,
        "timed_region": (
            "open connection, register DuckDB Parquet view where applicable, execute query, "
            "fetch all rows, close connection"
        ),
        "hardware": _hardware(),
        "versions": _versions(),
        "run_identity": _run_identity(),
        "queries": results,
        "hypothesis_holds": all(result["sqlite_over_duckdb"] >= 5.0 for result in results.values()),
    }


def benchmark_ingest(
    manifest: Path,
    raw_dir: Path,
    runs: int,
    cold_cache_command: str,
) -> dict[str, Any]:
    """Benchmark complete ULog-to-Parquet ingest into a fresh directory per run."""
    if runs < 1:
        raise ValueError("runs must be positive")
    durations: list[float] = []
    rows: list[int] = []
    log_counts: list[int] = []
    with tempfile.TemporaryDirectory(prefix="px4reqcheck-ingest-") as temporary:
        temporary_root = Path(temporary)
        for run_number in range(runs):
            destination = temporary_root / f"run-{run_number}"
            _drop_caches(cold_cache_command)
            elapsed, metadata = _timed(
                lambda destination=destination: ingest_manifest(manifest, raw_dir, destination)
            )
            durations.append(elapsed)
            rows.append(sum(int(log["telemetry_rows"]) for log in metadata))
            log_counts.append(len(metadata))
    if len(set(rows)) != 1:
        raise ValueError("ingest row count changed between runs")
    if len(set(log_counts)) != 1:
        raise ValueError("ingested log count changed between runs")
    throughput = [rows[0] / duration for duration in durations]
    return {
        "schema_version": 1,
        "benchmark": "ingest",
        "runs": runs,
        "statistic": f"median of {runs} cold-cache runs",
        "cold_cache_command": cold_cache_command,
        "timed_region": "parse all manifest ULogs and write all normalized Parquet outputs",
        "hardware": _hardware(),
        "versions": _versions(),
        "run_identity": _run_identity(),
        "log_count": log_counts[0],
        "telemetry_rows": rows[0],
        "duration_seconds": durations,
        "rows_per_second": throughput,
        "median_duration_seconds": statistics.median(durations),
        "median_rows_per_second": statistics.median(throughput),
    }


def write_result(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def render_benchmark_report(ingest_path: Path, sql_path: Path, output: Path) -> None:
    ingest = json.loads(ingest_path.read_text(encoding="utf-8"))
    sql = json.loads(sql_path.read_text(encoding="utf-8"))
    hardware = sql["hardware"]
    versions = sql["versions"]
    identity = sql["run_identity"]
    lines = [
        "# Week 2 benchmark results",
        "",
        "## Environment",
        "",
        f"- CPU: {hardware['cpu']}",
        f"- RAM: {hardware['ram']}",
        f"- Platform: Ubuntu 24.04 GitHub Actions hosted runner; `{hardware['platform']}`",
        f"- Logical CPUs: {hardware['logical_cpus']}",
        f"- Python: {versions['python']}",
        f"- DuckDB: {versions['duckdb']}",
        f"- SQLite: {versions['sqlite']}",
        f"- pandas: {versions['pandas']}",
        f"- PyArrow: {versions['pyarrow']}",
        f"- Git commit: `{identity['git_commit']}`",
        f"- GitHub Actions run ID: `{identity['github_run_id']}`",
        "",
        "## Ingest throughput",
        "",
        f"Median of {ingest['runs']} cold-cache runs over {ingest['log_count']} logs and "
        f"{ingest['telemetry_rows']} telemetry rows: "
        f"**{ingest['median_rows_per_second']:.0f} rows/s** "
        f"({ingest['median_duration_seconds']:.3f} s median wall time).",
        "",
        "Exact command:",
        "",
        "```bash",
        "uv run px4reqcheck benchmark ingest --runs 10 \\",
        "  --cold-cache-command 'sudo scripts/drop-caches.sh' \\",
        "  --output benchmark-output/ingest.json",
        "```",
        "",
        "## DuckDB versus SQLite",
        "",
        f"Statistic: {sql['statistic']}. The timed region is: {sql['timed_region']}.",
        "SQLite materialization and index creation occur before timing. Each engine's result rows "
        "are asserted equal before and during the timed repetitions.",
        "",
        "| Query | DuckDB median (s) | SQLite median (s) | SQLite / DuckDB |",
        "|---|---:|---:|---:|",
    ]
    for name in BENCHMARK_QUERIES:
        result = sql["queries"][name]
        lines.append(
            f"| `{name}` | {result['duckdb_median_seconds']:.6f} | "
            f"{result['sqlite_median_seconds']:.6f} | {result['sqlite_over_duckdb']:.2f}x |"
        )
    lines.extend(
        [
            "",
            "Exact command:",
            "",
            "```bash",
            "uv run px4reqcheck benchmark sql --runs 10 \\",
            "  --cold-cache-command 'sudo scripts/drop-caches.sh' \\",
            "  --output benchmark-output/sql.json",
            "```",
            "",
            "Cold-cache procedure: before every timed repetition, the harness invokes "
            f"`{sql['cold_cache_command']}`, which calls `sync` and asks Linux to drop page, "
            "dentry, and inode caches. The client is the benchmark process itself; there is no "
            "server or load generator, so client/server queueing is not applicable.",
            "",
        ]
    )
    if sql["hypothesis_holds"]:
        lines.append(
            "The preregistered hypothesis held: DuckDB was at least 5x faster than SQLite on all "
            "three named queries."
        )
    else:
        lines.append(
            "On the preregistered 20-log slice, DuckDB was not at least 5x faster than SQLite on "
            "all three analytical queries; the repository retains DuckDB for direct Parquet "
            "access and operational simplicity, not a universal speed claim."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit("use the px4reqcheck benchmark CLI")
