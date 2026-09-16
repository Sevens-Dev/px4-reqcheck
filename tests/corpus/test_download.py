import json
from collections.abc import Iterator
from pathlib import Path

from px4reqcheck.corpus.download import download_manifest


class Response:
    def __init__(self, status_code: int, body: bytes = b"") -> None:
        self.status_code = status_code
        self.body = body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def iter_content(self, _: int) -> Iterator[bytes]:
        yield self.body


class Session:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = iter(responses)

    def get(self, *_args: object, **_kwargs: object) -> Response:
        return next(self.responses)


def test_download_records_404_and_checksums_success(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "download_endpoint": "https://example.invalid/download",
                "logs": [{"log_id": "gone", "sha256": None}, {"log_id": "kept", "sha256": None}],
            }
        ),
        encoding="utf-8",
    )
    session = Session([Response(404), Response(200, b"ulog")])

    result = download_manifest(manifest_path, tmp_path / "raw", delay_s=0, session=session)

    assert result["logs"][0]["sha256"] is None
    assert (
        result["logs"][1]["sha256"]
        == "8f468ffb4d24458558e7e8be0f08b6f827a6ffb16f4bbcea50b5acfde4e9c80e"
    )
    assert json.loads((tmp_path / "missing.json").read_text())["missing"] == ["gone"]


def test_existing_file_must_match_manifest_checksum(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "download_endpoint": "https://example.invalid/download",
                "logs": [{"log_id": "kept", "sha256": "wrong"}],
            }
        ),
        encoding="utf-8",
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "kept.ulg").write_bytes(b"ulog")

    try:
        download_manifest(manifest_path, raw, delay_s=0, session=Session([]))
    except ValueError as error:
        assert "checksum mismatch" in str(error)
    else:
        raise AssertionError("checksum mismatch was not rejected")
