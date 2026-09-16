"""Register normalized Parquet views and execute committed analytical SQL."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import duckdb
import pandas as pd

QUERY_NAMES = (
    "full_scan_quality",
    "per_log_topic_rows",
    "time_window_local_position",
    "parameter_coverage",
    "firmware_duration",
)


def query_text(name: str) -> str:
    if name not in QUERY_NAMES:
        raise ValueError(f"unknown query: {name}")
    return (
        resources.files("px4reqcheck.analytics.sql")
        .joinpath(f"{name}.sql")
        .read_text(encoding="utf-8")
    )


def register_views(connection: duckdb.DuckDBPyConnection, data_root: Path) -> None:
    root = data_root.resolve().as_posix().replace("'", "''")
    paths = {
        "quality": f"{root}/log_id=*/quality.parquet",
        "parameters": f"{root}/log_id=*/parameters.parquet",
        "logmeta": f"{root}/log_id=*/logmeta.parquet",
        "topic_inventory": f"{root}/log_id=*/topic_inventory.parquet",
        "local_position": f"{root}/log_id=*/topic_vehicle_local_position.parquet",
    }
    for view, pattern in paths.items():
        connection.execute(
            f"CREATE OR REPLACE VIEW {view} AS "
            f"SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
        )


def run_query(connection: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    return connection.execute(query_text(name)).fetchdf()
