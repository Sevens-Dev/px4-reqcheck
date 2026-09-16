# AI usage

Codex contributed substantially to this repository, including scaffolding, architecture interpretation, source verification, implementation, tests, documentation, debugging, and refactoring.

The original planning document used “hand-written” labels for several components. The implementation brief explicitly supersedes that restriction and permits AI assistance throughout. This file therefore does not claim manual authorship for AI-generated work.

## Assistance log

- 2026-09-16: generated the initial package and CI scaffold.
- 2026-09-16: assisted with the Week 0 source-verification research and ADR drafting.

## Defects introduced by AI assistance

1. Codex supplied an incorrect expected SHA-256 for the downloader fixture. `tests/corpus/test_download.py::test_download_records_404_and_checksums_success` failed with the actual digest and prevented the mistake from entering the PR. Fixed in [`e00061d`](https://github.com/Sevens-Dev/px4-reqcheck/commit/e00061d).
2. Codex initially selected `pyarrow 21.0.0` and `pytest 8.4.2`, both affected by advisories current on 2026-09-16. The required `pip-audit` gate reported `PYSEC-2026-113` and `PYSEC-2026-1845`; the dependencies were upgraded to fixed releases and the audit reran clean. Fixed in [`e00061d`](https://github.com/Sevens-Dev/px4-reqcheck/commit/e00061d).
3. Codex wrote the battery-at-disarm test with an incorrect hand-computed expectation: it selected the penultimate battery sample even though a later sample still preceded the disarm edge. `tests/metrics/test_flight.py::test_battery_value_uses_last_sample_before_disarm` failed (`11.0 != 11.5`) and the expected value/window were corrected in [`81ee48b`](https://github.com/Sevens-Dev/px4-reqcheck/commit/81ee48b).
4. Automated Codex review found that battery-at-disarm used the last matching row rather than the maximum timestamp, which was wrong for reported-but-retained nonmonotonic input. `test_battery_value_uses_latest_timestamp_when_input_is_nonmonotonic` now guards the case. Fixed in [`efc7175`](https://github.com/Sevens-Dev/px4-reqcheck/commit/efc7175).
5. Automated Codex review found that the vibration metric removed non-finite samples before its FFT, silently compressing time and invalidating the frequency bins. `test_vibration_rejects_missing_samples_instead_of_compressing_time` now requires `quality_fail`. Fixed in [`efc7175`](https://github.com/Sevens-Dev/px4-reqcheck/commit/efc7175).

These are the defects actually observed. No defects were intentionally introduced.

## Rejected suggestions

- Codex considered treating the Flight Review repository's BSD license as permission to redistribute public uploaded logs. That inference was rejected: the repository license covers source code, while no license grant for user-uploaded log contents was found. The project stores raw logs only in git-ignored local data and publishes identifiers, checksums, metadata, and derived outputs.
