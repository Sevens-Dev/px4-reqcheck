"""Requirement schema and loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml

from px4reqcheck.requirements.expression import ParsedExpression, parse_expression

Comparator = Literal[">=", "<=", ">", "<"]


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    metric: str
    unit: str
    threshold: ParsedExpression
    comparator: Comparator
    requires_params: tuple[str, ...]
    requires_signals: tuple[str, ...]
    disabled_when: ParsedExpression | None = None
    requirement_class: str = "configured_limit"


def load_requirements(path: Path) -> tuple[Requirement, ...]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("requirements file must contain a list")
    requirements = tuple(_load_requirement(item) for item in loaded)
    identifiers = [requirement.id for requirement in requirements]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("requirement ids must be unique")
    return requirements


def _load_requirement(item: object) -> Requirement:
    if not isinstance(item, dict):
        raise ValueError("each requirement must be a mapping")
    required = {
        "id",
        "title",
        "metric",
        "unit",
        "threshold",
        "comparator",
        "requires_params",
        "requires_signals",
    }
    missing = required - item.keys()
    if missing:
        raise ValueError(f"requirement missing fields: {', '.join(sorted(missing))}")
    threshold_field = item["threshold"]
    if not isinstance(threshold_field, dict) or not isinstance(threshold_field.get("expr"), str):
        raise ValueError("threshold must contain a string expr")
    comparator = item["comparator"]
    if comparator not in {">=", "<=", ">", "<"}:
        raise ValueError(f"invalid comparator: {comparator}")
    required_params = _string_tuple(item["requires_params"], "requires_params")
    required_signals = _string_tuple(item["requires_signals"], "requires_signals")
    threshold = parse_expression(threshold_field["expr"])
    disabled_text = item.get("disabled_when")
    disabled = (
        parse_expression(disabled_text, condition=True) if isinstance(disabled_text, str) else None
    )
    permitted_names = set(required_params)
    referenced_names = set(threshold.names)
    if disabled is not None:
        referenced_names.update(disabled.names)
    unknown = referenced_names - permitted_names
    if unknown:
        raise ValueError(
            f"requirement {item['id']} expressions reference undeclared parameters: "
            f"{', '.join(sorted(unknown))}"
        )
    return Requirement(
        id=_string(item["id"], "id"),
        title=_string(item["title"], "title"),
        metric=_string(item["metric"], "metric"),
        unit=_string(item["unit"], "unit"),
        threshold=threshold,
        comparator=cast(Comparator, comparator),
        requires_params=required_params,
        requires_signals=required_signals,
        disabled_when=disabled,
        requirement_class=_string(item.get("class", "configured_limit"), "class"),
    )


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return tuple(value)
