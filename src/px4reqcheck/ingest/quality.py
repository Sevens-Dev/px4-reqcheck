"""Initial Week 1 data-quality checks."""

from __future__ import annotations

import numpy as np


def count_nonmonotonic(timestamps: np.ndarray) -> int:
    """Count adjacent timestamp pairs that move backward."""
    if timestamps.size < 2:
        return 0
    return int(np.count_nonzero(np.diff(timestamps.astype(np.int64, copy=False)) < 0))
