"""Build a deterministic manifest from the PX4 Flight Review public index."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

import requests

INDEX_URL = "https://review.px4.io/dbinfo"
DOWNLOAD_URL = "https://review.px4.io/download"
MULTICOPTER_LABELS = frozenset({"Quadrotor", "Hexarotor", "Octorotor"})
MISSION_MODE = 3


def _eligible(entry: Mapping[str, Any], firmware_minor: str) -> bool:
    duration = entry.get("duration_s")
    release = str(entry.get("ver_sw_release", ""))
    modes = entry.get("flight_modes") or []
    return (
        entry.get("mav_type") in MULTICOPTER_LABELS
        and MISSION_MODE in modes
        and isinstance(duration, (int, float))
        and 60 <= duration <= 1_200
        and release.startswith(f"v{firmware_minor}.")
    )


def select_logs(
    entries: Iterable[Mapping[str, Any]], *, limit: int, firmware_minor: str = "1.15"
) -> list[dict[str, Any]]:
    """Select latest eligible logs, preferring one log per known vehicle."""
    if limit < 1:
        raise ValueError("limit must be positive")
    eligible = sorted(
        (dict(entry) for entry in entries if _eligible(entry, firmware_minor)),
        key=lambda entry: (str(entry.get("log_date", "")), str(entry.get("log_id", ""))),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    vehicles: set[str] = set()
    for entry in eligible:
        vehicle = str(entry.get("vehicle_uuid") or "")
        if vehicle and vehicle in vehicles:
            deferred.append(entry)
            continue
        if vehicle:
            vehicles.add(vehicle)
        selected.append(entry)
        if len(selected) == limit:
            break
    if len(selected) < limit:
        selected.extend(deferred[: limit - len(selected)])
    return selected


def build_manifest(
    *, limit: int = 20, firmware_minor: str = "1.15", timeout_s: float = 300
) -> dict[str, Any]:
    """Fetch the index and return a manifest whose checksums are filled on download."""
    response = requests.get(INDEX_URL, timeout=timeout_s)
    response.raise_for_status()
    entries = response.json()
    selected = select_logs(entries, limit=limit, firmware_minor=firmware_minor)
    if len(selected) < limit:
        raise RuntimeError(f"only {len(selected)} eligible logs found; requested {limit}")
    keys = (
        "log_id",
        "log_date",
        "mav_type",
        "flight_modes",
        "duration_s",
        "ver_sw",
        "ver_sw_release",
        "vehicle_uuid",
        "airframe_name",
        "airframe_type",
        "source",
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": INDEX_URL,
        "download_endpoint": DOWNLOAD_URL,
        "filters": {
            "mav_types": sorted(MULTICOPTER_LABELS),
            "mission_mode": MISSION_MODE,
            "duration_s": [60, 1200],
            "firmware_minor": firmware_minor,
            "latest_per_vehicle_preferred": True,
        },
        "logs": [{**{key: entry.get(key) for key in keys}, "sha256": None} for entry in selected],
    }
