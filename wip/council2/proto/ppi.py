import numpy as np, time
from scipy import stats

def hyper_ci(x, g, N, alpha=0.1):
    K = np.arange(N + 1)
    # P(X>=x|K) and P(X<=x|K)
    up = stats.hypergeom.sf(x - 1, N, K, g)
    lo = stats.hypergeom.cdf(x, N, K, g)
    ok = (up > alpha / 2) & (lo > alpha / 2)
    Ks = K[ok]
    return Ks.min() / N, Ks.max() / N

def ppi_strat(strata, Nh, f, y, gold, B, rng, alpha=0.1, guard=True):
    """strata: stratum index per sampled unit (phase1 sample S); Nh: population sizes;
    f: predictor in [0,1] per unit (abstain already mapped); y: gold label (nan if not gold);
    gold: bool mask."""
    H = len(Nh); N = Nh.sum(); W = Nh / N
    theta = 0.0; V = 0.0
    reps = np.zeros(B)
    for h in range(H):
        m = strata == h
        fs = f[m]; gs = gold[m]; ys = y[m]
        n = m.sum(); g = gs.sum()
        d = ys[gs] - fs[gs]
        th = fs.mean() + d.mean()
        theta += W[h] * th
        sy2 = ys[gs].var(ddof=1) if g > 1 else 0.0
        sd2 = d.var(ddof=1) if g > 1 else 0.0
        V += W[h] ** 2 * ((1 - n / Nh[h]) * sy2 / n + (1 - g / n) * sd2 / g)
        fg = fs[gs]; fng = fs[~gs]
        ig = rng.integers(0, g, size=(B, g))
        ing = rng.integers(0, n - g, size=(B, n - g)) if n > g else None
        s = fg[ig].sum(1) + (fng[ing].sum(1) if ing is not None else 0)
        reps += W[h] * (s / n + d[ig].mean(1))
    ve = reps.var(ddof=1)
    r = np.sqrt(V / ve) if ve > 0 else 0.0
    adj = theta + r * (reps - theta)
    lo, hi = np.quantile(adj, [alpha / 2, 1 - alpha / 2])
    lo, hi = max(lo, 0.0), min(hi, 1.0)
    return theta, lo, hi

def sim(R=300, N=60, n_per=None, g_per=(7, 7, 6), p=(0.9, 0.75, 0.6), se=0.85, sp=0.7,
        abst=(0.05, 0.1, 0.35), B=400, seed=0, shuffle=False, alpha=0.1):
    rng = np.random.default_rng(seed)
    Nh = np.array([20, 20, 20]) if N == 60 else np.array([N // 3] * 3)
    if n_per is None: n_per = Nh
    cov = 0; widths = []; gw = []; covg = 0
    for r in range(R):
        Y = np.concatenate([rng.random(Nh[h]) < p[h] for h in range(3)]).astype(float)
        st = np.repeat(np.arange(3), Nh)
        truth = Y.mean()
        # phase 1
        idx = np.concatenate([rng.choice(np.where(st == h)[0], n_per[h], replace=False) for h in range(3)])
        ys = Y[idx]; ss = st[idx]
        v = np.where(ys == 1, rng.random(len(ys)) < se, rng.random(len(ys)) > sp).astype(float)
        ab = rng.random(len(ys)) < np.array(abst)[ss]
        if shuffle: v = rng.permutation(v)
        f = v.copy()
        for h in range(3):
            mm = (ss == h) & ~ab
            mh = f[mm].mean() if mm.any() else 0.5
            f[(ss == h) & ab] = mh
        gold = np.zeros(len(ys), bool)
        for h in range(3):
            w = np.where(ss == h)[0]
            gold[rng.choice(w, g_per[h], replace=False)] = True
        yy = np.where(gold, ys, np.nan)
        th, lo, hi = ppi_strat(ss, Nh, f, yy, gold, B, rng, alpha)
        cov += lo <= truth <= hi; widths.append(hi - lo)
        # gold-only stratified (classical) via same function with f=0 predictor
        th2, lo2, hi2 = ppi_strat(ss, Nh, np.zeros_like(f), yy, gold, B, rng, alpha)
        covg += lo2 <= truth <= hi2; gw.append(hi2 - lo2)
    return cov / R, np.mean(widths), covg / R, np.mean(gw)

if __name__ == "__main__":
    t = time.time()
    print("census verifier, good", sim(seed=1), time.time() - t)
    t = time.time()
    print("census verifier, shuffled", sim(seed=2, shuffle=True), time.time() - t)
    print("strong verifier", sim(seed=3, se=0.95, sp=0.9, abst=(0, 0, .1)))
    print("high precision", sim(seed=4, p=(0.97, 0.95, 0.9)))
    print("two-phase N=300,n=30/str", sim(seed=5, N=300, n_per=np.array([30, 30, 30])))
    # exact hypergeometric coverage
    N, g, a = 60, 20, 0.1
    mins = 1
    for K in range(N + 1):
        xs = np.arange(g + 1); pm = stats.hypergeom.pmf(xs, N, K, g)
        c = sum(pm[x] for x in xs if hyper_ci(x, g, N, a)[0] <= K / N <= hyper_ci(x, g, N, a)[1])
        mins = min(mins, c)
    print("hypergeom min coverage", mins)
