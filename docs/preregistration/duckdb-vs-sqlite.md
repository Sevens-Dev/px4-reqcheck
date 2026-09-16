# Preregistration: DuckDB versus SQLite analytical queries

- Status: Registered before any timed comparison
- Registered: 2026-09-16
- Dataset: the committed 20-log v1.15 corpus manifest, after Week 2 ingest
- Repetitions: 10 cold-cache runs per engine and query

## Hypothesis

DuckDB is at least 5x faster than SQLite on all three named queries below.

## Queries

1. Full-scan aggregate: `full_scan_quality.sql`
2. Per-log group-by: `per_log_topic_rows.sql`
3. Time-window filter: `time_window_local_position.sql`

## Statistic and decision rule

For each engine/query pair, report the median of 10 runs. The hypothesis holds only if the SQLite median divided by the DuckDB median is at least 5.0 for every query. This is not a paired-by-item statistical comparison; no paired-bootstrap decision is used.

## Measurement controls

The final run must state CPU, RAM, operating environment, Python/DuckDB/SQLite versions, exact command, cold-cache procedure, and whether client work is the bottleneck. WSL2 timing must use pinned cores via `taskset` or be moved to a quieter disclosed machine.

## Null-result sentence

“On the preregistered 20-log slice, DuckDB was not at least 5x faster than SQLite on all three analytical queries; the repository retains DuckDB for direct Parquet access and operational simplicity, not a universal speed claim.”

## Minimum meaningful difference

The preregistered meaningful difference is the stated 5x ratio on every query. Smaller differences do not support the performance hypothesis.

## Current execution status

No publishable comparison has been run. The current implementation host is Ubuntu 26.04 rather than the required WSL2 Ubuntu 24.04 environment, so timing performed here would not satisfy the measurement contract.
