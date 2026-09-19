# Python/C++ checker timing

Both commands consume the same versioned `export/checks.json`, re-derive 140 verdicts, independently compute `descent_rate_pre_land_p95` from raw timestamp/`vz`/`z` arrays, and write a verdict JSON file. ULog download, parsing, Parquet normalization, and exchange export are outside the measured command boundary. Process startup and imports are included.

| Implementation | Median of 20 | IQR (Q1-Q3) | Agreement |
|---|---:|---:|---:|
| Python 3.12.3 | 5.010 s | 0.095 s (4.985-5.080 s) | 140/140 verdicts |
| C++17, GCC 13.3.0 `-O3` | 0.187 s | 0.003 s (0.186-0.189 s) | 140/140 verdicts |

This is a checker-only timing table, not a pipeline speedup claim. The C++ checker re-derives every scalar verdict, but independent computation is meaningful only for the one raw-sample metric; the remaining verdicts deliberately share Python-exported scalar metrics and thresholds.

## Measurement contract

- Run: [GitHub Actions workflow 35449563251](https://github.com/Sevens-Dev/px4-reqcheck/actions/runs/35449563251), commit `e5631d6`.
- Host: Ubuntu 24.04 GitHub-hosted shared runner, AMD EPYC 7763, 4 logical CPUs, 15.6 GiB RAM.
- Harness: hyperfine 1.19.0, 3 warmups, 20 measured runs per command.
- Python command: `uv run px4reqcheck python-checks --checks export/checks.json --output /tmp/python_verdicts.json`.
- C++ command: `cpp/build/px4-reqcheck-cpp export/checks.json /tmp/cpp_verdicts.json`.
- Toolchain: uv 0.8.22, Python 3.12.3, CMake 3.31.6, GCC 13.3.0, Release build (`-O3`).
- Raw evidence: [`cpp-timing.json`](cpp-timing.json) and [`cpp-timing-environment.txt`](cpp-timing-environment.txt).

Both post-timing outputs passed the same schema and matched the committed Python report. No claim is made that these shared-CPU wall-clock values generalize to other hardware.
