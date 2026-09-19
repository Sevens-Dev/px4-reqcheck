from __future__ import annotations

import json
from pathlib import Path

import pytest

from px4reqcheck.crosscheck import (
    SCHEMA_ROOT,
    _log_contract,
    assert_agreement,
    validate_contract,
)
from px4reqcheck.requirements import Verdict


def test_exchange_document_validates_parameter_and_metric_causes() -> None:
    verdicts = [
        Verdict(
            log_id="log-1",
            requirement_id="REQ-PASS",
            metric="battery",
            unit="fraction",
            status="pass",
            metric_value=0.5,
            threshold_value=0.4,
            comparator=">=",
            cause=None,
            source_params=(),
        ),
        Verdict(
            log_id="log-1",
            requirement_id="REQ-DISABLED",
            metric="distance",
            unit="m",
            status="not_evaluable",
            metric_value=None,
            threshold_value=None,
            comparator="<=",
            cause="param_disabled",
            source_params=(),
        ),
    ]
    raw = {
        "timestamps_us": [],
        "descent_vz": [],
        "z_m": [],
        "land_edge_us": None,
        "land_edge_index": None,
        "land_alt2_m": 5.0,
        "reason": "signal_missing",
    }
    document = {"version": 1, "logs": [_log_contract("log-1", verdicts, raw)]}

    validate_contract(document, SCHEMA_ROOT / "checks.schema.json")
    disabled = document["logs"][0]["thresholds"][1]
    assert disabled["reason"] == "param_disabled"
    assert document["logs"][0]["metric_reasons"]["distance"] is None


def test_agreement_checks_status_reason_and_descent_tolerance(tmp_path: Path) -> None:
    python_rows = [
        {
            "log_id": "log-1",
            "requirement_id": "REQ-LAND",
            "metric": "descent_rate_pre_land_p95",
            "status": "pass",
            "metric_value": 1.25,
            "cause": None,
        }
    ]
    cpp_rows = [
        {
            "log_id": "log-1",
            "req_id": "REQ-LAND",
            "status": "pass",
            "metric_value": 1.2500005,
            "reason": None,
        }
    ]
    python_path = tmp_path / "python.json"
    cpp_path = tmp_path / "cpp.json"
    python_path.write_text(json.dumps(python_rows), encoding="utf-8")
    cpp_path.write_text(json.dumps(cpp_rows), encoding="utf-8")

    assert assert_agreement(python_path, cpp_path) == 1
    cpp_rows[0]["metric_value"] = 1.250002
    cpp_path.write_text(json.dumps(cpp_rows), encoding="utf-8")
    with pytest.raises(AssertionError, match="descent metric mismatch"):
        assert_agreement(python_path, cpp_path)
