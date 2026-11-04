# Council 2, round (a): STAT (statistician) implementation proposal

Scope: all of I1-I9. Most of the detail is on `treehouse.stats`, `treehouse.sampling`, `treehouse.trust` and the tests for the unkeyed-verification methods. Nothing here changes SYSTEM-DESIGN.md. Where the spec leaves a numeric choice open, I fill it with a **pre-registered constant** in `TrustConfig`. One frozen object holds those constants, and its hash goes into every passport.

## 0. Prototype evidence (run tonight, numpy 2.5 / scipy 1.18, about 10 s total)

I prototyped the PPI interval and Rogan-Gladen in the scratchpad (`council2/proto/ppi2.py`, `rg.py`). Setup: N=60 claims in 3 strata, n_gold=20, 90% nominal level, 300 seeded populations per scenario.

| Scenario | Naive rescaled bootstrap | **+ half-unit pseudo-disagreements (adopted)** | Exact hypergeometric, gold only |
|---|---|---|---|
| Moderate verifier (Se .85 / Sp .70, 5-35% abstain) | 0.86 cov, width .25 | **0.90, .28** | 0.96, .27 |
| Shuffled verifier (useless) | 0.87, .33 | **0.90, .34** | 0.94, .27 |
| Strong verifier (.95/.90) | **0.76**, .14 | **0.98, .20** | 0.94, .27 |
| Perfect verifier | **0.60**, .00 | **1.00, .13** | 0.97, .27 |
| High precision (0.9-0.97) | 0.83, .15 | **0.90, .17** | 0.99, .17 |
| Two-phase (N=300, n=60) | 0.90, .29 | **0.93, .32** | n/a |

Three findings, each of which changes what we build:
1. **The textbook bootstrap under-covers badly when the verifier is good.** The rectifier (human minus verifier) is all zeros in a stratum, so its variance collapses. Fixes: pool the rectifier across strata while n_gold < 50, and add two half-weight pseudo-disagreements (d=+1, d=-1) **to the variance only, never to the point estimate**. With both, coverage was at least 0.897 in every scenario.
2. **With n_gold=20 and λ=1, a moderate verifier does not narrow the interval at all, and a useless one widens it (.34 vs .27).** The passport must therefore print the classical gold-only interval next to the PPI one, along with the width ratio. Narrowing is shown when it happens, never assumed.
3. **Rogan-Gladen with 15+15 controls is about ±0.24 wide.** Inflation helps under shift (0.78 → 0.82 coverage at a 0.7-logit shift) but does not restore nominal coverage, so the CALIBRATED-TRANSFER cap is justified. A weak verifier (J≈0.15) triggered the abstain rule in 98% of draws, which is the intended behaviour.

---

## I1. Repo and module layout

```
pyproject.toml (uv, requires-python>=3.12, ruff, pytest; extras: aws=[boto3], strands=[strands-agents], mcp=[mcp], geo=[rasterio])
src/treehouse/
  schemas/      task.py manifest.py trace.py claim.py ledger.py numbers.py passport.py scorecard.py
  stats/        intervals.py bootstrap.py tests.py agreement.py shift.py   # numpy/scipy only, no treehouse imports except schemas.numbers
  sampling/     frame.py design.py gold.py batch.py geo.py                 # numpy only
  trust/        config.py ppi.py rogan_gladen.py baselines.py tiers.py passport.py controls.py
  providers/    base.py fake.py cassette.py bedrock.py openai_compat.py
  harness/      base.py plain_loop.py strands_adapter.py
  tools/        gateway.py imagery_window.py stac.py clay_search.py record_claim.py server.py
  trace/        tracer.py chain.py otlp.py
  store/        base.py local_cas.py s3.py
  checks/       rules.py keyed.py verifier.py leak.py
  score/        panels.py summary.py report.py
  api/          cli.py mcp_server.py
tests/{unit,method,golden,integration}/   fixtures/{cards,keys,traces,cassettes,frames,embeddings}
prereg/  primary.yaml  gold-seed.txt  trust-config.yaml     estimators.lock
```

Rule: `stats` and `sampling` are leaf packages, pure functions over arrays, with no I/O and no pydantic in hot loops. `trust` adapts them to the schemas. That keeps the method tests fast and keeps the estimator easy to freeze.

## I2. Core schemas (Pydantic v2, `extra="forbid"`, frozen)

My seat cares most about these:

```python
class Interval(BaseModel):
    lo: float; hi: float; level: float
    method: str            # "wilson" | "clopper-pearson" | "hypergeom-exact" | "ppi-2phase-rbs-v1" | "cluster-bootstrap" | "rg-bootstrap-inflated-v1" | "betabinom-predictive"
    B: int | None = None; seed: int | None = None; fpc: bool = False

class TypedNumber(BaseModel):
    value: float | None                    # None iff tier == ABSTAINED
    type: Literal["precision","recall","f1","status_accuracy","count","miss_rate","rate","cost_usd","seconds","bytes","p_correct"]
    tier: Literal["KEYED","GOLD-ANCHORED","CALIBRATED-TRANSFER","MODEL-ESTIMATED","ABSTAINED"]
    rung: Literal["L1","L2","L3","L4"] | None = None
    n: int; n_gold: int | None = None; n_verified: int | None = None; abstention_rate: float | None = None
    interval: Interval | None
    estimator_version: str; config_hash: str; manifest_ref: str
    reasons: list[str] = []                # abstain reasons, caps ("self-checked", "estimators disagree")
```

`TrustPassport` holds: estimand, headline (TypedNumber), `alternatives` (list of TypedNumber: classical gold-only, RG, B0, B1, B2), `width_ratio_ppi_vs_classical`, `disagreement` (list of pairs), gate (`Rely | Spot-check | Do not rely`), `controls` (Se/Sp, placebo FAR, test-retest kappa, each with n and an `anecdotal` flag when n<10), shift (number, percentile or "ruler not computable: k keyed regions"), `beat_baseline` ("not computable: 1 keyed regime" or a table), `sample_design_id`, `gold_draw_id`, `trust_config_hash`, `code_sha256`.

`SampleDesign` / `GoldDraw` (see I3) are schemas too, because they are stored. The other schemas (TaskCard, RunConfig/EvalSpec, Manifest, Span, Claim, CheckLedger, VerifierVerdict with `verdict ∈ {yes,no,abstain}`, GoldLabel with `labeller`, `blind=True`, `sealed_at`) follow SYSTEM-DESIGN A2/A4/A5 field for field. I leave their detail to the AGENT-EVAL and AWS seats.

## I3. Interfaces and implementations

### Non-stats seams (short)
- `ModelProvider.converse(messages, tools, params) -> ModelTurn`. Implementations: `FakeProvider` (scripted turns), `CassetteProvider` (content-addressed replay, miss → error), `BedrockProvider` (boto3 Converse with backoff, tested with `botocore.stub.Stubber`), `OpenAICompatProvider` (httpx, Could).
- `Harness.run(task, config, tracer, budget) -> RunResult`. Implementations: `PlainLoop`, and `StrandsHarness` (a `strands.models.model.Model` subclass that wraps our provider, so the FakeProvider drives a real Strands Agent offline).
- `Tracer.emit(span)`: hash-chained JSONL, one file per trial; `OtlpTracer` is optional.
- `ToolGateway`: wraps an in-process `MCPServer`; owns the deny-list, `as_of`, metering and `key_access_attempt` spans.
- `Store.put(bytes)->sha256`, `seal(run_dir)`, `verify()`: `LocalCAS`, plus `S3Store` (versioned, Object Lock if probed).
- `Scorer(sealed_run, eval_ctx) -> Panel`; `Verifier.check(blind_batch) -> list[VerifierVerdict]`; `TrustEngine.passport(estimand, evidence, cfg) -> TrustPassport`; `Summarizer`.

### `treehouse.stats` (exact signatures)
```python
# intervals.py
def wilson(k: int, n: int, level: float = 0.95) -> Interval
def clopper_pearson(k: int, n: int, level: float = 0.95) -> Interval
def hypergeom_exact(k: int, n: int, N: int, level: float = 0.90) -> Interval
    # SRSWOR of n from N, k successes; inverts scipy.stats.hypergeom over K=0..N; exact FPC.
def poisson_binomial_interval(p: np.ndarray, level: float = 0.90) -> Interval   # DP convolution; used by B1
def interval_score(lo: np.ndarray, hi: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray  # Gneiting-Raftery

# bootstrap.py
@dataclass(frozen=True)
class Estimate: point: float; interval: Interval; n: int; extra: dict
def cluster_bootstrap(values: np.ndarray, clusters: np.ndarray, *, stat: Callable[[np.ndarray, np.ndarray], float] = weighted_mean,
                      weights: np.ndarray | None = None, B: int = 2000, level: float = 0.95, seed: int) -> Estimate
def paired_bootstrap_diff(a: np.ndarray, b: np.ndarray, clusters: np.ndarray, *, B: int = 2000, level: float = 0.95, seed: int) -> Estimate
    # a, b aligned on (task, data snapshot, trial seed); resamples clusters of paired differences
def block_bootstrap_spatial(values, xy: np.ndarray, block_m: float, **kw) -> Estimate     # clusters = grid blocks, then cluster_bootstrap

# tests.py
@dataclass(frozen=True)
class PermResult: p: float; effect: float; effect_name: str; exact: bool; n_perm: int
def permutation_test(a: np.ndarray, b: np.ndarray, *, paired: bool, clusters: np.ndarray | None = None,
                     n_perm: int = 9999, seed: int, alternative: Literal["two-sided","greater","less"] = "two-sided") -> PermResult
    # paired: cluster-level sign flips, exact enumeration when n_clusters <= 16; unpaired: label shuffles; effect = mean diff (+ Hedges g in extra)
def holm(pvalues: Mapping[str, float], alpha: float = 0.05) -> dict[str, tuple[float, float, bool]]   # name -> (p_raw, p_adj, reject)
def mde_paired(sd_diff: float, n: int, alpha: float = 0.05, power: float = 0.8) -> float

# agreement.py
def cohen_kappa(a: Sequence, b: Sequence, *, B: int = 2000, seed: int) -> Estimate      # + percent agreement in extra; flags n<10 anecdotal
def error_phi(err_worker: np.ndarray, err_verifier: np.ndarray, *, B: int, seed: int) -> Estimate   # A5 "measure, do not assume"

# shift.py
def energy_distance(X: np.ndarray, Y: np.ndarray) -> float                 # multivariate, numpy pairwise (scipy's is 1-D only)
def shift_percentile(target: np.ndarray, keyed: Mapping[str, np.ndarray]) -> tuple[float, float | None, str]
    # (distance to nearest keyed, percentile among keyed-to-keyed distances or None if <2 keyed regions, nearest region name)
```

### `treehouse.sampling` (design-based; Olofsson style)
```python
@dataclass(frozen=True) class FrameUnit: unit_id: str; kind: Literal["claim","unreported","clay_skipped","key_candidate"]; stratum: str; lon: float; lat: float; attrs: dict
@dataclass(frozen=True) class SampledUnit: unit_id: str; stratum: str; pi: float; order: int
@dataclass(frozen=True) class SampleDesign: design_id: str; seed: int; rng: str = "numpy.PCG64"; algorithm: str = "strat-srswor-v1"
                                            frame_hash: str; N_h: dict[str,int]; n_h: dict[str,int]; units: tuple[SampledUnit, ...]

def assign_strata(claims: Sequence[Claim], scene_cloud: Mapping[str, float], *, min_N_h: int = 4,
                  collapse_order: tuple[str, ...] = ("cloud_class", "conf_tercile")) -> dict[str, str]
    # class x confidence tercile x cloud class (<5%, >=5%); deterministic collapse of strata with N_h < min_N_h, dropping keys in collapse_order
def allocate(N_h: Mapping[str, int], n_total: int, *, min_per_stratum: int = 2, census_if_N_le: int = 60) -> dict[str, int]
def stratified_sample(frame: Sequence[FrameUnit], n_h: Mapping[str, int], *, seed: int) -> SampleDesign     # pi = n_h/N_h stored per unit
def unreported_frame(aoi: list[tuple[float,float]], corridors: Sequence[list[tuple[float,float]]], claims_lonlat: np.ndarray, *,
                     spacing_m: float = 250, exclusion_m: float = 150, seed: int,
                     clay_skipped: np.ndarray | None = None) -> list[FrameUnit]
    # seeded random-offset grid inside corridor polygons (numpy ray casting, local equirectangular metres),
    # minus points within exclusion_m of any claim; skipped Clay candidates form stratum "clay_skipped"
def draw_gold(design: SampleDesign, n_gold: int, *, seed: int, committed_ref: str) -> GoldDraw
    # SRSWOR from ALL sampled units (abstentions included, since verdicts do not exist yet); pooled while n_gold<50, else stratified;
    # stores pi2 = n_gold/n and joint pi; committed_ref = git commit of prereg/gold-seed.txt
def assemble_verifier_batch(design: SampleDesign, controls: Sequence[ControlItem], *, seed: int, hmac_key: bytes) -> tuple[list[BlindItem], SealedMap]
    # shuffled; opaque HMAC ids; BlindItem has ONLY (opaque_id, lon, lat, object_definition, scene_ids); SealedMap stored separately
def ht_mean(y: np.ndarray, pi: np.ndarray, N: int) -> float
```

### `treehouse.trust`
**PPI estimator (two-phase, design-based).** Notation: U is the whole claim table (or the unreported frame, as a separate estimand), with strata h of size N_h and weights W_h = N_h/N. Phase 1: SRSWOR S, π_i = n_h/N_h. Phase 2: SRSWOR G ⊂ S of size n_G. The predictor is f_i = 1 (yes), 0 (no), or for an abstention m_h, the mean of non-abstained verdicts in stratum h within S (pooled mean if none; 0.5 if no verdicts at all). Because f depends only on phase-1 data, the rectifier stays unbiased.

θ̂_λ = λ Σ_h W_h f̄_{S_h} + Σ_{i∈G} w_i (y_i − λ f_i) / Σ_{i∈G} w_i, with w_i = 1/π_i.

λ = 1 whenever n_G < 50. For n_G ≥ 50: two-fold cross-fitted λ̂ = clip(Cov(y,f) / ((1+n_G/n) Var f), 0, 1).

Interval (`ppi-2phase-rbs-v1`), with B = 2000 in production:
1. Draw replicates by resampling S with replacement within strata; gold flags travel with their units.
2. Compute the analytic two-phase variance V̂ = Σ_h W_h² (1 − n_h/N_h) s²_y/n_h + (1 − n_G/n) s²_d/n_G,eff. Compute s²_y and s²_d after appending two half-weight pseudo-units (d=+1 and d=−1; y=1 and y=0).
3. Rescale the replicate deviations by r = √(V̂ / Var*(θ*)). This is where the FPC and the small-n floor enter.
4. Take the percentile interval and clip it to [0,1]. If Var* = 0, use θ̂ ± t_{n_G−1} √V̂ instead.

The classical comparator is `hypergeom_exact` when the verifier pass is a single-stratum census, otherwise the same machinery with f ≡ 0.

```python
@dataclass(frozen=True) class TrustConfig: level: float = 0.90; B: int = 2000; pseudo_weight: float = 0.5; lam_fixed_below: int = 50
    j_min: float = 0.2; tau_floor: float = 0.5; kappa0: float = 10.0; min_runs_mle: int = 3; g_min_label: int = 5
    max_abstention_for_rely: float = 0.3; placebo_far_max: float = 0.10; anecdotal_below: int = 10
def predictor_values(verdicts: Sequence[str], strata: Sequence[str]) -> tuple[np.ndarray, np.ndarray]   # (f, abstain_mask)
def ppi_mean(design: SampleDesign, gold: GoldDraw, verdicts: Mapping[str, str], y_gold: Mapping[str, int], *,
             cfg: TrustConfig, seed: int) -> PPIResult   # estimate, classical, abstention_rate (HT, with Wilson), n_gold, n_verified, lam, width_ratio
def ppi_total(...) -> PPIResult        # N * mean, for "N bridges damaged"
def rogan_gladen(apparent_k: int, apparent_n: int, se_counts: Sequence[tuple[int,int]], sp_counts: Sequence[tuple[int,int]], *,
                 estimand_kind: Literal["existence","damage_state"], cfg: TrustConfig, seed: int) -> RGResult
    # raises ValueError for damage_state (existence only, by construction)
    # pi = clip((p_a + Sp - 1)/(Se + Sp - 1)); bootstrap: binomial p_a*, Jeffreys Beta Se*/Sp*, then logit-normal inflation
    # tau = max(tau_floor, DerSimonian-Laird between-regime SD of logit Se, Sp) when >= 2 regimes, else tau_floor
    # ABSTAIN if the alpha/2 quantile of J* = Se*+Sp*-1 <= j_min; reports clipped fraction
def betabinom_fit(k: np.ndarray, n: np.ndarray, *, cfg: TrustConfig) -> BBFit          # MLE on (log a, log b) via scipy.optimize when runs >= 3, else mu=(sum k+1)/(sum n+2), kappa=kappa0
def betabinom_predictive(fit: BBFit, n_new: int, level: float) -> Interval              # scipy.stats.betabinom quantiles / n_new
def baseline_b0(keyed_runs: Sequence[KeyedRun], family, model, harness, toolset, n_new, cfg) -> TypedNumber | None
def baseline_b1(confidences: np.ndarray, level) -> TypedNumber                          # Poisson-binomial "the agent's own claim"
def baseline_b2(keyed_runs, model, harness, n_new, cfg) -> TypedNumber                  # defaults to Beta(1,1) mean, kappa0 -> wide
def select_tier(ev: EvidenceBundle, cfg: TrustConfig) -> TierDecision
def disagreements(estimates: Sequence[TypedNumber]) -> list[tuple[str, str]]
def gate(headline: TypedNumber, threshold: float, disagree: bool, cfg: TrustConfig) -> Literal["Rely","Spot-check","Do not rely"]
def build_passport(estimand: Estimand, ev: EvidenceBundle, cfg: TrustConfig, *, seed: int) -> TrustPassport
```

**Tier ladder (`select_tier`, first match wins, reasons recorded).**
1. The key covers the estimand → **KEYED** (L1).
2. n_gold ≥ 1 random gold, `gold.committed_at` earlier than the first verdict's `created_at`, blind protocol recorded, gold drawn from the full S → **GOLD-ANCHORED**. Rung L3, or L2 if `allow_same_family`. Below `g_min_label`=5 the chip adds "n_gold=k, anecdotal", but the method does not switch. If the ordering or blinding check fails → downgrade with reason `gold-not-precommitted`.
3. Verifier sample plus calibration for this `family`, estimand is existence, and RG did not abstain → **CALIBRATED-TRANSFER**. Capped at Spot-check. Becomes "self-checked" if same-family with no gold.
4. Keyed runs exist for (model, harness) → **MODEL-ESTIMATED** using the B2 interval. The Bayesian logistic prior is a Should.
5. Otherwise, or if the shift percentile is above 95 with no gold → **ABSTAINED**.

**Combination rule.** The passport computes every available estimator. The headline is the highest tier. `disagreements` runs over all pairs in {KEYED, PPI, classical, RG, MODEL-ESTIMATED, B0 (same family only)}; B1 is shown as "agent's claim" with its calibration gap and excluded. Any non-overlapping pair adds the reason "estimators disagree: treat as unverified", caps confidence at LOW and forces "Do not rely".

**Gate.**
- **Rely**: tier ∈ {KEYED, GOLD-ANCHORED}, lo ≥ threshold, no disagreement, abstention ≤ 0.3, placebo FAR upper bound ≤ 0.10 where measured.
- **Spot-check**: hi ≥ threshold.
- **Do not rely**: otherwise.

**Controls (`trust/controls.py`).**
- Se and Sp: Clopper-Pearson on keyed controls.
- Placebo false-alarm rate: Clopper-Pearson on "damaged" verdicts for pre/pre pairs.
- Test-retest: kappa on post/post pairs.
- Gold re-labels: kappa with n=5, flagged anecdotal.

**Freezing.** `ESTIMATOR_VERSION = "trust-1.0.0"`. `estimators.lock` stores the sha256 of the normalized source of `stats/`, `sampling/` and `trust/`, plus the `TrustConfig` hash. A test fails if the source changes without a version bump.

## I4. Storage layout (local CAS; S3 mirrors the same keys)
```
store/cas/sha256/ab/cdef...        blobs (tool payloads, crops kept in private cache dir only for Vantor)
store/runs/<run_id>/trial-<k>.jsonl  manifest.json (chains trial heads, prev manifest)  claims.jsonl  task.yaml
store/designs/<design_id>.json      store/gold/<draw_id>.json      store/labels/<labeller>/<sealed_at>.jsonl
store/evals/<run_id>/<scorer>@<ver>/<key_ver>/record.json         (append-only)
store/verdicts/<run_id>/<verifier_cfg_hash>/<design_id>.jsonl
store/passports/<run_id>/<estimator_version>/<seed>.json           reports/<run_id>/{report.html,bundle.json}
keys/ (outside the worker volume; manifest says "local convention, not IAM-enforced")
```

## I5. CLI / API / MCP
- CLI (typer): `treehouse task init|validate`, `run`, `check`, `sample` (writes design and gold draw; refuses if `prereg/gold-seed.txt` is uncommitted), `label` (static blind page/CSV export and import), `score`, `trust`, `verify`, `replay`, `report`, `compare`, `prereg commit`.
- MCP is a read-only `MCPServer` over the bundle (A9 tool list). Every numeric field is returned as a TypedNumber dict.
- API: FastAPI, Should.

## I6. Test strategy

**Offline guarantee.** An autouse `conftest.py` fixture monkeypatches `socket.socket.connect` and `getaddrinfo` to raise, except under `@pytest.mark.network`, which is deselected by default. `TREEHOUSE_OFFLINE=1` makes providers refuse anything other than fake or cassette.

**Determinism.** Every method test uses `SEEDS` from `tests/method/seeds.py` and `np.random.default_rng(seed)`. The numpy version is pinned in `uv.lock`, because Generator stream stability is not promised across numpy versions. Tolerances sit about 2.3 SE inside the nominal value, so a seed change rarely flips a result. Under the fixed seed every result is bit-reproducible. The method tests use R≈300 synthetic populations and B=400, vectorized with index matrices. The measured cost in the prototype was about 0.3 s per PPI scenario and 0.15 s per RG scenario. Budget: **`pytest -m method` under 6 s; the whole suite under 10 s**. A `-m slow` variant (R=3000, B=2000, 20 seeds) runs before the freeze, not in CI.

**Exact tests (no simulation; coverage computed from pmfs).**
- `hypergeom_exact` and `clopper_pearson`: coverage ≥ 1−α for every K in 0..N (N=60, n=20) and every p on a 0.01 grid (n ∈ {5,10,20,40}). The prototype gave a hypergeometric minimum of 0.916 at 90%.
- `wilson`: average coverage over a p grid between 0.93 and 0.97 at n=20 and 95%, minimum ≥ 0.83.
- `holm`: textbook vector reproduced exactly; adjusted p monotone; FWER ≤ 0.05 + 0.02 over 2000 global-null draws of m=5.
- Permutation exact: n=5, all diffs positive → p=0.0625 two-sided; under the null over 400 sims, the share of p<0.05 lies between 0.025 and 0.075.
- `poisson_binomial_interval` matches Monte Carlo quantiles to ±1 count.

**Simulation tests with known ground truth (`tests/method/`).**
| Test | Construction | Pass criterion |
|---|---|---|
| PPI coverage | 6 scenarios from §0 (moderate, shuffled, strong, perfect, high-precision, two-phase), abstention correlated with cloud stratum | coverage ≥ 0.86 in each; ≤ 0.995 except "perfect" |
| **Test-has-power (mutation)** | same harness with `pseudo_weight=0` | coverage < 0.80 in "perfect" and "strong" (proves the coverage test catches the known bug) |
| PPI narrowing is real, not asserted | strong verifier | mean width ≤ 0.85 × classical exact |
| **Shuffled-label null** | permute verdicts across units | coverage ≥ 0.86 **and** mean width ≥ 0.95 × classical (no fake narrowing); MODEL-ESTIMATED with shuffled features: width ≥ B2 width |
| Abstention as third category | abstention 35% in the hardest stratum, correlated with error | coverage holds; a variant that drops abstentions from G is biased (|bias| > 0.04) → documents why the rule exists |
| Gold from adjudication queue (forbidden) | gold drawn from disagreements | coverage < 0.7 → `select_tier` must refuse a GoldDraw without `committed_ref`/random design |
| Design-based sampling | 5000 seeded draws of `stratified_sample` | empirical inclusion frequency within 4 SE of stored π for every unit; Σπ = n; HT mean unbiased within 3 SE; same seed → identical `design_id`; different seed → different |
| Unreported frame | synthetic L-shaped corridor polygon, 3 claims | all points inside polygon, none within exclusion_m of claims, count within ±5% of area/spacing²; seeded and reproducible |
| **Planted-error monotonicity** | keyed synthetic table of 60; flip k ∈ {0,6,12,18,24} correct claims to wrong; verifier Se/Sp fixed, gold = key on a random 20 | mean PPI estimate over 50 reps strictly decreasing; Spearman ≤ −0.9; RG slope vs true rate in [−1.2, −0.8] while raw verifier rate slope ≈ −J (attenuated) |
| **Placebo false alarm** | verifier stub says "damaged" on pre/pre pairs with q ∈ {0, 0.1, 0.3}; plus "always damaged" stub | Clopper-Pearson covers q at nominal; always-damaged → passport reason `verifier-fails-placebo`, gate never Rely |
| **Test-retest** | post/post pairs with agreement prob a | kappa estimate within 0.1 of truth at n=200; n=5 → `anecdotal=True`; estimator retest: same inputs + seed → byte-identical passport JSON; different bootstrap seed at B=2000 → endpoints move < 0.02 |
| Rogan-Gladen | prevalence 0.7, Se .85, Sp .8, 15+15 controls | no-shift coverage ≥ 0.86; with shift, τ=0.5 coverage ≥ τ=0 coverage and width larger; weak verifier (J≈0.15) abstains ≥ 90%; `damage_state` raises |
| Cluster bootstrap | 12 clusters × 8 items, ICC 0.3 | cluster CI coverage ≥ 0.85 at 95%; naive iid bootstrap coverage < 0.85 (documents the unit-of-inference rule) |
| Paired bootstrap / permutation | paired diffs with known δ | coverage of δ ≥ 0.88 at 95%; null rejection rate in [0.02, 0.08] |
| Beta-binomial baselines | 30 runs from known (a,b) | MLE μ within 0.03, κ within factor 2; 1 run → `kappa0` path, predictive width ≥ 0.4; B2 default with no data ≈ wide |
| Tier ladder and disagreement | table-driven EvidenceBundles (about 15 rows) | exact tier, rung and reasons; non-overlap → "estimators disagree", gate "Do not rely" |
| Shift ruler | 1 keyed region | percentile None, label "ruler not computable: 1 keyed region"; synthetic shifted Gaussians → monotone distance |

**Pipeline-level checks in replay mode (`tests/integration/`, FakeProvider plus cassettes).**
- Evidence-in-trace: synthetic traces where the bbox contains the claim / merely overlaps / was never fetched → pass / fabrication flag / ungrounded.
- Forbidden source: worker calls a denied host → `key_access_attempt` span, item marked contaminated, process score reduced.
- Leak: a claim matching a key item with no imagery span → `probable_leak`; a canary decoy in claims → `INVALID_FOR_ACCURACY`, excluded from trust training.
- Verifier blindness: Hypothesis property. Two claims differing only in label, confidence or reasoning produce byte-identical `BlindItem` payloads, and controls and claims share one field set.
- Gold before verdict: a GoldDraw committed after the first verdict downgrades the tier.
- End-to-end planted-trace replay produces the golden passport hash.
- The Virginia planted-error replay runs the monotonicity test through the real `build_passport`.

**Golden.** A frozen sample trace scored after any semconv bump. Golden passport JSON for the Nepal synthetic fixture.

## I7. Ordered package plan (one branch and PR each, tests first, merge when green)
| # | Package | Size | Acceptance |
|---|---|---|---|
| P0 | scaffold: uv, ruff, pytest, offline fixture, CI script | 0.5 h | `pytest` green, socket blocked |
| P1 | schemas incl. TypedNumber, Interval, passport, design | 1 h | round-trip and JSON Schema export tests |
| P2 | `stats` (intervals, bootstrap, permutation, Holm, kappa, shift) | 1.5 h | exact tests and cluster/paired sims |
| P3 | store (CAS, seal, manifest chain, `verify`) + tracer | 1.5 h | tamper test fails `verify` |
| P4 | tools + gateway (in-process MCP, fixtures, deny-list, as_of) | 2 h | forbidden-source and metering tests |
| P5 | providers (fake, cassette, bedrock-stubbed) + PlainLoop + Strands adapter | 2 h | FakeModel drives Strands offline; Stubber test |
| P6 | planted-trace replay fixtures (Virginia keyed, Nepal synthetic) | 1 h | `treehouse replay` with zero network |
| P7 | rules + keyed grader + check ledger | 1.5 h | evidence-in-trace, leak, cluster-bootstrap P/R |
| P8 | `sampling` (strata, allocation, frame, gold draw, blind batch) | 1.5 h | sampling sims, blindness property |
| P9 | `trust` (PPI, RG, baselines, tiers, passport, controls, lock) | 2.5 h | all method sims incl. mutation tests |
| P10 | verifier agent (Strands, fake model) + `check` pipeline | 1.5 h | planted-error replay through passport |
| P11 | panels, plain summary with numeric lint, HTML report, CLI | 2 h | golden report; lint rejects stray numbers |
| P12 | labelling page/CSV + `prereg commit` | 0.75 h | blind export hides worker and verifier fields |
| P13 | read-only MCP server | 1 h | in-process Client lists tools and returns typed chips |

About 20 h in total, so the overnight agent will not finish. **Cut from the bottom:** P13, then report polish, then cross-fitted λ (n_gold ≥ 50 never happens tonight), then the Strands adapter (PlainLoop remains). **Never cut** P2, P8 or P9's mutation tests: they are the evidence behind the headline claim. Demo path on a fresh machine: `uv sync && treehouse replay fixtures/runs/nepal-synth && treehouse report` with no AWS.

## I8. Kiro prompts (Wed morning, AWS)
1. Capability probe → `aws-capabilities.json` (locus, models, quotas, Object Lock, invocation-log policy).
2. Vision smoke test on real 0.5 m Vantor windows; pick worker and verifier families.
3. **Before any verifier run:** `treehouse prereg commit` (primary comparison list, gold seed, `trust-config.yaml`), then push so the git timestamp is public.
4. One real vision run to measure cost; write N into `prereg/primary.yaml` (paired-difference sizing, floor 5 per arm).
5. Record cassettes: Virginia keyed (worker + verifier) and Nepal (worker, verifier batch with controls).
6. CDK: versioned bucket (Object Lock if allowed), key bucket with Deny; `treehouse store sync s3`.
7. Live contract test of BedrockProvider against the Stubber fixtures (`pytest -m aws`).
8. Human block (not AWS): `treehouse label` for 20-25 blind gold labels and 5 re-labels, then `treehouse trust` → passport moves from MODEL-ESTIMATED to GOLD-ANCHORED.

## I9. Risks
1. **The overnight agent "simplifies" the estimator.** It might drop the pseudo-units, filter out abstentions or use CLT intervals. Mitigation: the mutation tests fail exactly these simplifications; `estimators.lock` stops silent edits.
2. **Wide intervals at n_gold=20, and PPI may not narrow them.** This is shown as a finding (width ratio), never hidden.
3. **Numpy stream drift.** Mitigation: pin the lock, and store seed, rng name and algorithm in every design.
4. **Sequencing.** If gold seed commitment and verifier runs happen out of order on Wednesday, GOLD-ANCHORED is lost. `select_tier` enforces the order; the Kiro prompt order makes it explicit.
5. **RG under shift under-covers even when inflated.** It stays capped CALIBRATED-TRANSFER, existence only.
6. **Unreported frame without OSM.** The corridor polygon is hand-drawn and committed, so recall is "within the drawn corridor" and the report says so.
7. **Suite time creep.** The `method` marker has a timing assertion (fail above 8 s), and the slow variants live behind `-m slow`.
