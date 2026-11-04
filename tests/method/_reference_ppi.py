# ruff: noqa
# Verbatim copy of wip/council2/proto/ppi2.py: the test oracle for trust.ppi (IMPLEMENTATION-DESIGN §3 PPI).
import numpy as np, time
from scipy import stats

def ppi(ss, Nh, f, ys, gold, rng, B=400, alpha=0.1, pseudo=1.0, method="boot"):
    """phase1: stratified SRSWOR S (ss stratum per unit); phase2: SRSWOR gold from S (pooled).
    Rectifier pooled with phase-1 weights. pseudo: weight of the +1/-1 pseudo-disagreements used
    only for the interval (not the point estimate)."""
    H = len(Nh); N = Nh.sum(); W = Nh / N
    nh = np.bincount(ss, minlength=H); n = len(ss); g = gold.sum()
    w = (Nh / nh)[ss]                       # phase-1 weights
    fbar = sum(W[h] * f[ss == h].mean() for h in range(H))
    d = ys[gold] - f[gold]; wg = w[gold]
    dbar = (wg * d).sum() / wg.sum()
    theta = fbar + dbar
    # analytic variance with pseudo units
    da = np.concatenate([d, [1.0, -1.0]]); wa = np.concatenate([wg, [wg.mean()] * 2]) * np.concatenate([np.ones(g), [pseudo] * 2])
    if pseudo == 0: da, wa = d, wg
    mu = (wa * da).sum() / wa.sum()
    geff = wa.sum() ** 2 / (wa ** 2).sum()
    sd2 = (wa * (da - mu) ** 2).sum() / wa.sum() * geff / max(geff - 1, 1)
    yg = ys[gold]; ya = np.concatenate([yg, [1.0, 0.0]]) if pseudo else yg
    sy2 = ya.var(ddof=1)
    V1 = sum(W[h] ** 2 * (1 - nh[h] / Nh[h]) * sy2 / nh[h] for h in range(H))
    V2 = (1 - g / n) * sd2 / g
    V = V1 + V2
    if method == "t":
        q = stats.t.ppf(1 - alpha / 2, df=g - 1)
        lo, hi = theta - q * np.sqrt(V), theta + q * np.sqrt(V)
    else:
        # bootstrap: resample S within strata (gold travels), recompute; then rescale to V
        reps = np.empty(B)
        idx_all = []
        rows = [np.where(ss == h)[0] for h in range(H)]
        I = np.concatenate([r[rng.integers(0, len(r), size=(B, len(r)))] for r in rows], axis=1)
        fb = np.zeros(B)
        off = 0
        for h, r in enumerate(rows):
            fb += W[h] * f[I[:, off:off + len(r)]].mean(1); off += len(r)
        gm = gold[I]; dd = np.where(gm, (np.nan_to_num(ys) - f)[I], 0.0); ww = np.where(gm, w[I], 0.0)
        db = (ww * dd).sum(1) / np.maximum(ww.sum(1), 1e-12)
        reps = fb + db
        ve = reps.var(ddof=1)
        r = np.sqrt(V / ve) if ve > 0 else 0.0
        if ve == 0:
            q = stats.t.ppf(1 - alpha / 2, df=g - 1); lo, hi = theta - q * np.sqrt(V), theta + q * np.sqrt(V)
        else:
            lo, hi = np.quantile(theta + r * (reps - theta), [alpha / 2, 1 - alpha / 2])
    return theta, max(lo, 0.0), min(hi, 1.0)

def hyper_ci(x, g, N, alpha=0.1):
    K = np.arange(N + 1)
    ok = (stats.hypergeom.sf(x - 1, N, K, g) > alpha / 2) & (stats.hypergeom.cdf(x, N, K, g) > alpha / 2)
    return K[ok].min() / N, K[ok].max() / N

def sim(R=300, Nh=(20, 20, 20), nh=None, g=20, p=(0.9, 0.75, 0.6), se=0.85, sp=0.7,
        abst=(0.05, 0.1, 0.35), seed=0, shuffle=False, alpha=0.1, **kw):
    rng = np.random.default_rng(seed); Nh = np.array(Nh); nh = Nh if nh is None else np.array(nh)
    out = dict(cov=0, w=0.0, covx=0, wx=0.0)
    st = np.repeat(np.arange(3), Nh)
    for _ in range(R):
        Y = (rng.random(Nh.sum()) < np.array(p)[st]).astype(float); truth = Y.mean()
        idx = np.concatenate([rng.choice(np.where(st == h)[0], nh[h], replace=False) for h in range(3)])
        ys = Y[idx]; ss = st[idx]
        v = np.where(ys == 1, rng.random(len(ys)) < se, rng.random(len(ys)) > sp).astype(float)
        if shuffle: v = rng.permutation(v)
        ab = rng.random(len(ys)) < np.array(abst)[ss]
        f = v.copy()
        for h in range(3):
            mm = (ss == h) & ~ab; f[(ss == h) & ab] = f[mm].mean() if mm.any() else 0.5
        gold = np.zeros(len(ys), bool); gold[rng.choice(len(ys), g, replace=False)] = True
        yy = np.where(gold, ys, np.nan)
        th, lo, hi = ppi(ss, Nh, f, yy, gold, rng, alpha=alpha, **kw)
        out["cov"] += lo <= truth <= hi; out["w"] += hi - lo
        if (nh == Nh).all():
            lo2, hi2 = hyper_ci(int(ys[gold].sum()), g, Nh.sum(), alpha)
            out["covx"] += lo2 <= truth <= hi2; out["wx"] += hi2 - lo2
    return {k: round(v / R, 3) for k, v in out.items()}

if __name__ == "__main__":
    scen = {
        "base": {}, "shuffled": dict(shuffle=True), "strong": dict(se=0.95, sp=0.9, abst=(0, 0, .1)),
        "perfect": dict(se=1.0, sp=1.0, abst=(0, 0, 0)), "highprec": dict(p=(0.97, 0.95, 0.9)),
        "twophase": dict(Nh=(100, 100, 100), nh=(20, 20, 20)),
    }
    for meth, ps in [("boot", 0.0), ("boot", 0.5), ("boot", 1.0), ("t", 0.5), ("t", 1.0)]:
        t = time.time()
        res = {k: sim(seed=i + 10, method=meth, pseudo=ps, **v) for i, (k, v) in enumerate(scen.items())}
        print(meth, ps, round(time.time() - t, 2))
        for k, v in res.items(): print("   ", k, v)
