# Root-cause memo: pre-landing descent-rate violation in public log `0d728b7d`

## Scope and finding

This memo analyzes one requirement violation in public PX4 Flight Review log `0d728b7d-8d15-4975-b834-1c6b3174b062`. It does not diagnose a vehicle fault, certify unsafe operation, or claim that the configured value is a universal safety limit. The implemented requirement is narrower: during the five seconds ending at the rising edge of `vehicle_land_detected.landed`, the linear-method 95th percentile of finite NED `vehicle_local_position.vz` samples, restricted to `-z < MPC_LAND_ALT2`, must not exceed the log's initial `MPC_LAND_SPEED`.

The result is a reproducible fail. The metric is `0.936580 m/s`; the parameter-derived threshold is `0.699999988 m/s`. The excess is `0.236580 m/s`, or about 34% of the configured threshold. This is therefore described as a requirement violation, not as proof of a failsafe-caused landing.

## Provenance and method

The corpus manifest pins the public log identifier and SHA-256. Ingest retains the needed source topics as Parquet and records quality findings without dropping samples. The log reports PX4 `1.15.1`, 63.928 seconds duration, 15,475 retained telemetry rows, `MPC_LAND_ALT2=5.0 m`, and `MPC_LAND_SPEED=0.7 m/s`.

The landing edge occurs at source timestamp `188077995 us`, 60.913 seconds after the first retained timestamp. The metric window is `[183077995, 188077995] us`. Fifty `vehicle_local_position` samples survive the time, altitude, and finite-value predicates. The topic's observed sample rate is 10.068 Hz. Its quality rows report zero nonmonotonic timestamps, gaps over one second, duplicates, and out-of-range `x`, `y`, `z`, or `vz` values. The result is not explained by a recorded input-quality failure.

Within the selected window, `vz` ranges from `0.147054` to `0.956967 m/s`, with median `0.852259 m/s` and mean `0.664875 m/s`. Thirty-two of 50 selected samples exceed `0.7 m/s`. The metric is not driven by a single spike: most of the first roughly 3.5 seconds of the five-second window are above the configured value.

## Timeline

- 55.913 s after the retained-log start: the five-second metric window begins. The first selected sample is approximately `0.815 m/s` down.
- 56.436-59.0 s: descent remains near `0.85-0.96 m/s`; the window's high values are sustained rather than isolated.
- 59.536 s: `ground_contact` rises. The descent estimate has begun falling by this stage.
- 60.573 s: `maybe_landed` rises.
- 60.913 s: `landed` rises, closing the metric window. The last second is approximately `0.23-0.29 m/s` down.
- 61.672 s: `at_rest` rises.

The timing shows that the vehicle decelerated before the `landed` edge, but the fixed five-second percentile still captures the faster approach portion. Using disarm instead would dilute that evidence with post-landing near-zero samples, which is why the requirement intentionally anchors to the landed edge.

## Hypothesis chain

**Hypothesis 1: one corrupt or non-finite sample inflated p95.** Rejected. All 50 selected `vz`/`z` pairs are finite, the source topic has no reported timestamp or range defect, and 32 samples—not one—exceed the threshold.

**Hypothesis 2: the evaluator used a default threshold instead of the vehicle configuration.** Rejected. `MPC_LAND_SPEED` resolves directly from the log's initial parameter table to `0.699999988 m/s`; `MPC_LAND_ALT2` resolves to `5.0 m`. Neither parameter changes in flight.

**Hypothesis 3: the window was accidentally anchored to disarm.** Rejected. The selected endpoint is the first `landed` rising edge at `188077995 us`. The `ground_contact`, `maybe_landed`, `landed`, and `at_rest` sequence is internally ordered and supports that event selection.

**Hypothesis 4: a failsafe transition caused the landing violation.** Not supported. The log does contain a failsafe transition, but it rises about 53.2 seconds before the landing edge and clears about 51.8 seconds before it. That temporal separation is not evidence that the transient caused the later landing profile, so the project does not upgrade this finding to a "public failsafe event" claim.

**Supported explanation.** The logged approach spends enough of the fixed pre-land window above the configured `MPC_LAND_SPEED` that the linear p95 exceeds the threshold, despite decelerating before the final landing-state transition. The pipeline is reporting the requirement exactly as defined. Whether the configuration, estimator frame, or flight context makes this operationally acceptable is outside this project's claim.

## Regression and limits

`golden/corpus/test_corpus_golden.py::test_memo_landing_violation_remains_guarded` fixes this finding to three observable facts: status remains `fail`, the resolved threshold remains `0.699999988 m/s`, and the metric remains `0.936580 m/s` within absolute `1e-6`. The full tier-2 test also compares all 140 requirement/log verdicts exactly and all available metric values under the committed per-metric absolute and relative tolerances.

The raw log is not redistributed. Reproduction downloads it from the public service using the pinned manifest and checksum, normalizes it, and runs the manually triggered golden workflow. This memo cannot establish intent, vehicle geometry, payload, local terrain, or pilot judgment, and it makes no claim beyond the implemented requirement and retained signals.
