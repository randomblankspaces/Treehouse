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
3. **Decision affected by the fact-check:** NAIP is Requester Pays, so the Virginia keyed demo needs AWS credentials. The overnight build has none, so it cannot read NAIP tonight. As first written, this pass replaced Virginia with a synthetic keyed task. After the judge pass below, Virginia stays demo task 1 (run live once credentials exist), and a SYNTHETIC keyed task is **added** for offline replay and method tests only. Suhas to confirm.
4. **A13 "Unkeyed methods compared"** was added. It holds Suhas's top-priority comparison table (catches, misses, cost, how each method is validated on keyed data, MVP combination, and how "evaluated" vs "estimated" is shown), which revision 2 had spread across A5 and A7. A doubter pass and a judge pass on it, and on the rest of this pass, are recorded in the section "Doubter/judge pass on the overnight edits" below.

## Doubter/judge pass on the overnight edits

Date: 2026-11-04. A doubter attacked the fact-check pass 2 edits, the new A13 and the pass-2 notes in SYSTEM-DESIGN.md (36 doubts: 3 blocking, 18 major, 15 minor). A judge ruled on each and applied the fixes to SYSTEM-DESIGN.md and this log. The judge re-checked the July 2025 flood by web search (Kathmandu Post and ekantipur, 2025-07-08). The judge did not re-run the doubter's Vantor footprint and `pan_gsd` checks; the design cites them as the doubter's and leaves the per-bridge footprint check to the hour-1 probe.

**Rulings: 34 valid, 2 partly valid, 0 invalid.**

| # | Severity | Ruling | Action taken |
|---|---|---|---|
| 1 | blocking | VALID. Under positive dependence the overlap is inflated, N̂ is too small, so misses are underestimated: a lower bound on misses, an upper bound on recall | V9 rewritten (recall upper bound; Chapman fixes small-sample bias, not dependence); A5 item 4 given the same sentence |
| 2 | major | VALID. PPI validity is relative to builder labels at n_gold ≈ 20, not to truth | A13 §3 and V4 restate what U1 relies on; up-front section given a short qualifier |
| 3 | major | VALID. Several rows are validated by simulation, by a Should step, or not until a 2nd keyed regime | Intro reworded; "Validated in MVP?" column added to both tables (yes / simulation only / not until 2nd keyed regime / no / n/a) |
| 4 | major | VALID. HT is design-unbiased for verifier verdicts, not correctness; small strata; two-phase variance | V3 reworded: strata-collapse rule (≥2 sampled, ≥1 gold), two-phase variance, nominal coverage only approximate at this n, actual coverage printed |
| 5 | minor | VALID. Rare objects give very wide omission intervals | V3 states "within the frame only" and the 0/10 → about 30 % example |
| 6 | major | VALID. Comparing damage placebo to solar specificity is cross-family borrowing | V5 validation: Wilson interval on the false-alarm rate; same-family negatives only; no cross-family comparison for damage |
| 7 | major | VALID. The 2025-07-08 flood (confirmed) breaks the pre-2025 "no change" baseline | A5 controls, A13 V5, A12 demo task 2 (scene must cover the bridges) and A12 risk 11 updated; rubric grades post-event state; per-bridge footprint check added to hour-1 probe |
| 8 | major | VALID. Moving the AOI does not move bridges | V7 relations corrected (overlap claims keep coordinates; georeference shift is the synthetic case); V2 crop called blindness, not metamorphic |
| 9 | major | VALID. There is no cloud mask, so guessing under cloud cannot be scored at cost 0 | U9: footprint part deterministic; cloud part only on gold-marked items; cost "0 / H" |
| 10 | minor | VALID. Calibration against the verifier is agreement; ECE unreliable at small n | U8: KEYED and gold items only; "agreement with verifier" label; Brier plus ≤3-bin plot; no ECE headline at n < 50 |
| 11 | minor | VALID | U2 catches/misses rewritten; abstain threshold to be pre-registered, with the doubter's 0.3 bound recorded as a proposal |
| 12 | minor | VALID. Fabrication and loops are caught by V1 and Panel 1 | U3 "what it catches" rewritten |
| 13 | minor | VALID. Non-overlap is a weak test | §3 says silence is not agreement; both intervals shown |
| 14 | blocking | PARTLY VALID. Requester Pays does only need credentials, but the overnight build has none, so tonight's offline build cannot read NAIP; the rest (scope change, broken H10/headline, no SYNTHETIC rule, decided without Suhas) is valid | Virginia restored as demo task 1 (live); SYNTHETIC keyed task added, never a keyed regime, never backs KEYED/Se-Sp/Clay claims; SYNTHETIC defined in Conventions and A7 LORO; H10 note; flagged for Suhas in A12, decisions table and pass-2 notes; Virginia cassette may later carry NAIP crops |
| 15 | major | VALID. A12 budgets B2, not a fitted process model | U3 → Should; MVP uses B2; features logged |
| 16 | major | VALID. Needs an OSM existence key the cut line does not budget | U2 → Should, only with a same-family key; never from solar |
| 17 | major | VALID | U5 cost "0 marginal given K=3"; MVP → Should (stored feature, no extra runs; matching via `match_rule`), since A12 does not budget the matching code |
| 18 | minor | VALID | V2 marks phi as Should (A12 Should item 7) |
| 19 | major | VALID. No human labels on keyed items are planned | V4: "reference error unmeasured in MVP (test-retest n=5 only)"; 5 keyed gold labels listed as Could, not added to Must |
| 20 | major | VALID | §3 is now the single source of truth; every row's MVP cell matches it; H10 fallback combination added |
| 21 | major | VALID. Cost, time, bytes and process sub-scores are exact | MEASURED type added in Conventions, A6 chips and A13 §3; U10 tier set to MEASURED |
| 22 | major | VALID. IMPLEMENTATION-DESIGN.md does not exist; "every method" was false | §4: "each MVP method", "will be specified in IMPLEMENTATION-DESIGN.md, not yet written"; U9, U10, V6 tests added; U2/V9 tests "if built" |
| 23 | minor | VALID | V7 and V8 added to A12 Could; V11 queue export, V1b, U2, U3, U5 added as A12 Should item 12; nothing new in Must |
| 24 | major | VALID | "Not chosen for the MVP, and why" list added to §3 (a list, not a column, because the tables are already wide); V1b physical-plausibility row added (Should), with the OSM-roads leak warning; cost scale defined; B1 named as the confidence-based estimator |
| 25 | major | VALID. The claimed review had no record | A13 header and log addendum now point to this section |
| 26 | blocking | VALID. Enabling Object Lock locks nothing without retention | A4 and A10: Object Lock on the run-store bucket itself, bucket default governance retention plus per-PUT retention headers; no separate demo bucket |
| 27 | minor | VALID | "cannot be disabled" marked known record, not re-fetched (A4 and pass-2 notes) |
| 28 | major | VALID. The table was only in the scratchpad | Full table appended below; pass-2 notes point to it |
| 29 | major | VALID | A4 licenses (USPVDB CC0, NAIP public domain), A3 provider matrix, A8 "select models", pass-1 "28 post" marked superseded |
| 30 | minor | VALID | Sources "Local" now cites the STAC check, not council-brief.md, for 29 post; notes say the cause of the 28/29 gap was not identified |
| 31 | minor | PARTLY VALID. That v1.42.0 is the core release is the doubter's guess, also unverified; the hedge and the intermediate-span point are right either way | A4 wording hedged (core v1.42.0 per one secondary source; genai repo version read at hour 0); match on `gen_ai.operation.name` and allow Strands event-loop spans |
| 32 | minor | VALID | A9 adds account-level BPA or SCP risk |
| 33 | minor | VALID | NeurIPS source line reworded |
| 34 | minor | VALID. "Seven families" was not confirmed | A5 sentence reworded to what fc row 16 verified |
| 35 | minor | VALID (from the doubter's STAC fetch) | A3 and A7 name `pan_gsd` 0.43-0.71 m; smoke test confirms the delivered band set |
| 36 | minor | VALID | U4: B1 "self-reported", never a tier; B0 "not computable" on Nepal damage |

**New finding recorded:** the 2025-07-08 Bhote Koshi flood destroyed the Miteri (Nepal-China friendship) bridge at Rasuwagadhi, and a 2025-07-30 flood cut the Syabrubesi-Rasuwagadhi road. Pre-2025 pre-event scenes are therefore not a valid "no change" baseline for the upper corridor (A5 controls, A13 V5, A12 risk 11).

**Open for Suhas:** (1) Virginia stays demo task 1 run live; the SYNTHETIC keyed task is added for offline replay and method tests only; the synthetic task does not satisfy the H10 checkpoint. (2) The damage rubric grades post-event state; change is attributed to the 2026 event only where the 2026-02-05 pre scene covers a bridge. (3) Object Lock is made permanent on the run-store bucket, with short governance retention.

## Fact-check pass 2: full table

Copied from the fact-checker's working file (session scratchpad), unchanged except for heading levels. One suggestion is superseded by the judge pass: row 14's "use a dedicated demo bucket" (doubt 26; Object Lock now goes on the run-store bucket). Every check used WebSearch result snippets, because arxiv.org, export.arxiv.org and emergentmind.com did not resolve through WebFetch and curl to arxiv.org got a 403 from the proxy. data.source.coop and overpass-api.de were also blocked.

Result legend: **VERIFIED** = confirmed by the search evidence at the URL given; **VERIFIED-K** = matches a well-known bibliographic or doc fact, but no page could be fetched; **CORRECTED** = the fact differs from the doc or needs tightening; **UNVERIFIABLE** = no evidence found with the tools available.

| # | Claim | Where in doc | Result | Evidence URL | Suggested doc edit |
|---|---|---|---|---|---|
| 1 | Strands Agents is OpenTelemetry-native | A3 | VERIFIED. Traces use the OTel standard; spans cover LLM calls, tools and the event loop; `gen_ai.*` attribute names; OTLP export through the `otel` extra and `OTEL_EXPORTER_OTLP_ENDPOINT`. | https://strandsagents.com/docs/user-guide/observability-evaluation/traces/ | Add "install `strands-agents[otel]`" to the hour-0 probe. |
| 2 | Strands provider matrix ("sources disagreed") | A3 | VERIFIED. Lists differ by doc version and by language (Python vs TypeScript). The current SDK docs list Amazon Bedrock, Anthropic, OpenAI (+Responses), Google, Ollama, LiteLLM, Mistral, Llama API, llama.cpp, SageMaker, Writer, Vercel, plus a **custom provider** (subclass the abstract `Model`). | https://strandsagents.com/docs/user-guide/sdk/model-providers/ ; https://strandsagents.com/latest/user-guide/concepts/model-providers/custom_model_provider | Replace "sources disagreed" with "matrix differs by doc version and Python/TS; Python has native Ollama, OpenAI, LiteLLM and a custom-provider base class". |
| 3 | OTel GenAI semconv is "Development" status | A4 | VERIFIED. The agent-spans page shows Status: Development. Per Dash0, all `gen_ai.*` signals are Development. | https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans ; https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained | Remove "(unverified in this pass)". |
| 4 | Span names `invoke_agent` root, `chat` and `execute_tool` children | A4 | VERIFIED. `invoke_agent` is the operation name; the span name is `invoke_agent {gen_ai.agent.name}` (bare `invoke_agent` if no name); kind CLIENT, may be INTERNAL. `execute_tool` is a defined operation (span `execute_tool {gen_ai.tool.name}`). `chat` is an inference operation (span `chat {gen_ai.request.model}`). | Same as row 3; https://nango.dev/blog/opentelemetry-ai-agent-observability | State that span *names* carry a suffix (agent, tool or model name); match on `gen_ai.operation.name`, not on the span name. |
| 5 | OTel source URL / location of the GenAI conventions | Sources ("Tracing"), A4 | CORRECTED. A secondary source (Dash0) says the conventions moved out of the core semconv repo into a dedicated `open-telemetry/semantic-conventions-genai` repo on 12 June 2026 (v1.42.0). The repo itself was not fetched. | https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained | Cite the `semantic-conventions-genai` repo and **pin that repo's version** in the manifest, not the core semconv version. |
| 6 | Bedrock batch is about half price | A8 | VERIFIED for **select** models (Anthropic, Meta, Mistral, Amazon): 50% of on-demand. Announced 21 Aug 2024; the current pricing page still says so. | https://aws.amazon.com/about-aws/whats-new/2024/08/amazon-bedrock-fms-batch-inference-50-price/ ; https://aws.amazon.com/bedrock/pricing/ | "about half price for select models". |
| 7 | Bedrock batch "up to about 24 h" | A8 | VERIFIED. "Typical job within 24 hours" (not a guarantee). | Same as row 6 | None. |
| 8 | Bedrock batch has "uneven image/model support" | A8, A10 | UNVERIFIABLE. The batch support table has no input-modality column, so image support per model cannot be confirmed. | https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-supported.html | Keep "Coverage UNVERIFIED". The probe should submit a 1-record image batch job. |
| 9 | Invocation logging can be set to text and metadata only, with image delivery disabled | A4 | VERIFIED. `PutModelInvocationLoggingConfiguration` has the booleans `textDataDeliveryEnabled`, `imageDataDeliveryEnabled`, `embeddingDataDeliveryEnabled`, plus newer `videoDataDeliveryEnabled` / `audioDataDeliveryEnabled`. Destinations are S3 and/or CloudWatch, same account and region only. Logging is off by default. | https://botocore.readthedocs.io/reference/services/bedrock/client/put_model_invocation_logging_configuration.html | Name the flags: text=true; image, embedding, video, audio=false. The bucket must be in the same region as the Bedrock calls. |
| 10 | Lambda Function URL supports `AWS_IAM` auth | A9 | VERIFIED. AWS_IAM checks the caller's identity policy plus the resource policy; the caller needs `lambda:InvokeFunctionUrl`. | https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html | Note that callers must SigV4-sign requests, so a browser UI cannot call it unsigned. |
| 11 | "S3 static hosting likely collides with account Block Public Access" | A9 | CORRECTED (tighten). Since April 2023 **every new bucket** has bucket-level Block Public Access on and ACLs disabled, whatever the account setting. Account-level BPA, if set, blocks on top of that. | https://aws.amazon.com/about-aws/whats-new/2023/04/amazon-s3-security-best-practices-buckets-default | "Public S3 website hosting is blocked by default on new buckets (bucket-level BPA since Apr 2023) and may also be blocked at account level." |
| 12 | S3 Vectors GA (Dec 2025) | A10 (Stretch), Sources | VERIFIED. GA on 2 Dec 2025 (re:Invent), 14 regions. | https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/ | None. |
| 13 | Object Lock can be enabled on an existing versioned bucket since Nov 2023 | A4, A10 | VERIFIED. Announced 20 Nov 2023; no Support ticket needed. Enabling it does **not** retroactively lock existing objects. | https://aws.amazon.com/about-aws/whats-new/2023/11/amazon-s3-enabling-object-lock-buckets | Add: "objects written before enablement are not locked; the demo object must be written after enablement or given retention explicitly". |
| 14 | Object Lock cannot be disabled once on | A4 | VERIFIED-K (stated in the S3 Object Lock docs; not re-fetched). | https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-configure.html | Use a dedicated demo bucket, because the setting is permanent. |
| 15 | Object Lock buckets cannot be server-access-log destinations | A4 | VERIFIED. AWS docs: "S3 buckets that have S3 Object Lock enabled can't be used as destination buckets for server access logs", and the destination must not have a default retention or Requester Pays. | https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-server-access-logging.html ; https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html | Remove "(unverified in this pass)". |
| 16 | "Nine judges from seven families behave like about 2.2 independent votes" | A5 DECISION | VERIFIED. Kish n_eff = 2.18 on MNLI; range 1.9-2.5 across prompts, temperatures, chain-of-thought and RewardBench. The panel falls 7-22 pp short of the Condorcet prediction and never clearly beats the best single judge. The data is NLI text, not imagery. | https://huggingface.co/papers/2605.29800 ; https://machinelearning.apple.com/research/correlated-llm-evaluation-panels ; https://neurips.cc/virtual/2026/161256 | Replace "(unverified)" with "(Kohli 2026, arXiv 2605.29800; NLI tasks, n_eff 2.18)". |
| 17 | arXiv 2605.29800 | Sources | VERIFIED. "Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels", G. Kohli, 28 May 2026 (NeurIPS 2026 listing). | Same as row 16 | Remove "(unverified)"; add the title. |
| 18 | arXiv 2506.07962 | Sources | VERIFIED. "Correlated Errors in Large Language Models", Kim, Garg, Peng, Garg, June 2025, **ICML 2025**. | https://arxiv.org/abs/2506.07962v1 (via search) | Remove "(unverified)"; add the title. |
| 19 | icml.cc/virtual/2026/poster/61230 | Sources | UNVERIFIABLE. 2506.07962 is ICML **2025** and 2605.29800 is listed at NeurIPS 2026, so this ICML 2026 poster id does not match either known paper. | n/a | Drop it, or replace it with https://neurips.cc/virtual/2026/161256. |
| 20 | arXiv 2510.11977 | Sources (agent eval) | VERIFIED. "Holistic Agent Leaderboard: The Missing Infrastructure for AI Agent Evaluation", Kapoor et al., 13 Oct 2025. | https://arxiv.org/abs/2510.11977 (via search) | Remove "(unverified)"; add "(HAL)". |
| 21 | arXiv 2303.07334 ("spatial structure inflates random CV") | Sources | VERIFIED. "Assessing the performance of spatial cross-validation approaches for models of spatially structured data", Mahoney, Johnson, Silge, Frick, Kuhn, Beier (2023). The label is a fair paraphrase. | https://arxiv.org/abs/2303.07334 | Remove "(unverified)". |
| 22 | arXiv 2301.09633 (PPI) | Sources | VERIFIED. Angelopoulos, Bates, Fannjiang, Jordan, Zrnic. | https://arxiv.org/pdf/2301.09633 (search result) | None. |
| 23 | arXiv 2505.18659 ("adaptive PPI") | Sources | UNVERIFIABLE. No index hit for this id; arXiv blocked. | n/a | Keep "(unverified)" or drop it. Nothing in the design depends on it (lambda is fixed at 1). |
| 24 | arXiv 2510.04265 | Sources (agent eval) | UNVERIFIABLE. No index hit. | n/a | Keep "(unverified)"; the doc gives no label for it. |
| 25 | aclanthology 2026.cas-1.11 ("Dawid-Skene over-estimates LLM accuracy") | Sources | UNVERIFIABLE. The id was not found. Related work does support the claim: Dawid-Skene assumes conditional independence, which LLM judges violate (arXiv 2601.22336). | https://arxiv.org/html/2601.22336v1 | Keep "(unverified)", or cite 2601.22336 as support for "Dawid-Skene needs conditionally independent sources". |
| 26 | arena.ai/blog/llm-judge-self-preference | Sources | UNVERIFIABLE (not reachable within budget). | n/a | Keep "(unverified)". |
| 27 | arXiv 2311.01453 (PPI++) | Sources | VERIFIED-K (Angelopoulos, Duchi, Zrnic). | https://arxiv.org/abs/2311.01453 (not fetched) | None. |
| 28 | arXiv 2206.13089 (Agreement-on-the-Line) | Sources | VERIFIED-K (Baek, Jiang, Raghunathan, Kolter, NeurIPS 2022). | https://arxiv.org/abs/2206.13089 (not fetched) | None. |
| 29 | arXiv 1904.06019 (weighted conformal, covariate shift) | Sources | VERIFIED-K (Tibshirani, Barber, Candès, Ramdas). | https://arxiv.org/abs/1904.06019 (not fetched) | None. |
| 30 | arXiv 2005.07939 (Area of Applicability) | Sources | VERIFIED-K (Meyer and Pebesma, "Predicting into unknown space?"). | https://arxiv.org/abs/2005.07939 (not fetched) | None. |
| 31 | arXiv 2406.12045 (tau-bench) | Sources | VERIFIED-K (Yao, Shinn, Razavi, Narasimhan). | https://arxiv.org/abs/2406.12045 (not fetched) | None. |
| 32 | arXiv 1911.09296 (xBD) | Sources | VERIFIED. "xBD: A Dataset for Assessing Building Damage from Satellite Imagery". | https://ar5iv.labs.arxiv.org/html/1911.09296 (search result) | None. |
| 33 | arXiv 2404.13076 (self-preference) | Sources | VERIFIED-K ("LLM Evaluators Recognize and Favor Their Own Generations", Panickssery, Bowman, Feng). | https://arxiv.org/abs/2404.13076 (not fetched) | None. |
| 34 | arXiv 2410.10934 | Sources | VERIFIED-K ("Agent-as-a-Judge: Evaluate Agents with Agents", Zhuge et al.). | https://arxiv.org/abs/2410.10934 (not fetched) | None. |
| 35 | arXiv 2305.04388 | Sources | VERIFIED-K ("Language Models Don't Always Say What They Think", Turpin et al.). This supports "reasoning stored, never scored". | https://arxiv.org/abs/2305.04388 (not fetched) | None. |
| 36 | arXiv 2411.00640 | Sources | VERIFIED-K ("Adding Error Bars to Evals", E. Miller). | https://arxiv.org/abs/2411.00640 (not fetched) | None. |
| 37 | USPVDB license / redistribution | A4, A12 demo task 1 | VERIFIED. **Public domain** (USGS says "free and in the public domain"; the v3.0 data release is marked CC0 1.0). Acknowledgment is requested, not required. Redistribution is allowed. | https://energy.usgs.gov/uspvdb ; https://www.usgs.gov/data/united-states-large-scale-solar-photovoltaic-database-ver-30-april-2025 | Replace "USPVDB ... redistribution terms UNVERIFIED" with "USPVDB: public domain (CC0), attribution requested". SPDX `CC0-1.0`. |
| 38 | USPVDB site is up / current version | A12 | VERIFIED (indexed; live reachability from this container not tested). Current release is **V4.0, April 2026** (6,611 facilities, file `USPVDB_V4_0_20260415`). All versions are at doi:10.5066/P9IA3TUS. | https://www.usgs.gov/data/united-states-large-scale-solar-photovoltaic-database-ver-40-april-2026 ; https://eta-publications.lbl.gov/publications/us-large-scale-solar-photovoltaic | Pin "USPVDB V4.0 (2026-04-15)" in the Virginia card. Date-align NAIP to it (NAIP on AWS runs only to about 2023). |
| 39 | NAIP on AWS requester-pays status | A12 demo task 1 | VERIFIED: **it is Requester Pays.** `naip-analytic` (MRF) and `naip-visualization` (RGB COG) are in us-west-2, plus legacy `aws-naip` in us-east-1. Requests need `RequestPayer=requester` and AWS credentials. Egress is charged outside us-west-2. Coverage is about 2010-2023. | https://registry.opendata.aws/naip/ | Change the open item to "NAIP on AWS is requester-pays: signed requests plus `AWS_REQUEST_PAYER=requester` are required; unsigned HTTP range reads will fail; the budget guard must count egress if run from the Mac". |
| 40 | NAIP license | A4 | VERIFIED. Public Domain with attribution. | https://registry.opendata.aws/naip/ | SPDX: public domain; cite "NAIP on AWS". |
| 41 | xBD is non-commercial | A7, A11 | CORRECTED (tighten). **CC BY-NC-SA 4.0**: non-commercial **and share-alike**. | https://huggingface.co/datasets/hannan022/xview2-xbd ; https://forums.fast.ai/t/interesting-challenge-project-xview2/58725 | "xBD is CC BY-NC-SA 4.0". |
| 42 | Wilson-interval citation: Brown, Cai, DasGupta 2001 | Sources | VERIFIED-K. "Interval Estimation for a Binomial Proportion", *Statistical Science* 16(2):101-133. Project Euclid id euclid.ss/1009213286 matches. | https://projecteuclid.org/euclid.ss/1009213286 (not fetched) | Optionally add the title, volume and pages. |
| 43 | Dawid and Skene 1979, JRSS C 28:20-28 | Sources | VERIFIED-K. "Maximum Likelihood Estimation of Observer Error-Rates Using the EM Algorithm", *JRSS Series C (Applied Statistics)* 28(1):20-28. The RePEc URL path matches. | https://ideas.repec.org/a/bla/jorssc/v28y1979i1p20-28.html (not fetched) | None. |

### Counts

- VERIFIED: 22
- VERIFIED-K (known record, not fetched because arXiv was blocked): 12
- CORRECTED: 3
- UNVERIFIABLE: 6

### Decisions affected by a corrected or resolved fact (as written by the fact-checker)

1. **A3/A12 `imagery_window` "implemented first as local HTTP range reads", with NAIP as the Virginia imagery: the basis is weakened.** NAIP on AWS is Requester Pays (row 39), so anonymous or unsigned HTTP range reads get 403. The keyed Virginia demo therefore needs AWS credentials wherever the reader runs. That ties it to the hour-0 execution-locus outcome (A10): if credentials cannot be exported to the Mac, NAIP reads must run in the Kiro terminal. Reads from outside us-west-2 also add egress cost the budget guard must count. NAIP on AWS also ends around 2023, while USPVDB V4.0 is April 2026, so date alignment needs a check. Mitigation (not verified here): use signed rasterio/GDAL reads with `AWS_REQUEST_PAYER=requester`, or another NAIP host.
2. **A4 "pin the semconv version": the decision stands, but the pin target changes.** If the GenAI conventions now live in `semantic-conventions-genai` (row 5, secondary source), the manifest should pin that repo's version. The CI frozen-trace test should match on `gen_ai.operation.name` (row 4), because span names carry agent, tool or model suffixes.
3. **A9 hosting: strengthened, not undermined.** Bucket-level BPA is on by default (row 11), so "not public S3" is required, not merely likely.

No other decision is undermined. Several are **strengthened**:
- The A5 different-family verifier decision now has a verified source (n_eff 2.18, row 16). That evidence is on NLI text, so it bears on, but does not measure, imagery verification.
- The A4 non-Object-Lock bucket for invocation logs is confirmed necessary for server access logs (row 15) and is consistent with the logging API flags (row 9).
- The A3 "other providers" Could item is cheaper than implied. Strands natively supports OpenAI (custom base URL), Ollama, LiteLLM and a custom `Model` subclass (row 2), so the OpenAI-compatible adapter is only needed for the plain Converse loop.
