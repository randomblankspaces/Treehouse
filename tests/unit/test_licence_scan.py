"""No imagery pixels in the repo: reject image magic bytes or base64 image data in fixtures/, tasks/, docs/."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ["fixtures", "tasks", "docs"]
MAGIC = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "tiff-le": b"II*\x00",
    "tiff-be": b"MM\x00*",
}
# base64 of the magic numbers above, plus data: URIs
B64 = re.compile(rb"data:image/|iVBORw0KGgo|/9j/[0-9A-Za-z+/]{4}|SUkqA|TU0AKg")


def image_findings(roots: list[Path]) -> list[str]:
    found = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            data = path.read_bytes()
            for name, magic in MAGIC.items():
                if data.startswith(magic) or magic in data:
                    found.append(f"{path.name}: {name} bytes")
            if B64.search(data):
                found.append(f"{path.name}: base64 image data")
    return found


def test_repo_has_no_image_data():
    assert image_findings([ROOT / d for d in SCANNED]) == []


def test_scan_catches_planted_images(tmp_path):
    (tmp_path / "a.png").write_bytes(MAGIC["png"] + b"rest")
    (tmp_path / "b.bin").write_bytes(b"xx" + MAGIC["jpeg"] + b"yy")
    (tmp_path / "c.tif").write_bytes(MAGIC["tiff-le"])
    (tmp_path / "d.md").write_text("![x](data:image/png;base64,iVBORw0KGgoAAAANS)")
    (tmp_path / "e.json").write_text('{"img": "/9j/4AAQSkZJRg"}')
    (tmp_path / "ok.txt").write_text("plain text about MM and II")
    found = image_findings([tmp_path])
    assert {f.split(":")[0] for f in found} == {"a.png", "b.bin", "c.tif", "d.md", "e.json"}
