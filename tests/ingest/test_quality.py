import numpy as np

from px4reqcheck.ingest.quality import (
    count_duplicates,
    count_gaps,
    count_nonmonotonic,
    count_out_of_range,
    sample_rate_hz,
)


def test_nonmonotonic_timestamps_are_counted_not_dropped() -> None:
    timestamps = np.array([10, 20, 15, 30, 29], dtype=np.uint64)

    assert count_nonmonotonic(timestamps) == 2


def test_short_timestamp_series_is_monotonic() -> None:
    assert count_nonmonotonic(np.array([], dtype=np.uint64)) == 0
    assert count_nonmonotonic(np.array([10], dtype=np.uint64)) == 0


def test_gaps_and_duplicates_are_counted_without_dropping() -> None:
    timestamps = np.array([0, 100_000, 100_000, 1_200_001], dtype=np.uint64)

    assert count_duplicates(timestamps) == 1
    assert count_gaps(timestamps) == 1
    assert timestamps.tolist() == [0, 100_000, 100_000, 1_200_001]


def test_out_of_range_counts_bounds_and_nonfinite_values() -> None:
    values = np.array([-1.0, 0.0, 0.5, 1.0, 2.0, np.nan])

    assert count_out_of_range(values, minimum=0, maximum=1) == 3


def test_sample_rate_uses_median_positive_interval() -> None:
    timestamps = np.array([0, 10_000, 20_000, 20_000, 30_000], dtype=np.uint64)

    assert sample_rate_hz(timestamps) == 100.0


def test_sample_rate_is_unknown_without_positive_intervals() -> None:
    assert sample_rate_hz(np.array([10, 10], dtype=np.uint64)) is None
