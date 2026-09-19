from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from px4reqcheck.metrics import MetricResult
from px4reqcheck.params import load_parameter_aliases, resolve_threshold
from px4reqcheck.requirements import Requirement, evaluate_requirement, load_requirements
from px4reqcheck.requirements.expression import parse_expression

ROOT = Path(__file__).parents[2]
ALIASES = load_parameter_aliases(ROOT / "src" / "px4reqcheck" / "params" / "aliases.yaml")
REQUIREMENTS = load_requirements(
    ROOT / "src" / "px4reqcheck" / "requirements" / "requirements.yaml"
)


def requirement(requirement_id: str) -> Requirement:
    return next(item for item in REQUIREMENTS if item.id == requirement_id)


def test_all_seven_corrected_requirements_load() -> None:
    assert len(REQUIREMENTS) == 7
    assert len({item.id for item in REQUIREMENTS}) == 7
    assert all(item.unit for item in REQUIREMENTS)


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "danger()",
        "object.attribute",
        "[value for value in values]",
    ],
)
def test_expression_language_rejects_executable_constructs(expression: str) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        parse_expression(expression)


def test_parameter_alias_prefers_current_battery_name() -> None:
    result = resolve_threshold(
        requirement("REQ-BATT-003-VOLT"),
        ALIASES,
        {"BAT1_N_CELLS": 4, "BAT_N_CELLS": 3, "BAT1_V_EMPTY": 3.5},
        [],
    )

    assert result.value == 14.0
    assert [source.source_name for source in result.source_params] == [
        "BAT1_N_CELLS",
        "BAT1_V_EMPTY",
    ]


@pytest.mark.parametrize(
    ("item", "parameters"),
    [
        ("REQ-BATT-003-VOLT", {"BAT1_N_CELLS": 0, "BAT1_V_EMPTY": 3.5}),
        ("REQ-GEOFENCE-001", {"GF_MAX_HOR_DIST": 0}),
    ],
)
def test_known_requirement_sentinels_are_not_evaluable(
    item: str, parameters: dict[str, float]
) -> None:
    result = resolve_threshold(requirement(item), ALIASES, parameters, [])

    assert result.reason == "param_disabled"
    assert result.value is None


def test_com_disarm_land_nonpositive_sentinel_is_disabled() -> None:
    item = Requirement(
        id="TEST-COM-DISARM",
        title="sentinel test",
        metric="timeout",
        unit="s",
        threshold=parse_expression("COM_DISARM_LAND"),
        comparator=">=",
        requires_params=("COM_DISARM_LAND",),
        requires_signals=(),
        disabled_when=parse_expression("COM_DISARM_LAND <= 0", condition=True),
    )

    result = resolve_threshold(item, ALIASES, {"COM_DISARM_LAND": 0}, [])

    assert result.reason == "param_disabled"


def test_parameter_change_makes_threshold_ambiguous() -> None:
    result = resolve_threshold(
        requirement("REQ-GEOFENCE-001"),
        ALIASES,
        {"GF_MAX_HOR_DIST": 100},
        [(5_000_000, "GF_MAX_HOR_DIST", 50)],
    )

    assert result.reason == "param_changed_in_flight"


def test_unit_mismatch_is_refused() -> None:
    with pytest.raises(ValueError, match="unit mismatch"):
        evaluate_requirement(
            log_id="a",
            requirement=requirement("REQ-GPS-001"),
            metric_result=MetricResult(3.0),
            metric_unit="m",
            aliases=ALIASES,
            initial_parameters={},
            changed_parameters=[],
            available_signals={"gps"},
        )


def test_threshold_expression_unit_mismatch_is_refused() -> None:
    item = Requirement(
        id="UNIT-MISMATCH",
        title="unit mismatch",
        metric="distance",
        unit="m",
        threshold=parse_expression("COM_DISARM_LAND"),
        comparator="<=",
        requires_params=("COM_DISARM_LAND",),
        requires_signals=(),
    )

    with pytest.raises(ValueError, match="threshold unit mismatch"):
        resolve_threshold(item, ALIASES, {"COM_DISARM_LAND": 5}, [])


def test_not_evaluable_cause_precedence_is_deterministic() -> None:
    verdict = evaluate_requirement(
        log_id="a",
        requirement=requirement("REQ-GEOFENCE-001"),
        metric_result=MetricResult(None, "window_missing"),
        metric_unit="m",
        aliases=ALIASES,
        initial_parameters={},
        changed_parameters=[],
        available_signals=set(),
    )

    assert verdict.status == "not_evaluable"
    assert verdict.cause == "param_missing"


@given(
    metric_value=st.floats(allow_nan=False, allow_infinity=False),
    threshold=st.floats(allow_nan=False, allow_infinity=False),
)
def test_verdict_is_total_and_deterministic(metric_value: float, threshold: float) -> None:
    item = Requirement(
        id="PROPERTY",
        title="property",
        metric="value",
        unit="value",
        threshold=parse_expression(repr(threshold)),
        comparator=">=",
        requires_params=(),
        requires_signals=("value",),
    )
    arguments = {
        "log_id": "log",
        "requirement": item,
        "metric_result": MetricResult(metric_value),
        "metric_unit": "value",
        "aliases": ALIASES,
        "initial_parameters": {},
        "changed_parameters": [],
        "available_signals": {"value"},
    }

    first = evaluate_requirement(**arguments)
    second = evaluate_requirement(**arguments)

    assert first.status in {"pass", "fail", "not_evaluable"}
    assert first == second
