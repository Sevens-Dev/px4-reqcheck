"""Resolve logical signals to version-compatible normalized Parquet fields."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as parquet
import yaml


@dataclass(frozen=True)
class SignalCandidate:
    topic: str
    fields: tuple[str, ...]
    minimum_version: tuple[int, ...] | None
    maximum_version: tuple[int, ...] | None
    scale: float
    unit: str


@dataclass(frozen=True)
class SignalAlias:
    logical_name: str
    unit: str
    candidates: tuple[SignalCandidate, ...]


@dataclass(frozen=True)
class ResolvedSignal:
    logical_name: str
    topic: str
    fields: tuple[str, ...]
    scale: float
    unit: str


def load_signal_aliases(path: Path) -> dict[str, SignalAlias]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("signal aliases must contain a mapping")
    aliases: dict[str, SignalAlias] = {}
    for logical_name, specification in loaded.items():
        if not isinstance(logical_name, str) or not isinstance(specification, dict):
            raise ValueError("invalid signal alias")
        unit = specification.get("unit")
        candidate_rows = specification.get("candidates")
        if not isinstance(unit, str) or not isinstance(candidate_rows, list):
            raise ValueError(f"invalid signal alias: {logical_name}")
        candidates = []
        for row in candidate_rows:
            if not isinstance(row, dict) or row.get("unit") != unit:
                raise ValueError(f"unit mismatch for signal alias: {logical_name}")
            topic = row.get("topic")
            field = row.get("field")
            if not isinstance(topic, str) or not isinstance(field, str):
                raise ValueError(f"invalid candidate for signal alias: {logical_name}")
            candidates.append(
                SignalCandidate(
                    topic=topic,
                    fields=tuple(field.split(",")),
                    minimum_version=_version(row.get("min_version"), upper=False),
                    maximum_version=_version(row.get("max_version"), upper=True),
                    scale=float(row.get("scale", 1.0)),
                    unit=unit,
                )
            )
        aliases[logical_name] = SignalAlias(logical_name, unit, tuple(candidates))
    return aliases


def resolve_signals(
    log_root: Path,
    version: str | None,
    aliases: dict[str, SignalAlias],
) -> dict[str, ResolvedSignal]:
    actual_version = _version(version, upper=False)
    resolved: dict[str, ResolvedSignal] = {}
    for logical_name, alias in aliases.items():
        for candidate in alias.candidates:
            if not _version_matches(actual_version, candidate):
                continue
            source = log_root / f"topic_{candidate.topic}.parquet"
            if not source.exists():
                continue
            columns = set(parquet.read_schema(source).names)
            if not set(candidate.fields).issubset(columns):
                continue
            resolved[logical_name] = ResolvedSignal(
                logical_name,
                candidate.topic,
                candidate.fields,
                candidate.scale,
                candidate.unit,
            )
            break
    return resolved


def _version(value: object, *, upper: bool) -> tuple[int, ...] | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid version: {value}")
    parts = [int(part) for part in value.split(".")]
    if len(parts) > 3:
        raise ValueError(f"invalid version: {value}")
    parts.extend(([999_999] if upper else [0]) * (3 - len(parts)))
    return tuple(parts)


def _version_matches(
    version: tuple[int, ...] | None,
    candidate: SignalCandidate,
) -> bool:
    if version is None:
        return candidate.minimum_version is None and candidate.maximum_version is None
    if candidate.minimum_version is not None and version < candidate.minimum_version:
        return False
    return candidate.maximum_version is None or version <= candidate.maximum_version
