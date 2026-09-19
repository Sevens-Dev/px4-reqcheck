"""Adapt normalized Parquet logs into requirement metrics and verdicts."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from px4reqcheck.ingest.aliases import ResolvedSignal, load_signal_aliases, resolve_signals
from px4reqcheck.metrics import (
    MetricResult,
    altitude_error_rms_cruise,
    battery_value_at_disarm,
    descent_rate_pre_land_p95,
    gps_min_fix_type,
    max_distance_from_home,
    vibration_rms_z,
)
from px4reqcheck.params import load_parameter_aliases
from px4reqcheck.requirements import Verdict, evaluate_requirement, load_requirements

METRIC_UNITS = {
    "battery_remaining_at_disarm": "fraction",
    "battery_voltage_at_disarm": "V",
    "max_distance_from_home": "m",
    "descent_rate_pre_land_p95": "m/s",
    "gps_min_fix_type": "fix_type",
    "altitude_error_rms_cruise": "m",
    "vibration_rms_z": "m/s^2",
}


def evaluate_corpus(data_root: Path) -> tuple[list[Verdict], list[dict[str, Any]]]:
    requirements_path = Path(__file__).parents[1] / "requirements" / "requirements.yaml"
    parameter_aliases_path = Path(__file__).parents[1] / "params" / "aliases.yaml"
    signal_aliases_path = Path(__file__).parents[1] / "ingest" / "aliases.yaml"
    requirements = load_requirements(requirements_path)
    parameter_aliases = load_parameter_aliases(parameter_aliases_path)
    signal_aliases = load_signal_aliases(signal_aliases_path)
    verdicts: list[Verdict] = []
    resolved_rows: list[dict[str, Any]] = []
    for log_root in sorted(data_root.glob("log_id=*")):
        metadata = json.loads((log_root / "logmeta.json").read_text(encoding="utf-8"))
        log_id = str(metadata["log_id"])
        resolved = resolve_signals(log_root, metadata.get("sw_version"), signal_aliases)
        initial = _initial_parameters(log_root)
        changes = _changed_parameters(log_root)
        metrics = _metric_results(log_root, resolved, initial)
        available = set(resolved)
        for signal in resolved.values():
            resolved_rows.append(
                {
                    "log_id": log_id,
                    "logical_signal": signal.logical_name,
                    "topic": signal.topic,
                    "fields": ",".join(signal.fields),
                    "scale": signal.scale,
                    "unit": signal.unit,
                }
            )
        for requirement in requirements:
            metric = metrics.get(requirement.metric, MetricResult(None, "signal_missing"))
            verdicts.append(
                evaluate_requirement(
                    log_id=log_id,
                    requirement=requirement,
                    metric_result=metric,
                    metric_unit=METRIC_UNITS[requirement.metric],
                    aliases=parameter_aliases,
                    initial_parameters=initial,
                    changed_parameters=changes,
                    available_signals=available,
                )
            )
    return verdicts, resolved_rows


def verdict_records(verdicts: list[Verdict]) -> list[dict[str, Any]]:
    return [asdict(verdict) for verdict in verdicts]


def _initial_parameters(log_root: Path) -> dict[str, float]:
    frame = pd.read_parquet(log_root / "parameters.parquet", columns=["name", "value_num"])
    return dict(zip(frame["name"], frame["value_num"], strict=True))


def _changed_parameters(log_root: Path) -> list[tuple[int, str, float]]:
    path = log_root / "parameter_changes.parquet"
    if not path.exists():
        return []
    frame = pd.read_parquet(path)
    return [
        (int(row.timestamp), str(row.name), float(row.value_num))
        for row in frame.itertuples(index=False)
    ]


def _topic(log_root: Path, signal: ResolvedSignal) -> pd.DataFrame:
    columns = ["timestamp", *signal.fields]
    frame = pd.read_parquet(log_root / f"topic_{signal.topic}.parquet", columns=columns)
    for field in signal.fields:
        frame[field] = frame[field] * signal.scale
    return frame.sort_values("timestamp")


def _missing() -> MetricResult:
    return MetricResult(None, "signal_missing")


def _metric_results(
    log_root: Path,
    signals: dict[str, ResolvedSignal],
    initial_parameters: dict[str, float],
) -> dict[str, MetricResult]:
    metrics = {
        "battery_remaining_at_disarm": _missing(),
        "battery_voltage_at_disarm": _missing(),
        "max_distance_from_home": _missing(),
        "descent_rate_pre_land_p95": _missing(),
        "gps_min_fix_type": _missing(),
        "altitude_error_rms_cruise": _missing(),
        "vibration_rms_z": _missing(),
    }
    armed_path = log_root / "topic_actuator_armed.parquet"
    if armed_path.exists():
        armed = pd.read_parquet(armed_path, columns=["timestamp", "armed"])
        for logical_name, metric_name in (
            ("battery_remaining", "battery_remaining_at_disarm"),
            ("battery_voltage", "battery_voltage_at_disarm"),
        ):
            signal = signals.get(logical_name)
            if signal is not None:
                values = _topic(log_root, signal)
                metrics[metric_name] = battery_value_at_disarm(
                    values["timestamp"].to_numpy(),
                    values[signal.fields[0]].to_numpy(),
                    armed["timestamp"].to_numpy(),
                    armed["armed"].to_numpy(),
                )
    _distance_metric(log_root, signals, metrics)
    _landing_metric(log_root, signals, initial_parameters, metrics)
    _gps_metric(log_root, signals, metrics)
    _cruise_metric(log_root, signals, metrics)
    _vibration_metric(log_root, signals, metrics)
    return metrics


def _distance_metric(
    log_root: Path,
    signals: dict[str, ResolvedSignal],
    metrics: dict[str, MetricResult],
) -> None:
    local_signal = signals.get("local_position")
    home_signal = signals.get("home_position")
    if local_signal is None or home_signal is None:
        return
    local = _topic(log_root, local_signal)
    home = _topic(log_root, home_signal)
    aligned = pd.merge_asof(
        local, home, on="timestamp", direction="backward", suffixes=("", "_home")
    )
    metrics["max_distance_from_home"] = max_distance_from_home(
        aligned["x"].to_numpy(),
        aligned["y"].to_numpy(),
        aligned["x_home"].to_numpy(),
        aligned["y_home"].to_numpy(),
    )


def _landing_metric(
    log_root: Path,
    signals: dict[str, ResolvedSignal],
    initial_parameters: dict[str, float],
    metrics: dict[str, MetricResult],
) -> None:
    local_signal = signals.get("local_position_vz")
    landed_signal = signals.get("land_detected")
    if local_signal is None or landed_signal is None:
        return
    local = pd.read_parquet(
        log_root / f"topic_{local_signal.topic}.parquet",
        columns=["timestamp", "vz", "z"],
    ).sort_values("timestamp")
    landed = _topic(log_root, landed_signal)
    values = landed[landed_signal.fields[0]].to_numpy(dtype=np.int64)
    rising = np.flatnonzero((values[:-1] == 0) & (values[1:] == 1)) + 1
    land_edge = int(landed.iloc[rising[0]]["timestamp"]) if rising.size else None
    altitude = initial_parameters.get("MPC_LAND_ALT2")
    if altitude is None:
        return
    metrics["descent_rate_pre_land_p95"] = descent_rate_pre_land_p95(
        local["timestamp"].to_numpy(),
        local["vz"].to_numpy(),
        local["z"].to_numpy(),
        land_edge_us=land_edge,
        land_alt2_m=float(altitude),
    )


def _gps_metric(
    log_root: Path,
    signals: dict[str, ResolvedSignal],
    metrics: dict[str, MetricResult],
) -> None:
    gps_signal = signals.get("gps")
    nav_signal = signals.get("nav_state")
    if gps_signal is None or nav_signal is None:
        return
    gps = _topic(log_root, gps_signal)
    nav = _topic(log_root, nav_signal)
    aligned = pd.merge_asof(gps, nav, on="timestamp", direction="backward")
    mission = aligned.loc[aligned[nav_signal.fields[0]] == 3, gps_signal.fields[0]]
    metrics["gps_min_fix_type"] = (
        gps_min_fix_type(mission.to_numpy())
        if not mission.empty
        else MetricResult(None, "window_missing")
    )


def _cruise_metric(
    log_root: Path,
    signals: dict[str, ResolvedSignal],
    metrics: dict[str, MetricResult],
) -> None:
    local_signal = signals.get("local_position")
    setpoint_signal = signals.get("trajectory_setpoint")
    nav_signal = signals.get("nav_state")
    if local_signal is None or setpoint_signal is None or nav_signal is None:
        return
    local = pd.read_parquet(
        log_root / f"topic_{local_signal.topic}.parquet",
        columns=["timestamp", "z"],
    ).sort_values("timestamp")
    setpoint = _topic(log_root, setpoint_signal).rename(
        columns={setpoint_signal.fields[0]: "setpoint_z"}
    )
    nav = _topic(log_root, nav_signal).rename(columns={nav_signal.fields[0]: "nav_state"})
    aligned = pd.merge_asof(local, setpoint, on="timestamp", direction="backward")
    aligned = pd.merge_asof(aligned, nav, on="timestamp", direction="backward")
    metrics["altitude_error_rms_cruise"] = altitude_error_rms_cruise(
        aligned["timestamp"].to_numpy(),
        aligned["z"].to_numpy(),
        aligned["setpoint_z"].to_numpy(),
        aligned["nav_state"].fillna(-1).to_numpy(),
    )


def _vibration_metric(
    log_root: Path,
    signals: dict[str, ResolvedSignal],
    metrics: dict[str, MetricResult],
) -> None:
    signal = signals.get("sensor_combined_or_imu_status")
    if signal is None:
        return
    frame = _topic(log_root, signal)
    values = frame[signal.fields[0]].to_numpy(dtype=np.float64)
    if signal.topic == "sensor_combined":
        timestamps = frame["timestamp"].to_numpy(dtype=np.int64)
        intervals = np.diff(timestamps)
        positive = intervals[intervals > 0]
        rate = 1_000_000 / float(np.median(positive)) if positive.size else 0.0
        metrics["vibration_rms_z"] = vibration_rms_z(values, rate)
    else:
        finite = values[np.isfinite(values)]
        metrics["vibration_rms_z"] = (
            MetricResult(float(np.max(finite)))
            if finite.size
            else MetricResult(None, "insufficient_samples")
        )
