import json, pathlib, sys, collections
store, rid = pathlib.Path(sys.argv[1]), sys.argv[2]
hits = [p for p in store.rglob("*") if rid in str(p) and p.is_dir() and (p / "manifest.json").exists()]
if not hits: print("NO RUN DIR", rid); sys.exit()
d = hits[0]; inv = next(d.glob("*.investigation.json"), None); cl = next(d.glob("*.claims.jsonl"), None)
if inv:
    j = json.loads(inv.read_text()); ds = j.get("decisions", [])
    print("decisions", len(ds), "tools", dict(collections.Counter(x.get("tool") for x in ds)))
    for x in ds: print(" ", x.get("tool"), json.dumps(x.get("parameters"))[:90], "conf", x.get("confidence"), "|", (x.get("rationale") or "")[:110].replace("\n", " "))
if cl:
    rows = [json.loads(l) for l in cl.read_text().splitlines() if l.strip()]
    print("claims", len(rows), dict(collections.Counter(r.get("status") for r in rows)))
print("SUMMARY-END", rid)
