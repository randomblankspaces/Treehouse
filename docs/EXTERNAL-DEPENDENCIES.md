# External Dependencies — Clay Earth Dataset Foundry hackathon

> **New report context, November 4:** read [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md) before
> selecting benchmark models, imagery or reference data. Table 17 distinguishes open embeddings,
> attribution-required GSI imagery, view-only Esri imagery and noncommercial Maxar data excluded by
> the report from ADB datasets. Existing demo access does not establish ADB reuse rights. Reference
> completeness, asset definitions and licenses differ by source/extent; source claims require
> verification for the intended use. FarSLIP's checkpoint license and some register access/terms are
> unresolved. The minimal Strands/GeoFM pipeline is confirmed; no new dependency, purchase or cloud
> call was added by this documentation update. The historical link checks below were not repeated as part of the PDF reading.

> **For agents — what this file is:** Every outside resource: MCP servers, datasets, answer keys, platform and stack. Each has a link, access path, license, MVP/stretch tag, and a link check from 2026-11-03. Access facts and licences were updated on 2026-11-04 from the two designs ([design/SYSTEM-DESIGN.md](design/SYSTEM-DESIGN.md) A4 and fact-check pass 2; [design/IMPLEMENTATION-DESIGN.md](design/IMPLEMENTATION-DESIGN.md) fact-check of r3) and HANDOFF.md. Only reference/geomcp-catalog.csv and the Vantor STAC metadata fixture are committed; the source PDFs and all imagery pixels are kept out of the repo.

All links below were checked on **2026-11-03**. The status column shows the result. "Build container" means the overnight agent's container (no AWS credentials, proxied network), checked 2026-11-04. Links added on 2026-11-04 (the USPVDB V4.0 release) come from the SD fact-check's search results and were not link-checked.
Source documents: the PDFs and their text copies are kept out of the repo by `.gitignore` (the AWS guide is marked Amazon Confidential). Ask the team for a copy. Only the catalog CSV is committed:

| Local file | What it is |
|---|---|
| Clay vision doc (not in repo) | Clay vision doc: business context, the tasks (it says three but defines two), MVP scope, technical environment |
| AWS event guide (not in repo, Amazon Confidential) | AWS Breaking Barriers DC event guide: venues, agenda, sandbox rules, judging |
| [reference/geomcp-catalog.csv](reference/geomcp-catalog.csv) | Snapshot of Clay's geoMCP catalog sheet (first tab, 15 servers). Exported 2026-11-03 |

**Use** column: **MVP** = needed for the ADB eval. **Stretch** = only for the later caption task. **Not used** = recorded so nobody adopts it by mistake.

---

## 1. Agent tooling (MCP)

| Dependency | Link | Access / install | License | Use | Status |
|---|---|---|---|---|---|
| RODA MCP server (AWS Registry of Open Data) | [Announcement blog](https://aws.amazon.com/blogs/opensource/introducing-mcp-server-for-registry-of-open-data-on-aws/) · [PyPI](https://pypi.org/project/awslabs.roda-mcp-server/) · [Source (awslabs/mcp)](https://github.com/awslabs/mcp) | `uvx awslabs.roda-mcp-server@latest` | Apache-2.0 | Optional (F1): Clay's Day-1 starting tool; Treehouse's own servers replace it in the demo | Links OK. Install not tested yet |
| Clay geoMCP catalog (about 99 servers; free/priority shortlist to come from Clay) | [Google Sheet](https://docs.google.com/spreadsheets/d/1cMoPxhNTzNHuWEAK_PtAgFUqEMxQ1AyoZxMCzfdkYzQ/edit?usp=sharing) | Public. CSV export: `…/export?format=csv` | Varies per server | Optional (F1): pick 1–2 alongside RODA | OK. First tab saved locally |
| LGND Geo MCP server | [lgnd.ai/geo](https://lgnd.ai/geo) | Commercial. Hackathon teams get whitelisted | Commercial | MVP (optional) | Page OK. **Confirm our access with Clay** |
| Treehouse's own tool servers (`stac`, `imagery`, `clay`, `claims`, `decoy`) | this repo, `src/treehouse/tools/` | In-process `MCPServer`s behind the tool gateway (ID §3) | Apache-2.0 | **MVP**: the agent's tools in the demo | Being built (P4) |

Shortlist candidates from the saved catalog tab (all "active" and "Open"): `stac-mcp` (remote sensing catalog), `earthdata-mcp` (official, remote sensing), `GeoLens MCP` (official, data catalogs), `gis-mcp` (98 tools, GIS toolkit), `openstreetmap-mcp-server`, `Overture Maps MCP`. Clay has the final say on the shortlist. `openstreetmap-mcp-server` and `Overture Maps MCP` must be **forbidden** on any task where OSM is the answer key (SCOPE D51).

## 2. Input data

| Dependency | Link | Access | License | Use | Status |
|---|---|---|---|---|---|
| NAIP aerial imagery (0.3–1 m, 4-band, US) | [Registry of Open Data](https://registry.opendata.aws/naip/) | `s3://naip-analytic` (MRF), `s3://naip-source` (GeoTIFF), `s3://naip-visualization` (RGB COG), plus legacy `aws-naip` (us-east-1). **Requester Pays, us-west-2**: signed requests with AWS credentials and `RequestPayer=requester`; unsigned range reads fail; egress outside us-west-2 is charged. Coverage about 2010–2023 | Public domain (USDA); cite "NAIP on AWS" | MVP (Virginia keyed demo, live via Kiro only) | Link OK. Verified Requester Pays (SD fact-check pass 2). Not readable from the build container |
| Vantor open data (disaster-event imagery; Nepal flood event) | [Registry of Open Data](https://registry.opendata.aws/vantor-open-data/) | `s3://vantor-opendata/events/Nepal-Flooding-Aug-2026/`, us-east-1. Anonymous listing and HTTPS range reads work, **including from the build container**. Cloud-Optimized GeoTIFFs: EPSG:4326, 3-band JPEG, 512 px tiles, about 0.34 m pixels (measured on E5610). STAC items carry `phase`, `eo:cloud_cover` (scene-level only, **no cloud mask**), `pan_gsd`, `view:off_nadir`, `view:sun_*`. 33 scenes: 4 pre, 29 post. A 300 m window takes 5 range requests and about 80 KB with a 16 KB block cache | **CC-BY-NC-4.0** (non-commercial; attribution). No pixels in the repo, traces or demo recording; NC notice on derived views | **MVP**: flagship imagery | OK. Fixture: `wip/fixtures/nepal-flooding-aug-2026.stac.json` (metadata only) |
| LGND / Clay embeddings | [source.coop/clay/lgnd-embeddings](https://source.coop/clay/lgnd-embeddings) | HTTPS / S3-compatible via Source Cooperative, us-west-2. Clay v1.5 over Sentinel-2, Jan 2017 to Apr 2026, one 256-d vector per 1.28 km cell per month. **data.source.coop is blocked from the build container**; the demo uses a synthetic npz | **CC BY 4.0** (attribution required; checked 2026-11-03) | **MVP (narrowing only)**: `clay_search` ranks candidate cells and reports its coverage; it can't see footbridges and predates the Aug 2026 flood (review-1 judge C4, SCOPE D59) | OK from the Mac; blocked from the build container |
| SkyScript (large, semantically diverse vision-language dataset for remote sensing) | [GitHub](https://github.com/wangzhecheng/skyscript) | GitHub | Check repo | Stretch (captions) | OK |
| MegaEarth (Sentinel-2 windows + OSM labels, 485 classes in families, split by geography; tests transfer to unseen categories) | [Hugging Face](https://huggingface.co/datasets/Mead0w1ark/megaearth-osm-sentinel2) | Hugging Face dataset | Check dataset card | Stretch | OK |
| ADB task input data (and rubric) | — | **Inputs not coming** (SCOPE D13). Rubric unconfirmed. We generate synthetic tasks with task references built from the public data above (D19) | — | **MVP** | **Team generates** |

## 3. Reference / answer-key data

Global Renewables Watch is a stretch / fallback key. USPVDB and OSM are MVP keys for the ADB eval (Virginia, Nepal inventory) and also serve the caption-task retrieval stretch.

| Dependency | Link | License | Status |
|---|---|---|---|
| Global Renewables Watch v1.0 (solar and wind worldwide) | [GitHub release](https://github.com/microsoft/global-renewables-watch/releases/tag/v1.0) | MIT | OK |
| USGS USPVDB (US solar) | [eerscmap.usgs.gov/uspvdb](https://eerscmap.usgs.gov/uspvdb/) · [V4.0 data release](https://www.usgs.gov/data/united-states-large-scale-solar-photovoltaic-database-ver-40-april-2026) | **Public domain** (CC0-1.0; attribution requested). Current release **V4.0, 2026-04-15** (6,611 facilities). **MVP**: Virginia answer key | Unreachable from the dev machine on 2026-11-03 and **blocked from the build container** on 2026-11-04. `scripts/fetch_uspvdb.py` runs on Suhas's Mac (K6); the Virginia card ships `pending_fetch` |
| USGS USWTDB (US wind) | [eerscmap.usgs.gov/uswtdb](https://eerscmap.usgs.gov/uswtdb/) | Public domain | Same as USPVDB: retry from the venue |
| OpenStreetMap | [openstreetmap.org](https://www.openstreetmap.org) | ODbL. **MVP**: partial key for the Nepal inventory step (forbidden to the agent on that step). Keep OSM-derived keys in their own directory | OK. overpass-api.de is **blocked from the build container**; `fetch_osm_bridges.py` runs via Kiro or the Mac (K6), snapshot date pinned |
| xBD (building damage) | [arXiv 1911.09296](https://arxiv.org/abs/1911.09296) | **CC BY-NC-SA 4.0** (non-commercial, share-alike). **Not used**: different object class and licence (SD A7) | — |

## 4. Auxiliary caption datasets (stretch: check each license before use)

| Dataset | Task type | Link | Notes | Status |
|---|---|---|---|---|
| LEVIR-CC | Change | [GitHub](https://github.com/Chen-Yang-Liu/LEVIR-CC-Dataset) | Change captioning and detection | OK |
| Change-Agent | Change | [GitHub](https://github.com/Chen-Yang-Liu/Change-Agent) | Adds change masks | OK |
| SECOND-CC | Change | [GitHub](https://github.com/ChangeCapsInRS/SecondCC) | Change captioning | OK |
| RSCC | Change | [GitHub](https://github.com/Bili-Sakura/RSCC) | Larger set. Possibly only a small human-labeled subset; score only against that subset | OK |
| VRSBench | Fixed | [GitHub](https://github.com/lx709/VRSBench) | Single-image descriptions | OK |
| RSICD_optimal | Fixed | [GitHub](https://github.com/201528014227051/RSICD_optimal) | Single-image captions | OK |

## 5. Platform and event

| Dependency | Detail |
|---|---|
| AWS sandbox (Workshop Studio) | Provisioned by the team lead. **$500 spend cap.** Wiped after the event, so keep everything in the repo |
| Amazon Bedrock | Worker, verifier and (later) summarizer models, behind our `ModelProvider`. Access confirmed (D40). Default worker `anthropic.claude-sonnet-5-5` (called through a `us.`/`eu.`/`global.` inference profile; the bare id reportedly fails) and verifier `amazon.nova-pro-v1:0` (`us.`/`eu.`/`apac.` profiles; image input via Converse). **Both UNVERIFIED until the K1 probe** (ID fact-check U1, U2) |
| Kiro web IDE | The only way to reach the Workshop Studio account (D30). Runs the AWS steps K0–K9 from prompts in `TODO.md` |
| Public GitHub repo | Created at kickoff (per source). Required before judging. Open source (Apache-2.0, to match Clay), with infrastructure as code where it applies |
| Event contact | breaking-barriers-us-2026@amazon.com |
| Expected stack (Clay's doc) | Python 3.12+, boto3, an MCP SDK, an agent framework (any, kept swappable), an OpenTelemetry-style tracer (swappable), FastAPI for the thin API, scikit-learn/numpy for metrics, and optionally a TS/Node 20+ thin UI. Geospatial stack: rasterio / GDAL / xarray / pystac. Permitted extras: SQL (lightweight trace/metadata store) and Bash (sandbox scripting) |
| Pinned stack (ID §1, fact-checked 2026-11-04) | Python 3.12+ (3.13 in the build container), `uv`. Core: pydantic, pyyaml, numpy (2.5 checked; pinned by `uv.lock`), scipy (1.18), typer, httpx and **mcp 2.3** (`>=2.3,<3`; `from mcp.server.mcpserver import MCPServer`, in-process `mcp.client.client.Client`). Extras: `aws` = boto3 (botocore 1.43); `strands` = **strands-agents 1.63** (`>=1.63,<2`; custom `strands.models.model.Model`, `SequentialToolExecutor`); `geo` = rasterio 1.5.2 (macOS wheels need macOS 15); `api` = fastapi, uvicorn. Dev: pytest, ruff, hypothesis, moto 5.2.5 (from W5). No shapely or pyproj at runtime |
| Deployment model | Flexible (serverless, containers or K8s) in a single sandbox account |
