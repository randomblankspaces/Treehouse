# Round (b): AWS architect, debate

## New evidence this round

I ran these in the same scratch venv as before, now with strands-agents 1.63, sockets blocked.

1. **Strands builds requests deterministically.** I ran a FakeModel-driven `strands.Agent` twice. The per-turn request hashes (messages, tool specs and system prompt, as canonical JSON) were identical.
2. **The default tool executor is a replay hazard.** `Agent.__init__` defaults to `ConcurrentToolExecutor()`. When the model makes parallel tool calls, tool results arrive in completion order, so cassette keys can differ between runs. `SequentialToolExecutor` exists and removes this.
3. **From round (a):** moto 5.2.5 reproduces put-once (`IfNoneMatch`), the HEAD compare-and-swap (`IfMatch`), and Object Lock `AccessDenied` on version deletes. CDK synth runs offline in 6.5 s.

## 1. Attacks

**A1. Plan size against the night.**
- OBS, STAT, RS and I each planned about 20 h of work. The overnight agent has 6–8 h.
- Three of those plans (OBS P10, RS P13, my P12) put the demo near the bottom, so "cut from the bottom" cuts the demo first.
- Only ADV fits the night: P0–P8 in 7.2 h, demo skeleton at P5, checkpoint at 04:30.
- But ADV's hour estimates are optimistic. Its trust package is costed at 1.3 h. STAT costs the same content at 5.5 h (sampling 1.5 + trust 2.5 + verifier 1.5). I expect ADV's night to take 9–10 h, so its checkpoint rule matters more than its estimates.

**A2. ADV: "no Kiro code beyond stubs" leaves the morning with nothing to run.**
- `BedrockProvider` sits in ADV's P11, after the overnight line, and the probe has no script at all. At 08:00 Kiro either writes this code, burning Suhas's AWS hours, or waits for it.
- Both the adapter and the probe can be tested offline tonight (Stubber, plus moto for the probe), about 1 h in total.
- I accept ADV's cut of CDK, Object Lock, IAM, CloudWatch and Lambda. I do not accept cutting the probe or the adapter.

**A3. OBS, STAT and ADV test the S3 store with Stubber alone.**
- Stubber only proves that we send `IfNoneMatch`. It cannot show that a second put raises, that a stale compare-and-swap fails, or that a version delete is denied. moto shows all three, and I ran them.
- Keep Stubber for Bedrock, Logs and Budgets.

**A4. ADV's "Strands is not replay-deterministic" is half right.**
- Request construction is deterministic (evidence 1). The real hazard is the concurrent executor (evidence 2).
- With `SequentialToolExecutor` in record and replay mode, OBS's `TreehouseStrandsModel` is safe for replay. The demo should still run on the plain loop.

**A5. The offline guards are incomplete.**
- The build container exports `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` set to `proxy-injected`, plus `AWS_CA_BUNDLE`.
- OBS overrides only the access key id. STAT and ADV override nothing.
- Any `@aws` or `@network` test that lifts the socket guard would sign requests with the proxy's credentials.
- Fix: scrub every `AWS_*` variable, then set fake values.

**A6. Mine is the only proposal with a cumulative, cross-run dollar guard.**
- OBS and ADV have per-run budgets. That does not stop twenty $20 runs from passing the $500 cap.
- SYSTEM-DESIGN A8 requires a hard stop at $450.

**A7. Replay must take tool results from the cassette, never re-read live.**
- RS found that the Vantor imagery files are JPEG-compressed, so pixel hashes vary between libjpeg/GDAL builds.
- OBS keys model requests on image sha256s, not raw bytes.
- So a replay that re-reads windows live on a judge's Mac would miss every cassette key.

**A8. Conflicts the overnight agent must not resolve ad hoc.**
- Module names: `tracing/` or `trace/`; `verify/` or `verifier/`; `score/` or `scoring/`.
- Verdict values: ADV uses `present|absent|cannot_assess`, STAT uses `yes|no|abstain`, and the Nepal damage step needs damaged or intact. I propose `yes|no|cannot_assess` per question, with a question id.
- OBS sets Bedrock concurrency to 4. The new account's quotas are unknown, so default to 2 and raise it only after the probe.

## 2. Concessions

1. **Package order.** I adopt ADV's ordering: demo skeleton at P5, the 04:30 checkpoint, P0–P8 overnight. My ordering was wrong.
2. **CDK, OTLP, CloudWatch Logs and Object Lock code move to Wednesday.** CDK is about 1 h of work and its synth stays testable offline. It must land before the CDK deploy step (K6).
3. **MEASURED tier (OBS).** I adopt it. My `UNPRICED` type becomes `tier=MEASURED, value=None, reason="unpriced"`.
4. **The plain loop is Must-0** and is the demo engine. Strands with the fake model comes after it and is cut before the demo is.
5. **Synthetic demo world.** I accept a synthetic keyed world stamped SYNTHETIC: RS's pixel-driven detector if it fits, otherwise ADV's rectangles. Nepal uses real STAC metadata plus synthetic gold labels, both labelled as such.
6. **Module names.** I adopt OBS's layout (`service.py`, import-boundary test, `trace/`, `checks/`, `score/`, `summary/`), plus STAT's `stats/` and `sampling/` and RS's `geo/` and `synth/`. My `budget/` package becomes `gateway/budget.py`.

## 3. Revised position

1. **[BLOCKING] A cumulative spend ledger, built tonight.**
   - It lives in `~/.treehouse/spend.jsonl` and is mirrored after each trial.
   - Before each live call it reserves the worst-case cost.
   - Thresholds: warn at $250; at $350 require a flag plus a logged reason; at $450 hard stop, replay only.
   - A model with a null price is refused for live calls.
   - A property test proves the ledger can never pass the hard stop.
2. **[BLOCKING] An "AWS-a" package tonight, about 1 h, right after P5.**
   - Contents: the Bedrock Converse adapter (Stubber tests); `scripts/aws_probe.py` (moto plus Stubber, with a golden `aws-capabilities.json` schema); the model registry; the dated price table with null prices.
   - If the night slips it may move below P8, but it must be merged before 08:00.
3. **[BLOCKING] `backends_resolved` comes from read-backs or live denial tests, never from config.**
   - "IAM-enforced" needs both: the caller is the worker role, and a canary read of the key bucket is denied.
4. **[BLOCKING] The offline guard.**
   - Scrub every `AWS_*` variable, then set fake credentials, `AWS_CONFIG_FILE=/dev/null` and `AWS_EC2_METADATA_DISABLED=true`.
   - Block sockets.
   - A canary test asserts that an unstubbed boto3 call raises.
5. **Replay demo.**
   - `treehouse demo` runs the plain loop on model and tool cassettes into a fresh local store.
   - It then seals, checks, scores, computes trust, renders the report and runs `verify`.
   - It never reads live pixels.
   - Strands record and replay always use `SequentialToolExecutor`.
6. **S3 store on Wednesday morning (0.5 h, before the S3 push step K7).**
   - Put-once writes plus a compare-and-swap HEAD on a versioned bucket.
   - Tested with moto. Strongly preferred, not blocking.
7. **Model ids are config only.**
   - Worker: Claude Sonnet 5.5 through a `us.` or `global.` inference profile. Verifier: Nova Pro. Both ids are UNVERIFIED.
   - The probe rewrites which models are available. The vision smoke test (K2) makes the choice.
   - The image delivery mode (inside the tool result, or as a user-turn attachment) is set per model.
8. **Kiro step order:**
   1. Probe.
   2. Prices and vision smoke test.
   3. Keyed run.
   4. Gold-seed commit, which must come before Nepal.
   5. Nepal run.
   6. Cassettes.
   7. CDK (written Wednesday).
   8. S3 push.
   9. Tracer check.
