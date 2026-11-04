import numpy as np
from ppi2 import ppi
def run(R=300, seed=16, drop=False, p=(0.9,0.75,0.6), se=.85, sp=.70, g=20, Nh=(20,20,20), ab_y0=0.5, ab_y1=0.2):
    rng=np.random.default_rng(seed); Nh=np.array(Nh); st=np.repeat(np.arange(3),Nh)
    bias=[]; cov=0
    for _ in range(R):
        Y=(rng.random(Nh.sum())<np.array(p)[st]).astype(float); truth=Y.mean()
        ss=st; ys=Y
        v=np.where(ys==1, rng.random(len(ys))<se, rng.random(len(ys))>sp).astype(float)
        pab=np.where(ss==2, np.where(ys==0,ab_y0,ab_y1), np.array([.05,.10,0])[ss])
        ab=rng.random(len(ys))<pab
        f=v.copy()
        for h in range(3):
            mm=(ss==h)&~ab; f[(ss==h)&ab]=f[mm].mean() if mm.any() else .5
        pool=np.where(~ab)[0] if drop else np.arange(len(ys))
        gold=np.zeros(len(ys),bool); gold[rng.choice(pool,g,replace=False)]=True
        th,lo,hi=ppi(ss,Nh,f,np.where(gold,ys,np.nan),gold,rng,B=400,pseudo=.5)
        bias.append(th-truth); cov+=lo<=truth<=hi
    return round(np.mean(bias),4), cov/R
print("correct", run()); print("drop-abstentions mutation", run(drop=True))
print("mutation, Nh larger", run(drop=True, Nh=(40,40,40), g=30))
