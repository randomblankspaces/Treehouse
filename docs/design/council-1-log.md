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