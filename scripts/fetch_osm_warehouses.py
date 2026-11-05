"""Compatibility entry point; accepts fetch_osm_pool.py arguments, including --class."""
from __future__ import annotations

import runpy
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    return runpy.run_path(str(Path(__file__).with_name("fetch_osm_pool.py")))["main"](argv)


if __name__ == "__main__":
    raise SystemExit(main())
