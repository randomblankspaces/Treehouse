"""Bounded public data preparation only; no imagery, AWS, models or project code."""
import csv
import hashlib
import io
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ITEM = "https://www.sciencebase.gov/catalog/item/6671c479d34e84915adb7536?format=json"
SOURCE_NAME = "uspvdb_v4_0_20260414.csv"


def fetch(url, cap):
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read(cap + 1)
    if len(raw) > cap:
        raise ValueError("response exceeded bounded acquisition cap")
    return raw


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


item = json.loads(fetch(ITEM, 100_000))
source = next(f for f in item["files"] if f["name"] == SOURCE_NAME)
raw = fetch(source["url"], 1_300_000)
assert len(raw) == source["size"]
assert hashlib.md5(raw).hexdigest() == source["checksum"]["value"]
reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
fieldnames = reader.fieldnames
rows = list(reader)
eligible = [r for r in rows if r["p_state"] == "VA"
            and r["p_sys_type"] == "ground" and r["p_year"]
            and int(r["p_year"]) <= 2023 and float(r["p_area"]) >= 10000]
eligible.sort(key=lambda r: int(r["case_id"]))
# Longitude bands have an unused 0.4 degree buffer. No facility crosses splits
# because all records for one stable case_id belong to a single band.
splits = {
    "public-reference-examples": [r for r in eligible if float(r["xlong"]) <= -78.2][:12],
    "heldout-grading": [r for r in eligible if float(r["xlong"]) >= -77.8][:12],
}
selected = []
for name, subset in splits.items():
    assert len(subset) == 12
    features = [{"id": "uspvdb:" + r["case_id"], "lon": float(r["xlong"]),
                 "lat": float(r["ylat"]), "cls": "solar_farm"} for r in subset]
    write_json(ROOT / name / "features.json", features)
    selected.extend(subset)
assert len({r["case_id"] for r in selected}) == 24
audit = ROOT / "audit-do-not-expose-to-model"
audit.mkdir(exist_ok=True)
with (audit / "selected-source-rows.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(selected)
provenance = {
    "dataset": "United States Large-Scale Solar Photovoltaic Database",
    "version": "4.0", "source_filename": SOURCE_NAME,
    "file_version_date": "2026-04-14", "file_uploaded": source["dateUploaded"],
    "retrieved_date": "2026-11-04", "doi": "https://doi.org/10.5066/P9IA3TUS",
    "official_release_page": "https://www.usgs.gov/data/united-states-large-scale-solar-photovoltaic-database-ver-40-april-2026",
    "sciencebase_item": ITEM, "source_url": source["url"],
    "license": "CC0-1.0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
    "attribution": item["citation"],
    "full_csv_bytes": len(raw), "full_csv_sha256": hashlib.sha256(raw).hexdigest(),
    "full_csv_md5_verified_against_publisher": source["checksum"],
    "source_row_count": len(rows), "eligible_va_row_count": len(eligible),
    "selection": "p_state=VA; p_sys_type=ground; p_year<=2023; p_area>=10000 m2; ascending numeric case_id; first 12 per longitude band",
    "split": {"public-reference-examples": "xlong<=-78.2", "heldout-grading": "xlong>=-77.8"},
    "split_unit": "stable USPVDB case_id and disjoint longitude bands with 0.4 degree buffer",
    "normalization": "case_id prefixed uspvdb:; xlong->lon, ylat->lat, cls=solar_farm; omit status because source has no observation-date status",
    "coordinate_system": "geographic longitude/latitude decimal degrees as supplied; no projection or geometry conversion",
    "purpose": "independent public reference adapter and evaluator validation; not imagery detection accuracy",
    "limitations": [
        "Non-exhaustive 24-facility selection, not a complete Virginia or task AOI inventory; no absence labels.",
        "CSV locations only: no array polygons, point-in-facility guarantee, or polygon clipping. Do not replace polygon answer key with these points.",
        "Installation year <=2023 avoids unknown installation month in 2024 but does not establish June-2024 image visibility or operational status.",
        "USPVDB contains digitized, imagery-verified records, not field-verified physical measurements; confidence differs by row.",
        "Release title says April 2026; filename 20260414 and upload 2026-04-16 are frozen. ScienceBase child revision metadata inconsistently says 2025; do not silently harmonize.",
        "The source's current website/data mirror eerscmap.usgs.gov failed DNS in this environment; official ScienceBase DOI download succeeded.",
        "Real imagery classification, source pixel access, leakage isolation and live Kiro evaluation remain separate required work.",
    ],
    "model_visibility": "Only public-reference-examples may be model-visible. Deny heldout-grading, audit-do-not-expose-to-model and source/USPVDB lookup during grading. File separation alone is not access control.",
}
write_json(ROOT / "provenance.json", provenance)
hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(ROOT.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"}
write_json(ROOT / "SHA256SUMS.json", hashes)
print(json.dumps({"counts": {k: len(v) for k,v in splits.items()},
                  "full_csv_sha256": provenance["full_csv_sha256"],
                  "persistent_bytes": sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file())}))
