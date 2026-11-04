import numpy as np
from scipy import stats
from ppi2 import sim, ppi, hyper_ci
# ADV scenario: N=200 claims, census verifier, n_gold=24, p=.8, se .85 sp .80
for nm, kw in [("ADV 85/80 no abst", dict(abst=(0,0,0))), ("ADV 85/80 15% abst", dict(abst=(.15,.15,.15))),
               ("shuffled", dict(abst=(0,0,0), shuffle=True)), ("strong 95/95", dict(se=.95, sp=.95, abst=(0,0,0)))]:
    for ps in (0.0, 0.5):
        r = sim(R=300, Nh=(67,67,66), g=24, p=(.8,.8,.8), se=kw.get('se',.85), sp=kw.get('sp',.80),
                abst=kw['abst'], shuffle=kw.get('shuffle',False), seed=7, pseudo=ps)
        print(nm, "pseudo", ps, r)
# B2 default predictive width: Beta-binomial mu=.5 kappa=10, n_new=200, 90%
bb = stats.betabinom(200, 5, 5); print("B2 default 90% width", (bb.ppf(.95)-bb.ppf(.05))/200, "point .5")
