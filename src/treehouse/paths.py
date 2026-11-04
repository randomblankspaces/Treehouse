"""Repository roots and the key-path guard.

Answer keys live under ``keys/``, outside every tool root. Nothing a tool serves may resolve there.
``TREEHOUSE_ROOT`` overrides repo-root discovery (for installed copies).
"""

from __future__ import annotations

import os
from pathlib import Path


class KeyPathError(PermissionError):
    """A path resolves into the answer-key directory."""


def repo_root() -> Path:
    env = os.environ.get("TREEHOUSE_ROOT")
    if env:
        return Path(env).resolve()
    for d in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (d / "pyproject.toml").is_file() and (d / "src" / "treehouse").is_dir():
            return d
    for d in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (d / "pyproject.toml").is_file() and (d / "src" / "treehouse").is_dir():
            return d
    raise FileNotFoundError("Treehouse repo root not found; set TREEHOUSE_ROOT")


def fixtures_root() -> Path:
    return repo_root() / "fixtures"


def keys_root() -> Path:
    return repo_root() / "keys"


def tasks_root() -> Path:
    return repo_root() / "tasks"


def tool_roots() -> list[Path]:
    """Directories tools may read from."""
    return [fixtures_root()]


def is_under(path: Path | str, root: Path | str) -> bool:
    """True if ``path`` (after resolving ``..`` and symlinks) is ``root`` or inside it."""
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def assert_not_key_path(path: Path | str) -> None:
    if is_under(path, keys_root()):
        raise KeyPathError(f"path resolves into keys/: {path}")
