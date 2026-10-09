#!/usr/bin/env python3
"""Build a static FR catalogue from public source archives. No external dependencies."""
import io, json, os, re, urllib.request, zipfile
from pathlib import Path

SOURCES = [
    ("Suznyan", "https://github.com/Suznyan/IEM-and-Headphone-measurement-raw-database/archive/refs/heads/main.zip")
]
ROOT = Path("data")
ROOT.mkdir(exist_ok=True)
records = []
counts = {}
def parse(text):
    text = text.lstrip("\ufeff")
    if text.lstrip().startswith("["):
        try:
            obj = json.loads(text)
            if isinstance(obj, list) and len(obj) > 20:
                vals = [[float(row[0]), float(row[1])] for row in obj if isinstance(row, list) and len(row) >= 2]
                return clean(vals)
        except (ValueError, TypeError, KeyError): pass
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "//")): continue
        parts = re.split(r"[,;\t ]+", line.strip())
        try:
            if len(parts) >= 2: rows.append([float(parts[0]), float(parts[1])])
        except ValueError: pass
    return clean(rows)
def clean(rows):
    rows = sorted((f,v) for f,v in rows if 15 <= f <= 24000 and -150 <= v <= 200)
    dedup = {}
    for f,v in rows: dedup[f] = v
    rows = [[f,v] for f,v in sorted(dedup.items())]
    if len(rows) < 35 or rows[-1][0] < 7000 or rows[0][0] > 150: return []
    return rows
for source,url in SOURCES:
    print("Downloading",source,flush=True)
    req = urllib.request.Request(url, headers={"User-Agent":"JoeV5-Catalogue/1.0"})
    with urllib.request.urlopen(req,timeout=180) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    accepted = 0
    for member in archive.infolist():
        if member.is_dir() or not member.filename.lower().endswith((".txt",".csv",".tsv")) or member.file_size > 600000: continue
        path = "/".join(member.filename.split("/")[1:])
        if not path or "/targets/" in ("/"+path.lower()) or "target" in Path(path).stem.lower(): continue
        try:
            points = parse(archive.read(member).decode("utf-8-sig",errors="replace"))
            if not points: continue
            parts = path.split("/")
            reviewer = parts[0] if len(parts)>1 else source
            name = Path(path).stem
            # Preserve reviewer, source, and original file path. Do not assert rig compatibility.
            rec_id = len(records)
            records.append({"id":rec_id,"name":name,"reviewer":reviewer,"source":source,"path":path,"rig":"unverified","points":points})
            accepted += 1
        except Exception as exc:
            print("Skipped",path,str(exc)[:100])
    counts[source]=accepted
# Shard by 100 curves to keep GitHub Pages requests reasonably sized.
for old in ROOT.glob("measurements-*.json"): old.unlink()
index=[]
for i in range(0,len(records),100):
    shard = f"measurements-{i//100:04d}.json"
    data=records[i:i+100]
    (ROOT/shard).write_text(json.dumps(data,separators=(",",":")),encoding="utf-8")
    index.extend({"id":r["id"],"name":r["name"],"reviewer":r["reviewer"],"source":r["source"],"path":r["path"],"rig":r["rig"],"shard":shard} for r in data)
(ROOT/"catalogue.json").write_text(json.dumps({"version":1,"count":len(index),"sources":counts,"items":index},separators=(",",":")),encoding="utf-8")
print("Built catalogue",len(index),counts)
