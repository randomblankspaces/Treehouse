# Council brief — Treehouse system design (2026-11-03, 23:50 EST)

## What we are designing
"Clay agent-eval sandbox", presented as **Treehouse**. Hackathon: AWS Breaking Barriers Challenge 2026 (DC). Beneficiary: Clay (Earth Dataset Foundry); partner ADB (Asian Development Bank). SOLO builder (Suhas). Public repo due **Thu Nov 5, 10:00** (~34 h away incl. sleep). AWS sandbox: Workshop Studio account, $500 cap, reached only through the browser (Kiro web IDE); Bedrock access confirmed. Code license Apache-2.0. Judging: four equal criteria — Technological Implementation (incl. AWS integration), Design (UX, interface, architecture), Potential Impact, Quality of Idea.

## Suhas's vision (his words, lightly cleaned) — authoritative
- "We are just building the system. Everything else is examples going through the system." Nepal/Kathmandu, Virginia solar farms, India: all just example tasks.
- "The actual system is the thing that evals the agent, and then changes we can make on the world after the agent creates the database." E.g. with a bridge database after a flood, see which bridges are unsafe and do whatever ADB does with that.
- Score the way the agent worked (main judgment); whether its output can be trusted (output grade + how it reached its conclusion); whether it understood the task; give the user a plain summary of what the agent did. Cost and speed are key, easy parts of agent evals and first-class, because the agent goes through huge data.
- "The answer key is only for output eval" — its purpose: find the correlation between agent run context/input and output accuracy, so we can draw conclusions when there is no answer key. He thought of "a simple probability model" for unkeyed areas but wants something better.
- A second Strands agent checks the output: is each item really where the agent said?
- Scores and reports both exposed as an MCP server too. Model and tracer hot-swappable.
- Several model providers; **Bedrock is the ideal/default**. Open source and reproducible on other computers, with other inputs and providers.
- A flood/bridge-failure simulation (visible, every input number exposed, starts only when the user selects a location and clicks; realistic but not overly; human-verified) is STRETCH/FUTURE.
- He wants **more AWS integration** — keep the AWS map below and improve it.
- Clay = vector database (embeddings) that narrows the search, then the agent checks imagery more closely.

## Decided so far
- DD1: MVP truth sources = answer keys + a verifier agent (sampled, blind to the claim, its own accuracy measured on keyed tasks). Hindcasting = first stretch. This revises the old "no LLM judge for output" decision (D25/OQ12).
- Open (yours to settle): must the verifier use a different model/provider than the worker? (Proposed: different family by default, same allowed but flagged.)

## Read these
- The current spec: `git show a23dec5:docs/SCOPE.md` (requirements S1–S19, decisions D1–D42, glossary, example task). Older detail files: `git ... show 373719c:docs/<file>` for 01-features-in-scope.md, 02-success-criteria.md, 04-user-journeys-tests.md, 05-definition-of-done.md, 06-risks-and-dependencies.md, OPEN-QUESTIONS.md, EXTERNAL-DEPENDENCIES.md.
- Review 1 verdict (judge): docs/reviews/review1-judge.md — idea good, not set up: 3 critical gaps (trust estimate has no method/validation/provenance; flagship step has no reference; no cut line/F-SC-J-DoD for S14–S19) + must-fix list + 10 decisions.
- Verifier facts: docs/reviews/review1-verifier.md (Vantor Nepal event: 33 scenes, 28 post-flood, some 6–24 % cloud; glacier-collapse flash flood 2026-08-26, Bhote Koshi, Rasuwa; no cloud mask, scene-level cloud % only; Vantor license CC-BY-NC-4.0; Vantor bucket in us-east-1; LGND embeddings: Sentinel-2, Jan 2017–Apr 2026, 1.28 km cells, 256-d, CC BY 4.0, us-west-2).
- Clay's values: Clay's vision doc is not in the repo (kept private, SCOPE D15). Its values are distilled in docs/SCOPE.md (Problem, Constraints) and quoted in docs/reviews/review1-doubter.md section 2; the cloud session's prompt carries the excerpt.

## Proposal on the table: trust engine for unkeyed areas (assistant, not yet decided)
Four independent estimates; disagreement between them is itself a warning. Suhas's simple probability model kept as the baseline the engine must beat.
1. Shift score: compare the new area's Clay embeddings to the keyed regions' to measure how far we extrapolate; widens uncertainty; names the most similar keyed region.
2. Process model with honest uncertainty: hierarchical / beta-binomial model, pooling across tasks/regions, uncertainty grows with shift.
3. Agreement-on-the-line (Baek et al. 2022): agreement between independent runs/models (label-free) mapped to accuracy via a line fit on keyed tasks. Shown for image classifiers, unproven for agents.
4. Dawid–Skene latent-class model over all imperfect sources (agent runs, verifier, partial OSM, rules) → per-source reliability + per-item truth posterior, no key. Needs source independence.
+ Prediction-powered inference (Angelopoulos et al. 2023) when a person checks ~20 items → valid CIs on headline counts.
Validation: leave-one-keyed-region-out; compare each estimator to the hidden truth.
Check layers: (1) deterministic rules; (2) answer key where it exists; (3) blind sampled verifier (claimed items + unreported places, different model); (4) two-source overlap (Lincoln–Petersen) recall bound; (5) human review of disagreements.

## AWS map on the table (KEEP and improve) — principle: AWS-native, not AWS-locked (every AWS piece has a local stand-in)
| Service | Job | Tier |
|---|---|---|
| Bedrock (Converse) | worker + verifier models from different families | Must |
| Bedrock batch inference | verifier's sampled checks at ~half price | Should |
| Bedrock AgentCore (Runtime + Observability) | host the Strands agent; OTel traces to CloudWatch GenAI observability (second tracer) | Should |
| S3 versioned + Object Lock | immutable run store (audit trail) | Must |
| Athena over S3 traces | SQL across runs; feeds trust engine | Should |
| Step Functions (distributed map) | N trials × configs → verifier → score → trust, with retries | Should |
| Lambda | rules, scoring, image-window reads next to the data (Vantor us-east-1; Clay/NAIP us-west-2) | Should |
| Fargate + Cognito | hosted API + MCP + UI with partner login | Could |
| CDK | everything as code; anyone deploys to their own account | Must (for what we deploy) |
| Stretch: S3 Vectors, EventBridge (re-check when new event imagery lands), A2I (human review) | | |
Unchecked: which services Workshop Studio allows.

## ADDED BY SUHAS 23:58 — top priority for every stage after Propose
**Most datasets Treehouse sees will be UNKEYED.** Treat unkeyed as the normal case, keyed as the special case used for calibration. Compare and choose among *different* methods for:
1. **Eval scores on unkeyed output** (not one probability model): e.g. label-free accuracy estimation, agreement/consistency across runs and models, latent-class models over imperfect sources, self-consistency, rule/physics checks, coverage and evidence-quality scores, abstention quality.
2. **Testing/verification methods on unkeyed datasets**: e.g. blind sampled verification, stratified design-based sampling, human spot checks with prediction-powered inference, planted/synthetic canaries, perturbation and metamorphic tests (shift the area, rotate/crop windows, rephrase the prompt — output should change predictably), cross-source triangulation, temporal hindcasts, capture–recapture.
For each method say what it catches, what it misses, its cost, and how we validate the method itself on keyed data. The design must say which combination is MVP and how the report shows "estimated" vs "evaluated".
