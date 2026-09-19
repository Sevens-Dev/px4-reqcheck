#!/usr/bin/env python3
"""Update tier-2 expectations from an intentionally reviewed local corpus."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from px4reqcheck.analytics.evaluation import evaluate_corpus

ROOT = Path(__file__).parents[1]


def main() -> None:
    verdicts, _ = evaluate_corpus(ROOT / "data" / "parquet")
    output = ROOT / "golden" / "corpus" / "expected-verdicts.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([asdict(verdict) for verdict in verdicts], indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
