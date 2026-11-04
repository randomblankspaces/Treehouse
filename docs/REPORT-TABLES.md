# LGND / ADB inception report — table digest for builders

> **For agents:** a paraphrased digest of the tables in *Evals Inception and Discovery Report — Geospatial
> AI for asset datasets* (Ode with LGND AI for ADB, draft V1, Oct 2026; 30 pages). The PDF is not in the
> repo. Fuller reading notes: [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md). Everything here is a
> **claim of the report**, not something Treehouse has measured. Tables 2–3 (consultancy deliverables and
> questions for ADB) are out of scope (Suhas, 2026-11-04).

## Table 4 — risks that decide what data we may use

| Risk | Impact | Mitigation the report proposes |
|---|---|---|
| Few complete reference sets in ADB countries | High | Hand-label small complete test blocks; where recall is undefined, report precision only |
| Licences for commercial use | High | Prefer CC BY, MIT, public domain and hand labels. Needs permission: PCRAFI and Pacific Data Hub layers, SPREP portals, DPWH road/bridge inventory, **Maxar Open Data**, commercial sharp imagery (Maxar/Vantor, Planet, Airbus), ADB-held data, GRADE/Fathom/GEM, YOLO and FarSLIP model licences |
| Very-high-res imagery needed for small assets | Medium | Run embedding workflows on free 10 m data where assets are big enough; detector baseline only where sharp imagery exists (GSI Japan, OpenAerialMap) or on small purchased blocks |
| Small or rare assets give wide intervals | Medium | Report intervals; enlarge test blocks |

## Table 17 — imagery: may we reuse it?

| Imagery | Resolution | Reuse | Role |
|---|---|---|---|
| Sentinel-2 / AEF embeddings | 10 m | **Yes (open)** | Embedding workflows anywhere; too coarse for small substations and lines |
| GSI seamless aerial (Japan) | 0.5 m | **Yes, with attribution** | Nagoya labels and detector baseline |
| Esri World Imagery | sub-metre, varies | View only; check terms before publishing traced labels | Background for hand labelling |
| Maxar Open Data (= Vantor) | sub-metre | **No** — CC BY-NC 4.0 | Not usable for ADB datasets |
| Purchased sharp imagery | 0.3–0.5 m | Per licence | Small test blocks only (no purchase is authorised for Treehouse) |

Excluded reference/benchmark datasets: DOTA, DIOR, fMoW, xView (academic/non-commercial).

## Table 5 — ADB users and the decision the data informs (use cases)

| User | Decision | What makes the data trustworthy |
|---|---|---|
| Disaster risk finance (sovereign loans, contingent finance, APDRF) | How much to allocate after an event; loan/fund size; sector priority | Checkable against reliable records; clear sources and uncertainty |
| Post-disaster needs assessment (PDNA) | How many assets damaged per sector, and repair cost | Assets counted one by one; unit cost per asset; repeatable method |
| Disaster Risk Analytics Explorer | Where resilience investment goes (pilot: Cook Islands, Tonga, Vanuatu) | Data under 3 years old; clear licence and provenance |
| Project and sector teams (energy, transport, digital) | Baselines and monitoring for funded assets | Coverage of the assets ADB funds where it invests |

§4.2 requirements on any benchmark: accuracy **per asset class**; performance in **new geographies** reported separately; whether **uncertainty is stated and calibrated**; **effort** to build the dataset (labels, analyst review); **monetary cost** (imagery, storage, compute); **sources and licences** recorded; **reproducible**.

## Table 6 — the analyst tasks

| # | Analyst question | Task | Treehouse MVP |
|---|---|---|---|
| **T1** | Where are all the assets of this type here? | Locate every asset of a class in an area (inventory) | **MVP core: retrieval** |
| T2 | How big is each asset / which size class? | Outline, measure, grade assets in screened cells (retrieval + segmentation) | aim |
| T3 | Which records are missing, misplaced or out of date? | Check and update an existing register | aim |
| T4 | How many assets were affected by the event? | Flag and count affected assets (change detection) | aim |
| **T5** | Does a workflow transfer to another place? | Re-run a workflow for the same asset elsewhere | **MVP: Nagoya → Gifu** |

## Table 7 — six components fixed before results are examined (what analysts accept as success)

| Component | Default | Varies by use case |
|---|---|---|
| Reference data | Official register or hand-labelled set, with completeness class and licence recorded | Dated records for updates |
| Unit of evaluation | The asset (one warehouse, tank, bridge); models predict on **160 m grid cells** or image chips | Floor area / value per site; cell or district |
| Matching rule | An asset is **found when any flagged cell touches it**; each asset counts once whatever its size | Box IoU ≥ 0.5 for detectors; date match for updates |
| Scoring | Recall, precision, lift, count ratio, AUROC, AP; per hazard zone or district | — |
| Labelling cost | Expert reviews top 20 cells per round, classifier refits; scored at 0–1,000 labels, 5 seeds | One fixed label set for a supervised baseline |
| Transfer test | Train in one city, test another with **no new labels** | Country to country; before/after event; coastal/inland |

## Table 8 — what counts as the asset (taxonomy)

| Asset | Positive | Negative / excluded | Reference data |
|---|---|---|---|
| **Warehouses** | Warehouses and large logistics/storage buildings (Nagoya: PLATEAU warehouse use, ≥ 1,600 m²) | Factories, markets, hangars, other large roofs | OSM; PLATEAU 3D city model (Japan) |
| Oil/fuel tanks | Above-ground oil/fuel tanks, fixed and floating roof | Water, chemical, LNG/LPG spheres; demolished bases | Hand labels |
| Bridges | Road, rail, pedestrian bridges and flyovers ≥ 10 m | Culverts, spans < 10 m | OSM; camera-imagery coordinates |
| Energy infrastructure | Fenced substations/switchyards, HV lines and towers, ground solar, wind turbines | Distribution poles, small transformers, rooftop solar, greenhouses | OSM power=*; PCRAFI (Pacific) |

## Table 9 — workflow steps an agent may choose among (none is mandatory)

| Step | Approaches | Tasks |
|---|---|---|
| Embeddings | Split AOI imagery into cells; a GeoFM embeds each. **Record imagery source, date, resolution, cell size** | T1–T4 |
| Retrieval | **Zero-shot text** (FarSLIP, Clay text search); **few-shot** examples; **concept vector** learned from labels | T1–T4 |
| Labelling | **AI-guided** (most uncertain / most likely cells, reviewed by a VLM or rules); **hand labelling** to update the model | T1–T4 |
| Classification | **Linear probe (logistic regression) or linear SVM** trained in the training location, applied to the test location | T1, T3 |
| Segmentation | Promptable segmenter outlines each object in screened tiles | T2 |
| Change search | Compare pre/post embeddings, seeded by text or examples | T4 |
| Aggregation | Cutoff on the ranked list, **merge neighbouring positive cells into sites**, estimate positives among unreviewed cells, **report a count with a range** | T1–T4 |
| Baseline (optional) | Standard detector (e.g. YOLO) | T1–T4 |

## Table 10 — transfer levels

Within the same city · cross-city, same country · across countries.

## Table 11 — metrics and what they tell an analyst

| Metric | Meaning |
|---|---|
| Site recall | Share of known assets reached by the flagged locations |
| Site recall@k | Share of known assets found in the top k reviewed locations (fair when workflows flag different numbers) |
| Grid-cell precision | Share of flagged locations that contain the asset (wasted review) |
| Lift | How much more likely a flagged location holds the asset than a random one |
| Count ratio | Implied asset count ÷ known count (read with recall and precision) |
| AUROC | Ranking quality across thresholds (not detection accuracy, not calibration) |
| Review effort | Locations to inspect to reach 50 / 80 / 90 % of assets |
| Transfer gap | Score at home minus score in the new place, same model |

**§5.8 Agentic GeoAI evaluation** (the report leaves this uncommitted — it is Treehouse's job): how the agent **plans** its workflow; whether its searches **cover the area and period** asked; whether it **uses tools correctly**; whether its answer is **consistent with the evidence and honest about limits**; how it **combines imagery with web sources**; how **efficiently** it reaches an answer.

## Table 12 — foundation models (resources the agent may use)

| Model | Sees | Brings | Limits | Licence |
|---|---|---|---|---|
| AlphaEarth Foundations (AEF, Google) | Precomputed annual embeddings, 64 numbers per 10 m pixel (S1/S2/Landsat…) | Free, global, nothing to compute; learns from a plain coordinate list; cheapest at country scale | 10 m blurs small assets; **no text search**; tends to learn the setting (port, industry) more than the object | CC BY 4.0 |
| Clay (LGND) | Sentinel-2 and sharp aerial | Works at affordable resolution; reached 95 % of best warehouse score with ~120 labels | **Must be computed per area**; sharp imagery may need buying | Apache-2.0 |
| FarSLIP | Sharp imagery, vision-language | Text search with no labels | Prompts fixed in advance; confuses rail yards, quays | Confirm per checkpoint |
| YOLO11n baseline | 0.5–0.6 m RGB tiles | Standard detector; finds objects and size | Needs sharp imagery and boxes | AGPL-3.0 |

Note for Treehouse: the precomputed **LGND Clay index on source.coop uses 1.28 km / 2.56 km cells** on Sentinel-2 — far coarser than the report's 160 m cells. It is still a legitimate resource; choosing it for warehouses without justification is a reasoning error.

## Worked results the report gives (anchors, not our scores)

Warehouses, Nagoya (403 PLATEAU warehouses ≥ 1,600 m²) and Gifu (63), 160 m cells: all-label site recall in Nagoya 77 / 78 / 80 % (AEF / Clay / FarSLIP); the unchanged Nagoya-trained models reach 37 / 35 / 44 % in Gifu (transfer gap). Zero-shot site recall@k: 59 / 59 % Nagoya, 51 / 48 % Gifu (Clay / FarSLIP). Failure modes: smaller warehouses and industrial look-alikes.
