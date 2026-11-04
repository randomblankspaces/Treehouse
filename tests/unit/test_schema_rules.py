"""Cross-field schema rules: container MEASURED fence, passport estimand/cannot_assess, WindowResult bytes
model, GoldLabel, F3 stop reasons, F8 numpy version, stable_view; round-trip and frozen for each example."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from treehouse.canon import VOLATILE_FIELDS, sha256_json, stable_hash, stable_view
from treehouse.schemas import bundle, checks, sampling, tools, verdicts
from treehouse.schemas.model_io import ModelResponse
from treehouse.schemas.numbers import TypedNumber
from treehouse.schemas.passport import ControlsReport, Estimand, TrustPassport
from treehouse.schemas.scorecard import Panel, Scorecard

PX = "sha256:" + "cd" * 32
IV = {"lo": 0.6, "hi": 0.8, "level": 0.9, "method": "wilson"}


def num(**kw) -> TypedNumber:
    base = dict(metric="m", value=0.7, type="proportion", tier="GOLD-ANCHORED", panel="trust", n=30, n_gold=24,
                abstention_rate=0.1, interval=IV, estimator_version="v1", manifest_ref="run-1", synthetic=True,
                detail={"width_ratio_vs_classical": 0.8})
    return TypedNumber(**{**base, **kw})


def measured(panel: str = "process", **kw) -> TypedNumber:
    return TypedNumber(metric="tool_calls", value=12, type="count", tier="MEASURED", panel=panel, n=None,
                       estimator_version="v1", manifest_ref="run-1", synthetic=True, **kw)


def passport(**kw) -> TrustPassport:
    base = dict(
        estimand=Estimand(name="p", kind="verified_precision", step_id="damage", question_id="damaged",
                          population="claim_table"),
        headline=num(), n_gold_cannot_assess=2, gate="Spot-check", controls=ControlsReport(),
        beat_baseline="yes", sample_design_id="d1", trust_config_hash="sha256:t", estimator_version="v1",
        code_sha="abc", manifest_ref="run-1", synthetic=True,
    )
    return TrustPassport(**{**base, **kw})


def roundtrip(x: BaseModel) -> None:
    assert type(x).model_validate_json(x.model_dump_json()) == x
    with pytest.raises(ValidationError):
        setattr(x, next(iter(type(x).model_fields)), None)


# ---- container fence ----------------------------------------------------------------------------

def test_panel_rejects_numbers_from_another_panel():
    Panel(name="process", version="1", numbers={"calls": measured()})
    with pytest.raises(ValidationError, match="inside panel"):
        Panel(name="output", version="1", numbers={"calls": measured()})


def test_panel_output_and_trust_never_hold_measured():
    # MEASURED on output/trust is already refused by TypedNumber; the panel check is the container half.
    with pytest.raises(ValidationError):
        Panel(name="output", version="1", numbers={"x": measured(panel="output")})


def test_scorecard_slot_names_match_panels():
    p = {n: Panel(name=n, version="1") for n in ("process", "understanding", "output", "cost")}
    sc = Scorecard(run_ref="r", **p)
    roundtrip(sc)
    with pytest.raises(ValidationError, match="slot"):
        Scorecard(run_ref="r", **{**p, "output": Panel(name="cost", version="1")})


@pytest.mark.parametrize("where", ["headline", "alternatives", "truth_reveal"])
def test_passport_numbers_are_trust_and_never_measured(where):
    bad = measured(panel="process")
    kw = {"headline": bad} if where == "headline" else {"alternatives": [bad]} if where == "alternatives" \
        else {"truth_reveal": bad}
    with pytest.raises(ValidationError, match="trust panel"):
        passport(**kw)


def test_passport_controls_on_controls_panel():
    se = TypedNumber(metric="se", value=0.85, type="proportion", tier="KEYED", panel="controls", n=15,
                     estimator_version="v1", manifest_ref="run-1", synthetic=True, detail={"key_version": "k"})
    passport(controls=ControlsReport(se=se))
    wrong = se.model_copy(update={"panel": "trust"})
    with pytest.raises(ValidationError, match="controls"):
        passport(controls=ControlsReport(se=TypedNumber.model_validate(wrong.model_dump())))


# ---- passport estimand rules (STAT-B1, NB2) ------------------------------------------------------

def test_passport_round_trip():
    roundtrip(passport())


def test_precision_requires_zero_cannot_assess():
    est = Estimand(name="p", kind="precision", step_id="s", question_id="exists", population="claim_table")
    passport(estimand=est, n_gold_cannot_assess=0)
    with pytest.raises(ValidationError, match="verified_precision"):
        passport(estimand=est, n_gold_cannot_assess=1)


def test_verified_precision_requires_some_cannot_assess():
    with pytest.raises(ValidationError, match="only when"):
        passport(n_gold_cannot_assess=0)


def test_cannot_assess_bounded_and_required():
    with pytest.raises(ValidationError):
        passport(n_gold_cannot_assess=-1)
    with pytest.raises(ValidationError, match="exceed"):
        passport(n_gold_cannot_assess=25)
    kw = passport().model_dump()
    del kw["n_gold_cannot_assess"]
    with pytest.raises(ValidationError):
        TrustPassport.model_validate(kw)


def test_narrowing_note_required_when_ratio_at_least_one():
    wide = num(detail={"width_ratio_vs_classical": 1.0})
    with pytest.raises(ValidationError, match="narrowing_note"):
        passport(headline=wide)
    passport(headline=wide, narrowing_note="the verifier did not narrow the interval at this gold size")


def test_gold_anchored_headline_needs_width_ratio():
    with pytest.raises(ValidationError, match="width_ratio"):
        passport(headline=num(detail={}))


def test_truth_reveal_only_when_synthetic():
    with pytest.raises(ValidationError, match="truth_reveal"):
        passport(synthetic=False, headline=num(synthetic=False),
                 truth_reveal=num(tier="KEYED", detail={"key_version": "k"}, synthetic=False))


# ---- tool results --------------------------------------------------------------------------------

def window(**kw) -> tools.WindowResult:
    base = dict(
        result_id="r-0001", source_id="s", scene_id="SYN-POST-A", bbox_requested=(0, 0, 0.01, 0.01),
        bbox_read=(0, 0, 0.01, 0.01), footprint_coverage_fraction=1.0, scene_datetime="2026-09-01T00:00:00Z",
        nominal_gsd_m=0.5, pixel_spacing_m=0.5, effective_gsd_m=0.5, overview_level=0, scene_cloud_pct=10,
        out_shape=(128, 128), resampling="nearest", pixel_sha256=PX, bytes_read=65536, requests=1,
        block_size=512, reader="synthetic-v1",
        obscuration={"bright_lowvar_fraction": 0.0, "nodata_fraction": 0.0}, license="LicenseRef-synthetic",
        synthetic=True, detail={"bytes_model": "synthetic-overview-block-v1"},
    )
    return tools.WindowResult(**{**base, **kw})


def test_window_result_round_trip():
    roundtrip(window())


@pytest.mark.parametrize("kw", [
    {"detail": {}},
    {"detail": {"bytes_model": "guess"}},
    {"detail": {"bytes_model": "measured"}},  # synthetic reader models its bytes
    {"synthetic": False},
    {"reader": "rasterio-1.5.2", "detail": {"bytes_model": "synthetic-overview-block-v1"}},
    {"pixel_sha256": "sha256:px"},
    {"footprint_coverage_fraction": 1.5},
    {"scene_cloud_pct": 140},
    {"bytes_read": -1},
])
def test_window_result_rules(kw):
    with pytest.raises(ValidationError):
        window(**kw)


def test_recorded_window_may_model_or_measure():
    window(reader="recorded", detail={"bytes_model": "measured"})
    window(reader="rasterio-1.5.2", synthetic=False, detail={"bytes_model": "measured"})


def test_scene_summary_requires_synthetic():
    kw = dict(scene_id="SYN-PRE-1", datetime="2026-07-01T00:00:00Z", cloud_pct=0, pan_gsd_m=0.5,
              footprint={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
              aoi_coverage_fraction=1.0, license="LicenseRef-synthetic")
    roundtrip(tools.SceneSummary(**kw, synthetic=True))
    with pytest.raises(ValidationError):
        tools.SceneSummary(**kw)


# ---- other records -------------------------------------------------------------------------------

def test_gold_label_synthetic_consistency():
    kw = dict(unit_id="u", question_id="exists", label="cannot_assess", labeller="gen", labeller_kind="synthetic",
              blind_protocol_hash="h", ts="2026-11-04T00:00:00Z", sealed_ref="s")
    roundtrip(verdicts.GoldLabel(**kw, synthetic=True))
    with pytest.raises(ValidationError, match="synthetic"):
        verdicts.GoldLabel(**kw, synthetic=False)


def test_stop_reasons_cover_f3():
    allowed = set(ModelResponse.model_fields["stop_reason"].annotation.__args__)
    assert {"malformed_model_output", "malformed_tool_use", "model_context_window_exceeded",
            "content_filtered", "guardrail"} <= allowed


def test_sample_design_records_numpy_version():
    kw = dict(design_id="d", seed=1, frame_hash="h", N_h={"a": 2}, n_h={"a": 1},
              units=[sampling.SampledUnit(unit_id="u", kind="claim", ref="c", stratum="a", pi=0.5, order=0)],
              created_seq=1)
    roundtrip(sampling.SampleDesign(**kw, numpy_version="2.5.0"))
    with pytest.raises(ValidationError):
        sampling.SampleDesign(**kw)


def test_check_result_requires_record_ref():
    kw = dict(claim_id="c", layer="rules", check_id="R4", version="1", result="pass")
    roundtrip(checks.CheckResult(**kw, record_ref="evals/r/rules/x.json"))
    with pytest.raises(ValidationError):
        checks.CheckResult(**kw)


def test_bundle_carries_evidence_and_understanding():
    p = {n: Panel(name=n, version="1") for n in ("process", "understanding", "output", "cost")}
    b = bundle.ReportBundle(
        manifest_ref="run-1",
        manifest_summary=bundle.ManifestSummary(run_id="run-1", mode="fake", task_ref="t@sha256:x",
                                                key_isolation_statement="local", license_floor="CC-BY-NC-4.0"),
        card_ref="t@sha256:x",
        card_summary=bundle.CardSummary(id="t", version="1", title="T", goal="g", license_floor="CC-BY-NC-4.0"),
        scorecard=Scorecard(run_ref="r", **p), evidence=[window()], summary="s",
        lint=bundle.SummaryLint(ok=True), synthetic=True,
    )
    roundtrip(b)
    assert b.evidence[0].synthetic
    with pytest.raises(ValidationError):  # summaries are text-only records, not free dicts
        bundle.ReportBundle.model_validate({**b.model_dump(), "card_summary": {"title": "T", "bytes": "123"}})


# ---- golden stability ----------------------------------------------------------------------------

def test_stable_view_drops_volatile_fields_at_any_depth():
    a, b = passport(code_sha="aaa"), passport(code_sha="bbb", manifest_ref="run-2",
                                              headline=num(manifest_ref="run-2"))
    assert sha256_json(a) != sha256_json(b)
    assert stable_hash(a) == stable_hash(b)
    view = stable_view({"created_at": 1, "x": [{"git_sha": "g", "python": "3.12", "keep": 1}]})
    assert view == {"x": [{"keep": 1}]}
    assert {"created_at", "git_sha", "python", "code_sha", "manifest_ref"} <= VOLATILE_FIELDS
