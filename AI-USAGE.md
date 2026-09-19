# AI usage

Codex contributed substantially to this repository, including scaffolding, architecture interpretation, source verification, implementation, tests, documentation, debugging, and refactoring.

The original planning document used “hand-written” labels for several components. The implementation brief explicitly supersedes that restriction and permits AI assistance throughout. This file therefore does not claim manual authorship for AI-generated work.

## Assistance log

- 2026-09-16: generated the initial package and CI scaffold.
- 2026-09-16: assisted with the Week 0 source-verification research and ADR drafting.
- 2026-09-16: implemented the Week 1 corpus, normalized ingest, quality checks, and tests.
- 2026-09-16: implemented the Week 2 flight metrics, analytical SQL, and static reports.
- 2026-09-19: implemented the preregistered benchmark harness and manual measurement workflow.
- 2026-09-19: implemented the Week 3 requirement schema, safe expression parser, parameter aliases, threshold resolver, verdict model, and tests.

## Defects introduced by AI assistance

1. Codex supplied an incorrect expected SHA-256 for the downloader fixture. `tests/corpus/test_download.py::test_download_records_404_and_checksums_success` failed with the actual digest and prevented the mistake from entering the PR. Fixed in [`e00061d`](https://github.com/Sevens-Dev/px4-reqcheck/commit/e00061d).
2. Codex initially selected `pyarrow 21.0.0` and `pytest 8.4.2`, both affected by advisories current on 2026-09-16. The required `pip-audit` gate reported `PYSEC-2026-113` and `PYSEC-2026-1845`; the dependencies were upgraded to fixed releases and the audit reran clean. Fixed in [`e00061d`](https://github.com/Sevens-Dev/px4-reqcheck/commit/e00061d).
3. Codex wrote the battery-at-disarm test with an incorrect hand-computed expectation: it selected the penultimate battery sample even though a later sample still preceded the disarm edge. `tests/metrics/test_flight.py::test_battery_value_uses_last_sample_before_disarm` failed (`11.0 != 11.5`) and the expected value/window were corrected in [`81ee48b`](https://github.com/Sevens-Dev/px4-reqcheck/commit/81ee48b).
4. Automated Codex review found that battery-at-disarm used the last matching row rather than the maximum timestamp, which was wrong for reported-but-retained nonmonotonic input. `test_battery_value_uses_latest_timestamp_when_input_is_nonmonotonic` now guards the case. Fixed in [`efc7175`](https://github.com/Sevens-Dev/px4-reqcheck/commit/efc7175).
5. Automated Codex review found that the vibration metric removed non-finite samples before its FFT, silently compressing time and invalidating the frequency bins. `test_vibration_rejects_missing_samples_instead_of_compressing_time` now requires `quality_fail`. Fixed in [`efc7175`](https://github.com/Sevens-Dev/px4-reqcheck/commit/efc7175).
6. Codex initially plotted the sum of per-topic sample-rate values as though it were a count of data-quality findings. Visual inspection of the generated figure exposed the category error; the report now excludes sample-rate measurements from the findings chart and uses a symmetric logarithmic scale so rare and frequent findings remain visible. Fixed in [`974d8d7`](https://github.com/Sevens-Dev/px4-reqcheck/commit/974d8d7).
7. Automated Codex review found that eager registration of every analytical view made unrelated static figures fail when an optional `vehicle_local_position` topic was absent from the entire corpus. Figure generation now registers only its required inputs, with a regression test for selective registration. Fixed in [`e8fe58e`](https://github.com/Sevens-Dev/px4-reqcheck/commit/e8fe58e).
8. Automated Codex review found that the full-scan quality query counted zero-finding rows as affected logs. The distinct-log aggregation is now conditional on a positive finding count and is covered by a zero-count fixture. Fixed in [`e8fe58e`](https://github.com/Sevens-Dev/px4-reqcheck/commit/e8fe58e).
9. Codex initially created a SQLite index on the reserved column name `check` without quoting it. `tests/test_benchmark.py::test_sql_benchmark_checks_equivalence_and_records_every_run` failed with `sqlite3.OperationalError`; the identifier is now quoted. Fixed in [`2ca2997`](https://github.com/Sevens-Dev/px4-reqcheck/commit/2ca2997).
10. Codex's initial benchmark preregistration omitted the shared contract's explicit minimum-detectable-difference-given-N field. A post-run contract audit caught the omission, the first workflow artifact was rejected for publication, and the field plus amendment history were committed before a fresh run. `tests/test_benchmark_results.py::test_committed_results_recompute_and_preregistration_is_complete` now guards every required preregistration heading. Fixed in [`d1e10dc`](https://github.com/Sevens-Dev/px4-reqcheck/commit/d1e10dc).

These are the defects actually observed. No defects were intentionally introduced.

## Rejected suggestions

- Codex considered treating the Flight Review repository's BSD license as permission to redistribute public uploaded logs. That inference was rejected: the repository license covers source code, while no license grant for user-uploaded log contents was found. The project stores raw logs only in git-ignored local data and publishes identifiers, checksums, metadata, and derived outputs.
