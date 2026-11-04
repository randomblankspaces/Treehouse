# Frozen public USPVDB reference subset

This is **real public labeled facility data**, not synthetic coordinates. The 24 points are a deliberately small, non-exhaustive Virginia sample from USGS/LBNL USPVDB v4.0. Solar farms fit Treehouse's existing solar task and a general geospatial retrieval example; a warehouse scenario is not required or assumed.

- `public-reference-examples/features.json`: 12 western Virginia examples, permitted as reference/model input.
- `heldout-grading/features.json`: 12 eastern Virginia labels, evaluator only.
- `audit-do-not-expose-to-model/selected-source-rows.csv`: exact parsed source field values for all selected records; evaluator/audit only.
- `provenance.json`: frozen source URL, license, attribution, selection, dates and limitations.
- `prepare_subset.py`: bounded acquisition and deterministic data preparation; no application code.
- `SHA256SUMS.json`: SHA-256 digest of each other artifact.

The splits use unique stable facility IDs and longitude bands separated by a 0.4-degree unused buffer. All selected features retain source longitude and latitude directly. Every row has `cls=solar_farm`; `status` is omitted because the CSV does not establish observation-date visibility. Do not invent negative/absent examples from omitted facilities. Keep heldout labels, audit rows and USPVDB lookups outside worker/model inputs and tool access. Separate files alone do not enforce that restriction.

The official CSV was read in memory with a 1,300,000-byte cap (actual 1,219,202 bytes), and its publisher MD5 verified. Only this small subset and provenance persist. No pixels, paid requests, credentials, AWS or requester-pays resources were used. The official `eerscmap.usgs.gov` endpoint failed DNS; the DOI-resolved official ScienceBase download succeeded, so a fallback dataset was unnecessary.

The [USGS release page](https://www.usgs.gov/data/united-states-large-scale-solar-photovoltaic-database-ver-40-april-2026) marks the work [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/). Attribution is retained in `provenance.json`; [ScienceBase](https://www.sciencebase.gov/catalog/item/6671c479d34e84915adb7536) identifies the versioned source and explains that records were digitized and reviewed from imagery rather than field verified. These are statements from the data publisher, not independent physical measurements.

Coverage and date limits: the source contains 6,611 national records; 92 Virginia records satisfy this preparation's ground-system, >=1 ha and installation-year <=2023 filters. This fixture selects only 24 of those. It is not a complete AOI answer key and does not implement polygon clipping. The existing task asks about June 2024 imagery; the conservative <=2023 filter avoids unknown installation month in 2024 but does not prove image visibility or status. Source imagery dates differ by row. Release filename is dated 2026-04-14 and uploaded 2026-04-16; release title says April 2026, while a ScienceBase child revision field inconsistently says 2025. Those values are preserved rather than reconciled by inference.

Pass/fail checks for this artifact: publisher checksum matches; 12 records per split; IDs and source facility IDs disjoint; coordinates exactly equal selected CSV values and lie within valid geographic ranges; band buffer respected; all artifact hashes match; total output <100 KB. Passing only validates reference ingestion and evaluator mechanics. Scoring supplied labels against themselves is not detection accuracy. Independent real imagery classification and the live Kiro run remain untested.

Repository formatting: the audit CSV uses LF line endings; parsed source field values and the full-source CSV checksum remain unchanged.
