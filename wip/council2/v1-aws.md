# Vote, round 1: AWS seat

VOTE: REJECT. One blocking item, fixable in one row. Everything else I accept as written.

All four of my blocking items from round (b) are met:
- **Cumulative spend ledger:** §3 `SpendLedger`, with planned 250, alarm 350 and hard stop 450, worst-case reservation, unpriced models refused, and a property test.
- **P6 AWS-a merged by 08:00:** row 4, with checkpoint C2.
- **`backends_resolved` needs evidence:** the §2 `BackendResolution` validator.
- **Offline guard:** row 17 and §6, which clear `AWS_*`, set fake credentials, and add a canary.

I also accept rows 13 (our own retry loop with botocore `max_attempts=1`), 15 and 16 (Stubber for the probe tonight, moto with S3Store in W5) and 30 (K3 before the vision smoke test).

## Blocking

**B1. The probe's live Bedrock calls collide with the unpriced-refusal rule (§7 P6 row, §8 K1/K2a order).**
- K1 runs the probe, including a 20-token text call and a 64×64 vision Converse call for each candidate model. K2a, which fills the price table, comes after K1.
- At K1 every price is therefore null. `SpendLedger.reserve()` refuses unpriced models unless `unpriced_cap_usd` is passed.
- As specified, one of two things happens:
  - every Bedrock check in K1 comes back "refused", so the probe cannot choose models, image-delivery mode or quotas; or
  - the overnight agent lets the probe bypass the ledger, so real spend escapes the $450 hard stop.
- Either way the build is wrong.

**Replacement text** for the P6 "contents" cell, appended after `aws_probe.py (Stubber)`:

> `aws_probe.py` makes every Bedrock call through `SpendLedger.reserve(..., unpriced_cap_usd=0.25)` per call, with `max_tokens ≤ 32`. The whole probe has a total cap of $3, after which the remaining Bedrock checks are reported as `skipped_budget`. Each reservation is committed to the ledger, using the actual `usage` and a conservative placeholder price from `config/prices/probe-ceiling.yaml`, tagged `estimated: true`. A Stubber test shows that the probe never calls Converse without a ledger reservation, and that the probe stops at the $3 cap.

Add to the P6 acceptance column: "probe Bedrock calls are reserved in the ledger; the cap is enforced (Stubber)."

## Non-blocking suggestions

1. **Make the ledger survive Kiro session resets.** S3 mirroring arrives only in W5. Until then, the Kiro preamble should set `TREEHOUSE_SPEND_LEDGER=$REPO/.spend/spend.jsonl` and commit and push it after each K step. The file holds no secrets. Otherwise a container reset silently brings the guard back to $0.
2. **Add an AWS Budgets alert at $350.** Fold `budgets:CreateBudget` (ACTUAL 100%, FORECASTED 90%) into K1 if the account permits it. Billing lags by hours, so the ledger stays the control of record.
3. **Fill the price table more efficiently.** Have `prices check` print the exact rows that K2a must fill: available models with no price, taken from `aws-capabilities.json`. That way Kiro fills only those rows.
4. **Pin the record-mode tool executor.** Have `--mode record` in W2 assert `SequentialToolExecutor`. The default `ConcurrentToolExecutor` reorders results.
5. **Keep the AWS docs status honest.** Note in §9 that the AWS documentation was not fetched in this council: the docs host was blocked. The OTLP endpoint, Transaction Search and per-model image-in-`toolResult` support are UNVERIFIED until K1 and K9.
