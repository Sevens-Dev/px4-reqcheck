#!/usr/bin/env python3
"""Regenerate the three deterministic, committed tier-1 Parquet fixtures."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from px4reqcheck.analytics.evaluation import evaluate_corpus

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "golden" / "ci"
SECONDS = np.arange(0, 61, dtype=np.int64)
TIMESTAMPS = SECONDS * 1_000_000


def write_frame(log_root: Path, topic: str, **columns: object) -> None:
    pd.DataFrame(columns).to_parquet(log_root / f"topic_{topic}.parquet", index=False)


def write_parameters(log_root: Path, values: dict[str, float]) -> None:
    pd.DataFrame(
        {
            "name": list(values),
            "value_num": list(values.values()),
            "value_type": ["float"] * len(values),
        }
    ).to_parquet(log_root / "parameters.parquet", index=False)


def create_fixture(name: str, mode: str) -> None:
    log_root = OUTPUT / f"log_id={name}"
    log_root.mkdir(parents=True)
    (log_root / "logmeta.json").write_text(
        json.dumps({"log_id": name, "sw_version": "1.15.0"}) + "\n",
        encoding="utf-8",
    )
    parameters = {
        "BAT_LOW_THR": 0.2,
        "BAT1_N_CELLS": 4.0,
        "BAT1_V_EMPTY": 3.5,
        "GF_MAX_HOR_DIST": 100.0,
        "MPC_LAND_SPEED": 1.0,
        "MPC_LAND_ALT2": 10.0,
        "COM_DISARM_LAND": 2.0,
    }
    if mode == "partial":
        parameters["BAT1_N_CELLS"] = 0.0
        parameters["GF_MAX_HOR_DIST"] = 0.0
    write_parameters(log_root, parameters)

    write_frame(log_root, "actuator_armed", timestamp=[0, 60_000_000], armed=[1, 0])
    write_frame(
        log_root,
        "battery_status",
        timestamp=[0, 50_000_000, 61_000_000],
        remaining=[0.8, 0.1 if mode == "fail" else 0.5, 0.0],
        voltage_filtered_v=[16.0, 13.0 if mode == "fail" else 15.0, 12.0],
    )
    write_frame(
        log_root,
        "vehicle_land_detected",
        timestamp=[0, 60_000_000],
        landed=[0, 1],
    )
    if mode == "partial":
        return

    fail = mode == "fail"
    local_z = np.full(TIMESTAMPS.size, -5.0)
    write_frame(
        log_root,
        "vehicle_local_position",
        timestamp=TIMESTAMPS,
        x=np.linspace(0.0, 120.0 if fail else 20.0, TIMESTAMPS.size),
        y=np.zeros(TIMESTAMPS.size),
        z=local_z,
        vz=np.full(TIMESTAMPS.size, 1.5 if fail else 0.8),
    )
    write_frame(log_root, "home_position", timestamp=[0], x=[0.0], y=[0.0])
    write_frame(
        log_root,
        "sensor_gps",
        timestamp=[0, 30_000_000, 60_000_000],
        fix_type=[2 if fail else 3] * 3,
    )
    write_frame(
        log_root,
        "vehicle_status",
        timestamp=TIMESTAMPS,
        nav_state=np.full(TIMESTAMPS.size, 3),
    )
    write_frame(
        log_root,
        "trajectory_setpoint",
        timestamp=TIMESTAMPS,
        **{"position[2]": np.full(TIMESTAMPS.size, -7.0 if fail else -5.4)},
    )
    write_frame(
        log_root,
        "vehicle_imu_status",
        timestamp=[0, 60_000_000],
        accel_vibration_metric=[0.1, 0.5 if fail else 0.2],
    )


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    create_fixture("synthetic-pass", "pass")
    create_fixture("synthetic-fail", "fail")
    create_fixture("synthetic-partial", "partial")
    verdicts, _ = evaluate_corpus(OUTPUT)
    expected = [asdict(verdict) for verdict in verdicts]
    (OUTPUT / "expected-verdicts.json").write_text(
        json.dumps(expected, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
