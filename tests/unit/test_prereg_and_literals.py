"""prereg/trust-config.yaml equals TrustConfig defaults; no region constants in src/ (J15 partial)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

from treehouse.schemas.config import TrustConfig

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "treehouse"
PLACE_NAMES = [
    "nepal", "bhote", "koshi", "rasuwa", "syabrubesi", "timure", "rasuwagadhi", "trishuli", "kathmandu",
    "virginia", "india", "brahmaputra", "assam", "guwahati", "tibet", "china",
]
COORD_IN_STR = re.compile(r"(?<![\d.])-?(\d{2,3}\.\d{2,})(?![\d.])")
PLACE_RE = re.compile(r"\b(" + "|".join(PLACE_NAMES) + r")\b", re.IGNORECASE)


def test_prereg_trust_config_equals_defaults():
    data = yaml.safe_load((ROOT / "prereg" / "trust-config.yaml").read_text())
    assert TrustConfig(**data) == TrustConfig()
    assert set(data) == set(TrustConfig.model_fields)


def _docstrings(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def region_constants(path: Path) -> list[str]:
    """Coordinate-like literals (10 <= |x| <= 180 with >= 2 decimals, as floats or inside strings) and
    place names in code. One-decimal floats and integers are not flagged: too many legitimate uses."""
    tree = ast.parse(path.read_text())
    docs = _docstrings(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            x = abs(node.value)
            if 10 <= x <= 180 and round(x, 1) != x:
                found.append(f"{path.name}:{node.lineno}: coordinate-like literal {node.value}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            if PLACE_RE.search(node.value):
                found.append(f"{path.name}:{node.lineno}: place name in {node.value!r}")
            if any(10 <= float(m) <= 180 for m in COORD_IN_STR.findall(node.value)):
                found.append(f"{path.name}:{node.lineno}: coordinate-like text in {node.value!r}")
        elif isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if PLACE_RE.search(name.replace("_", " ")):
                found.append(f"{path.name}:{node.lineno}: place name in identifier {name}")
    return found


def test_no_region_constants_in_src():
    found = [f for p in sorted(SRC.rglob("*.py")) for f in region_constants(p)]
    assert found == []


def test_region_scan_can_fail(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text('"""Docstrings may mention Nepal."""\nAOI = [85.33, 28.15]\nNAME = "Bhote Koshi"\nnepal_aoi = 1\nZ = 1.96\n'
                 'BBOX = "85.33,28.15"\nVERSION = "1.43.2"\n')
    found = region_constants(p)
    assert len(found) == 5, found
