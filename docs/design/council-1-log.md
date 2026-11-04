# Council 1 log (system design)

Unanimous after 2 voting rounds; round 1 was NOT unanimous, so blocking objections were resolved before acceptance.

- accept=True | blocking: 
- accept=False | blocking: A7/A12 Must 9: the Must list requires a 'regime-grouped LORO table with distinct-regime count', but the Must task set has exactly one keyed regime (Virginia solar) and A8 says the spaced tiles count as one regime. LORO needs at least 2 folds, so it cannot be produced and the pre-registered 'beats B2 in a majority of folds' test is undefined. Fix: say Must ships B0/B1/B2, PPI and the shift numbers. The beat-baseline panel then renders 'not computable: 1 keyed regime' and the passport defaults to the wide B2 interval. The LORO table moves to Should, and runs only if a second keyed regime is adde
- accept=False | blocking: A5/A7 (gold frame is biased by abstentions): the random-gold queue is defined as a subsample 'of the verifier-labelled units'. Verifier abstentions are excluded from the rectifier but still sit in the estimand, the run's whole claim table. The PPI estimate is then valid only for the non-abstained subpopulation, and abstention correlates with cloud and hard cases. It should say: draw gold at random from ALL sampled units, including verifier abstentions, with inclusion probabilities stored. Define the predictor f(x) for an abstention as an explicit third category or a stratum-specific mean, so t
- accept=False | blocking: A12 (feasibility, blocks shipping): The Must list is not a 14 h item for one person. It bundles two harnesses, a gateway with 4-layer key enforcement, CDK for Object Lock plus IAM simulator test, a blind cross-family verifier with probability sampling plus unreported-places frame plus controls, a five-panel scorecard with predictive-validity strip, PPI trust passport with B0/B1/B2 and a regime-grouped LORO table, an MCP server, a plain-summary numbers lint, 2 to 3 task cards, and a clean-clone repro. Must (14 h) plus Should (6-8 h) is 20-22 h against 18-20 productive hours, with zero slack for
- accept=False | blocking: A10/A12 (execution locus is missing). The brief says the Workshop Studio account is reachable ONLY through the browser (Kiro web IDE), but the draft never says where the worker, verifier, gateway, CDK and tests actually run. Everything assumes boto3 credentials on a dev machine. Fix: add an hour-0 'execution locus' decision to the probe. Test (a) whether Workshop Studio's temporary CLI credentials can be exported to the Mac, then run locally with `backends: aws`. Fall back to (b): run everything inside the Kiro web IDE terminal, with git push/pull as the transport, and check its disk, CPU, ses
- accept=True | blocking: 
- accept=True | blocking: 
- accept=True | blocking: 
- accept=True | blocking: 
- accept=True | blocking: 

## Fact-check changes
- Marked Object Lock 'cannot be server-access-log destination' claim as (unverified in this pass) in A4
- Marked OTel GenAI semconv 'Development' status as (unverified in this pass) in A4 and noted the cited OTel page has moved to the GenAI semconv repository
- Marked 'nine judges from seven families ~2.2 independent votes' as (unverified) in A5
- Marked arXiv 2505.18659, 2303.07334, 2510.04265, 2506.07962, 2510.11977, 2605.29800, aclanthology 2026.cas-1.11, arena.ai blog and icml.cc poster as (unverified) in Sources
- Confirmed AgentCore Evaluations GA 2026-03-31 and Lambda code-based evaluators; confirmed arXiv 2404.01542 and 1703.03022 titles; confirmed A7 small-n arithmetic and brief data facts
- Appended Fact-check notes section, including the governance-mode bypass and delete-marker caveat for the denied-delete demo, and an explicit list of items not checked because the fact-checker hit a tool spend limit
## Addendum (overnight agent, 2026-11-04)

### What this log does and does not record
The original log above lists ten votes without seat names. Read in order:
- **Round 1:** 1 accept and 4 rejects, each reject with a blocking objection. Because round 1 was not unanimous, the forced devil's-advocate round was not needed.
- **Round 2:** all 5 seats accept.

Each seat's position changes between proposal and debate were **not recorded at the time** and cannot be recovered. The attribution below is **inferred** from the "Who argued it" column of SYSTEM-DESIGN.md's decisions table, not from a record of the vote.

| Round-1 blocking objection | Most likely raised by (inferred) | How it was resolved in revision 2 |
|---|---|---|
| LORO cannot run with one keyed regime | agent-eval or remote-sensing (four seats argued it over aws-architect) | LORO moved to Should; "not computable: k regimes" is displayed; the passport defaults to wide B2 |
| Gold frame biased by verifier abstentions | statistician | Gold drawn from ALL sampled units; abstention is a third predictor category; abstention rate shown |
| Must list not feasible solo | beneficiary-judge (A12 rows credit "all four objectors") | Must split into Must-0 skeleton (H10 checkpoint, fallback), Must-1 and Should, with a cut order |
| Execution locus missing (Kiro-only AWS) | aws-architect | Hour-0 execution-locus decision added to A10 |

**Judgement on unanimity:** genuine, in the sense that all five seats accepted revision 2 after four blocking objections were resolved in the text. The record of per-seat reasoning is thin.

### Post-merge changes (branch `docs/system-design-factcheck`)
1. **Fact-check pass 2** of the claims the first fact-checker could not reach. Counts: 22 verified, 12 match the known record (arXiv blocked), 3 corrected, 6 unverifiable. Corrections and resolved marks are summarised at the end of SYSTEM-DESIGN.md.
2. **Scene-count correction**, checked directly against the bucket: 33 Vantor scenes, **4 pre-event + 29 post-event** (not 28). Off-nadir and sun angles are present in the STAC items.
3. **Decision weakened by the fact-check:** NAIP is Requester Pays, so the Virginia keyed demo needs AWS credentials. The overnight build substitutes a synthetic keyed task for the offline demo. Virginia becomes a Kiro live run.
4. **A13 "Unkeyed methods compared"** was added. It holds Suhas's top-priority comparison table (catches, misses, cost, how each method is validated on keyed data, MVP combination, and how "evaluated" vs "estimated" is shown), which revision 2 had spread across A5 and A7. It went through a doubter pass and a judge pass; results are below.
