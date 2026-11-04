"""Trust STUB (P5). Reports ABSTAINED with the reason "trust engine not yet built"; P8 replaces it."""

from __future__ import annotations

from treehouse.schemas.numbers import Tier, TypedNumber
from treehouse.schemas.passport import ControlsReport, Estimand, TrustPassport
from treehouse.sealed import SealedRun

VERSION = "trust-stub-p5"
REASON = "trust engine not yet built"


def stub_passport(run: SealedRun, *, trust_config_hash: str, code_sha: str = "unknown") -> TrustPassport:
    step = next((s for s in run.card.steps if s.question_id == "damaged"), run.card.steps[0])
    head = TypedNumber(metric="verified_precision", value=None, type="proportion", tier=Tier.ABSTAINED,
                       panel="trust", n=None, estimator_version=VERSION, manifest_ref=run.manifest_ref,
                       reasons=[REASON], synthetic=run.synthetic, replayed=run.replayed)
    return TrustPassport(
        estimand=Estimand(name="verified_precision", kind="verified_precision", step_id=step.step_id,
                          question_id=step.question_id, population="claim_table"),
        headline=head, gate="Do not rely", gate_reasons=[REASON],
        controls=ControlsReport(unavailable=[f"controls: {REASON}"]), beat_baseline=f"not computed: {REASON}",
        sample_design_id="none", trust_config_hash=trust_config_hash, estimator_version=VERSION,
        code_sha=code_sha, manifest_ref=run.manifest_ref, synthetic=run.synthetic)
