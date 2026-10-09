#!/usr/bin/env python3
"""Build a strict-source 711 catalogue from Squig-Rank's published raw cache.
Unknown rigs and other headphone measurement formats are excluded.
"""
import gzip, io, json, re, urllib.request, zipfile
from pathlib import Path
from collections import Counter
URL="https://github.com/PEQHUB/Squig-Rank/archive/refs/heads/main.zip"
OUT=Path("data"); OUT.mkdir(exist_ok=True)
# Explicit source allowlist, not the upstream classifier's 'default to 711' rule.
# Crinacle uses a separately identifiable 711 graph.
SOURCES={"crinacle","superreview","hbb","precog","timmyv","aftersound","paulwasabii","vortexreviews","tonedeafmonk","rg","nymz","eliseaudio","achoreviews","dchpgall","animagus","ankramutt","atechreviews","awsmdanny","bakkwatan","banzai1122","bassyalexander","breampike","bryaudioreviews","bukanaudiophile","csi-zone","ekaudio","enemyspider","eplv","foxtoldmeso","freeryder05","hu-fi","ianfann","ideru","iemocean","iemworld","isaiahse","jacstone","jaytiss","joshtbvo","kazi","lestat","loomynarty","lown-fi","melatonin","mmagtech","musicafe","obodio","practiphile","recode","riz","smirk","soundignity","suporsalad","tgx78","therollo9","scboy","seanwee","silicagel","sl0the","soundcheck39","tanchjim","tedthepraimortis","treblewellxtended","yanyin","yoshiultra"}
DENY={"5128","kb006","kb6","gras","headphone","hats","clone","harman","target"}
print("Fetching Squig-Rank measurement cache...",flush=True)
req=urllib.request.Request(URL,headers={"User-Agent":"JoeV5/1.0"})
with urllib.request.urlopen(req,timeout=240) as resp: data=resp.read()
print("Downloaded bytes",len(data),flush=True)
z=zipfile.ZipFile(io.BytesIO(data))
index_name=next(x for x in z.namelist() if x.endswith("/dist/cache/index.json"))
idx=json.loads(z.read(index_name)); prefix=index_name.removesuffix("index.json")
entries=idx["entries"]; rows=[]; counts=Counter(); skipped=Counter()
def parse(raw):
    points=[]
    for line in raw.splitlines():
        p=re.split(r"[\s,;]+",line.strip())
        if len(p)<2: continue
        try: f,v=float(p[0]),float(p[1])
        except ValueError: continue
        if 15<=f<=24000 and -150<=v<=200: points.append([f,v])
    points=sorted({f:v for f,v in points}.items())
    return points if len(points)>=35 and points[0][0]<=150 and points[-1][0]>=7000 else []
for key,meta in entries.items():
    domain=key.split("::",1)[0].lower()
    if domain not in SOURCES or str(meta.get("rig","")).lower()!="711": skipped["rig/source"]+=1;continue
    name=str(meta.get("name","")).strip()
    if not name or any(term in (key+" "+name).lower() for term in DENY):skipped["label"]+=1;continue
    if meta.get("type")=="headphone":skipped["headphone"]+=1;continue
    h=meta.get("hash")
    if not re.fullmatch("[a-f0-9]{16,64}",str(h)):skipped["hash"]+=1;continue
    filename=prefix+"measurements/"+h+".bin"
    try: points=parse(gzip.decompress(z.read(filename)).decode("utf-8-sig",errors="replace"))
    except (KeyError,OSError):skipped["missing"]+=1;continue
    if not points:skipped["parse"]+=1;continue
    ident=len(rows)
    rows.append({"id":ident,"name":name,"reviewer":domain,"source":"Squig-Rank raw cache","path":key,"rig":"711 (source allowlist; independent calibration unverified)","points":points})
    counts[domain]+=1
for old in OUT.glob("measurements-*.json"):old.unlink()
catalogue=[]
for i in range(0,len(rows),100):
    filename=f"measurements-{i//100:04d}.json"
    part=rows[i:i+100]
    (OUT/filename).write_text(json.dumps(part,separators=(",",":")),encoding="utf-8")
    catalogue.extend({k:v for k,v in r.items() if k!="points"}|{"shard":filename} for r in part)
# Keep the index under GitHub Contents API's 1 MB inline-content limit.
for old_index in OUT.glob("catalogue-*.json"): old_index.unlink()
index_files=[]
for i in range(0,len(catalogue),500):
    fname=f"catalogue-{i//500:04d}.json"
    (OUT/fname).write_text(json.dumps(catalogue[i:i+500],separators=(",",":")),encoding="utf-8")
    index_files.append(fname)
(OUT/"catalogue.json").write_text(json.dumps({"version":3,"count":len(rows),"sources":dict(counts),"skipped":dict(skipped),"index_files":index_files},separators=(",",":")),encoding="utf-8")
print("711 source-filtered curves:",len(rows),"sources:",len(counts),"skipped:",dict(skipped),flush=True)
