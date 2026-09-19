import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[2]
REPORT = ROOT / "docs" / "report"


def test_committed_traceability_is_total_for_every_log_and_requirement() -> None:
    verdicts = json.loads((REPORT / "verdicts.json").read_text(encoding="utf-8"))
    pairs = Counter((row["log_id"], row["requirement_id"]) for row in verdicts)

    assert len(verdicts) == 20 * 7
    assert len(pairs) == 20 * 7
    assert set(pairs.values()) == {1}
    assert {row["status"] for row in verdicts} <= {"pass", "fail", "not_evaluable"}
    assert all(
        row["cause"] is not None if row["status"] == "not_evaluable" else row["cause"] is None
        for row in verdicts
    )


def test_traceability_counts_reconcile_with_raw_verdicts() -> None:
    verdicts = json.loads((REPORT / "verdicts.json").read_text(encoding="utf-8"))
    with (REPORT / "traceability.csv").open(encoding="utf-8", newline="") as source:
        matrix = list(csv.DictReader(source))

    assert len(matrix) == 7
    for row in matrix:
        matching = [item for item in verdicts if item["requirement_id"] == row["requirement_id"]]
        assert int(row["total"]) == len(matching) == 20
        assert int(row["evaluable"]) + int(row["not_evaluable"]) == 20
        assert int(row["pass"]) + int(row["fail"]) == int(row["evaluable"])
    html = (REPORT / "traceability.html").read_text(encoding="utf-8")
    assert html.count("cdn.plot.ly") == 1
    assert 'id="traceability-table"' in html
