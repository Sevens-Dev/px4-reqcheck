import numpy as np

from px4reqcheck.ingest.quality import count_nonmonotonic


def test_nonmonotonic_timestamps_are_counted_not_dropped() -> None:
    timestamps = np.array([10, 20, 15, 30, 29], dtype=np.uint64)

    assert count_nonmonotonic(timestamps) == 2


def test_short_timestamp_series_is_monotonic() -> None:
    assert count_nonmonotonic(np.array([], dtype=np.uint64)) == 0
    assert count_nonmonotonic(np.array([10], dtype=np.uint64)) == 0
