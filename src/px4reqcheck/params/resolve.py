"""Version-tolerant parameter aliases and sentinel-safe thresholds."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml

if TYPE_CHECKING:
    from px4reqcheck.requirements.model import Requirement

ThresholdReason = Literal["param_missing", "param_disabled", "param_changed_in_flight"]


@dataclass(frozen=True)
class ParameterCandidate:
    name: str
    unit: str


@dataclass(frozen=True)
class ParameterAlias:
    logical_name: str
    unit: str
    candidates: tuple[ParameterCandidate, ...]


ParameterAliases = dict[str, ParameterAlias]


@dataclass(frozen=True)
class SourceParameter:
    logical_name: str
    source_name: str
    value: float
    unit: str


@dataclass(frozen=True)
class ThresholdResult:
    value: float | None
    unit: str
    reason: ThresholdReason | None
    source_params: tuple[SourceParameter, ...]

    def __post_init__(self) -> None:
        if (self.value is None) == (self.reason is None):
            raise ValueError("exactly one of threshold value or reason must be present")


def load_parameter_aliases(path: Path) -> ParameterAliases:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("parameter aliases must contain a mapping")
    aliases: ParameterAliases = {}
    for logical_name, specification in loaded.items():
        if not isinstance(logical_name, str) or not isinstance(specification, dict):
            raise ValueError("invalid parameter alias")
        unit = specification.get("unit")
        candidates_field = specification.get("candidates")
        if not isinstance(unit, str) or not isinstance(candidates_field, list):
            raise ValueError(f"invalid alias specification: {logical_name}")
        candidates: list[ParameterCandidate] = []
        for candidate in candidates_field:
            if not isinstance(candidate, dict):
                raise ValueError(f"invalid candidate for {logical_name}")
            name = candidate.get("name")
            candidate_unit = candidate.get("unit")
            if not isinstance(name, str) or not isinstance(candidate_unit, str):
                raise ValueError(f"invalid candidate for {logical_name}")
            if candidate_unit != unit:
                raise ValueError(f"unit mismatch for {logical_name}: {candidate_unit} != {unit}")
            candidates.append(ParameterCandidate(name, candidate_unit))
        if not candidates:
            raise ValueError(f"alias has no candidates: {logical_name}")
        aliases[logical_name] = ParameterAlias(logical_name, unit, tuple(candidates))
    return aliases


def resolve_threshold(
    requirement: Requirement,
    aliases: ParameterAliases,
    initial_parameters: Mapping[str, int | float],
    changed_parameters: Sequence[tuple[int, str, int | float]],
) -> ThresholdResult:
    values: dict[str, float] = {}
    sources: list[SourceParameter] = []
    for logical_name in requirement.requires_params:
        alias = aliases.get(logical_name)
        if alias is None:
            raise ValueError(f"no parameter alias declared for {logical_name}")
        candidate = next(
            (item for item in alias.candidates if item.name in initial_parameters),
            None,
        )
        if candidate is None:
            return ThresholdResult(None, requirement.unit, "param_missing", tuple(sources))
        initial_value = float(initial_parameters[candidate.name])
        sources.append(SourceParameter(logical_name, candidate.name, initial_value, candidate.unit))
        values[logical_name] = initial_value
        if any(
            changed_name == candidate.name
            and not math.isclose(float(changed_value), initial_value, rel_tol=0, abs_tol=0)
            for _, changed_name, changed_value in changed_parameters
        ):
            return ThresholdResult(
                None,
                requirement.unit,
                "param_changed_in_flight",
                tuple(sources),
            )
    if requirement.disabled_when is not None and requirement.disabled_when.evaluate_condition(
        values
    ):
        return ThresholdResult(None, requirement.unit, "param_disabled", tuple(sources))
    value = requirement.threshold.evaluate_number(values)
    if not math.isfinite(value):
        raise ValueError(f"threshold is not finite for {requirement.id}")
    return ThresholdResult(value, requirement.unit, None, tuple(sources))
