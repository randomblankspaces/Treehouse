import json, pathlib, sys, collections
store, rid = pathlib.Path(sys.argv[1]), sys.argv[2]
d = store / "runs" / rid / "trials"
inv, cl = d / "t-0.investigation.json", d / "t-0.claims.jsonl"
if not inv.exists(): print("NO RUN", rid); sys.exit()
j = json.loads(inv.read_text()); ds = j.get("decisions", [])
print(rid, "decisions", len(ds), dict(collections.Counter(x.get("tool") for x in ds)))
for x in ds:
    print(" -", x.get("tool"), json.dumps(x.get("parameters"))[:70], "c=", x.get("confidence"), "|", (x.get("rationale") or "")[:140].replace("\n", " "))
rows = [json.loads(l) for l in cl.read_text().splitlines() if l.strip()] if cl.exists() else []
print("claims", len(rows), dict(collections.Counter(r.get("status") for r in rows)))
for r in rows[:6]: print(" *", r.get("status"), r.get("confidence"), (r.get("reason") or "")[:140].replace("\n", " "))
print("SUMMARY-END", rid)
