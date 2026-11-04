"""§2 schemas: round-trip, frozen/forbid, TypedNumber validator table, MEASURED fence, chips, walkers."""

from __future__ import annotations

import types
import typing

import pytest
from pydantic import BaseModel, ValidationError

from treehouse.schemas import bundle, geo, manifest, model_io, numbers, passport, scorecard
from treehouse.schemas.config import InferenceParams, RoleConfig, RunConfig, TrustConfig
from treehouse.schemas.numbers import Interval, Tier, TypedNumber

IV = {"lo": 0.6, "hi": 0.8, "level": 0.9, "method": "wilson"}
BASE = dict(
    metric="m",
    value=0.7,
    type="proportion",
    tier="KEYED",
    panel="output",
    n=40,
    estimator_version="v1",
    manifest_ref="sha256:abc",
    synthetic=True,
    detail={"key_version": "k1"},
)


def tn(**kw) -> TypedNumber:
    return TypedNumber(**{**BASE, **kw})


# (description, overrides, ok)
TABLE = [
    ("keyed ok", {}, True),
    ("keyed without key_version", {"detail": {}}, False),
    ("keyed without n", {"n": None}, False),
    ("value None, not abstained", {"value": None}, False),
    ("abstained with reasons", {"tier": "ABSTAINED", "value": None, "reasons": ["no gold"], "detail": {}}, True),
    ("abstained without reasons", {"tier": "ABSTAINED", "value": None, "detail": {}}, False),
    ("measured unpriced None", {"tier": "MEASURED", "panel": "cost", "type": "usd", "value": None,
                                "reasons": ["unpriced"], "detail": {}}, True),
    ("measured None not unpriced", {"tier": "MEASURED", "panel": "cost", "type": "usd", "value": None,
                                    "reasons": ["x"], "detail": {}}, False),
    ("gold-anchored ok", {"tier": "GOLD-ANCHORED", "panel": "trust", "n_gold": 24, "abstention_rate": 0.1,
                          "interval": IV, "detail": {}}, True),
    ("gold-anchored n_gold 0", {"tier": "GOLD-ANCHORED", "panel": "trust", "n_gold": 0, "abstention_rate": 0.1,
                                "interval": IV, "detail": {}}, False),
    ("gold-anchored no abstention", {"tier": "GOLD-ANCHORED", "panel": "trust", "n_gold": 5,
                                     "interval": IV, "detail": {}}, False),
    ("gold-anchored no interval", {"tier": "GOLD-ANCHORED", "panel": "trust", "n_gold": 5,
                                   "abstention_rate": 0.0, "detail": {}}, False),
    ("calibrated no interval", {"tier": "CALIBRATED-TRANSFER", "panel": "trust", "detail": {}}, False),
    ("calibrated ok", {"tier": "CALIBRATED-TRANSFER", "panel": "trust", "interval": IV, "detail": {}}, True),
    ("model-estimated no interval", {"tier": "MODEL-ESTIMATED", "panel": "trust", "detail": {}}, False),
    ("model-estimated ok", {"tier": "MODEL-ESTIMATED", "panel": "trust", "interval": IV, "detail": {}}, True),
    ("proportion > 1", {"value": 1.2}, False),
    ("proportion < 0", {"value": -0.1}, False),
    ("count may exceed 1", {"type": "count", "value": 12}, True),
]
FENCE = [
    ("process", True),
    ("understanding", True),
    ("cost", True),
    ("controls", True),
    ("output", False),
    ("trust", False),
]


@pytest.mark.parametrize("desc,overrides,ok", TABLE, ids=[r[0] for r in TABLE])
def test_typed_number_validator_table(desc, overrides, ok):
    if ok:
        tn(**overrides)
    else:
        with pytest.raises(ValidationError):
            tn(**overrides)


@pytest.mark.parametrize("panel,ok", FENCE)
def test_measured_fence(panel, ok):
    kw = {"tier": "MEASURED", "panel": panel, "detail": {}}
    if ok:
        tn(**kw)
    else:
        with pytest.raises(ValidationError):
            tn(**kw)


def test_measured_interval_needs_aggregate_over():
    kw = {"tier": "MEASURED", "panel": "process", "interval": IV}
    with pytest.raises(ValidationError):
        tn(**kw, detail={})
    tn(**kw, detail={"aggregate_over": "trials"})


def test_synthetic_is_required():
    kw = dict(BASE)
    del kw["synthetic"]
    with pytest.raises(ValidationError):
        TypedNumber(**kw)


def test_chip_labels():
    assert tn().chip() == "Checked · SYNTHETIC"
    assert tn(synthetic=False, replayed=True).chip() == "Checked · recorded"
    labels = {
        "GOLD-ANCHORED": "Estimated from a random check",
        "CALIBRATED-TRANSFER": "Estimated from track record",
        "MODEL-ESTIMATED": "Rough model guess",
        "ABSTAINED": "Not issued",
        "MEASURED": "Measured from trace",
    }
    for tier, label in labels.items():
        assert numbers.CHIP_LABELS[Tier(tier)] == label


def test_frozen_and_forbid():
    x = tn()
    with pytest.raises(ValidationError):
        x.value = 0.1
    with pytest.raises(ValidationError):
        tn(extra_field=1)
    with pytest.raises(ValidationError):
        Interval(**IV, bogus=1)


def test_round_trip():
    x = tn(interval=IV)
    assert TypedNumber.model_validate_json(x.model_dump_json()) == x


def test_interval_ordered():
    with pytest.raises(ValidationError):
        Interval(lo=0.9, hi=0.1, level=0.9, method="wilson")


def test_estimand_kinds_include_verified_precision():
    passport.Estimand(name="p", kind="verified_precision", step_id="s", question_id="exists",
                      population="claim_table")


def test_polygon_rings_closed():
    with pytest.raises(ValidationError):
        geo.Polygon(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1]]])
    with pytest.raises(ValidationError):
        geo.Polygon(type="MultiPolygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]])
    with pytest.raises(ValidationError):
        geo.Point(coordinates=(1.0, 2.0), extra=1)


def test_bbox_ordered():
    from pydantic import TypeAdapter

    with pytest.raises(ValidationError):
        TypeAdapter(geo.BBox).validate_python((1, 0, 0, 1))


def role(family: str) -> RoleConfig:
    return RoleConfig(provider="fake", model_key="m", family=family, params=InferenceParams(max_tokens=10))


def test_runconfig_cross_family():
    kw = dict(task_ref="t@sha256:ab", mode="fake", worker=role("a"), seed=1)
    RunConfig(**kw, verifier=role("b"))
    with pytest.raises(ValidationError):
        RunConfig(**kw, verifier=role("a"))
    RunConfig(**kw, verifier=role("a"), allow_same_family=True)
    with pytest.raises(ValidationError):
        RunConfig(**{**kw, "task_ref": "t"})


def test_runconfig_lists_every_swappable_part():
    """J9 (partial): model, harness, tracer, evaluator, tools, task, trials and budget are config."""
    f = RunConfig.model_fields
    for name in ("worker", "verifier", "harness", "backends", "task_ref", "trials", "budget"):
        assert name in f
    assert "tools" in RoleConfig.model_fields and "tracer" in RunConfig.model_fields["backends"].annotation.model_fields


def test_backend_resolution_rules():
    manifest.BackendResolution(requested="local", ran="local")
    with pytest.raises(ValidationError):
        manifest.BackendResolution(requested="s3", ran="local")
    manifest.BackendResolution(requested="s3", ran="local", degraded_from="s3", reason="no creds")
    with pytest.raises(ValidationError):
        manifest.BackendResolution(requested="s3", ran="s3")
    manifest.BackendResolution(requested="s3", ran="s3", evidence=["read-back ok"])


def test_request_key_ignores_image_bytes():
    def req(data: bytes | None):
        img = model_io.Image(format="png", sha256="sha256:px", bytes_=data)
        return model_io.ModelRequest(
            model_id="m",
            system="s",
            messages=[model_io.Message(role="user", content=[model_io.Text(text="hi"), img])],
            params=InferenceParams(max_tokens=5),
        )

    assert req(b"abc").key() == req(b"xyz").key() == req(None).key()
    other = model_io.ModelRequest(model_id="m2", system="s", messages=[], params=InferenceParams(max_tokens=5))
    assert other.key() != req(None).key()


def test_image_bytes_round_trip_json():
    img = model_io.Image(format="png", sha256="sha256:px", bytes_=b"\x00\xff")
    assert model_io.Image.model_validate_json(img.model_dump_json()) == img


def test_scorecard_has_no_composite():
    names = set(scorecard.Scorecard.model_fields)
    assert not {n for n in names if any(w in n for w in ("composite", "overall", "total", "grade"))}


# ---- no bare float in reported records -------------------------------------------------------

# Fields that hold coordinates, raw agent figures or raw trace data. Each is rendered as data,
# never as a Treehouse number, so it is exempt. Keep this list short.
EXEMPT = {
    (geo.Point, "coordinates"): "geometry",
    (geo.Polygon, "coordinates"): "geometry",
    ("Claim", "bbox"): "geometry",
    ("Claim", "confidence"): "agent's own claim, chipped as such",
    ("SpanRecord", "attributes"): "raw trace attributes",
    ("SpanEvent", "attributes"): "raw trace attributes",
    ("CheckResult", "detail"): "rule evidence (distances in m)",
}
TYPED = (TypedNumber,)  # floats inside a TypedNumber are typed by definition


def _exempt(model: type[BaseModel], field: str) -> bool:
    return (model, field) in EXEMPT or (model.__name__, field) in EXEMPT


def _floats(tp, path: str, seen: set) -> list[str]:
    if tp is float:
        return [path]
    origin = typing.get_origin(tp)
    if origin is typing.Annotated:
        return _floats(typing.get_args(tp)[0], path, seen)
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        if tp in TYPED or tp in seen:
            return []
        seen = seen | {tp}
        out = []
        for name, f in tp.model_fields.items():
            if not _exempt(tp, name):
                out += _floats(f.annotation, f"{tp.__name__}.{name}", seen)
        return out
    out = []
    for arg in typing.get_args(tp) if origin in (typing.Union, types.UnionType, list, tuple, dict) else []:
        out += _floats(arg, path, seen)
    return out


@pytest.mark.parametrize("model", [scorecard.Scorecard, passport.TrustPassport, bundle.ReportBundle])
def test_no_bare_float(model):
    assert _floats(model, model.__name__, set()) == []


def test_float_walker_can_fail():
    class Bad(BaseModel):
        score: dict[str, list[float | None]]

    assert _floats(Bad, "Bad", set()) == ["Bad.score"]
    assert _floats(TrustConfig, "TrustConfig", set())  # a config record has bare floats


def test_exemptions_name_real_fields():
    from treehouse.schemas import checks, claims, trace

    mods = [geo, claims, trace, checks]
    for (model, field), _ in EXEMPT.items():
        cls = model if isinstance(model, type) else next(getattr(m, model) for m in mods if hasattr(m, model))
        assert field in cls.model_fields
