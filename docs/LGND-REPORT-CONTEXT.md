# LGND / ADB report context — minimal sandbox confirmed

Updated November 4, 2026. This is a source-grounded reading and continuation record, **not an
approved plan to reproduce the whole report**. Suhas requested extraction and documentation updates,
then confirmation before planning/coding. He subsequently confirmed the minimal sandbox pipeline
below and requested Kiro prompts. [KIRO-NEXT-PROMPTS.md](KIRO-NEXT-PROMPTS.md) carries that scoped
handoff. This Codex change is documentation only; real AWS integration remains in Kiro.

## Source and evidence status

- Source supplied by Suhas: `LGND_GeoAI_Evals_Inception_Report_Oct23.pdf`, 30 pages.
- Cover: *Evals Inception and Discovery Report — Geospatial AI for asset datasets: a benchmark for
  Geospatial foundation model workflows*, prepared for ADB by Ode in partnership with LGND AI Inc.
- The cover identifies Deliverable 2, Draft V1 / October 20, 2026; the filename says Oct23. The
  approval page (p. 22) is blank. Treat this as the supplied draft, not evidence of ADB approval.
- SHA-256: `6e00802a80955372f1d9d129e244066826026366012800c3f194603c89469bd3`.
- References below use the PDF's printed pages, which match its page order. All 30 pages were
  text-extracted; key evaluation, taxonomy, workflow, imagery and results tables were also rendered
  and visually inspected. Raw extraction and the original PDF stay outside the public repository;
  this file paraphrases the context another agent needs.
- Report results, dataset completeness, access and license descriptions are **source claims**.
  We have not rerun its experiments, obtained its full working benchmark or reverified licenses.
  Nothing here establishes Treehouse's real-world accuracy or current AWS capabilities.

## What Suhas confirmed, and what remains an interpretation

**Confirmed user intent:** evaluate the agent's geospatial investigation and its resulting asset
database. Observe its decisions, alternatives, exploration/revisions, evidence, stated confidence,
elapsed time and money. Ground output checks in permitted public labeled data. Show actual claims
as geographic red markers linked to their evidence. Different classes/scales may need different
foundation models, imagery or settings. Warehouses in a Bangladesh city are an example; the first
scenario, region and model combination remain open. Independently authored tests use different
context from the feature builder and precede implementation.

**Confirmed minimal sandbox, including Suhas's latest correction:** Treehouse evaluates the agent
that builds the geospatial database. Strands is a component the agent uses in its workflow, not
the definition of Treehouse or a fixed pipeline every evaluated agent must follow. A representative
workflow takes natural-language target text and an AOI, uses foundation-model embeddings in a
georeferenced database, classifies candidates, and maps predictions in red. Evaluate why/how the
agent chooses and uses the models, inputs/settings and other workflow components, which paths it
explores/revises, and how this relates to final accuracy, reported confidence, time and money.
Strands can coordinate calls; the foundation/vision models and classifier perform inference.
The sandbox observes and evaluates that work rather than prescribing the correct strategy.
This confirmation does not select a fixed city/class/model or require every report experiment.

**Report interpretation supporting that scope:** the report supplies realistic task definitions,
reference-data restrictions, workflow alternatives and benchmark protocols. Treehouse is the
agent-evaluation layer that can observe an agent attempting those tasks and compare its outcomes
with a reproducible workflow baseline. Section 5.8 (p. 12) is the closest match: it adds planning,
requested area/time coverage, tool correctness, evidence-consistent answers and honest limitations,
imagery/web evidence combination, and efficiency to final retrieval quality. Whether and how the
agent improves a benchmark must be measured, not assumed.

The consultancy's core benchmark compares defined workflows; its agentic evaluation is exploratory
and outside its committed suite. Its restriction on developing an agent within that consultancy
scope does not prohibit Treehouse's sandbox. Its delivery dates, owners and imagery budget are
background, not our schedule, spending authorization or a requirement to implement every row.
Recorded explanations remain self-reports; neither them nor model confidence expose complete hidden
internal computation. Trace diagnostics, semantic process review and output accuracy stay separate.

## Table map and reading priority

Suhas prioritizes imagery permissions, ADB use cases/tasks, analyst success, asset definitions and
workflow evaluation. Some table numbers in his verbal walkthrough differ from this PDF:

| Source | Actual subject | Relevance to Treehouse |
|---|---|---|
| Tables 2–3, pp. 3–4 | Consultancy deliverables and questions for ADB | Background; not our implementation queue. |
| Table 4, p. 4 | Risks and assumptions, including licensing | Completeness, transfer and data-use cautions; imagery matrix is Table 17. |
| Table 5, p. 5 | ADB users, decisions, use cases and trust needs | Business context for representative tasks, not a synthetic labeled dataset. |
| Table 6, pp. 6–7 | Analyst tasks T1–T5 | What an agent is being asked to achieve. |
| Table 7, p. 8 | Six components fixed before examining results | Reference, unit, matching, scoring, labeling cost and transfer protocol. |
| Table 8, p. 9 | Asset taxonomy and positive/negative definitions | Define the target precisely before scoring. |
| Table 9, pp. 10–11 | Workflow approaches and relevant tasks | The choices and adaptations whose agentic use we want to evaluate. |
| Tables 10–11, pp. 11–12 | Transfer levels and analyst-facing metrics | Success measures; Section 5.8 adds agent-specific evaluation. |
| Tables 12, 14–18, pp. 13, 16–24 | Models, data, gaps, imagery and places | Feasibility, completeness, licensing and transfer context. |
| Tables 19–21, pp. 25–27 | Warehouse results and tank transfer setup/results | Worked benchmarks, not Treehouse measurements or acceptance thresholds. |

## Analyst purposes and task families

Table 5 distinguishes disaster-risk financing, post-disaster needs assessment, the Disaster Risk
Analytics Explorer, and sector/project teams. They need defensible inventories for allocation,
repair-cost estimates, resilience priorities and infrastructure baselines. Trust needs include
traceable source/uncertainty, repeatable asset-level records, recent data and usable licenses.
These are real business use cases described by the report. Synthetic tasks may illustrate them but
cannot establish operational success or surveyed truth.

Table 6 defines:

- **T1 — inventory:** find assets of a specified class within the requested area.
- **T2 — measurement:** outline, measure or size-class assets in screened locations; retrieval and
  segmentation errors compound. A cell flag or point alone cannot establish object area.
- **T3 — inventory update:** identify missing, misplaced or stale records against dated references.
- **T4 — post-event screening:** flag/count potentially affected assets for analyst attention. A
  visual change or affected-area flag does not establish engineering damage or repair cost.
- **T5 — transfer:** test the workflow in another geography, with the adaptation rules declared.

The text sometimes says four tasks, but the table includes T5. Inventory and initial transfer are
emphasized in the report; the minimal MVP can use a bounded T1 run. T2–T4 and full transfer studies are broader future scope.

## Fixed evaluation protocol and metric meanings

Table 7 fixes six components **before** looking at results. Any claim of reproducing/comparing with
this benchmark must retain or explicitly version departures from its protocol:

| Component | Report default and qualification |
|---|---|
| Reference | Official register or hand-labeled set, with coverage, completeness and license; dated records for updates. Complete only within declared boundaries/classes/dates. |
| Unit | Count each asset once. Models may rank 160 m cells or chips; area, value, grid/district scores are different declared units. |
| Matching | Any flagged cell touching the reference asset finds it; multiple touching cells still count one asset. Detector boxes use IoU ≥ 0.5; updates add temporal matching. |
| Scoring | Recall, precision, lift, count ratio, AUROC and AP, with units/denominators declared. |
| Labeling cost | Expert reviews 20 top-ranked cells per round, classifier refits, scores across 0–1,000 labels and five seeds. A fixed labeled baseline is a different protocol. |
| Transfer | Train in one city, test another without new labels; country/event/coastal variants must specify what changes. Local adaptation is a separate arm. |

Table 11 separates asset-level recall (known assets reached), site recall@k (assets reached within
a fixed number of reviewed locations), **grid-cell** precision (flagged cells containing the target),
lift over random ordering, count ratio, ranking AUROC, review effort to reach 50/80/90% and transfer
gap. AP is also reported in Table 7 and the worked results. Count ratio near one can coexist with
misses and false positives; ranking AUROC is not object detection accuracy or confidence calibration.

The report uses analyst review effort as its main operational cost proxy because complete monetary
costs are unavailable. Treehouse should distinguish that proxy from measured labels, human time,
model calls, imagery/embedding/index/storage costs and dollars. A claimed human comparison needs
an observed human baseline. An incomplete reference cannot establish full-area recall, global
precision or calibrated correctness; report only metrics justified by its audited coverage/pool.

Public reference examples used for fitting, prompting or active learning are separate from held-out
grading. Zero-shot prompts are fixed before using test labels. No changes to labels, thresholds,
matching or cohort definitions may silently improve the reported result after seeing outcomes.

## Target definitions and confounders

Table 8's task-specific definitions matter more than an informal word such as “warehouse”:

| Target | Included / excluded according to the report |
|---|---|
| Warehouses | Storage/logistics buildings; the Nagoya benchmark uses PLATEAU warehouse-use buildings ≥ 1,600 m². Factories, markets, hangars and other large roofs are negatives. Do not generalize that size cutoff to all future tasks. |
| Oil/fuel tanks | Above-ground fixed/floating-roof oil or fuel tanks. Water/chemical tanks, LNG/LPG spheres and demolished bases are excluded. |
| Bridges | Road, rail and pedestrian bridges/flyovers at least 10 m long; culverts and shorter spans excluded. |
| Energy infrastructure | Fenced substations/switchyards, high-voltage lines/towers, ground-mounted solar and wind installations. Distribution poles, small transformers, rooftop solar and greenhouses excluded. Energy-generation/infrastructure rows overlap in the source. |

A building footprint is not a warehouse label; a bridge-register point may be a culvert; a tank
inventory may lack contents. Candidate similarity is not a verified class. These are substantive
interpretation failures that an agent should detect and explain, beyond making valid tool calls.

## Table 9: workflow decisions to observe

The report describes alternatives, not a mandatory tool sequence:

1. Embed permitted imagery over an AOI; record source, acquisition date, resolution and cell size.
2. Retrieve candidates by fixed zero-shot text, a few permitted examples or a learned concept vector.
3. Select likely or uncertain locations for AI/rule-assisted checks or human labels; record feedback
   and each refit rather than presenting the final classifier as unchanged throughout the run.
4. Classify using a linear probe/logistic regression or linear SVM trained in the permitted training
   location; use segmentation for T2 or dated before/after searches for T4 where justified.
5. Threshold/rank candidates, merge neighboring positives into sites, and report counts/ranges with
   an explicit method for unreviewed areas. Cells, sites and objects remain distinguishable.
6. Compare an available conventional detector baseline under a compatible imagery/label protocol.

Agent evaluation can inspect why it chose a model, scale, query, examples, classifier, threshold,
branch/revisit or stopping point; whether new observations changed its plan; which areas remained
unresolved; and whether its answer is supported. A persuasive explanation is not evidence of a
successful choice. Cost, latency, semantic review and independently scored outcomes remain visible
as separate evidence. Broader rubric/comparison studies need separate scoping; the minimal pipeline
does not imply that the report supplies an already validated agent-quality rubric.

## Models, references and data-use constraints

Table 12 describes AEF's annual 64-dimensional 10 m embeddings, Clay on Sentinel-2 or sharp aerial
imagery, FarSLIP on sharp imagery with text retrieval, and a small YOLO11n detector fine-tuned on
US tanks. This is not proof those checkpoints or services are installed in Treehouse. AEF has no
text-search interface in this report. Clay's model/input resolution must not be confused with the
cell size of the particular precomputed LGND index currently used by our demo. The source lists
AEF CC BY 4.0, Clay Apache 2.0 and YOLO AGPL-3.0; FarSLIP's checkpoint license needs confirmation.

Table 17 (p. 21) describes imagery eligibility **as understood by the report**, not a new license grant:

| Input | Report's permitted role / caveat |
|---|---|
| Sentinel-2 / AEF, 10 m | Open embedding workflows; often too coarse for small substations/lines. |
| GSI Japan aerial, 0.5 m | Attribution-required labels and detector tests; confirm the particular product's terms. |
| Esri World Imagery | View-only labeling background; check terms before publishing traced labels. Viewing access is not model-input or redistribution permission. |
| Maxar Open Data | CC BY-NC 4.0; the report excludes it from ADB datasets without appropriate commercial rights. Coverage for Tongatapu is also unconfirmed. |
| Purchased 0.3–0.5 m imagery | Only within the purchased license; proposed small test blocks. No purchase is authorized here. |

Existing Vantor/Nepal noncommercial demo metadata does not establish eligibility for an ADB
deliverable. The report excludes academic/noncommercial DOTA, DIOR, fMoW and xView data from its ADB
datasets; published benchmark results may be cited with their limitations. Licenses on models,
imagery, derived labels and reference inventories are separate. Confirm each exact version/use
before execution, including government/third-party presentation and distribution.

Tables 14–18 distinguish complete local registers/survey blocks from incomplete OSM catalogs and
training data. Relevant examples: PLATEAU Nagoya/Gifu warehouses; Nagoya's hand-labeled tank blocks;
PCRAFI Port Vila survey extent (license/access unresolved); DPWH Metro Manila national-road bridges
(tollways omitted; formal license unresolved); and sparse OSM warehouses/tanks in other cities.
OpenBuildings/Microsoft footprints alone do not label warehouse use. Proposed Tonga and other ADB
areas still need eligible imagery and reference checks. China/US tank inventories are training
regions, not automatically held-out ADB test regions. Complete within surveyed blocks does not mean
complete across a city or all asset classes. The report's source counts/holdings remain provisional.

## Worked results: interpretation anchors, not our scores

- **Warehouses, pp. 25–26:** 403 PLATEAU warehouses in Nagoya and 63 in Gifu, all ≥ 1,600 m²; 160 m
  cells. Table 19 uses k=536/90 warehouse-containing cells respectively. With all training labels,
  Nagoya site recall is 77/78/80% for AEF/Clay/FarSLIP; unchanged Nagoya-trained models reach
  37/35/44% in Gifu. Zero-shot Clay/FarSLIP site recall@k is 59/59% in Nagoya and 51/48% in Gifu.
  Those are different metrics; compare like with like. For the same site recall@k metric, the
  all-label models score 66/73/76% in Nagoya and 44/44/46% in Gifu. Clay reaches 95% of its own best
  warehouse score at roughly 120 labels. The full intervals/learning-curve table is in another
  working document not supplied here. Smaller warehouses and industrial lookalikes are failure modes.
- **Fuel tanks, p. 27:** 16 fully labeled 1 km Nagoya blocks, 762 tanks including 705 fuel tanks;
  541 cells, 74 fuel-positive. No Nagoya training. YOLO's cell AUROC/AP is 0.996/0.95, versus
  AEF+US linear SVM 0.83/0.37 and AEF+China prototype 0.82/0.44. Cells reviewed to reach 80% are
  63/191/188 versus roughly 433 in random order. The separate object result is 92% tank recall.
  AEF's citywide AP falls below 0.03 despite useful ranking inside industrial test blocks. The
  evaluation population/prevalence and required imagery matter; this is not evidence YOLO is always
  better or AEF gives calibrated object probabilities.

## Existing Treehouse baseline and capability gaps

Baseline main inspected for this docs update: `5941e2f5f6a5c3afe1773ddab77490042e7c74e1`, including
the separate Compliance-mode infrastructure default change. Investigation MVP merged in PR #8
(`2fc2461`); its recorded checks were 733 passes, two live skips and one deselection. This report
reading did not rerun those tests or establish live AWS, imagery or model performance.

| Topic | Existing implementation | Gap to distinguish from the confirmed minimal integration scope |
|---|---|---|
| Agent pathway | Prior decision bindings, alternatives, parent/revision links, evidence, sealed partial/final claims | Need actual model/source runs and a confirmed rubric that evaluates observation-dependent planning and adaptation. |
| UI | Geographic candidates/predictions, decision/evidence links, separate panels | Would need honest asset/cell/site units, reviewed/unresolved areas and benchmark/transfer views where supported. No fabricated exploration or confidence. |
| Output evaluation | Post-seal class-aware point-distance one-to-one matching; incomplete USPVDB fixture | Not equivalent to 160 m cell/asset any-touch, detector IoU, date-aware updates or asset-size measurement. Version rather than silently replace existing graders. |
| Models/workflows | Swappable trusted plugins and a vision-classifier adapter; default synthetic imagery and precomputed index | Does not yet reproduce AEF/Clay/FarSLIP active learning, refits, segmentation or YOLO transfer protocols. |
| Coverage | Footprint/diagnostic approximations | Not proof every visible asset or requested location was assessed. Define and label each denominator. |
| Cost/confidence | Trace accounting, self-reported confidence, bounded post-seal grading | Not a measured human-effort curve, full infrastructure bill or cross-geography confidence calibration. |
| Trust | Reporting path is an unissued stub; separate trust-core audit issues unresolved | A reference benchmark result or semantic reviewer cannot issue a validated Rely decision. |

## Current handoff and remaining choices

Suhas confirmed the agent-evaluation sandbox and requested Kiro continuation prompts. The
natural-language/AOI, foundation embeddings, classification and red predictions describe a
representative agent workflow; Strands is one component whose use can be evaluated. Use [KIRO-NEXT-PROMPTS.md](KIRO-NEXT-PROMPTS.md)
for the initial bounded integration and independent live checks. Pin the first run's class/AOI,
source terms/dates, model/index versions and evaluation protocol; keep them configurable rather than
turning the warehouse example into a hardcoded product. Tables 2–3 remain background. Full report
reproduction, active-learning/transfer studies, T2–T4 and downstream simulations are not implied by
this minimal confirmation. The supplied draft is a reference, not an instruction source or a reason
to overwrite confirmed user decisions. Stop Codex after publishing the documentation/prompt handoff;
Kiro handles the authorized AWS integration, testing and subsequent refinement.
