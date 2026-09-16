from px4reqcheck.corpus.manifest import select_logs


def entry(log_id: str, vehicle: str, date: str = "2026-01-01") -> dict[str, object]:
    return {
        "log_id": log_id,
        "vehicle_uuid": vehicle,
        "log_date": date,
        "mav_type": "Quadrotor",
        "flight_modes": [3],
        "duration_s": 120,
        "ver_sw_release": "v1.15.4 0",
    }


def test_selection_prefers_latest_distinct_vehicles() -> None:
    entries = [
        entry("old-a", "a", "2025-01-01"),
        entry("new-a", "a", "2026-01-02"),
        entry("new-b", "b", "2026-01-01"),
    ]

    selected = select_logs(entries, limit=2)

    assert [item["log_id"] for item in selected] == ["new-a", "new-b"]


def test_selection_applies_firmware_duration_mode_and_type_filters() -> None:
    valid = entry("valid", "a")
    wrong_version = {**entry("version", "b"), "ver_sw_release": "v1.14.4 0"}
    too_short = {**entry("short", "c"), "duration_s": 59}
    no_mission = {**entry("mode", "d"), "flight_modes": [2]}
    fixed_wing = {**entry("fixed", "e"), "mav_type": "Fixed Wing"}

    assert select_logs([valid, wrong_version, too_short, no_mission, fixed_wing], limit=1) == [
        valid
    ]
