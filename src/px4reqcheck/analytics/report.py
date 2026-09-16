"""Generate the Week 2 static analytical figures."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "px4reqcheck-mpl"))

import duckdb
import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from px4reqcheck.analytics.queries import register_views, run_query  # noqa: E402


def generate_static_figures(data_root: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    try:
        register_views(connection, data_root)
        quality = run_query(connection, "full_scan_quality")
        firmware = run_query(connection, "firmware_duration")
    finally:
        connection.close()
    quality = quality.loc[quality["check_name"] != "sample_rate_hz"]
    generated: list[Path] = []

    figure, axis = plt.subplots(figsize=(9, 4.5))
    axis.bar(quality["check_name"], quality["total_findings"])
    axis.set(title="Reported data-quality findings", ylabel="count")
    axis.set_yscale("symlog", linthresh=1)
    axis.tick_params(axis="x", rotation=30)
    figure.tight_layout()
    quality_path = output / "quality-findings.png"
    figure.savefig(quality_path, dpi=150)
    plt.close(figure)
    generated.append(quality_path)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar(firmware["sw_version"], firmware["mean_duration_s"])
    axis.set(title="Mean log duration by firmware patch", xlabel="firmware", ylabel="seconds")
    axis.tick_params(axis="x", rotation=30)
    figure.tight_layout()
    firmware_path = output / "duration-by-firmware.png"
    figure.savefig(firmware_path, dpi=150)
    plt.close(figure)
    generated.append(firmware_path)
    return generated
