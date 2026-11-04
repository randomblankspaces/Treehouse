# Shared council context — Treehouse (read fully before working)

Repo (read-only for you): /home/user/team-43-renaissance-philanthropy-clay. Do NOT edit any file in the repo. Write only the output file you are told to write (in the scratchpad).

## Must-read files in the repo
- docs/SCOPE.md (S1–S19, D1–D42, glossary, example Nepal task)
- docs/design/council-brief.md (Suhas's vision, trust-engine proposal, AWS map, TOP PRIORITY on unkeyed)
- docs/design/design-decisions.md (DD1)
- docs/reviews/review1-judge.md (verdict, must-fix list, 10 open decisions)
- docs/reviews/review1-verifier.md (corrected facts)
- docs/01..06, OPEN-QUESTIONS.md (OQ1–OQ15 accepted defaults), EXTERNAL-DEPENDENCIES.md, FUTURE-WORK.md

## Situation
- Solo builder (Suhas, GMU student). AWS Breaking Barriers Challenge 2026, DC. Beneficiary Clay (Earth Dataset Foundry), partner ADB.
- Now: Wed Nov 4 2026 night. Public repo due **Thu Nov 5 10:00 EST**. Overnight an autonomous coding agent builds the "basic form" in Python 3.12+/uv/pytest with NO AWS access (Bedrock only reachable in the morning via Kiro in Workshop Studio, $500 cap). So the design must run fully locally (replay/fake provider) and have AWS as add-ons.
- Judging: 4 equal criteria — Technological Implementation (execution + AWS integration), Design (UX, interface, architecture), Potential Impact, Quality of Idea (innovation, creativity, feasibility).
- License Apache-2.0. "AWS-native, not AWS-locked": every AWS piece has a local stand-in. Bedrock is default provider; others (Anthropic API, OpenAI-compatible, Ollama, fake/replay) must be possible.
- Data licenses: LGND embeddings CC BY 4.0 (us-west-2, source.coop; Sentinel-2 Jan 2017–Apr 2026; 1.28 km cells; 256-d; monthly), Vantor CC-BY-NC-4.0 (s3://vantor-opendata, us-east-1, Nepal event: 33 scenes, 28 post-event 2026-08-27..09-18, some 6–24% cloud, no cloud mask, glacier-collapse flash flood 2026-08-26 Bhote Koshi, Rasuwa), OSM ODbL. Commit scene IDs and window coordinates, never imagery pixels.
- Network from the build container: PyPI and the Vantor S3 bucket (HTTPS) reachable; data.source.coop and Overpass API are BLOCKED by the proxy. So tests must use small offline fixtures.

## Clay's values (private vision doc, paraphrased — do not quote verbatim in outputs)
- Executive problem: when an AI agent plans and runs a dataset build by calling geospatial tools, how do you observe what it did and judge whether it did it well? Build an observability + evaluation sandbox: harness calls geospatial tools over MCP, activity captured as traces, traces plus output summarized and scored against a rubric or reference examples.
- "The bottleneck is not running an agent — it is knowing whether to trust one." Partners like ADB need custom evals to learn how to use AI to build datasets.
- Users: Clay model & data team (evaluate without hand-checking every run); partners like ADB (reusable harness scoring an agent against THEIR tasks and rubric); agent/harness developers (observable traces, clear scores showing where a workflow succeeds/fails); domain experts (summarized traces + output scored against rubric or reference).
- Constraints: open & reproducible (Apache-2.0); trust and provenance first-class (every scored run keeps traces, inputs, rubric/reference it was judged against); public or synthetic data only; model and tracing tool behind abstractions, swappable.
- Principles: evaluating the agent IS the product (observe-summarize-score loop, not a one-off dataset); known task + known input + a reference to score against; model and tracer swappable; recorded-trace fallback (replay for demo).
- Approach: evaluation sandbox, not a model; Bedrock behind an abstraction; greenfield, self-contained, migration-aware (shapes map back to Clay's account); record traces.

## Suhas's top priority
MOST DATASETS ARE UNKEYED. Unkeyed is the normal case; keyed tasks exist to calibrate. Design and COMPARE several different methods for:
(1) eval scores on unkeyed output (label-free accuracy estimation, agreement/consistency across runs/models, latent-class models over imperfect sources, self-consistency, rule/physics checks, coverage & evidence-quality scores, abstention quality, ...),
(2) testing/verification on unkeyed datasets (blind sampled verifier, stratified design-based sampling, human spot checks + prediction-powered inference, planted/synthetic canaries, perturbation & metamorphic tests, cross-source triangulation, temporal hindcasts, capture–recapture, ...).
For each: what it catches, what it misses, cost, and HOW THE METHOD ITSELF IS VALIDATED ON KEYED DATA. Say which combination is MVP and how reports show "evaluated" vs "estimated".
Decided (DD1): MVP truth sources = answer keys + a blind, sampled verifier agent (claimed items + unreported places, blind to the claim, its own accuracy measured on keyed tasks). Hindcasting = first stretch. Keep and improve the AWS map from the brief.
Open for the council: must the verifier use a different model/provider from the worker? (Proposed: different family by default, same allowed but flagged.)

## Design items every proposal must cover (A1–A12)
A1 End-to-end flow. A2 Task format (self-contained file: region/AOI, imagery source, prompt with "synthetic" label, optional reference, forbidden tools, expected-workflow spec). A3 Harness/providers/tools (Strands + plain loop; Bedrock default + others; MCP tools incl. imagery-window/COG tool, LGND embeddings tool, STAC scene discovery; multimodal constraint). A4 Tracing & provenance (OTel GenAI semantic conventions, JSONL default, CloudWatch second; manifest; licenses; no pixels). A5 Claim-checking layers (rules, key, verifier, overlap, human) and the verifier-model decision. A6 Scoring breakdown (process/workflow, task understanding, output grade, trust, cost/speed/data-touched panel — evaluated vs estimated, never blended). A7 Trust for unkeyed areas (methods compared, MVP combo, validation, versioned frozen estimator). A8 Statistics & comparisons (OQ2 baseline; N sizing; A/B). A9 Interfaces (API, MCP server, UI, plain summary). A10 AWS map (service, job, tier, local stand-in, cost under $500, Workshop Studio caveats). A11 Act-on-the-world / simulation / hindcast (stretch shape). A12 Cut line (Must/Should/Stretch for Thu 10:00, solo) + demo tasks (keyed calibration tasks + Nepal example + second region).
