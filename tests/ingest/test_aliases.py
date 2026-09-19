from pathlib import Path

import pandas as pd

from px4reqcheck.ingest.aliases import load_signal_aliases, resolve_signals

ROOT = Path(__file__).parents[2]


def test_versioned_aliases_select_new_and_legacy_trajectory_topics(tmp_path: Path) -> None:
    aliases = load_signal_aliases(ROOT / "src" / "px4reqcheck" / "ingest" / "aliases.yaml")
    pd.DataFrame({"timestamp": [0], "position[2]": [1.0]}).to_parquet(
        tmp_path / "topic_trajectory_setpoint.parquet",
        index=False,
    )
    pd.DataFrame({"timestamp": [0], "z": [1.0]}).to_parquet(
        tmp_path / "topic_vehicle_local_position_setpoint.parquet",
        index=False,
    )

    current = resolve_signals(tmp_path, "1.15.4", aliases)
    legacy = resolve_signals(tmp_path, "1.12.9", aliases)

    assert current["trajectory_setpoint"].topic == "trajectory_setpoint"
    assert current["trajectory_setpoint"].fields == ("position[2]",)
    assert legacy["trajectory_setpoint"].topic == "vehicle_local_position_setpoint"
    assert legacy["trajectory_setpoint"].fields == ("z",)


def test_signal_alias_loader_refuses_unit_mismatch(tmp_path: Path) -> None:
    aliases = tmp_path / "aliases.yaml"
    aliases.write_text(
        "signal:\n  unit: m\n  candidates:\n    - {topic: t, field: f, unit: s}\n",
        encoding="utf-8",
    )

    try:
        load_signal_aliases(aliases)
    except ValueError as error:
        assert "unit mismatch" in str(error)
    else:
        raise AssertionError("unit mismatch was accepted")
