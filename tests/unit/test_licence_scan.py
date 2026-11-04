"""No imagery pixels in the repo: reject image magic bytes, base64 image data, images inside zip/npz/gz
containers, and uint8 pixel arrays (``.npy``, ``.npz`` members) in fixtures/, tasks/, docs/, tests/, keys/."""

from __future__ import annotations

import gzip
import io
import re
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ["fixtures", "tasks", "docs", "tests", "keys"]
SELF = Path(__file__).resolve()  # this file names the patterns it looks for
MAGIC = {  # found anywhere in a file
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "tiff-le": b"II*\x00",
    "tiff-be": b"MM\x00*",
    "bigtiff-le": b"II+\x00",
    "bigtiff-be": b"MM\x00+",
    "jp2": b"\x00\x00\x00\x0cjP  \r\n\x87\n",
    "j2k": b"\xff\x4f\xff\x51",
}
LEADING = {  # short or text-like signatures: only at the start of a file or container member
    "gif": re.compile(rb"\AGIF8[79]a", re.S),
    "webp": re.compile(rb"\ARIFF.{4}WEBP", re.S),
}
# base64 of the signatures above, plus data: URIs
B64 = re.compile(rb"data:image/|iVBORw0KGgo|/9j/[0-9A-Za-z+/]{4}|SUkqA|TU0AKg|R0lGOD[dl]h|UklGR[0-9A-Za-z+/]{6}XRUJQ")


def _npy_pixels(data: bytes) -> bool:
    try:
        arr = np.load(io.BytesIO(data), allow_pickle=False, mmap_mode=None)
    except Exception:  # noqa: BLE001 - not a readable .npy
        return False
    return arr.dtype == np.uint8 and arr.ndim >= 2


def _bytes_findings(name: str, data: bytes, depth: int = 0) -> list[str]:
    found = [f"{name}: {k} bytes" for k, m in MAGIC.items() if m in data]
    found += [f"{name}: {k} bytes" for k, rx in LEADING.items() if rx.search(data)]
    if B64.search(data):
        found.append(f"{name}: base64 image data")
    if data.startswith(b"\x93NUMPY") and _npy_pixels(data):
        found.append(f"{name}: uint8 pixel array")
    if depth < 2 and data.startswith(b"PK\x03\x04"):  # zip / npz
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for member in z.namelist():
                    found += _bytes_findings(f"{name}/{member}", z.read(member), depth + 1)
        except zipfile.BadZipFile:
            pass
    if depth < 2 and data.startswith(b"\x1f\x8b"):
        try:
            found += _bytes_findings(f"{name}/gunzip", gzip.decompress(data), depth + 1)
        except OSError:
            pass
    return found


def image_findings(roots: list[Path]) -> list[str]:
    found = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if path.resolve() == SELF or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            found += _bytes_findings(path.name, path.read_bytes())
    return found


def test_repo_has_no_image_data():
    assert image_findings([ROOT / d for d in SCANNED]) == []


def test_scan_catches_planted_images(tmp_path):
    (tmp_path / "a.png").write_bytes(MAGIC["png"] + b"rest")
    (tmp_path / "b.bin").write_bytes(b"xx" + MAGIC["jpeg"] + b"yy")
    (tmp_path / "c.tif").write_bytes(MAGIC["tiff-le"])
    (tmp_path / "d.md").write_text("![x](data:image/png;base64,iVBORw0KGgoAAAANS)")
    (tmp_path / "e.json").write_text('{"img": "/9j/4AAQSkZJRg"}')
    (tmp_path / "f.gif").write_bytes(b"GIF89a\x01\x00")
    (tmp_path / "g.webp").write_bytes(b"RIFF\x10\x00\x00\x00WEBPVP8 ")
    (tmp_path / "h.tif").write_bytes(MAGIC["bigtiff-le"] + b"\x08\x00")
    (tmp_path / "i.jp2").write_bytes(MAGIC["jp2"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("inner.png", MAGIC["png"])
    (tmp_path / "j.zip").write_bytes(buf.getvalue())
    (tmp_path / "k.gz").write_bytes(gzip.compress(MAGIC["png"] + b"x"))
    np.save(tmp_path / "l.npy", np.zeros((4, 4, 3), dtype=np.uint8))
    np.savez(tmp_path / "m.npz", pixels=np.zeros((8, 8), dtype=np.uint8))
    (tmp_path / "n.json").write_text('{"gif": "R0lGODlhAQABAIAAAP"}')
    (tmp_path / "ok.txt").write_text("plain text about MM and II, GIF and RIFF")
    np.save(tmp_path / "ok-floats.npy", np.zeros((4, 4), dtype=np.float32))
    np.savez(tmp_path / "ok-embeddings.npz", emb=np.zeros((10, 32), dtype=np.float32))
    found = image_findings([tmp_path])
    assert {f.split(":")[0].split("/")[0] for f in found} == {
        "a.png", "b.bin", "c.tif", "d.md", "e.json", "f.gif", "g.webp", "h.tif", "i.jp2", "j.zip", "k.gz",
        "l.npy", "m.npz", "n.json",
    }
