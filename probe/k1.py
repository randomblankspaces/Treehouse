"""K-1 readiness probe (run in Workshop): models, thinking, LGND coverage, GRW, RODA, Polly, AgentCore. No secrets in output."""
import json, re, subprocess, time, urllib.request
import boto3
from botocore import UNSIGNED
from botocore.config import Config

out = {"ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
red = lambda s: re.sub(r"\b\d{12}\b", "<acct>", str(s))[:600]
br = boto3.client("bedrock-runtime", region_name="us-east-1")

def converse(model, extra=None, max_tokens=64, text="Reply with the single word: ok"):
    kw = dict(modelId=model, messages=[{"role": "user", "content": [{"text": text}]}],
              inferenceConfig={"maxTokens": max_tokens})
    if extra: kw["additionalModelRequestFields"] = extra
    try:
        r = br.converse(**kw)
        blocks = r["output"]["message"]["content"]
        return {"ok": True, "usage": r.get("usage"), "kinds": [list(b)[0] for b in blocks],
                "text": "".join(b.get("text", "") for b in blocks)[:80]}
    except Exception as e:
        return {"ok": False, "error": red(e)}

out["haiku"] = converse("us.anthropic.claude-haiku-5-5")
q = "Is 1,280 m a good grid cell size for finding 40 m warehouses? One sentence."
out["thinking_adaptive"] = converse("us.anthropic.claude-sonnet-5-5", {"thinking": {"type": "adaptive"}}, 2048, q)
out["thinking_enabled"] = converse("us.anthropic.claude-sonnet-5-5", {"thinking": {"type": "enabled", "budget_tokens": 1024}}, 2048, q)

def gh(lat, lon, n=2):
    b32 = "0123456789bcdefghjkmnpqrstuvwxyz"; la, lo = [-90.0, 90.0], [-180.0, 180.0]; bits = []; even = True
    while len(bits) < n * 5:
        r = lo if even else la; v = lon if even else lat; mid = sum(r) / 2
        bits.append(1 if v >= mid else 0); r[0 if v >= mid else 1] = mid; even = not even
    return "".join(b32[int("".join(map(str, bits[i:i + 5])), 2)] for i in range(0, len(bits), 5))

s3 = boto3.client("s3", region_name="us-west-2", config=Config(signature_version=UNSIGNED))
base = "clay/lgnd-embeddings/monthly-aggregated/model_version=v1.5/collection=sentinel-2-l2a/chip_size=1280m/dims=256/"
try:
    pref = [p["Prefix"] for pg in s3.get_paginator("list_objects_v2").paginate(Bucket="us-west-2.opendata.source.coop", Prefix=base, Delimiter="/") for p in pg.get("CommonPrefixes", [])]
    have = sorted(p.split("geohash=")[1].strip("/") for p in pref if "geohash=" in p)
    out["lgnd_geohash_count"] = len(have); out["lgnd_geohashes_sample"] = have[:80]
    places = {"nagoya": (35.085, 136.87), "gifu": (35.42, 136.76), "chattogram": (22.30, 91.80), "dhaka": (23.78, 90.40),
              "akita_noshiro": (40.2, 140.0), "kamisu": (35.9, 140.7), "choshi": (35.73, 140.83), "jhimpir_pk": (25.0, 68.0)}
    out["lgnd_coverage"] = {}
    for k, (la, lo) in places.items():
        g = gh(la, lo); entry = {"geohash": g, "present": g in have}
        if entry["present"]:
            yrs = s3.list_objects_v2(Bucket="us-west-2.opendata.source.coop", Prefix=f"{base}geohash={g}/", Delimiter="/").get("CommonPrefixes", [])
            entry["years"] = [p["Prefix"].rstrip("/").split("=")[-1] for p in yrs]
        out["lgnd_coverage"][k] = entry
except Exception as e:
    out["lgnd_error"] = red(e)

try:
    rel = json.load(urllib.request.urlopen("https://api.github.com/repos/microsoft/global-renewables-watch/releases/tags/v1.0", timeout=20))
    out["grw_assets"] = [{"name": a["name"], "size": a["size"], "url": a["browser_download_url"]} for a in rel.get("assets", [])]
except Exception as e:
    out["grw_error"] = red(e)

try:
    p = subprocess.run(["uvx", "awslabs.roda-mcp-server@latest", "--help"], capture_output=True, text=True, timeout=120)
    out["roda"] = {"rc": p.returncode, "out": red(p.stdout + p.stderr)[:400]}
except Exception as e:
    out["roda"] = {"error": red(e)}

try:
    pl = boto3.client("polly", region_name="us-east-1")
    v = pl.describe_voices(Engine="neural", LanguageCode="en-US")["Voices"]
    out["polly_neural_voices"] = [x["Id"] for x in v][:12]
    a = pl.synthesize_speech(Engine="neural", OutputFormat="mp3", Text="Treehouse narrator test.", VoiceId="Joanna")
    out["polly_synth_bytes"] = len(a["AudioStream"].read())
except Exception as e:
    out["polly_error"] = red(e)

try:
    ac = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
    ev = ac.list_evaluators()
    out["agentcore_evaluators"] = [e.get("evaluatorName") or e.get("evaluatorId") for e in ev.get("evaluators", [])][:40]
except Exception as e:
    out["agentcore_error"] = red(e)

out["note"] = "Direct probe calls (not via spend guard): ~3 tiny Bedrock calls, est < $0.05; 1 Polly call (24 chars)."
print(json.dumps(out, indent=1))
