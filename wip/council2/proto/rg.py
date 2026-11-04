import numpy as np
from scipy.special import logit, expit

def rg_ci(k_app, n, k_se, n_se, k_sp, n_sp, rng, B=1000, alpha=0.1, tau=0.0, jmin=0.2):
    # jeffreys-smoothed resampling of each of the three binomials
    pa = rng.binomial(n, k_app / n, B) / n
    se = rng.beta(k_se + .5, n_se - k_se + .5, B)
    sp = rng.beta(k_sp + .5, n_sp - k_sp + .5, B)
    if tau > 0:
        se = expit(logit(se) + tau * rng.standard_normal(B)); sp = expit(logit(sp) + tau * rng.standard_normal(B))
    J = se + sp - 1
    est = lambda pa, se, sp: np.clip((pa + sp - 1) / (se + sp - 1), 0, 1)
    seh = (k_se + .5) / (n_se + 1); sph = (k_sp + .5) / (n_sp + 1)
    point = est(k_app / n, seh, sph)
    if np.quantile(J, alpha / 2) <= jmin:
        return point, np.nan, np.nan, True
    reps = est(pa, se, sp)
    lo, hi = np.quantile(reps, [alpha / 2, 1 - alpha / 2])
    return point, lo, hi, False

def sim(R=300, N=50, prev=0.7, se=0.85, sp=0.8, nc=15, shift=0.0, tau=0.0, seed=0):
    rng = np.random.default_rng(seed); cov = 0; ab = 0; w = 0
    for _ in range(R):
        y = rng.random(N) < prev; truth = y.mean()
        set_ = expit(logit(se) + shift); spt = expit(logit(sp) - shift)
        v = np.where(y, rng.random(N) < set_, rng.random(N) > spt)
        kse = rng.binomial(nc, se); ksp = rng.binomial(nc, sp)
        p, lo, hi, a = rg_ci(v.sum(), N, kse, nc, ksp, nc, rng, tau=tau)
        if a: ab += 1; continue
        cov += lo <= truth <= hi; w += hi - lo
    k = R - ab
    return dict(cov=round(cov / max(k, 1), 3), abst=ab / R, w=round(w / max(k, 1), 3))

for name, kw in [("noshift", {}), ("shift .7 no infl", dict(shift=.7)), ("shift .7 tau .5", dict(shift=.7, tau=.5)),
                 ("noshift tau .5", dict(tau=.5)), ("weak verifier", dict(se=.6, sp=.55)), ("strong", dict(se=.95, sp=.95))]:
    print(name, sim(**kw))
