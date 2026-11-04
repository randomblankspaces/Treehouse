"""Import boundary (IMPLEMENTATION-DESIGN §1), enforced by AST. A planted violation proves it can fail."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "treehouse"
STDLIB = set(sys.stdlib_module_names) | {"__future__"}

LEAF = {"stats", "sampling"}  # stdlib + numpy + scipy only
PURE = {"geo", "checks", "score", "trust", "summary", "report"}  # never touch I/O layers
PURE_EXEMPT = {("summary", "phrase.py")}
IO_INTERNAL = {"providers", "harness", "gateway", "tools", "store", "runner"}
IO_EXTERNAL = {"boto3", "botocore", "httpx", "strands", "mcp", "rasterio", "socket"}
LAZY = ["boto3", "strands", "rasterio"]


def _imports(path: Path, pkg: list[str]) -> list[str]:
    """Absolute dotted names imported by ``path``; ``pkg`` is its package, e.g. ['treehouse', 'stats']."""
    out: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - node.level + 1]
                mod = ".".join(base + ([node.module] if node.module else []))
                out += [mod] if node.module else [f"{mod}.{a.name}" for a in node.names]
            elif node.module:
                out.append(node.module)
    return out


def boundary_violations(src: Path) -> list[str]:
    bad: list[str] = []
    for path in sorted(src.rglob("*.py")):
        rel = path.relative_to(src)
        pkg = ["treehouse", *rel.parts[:-1]]
        sub = rel.parts[0] if len(rel.parts) > 1 else None
        for mod in _imports(path, pkg):
            top = mod.split(".")[0]
            inner = mod.split(".")[1] if top == "treehouse" and "." in mod else None
            where = f"{rel}: imports {mod}"
            if sub in LEAF:
                if not (top in STDLIB or top in {"numpy", "scipy"} or inner == sub):
                    bad.append(where)
            elif sub == "schemas":
                if not (top in STDLIB or top == "pydantic" or inner in {"schemas", "canon"}):
                    bad.append(where)
            elif sub in PURE and (sub, rel.name) not in PURE_EXEMPT:
                if top in IO_EXTERNAL or inner in IO_INTERNAL:
                    bad.append(where)
    return bad


def test_source_tree_respects_boundaries():
    assert boundary_violations(SRC) == []


def test_planted_violations_are_caught(tmp_path):
    root = tmp_path / "treehouse"
    for sub, body in {
        "stats": "import requests\n",
        "schemas": "from treehouse.providers import fake\n",
        "trust": "from ..gateway import gateway\nimport boto3\n",
        "geo": "import numpy\nfrom . import match\n",
    }.items():
        (root / sub).mkdir(parents=True)
        (root / sub / "bad.py").write_text(body)
    (root / "summary").mkdir()
    (root / "summary" / "phrase.py").write_text("import boto3\n")
    found = boundary_violations(root)
    assert found == [
        "schemas/bad.py: imports treehouse.providers",
        "stats/bad.py: imports requests",
        "trust/bad.py: imports treehouse.gateway",
        "trust/bad.py: imports boto3",
    ]


def test_lazy_imports():
    """Every module imports with boto3, strands and rasterio unavailable."""
    code = (
        "import sys, pkgutil, importlib\n"
        f"for m in {LAZY!r}: sys.modules[m] = None\n"
        "import treehouse\n"
        "for info in pkgutil.walk_packages(treehouse.__path__, 'treehouse.'):\n"
        "    importlib.import_module(info.name)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
