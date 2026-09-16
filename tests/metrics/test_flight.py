import math

import numpy as np
import pytest

from px4reqcheck.metrics import (
    MetricResult,
    altitude_error_rms_cruise,
    battery_value_at_disarm,
    descent_rate_pre_land_p95,
    gps_max_eph,
    gps_min_fix_type,
    max_distance_from_home,
    vibration_rms_z,
)


def test_metric_result_requires_value_xor_reason() -> None:
    with pytest.raises(ValueError):
        MetricResult(None)
    with pytest.raises(ValueError):
        MetricResult(1.0, "quality_fail")


def test_altitude_error_rms_uses_trimmed_mission_window() -> None:
    timestamps = np.arange(0, 61, dtype=np.int64) * 1_000_000
    local_z = np.zeros(timestamps.size)
    setpoint_z = np.zeros(timestamps.size)
    setpoint_z[10:51] = 2.0
    nav_state = np.full(timestamps.size, 3)

    result = altitude_error_rms_cruise(timestamps, local_z, setpoint_z, nav_state)

    assert result.value == 2.0
    assert result.window_start_us == 10_000_000
    assert result.window_end_us == 50_000_000


def test_altitude_error_requires_thirty_seconds_after_trimming() -> None:
    timestamps = np.arange(0, 49, dtype=np.int64) * 1_000_000

    result = altitude_error_rms_cruise(timestamps, np.zeros(49), np.zeros(49), np.full(49, 3))

    assert result.reason == "window_missing"


def test_descent_rate_p95_uses_linear_percentile_and_altitude_gate() -> None:
    timestamps = np.arange(0, 7, dtype=np.int64) * 1_000_000
    vz = np.array([99.0, 1.0, 2.0, 3.0, 4.0, 100.0, 5.0])
    z = np.array([-1.0, -1.0, -1.0, -1.0, -1.0, -6.0, -1.0])

    result = descent_rate_pre_land_p95(timestamps, vz, z, land_edge_us=6_000_000, land_alt2_m=5.0)

    assert result.value == pytest.approx(4.8)


def test_distance_from_home_has_hand_computed_answer() -> None:
    result = max_distance_from_home([0.0, 3.0], [0.0, 4.0], [0.0, 0.0], [0.0, 0.0])

    assert result.value == 5.0


def test_gps_scalars_have_hand_computed_answers() -> None:
    assert gps_min_fix_type([5, 3, 4]).value == 3.0
    assert gps_max_eph([0.4, 1.2, 0.8]).value == 1.2


def test_battery_value_uses_last_sample_before_disarm() -> None:
    result = battery_value_at_disarm([1, 2, 3, 4], [12.0, 11.8, 11.5, 11.0], [0, 3, 5], [0, 1, 0])

    assert result.value == 11.0
    assert result.window_start_us == 4
    assert result.window_end_us == 5


def test_vibration_rms_matches_sine_rms() -> None:
    sample_rate = 400.0
    t = np.arange(0, 2, 1 / sample_rate)
    amplitude = 0.4
    signal = 9.81 + amplitude * np.sin(2 * math.pi * 40 * t)

    result = vibration_rms_z(signal, sample_rate)

    assert result.value == pytest.approx(amplitude / math.sqrt(2), rel=0.02)


def test_vibration_rejects_sample_rate_below_nyquist_margin() -> None:
    result = vibration_rms_z(np.ones(100), 199.9)

    assert result.reason == "insufficient_samples"
