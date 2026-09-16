"""Initial Week 1 data-quality checks."""

from __future__ import annotations

import numpy as np


def count_nonmonotonic(timestamps: np.ndarray) -> int:
    """Count adjacent timestamp pairs that move backward."""
    if timestamps.size < 2:
        return 0
    return int(np.count_nonzero(np.diff(timestamps.astype(np.int64, copy=False)) < 0))


def count_gaps(timestamps: np.ndarray, *, maximum_gap_us: int = 1_000_000) -> int:
    """Count adjacent positive timestamp gaps above the declared limit."""
    if timestamps.size < 2:
        return 0
    differences = np.diff(timestamps.astype(np.int64, copy=False))
    return int(np.count_nonzero(differences > maximum_gap_us))


def count_duplicates(timestamps: np.ndarray) -> int:
    """Count duplicate samples beyond the first occurrence of each timestamp."""
    if timestamps.size < 2:
        return 0
    return int(timestamps.size - np.unique(timestamps).size)


def count_out_of_range(values: np.ndarray, *, minimum: float, maximum: float) -> int:
    """Count non-finite or physically out-of-range values without dropping them."""
    numeric = np.asarray(values, dtype=np.float64)
    return int(np.count_nonzero(~np.isfinite(numeric) | (numeric < minimum) | (numeric > maximum)))


def sample_rate_hz(timestamps: np.ndarray) -> float | None:
    """Estimate sample rate from the median positive inter-sample interval."""
    if timestamps.size < 2:
        return None
    differences = np.diff(timestamps.astype(np.int64, copy=False))
    positive = differences[differences > 0]
    if positive.size == 0:
        return None
    return float(1_000_000 / np.median(positive))
