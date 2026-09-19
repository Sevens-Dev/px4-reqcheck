# Week 2 benchmark results

## Environment

- CPU: AMD EPYC 7763 64-Core Processor
- RAM: 16373452 kB
- Platform: Ubuntu 24.04 GitHub Actions hosted runner; `Linux-6.17.0-1022-azure-x86_64-with-glibc2.39`
- Logical CPUs: 4
- Python: 3.12.3
- DuckDB: 1.5.5
- SQLite: 3.45.1
- pandas: 2.3.3
- PyArrow: 23.0.1
- Git commit: `4ef944c4923f7d3844c5d546109dc947e3bf75e8`
- GitHub Actions run ID: `35446881914`

## Ingest throughput

Median of 10 cold-cache runs over 20 logs and 2135881 telemetry rows: **187231 rows/s** (11.408 s median wall time).

Exact command:

```bash
uv run px4reqcheck benchmark ingest --runs 10 \
  --cold-cache-command 'sudo scripts/drop-caches.sh' \
  --output benchmark-output/ingest.json
```

## DuckDB versus SQLite

Statistic: median of 10 cold-cache runs. The timed region is: open connection, register DuckDB Parquet view where applicable, execute query, fetch all rows, close connection.
SQLite materialization and index creation occur before timing. Each engine's result rows are asserted equal before and during the timed repetitions.

| Query | DuckDB median (s) | SQLite median (s) | SQLite / DuckDB |
|---|---:|---:|---:|
| `full_scan_quality` | 0.023416 | 0.002543 | 0.11x |
| `per_log_topic_rows` | 0.021554 | 0.001863 | 0.09x |
| `time_window_local_position` | 0.047302 | 0.042771 | 0.90x |

Exact command:

```bash
uv run px4reqcheck benchmark sql --runs 10 \
  --cold-cache-command 'sudo scripts/drop-caches.sh' \
  --output benchmark-output/sql.json
```

Cold-cache procedure: before every timed repetition, the harness invokes `sudo scripts/drop-caches.sh`, which calls `sync` and asks Linux to drop page, dentry, and inode caches. The client is the benchmark process itself; there is no server or load generator, so client/server queueing is not applicable.

On the preregistered 20-log slice, DuckDB was not at least 5x faster than SQLite on all three analytical queries; the repository retains DuckDB for direct Parquet access and operational simplicity, not a universal speed claim.
