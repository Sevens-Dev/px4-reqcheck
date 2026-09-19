from pathlib import Path

import pytest

from px4reqcheck.analytics.evaluation import evaluate_corpus
from px4reqcheck.golden import assert_golden

ROOT = Path(__file__).parents[2]
DATA = ROOT / "data" / "parquet"
EXPECTED = ROOT / "golden" / "corpus" / "expected-verdicts.json"
TOLERANCES = ROOT / "golden" / "tolerances.yaml"
MEMO_LOG = "0d728b7d-8d15-4975-b834-1c6b3174b062"


def test_real_corpus_matches_golden_outputs() -> None:
    assert assert_golden(DATA, EXPECTED, TOLERANCES) == 20 * 7


def test_memo_landing_violation_remains_guarded() -> None:
    verdicts, _ = evaluate_corpus(DATA)
    verdict = next(
        row for row in verdicts if row.log_id == MEMO_LOG and row.requirement_id == "REQ-LAND-001"
    )

    assert verdict.status == "fail"
    assert verdict.cause is None
    assert verdict.threshold_value == pytest.approx(0.699999988079071, abs=1e-9)
    assert verdict.metric_value == pytest.approx(0.93658007979393, abs=1e-6)
