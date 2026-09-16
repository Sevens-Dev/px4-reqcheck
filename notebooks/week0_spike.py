"""Week 0 learning spike: ULog -> pandas -> metric -> Parquet/DuckDB -> plot.

This is intentionally exploratory code, not the production ingest or metric path.
It uses five public PX4 v1.15 logs selected during the source-verification gate.
Raw logs and generated outputs stay under git-ignored ``data/``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "px4reqcheck-mpl"))

import duckdb
import matplotlib
import numpy as np
import pandas as pd
from pyulog import ULog

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

LOG_IDS = (
    "6032c737-ca04-4331-92a2-d666d9a39d51",
    "ad0d295b-ebfc-4382-ad7c-e72ad43091b0",
    "4e2226d8-a13c-4aba-8683-35fb38308fb8",
    "f6591f05-7b14-4aad-9088-beec302362db",
    "2a7d3156-d02c-455c-8859-a68d50afc149",
)

TOPICS = [
    "vehicle_local_position",
    "trajectory_setpoint",
    "vehicle_local_position_setpoint",
    "vehicle_status",
]


def dataset_frame(ulog: ULog, name: str, fields: tuple[str, ...]) -> pd.DataFrame:
    """Return timestamp plus selected fields from topic instance zero."""
    dataset = ulog.get_dataset(name, multi_instance=0)
    return pd.DataFrame({field: dataset.data[field] for field in ("timestamp", *fields)})


def setpoint_frame(ulog: ULog) -> pd.DataFrame:
    """Read the v1.15 setpoint, retaining a fallback used by older logs."""
    try:
        frame = dataset_frame(ulog, "trajectory_setpoint", ("position[2]",))
        return frame.rename(columns={"position[2]": "z_setpoint"})
    except (KeyError, IndexError):
        frame = dataset_frame(ulog, "vehicle_local_position_setpoint", ("z",))
        return frame.rename(columns={"z": "z_setpoint"})


def mission_altitude_errors(log_id: str, path: Path) -> pd.DataFrame:
    """Compute exploratory cruise altitude error samples for one log."""
    ulog = ULog(str(path), message_name_filter_list=TOPICS)
    local = dataset_frame(ulog, "vehicle_local_position", ("z",)).sort_values("timestamp")
    setpoint = setpoint_frame(ulog).sort_values("timestamp")
    status = dataset_frame(ulog, "vehicle_status", ("nav_state",)).sort_values("timestamp")

    aligned = pd.merge_asof(local, setpoint, on="timestamp", direction="nearest")
    aligned = pd.merge_asof(aligned, status, on="timestamp", direction="backward")
    aligned = aligned.dropna(subset=["z", "z_setpoint", "nav_state"])
    aligned["segment"] = aligned["nav_state"].ne(aligned["nav_state"].shift()).cumsum()

    kept: list[pd.DataFrame] = []
    for _, segment in aligned.loc[aligned["nav_state"] == 3].groupby("segment"):
        start = int(segment["timestamp"].iloc[0])
        end = int(segment["timestamp"].iloc[-1])
        if end - start < 50_000_000:
            continue
        trimmed = segment.loc[
            (segment["timestamp"] >= start + 10_000_000)
            & (segment["timestamp"] <= end - 10_000_000)
        ].copy()
        if not trimmed.empty:
            trimmed["log_id"] = log_id
            trimmed["error_m"] = trimmed["z"] - trimmed["z_setpoint"]
            kept.append(trimmed[["log_id", "timestamp", "error_m"]])
    if not kept:
        return pd.DataFrame(columns=["log_id", "timestamp", "error_m"])
    return pd.concat(kept, ignore_index=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw_dir = root / "data" / "raw"
    output_dir = root / "data" / "week0"
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = [mission_altitude_errors(log_id, raw_dir / f"{log_id}.ulg") for log_id in LOG_IDS]
    samples = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    parquet_path = output_dir / "altitude_error_samples.parquet"
    samples.to_parquet(parquet_path, index=False)

    query = f"""
        SELECT log_id,
               count(*) AS sample_count,
               sqrt(avg(error_m * error_m)) AS altitude_error_rms_m
        FROM read_parquet('{parquet_path.as_posix()}')
        GROUP BY log_id
        ORDER BY log_id
    """
    summary = duckdb.sql(query).df()
    (output_dir / "summary.json").write_text(
        json.dumps(summary.to_dict(orient="records"), indent=2) + "\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(8, 4))
    axis.bar(summary["log_id"].str.slice(0, 8), summary["altitude_error_rms_m"])
    axis.set(title="Week 0 exploratory metric", xlabel="log id prefix", ylabel="RMS error (m)")
    figure.tight_layout()
    figure.savefig(output_dir / "altitude_error_rms.png", dpi=150)
    plt.close(figure)

    values = summary["altitude_error_rms_m"].to_numpy(dtype=float)
    assert np.all(np.isfinite(values))
    print(f"processed={len(LOG_IDS)} evaluable={len(summary)}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
