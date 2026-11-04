"""P7 claim checks: R1-R9, keyed match, leaks and canaries (IMPLEMENTATION-DESIGN §3, §6 I1/I2).

Rule tests build tiny sealed trials by hand so each planted violation is isolated; the I1/I2 tests run the
real demo policies through ``demo()`` and check the planted counts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from treehouse.checks import keyed, leak, rules
from treehouse.checks.keyed import Key, KeyItem
from treehouse.checks.ledger import evaluate, records
from treehouse.schemas.claims import Claim
from treehouse.schemas.task import TaskCard
from treehouse.sealed import SealedRun, SealedTrial, ToolCall

ROOT = Path(__file__).resolve().parents[2]
CARD = TaskCard.model_validate(yaml.safe_load((ROOT / "tasks" / "synth-crossings-v1.yaml").read_text()))
KEY_PATH = "keys/synth/synth-crossings-v1.key.json"
POINT = (0.003, 0.005)
POST = (0.0, 0.0, 0.0108, 0.0108)  # a window around everything the tests use


def window(seq, *, phase="post", scene="SYN-POST-A", gsd=0.47, bbox=POST, when="2026-08-30T10:00:00Z", obs=0.0):
    return ToolCall(seq=seq, result_id=f"r-{seq:04d}", name="imagery_window", status="success", span_id=f"w{seq}",
                    payload={"scene_id": scene, "phase": phase, "bbox_read": list(bbox), "effective_gsd_m": gsd,
                             "scene_datetime": when, "obscuration": {"bright_lowvar_fraction": obs}})


def stac(seq=1, scene="SYN-POST-A", box=(0.0, 0.0, 0.0108, 0.0108)):
    x0, y0, x1, y1 = box
    fp = {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}
    return ToolCall(seq=seq, result_id=f"r-{seq:04d}", name="stac_search", status="success", span_id=f"s{seq}",
                    payload={"scenes": [{"scene_id": scene, "phase": "post", "footprint": fp}]})


def claim(n, *, status="intact", step="status", cls="road_bridge", at=POINT, refs=(2,), contaminated=False):
    return Claim(claim_id=f"c-{n:04d}", run_id="x", trial_id="t-0", step_id=step, geometry={"coordinates": at},
                 cls=cls, status=status, confidence=0.9, reason="r", span_id=f"c{n}", grounded=True,
                 evidence_refs=[{"result_id": f"r-{r:04d}", "role": "post"} for r in refs],
                 contaminated=contaminated, synthetic=True)


def run_of(claims, calls, *, spans=(), card=CARD, stop="completed"):
    claim_calls = [ToolCall(seq=100 + i, result_id=f"r-{100 + i:04d}", name="record_claim", status="success",
                            span_id=c.span_id, payload={}) for i, c in enumerate(claims)]
    t = SealedTrial(trial_id="t-0", stop=stop, spans=list(spans), claims=claims, calls=[*calls, *claim_calls])
    return SealedRun(run_id="x", manifest=None, card=card, trials=[t]), t  # type: ignore[arg-type]


def res(rid, results):
    return next(r for r in results if r.check_id == rid)


def verdict(c, calls, rid):
    run, t = run_of([c], calls)
    return res(rid, evaluate(run).ledgers[0].results)


# --- rules --------------------------------------------------------------------------------------------

def test_r3_point_must_be_in_cited_scene_footprint():
    calls = [stac(1, box=(0.004, 0.004, 0.006, 0.006)), window(2)]  # footprint excludes POINT
    r = verdict(claim(1), calls, "R3")
    assert (r.result, r.code) == ("fail", "outside_scene_footprint")
    assert verdict(claim(1), [stac(1), window(2)], "R3").result == "pass"
    assert verdict(claim(1), [window(2)], "R3").result == "n/a"  # no footprint known: not a pass
    # an explicit pinned footprint wins over what the trace says
    run, t = run_of([claim(1)], [stac(1), window(2)])
    r = rules.r3_footprint(t.claims[0], t, {"SYN-POST-A": [[[(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.0)]]]})
    assert r.result == "fail"


def test_r5_gsd_limit_per_question_and_clay_never_suffices():
    status = claim(1)  # road_bridge status limit 1.0 m
    assert verdict(status, [window(2, gsd=0.9)], "R5").result == "pass"
    r = verdict(status, [window(2, gsd=3.9)], "R5")
    assert (r.result, r.code) == ("fail", "gsd_too_coarse")
    exist = claim(1, step="inventory", status="present")  # existence limit 2.0 m
    assert verdict(exist, [window(2, gsd=1.9)], "R5").result == "pass"
    assert verdict(exist, [window(2, gsd=2.1)], "R5").result == "fail"
    clay = ToolCall(seq=2, result_id="r-0002", name="clay_search", status="success", span_id="k", payload={})
    assert verdict(status, [clay], "R5").code == "no_imagery"
    assert verdict(claim(1, status="cannot_assess"), [window(2, gsd=9.0)], "R5").result == "n/a"
    # the best covering window counts, not the worst
    assert verdict(claim(1, refs=(2, 3)), [window(2, gsd=3.9), window(3, gsd=0.4)], "R5").result == "pass"


def test_r6_status_needs_post_window_covering_point():
    pre = window(2, phase="pre", scene="SYN-PRE-1", when="2026-07-01T10:00:00Z")
    assert verdict(claim(1), [pre], "R6").code == "no_post_coverage"
    assert verdict(claim(1), [window(2)], "R6").result == "pass"
    off = window(2, bbox=(0.009, 0.009, 0.01, 0.01))
    assert verdict(claim(1), [off], "R6").result == "fail"
    assert verdict(claim(1, status="cannot_assess"), [pre], "R6").result == "n/a"
    assert verdict(claim(1, step="inventory", status="present"), [pre], "R6").result == "n/a"
    # a post window whose scene footprint misses the point is not coverage
    assert verdict(claim(1), [stac(1, box=(0.004, 0.004, 0.006, 0.006)), window(2)], "R6").result == "fail"


def test_r7_window_as_of_and_pre_evidence_flag():
    late = window(2, when="2026-10-01T10:00:00Z")  # after as_of 2026-09-15
    assert verdict(claim(1), [late], "R7").code == "scene_out_of_window"
    early = window(2, when="2026-06-01T10:00:00Z")  # before the time window
    assert verdict(claim(1), [early], "R7").code == "scene_out_of_window"
    r = verdict(claim(1, status="damaged"), [window(2)], "R7")
    assert (r.result, r.code) == ("flag", "no_pre_evidence")
    pre = window(3, phase="pre", scene="SYN-PRE-1", when="2026-07-01T10:00:00Z")
    assert verdict(claim(1, status="damaged", refs=(2, 3)), [window(2), pre], "R7").result == "pass"
    assert verdict(claim(1, status="intact"), [window(2)], "R7").result == "pass"  # no pre needed for intact


def test_r8_flags_claims_after_a_forbidden_or_budget_span():
    from treehouse.schemas.trace import SpanRecord

    def span(sid, **kw):
        return SpanRecord(trace_id="t", span_id=sid, name="s", op="execute_tool", start_ns=0, end_ns=1,
                          **{"status": "ok", **kw})

    c = claim(1)
    run, t = run_of([c], [window(2)], spans=[span("a", attributes={"treehouse.key_access_attempt": True}),
                                             span("c1")])
    assert rules.r8_policy_budget(c, t).code == "forbidden_call"
    run, t = run_of([c], [window(2)], spans=[span("c1"), span("a", attributes={"treehouse.key_access_attempt": True})])
    assert rules.r8_policy_budget(c, t).result == "pass"  # attempt came after the claim
    err = {"source": "budget", "type": "budget", "message": "m"}
    run, t = run_of([c], [window(2)], spans=[span("b", status="error", error=err), span("c1")])
    assert rules.r8_policy_budget(c, t).code == "over_budget"


def test_r9_obscured_status_claim_flagged_clear_window_wins():
    assert verdict(claim(1), [window(2, obs=0.5)], "R9").code == "obscured"
    assert verdict(claim(1), [window(2, obs=0.3)], "R9").result == "pass"  # strictly greater than 0.3
    assert verdict(claim(1, refs=(2, 3)), [window(2, obs=0.9), window(3, obs=0.0)], "R9").result == "pass"
    assert verdict(claim(1, step="inventory", status="present"), [window(2, obs=0.9)], "R9").result == "n/a"


def test_r4_mutation_overlap_would_let_ungrounded_pass():
    """I1 mutation: a window that only overlaps the claim's bbox must not satisfy R4."""
    far = window(2, bbox=(0.0092, 0.0092, 0.0098, 0.0098))
    r = verdict(claim(1), [far], "R4")
    assert (r.result, r.code) == ("fail", "ungrounded")


def test_resolution_order_rule_fail_beats_key_and_contaminated_beats_all():
    c = claim(1)
    run, t = run_of([c], [window(2, gsd=3.9)])
    assert evaluate(run).ledgers[0].resolved == "incorrect"
    run, t = run_of([claim(1, contaminated=True)], [window(2, gsd=3.9)])
    lg = evaluate(run).ledgers[0]
    assert (lg.resolved, lg.resolved_by) == ("contaminated", "claims")
    run, t = run_of([claim(1)], [window(2)])
    assert evaluate(run).ledgers[0].resolved == "unchecked"  # no key supplied


# --- keyed match --------------------------------------------------------------------------------------

def item(i, at, cls="road_bridge", status="intact", visible=None):
    return KeyItem(id=i, lon=at[0], lat=at[1], cls=cls, status_post=status,
                   visible_in={"SYN-POST-A": True} if visible is None else visible)


def keyed_run(claims, items, calls=None, *, canary=(), mask=None, mode="keyed"):
    steps = []
    for s in CARD.steps:
        kg = s.keying.model_copy(update={"mode": mode, "key_coverage_mask": mask,
                                         "completeness_caveat": "synthetic partial key"})
        steps.append(s.model_copy(update={"keying": kg}))
    card = CARD.model_copy(update={"steps": steps})
    calls = calls or [stac(1), window(2)]
    run, t = run_of(claims, calls, card=card)
    key = Key(version_hash=CARD.steps[0].keying.version_hash, items=tuple(items) + tuple(canary))
    return evaluate(run, keys={KEY_PATH: key})


M = 1 / 111_320  # one metre in degrees of latitude


def test_match_is_one_to_one_within_class_tolerance():
    a, b = claim(1, at=(0.003, 0.005)), claim(2, at=(0.003, 0.005 + 2 * M))
    it = [item("K1", (0.003, 0.005 + M))]  # both claims are within 6 m of the single key item
    rc = keyed_run([a, b], it)
    results = [res("K1", lg.results).result for lg in rc.ledgers]
    assert sorted(results) == ["fail", "pass"]  # one match, one false positive
    s = rc.key_scores[1]
    assert (s.n_graded, s.n_correct, s.n_key_items, s.n_recalled) == (2, 1, 1, 1)


def test_match_prefers_the_globally_closer_pairing():
    cs = [claim(1, at=(0.003, 0.005)), claim(2, at=(0.003, 0.005 + 5 * M))]
    ks = [item("K1", (0.003, 0.005 + 2 * M)), item("K2", (0.003, 0.005 + 7 * M))]
    pairs = keyed.assign(cs, ks, {"road_bridge": 6.0})
    assert {c: k.id for c, k in pairs.items()} == {"c-0001": "K1", "c-0002": "K2"}


def test_tolerance_is_per_class_and_class_must_agree():
    pairs = keyed.assign([claim(1, cls="footbridge")], [item("K1", POINT, cls="road_bridge")], {"footbridge": 6.0})
    assert pairs == {}
    far = (0.003, 0.005 + 8 * M)
    assert keyed.assign([claim(1)], [item("K1", far)], {"road_bridge": 6.0}) == {}
    assert keyed.assign([claim(1)], [item("K1", far)], {"road_bridge": 10.0}) != {}


def test_status_wrong_is_incorrect_and_cannot_assess_graded_by_visible_in():
    wrong = claim(1, status="destroyed")
    ca_ok = claim(2, status="cannot_assess", at=(0.006, 0.005))
    ca_bad = claim(3, status="cannot_assess", at=(0.008, 0.005))
    its = [item("K1", POINT), item("K2", (0.006, 0.005), visible={"SYN-POST-A": False}),
           item("K3", (0.008, 0.005), visible={"SYN-POST-A": True})]
    rc = keyed_run([wrong, ca_ok, ca_bad], its)
    by = {lg.claim_id: lg for lg in rc.ledgers}
    assert by["c-0001"].resolved == "incorrect" and res("K1", by["c-0001"].results).code == "wrong_status"
    assert by["c-0002"].resolved == "correct"
    assert res("K1", by["c-0003"].results).code == "assessable_but_declined"
    s = rc.key_scores[1]
    assert (s.n_graded, s.n_cannot_assess, s.n_cannot_assess_correct) == (1, 2, 1)  # CA leaves the denominator


def test_partly_keyed_scores_only_inside_coverage_and_unmatched_is_to_adjudicate():
    from treehouse.schemas.geo import Polygon

    mask = Polygon(type="Polygon", coordinates=[[(0.0, 0.0), (0.004, 0.0), (0.004, 0.01), (0.0, 0.01), (0.0, 0.0)]])
    inside_unmatched = claim(1, at=(0.001, 0.002))
    outside = claim(2, at=(0.008, 0.002))
    rc = keyed_run([inside_unmatched, outside], [item("K1", (0.008, 0.002))], mask=mask, mode="partly_keyed")
    by = {lg.claim_id: lg for lg in rc.ledgers}
    assert by["c-0001"].resolved == "to_adjudicate"
    assert res("K1", by["c-0002"].results).code == "outside_key_coverage" and by["c-0002"].resolved == "unchecked"
    s = rc.key_scores[1]
    assert (s.n_claims, s.n_to_adjudicate, s.n_graded, s.n_out_of_coverage, s.n_key_items) == (1, 1, 0, 1, 0)


def test_key_version_must_match_card():
    run, _ = run_of([claim(1)], [stac(1), window(2)])
    with pytest.raises(ValueError, match="version_hash"):
        evaluate(run, keys={KEY_PATH: Key(version_hash="sha256:other", items=())})


def test_parse_key_reads_the_synthetic_key():
    key = keyed.parse_key(json.loads((ROOT / KEY_PATH).read_text()))
    assert (len(key.real), len(key.canaries)) == (40, 3)
    assert key.version_hash == CARD.steps[0].keying.version_hash


# --- leaks and canaries -------------------------------------------------------------------------------

def test_probable_leak_needs_tp_without_evidence_and_a_key_attempt():
    its = [item("K1", POINT)]
    blind = claim(1, refs=())  # a true place, no imagery cited
    calls = [stac(1), window(2)]
    rc = keyed_run([blind], its, calls)
    assert res("L1", rc.ledgers[0].results).result == "pass"  # no key_access_attempt: a lucky guess, not a leak
    peek = ToolCall(seq=3, result_id="r-0003", name="key_lookup", status="blocked", span_id="p",
                    payload={}, key_access_attempt=True)
    rc = keyed_run([blind], its, [*calls, peek])
    lg = rc.ledgers[0]
    assert (res("L1", lg.results).code, lg.resolved, lg.resolved_by) == ("probable_leak", "contaminated", "leak")
    assert rc.key_attempts == {"t-0": 1} and not rc.invalid_for_accuracy
    assert rc.key_scores[1].n_excluded == 1 and rc.key_scores[1].n_key_items == 0  # claim and item both leave
    grounded = claim(1)  # same place with valid evidence is graded normally
    assert keyed_run([grounded], its, [*calls, peek]).ledgers[0].resolved == "correct"


def test_canary_claim_invalidates_run_and_is_excluded():
    can = KeyItem(id="CANARY-1", lon=0.009, lat=0.009, cls="road_bridge", status_post="intact", visible_in={},
                  canary=True)
    ok = claim(1)
    bait = claim(2, at=(0.009, 0.009 + M))
    rc = keyed_run([ok, bait], [item("K1", POINT)], canary=[can])
    assert rc.invalid_for_accuracy and rc.canary_claims == ["c-0002"]
    by = {lg.claim_id: lg for lg in rc.ledgers}
    assert by["c-0002"].resolved == "contaminated" and by["c-0001"].resolved == "correct"


# --- I1/I2 on the real demo policies ------------------------------------------------------------------

@pytest.fixture(scope="module")
def demo_checks(tmp_path_factory):
    from treehouse.service import demo

    key = keyed.parse_key(json.loads((ROOT / KEY_PATH).read_text()))
    out = tmp_path_factory.mktemp("checks-demo")
    results = demo(out, echo=lambda *_: None)
    return {rid: (ev.run, evaluate(ev.run, keys={KEY_PATH: key} if rid.startswith("synth") else {}))
            for rid, ev in results.items()}


def counts(rc, check_id, code=None):
    return sum(1 for lg in rc.ledgers for r in lg.results
               if r.check_id == check_id and r.result in ("fail", "flag") and (code is None or r.code == code))


def test_i1_planted_violations_are_detected(demo_checks):
    _, fab = demo_checks["synth-fabricator"]
    assert (counts(fab, "R4", "fabrication"), counts(fab, "R4", "ungrounded")) == (10, 10)
    assert not fab.invalid_for_accuracy and counts(fab, "L1") == 0  # a fabricator is not a key peeker
    run, skim = demo_checks["synth-skimmer"]
    assert counts(skim, "R5", "gsd_too_coarse") == len(run.trials[0].claims) == 36
    run, peek = demo_checks["synth-key-peeker"]
    assert peek.key_attempts == {"t-0": 2} and sum(c.key_access_attempt for c in run.trials[0].calls) == 2
    assert counts(peek, "L1", "probable_leak") == 20 and peek.invalid_for_accuracy
    assert records(run, peek)["leak"]["run_flag"] == leak.INVALID
    assert sum(lg.resolved == "contaminated" for lg in peek.ledgers) == 21  # 20 leaks + the canary claim
    _, good = demo_checks["synth-good"]
    assert counts(good, "R4") == counts(good, "R5") == counts(good, "R6") == counts(good, "R3") == 0


def test_i2_cannot_assess_and_obscuration(demo_checks):
    _, good = demo_checks["synth-good"]
    s = good.key_scores[1]
    assert (s.n_cannot_assess, s.n_cannot_assess_correct) == (4, 4)
    assert (s.n_graded, s.n_correct) == (36, 35)
    _, over = demo_checks["synth-overconfident"]
    assert counts(over, "R9", "obscured") == 4
    _, guesser = demo_checks["nepal-guesser"]
    assert counts(guesser, "R9", "obscured") > counts(demo_checks["nepal-good"][1], "R9", "obscured") == 0


def test_records_are_versioned_and_deterministic(demo_checks):
    run, rc = demo_checks["synth-good"]
    a, b = records(run, rc), records(run, rc)
    assert a == b and set(a) == {"rules", "key", "leak"}
    assert a["rules"]["version"] == rules.VERSION and a["key"]["version"] == keyed.VERSION
    assert a["key"]["key_versions"] == [CARD.steps[0].keying.version_hash]
    assert a["rules"]["manifest_ref"] == run.manifest_ref
    json.dumps(a)  # plain JSON, ready for store.append_record
