import duckdb
import pandas as pd

from px4reqcheck.analytics.queries import QUERY_NAMES, query_text, register_views, run_query
from px4reqcheck.analytics.report import generate_static_figures


def connection_with_fixtures() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute(
        'CREATE TABLE quality(log_id VARCHAR, "check" VARCHAR, "count" DOUBLE, detail VARCHAR)'
    )
    connection.execute(
        "INSERT INTO quality VALUES ('a', 'gap', 2, ''), ('b', 'gap', 1, ''), "
        "('a', 'duplicate', 3, ''), ('b', 'duplicate', 0, '')"
    )
    connection.execute(
        "CREATE TABLE topic_inventory(log_id VARCHAR, topic VARCHAR, row_count BIGINT)"
    )
    connection.execute(
        "INSERT INTO topic_inventory VALUES ('a', 'position', 10), ('a', 'status', 2), "
        "('b', 'position', 20)"
    )
    connection.execute('CREATE TABLE local_position(log_id VARCHAR, "timestamp" BIGINT, z DOUBLE)')
    connection.execute(
        "INSERT INTO local_position VALUES "
        "('a', 0, 0), ('a', 10000000, -1), ('a', 15000000, -3), ('a', 20000000, -9)"
    )
    connection.execute("CREATE TABLE parameters(log_id VARCHAR, name VARCHAR, value_num DOUBLE)")
    connection.execute("INSERT INTO parameters VALUES ('a', 'P', 1), ('b', 'P', 3), ('a', 'Q', 2)")
    connection.execute("CREATE TABLE logmeta(sw_version VARCHAR, duration_s DOUBLE)")
    connection.execute("INSERT INTO logmeta VALUES ('1.15.4', 100), ('1.15.4', 200)")
    return connection


def test_all_five_queries_are_committed() -> None:
    assert len(QUERY_NAMES) == 5
    assert all(query_text(name).strip().endswith(";") for name in QUERY_NAMES)


def test_full_scan_quality_query() -> None:
    result = run_query(connection_with_fixtures(), "full_scan_quality")

    gap = result.loc[result["check_name"] == "gap"].iloc[0]
    assert gap["logs_reported"] == 2
    assert gap["total_findings"] == 3
    duplicate = result.loc[result["check_name"] == "duplicate"].iloc[0]
    assert duplicate["logs_reported"] == 1


def test_per_log_group_by_query() -> None:
    result = run_query(connection_with_fixtures(), "per_log_topic_rows")

    first = result.loc[result["log_id"] == "a"].iloc[0]
    assert first["telemetry_rows"] == 12
    assert first["topic_count"] == 2


def test_time_window_query() -> None:
    result = run_query(connection_with_fixtures(), "time_window_local_position")

    assert result.iloc[0]["samples_in_window"] == 2
    assert result.iloc[0]["mean_z_m"] == -2


def test_parameter_coverage_query() -> None:
    result = run_query(connection_with_fixtures(), "parameter_coverage")

    parameter = result.loc[result["name"] == "P"].iloc[0]
    assert parameter["log_count"] == 2
    assert parameter["minimum"] == 1
    assert parameter["maximum"] == 3


def test_firmware_duration_query() -> None:
    result = run_query(connection_with_fixtures(), "firmware_duration")

    assert result.iloc[0]["log_count"] == 2
    assert result.iloc[0]["mean_duration_s"] == 150


def test_register_views_and_generate_figures_from_parquet(tmp_path) -> None:
    data_root = tmp_path / "parquet"
    partition = data_root / "log_id=a"
    partition.mkdir(parents=True)
    pd.DataFrame(
        [{"log_id": "a", "check": "ts_gap_gt_1s", "count": 2, "detail": "position"}]
    ).to_parquet(partition / "quality.parquet", index=False)
    pd.DataFrame([{"log_id": "a", "name": "P", "value_num": 1.0}]).to_parquet(
        partition / "parameters.parquet", index=False
    )
    pd.DataFrame([{"log_id": "a", "sw_version": "1.15.4", "duration_s": 100.0}]).to_parquet(
        partition / "logmeta.parquet", index=False
    )
    pd.DataFrame([{"log_id": "a", "topic": "vehicle_local_position", "row_count": 2}]).to_parquet(
        partition / "topic_inventory.parquet", index=False
    )
    pd.DataFrame(
        [
            {"log_id": "a", "timestamp": 0, "z": 0.0},
            {"log_id": "a", "timestamp": 10_000_000, "z": -1.0},
        ]
    ).to_parquet(partition / "topic_vehicle_local_position.parquet", index=False)

    output = tmp_path / "figures"
    generated = generate_static_figures(data_root, output)

    assert [path.name for path in generated] == [
        "quality-findings.png",
        "duration-by-firmware.png",
    ]
    assert all(path.stat().st_size > 0 for path in generated)


def test_register_views_can_select_only_available_inputs(tmp_path) -> None:
    partition = tmp_path / "parquet" / "log_id=a"
    partition.mkdir(parents=True)
    pd.DataFrame([{"log_id": "a", "check": "gap", "count": 0}]).to_parquet(
        partition / "quality.parquet", index=False
    )
    connection = duckdb.connect()

    register_views(connection, tmp_path / "parquet", views=("quality",))

    assert connection.execute("SELECT count(*) FROM quality").fetchone() == (1,)
    connection.close()
