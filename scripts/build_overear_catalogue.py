#!/usr/bin/env python3
"""Build a static, rig-filtered over-ear catalogue from AutoEq."""
import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ARCHIVE = "https://github.com/jaakkopasanen/AutoEq/archive/refs/heads/master.zip"
ROOT = Path("data/over-ear")
RIG = "HMS II.3"
MEASUREMENTS = "measurements/Rtings/data/over-ear/HMS II.3/"
TARGETS = [
    ("harman-2018", "Harman over-ear 2018", "targets/HMS II.3 Harman over-ear 2018.csv"),
    ("harman-2018-no-bass", "Harman over-ear 2018 (without bass shelf)", "targets/HMS II.3 Harman over-ear 2018 without bass.csv"),
]
SOURCE = "https://github.com/jaakkopasanen/AutoEq"


def points_from_csv(text):
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    header = next((i for i, row in enumerate(rows) if any("freq" in c.lower() for c in row)), None)
    if header is None:
        return []
    names = [c.strip().lower() for c in rows[header]]
    fi = next(i for i, c in enumerate(names) if "freq" in c)
    vi = names.index("raw") if "raw" in names else next(i for i in range(len(names)) if i != fi)
    values = {}
    for row in rows[header + 1:]:
        try:
            f, v = float(row[fi]), float(row[vi])
            if 15 <= f <= 24000 and -150 <= v <= 200:
                values[f] = v
        except (ValueError, IndexError):
            continue
    points = [[f, values[f]] for f in sorted(values)]
    return points if len(points) >= 35 and points[0][0] <= 150 and points[-1][0] >= 7000 else []


def index_records(records):
    return [{**{k: r[k] for k in ("id", "name", "reviewer", "rig", "path", "sourceUrl")},
             "shard": f"measurements-{i // 40:04d}.json"} for i, r in enumerate(records)]


def self_check():
    rows = "\n".join(f"{20 * 1000 ** (i / 34):.2f},{i - 17},0" for i in range(35))
    points = points_from_csv("frequency,raw,error\n" + rows)
    assert len(points) == 35 and points[0][0] == 20 and points[-1][0] >= 19000
    assert points_from_csv("frequency,raw\n1000,0\n") == []
    sample = [{k: "x" for k in ("name", "reviewer", "rig", "path", "sourceUrl")} | {"id": i} for i in range(41)]
    index = index_records(sample)
    assert len(index) == 41 and index[39]["shard"] == "measurements-0000.json" and index[40]["shard"] == "measurements-0001.json"
    print("AutoEq CSV parser self-check passed")


def build():
    ROOT.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(ARCHIVE, headers={"User-Agent": "JoeV5-Catalogue/1.0"})
    with urllib.request.urlopen(request, timeout=240) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    members = {PurePosixPath(m.filename).as_posix().split("/", 1)[-1]: m for m in archive.infolist() if not m.is_dir()}
    records = []
    for path, member in sorted(members.items()):
        if not path.startswith(MEASUREMENTS) or not path.lower().endswith(".csv") or member.file_size > 600000:
            continue
        points = points_from_csv(archive.read(member).decode("utf-8-sig", errors="replace"))
        if not points:
            continue
        name = PurePosixPath(path).stem
        records.append({"id": len(records), "name": name, "reviewer": "RTINGS", "rig": RIG,
                        "path": path, "sourceUrl": SOURCE + "/blob/master/" + path.replace(" ", "%20"), "points": points})
    if not records:
        raise RuntimeError("No compatible HMS II.3 over-ear measurements found; leaving existing catalogue intact")

    targets = []
    for target_id, name, path in TARGETS:
        member = members.get(path)
        points = points_from_csv(archive.read(member).decode("utf-8-sig", errors="replace")) if member else []
        if not points:
            raise RuntimeError(f"Missing or invalid AutoEq target: {path}")
        targets.append({"id": target_id, "name": name, "rig": RIG, "compensation": name,
                        "path": path, "sourceUrl": SOURCE + "/blob/master/" + path.replace(" ", "%20"), "points": points})

    shard_paths = []
    for old in ROOT.glob("measurements-*.json"):
        old.unlink()
    for offset in range(0, len(records), 40):
        shard = f"measurements-{offset // 40:04d}.json"
        shard_paths.append(shard)
        (ROOT / shard).write_text(json.dumps(records[offset:offset + 40], separators=(",", ":")), encoding="utf-8")
    (ROOT / "index.json").write_text(json.dumps(index_records(records), separators=(",", ":")), encoding="utf-8")
    (ROOT / "targets.json").write_text(json.dumps(targets, separators=(",", ":")), encoding="utf-8")
    (ROOT / "catalogue.json").write_text(json.dumps({"version": 1, "count": len(records), "source": SOURCE,
        "reviewer": "RTINGS", "rig": RIG, "targets": "targets.json", "index": "index.json", "shards": shard_paths}, separators=(",", ":")), encoding="utf-8")
    print(f"Built {len(records)} {RIG} over-ear measurements in {len(shard_paths)} shards")


if __name__ == "__main__":
    import sys
    self_check()
    if "--self-check" not in sys.argv:
        build()

