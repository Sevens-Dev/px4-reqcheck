"""Total three-valued requirement evaluation."""

from __future__ import annotations

import math
import operator
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from typing import Literal

from px4reqcheck.metrics import MetricResult
from px4reqcheck.params.resolve import ParameterAliases, SourceParameter, resolve_threshold
from px4reqcheck.requirements.model import Comparator, Requirement

VerdictStatus = Literal["pass", "fail", "not_evaluable"]
NotEvaluableCause = Literal[
    "param_missing",
    "param_disabled",
    "param_changed_in_flight",
    "signal_missing",
    "window_missing",
    "insufficient_samples",
    "quality_fail",
]

_COMPARATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}


@dataclass(frozen=True)
class Verdict:
    log_id: str
    requirement_id: str
    metric: str
    unit: str
    status: VerdictStatus
    metric_value: float | None
    threshold_value: float | None
    comparator: Comparator
    cause: NotEvaluableCause | None
    source_params: tuple[SourceParameter, ...]

    def __post_init__(self) -> None:
        if self.status == "not_evaluable":
            if self.cause is None:
                raise ValueError("not_evaluable verdict requires a cause")
        elif self.cause is not None or self.metric_value is None or self.threshold_value is None:
            raise ValueError("pass/fail verdict requires values and no cause")


def evaluate_requirement(
    *,
    log_id: str,
    requirement: Requirement,
    metric_result: MetricResult,
    metric_unit: str,
    aliases: ParameterAliases,
    initial_parameters: Mapping[str, int | float],
    changed_parameters: Sequence[tuple[int, str, int | float]],
    available_signals: Set[str],
) -> Verdict:
    if metric_unit != requirement.unit:
        raise ValueError(
            f"unit mismatch for {requirement.id}: metric {metric_unit} != requirement "
            f"{requirement.unit}"
        )
    threshold = resolve_threshold(
        requirement,
        aliases,
        initial_parameters,
        changed_parameters,
    )
    if threshold.reason is not None:
        return _not_evaluable(log_id, requirement, threshold.reason, threshold.source_params)
    if not set(requirement.requires_signals).issubset(available_signals):
        return _not_evaluable(
            log_id,
            requirement,
            "signal_missing",
            threshold.source_params,
            threshold_value=threshold.value,
        )
    if metric_result.reason is not None:
        return _not_evaluable(
            log_id,
            requirement,
            metric_result.reason,
            threshold.source_params,
            threshold_value=threshold.value,
        )
    if metric_result.value is None or threshold.value is None:
        raise ValueError("resolved metric and threshold must contain values")
    if not math.isfinite(metric_result.value):
        return _not_evaluable(
            log_id,
            requirement,
            "quality_fail",
            threshold.source_params,
            threshold_value=threshold.value,
        )
    comparison = _COMPARATORS[requirement.comparator]
    status: VerdictStatus = "pass" if comparison(metric_result.value, threshold.value) else "fail"
    return Verdict(
        log_id=log_id,
        requirement_id=requirement.id,
        metric=requirement.metric,
        unit=requirement.unit,
        status=status,
        metric_value=metric_result.value,
        threshold_value=threshold.value,
        comparator=requirement.comparator,
        cause=None,
        source_params=threshold.source_params,
    )


def _not_evaluable(
    log_id: str,
    requirement: Requirement,
    cause: NotEvaluableCause,
    source_params: tuple[SourceParameter, ...],
    *,
    threshold_value: float | None = None,
) -> Verdict:
    return Verdict(
        log_id=log_id,
        requirement_id=requirement.id,
        metric=requirement.metric,
        unit=requirement.unit,
        status="not_evaluable",
        metric_value=None,
        threshold_value=threshold_value,
        comparator=requirement.comparator,
        cause=cause,
        source_params=source_params,
    )
