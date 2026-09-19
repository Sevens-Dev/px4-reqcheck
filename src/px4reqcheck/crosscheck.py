"""Versioned Python-to-C++ exchange and agreement checks."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator

from px4reqcheck.analytics.evaluation import (
    _initial_parameters,
    _topic,
    evaluate_corpus,
)
from px4reqcheck.ingest.aliases import load_signal_aliases, resolve_signals
from px4reqcheck.requirements import Verdict

PARAMETER_CAUSES = {"param_missing", "param_disabled", "param_changed_in_flight"}
SCHEMA_ROOT = Path(__file__).parents[2] / "export"


def export_checks(data_root: Path, output: Path) -> dict[str, Any]:
    """Export scalar checks plus independent raw descent inputs."""
    verdicts, _ = evaluate_corpus(data_root)
    grouped: dict[str, list[Verdict]] = defaultdict(list)
    for verdict in verdicts:
        grouped[verdict.log_id].append(verdict)

    signal_aliases = load_signal_aliases(Path(__file__).parent / "ingest" / "aliases.yaml")
    logs: list[dict[str, Any]] = []
    for log_root in sorted(data_root.glob("log_id=*")):
        metadata = json.loads((log_root / "logmeta.json").read_text(encoding="utf-8"))
        log_id = str(metadata["log_id"])
        signals = resolve_signals(log_root, metadata.get("sw_version"), signal_aliases)
        rows = sorted(grouped[log_id], key=lambda verdict: verdict.requirement_id)
        logs.append(_log_contract(log_id, rows, _raw_descent(log_root, signals)))

    document = {"version": 1, "logs": logs}
    validate_contract(document, SCHEMA_ROOT / "checks.schema.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return document


def _log_contract(log_id: str, verdicts: list[Verdict], raw: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, float | None] = {}
    reasons: dict[str, str | None] = {}
    thresholds: list[dict[str, Any]] = []
    for verdict in verdicts:
        metrics[verdict.metric] = verdict.metric_value
        reasons[verdict.metric] = (
            verdict.cause
            if verdict.status == "not_evaluable" and verdict.cause not in PARAMETER_CAUSES
            else None
        )
        thresholds.append(
            {
                "req_id": verdict.requirement_id,
                "metric": verdict.metric,
                "comparator": verdict.comparator,
                "value": verdict.threshold_value,
                "reason": verdict.cause if verdict.cause in PARAMETER_CAUSES else None,
            }
        )
    return {
        "log_id": log_id,
        "metrics": metrics,
        "metric_reasons": reasons,
        "thresholds": thresholds,
        "raw": raw,
    }


def _raw_descent(log_root: Path, signals: dict[str, Any]) -> dict[str, Any]:
    parameters = _initial_parameters(log_root)
    raw: dict[str, Any] = {
        "timestamps_us": [],
        "descent_vz": [],
        "z_m": [],
        "land_edge_us": None,
        "land_edge_index": None,
        "land_alt2_m": parameters.get("MPC_LAND_ALT2"),
        "reason": None,
    }
    local_signal = signals.get("local_position_vz")
    landed_signal = signals.get("land_detected")
    if local_signal is None or landed_signal is None:
        raw["reason"] = "signal_missing"
        return raw

    local = pd.read_parquet(
        log_root / f"topic_{local_signal.topic}.parquet",
        columns=["timestamp", "vz", "z"],
    ).sort_values("timestamp")
    timestamps = local["timestamp"].to_numpy(dtype=np.int64)
    raw["timestamps_us"] = timestamps.tolist()
    raw["descent_vz"] = [_finite_or_none(value) for value in local["vz"]]
    raw["z_m"] = [_finite_or_none(value) for value in local["z"]]

    landed = _topic(log_root, landed_signal)
    values = landed[landed_signal.fields[0]].to_numpy(dtype=np.int64)
    rising = np.flatnonzero((values[:-1] == 0) & (values[1:] == 1)) + 1
    if not rising.size:
        raw["reason"] = "window_missing"
        return raw
    edge = int(landed.iloc[rising[0]]["timestamp"])
    raw["land_edge_us"] = edge
    if timestamps.size:
        raw["land_edge_index"] = int(
            np.clip(np.searchsorted(timestamps, edge), 0, timestamps.size - 1)
        )
    return raw


def _finite_or_none(value: object) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def validate_contract(document: Any, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)


def assert_agreement(python_verdicts: Path, cpp_verdicts: Path) -> int:
    """Require identical verdict sets and independently computed descent metrics."""
    python_rows = json.loads(python_verdicts.read_text(encoding="utf-8"))
    cpp_rows = json.loads(cpp_verdicts.read_text(encoding="utf-8"))
    validate_contract(cpp_rows, SCHEMA_ROOT / "cpp_verdicts.schema.json")
    python_by_key = {(row["log_id"], row["requirement_id"]): row for row in python_rows}
    cpp_by_key = {(row["log_id"], row["req_id"]): row for row in cpp_rows}
    if python_by_key.keys() != cpp_by_key.keys():
        raise AssertionError("Python and C++ verdict sets differ")
    for key, python_row in python_by_key.items():
        cpp_row = cpp_by_key[key]
        if python_row["status"] != cpp_row["status"]:
            raise AssertionError(f"status mismatch for {key}")
        if python_row["cause"] != cpp_row["reason"]:
            raise AssertionError(f"reason mismatch for {key}")
        if python_row["metric"] == "descent_rate_pre_land_p95":
            _assert_metric_close(key, python_row["metric_value"], cpp_row["metric_value"])
    return len(python_by_key)


def _assert_metric_close(key: tuple[str, str], python_value: Any, cpp_value: Any) -> None:
    if python_value is None or cpp_value is None:
        if python_value != cpp_value:
            raise AssertionError(f"descent metric availability mismatch for {key}")
        return
    if not math.isclose(float(python_value), float(cpp_value), rel_tol=0.0, abs_tol=1e-6):
        raise AssertionError(f"descent metric mismatch for {key}: {python_value} != {cpp_value}")
