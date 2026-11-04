"""Seeds and a seeded synthetic world for the trust method tests (IMPLEMENTATION-DESIGN §6)."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from treehouse.sampling.design import stratified_sample
from treehouse.sampling.gold import draw_gold
from treehouse.schemas.sampling import GoldDraw, SampleDesign
from treehouse.schemas.verdicts import GoldLabel, VerifierVerdict
from treehouse.trust.tiers import EvidenceBundle

BASE = 20261104
TS = datetime(2026, 11, 4, tzinfo=UTC)


def verdict(uid, answer, seq=10):
    return VerifierVerdict(unit_id=uid, question_id="damaged", answer=answer, verifier_config_hash="v",
                           request_hash="r-" + uid, recorded=True, synthetic=True, created_seq=seq)


def label(uid, lab, *, relabel=False, ref=None, protocol="bp"):
    return GoldLabel(unit_id=uid, question_id="damaged", label=lab, labeller="t", labeller_kind="synthetic",
                     blind_protocol_hash=protocol, ts=TS, sealed_ref=ref or f"gold/{uid}", is_relabel=relabel,
                     synthetic=True)


def world(seed, *, Nh=(20, 20, 20), nh=None, n_gold=20, p=(0.9, 0.75, 0.6), se=0.85, sp=0.7,
          abst=(0.05, 0.1, 0.35), n_cannot=0, controls=None, gold_seq=1, verdict_seq=10, **ev_kw):
    """Claims with truth Y ~ Bernoulli(p_h); worker always claims "yes"; verifier with Se/Sp and abstention.
    Returns (EvidenceBundle, truth precision over the frame)."""
    rng = np.random.default_rng(seed)  # design and gold use other seeds: a shared stream would correlate them
    nh = Nh if nh is None else nh
    frame, truth = [], {}
    for h, N in enumerate(Nh):
        for i in range(N):
            uid = f"c{h}-{i:03d}"
            truth[uid] = bool(rng.random() < p[h])
            frame.append({"unit_id": uid, "kind": "claim", "ref": uid, "stratum": f"s{h}"})
    n_h = {f"s{h}": nh[h] for h in range(len(Nh))}
    for kind, k in (controls or {}).items():
        frame += [{"unit_id": f"{kind}-{i:03d}", "kind": kind, "ref": f"c0-{i:03d}" if kind == "retest" else "-",
                   "stratum": f"ctl-{kind}"} for i in range(k)]
        n_h[f"ctl-{kind}"] = k
    design = SampleDesign.model_validate(stratified_sample(frame, n_h, seed=seed + 7, created_seq=0))
    claims = [u for u in design.units if u.kind == "claim"]
    verdicts = []
    for u in claims:
        h = int(u.stratum[1:])
        if rng.random() < abst[h]:
            ans = "cannot_assess"
        else:
            ans = "yes" if (rng.random() < se if truth[u.unit_id] else rng.random() > sp) else "no"
        verdicts.append(verdict(u.unit_id, ans, verdict_seq))
    for u in design.units:
        if u.kind == "control_pos":
            verdicts.append(verdict(u.unit_id, "yes" if rng.random() < se else "no", verdict_seq))
        elif u.kind in ("control_neg", "placebo"):
            verdicts.append(verdict(u.unit_id, "no" if rng.random() < sp else "yes", verdict_seq))
    by = {v.unit_id: v.answer for v in verdicts}
    verdicts += [verdict(u.unit_id, by.get(u.ref, "yes"), verdict_seq) for u in design.units if u.kind == "retest"]
    gd = GoldDraw.model_validate(draw_gold(design.model_dump(), n_gold, seed=seed + 1,
                                           committed_ref="git:abc", committed_seq=gold_seq)) if n_gold else None
    gold = [label(u, "yes" if truth[u] else "no") for u in (gd.unit_ids if gd else [])]
    gold = [label(g.unit_id, "cannot_assess") if i < n_cannot else g for i, g in enumerate(gold)]
    kw = dict(step_id="damage", question_id="damaged", design=design, claimed={u.unit_id: "yes" for u in claims},
              verdicts=verdicts, family="bridges", model="m", harness="plain_loop", toolset="t1",
              threshold=0.8, manifest_ref="sha256:m", synthetic=True, gold_draw=gd, gold=gold, code_sha="x")
    kw.update(ev_kw)
    return EvidenceBundle(**kw), float(np.mean(list(truth.values())))
