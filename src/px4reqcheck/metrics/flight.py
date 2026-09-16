"""Per-flight scalar metrics with explicit non-evaluable outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.signal import butter, sosfiltfilt

MetricReason = Literal["signal_missing", "window_missing", "insufficient_samples", "quality_fail"]


@dataclass(frozen=True)
class MetricResult:
    value: float | None
    reason: MetricReason | None = None
    window_start_us: int | None = None
    window_end_us: int | None = None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.reason is None):
            raise ValueError("exactly one of value or reason must be present")


def _float_array(values: NDArray[np.floating] | list[float]) -> NDArray[np.float64]:
    return np.asarray(values, dtype=np.float64)


def _int_array(values: NDArray[np.integer] | list[int]) -> NDArray[np.int64]:
    return np.asarray(values, dtype=np.int64)


def altitude_error_rms_cruise(
    timestamps_us: NDArray[np.integer] | list[int],
    local_z_m: NDArray[np.floating] | list[float],
    setpoint_z_m: NDArray[np.floating] | list[float],
    nav_state: NDArray[np.integer] | list[int],
) -> MetricResult:
    """RMS z error in trimmed AUTO_MISSION segments."""
    timestamps = _int_array(timestamps_us)
    local_z = _float_array(local_z_m)
    setpoint_z = _float_array(setpoint_z_m)
    states = _int_array(nav_state)
    if not (timestamps.size == local_z.size == setpoint_z.size == states.size):
        raise ValueError("all arrays must have equal length")
    if timestamps.size == 0:
        return MetricResult(None, "signal_missing")

    chosen: list[NDArray[np.int64]] = []
    mission = states == 3
    transitions = np.flatnonzero(np.diff(mission.astype(np.int8)) != 0) + 1
    for indices in np.split(np.arange(timestamps.size), transitions):
        if indices.size == 0 or not mission[indices[0]]:
            continue
        start = timestamps[indices[0]]
        end = timestamps[indices[-1]]
        trimmed = indices[
            (timestamps[indices] >= start + 10_000_000) & (timestamps[indices] <= end - 10_000_000)
        ]
        if trimmed.size and timestamps[trimmed[-1]] - timestamps[trimmed[0]] >= 30_000_000:
            chosen.append(trimmed)
    if not chosen:
        return MetricResult(None, "window_missing")
    selected = np.concatenate(chosen)
    finite = np.isfinite(local_z[selected]) & np.isfinite(setpoint_z[selected])
    selected = selected[finite]
    if selected.size < 2:
        return MetricResult(None, "insufficient_samples")
    errors = local_z[selected] - setpoint_z[selected]
    return MetricResult(
        float(np.sqrt(np.mean(np.square(errors)))),
        window_start_us=int(timestamps[selected[0]]),
        window_end_us=int(timestamps[selected[-1]]),
    )


def descent_rate_pre_land_p95(
    timestamps_us: NDArray[np.integer] | list[int],
    vz_m_s: NDArray[np.floating] | list[float],
    z_m: NDArray[np.floating] | list[float],
    *,
    land_edge_us: int | None,
    land_alt2_m: float,
) -> MetricResult:
    """Linear-method p95 NED descent rate in the five seconds before landing."""
    if land_edge_us is None:
        return MetricResult(None, "window_missing")
    timestamps = _int_array(timestamps_us)
    vz = _float_array(vz_m_s)
    z = _float_array(z_m)
    if not (timestamps.size == vz.size == z.size):
        raise ValueError("all arrays must have equal length")
    mask = (
        (timestamps >= land_edge_us - 5_000_000)
        & (timestamps <= land_edge_us)
        & (-z < land_alt2_m)
        & np.isfinite(vz)
        & np.isfinite(z)
    )
    selected = vz[mask]
    if selected.size < 2:
        return MetricResult(None, "insufficient_samples")
    return MetricResult(
        float(np.percentile(selected, 95, method="linear")),
        window_start_us=land_edge_us - 5_000_000,
        window_end_us=land_edge_us,
    )


def max_distance_from_home(
    x_m: NDArray[np.floating] | list[float],
    y_m: NDArray[np.floating] | list[float],
    home_x_m: NDArray[np.floating] | list[float],
    home_y_m: NDArray[np.floating] | list[float],
) -> MetricResult:
    arrays = tuple(_float_array(values) for values in (x_m, y_m, home_x_m, home_y_m))
    if len({array.size for array in arrays}) != 1:
        raise ValueError("all arrays must have equal length")
    if arrays[0].size == 0:
        return MetricResult(None, "signal_missing")
    finite = np.logical_and.reduce(tuple(np.isfinite(array) for array in arrays))
    if not finite.any():
        return MetricResult(None, "insufficient_samples")
    x, y, home_x, home_y = (array[finite] for array in arrays)
    return MetricResult(float(np.max(np.hypot(x - home_x, y - home_y))))


def gps_min_fix_type(values: NDArray[np.integer] | list[int]) -> MetricResult:
    fixes = _int_array(values)
    if fixes.size == 0:
        return MetricResult(None, "signal_missing")
    return MetricResult(float(np.min(fixes)))


def gps_max_eph(values: NDArray[np.floating] | list[float]) -> MetricResult:
    eph = _float_array(values)
    finite = eph[np.isfinite(eph)]
    if finite.size == 0:
        return MetricResult(None, "signal_missing")
    return MetricResult(float(np.max(finite)))


def battery_value_at_disarm(
    value_timestamps_us: NDArray[np.integer] | list[int],
    values: NDArray[np.floating] | list[float],
    armed_timestamps_us: NDArray[np.integer] | list[int],
    armed: NDArray[np.integer] | list[int],
) -> MetricResult:
    """Return the last finite value at or before the first armed-to-disarmed edge."""
    value_timestamps = _int_array(value_timestamps_us)
    samples = _float_array(values)
    armed_timestamps = _int_array(armed_timestamps_us)
    armed_values = _int_array(armed)
    if value_timestamps.size != samples.size or armed_timestamps.size != armed_values.size:
        raise ValueError("timestamp and value arrays must have equal length")
    falling = np.flatnonzero((armed_values[:-1] == 1) & (armed_values[1:] == 0)) + 1
    if falling.size == 0:
        return MetricResult(None, "window_missing")
    edge = int(armed_timestamps[falling[0]])
    candidates = np.flatnonzero((value_timestamps <= edge) & np.isfinite(samples))
    if candidates.size == 0:
        return MetricResult(None, "insufficient_samples")
    index = int(candidates[np.argmax(value_timestamps[candidates])])
    return MetricResult(
        float(samples[index]),
        window_start_us=int(value_timestamps[index]),
        window_end_us=edge,
    )


def vibration_rms_z(
    acceleration_z: NDArray[np.floating] | list[float], sample_rate_hz: float
) -> MetricResult:
    """Compute RMS acceleration in the 10-80 Hz FFT band after baseline removal."""
    if sample_rate_hz < 200:
        return MetricResult(None, "insufficient_samples")
    values = _float_array(acceleration_z)
    if not np.all(np.isfinite(values)):
        return MetricResult(None, "quality_fail")
    if values.size < 32:
        return MetricResult(None, "insufficient_samples")
    lowpass = butter(2, 5, btype="lowpass", fs=sample_rate_hz, output="sos")
    centered = values - sosfiltfilt(lowpass, values)
    spectrum = np.fft.rfft(centered)
    frequencies = np.fft.rfftfreq(values.size, d=1 / sample_rate_hz)
    band = (frequencies >= 10) & (frequencies <= 80)
    if not band.any():
        return MetricResult(None, "insufficient_samples")
    power = np.abs(spectrum[band]) ** 2 / values.size**2
    interior = frequencies[band] > 0
    if values.size % 2 == 0:
        interior &= frequencies[band] < sample_rate_hz / 2
    power[interior] *= 2
    return MetricResult(float(np.sqrt(np.sum(power))))
