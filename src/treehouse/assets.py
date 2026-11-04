"""Asset-class registry (``config/asset-classes.yaml``, Req 1.4).

The system is class-agnostic: every report Table 8 class is defined once in the registry, and a new class
needs only a registry entry plus a task card — no class-specific code. RV1 (scale fit) and the output grader
read ``min_size_m`` / ``typical_size_m`` / ``cell_size_m`` from here, so sizes live in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

from treehouse.cards import LICENSE_RANK
from treehouse.paths import repo_root
from treehouse.schemas.base import Frozen


class AssetClassError(ValueError):
    pass


class UnknownAssetClass(AssetClassError):
    pass


class ReferenceSource(Frozen):
    id: str
    name: str
    completeness: Literal["complete", "incomplete", "synthetic"]
    license: str


class AssetClass(Frozen):
    label: str
    positive: str
    negative: list[str]
    min_size_m: float
    typical_size_m: float
    min_area_m2: float | None = None
    suitable_gsd_m: list[float]
    cell_size_m: float
    references: list[ReferenceSource]


class AssetClasses(Frozen):
    schema_version: Literal["treehouse.asset-classes/1"] = "treehouse.asset-classes/1"
    cell_size_default_m: float = 160
    classes: dict[str, AssetClass]

    @classmethod
    def load(cls, path: Path | str | None = None) -> AssetClasses:
        p = Path(path) if path is not None else repo_root() / "config" / "asset-classes.yaml"
        reg = cls.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
        reg._validate()
        return reg

    def _validate(self) -> None:
        if not self.classes:
            raise AssetClassError("asset-classes.yaml defines no classes")
        for name, c in self.classes.items():
            if not (0 < c.min_size_m <= c.typical_size_m):
                raise AssetClassError(f"{name}: need 0 < min_size_m <= typical_size_m")
            if not c.suitable_gsd_m or any(g <= 0 for g in c.suitable_gsd_m):
                raise AssetClassError(f"{name}: suitable_gsd_m must be non-empty and positive")
            if c.cell_size_m <= 0:
                raise AssetClassError(f"{name}: cell_size_m must be positive")
            if not c.references:
                raise AssetClassError(f"{name}: at least one reference source is required")
            unknown = sorted({r.license for r in c.references} - set(LICENSE_RANK))
            if unknown:
                raise AssetClassError(f"{name}: unknown licence id(s) {', '.join(unknown)}")

    def get(self, name: str) -> AssetClass:
        try:
            return self.classes[name]
        except KeyError:
            raise UnknownAssetClass(f"no asset class {name!r}; known: {sorted(self.classes)}") from None

    def resolvable_at(self, name: str, gsd_m: float) -> bool:
        """RV3 helper: is the class resolvable at this ground-sample distance?"""
        return gsd_m <= max(self.get(name).suitable_gsd_m)

    def cell_fits(self, name: str, cell_size_m: float) -> bool:
        """RV1 helper: a cell is a plausible unit only if it is not much larger than a typical instance.

        A cell up to ~4x the typical object side still localises it; far-coarser cells (e.g. the 1.28 km
        LGND index for 80 m warehouses) do not, and choosing one without a stated limitation is an error.
        """
        return cell_size_m <= 4 * self.get(name).typical_size_m
