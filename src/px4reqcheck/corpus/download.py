"""Checksum-aware, rate-limited public log downloader."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol

import requests


class HttpResponse(Protocol):
    status_code: int

    def raise_for_status(self) -> None: ...

    def iter_content(self, chunk_size: int) -> Iterator[bytes]: ...


class HttpClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> HttpResponse: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_manifest(
    manifest_path: Path,
    destination: Path,
    *,
    delay_s: float = 6.0,
    timeout_s: float = 600,
    session: HttpClient | None = None,
) -> dict[str, Any]:
    """Download every manifest entry, recording checksums and non-fatal 404s."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    client = session or requests.Session()
    logs = manifest["logs"]
    request_count = 0
    for entry in logs:
        log_id = entry["log_id"]
        target = destination / f"{log_id}.ulg"
        if target.exists():
            actual = sha256_file(target)
            expected = entry.get("sha256")
            if expected and actual != expected:
                raise ValueError(f"checksum mismatch for existing log {log_id}")
            entry["sha256"] = actual
        else:
            if request_count and delay_s > 0:
                time.sleep(delay_s)
            response = client.get(
                manifest["download_endpoint"],
                params={"log": log_id},
                stream=True,
                timeout=timeout_s,
            )
            request_count += 1
            if response.status_code == 404:
                missing.append(log_id)
            else:
                response.raise_for_status()
                partial = target.with_suffix(".ulg.part")
                with partial.open("wb") as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            stream.write(chunk)
                os.replace(partial, target)
                entry["sha256"] = sha256_file(target)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    missing_path = manifest_path.with_name("missing.json")
    missing_path.write_text(json.dumps({"missing": missing}, indent=2) + "\n", encoding="utf-8")
    return manifest
