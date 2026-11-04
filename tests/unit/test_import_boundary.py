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
IO_EXTERNAL = {"boto3", "botocore", "httpx", "strands", "mcp", "rasterio", "socket",
               "requests", "urllib3", "aiohttp", "ssl", "urllib.request", "http.client"}  # last 5: beyond §1
LAZY = ["boto3", "botocore", "strands", "rasterio"]
_DYNAMIC = {"import_module", "__import__"}


def _is_io_external(mod: str) -> bool:
    return any(mod == x or mod.startswith(x + ".") for x in IO_EXTERNAL)


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
            elif node.module:  # ``from treehouse import gateway`` -> treehouse.gateway
                out += [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
            if name in _DYNAMIC:  # importlib.import_module("boto3") / __import__("boto3")
                out.append(node.args[0].value)
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
                if _is_io_external(mod) or inner in IO_INTERNAL:
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
        "score": "import importlib\nimportlib.import_module('boto3')\n",
        "checks": "import urllib.request, http.client, requests\nimport urllib.parse\n",
        "report": "from treehouse import gateway, schemas\n",
    }.items():
        (root / sub).mkdir(parents=True)
        (root / sub / "bad.py").write_text(body)
    (root / "summary").mkdir()
    (root / "summary" / "phrase.py").write_text("import boto3\n")
    (root / "schemas" / "ok.py").write_text("from treehouse import canon\nfrom treehouse.schemas import base\n")
    found = boundary_violations(root)
    assert found == [
        "checks/bad.py: imports urllib.request",
        "checks/bad.py: imports http.client",
        "checks/bad.py: imports requests",
        "report/bad.py: imports treehouse.gateway",
        "schemas/bad.py: imports treehouse.providers.fake",
        "score/bad.py: imports boto3",
        "stats/bad.py: imports requests",
        "trust/bad.py: imports treehouse.gateway",
        "trust/bad.py: imports boto3",
    ]


def _import_all_without_lazy(package: str, extra_path: Path | None = None) -> subprocess.CompletedProcess:
    code = (
        "import sys, pkgutil, importlib\n"
        + (f"sys.path.insert(0, {str(extra_path)!r})\n" if extra_path else "")
        + f"for m in {LAZY!r}: sys.modules[m] = None\n"
        f"import {package}\n"
        f"for info in pkgutil.walk_packages({package}.__path__, '{package}.'):\n"
        "    importlib.import_module(info.name)\n"
    )
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)


def test_lazy_imports():
    """Every module imports with boto3, botocore, strands and rasterio unavailable."""
    r = _import_all_without_lazy("treehouse")
    assert r.returncode == 0, r.stderr


def test_lazy_import_check_can_fail(tmp_path):
    pkg = tmp_path / "plantpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "bedrock.py").write_text("import botocore.config\n")
    r = _import_all_without_lazy("plantpkg", tmp_path)
    assert r.returncode != 0 and "botocore" in r.stderr
