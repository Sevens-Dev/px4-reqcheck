"""Version-tolerant parameter aliases and sentinel-safe thresholds."""

from __future__ import annotations

import ast
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
    source_units = {source.logical_name: source.unit for source in sources}
    threshold_dimension = _expression_dimension(
        requirement.threshold.tree.body,
        source_units,
        default_unit=requirement.unit,
        expression_has_names=bool(requirement.threshold.names),
    )
    if threshold_dimension != _unit_dimension(requirement.unit):
        raise ValueError(
            f"threshold unit mismatch for {requirement.id}: expression does not produce "
            f"{requirement.unit}"
        )
    value = requirement.threshold.evaluate_number(values)
    if not math.isfinite(value):
        raise ValueError(f"threshold is not finite for {requirement.id}")
    return ThresholdResult(value, requirement.unit, None, tuple(sources))


def _expression_dimension(
    node: ast.AST,
    units: Mapping[str, str],
    *,
    default_unit: str,
    expression_has_names: bool,
) -> dict[str, int]:
    if not expression_has_names:
        return _unit_dimension(default_unit)
    if isinstance(node, ast.Name):
        return _unit_dimension(units[node.id])
    if isinstance(node, ast.Constant):
        return {}
    if isinstance(node, ast.UnaryOp):
        return _expression_dimension(
            node.operand,
            units,
            default_unit=default_unit,
            expression_has_names=True,
        )
    if isinstance(node, ast.BinOp):
        left = _expression_dimension(
            node.left,
            units,
            default_unit=default_unit,
            expression_has_names=True,
        )
        right = _expression_dimension(
            node.right,
            units,
            default_unit=default_unit,
            expression_has_names=True,
        )
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if left != right:
                raise ValueError("addition and subtraction require matching units")
            return left
        multiplier = 1 if isinstance(node.op, ast.Mult) else -1
        result = dict(left)
        for base, exponent in right.items():
            result[base] = result.get(base, 0) + multiplier * exponent
            if result[base] == 0:
                del result[base]
        return result
    raise ValueError(f"cannot derive units for {type(node).__name__}")


def _unit_dimension(unit: str) -> dict[str, int]:
    known = {
        "fraction": {"fraction": 1},
        "cells": {"cell": 1},
        "V": {"V": 1},
        "V/cell": {"V": 1, "cell": -1},
        "m": {"m": 1},
        "s": {"s": 1},
        "m/s": {"m": 1, "s": -1},
        "m/s^2": {"m": 1, "s": -2},
        "fix_type": {"fix_type": 1},
    }
    return known.get(unit, {unit: 1})
