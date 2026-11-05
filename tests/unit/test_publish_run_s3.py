from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/publish_run_s3.py"
SPEC = importlib.util.spec_from_file_location("publish_run_s3", SCRIPT)
assert SPEC and SPEC.loader
publish_run_s3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish_run_s3)


class FakeS3:
    def __init__(self) -> None:
        self.puts: list[dict] = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        return {"VersionId": f"version-{len(self.puts)}"}

    def head_object(self, **kwargs):
        return {
            "VersionId": kwargs["VersionId"],
            "ObjectLockMode": "COMPLIANCE",
            "ObjectLockRetainUntilDate": datetime(2030, 1, 1, tzinfo=UTC),
        }


def run_dir(tmp_path: Path) -> Path:
    path = tmp_path / "store" / "runs" / "run-1"
    (path / "trials").mkdir(parents=True)
    (path / "SEALED").write_text("sha256:sealed\n")
    (path / "manifest.json").write_text("{}")
    (path / "trials" / "t-0.claims.jsonl").write_text("{}\n")
    return path


def test_publish_uses_run_keys_and_writes_retention_receipt(tmp_path: Path, monkeypatch) -> None:
    path = run_dir(tmp_path)
    monkeypatch.setattr(publish_run_s3, "verify", lambda store, run_id: SimpleNamespace(ok=True, problems=[]))
    s3 = FakeS3()
    receipt_path = tmp_path / "receipt.json"

    receipt = publish_run_s3.publish_run(
        path.parent.parent,
        "run-1",
        bucket="run-store",
        receipt_path=receipt_path,
        s3=s3,
    )

    assert [call["Key"] for call in s3.puts] == [
        "runs/run-1/SEALED",
        "runs/run-1/manifest.json",
        "runs/run-1/trials/t-0.claims.jsonl",
    ]
    assert all(call["Bucket"] == "run-store" for call in s3.puts)
    assert all(call["ChecksumAlgorithm"] == "SHA256" for call in s3.puts)
    assert json.loads(receipt_path.read_text()) == receipt
    assert receipt["bucket"] == "run-store"
    assert receipt["objects"][0] == {
        "key": "runs/run-1/SEALED",
        "VersionId": "version-1",
        "sha256": "sha256:50b4825a7d245801659d4ae9ad0dff747ab1c48058faabbf9a2c6aaf084e90f8",
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2030-01-01T00:00:00+00:00",
    }


@pytest.mark.parametrize("case", ["existing-receipt", "image-bytes", "symlink"])
def test_publish_refuses_unsafe_inputs(tmp_path: Path, monkeypatch, case: str) -> None:
    path = run_dir(tmp_path)
    monkeypatch.setattr(publish_run_s3, "verify", lambda store, run_id: SimpleNamespace(ok=True, problems=[]))
    receipt = tmp_path / "receipt.json"
    if case == "existing-receipt":
        receipt.write_text("keep")
    elif case == "image-bytes":
        (path / "pixels.bin").write_bytes(b"prefix\x89PNG\r\n\x1a\nsuffix")
    else:
        (path / "outside-link").symlink_to(tmp_path / "outside")

    with pytest.raises(ValueError):
        publish_run_s3.publish_run(
            path.parent.parent,
            "run-1",
            bucket="run-store",
            receipt_path=receipt,
            s3=FakeS3(),
        )
