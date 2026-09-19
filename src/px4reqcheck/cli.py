"""Command-line interface for the PX4 requirement checker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from px4reqcheck.analytics.report import generate_static_figures
from px4reqcheck.analytics.requirements_report import generate_requirements_report
from px4reqcheck.benchmark import (
    benchmark_ingest,
    benchmark_sql,
    render_benchmark_report,
    write_result,
)
from px4reqcheck.corpus.download import download_manifest
from px4reqcheck.corpus.manifest import build_manifest
from px4reqcheck.ingest.pipeline import ingest_manifest

app = typer.Typer(no_args_is_help=True)
corpus_app = typer.Typer(no_args_is_help=True)
benchmark_app = typer.Typer(no_args_is_help=True)
requirements_app = typer.Typer(no_args_is_help=True)
app.add_typer(corpus_app, name="corpus")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(requirements_app, name="requirements")


@app.command("analyze")
def analyze(
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data/parquet"),
    output: Annotated[Path, typer.Option("--output")] = Path("reports/figures"),
) -> None:
    """Run committed analytical queries and emit static figures."""
    generated = generate_static_figures(data_root, output)
    typer.echo(f"generated {len(generated)} figures")


@requirements_app.command("evaluate")
def requirements_evaluate(
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data/parquet"),
    manifest: Annotated[Path, typer.Option("--manifest")] = Path("corpus/manifest.json"),
    output: Annotated[Path, typer.Option("--output")] = Path("docs/report"),
) -> None:
    """Evaluate all requirement/log pairs and generate traceability artifacts."""
    generated = generate_requirements_report(data_root, output, manifest)
    typer.echo(f"generated {len(generated)} requirement artifacts")


@benchmark_app.command("ingest")
def benchmark_ingest_command(
    manifest: Annotated[Path, typer.Option("--manifest")] = Path("corpus/manifest.json"),
    raw_dir: Annotated[Path, typer.Option("--raw-dir")] = Path("data/raw"),
    runs: Annotated[int, typer.Option("--runs", min=1)] = 10,
    cold_cache_command: Annotated[str, typer.Option("--cold-cache-command")] = (
        "sudo scripts/drop-caches.sh"
    ),
    output: Annotated[Path, typer.Option("--output")] = Path("reports/benchmarks/ingest.json"),
) -> None:
    """Measure cold-cache ULog-to-Parquet ingest throughput."""
    result = benchmark_ingest(manifest, raw_dir, runs, cold_cache_command)
    write_result(result, output)
    typer.echo(f"wrote {output}")


@benchmark_app.command("sql")
def benchmark_sql_command(
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data/parquet"),
    database: Annotated[Path, typer.Option("--database")] = Path("data/benchmark.sqlite"),
    runs: Annotated[int, typer.Option("--runs", min=1)] = 10,
    cold_cache_command: Annotated[str, typer.Option("--cold-cache-command")] = (
        "sudo scripts/drop-caches.sh"
    ),
    output: Annotated[Path, typer.Option("--output")] = Path("reports/benchmarks/sql.json"),
) -> None:
    """Compare DuckDB and SQLite on the three preregistered queries."""
    result = benchmark_sql(data_root, database, runs, cold_cache_command)
    write_result(result, output)
    typer.echo(f"wrote {output}")


@benchmark_app.command("report")
def benchmark_report_command(
    ingest_result: Annotated[Path, typer.Option("--ingest-result")] = Path(
        "reports/benchmarks/ingest.json"
    ),
    sql_result: Annotated[Path, typer.Option("--sql-result")] = Path("reports/benchmarks/sql.json"),
    output: Annotated[Path, typer.Option("--output")] = Path("reports/benchmarks/week2-results.md"),
) -> None:
    """Render the two raw benchmark results as a publication-ready report."""
    render_benchmark_report(ingest_result, sql_result, output)
    typer.echo(f"wrote {output}")


@corpus_app.command("build")
def corpus_build(
    output: Annotated[Path, typer.Option("--output")] = Path("corpus/manifest.json"),
    limit: Annotated[int, typer.Option("--limit", min=1)] = 20,
    firmware_minor: Annotated[str, typer.Option("--firmware-minor")] = "1.15",
) -> None:
    """Build the deterministic public-log manifest."""
    manifest = build_manifest(limit=limit, firmware_minor=firmware_minor)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"selected {len(manifest['logs'])} logs")


@corpus_app.command("download")
def corpus_download(
    manifest: Annotated[Path, typer.Option("--manifest")] = Path("corpus/manifest.json"),
    destination: Annotated[Path, typer.Option("--destination")] = Path("data/raw"),
    delay: Annotated[float, typer.Option("--delay", min=0)] = 6.0,
) -> None:
    """Download and checksum every log in a manifest."""
    result = download_manifest(manifest, destination, delay_s=delay)
    typer.echo(f"checksummed {sum(bool(item['sha256']) for item in result['logs'])} logs")


@app.command("ingest")
def ingest(
    manifest: Annotated[Path, typer.Option("--manifest")] = Path("corpus/manifest.json"),
    raw_dir: Annotated[Path, typer.Option("--raw-dir")] = Path("data/raw"),
    output: Annotated[Path, typer.Option("--output")] = Path("data/parquet"),
) -> None:
    """Normalize downloaded logs to per-log Parquet datasets."""
    results = ingest_manifest(manifest, raw_dir, output)
    typer.echo(f"ingested {len(results)} logs")
