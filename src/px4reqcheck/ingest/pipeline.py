"""Initial ULog-to-Parquet normalization pipeline."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from pyulog import ULog

from px4reqcheck.ingest.quality import (
    count_duplicates,
    count_gaps,
    count_nonmonotonic,
    count_out_of_range,
    sample_rate_hz,
)

WHITELIST = [
    "actuator_armed",
    "battery_status",
    "home_position",
    "sensor_combined",
    "sensor_gps",
    "trajectory_setpoint",
    "vehicle_gps_position",
    "vehicle_imu_status",
    "vehicle_land_detected",
    "vehicle_local_position",
    "vehicle_local_position_setpoint",
    "vehicle_status",
]


def _range_table() -> dict[str, dict[str, float | str]]:
    text = resources.files("px4reqcheck.ingest").joinpath("ranges.yaml").read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError("ranges.yaml must contain a mapping")
    return loaded


def _parameter_rows(log_id: str, ulog: ULog) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "log_id": log_id,
                "name": name,
                "value_num": float(value),
                "value_type": "int32" if isinstance(value, int) else "float32",
            }
            for name, value in sorted(ulog.initial_parameters.items())
        ]
    )


def ingest_log(log_id: str, source: Path, output_root: Path) -> dict[str, Any]:
    """Write whitelisted instance-zero topics and Week 1 quality records."""
    ulog = ULog(str(source), message_name_filter_list=WHITELIST)
    destination = output_root / f"log_id={log_id}"
    destination.mkdir(parents=True, exist_ok=True)
    quality: list[dict[str, Any]] = []
    ranges = _range_table()
    present_topics: set[str] = set()
    additional_instances: dict[str, list[int]] = {}
    for dataset in ulog.data_list:
        if dataset.multi_id != 0:
            additional_instances.setdefault(dataset.name, []).append(dataset.multi_id)
    topic_count = 0
    row_count = 0
    inventory: list[dict[str, Any]] = []
    for dataset in ulog.data_list:
        if dataset.multi_id != 0:
            continue
        frame = pd.DataFrame(dataset.data)
        if "timestamp" not in frame:
            continue
        present_topics.add(dataset.name)
        topic_count += 1
        row_count += len(frame)
        inventory.append({"log_id": log_id, "topic": dataset.name, "row_count": len(frame)})
        timestamps = frame["timestamp"].to_numpy()
        checks = {
            "ts_nonmonotonic": count_nonmonotonic(timestamps),
            "ts_gap_gt_1s": count_gaps(timestamps),
            "ts_duplicate": count_duplicates(timestamps),
        }
        for check, count in checks.items():
            quality.append(
                {"log_id": log_id, "check": check, "count": count, "detail": dataset.name}
            )
        rate = sample_rate_hz(timestamps)
        quality.append(
            {
                "log_id": log_id,
                "check": "sample_rate_hz",
                "count": rate if rate is not None else 0.0,
                "detail": json.dumps(
                    {
                        "topic": dataset.name,
                        "additional_multi_ids": sorted(additional_instances.get(dataset.name, [])),
                    },
                    sort_keys=True,
                ),
            }
        )
        for field in frame.columns:
            specification = ranges.get(f"{dataset.name}.{field}")
            if specification is None:
                continue
            count = count_out_of_range(
                frame[field].to_numpy(),
                minimum=float(specification["min"]),
                maximum=float(specification["max"]),
            )
            quality.append(
                {
                    "log_id": log_id,
                    "check": "value_out_of_range",
                    "count": count,
                    "detail": f"{dataset.name}.{field} [{specification['unit']}]",
                }
            )
        frame.insert(0, "log_id", log_id)
        frame.to_parquet(destination / f"topic_{dataset.name}.parquet", index=False)
    for topic in sorted(set(WHITELIST) - present_topics):
        quality.append({"log_id": log_id, "check": "topic_missing", "count": 1, "detail": topic})
    _parameter_rows(log_id, ulog).to_parquet(destination / "parameters.parquet", index=False)
    pd.DataFrame(quality).to_parquet(destination / "quality.parquet", index=False)
    pd.DataFrame(inventory).to_parquet(destination / "topic_inventory.parquet", index=False)
    version = ulog.get_version_info()
    metadata = {
        "log_id": log_id,
        "sw_version": ".".join(str(part) for part in version[:3]) if version else None,
        "start_timestamp_us": int(ulog.start_timestamp),
        "last_timestamp_us": int(ulog.last_timestamp),
        "duration_s": (ulog.last_timestamp - ulog.start_timestamp) / 1_000_000,
        "topic_count": topic_count,
        "telemetry_rows": row_count,
    }
    (destination / "logmeta.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame([metadata]).to_parquet(destination / "logmeta.parquet", index=False)
    return metadata


def ingest_manifest(manifest_path: Path, raw_dir: Path, output_root: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for entry in manifest["logs"]:
        source = raw_dir / f"{entry['log_id']}.ulg"
        if not source.exists():
            continue
        results.append(ingest_log(entry["log_id"], source, output_root))
    return results
