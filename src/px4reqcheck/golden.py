"""Golden-output regression helpers shared by CI and real-corpus tiers."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from px4reqcheck.analytics.evaluation import evaluate_corpus


def assert_golden(data_root: Path, expected_path: Path, tolerances_path: Path) -> int:
    actual_verdicts, _ = evaluate_corpus(data_root)
    actual = json.loads(json.dumps([asdict(verdict) for verdict in actual_verdicts]))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    tolerances = yaml.safe_load(tolerances_path.read_text(encoding="utf-8"))
    actual_by_key = {_key(row): row for row in actual}
    expected_by_key = {_key(row): row for row in expected}
    if actual_by_key.keys() != expected_by_key.keys():
        raise AssertionError("golden verdict sets differ")

    exact_fields = {
        "log_id",
        "requirement_id",
        "metric",
        "unit",
        "status",
        "threshold_value",
        "comparator",
        "cause",
        "source_params",
    }
    for key, expected_row in expected_by_key.items():
        actual_row = actual_by_key[key]
        for field in exact_fields:
            if actual_row[field] != expected_row[field]:
                raise AssertionError(f"{field} mismatch for {key}")
        _assert_metric(key, actual_row, expected_row, tolerances)
    return len(actual_by_key)


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["log_id"]), str(row["requirement_id"])


def _assert_metric(
    key: tuple[str, str],
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerances: dict[str, dict[str, float]],
) -> None:
    actual_value = actual["metric_value"]
    expected_value = expected["metric_value"]
    if actual_value is None or expected_value is None:
        if actual_value != expected_value:
            raise AssertionError(f"metric availability mismatch for {key}")
        return
    tolerance = tolerances[expected["metric"]]
    if not math.isclose(
        float(actual_value),
        float(expected_value),
        rel_tol=float(tolerance["relative"]),
        abs_tol=float(tolerance["absolute"]),
    ):
        raise AssertionError(f"metric mismatch for {key}: {actual_value} != {expected_value}")
