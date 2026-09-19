import json
from pathlib import Path
from typing import Any

from px4reqcheck.ingest import pipeline


def test_parameter_changes_are_normalized_without_losing_timestamp() -> None:
    class FakeULog:
        changed_parameters = [(123, "GF_MAX_HOR_DIST", 50.0)]

    frame = pipeline._parameter_change_rows("log", FakeULog())

    assert frame.to_dict(orient="records") == [
        {
            "log_id": "log",
            "timestamp": 123,
            "name": "GF_MAX_HOR_DIST",
            "value_num": 50.0,
        }
    ]


def test_manifest_ingest_uses_half_core_pool_with_fresh_workers(
    tmp_path: Path, monkeypatch: Any
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"logs": [{"log_id": "a"}, {"log_id": "missing"}]}),
        encoding="utf-8",
    )
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "a.ulg").write_bytes(b"fixture")
    observed: dict[str, Any] = {}

    class FakePool:
        def __init__(self, processes: int, maxtasksperchild: int) -> None:
            observed["processes"] = processes
            observed["maxtasksperchild"] = maxtasksperchild

        def __enter__(self) -> "FakePool":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def starmap(self, _function: Any, tasks: list[tuple[str, Path, Path]]) -> list[dict]:
            observed["tasks"] = tasks
            return [{"log_id": task[0]} for task in tasks]

    monkeypatch.setattr(pipeline.multiprocessing, "cpu_count", lambda: 8)
    monkeypatch.setattr(pipeline.multiprocessing, "Pool", FakePool)

    results = pipeline.ingest_manifest(manifest, raw_dir, tmp_path / "output")

    assert observed["processes"] == 4
    assert observed["maxtasksperchild"] == 1
    assert observed["tasks"] == [("a", raw_dir / "a.ulg", tmp_path / "output")]
    assert results == [{"log_id": "a"}]
