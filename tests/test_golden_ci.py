from pathlib import Path

from px4reqcheck.golden import assert_golden

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "golden" / "ci"


def test_three_committed_synthetic_fixtures_match_golden_outputs() -> None:
    count = assert_golden(
        FIXTURES,
        FIXTURES / "expected-verdicts.json",
        ROOT / "golden" / "tolerances.yaml",
    )

    assert count == 3 * 7
    fixture_bytes = sum(path.stat().st_size for path in FIXTURES.rglob("*") if path.is_file())
    assert fixture_bytes <= 5 * 1024 * 1024
