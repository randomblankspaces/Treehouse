"""Task-card loading and ``treehouse task validate``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from treehouse import paths
from treehouse.geo.geom import polygon_problems
from treehouse.schemas.task import TaskCard

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


@dataclass
class ValidationReport:
    path: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    license_floor: str | None = None
    card_hash: str | None = None


def load_card(path: Path | str) -> TaskCard:
    return TaskCard.model_validate(yaml.safe_load(Path(path).read_text()))


def license_floor(licenses: list[str]) -> str:
    top = max(LICENSE_RANK[x] for x in licenses)
    return "+".join(sorted({x for x in licenses if LICENSE_RANK[x] == top}))


def _field_errors(e: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in err['loc']) or 'card'}: {err['msg']}" for err in e.errors()]


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

    errors += [f"aoi: {p}" for p in polygon_problems(card.aoi.polygons())]
    warnings.append("aoi: footprint intersection not checked yet (TODO: needs the STAC fixture, P4)")

    licenses = []
    for i, src in enumerate(card.data_allowlist):
        where = f"data_allowlist.{i}"
        licenses.append(src.license)
        if src.status == "pinned":
            if not src.fixture_path or not (root / src.fixture_path).exists():
                errors.append(f"{where}.fixture_path: pinned source has no fixture on disk")
            missing = [x for x in src.item_ids if x not in src.etags]
            if missing or not src.item_ids:
                errors.append(f"{where}.etags: pinned items need an ETag each (missing: {len(missing)})")
        else:
            warnings.append(f"{where}: source {src.source_id} is {src.status}")

    for i, step in enumerate(card.steps):
        k, where = step.keying, f"steps.{i}.keying"
        if k.mode == "unkeyed":
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
        elif not key.exists():
            warnings.append(f"{where}.key_path: key file {k.key_path} not present on disk")

    unknown = sorted({x for x in licenses if x not in LICENSE_RANK})
    if unknown:
        errors.append(f"license: unknown licence id(s) {', '.join(unknown)}; add them to LICENSE_RANK")
    else:
        report.license_floor = license_floor(licenses)
    report.card_hash = card.card_hash()
    return report
