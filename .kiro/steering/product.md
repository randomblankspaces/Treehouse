---
inclusion: always
---
# Product: Treehouse (repo name: Clay agent-eval sandbox)

Built for the AWS Breaking Barriers Challenge 2026 (DC) for **Clay** (Earth Dataset Foundry) and its partner
**ADB**. Judges are AWS staff; criteria: Technological Implementation (incl. AWS integration), Design,
Potential Impact, Quality of Idea. Public repo due **Thu Nov 5 2026, 10:00 EST**.

**What it does.** An ADB analyst's geospatial question (MVP: **T1 retrieval — "where are all the warehouses
in this city?"**) goes to an AI agent (Strands on Amazon Bedrock). The agent uses **foundation models as
resources** (AEF, Clay, a Bedrock vision model) to build a georeferenced asset database and plots predicted
sites as red markers. **Treehouse judges the agent's thinking**: each decision (model, imagery, cell/chip
size, retrieval method, classifier, threshold, site merging, revisions), whether each decision's **why is
valid**, and how that reasoning relates to measured accuracy, stated confidence, time and money.

**Three separate scores, never blended:** (a) reasoning validity, (b) confidence calibration, (c) predicted
accuracy from reasoning (for unkeyed runs). Output accuracy (report protocol) and cost/time/data are their
own panels.

**Scenarios:** Nagoya warehouses (keyed, complete PLATEAU reference) → Gifu (transfer, no new labels) →
a Bangladesh city (unkeyed; precision within the OSM pool only).

**Authoritative docs:** `docs/MVP-PLAN.md` (plan, decisions DM1–DM10, acceptance checklist),
`docs/REPORT-TABLES.md` (ADB/LGND report digest), `docs/LGND-REPORT-CONTEXT.md`,
`docs/design/DEFENSE-BOOK.md` (how to defend choices to AWS judges), `docs/design/AWS-BLUEPRINT.md`.

**Product rules:**
- Claim only what ran; label everything else "designed" or "roadmap".
- Self-reported rationales are evidence of what the agent said, not proof of its internal reasoning; keep
  them separate from measured outcomes.
- Never use Maxar/Vantor imagery for ADB datasets (CC BY-NC). Record every source's licence.
- Never let a grading reference reach the agent; few-shot examples come from the training split only.
