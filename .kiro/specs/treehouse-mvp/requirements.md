# Requirements — Treehouse MVP

Source of truth: `docs/MVP-PLAN.md` (decisions DM1–DM10) and `docs/REPORT-TABLES.md`.

## R1 Retrieval task (T1) and scenarios
1.1 WHEN an analyst submits a task card with a natural-language target, an AOI and a Table-8 class definition, THE SYSTEM SHALL run an agent that produces predicted asset sites for that AOI.
1.2 THE SYSTEM SHALL ship task cards for: Nagoya warehouses (keyed, PLATEAU, warehouse use ≥ 1,600 m²), Gifu warehouses (T5 transfer, no new labels), and a Bangladesh city's warehouses (unkeyed, OSM pool only).
1.4 THE SYSTEM SHALL be class-agnostic: an asset-class registry (`config/asset-classes.yaml`) SHALL define every Table 8 class (positive/negative definition, minimum/typical size, suitable resolutions, reference sources and licences), and a new class SHALL need only a registry entry and a task card.
1.5 THE SYSTEM SHALL run T1 for at least one second class with a usable reference (recommended: ground-mounted solar, Global Renewables Watch, in an ADB country).
1.3 THE SYSTEM SHALL keep grading references out of the agent's reach (forbidden sources, separate key storage) and SHALL serve few-shot examples only from the training split.

## R2 Agent and resources
2.1 THE agent SHALL run on Strands with a Bedrock model by default; model and harness SHALL be swappable by run config.
2.2 THE agent SHALL be able to choose among at least two embedding resources (AEF precomputed 10 m; LGND Clay precomputed 1.28/2.56 km) and SHOULD be able to choose Clay computed on 160 m Sentinel-2 chips.
2.3 THE agent SHALL be able to choose cell/chip size, retrieval method (zero-shot text, few-shot, concept vector), classifier (linear probe, linear SVM, Strands vision sub-agent), threshold and site-merge rule.
2.4 WHEN the agent calls any tool, THE SYSTEM SHALL first require a recorded decision with rationale, alternatives, confidence, parent and evidence (existing `record_decision` contract).
2.5 THE SYSTEM SHALL record imagery source, date, resolution, cell size and licence for every index built.
2.6 THE SYSTEM SHALL refuse imagery not reusable for ADB per Table 17 (Maxar/Vantor) at the gateway and log the attempt.

## R3 Output (map)
3.1 THE agent's final sites SHALL be sealed claims with geometry, confidence and evidence references.
3.2 THE UI SHALL show predicted sites as red markers linked to their evidence and decisions.

## R4 Output accuracy (report protocol)
4.1 THE SYSTEM SHALL grade keyed runs with a new versioned grader using 160 m cells, any-touch matching and one count per asset (report Table 7).
4.2 THE grader SHALL report site recall, recall@k, grid-cell precision, lift, count ratio, AUROC, AP and review effort to 50/80/90 %, and the transfer gap Nagoya → Gifu.
4.3 WHERE the reference is incomplete (Bangladesh OSM), THE SYSTEM SHALL report precision within the reference pool only and SHALL NOT report recall.

## R5 Reasoning validity (score a)
5.1 THE SYSTEM SHALL evaluate each decision against rules RV1–RV10 (MVP-PLAN §5.1) and record pass/fail with reasons.
5.2 THE SYSTEM SHALL score each rationale with a reviewer model of a different family than the worker, against the rubric, recorded separately.
5.3 THE SYSTEM SHALL run AgentCore Evaluations (built-in tool/trajectory/goal evaluators and Treehouse code-based Lambda evaluators) on the run's spans and record results separately.
5.4 WHEN a planted bad agent chooses 1.28 km cells for warehouses without justification or uses Maxar imagery, THE SYSTEM SHALL fail RV1 or RV2 respectively.

## R6 Confidence calibration (score b)
6.1 FOR keyed runs THE SYSTEM SHALL compare per-claim stated confidence with graded correctness: Brier score, reliability bins with counts, ECE.

## R7 Predicted accuracy from reasoning (score c)
7.1 THE SYSTEM SHALL fit, on keyed runs, a model from reasoning features to measured site recall and cell precision, and SHALL apply it to unkeyed runs with an interval labelled MODEL-ESTIMATED.
7.2 THE SYSTEM SHALL report the fit's validation (leave-one-config-out and the Gifu transfer) and its comparison to a mean baseline, including "no better than baseline" when true.

## R8 Comparisons and statistics
8.1 THE SYSTEM SHALL run one-factor-at-a-time comparisons (model, classifier, tool set; harness if time) with N ≥ 3 trials and intervals.

## R9 AWS integration
9.1 Runs SHALL be sealed to the CDK-deployed S3 run store with Compliance-mode Object Lock; a denied delete SHALL be demonstrated and recorded.
9.2 Bedrock, Strands, AgentCore Evaluations, AgentCore Observability (Transaction Search enabled) and Lambda evaluators SHALL run live at least once, with committed evidence (JSON outputs, CloudFormation outputs).
9.3 THE SYSTEM SHALL NOT use Bedrock batch inference (denied in this account).

## R10 Reproducibility and safety
10.1 A recorded replay of the live runs SHALL be committed so the demo runs offline on a fresh machine.
10.2 `uv run pytest` SHALL stay green; live tests SHALL be `@live` and skipped by default.
10.3 Spend SHALL stay under the guard; no credentials, account IDs or imagery pixels SHALL be committed.
10.4 Every live claim in README or demo SHALL be backed by a committed artifact.
