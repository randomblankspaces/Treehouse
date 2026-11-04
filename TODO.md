# TODO

> Kept current by the overnight agent. See [HANDOFF.md](HANDOFF.md) for the job and the current state.

## Overnight (agent)
- [x] Implementation council → `docs/design/IMPLEMENTATION-DESIGN.md` and `docs/design/council-2-log.md` (unanimous at round 3)
- [ ] Spec-sheet update (01/02/04/05/06, EXTERNAL-DEPENDENCIES, FUTURE-WORK, README, SCOPE D43+)
- [ ] Build the basic form (package plan), replay quickstart
- [ ] `docs/OVERNIGHT-REPORT.md`

## Needs Suhas / Kiro (AWS-only steps; paste each prompt into Kiro in Workshop Studio)

> Order: K0 → K1 → K2a → K3, then the Wednesday code queue (W1, W2, W3) → K2b → human labelling block → K4 → K5 → K6 → K7 → K8 → K9.
> Each prompt says which code it needs. If that code is not on `main` yet, ask the agent (Codex or Claude) to build that W-package first.

**Shared preamble.** Every prompt below starts with this block; paste it first.

```
You are working in the Treehouse repo (github.com/randomblankspaces/Treehouse, formerly team-43-renaissance-philanthropy-clay; it is Suhas's fork).
Rules:
- Push only to that repo, on a new branch named kiro/<step>. Never push to VishalPatil18/....
- Never commit credentials, imagery pixels (PNG, JPEG or TIFF crops), or Bedrock image payloads.
- Commit only scene IDs, window coordinates, hashes and JSON results.
Setup:
  git pull
  uv sync --extra aws --extra strands --extra geo
  export TREEHOUSE_SPEND_LEDGER=$PWD/.spend/spend.jsonl   # also the default inside the repo; keep it absolute
Spend guard (stop if the guard says so):
  uv run treehouse budget status   # exit 2/3: spent + reserved > $350: STOP and tell Suhas
                                   # exit 4 NO LEDGER: expected only before K1 (K0: carry on; K1: follow its init
                                   #   step); from K2a on: STOP and tell Suhas
                                   # exit 4 WRONG LEDGER, or "EMPTY LEDGER" after K1: STOP and tell Suhas
  uv run treehouse budget open     # open reservations left by a crashed earlier step, if any
  NEVER delete, move, truncate or re-create .spend/spend.jsonl (that zeroes the $450 guard). If it reports a
  corrupt line, stop and tell Suhas. If open reservations are from a crashed step:
    uv run treehouse budget release-stale --reason "<step> crashed"   # books them as spent (conservative)
  The ledger is NOT the AWS bill: it counts only Treehouse's Bedrock calls at our price table.
At the end of the step:
  git add .spend/ and the step's outputs, commit, push.
Report back: the commands run, their output (trimmed), and anything denied.
```

---

### K0. Execution locus (5 min, $0)

Needs: nothing.

```
<preamble>
Find out where Treehouse can run in this Workshop Studio account. Do not change anything.
1. Run: aws sts get-caller-identity; aws configure list; echo $AWS_REGION; python3 --version; uv --version; df -h .; nproc.
2. Check whether docker works (docker info) and whether node and npx cdk --version are available.
3. Write aws-locus.json at the repo root:
   {identity_arn, region, python, uv, disk_free, cpus, docker: bool, cdk: bool, can_export_creds: "unknown - Suhas decides"}.
   Commit it on kiro/k0-locus and push.
```

### K1. Capability probe (15 min, at most $3)

Needs: P6 (`scripts/aws_probe.py`, `treehouse probe import`, `config/models.yaml`). Every probe call is reserved in the spend ledger at up to $0.25, with `max_tokens` ≤ 32 and a $3 total cap.

```
<preamble>
First live step only: create the spend ledger if (and only if) `budget status` said NO LEDGER and
`git log --oneline -- .spend/spend.jsonl` shows nothing:
  uv run treehouse budget init --note "K1 first live step"
  git add .spend/spend.jsonl && git commit -m "spend ledger genesis"
Run the Treehouse AWS capability probe. It makes one cheap call per service and never aborts (it refuses to
start without the ledger). Region is us-east-1 everywhere; do not change it.
  uv run python scripts/aws_probe.py --region us-east-1 --out aws-capabilities.json
  uv run treehouse probe import aws-capabilities.json
Status meanings: unavailable = the model id/profile is not usable here; invalid_request = Bedrock rejected our
request shape or a parameter (report the detail; do NOT edit models.yaml for it); denied = IAM.
`probe import` prints near matches (listed ids that extend the registry id, e.g. dated -v1:0 suffixes) and,
when another id worked, the exact `inference_profile:` line to put in config/models.yaml.
The report redacts the account id and ARN; the CloudWatch log group it creates gets 1-day retention.
Then show me:
- (a) which Bedrock models are listed and usable, with exact model ids and inference profiles. Report especially Claude Sonnet 5.5 (anthropic.claude-sonnet-5-5 via a us./global. profile) and Amazon Nova Pro (amazon.nova-pro-v1:0 via us.);
- (b) whether each model accepts an image in a user turn and inside a tool result;
- (c) S3 versioning and Object Lock results;
- (d) quotas and throttle behaviour;
- (e) which services were denied.
Update config/models.yaml only where the probe proved a different id or profile.
Commit aws-capabilities.json, the models.yaml changes and .spend/ on branch kiro/k1-probe and push.
```

### K2a. Fill the price table (10 min, $0)

Needs: P6 (`treehouse prices check`).

```
<preamble>
Fill config/prices/bedrock-us-east-1.2026-11-04.yaml with the on-demand USD per 1,000 (1K) input and output tokens (plus cache read/write if listed).
UNITS: pages usually quote per 1M tokens: DIVIDE BY 1000 ($3.00 per 1M -> 0.003). Prices must be > 0 and in a
plausibility band, or the table will not load.
ROWS ARE PER (model, inference profile): fill claude-sonnet-5-5@us (the us. profile we call), claude-sonnet-5-5@global
and nova-pro@us. us./eu. geographic profiles can cost ~10% more than global.; if unsure which profile a number is
for, use the MORE EXPENSIVE number in the @us row.
Use the AWS Bedrock pricing page or the Pricing API:
  aws pricing get-products --service-code AmazonBedrock --region us-east-1
Write source, retrieved (date) and unit_source (e.g. "page per 1M; divided by 1000") into the file. Then run:
  uv run treehouse prices check
It must exit 0 (no null or FALLBACK rows for the worker and verifier). It prints each price back as $/1M:
compare every number with the pricing page before committing.
Commit on kiro/k2a-prices and push.
```

### K3. First live keyed run on the synthetic task (30 min, about $15; stop at $25)

Needs: P5–P7 merged. `treehouse run` supports `--mode record` and `--live`.

```
<preamble>
Run the first live Treehouse run on Bedrock with the plain-loop harness on the SYNTHETIC keyed task (tasks/synth-crossings-v1.yaml), K=3 trials, recording cassettes:
  uv run treehouse budget plan --task tasks/synth-crossings-v1.yaml --trials 3   # exit 1 = unpriced: do K2a first
  uv run treehouse run --task tasks/synth-crossings-v1.yaml --config fixtures/demo/configs/live-bedrock.yaml --mode record --trials 3
  uv run treehouse check <run_id> && uv run treehouse score <run_id> && uv run treehouse report <run_id>
  uv run treehouse verify
  uv run treehouse budget status
Then check the real bill (Cost Explorer lags hours; ~$0.01 per call) and record it:
  aws ce get-cost-and-usage --region us-east-1 --time-period Start=$(date -u +%Y-%m-01),End=$(date -u -d tomorrow +%Y-%m-%d) --granularity MONTHLY --metrics UnblendedCost
  uv run treehouse budget reconcile --aws-usd <Amount> --source "aws ce $(date -u +%F)"   # exit 2: AWS >> ledger: STOP
  (or read it from the AWS Billing console). Report both numbers.
Report:
- per-trial cost, p90 cost, tokens (incl. image tokens), wall time;
- any throttles (span events);
- the KEYED precision/recall chips;
- the report path.
Copy bundles/<run_id>/report.html and bundle.json into runs-live/ in the repo. They contain no pixels; check that with the licence scan:
  uv run pytest tests/unit/test_licence_scan.py
Commit on kiro/k3-live-synth and push.
```

### K2b. Vision smoke test on real Vantor 0.5 m windows (20 min, about $5)

Needs: W1 (`CogSource` and `treehouse smoke vision`).

```
<preamble>
Run the vision smoke test on real Vantor Nepal windows to choose the worker and verifier models and to confirm the Nepal AOI:
  uv run treehouse smoke vision --task tasks/nepal-bhote-koshi-bridges.yaml --scenes B1300011011E5610,B1300011011E5810 --gsd 0.5,1,2
Report, per model and effective resolution:
- can it see the road bridge and the footbridge (yes/no/cannot tell);
- tokens and cost;
- bytes read.
Also open the AOI corners in the report map and say whether the corridor (Syabrubesi to Rasuwagadhi) is inside the AOI.
Never commit image crops: commit only smoke-vision.json (ids, windows, answers, hashes) on kiro/k2b-smoke.
```

### H. Suhas: blind labelling block (60–90 min, $0)

Needs: W3 (`treehouse label export/import`) and the K4 gold-seed commit.

```
1. uv run treehouse prereg commit        # commits gold seed, trust config and primary list BEFORE any verifier verdicts
2. uv run treehouse label export --run <nepal run id> --out labels/
   Open labels/index.html. Label each crop yes/no/cannot_assess using only the crop. Worker and verifier answers are hidden.
3. After a break, re-label the 5 shuffled re-label items.
4. uv run treehouse label import labels/answers.csv && uv run treehouse trust <run id>
```

### K4. Live Nepal run with the blind cross-family verifier (45 min, about $40; stop at $60)

Needs: W1, W3 and W13. W2 (Strands) is optional: without it, use `--harness plain_loop` and say "Strands adapter: offline-tested only".

```
<preamble>
1. Confirm the gold seed is committed (git log prereg/gold-seed.txt) BEFORE running anything.
2. uv run treehouse run --task tasks/nepal-bhote-koshi-bridges.yaml --config fixtures/demo/configs/live-bedrock.yaml --mode record --trials 3 --harness strands
   If the strands harness is not merged, use --harness plain_loop and say so.
3. uv run treehouse check <run_id> && uv run treehouse verify-claims <run_id> --verifier agent
   The verifier must be a different model family from the worker; the config validator enforces it.
4. uv run treehouse score <run_id> && uv run treehouse trust <run_id> && uv run treehouse report <run_id>
Report:
- cost;
- how many bridges were claimed and how many were marked cannot_assess;
- verifier abstention rate;
- the trust passport headline and tier;
- the test-retest kappa.
Before step 2, plan with the verifier counted:
  uv run treehouse budget plan --task tasks/nepal-bhote-koshi-bridges.yaml --trials 3 --verifier-calls 40
After the run, repeat the K3 Cost Explorer check and `treehouse budget reconcile`, and report AWS vs ledger.
Commit the bundle (no pixels) and .spend/ on kiro/k4-nepal.
```

### K5. Export pixel-free cassettes for replay (10 min, $0)

Needs: W3b (`treehouse cassette export --pixel-free`).

```
<preamble>
uv run treehouse cassette export --pixel-free --runs <K3 run id>,<K4 run id> --out fixtures/live/
uv run treehouse replay --cassettes fixtures/live/ --verify   # must reproduce the trace heads with Bedrock access off
Run the licence scan, then commit fixtures/live/ on kiro/k5-cassettes.
```

### K6. Fetch answer keys (on Suhas's Mac or in Kiro if reachable, 15 min, $0)

Needs: W3b (`scripts/fetch_uspvdb.py` and `scripts/fetch_osm_bridges.py`).

```
uv run python scripts/fetch_uspvdb.py --aoi tasks/virginia-solar-18sth.yaml --out keys/virginia/
uv run python scripts/fetch_osm_bridges.py --aoi tasks/nepal-bhote-koshi-bridges.yaml --out keys/nepal-osm/
uv run treehouse task validate tasks/virginia-solar-18sth.yaml   # key status becomes present with a version hash
Commit keys/ with the printed hashes. USPVDB is public domain; OSM is ODbL, so keep it in its own directory with attribution.
```

### K7. CDK deploy (20 min, about $0)

Needs: W6 (`infra/`).

```
<preamble>
cd infra && npx cdk bootstrap && npx cdk deploy --all --require-approval never
If bootstrap is denied, use the bootstrapless synth plus aws cloudformation deploy, as written in infra/README.md.
Then: uv run treehouse probe verify-infra
It must show:
- the run bucket with versioning;
- Object Lock with default governance retention, if allowed;
- the key bucket with an explicit Deny for the worker role.
Commit cdk-outputs.json on kiro/k7-cdk.
```

### K8. Push sealed runs to versioned S3 and show the denied delete (10 min, $0)

Needs: W5 (`treehouse store push`).

```
<preamble>
uv run treehouse store push --bucket <run bucket from cdk-outputs.json>
Then demonstrate immutability: try to delete a specific object VERSION, passing --version-id, as the worker role and without bypass:
  aws s3api delete-object --bucket ... --key ... --version-id ...
It must be denied (403). Do not use aws s3 sync. Record the output in s3-proof.txt and commit it on kiro/k8-s3.
```

### K9. Second tracer reconcile (10 min, about $0)

Needs: W9.

```
<preamble>
uv run treehouse run ... --tracer jsonl,cwlogs   # a 1-trial synthetic live run
uv run treehouse trace reconcile <run_id>        # span counts and token totals must match between JSONL and CloudWatch
Commit reconcile.json on kiro/k9-tracer.
```

## P5 demo skeleton (pkg/p5-demo-skeleton): merged state and hand-offs
- `uv sync && uv run treehouse demo` works offline (about 10 s): 9 replayed runs, golden heads, R1/R2/R4,
  Panel 1 basics + Panel 5, trust STUB (ABSTAINED "trust engine not yet built"), reports, index, verify.
- After merging pkg/p4-fixes (specs filtered by tools_allowed, effective-GSD floor, tool-cassette changes):
  rerun `uv run python scripts/make_demo_fixtures.py`, then commit the regenerated cassettes and
  `fixtures/golden/heads.json`.
- P7: replace `checks/rules.py` (R1/R2/R4 only) with R1-R9 + keyed match + leaks; fill the understanding and
  output panels (currently `no_grade_reason`); I1-I3 use the demo runs (fabricator 10/10/16, key-peeker 2 blocked).
- P8: replace `trust/stub.py`; add verdict/gold fixtures (`fixtures/demo/{verdicts,gold}`) to
  `scripts/make_demo_fixtures.py` from `keys/synth/*.json`; wire §5.3 steps 5 and 7 into `service.demo`.


## Current continuation — user clarification November 4

This section supplements the historical overnight checklist above; it does not erase previous decisions.
See docs/PLAN.md and docs/KIRO-HANDOFF.md for the current sequence and actual commands.

- [x] Independently authored investigation acceptance/rubric and reference/holdout regression tests.
- [x] Local plugin sandbox, causal decisions, vision-classifier adapter, sealed reports and SQLite/GeoJSON.
- [x] Investigation UI with actual prediction markers, evidence and confidence links.
- [x] Local all-extras suite: 733 passed, 2 live skips, 1 deselected; fresh independent repair review passed.
- [x] Reviewed implementation merged via PR #8 (`2fc2461`); subsequent report clarification is recorded below and Kiro prompts are prepared.
- [x] Incorporate Suhas's report and clarification: evaluate the agent's model choices/workflow and final database; Strands is a workflow component.
- [ ] Kiro: connect real AWS providers, imagery/embedding sources and classifier under existing guards.
- [ ] Kiro: independently test real workflow/output, record actual costs/accuracy and remaining failures.
- [ ] Refine from live evidence; keep simulations, human-baseline claims and unsafe trust wiring deferred.

## Latest context — LGND/ADB report and confirmed minimal sandbox

This supersedes the old overnight execution queue as the next action. See
[docs/LGND-REPORT-CONTEXT.md](docs/LGND-REPORT-CONTEXT.md) for the source hash, table/page map,
analyst tasks, asset definitions, workflow alternatives, benchmark protocol, imagery constraints,
worked results and differences from the implemented sandbox.

- [x] Extract all 30 pages locally; visually inspect the key tables; preserve a source-grounded repo brief.
- [x] Update active outline, status, constraints, future-work and handoff pointers for another agent.
- [x] Suhas confirmed the agent-evaluation sandbox; natural-language/AOI, embeddings, classifier and red markers describe a representative workflow, with Strands as one component.
- [x] Prepare scoped [Kiro continuation prompts](docs/KIRO-NEXT-PROMPTS.md), with existing paths and evidence limits.
- [ ] Kiro: pin a suitable bounded first task/AOI, eligible data and actual model versions; freeze independent acceptance before feature code.

The report's Section 5.8 is the working agent-evaluation framing. Tables 2–3 are background, Table 17
is the imagery matrix, Table 8 defines assets, Table 7 fixes the evaluation protocol, Table 11
explains success metrics and Table 9 describes workflows. These notes are not accepted new S/D/F
requirements. Only the confirmed minimal integration is the Kiro scope; broader tasks and imagery
purchases are not implied.
