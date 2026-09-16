"""Command-line interface for the PX4 requirement checker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from px4reqcheck.corpus.download import download_manifest
from px4reqcheck.corpus.manifest import build_manifest
from px4reqcheck.ingest.pipeline import ingest_manifest

app = typer.Typer(no_args_is_help=True)
corpus_app = typer.Typer(no_args_is_help=True)
app.add_typer(corpus_app, name="corpus")


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
