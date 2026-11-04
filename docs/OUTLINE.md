# Treehouse product outline

Updated November 4, 2026 from Suhas's clarification. This outline and [PLAN.md](PLAN.md) supersede
older delivery assumptions where they differ. The historical council designs remain useful context.

## Newly supplied benchmark context and confirmed minimal MVP

The [LGND/ADB report brief](LGND-REPORT-CONTEXT.md) records the source, corrected table map, analyst
tasks, assets, imagery constraints, fixed evaluation protocol and worked results. Its Section 5.8
describes the agent-evaluation layer that matches the product intent below. Our working reading is
to observe how an agent selects/adapts the Table 9 workflows and independently evaluate its output
under an explicit task protocol. The report's workflow benchmark and our agent evaluation are
related but distinct. MCP call validity alone cannot establish planning or decision quality.

Suhas confirmed the minimal product and clarified its focus: **evaluate the agent building the
geospatial database**, including why/how it selects and uses foundation models and workflow
components. Strands is one component in that workflow, not the product or a mandatory architecture
for every evaluated agent. Natural-language target/AOI, embeddings, classification and red markers
form a representative workflow whose decisions, evidence, confidence and output are assessed.
The sandbox must allow different valid strategies. This is not adoption of every report benchmark. First task/region and model/data choices are runtime
configuration to pin for the initial bounded test. See [KIRO-NEXT-PROMPTS.md](KIRO-NEXT-PROMPTS.md).

## Product and unit of evaluation

Treehouse evaluates an agent's complete geospatial investigation and the accuracy of the database
it creates. An analyst asks for a particular object type inside a target zone. The sandbox lets an
agent use permitted foundation models, embedding indexes, imagery, classifiers and reference examples,
while recording its decisions, evidence and observable exploration. A warehouse search in a
Bangladesh city is an example, not a fixed dataset, city, classifier or product requirement.

An example workflow is task → strategy → candidate search → imagery inspection/classification → revision →
geographic database → independent evaluation. Scale and settings should fit the object: large
facilities and small objects can require different imagery and search strategies. A foundation
embedding candidate is a region of interest, not proof that an object exists. Strands is an agent
framework; the classifier or foundation model performs the visual/semantic inference.

## What is observed and assessed

- The agent's stated rationale, alternatives, confidence, chosen model/tool/settings and evidence
  available at decision time; actual actions/results and parent/revision links establish the pathway.
- Exploration coverage, repeated inspections, errors, changes of direction, unresolved areas and
  stopping behavior. Appropriate strategies can differ; there is no required universal call sequence.
- Final claim locations/classes/statuses, evidence, cost and speed. Independent reference matching
  and calibration use held-out records with explicit coverage, date, completeness and denominators.
- Optional semantic process review uses a different configured/observed model and a fresh context,
  with an independently authored rubric. Findings are model-estimated, not ground truth.

MCP spans support this evaluation but call counts alone do not establish decision quality. Recorded
rationales are agent self-reports, not proof of complete hidden internal computation. Confidence is
also self-reported; evidence quality and independently measured accuracy are separate quantities.

## Application surfaces

The Book configures a task. Living Sky shows actual Clay candidates and observable activity. Atlas
connects the final prediction database to decisions, evidence, typed evaluations and provenance.
The Investigation pane presents the recorded pathway and actual red prediction markers with a
keyboard-accessible table. Red means prediction, not confirmed truth. Story and Developer modes
share the same underlying records and selection state.

The initial UI starts pinned offline replays. Trusted agent/provider/classifier/source plugins run
through the sandbox CLI/Python API, then their sealed runs appear in the UI. New custom live task
launching and live streaming require further integration. Scene Builder/simulations remain planned.

## Evaluation and data boundaries

Software acceptance tests are authored by a separate agent in a different context, from the
requirements, before the corresponding implementation. Test provenance records original hashes,
red results and justified harness changes. Feature builders do not modify assertions to make green.

Agent evaluation is separate: permitted reference examples may inform the agent, while held-out
records enter grading only after sealing. Reference-example predictions are excluded from held-out
scores; ambiguous split neighborhoods abstain. Incomplete catalogs cannot establish global precision
or calibrated confidence. A human comparison requires an actual measured human baseline.

The public USPVDB subset is a small, incomplete solar-facility reference/evaluator test, not a claim
of successful satellite-image detection. Public data/provenance and an offline synthetic example
cannot substitute for a real model/imagery run in Kiro.

## Current boundary and delivery sequence

The local MVP includes plugin seams, causal decision recording, sealed evaluation, database exports,
and the observatory UI. It is a trusted local evaluation environment, not OS isolation for hostile
plugins. The reporting trust passport remains a visibly unissued stub; no new Rely gate is claimed.

The next handoff is reviewed code and confirmed minimal scope on Treehouse main → Kiro clones
and connects AWS/models/imagery → live tests → refinement. AWS challenge demonstrations remain an
optional integrated surface, not the definition of the product. See [PRODUCT-STATUS.md](PRODUCT-STATUS.md)
and [FUTURE-WORK.md](FUTURE-WORK.md).
