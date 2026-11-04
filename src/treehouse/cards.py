"""Task-card loading and ``treehouse task validate``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from treehouse import paths
from treehouse.geo.geom import bbox_ring, point_in_polygon, polygon_problems, polygons_intersect
from treehouse.schemas.task import DataSource, TaskCard

# Higher rank = more restrictive. The floor is the most restrictive licence among the inputs.
LICENSE_RANK = {
    "CC0-1.0": 0,
    "LicenseRef-public-domain": 0,
    "LicenseRef-synthetic": 0,
    "MIT": 1,
    "Apache-2.0": 1,
    "CC-BY-4.0": 2,
    "LicenseRef-copernicus-sentinel": 2,  # free and open, attribution required
    "CC-BY-SA-4.0": 3,
    "ODbL-1.0": 3,
    "CC-BY-NC-4.0": 4,
}
# Licences are not totally ordered, so the floor alone loses obligations. Every input licence that
# carries one is also reported (``license_obligations``) with its flags.
LICENSE_OBLIGATIONS: dict[str, tuple[str, ...]] = {
    "CC0-1.0": (),
    "LicenseRef-public-domain": (),
    "LicenseRef-synthetic": (),
    "MIT": ("attribution",),
    "Apache-2.0": ("attribution",),
    "CC-BY-4.0": ("attribution",),
    "LicenseRef-copernicus-sentinel": ("attribution",),
    "CC-BY-SA-4.0": ("attribution", "share_alike"),
    "ODbL-1.0": ("attribution", "share_alike"),
    "CC-BY-NC-4.0": ("attribution", "non_commercial"),
}
assert set(LICENSE_OBLIGATIONS) == set(LICENSE_RANK)


@dataclass
class ValidationReport:
    path: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    license_floor: str | None = None
    license_obligations: list[str] = field(default_factory=list)
    card_hash: str | None = None


def load_card(path: Path | str) -> TaskCard:
    return TaskCard.model_validate(yaml.safe_load(Path(path).read_text()))


def license_floor(licenses: list[str]) -> str | None:
    """The most restrictive licence id(s) among ``licenses`` (ties joined with '+'); None if empty."""
    if not licenses:
        return None
    top = max(LICENSE_RANK[x] for x in licenses)
    return "+".join(sorted({x for x in licenses if LICENSE_RANK[x] == top}))


def license_obligations(licenses: list[str]) -> list[str]:
    """Every distinct input licence that carries an obligation, most restrictive first."""
    ids = {x for x in licenses if LICENSE_OBLIGATIONS[x]}
    return sorted(ids, key=lambda x: (-LICENSE_RANK[x], x))


def describe_obligations(ids: list[str]) -> str:
    return "; ".join(f"{x} ({', '.join(LICENSE_OBLIGATIONS[x])})" for x in ids) or "none"


def _field_errors(e: ValidationError) -> list[str]:
    out = []
    for err in e.errors():
        msg = err["msg"].removeprefix("Value error, ")
        loc = ".".join(str(p) for p in err["loc"])
        out.append(f"{loc}: {msg}" if loc else (msg if ": " in msg else f"card: {msg}"))
    return out


def _footprint(item: dict[str, Any]) -> list | None:
    """Polygons (list of rings) of a STAC item: GeoJSON ``geometry`` or a bare ``footprint`` ring."""
    g = item.get("geometry")
    if isinstance(g, dict) and g.get("type") == "Polygon":
        return [g["coordinates"]]
    if isinstance(g, dict) and g.get("type") == "MultiPolygon":
        return g["coordinates"]
    ring = item.get("footprint")
    if isinstance(ring, list) and ring:
        return [[ring if ring[0] == ring[-1] else [*ring, ring[0]]]]
    return None


def _pinned_items(base: Path, src: DataSource, where: str, errors: list[str]) -> dict[str, dict]:
    """Load the pinned items of a STAC fixture: ``<dir>/items/<id>.json`` (with ``etags.json`` checked
    against the card when present), or one JSON file holding ``items`` / ``features``."""
    items: dict[str, dict] = {}
    if base.is_file():
        data = json.loads(base.read_text())
        found = {i.get("id"): i for i in data.get("items") or data.get("features") or []}
        for x in src.item_ids:
            if x in found:
                items[x] = found[x]
            else:
                errors.append(f"{where}.item_ids: item {x} not in fixture {src.fixture_path}")
        return items
    for x in src.item_ids:
        f = base / "items" / f"{x}.json"
        if f.is_file():
            items[x] = json.loads(f.read_text())
        else:
            errors.append(f"{where}.item_ids: no fixture file items/{x}.json")
    etags_file = base / "etags.json"
    if etags_file.is_file():
        on_disk = json.loads(etags_file.read_text())
        wrong = [x for x in src.item_ids if on_disk.get(x) != src.etags.get(x)]
        if wrong:
            errors.append(f"{where}.etags: {len(wrong)} ETag(s) differ from etags.json (first: {wrong[0]})")
    return items


def _path_rules(rel: str, where: str, errors: list[str], tool_root: bool) -> None:
    root = paths.repo_root()
    p = root / rel
    if paths.may_be_under(p, paths.keys_root()):
        errors.append(f"{where}: {rel} is under keys/")
    elif tool_root and not any(paths.is_under(p, t) for t in paths.tool_roots()):
        errors.append(f"{where}: {rel} is not under a tool root (fixtures/)")
    elif not paths.is_under(p, root):
        errors.append(f"{where}: {rel} escapes the repository")


def validate_card(path: Path | str) -> ValidationReport:
    report = ValidationReport(path=str(path))
    try:
        card = load_card(path)
    except ValidationError as e:
        report.errors = _field_errors(e)
        return report
    except (OSError, yaml.YAMLError) as e:
        report.errors = [f"card: {e}"]
        return report
    errors, warnings = report.errors, report.warnings
    root = paths.repo_root()
    aoi = card.aoi.polygons()

    errors += [f"aoi: {p}" for p in polygon_problems(aoi)]
    if card.smoke_aoi is not None and not any(
        all(point_in_polygon(c, poly) for c in bbox_ring(card.smoke_aoi)) for poly in aoi
    ):
        errors.append("smoke_aoi: every corner must lie inside the aoi")
    if card.event and card.event.footprint_ref:
        _path_rules(card.event.footprint_ref, "event.footprint_ref", errors, tool_root=True)
    if card.gold_plan:
        _path_rules(card.gold_plan.seed_file, "gold_plan.seed_file", errors, tool_root=False)

    licenses = []
    footprints: list[list] = []
    for i, src in enumerate(card.data_allowlist):
        where = f"data_allowlist.{i}"
        licenses.append(src.license)
        if src.fixture_path:
            _path_rules(src.fixture_path, f"{where}.fixture_path", errors, tool_root=True)
        if src.status == "pinned":
            base = root / src.fixture_path if src.fixture_path else None
            if base is None or not base.exists():
                errors.append(f"{where}.fixture_path: pinned source has no fixture on disk")
            missing = [x for x in src.item_ids if x not in src.etags]
            if missing or not src.item_ids:
                errors.append(f"{where}.etags: pinned items need an ETag each (missing: {len(missing)})")
            if base is not None and base.exists() and src.kind == "stac":
                for x, item in _pinned_items(base, src, where, errors).items():
                    fp = _footprint(item)
                    if fp is None:
                        errors.append(f"{where}.item_ids: item {x} has no footprint")
                    else:
                        footprints.append(fp)
        else:
            warnings.append(f"{where}: source {src.source_id} is {src.status}")

    if footprints:
        if not polygons_intersect(aoi, [p for fp in footprints for p in fp]):
            errors.append("aoi: does not intersect any pinned footprint (lon/lat swapped?)")
    else:
        warnings.append("aoi: footprint intersection not checked (no pinned STAC source with footprints yet)")

    for i, step in enumerate(card.steps):
        k, where = step.keying, f"steps.{i}.keying"
        if k.mode == "unkeyed":
            if card.gold_plan is None:
                warnings.append(f"steps.{i}: unkeyed and no gold_plan; its accuracy can only be model-estimated")
            continue
        if k.license:
            licenses.append(k.license)
        key = root / k.key_path
        if not paths.is_under(key, paths.keys_root()):
            errors.append(f"{where}.key_path: {k.key_path} is not under keys/")
        if any(paths.is_under(key, t) for t in paths.tool_roots()):
            errors.append(f"{where}.key_path: {k.key_path} is under a tool root")
        if k.status == "pending_fetch":
            warnings.append(f"{where}: key is pending_fetch; keyed scores unavailable until it is fetched")
        elif k.status == "pending_generation":
            warnings.append(f"{where}: key is pending_generation; keyed scores unavailable until it is generated")
        elif not key.exists():
            errors.append(f"{where}.key_path: key is 'present' but {k.key_path} is not on disk")

    unknown = sorted({x for x in licenses if x not in LICENSE_RANK})
    if unknown:
        errors.append(f"license: unknown licence id(s) {', '.join(unknown)}; add them to LICENSE_RANK")
    elif not licenses:
        errors.append("license: no licences declared")
    else:
        report.license_floor = license_floor(licenses)
        report.license_obligations = license_obligations(licenses)
    report.card_hash = card.card_hash()
    return report
