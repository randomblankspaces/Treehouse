# Treehouse product outline

Updated November 4, 2026 from Suhas's clarification. This outline and [PLAN.md](PLAN.md) supersede
older delivery assumptions where they differ. The historical council designs remain useful context.

## Product and unit of evaluation

Treehouse evaluates an agent's complete geospatial investigation and the accuracy of the database
it creates. An analyst asks for a particular object type inside a target zone. The sandbox lets an
agent use permitted foundation models, embedding indexes, imagery, classifiers and reference examples,
while recording its decisions, evidence and observable exploration. A warehouse search in a
Bangladesh city is an example, not a fixed dataset, city, classifier or product requirement.

The workflow is task → strategy → candidate search → imagery inspection/classification → revision →
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

The next handoff is reviewed code on Treehouse main → user supplies additional context → Kiro clones
and connects AWS/models/imagery → live tests → refinement. AWS challenge demonstrations remain an
optional integrated surface, not the definition of the product. See [PRODUCT-STATUS.md](PRODUCT-STATUS.md)
and [FUTURE-WORK.md](FUTURE-WORK.md).
