"""Upload one verified sealed local run to the Object Lock run-store bucket."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.paths import repo_root
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify

IMAGE_MAGIC = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"II*\x00",
    b"MM\x00*",
    b"II+\x00",
    b"MM\x00+",
)


def _run_files(run_dir: Path) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"run contains a symlink: {path.relative_to(run_dir)}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"run contains a non-file entry: {path.relative_to(run_dir)}")
        resolved = path.resolve()
        if not resolved.is_relative_to(run_dir):
            raise ValueError(f"run entry escapes the run directory: {path.relative_to(run_dir)}")
        data = path.read_bytes()
        if any(magic in data for magic in IMAGE_MAGIC):
            raise ValueError(f"run contains image bytes: {path.relative_to(run_dir)}")
        files.append((path.relative_to(run_dir).as_posix(), data))
    return files


def _json_value(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def publish_run(
    store_root: Path | str,
    run_id: str,
    *,
    bucket: str,
    receipt_path: Path | str,
    s3: Any,
) -> dict[str, Any]:
    receipt_path = Path(receipt_path).expanduser().resolve()
    if receipt_path.exists():
        raise ValueError(f"receipt already exists: {receipt_path}")
    store = LocalStore(Path(store_root).expanduser().resolve())
    unresolved_run_dir = store.run_dir(run_id)
    if unresolved_run_dir.is_symlink():
        raise ValueError(f"run directory is a symlink: {unresolved_run_dir}")
    run_dir = unresolved_run_dir.resolve()
    if receipt_path.is_relative_to(run_dir):
        raise ValueError("receipt must be outside the sealed run directory")
    if not (run_dir / "SEALED").is_file():
        raise ValueError(f"run is not sealed: {run_dir}")
    report = verify(store, run_id)
    if not report.ok:
        detail = "; ".join(f"{problem.path}: {problem.message}" for problem in report.problems)
        raise ValueError(f"run verification failed: {detail}")
    files = _run_files(run_dir)

    objects = []
    for relative, data in files:
        key = f"runs/{run_id}/{relative}"
        response = s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ChecksumAlgorithm="SHA256",
        )
        version_id = response.get("VersionId")
        if not version_id:
            raise RuntimeError(f"S3 did not return a VersionId for {key}")
        head = s3.head_object(Bucket=bucket, Key=key, VersionId=version_id)
        objects.append(
            {
                "key": key,
                "VersionId": version_id,
                "sha256": sha256_bytes(data),
                "ObjectLockMode": head.get("ObjectLockMode"),
                "ObjectLockRetainUntilDate": _json_value(head.get("ObjectLockRetainUntilDate")),
            }
        )

    receipt = {"bucket": bucket, "run_id": run_id, "objects": objects}
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json(receipt) + "\n")
    return receipt


def _bucket(outputs_path: Path) -> str:
    outputs = json.loads(outputs_path.read_text(encoding="utf-8"))
    try:
        return outputs["TreehouseRunStore"]["RunStoreBucketName"]
    except (KeyError, TypeError) as exc:
        raise ValueError("CDK outputs do not contain TreehouseRunStore.RunStoreBucketName") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, default=repo_root() / "infra/cdk-outputs.json")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args(argv)

    import boto3

    publish_run(
        args.store,
        args.run_id,
        bucket=_bucket(args.outputs),
        receipt_path=args.receipt,
        s3=boto3.client("s3", region_name=args.region),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
