"""E. coli evidence at the inland bathing waters, for the site's research pages (docs/ECOLI-EVIDENCE-CONTRACT-v1.md):
every EA lab sample, with the lab's qualifier, beside what SwimSignal's model would have estimated for it in
hindsight. Offline:

    DIPCAST_ROOT=<checkout with data/raw/bwq_samples.parquet> uv run python scripts/export_ecoli_evidence.py export
    uv run python scripts/export_ecoli_evidence.py check [PATH]

The hindsight estimate is the concentration study's (#466) leave-one-year-out prediction of the production model's
form: fitted without any sample from that year, with archived lead-0 forecast rain and replayed exposure. It is not
the forecast the site issued that day, and the file says so on every site. Samples outside the study's rows (2023,
and bathing waters with no overflow upstream) have no hindsight estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
ATLAS = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11-atlas-rows.csv"
SITES = ROOT / "data" / "raw" / "bathing_waters_inland.json"
SCHEMA, VERSION = "swimsignal.ecoli-evidence", "1.0.0"
LINE = 900
CLAIM = {
    "public_wording": "Environment Agency lab samples of E. coli at this bathing water, with the date each was taken. "
                      "Beside them, what SwimSignal's model would have estimated in hindsight, refitted without that "
                      "year's samples: not the forecast the site showed that day. A miss is a mismatch between model "
                      "and sample, not evidence about any particular source.",
    "not_claimed": ["that a sample shows the water was safe or unsafe at another time",
                    "that a hindsight estimate was the forecast the site issued",
                    "that a mismatch points to a particular overflow, company or source"],
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(wqa: Path | None = None) -> dict:
    """`wqa`: the live verifier's Water Quality Archive samples (the state release's ecoli_samples.parquet), whose
    samples the cached bathing-water file lacks are added (statutory monitoring only, as ingest.wqa keeps them)."""
    from dipcast import config
    raw_path = config.RAW / "bwq_samples.parquet"
    inputs = [raw_path, ATLAS, SITES] + ([wqa] if wqa else [])
    before = {p.name: sha256(p) for p in inputs}
    raw = pd.read_parquet(raw_path).drop_duplicates(["bw_id", "sample_time"]).assign(source="bathing water service")
    added = 0
    if wqa:
        w = pd.read_parquet(wqa)
        have = set(zip(raw["bw_id"], raw["sample_time"], strict=True))
        w = w[[(b, t) not in have for b, t in zip(w["bw_id"], w["sample_time"], strict=True)]]
        w = w.assign(ie=pd.NA, ie_qual=None, source="Water Quality Archive")
        added = len(w)
        raw = pd.concat([raw, w[["bw_id", "name", "kind", "sample_time", "ecoli", "ecoli_qual", "ie", "ie_qual", "source"]]],
                        ignore_index=True)
    raw = raw.sort_values(["bw_id", "sample_time"])
    atlas = pd.read_csv(ATLAS)
    atlas["key"] = atlas["bw_id"] + "|" + pd.to_datetime(atlas["sample_time"], utc=True).dt.strftime("%Y-%m-%dT%H:%MZ")
    hind = atlas.set_index("key")["p_loyo"].to_dict()
    sites = {s["id"]: s for s in json.loads(SITES.read_text())}
    out = []
    for bid, g in raw.groupby("bw_id"):
        s = sites.get(bid, {})
        rows = []
        for r in g.itertuples():
            key = f"{bid}|{pd.Timestamp(r.sample_time).tz_convert('UTC').strftime('%Y-%m-%dT%H:%MZ')}"
            p = hind.get(key)
            rows.append({"t": pd.Timestamp(r.sample_time).isoformat(timespec="minutes"), "ecoli": int(r.ecoli),
                         "q": r.ecoli_qual if r.ecoli_qual in ("<", ">") else None,
                         "ie": None if pd.isna(r.ie) else int(r.ie), "ie_q": r.ie_qual if r.ie_qual in ("<", ">") else None,
                         "src": "wqa" if r.source == "Water Quality Archive" else "bwq",
                         "over": bool(r.ecoli > LINE),
                         "hindsight": None if p is None or pd.isna(p) else round(float(p), 3)})
        with_h = [x for x in rows if x["hindsight"] is not None]
        out.append({"spot_id": f"bw-{bid}", "bw_id": bid, "name": s.get("name") or g["name"].iloc[0],
                    "kind": s.get("kind") or g["kind"].iloc[0], "samples": rows,
                    "summary": {"samples": len(rows), "over_900": int(sum(x["over"] for x in rows)),
                                "below_limit": int(sum(x["q"] == "<" for x in rows)),
                                "first": rows[0]["t"][:10], "last": rows[-1]["t"][:10],
                                "with_hindsight": len(with_h),
                                "hindsight_misses": int(sum(x["over"] and x["hindsight"] < 0.25 for x in with_h)),
                                "hindsight_false_alarms": int(sum(not x["over"] and x["hindsight"] >= 0.25 for x in with_h))}})
    after = {p.name: sha256(p) for p in inputs}
    if after != before:
        raise SystemExit("an input changed during the export")
    return {"schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "line": LINE, "warn_at": 0.25,
            "hindsight": {"model": "production's form (rain, upstream exposure, season, soil moisture for rivers), "
                                   "refitted leaving out each year in turn (docs/CONCENTRATION-STUDY-2026-11.md)",
                          "rain": "archived lead-0 forecast rain", "exposure": "replayed lead-0 exposure",
                          "issued": False, "rows": int(atlas["p_loyo"].notna().sum())},
            "sources": [{"file": k, "sha256": v} for k, v in before.items()],
            "attribution": ["Environment Agency bathing water quality data, Open Government Licence v3.0"],
            "claim": CLAIM, "sites": out,
            "sample_sources": {"bwq": "Environment Agency bathing water quality service (cached 12 Sep 2026)",
                               "wqa": "Environment Agency Water Quality Archive, statutory monitoring (the live "
                                      "verifier's copy), for samples the cached file lacks"},
            "coverage": {"sites": len(out), "samples": sum(x["summary"]["samples"] for x in out),
                         "added_from_wqa": added,
                         "with_hindsight": sum(x["summary"]["with_hindsight"] for x in out)}}


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("generated_at", "line", "hindsight", "sources", "attribution", "claim", "sites", "coverage"):
        if k not in doc:
            err.append(f"missing {k}")
    if doc.get("hindsight", {}).get("issued") is not False:
        err.append("hindsight.issued must be false: these are not issued forecasts")
    if "not the forecast the site showed" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say the hindsight estimate is not the issued forecast")
    for s in doc.get("sites", []):
        ts = [x["t"] for x in s["samples"]]
        if ts != sorted(ts):
            err.append(f"{s['bw_id']}: samples not in time order")
        for x in s["samples"]:
            if x.get("src") not in ("bwq", "wqa"):
                err.append(f"{s['bw_id']}: unknown sample source")
            if x["q"] not in (None, "<", ">"):
                err.append(f"{s['bw_id']}: qualifier {x['q']!r}")
            if x["hindsight"] is not None and not 0 <= x["hindsight"] <= 1:
                err.append(f"{s['bw_id']}: hindsight out of range")
            if x["over"] != (x["ecoli"] > doc.get("line", LINE)):
                err.append(f"{s['bw_id']}: over flag disagrees with the count")
    if doc.get("coverage", {}).get("samples") != sum(len(s["samples"]) for s in doc.get("sites", [])):
        err.append("coverage count does not match")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--wqa", type=Path, help="the state release's ecoli_samples.parquet")
    a = ap.parse_args()
    if a.step == "export":
        doc = build(a.wqa)
        problems = check(doc)
        if problems:
            raise SystemExit("\n".join(problems))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(json.dumps(doc["coverage"]))
        print(f"wrote {a.out} ({a.out.stat().st_size:,} bytes)")
    else:
        p = Path(a.path) if a.path else OUT
        problems = check(json.loads(p.read_text()))
        print("\n".join(problems) or f"{p}: holds the contract")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
