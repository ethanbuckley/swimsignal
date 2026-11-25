"""Stage 1 of docs/RIVER-UNSEEN-PROTOCOL-2026-11.md: count the fetched river E. coli rows and place their sampling
points, without reading a result. Offline, in a scratch root (AGENTS.md: a worktree alone does not isolate data):

    export DIPCAST_ROOT=<scratch copy of data/> DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<scratch>/cache
    python scripts/river_unseen/stage.py <fetch out dir> docs/river-unseen

Writes <fetch out dir>/samples.parquet (sealed: it holds the results, which this script carries as text and never
prints, summarises or joins), and in the second folder points.csv (every sampling point, its counts and each rule's
outcome; no result) and manifest.json (counts, duplicate checks, the kill rule's figures, the sealed table's hash).
Data: Environment Agency, Open Government Licence v3.0."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

KEPT_PURPOSES = {
    "ENVIRONMENTAL MONITORING STATUTORY (EU DIRECTIVES)": "MS",
    "ENVIRONMENTAL MONITORING (GQA & RE ONLY)": "MP",
    "MONITORING (UK GOVT POLICY - NOT GQA OR RE)": "MU",
    "MONITORING (NATIONAL AGENCY POLICY)": "MN",
    "PLANNED INVESTIGATION (LOCAL MONITORING)": "PI",
    "PLANNED INVESTIGATION (NATIONAL AGENCY POLICY)": "PN",
}
MATERIAL = "RIVER / RUNNING SURFACE WATER"
HELD_OUT, LATER = (2012, 2022), (2023, 2026)
MIN_ROWS, MIN_SEASONS, SNAP_M, BENCH_M, MIN_POINTS = 30, 3, 50.0, 500.0, 30
COLUMNS = {"id": "id", "samplingPoint.notation": "point", "samplingPoint.prefLabel": "label",
           "samplingPoint.easting": "easting", "samplingPoint.northing": "northing", "samplingPoint.region": "region",
           "samplingPoint.area": "area", "samplingPoint.samplingPointStatus": "status", "phenomenonTime": "time",
           "samplingPurpose": "purpose", "sampleMaterialType": "material", "result": "result", "unit": "unit"}


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().upper()


def load_pages(raw: Path) -> tuple[pd.DataFrame, dict]:
    """Every fetched row, results as text, one row per observation id, and the duplicate counts."""
    frames = [pd.read_csv(f, dtype=str, keep_default_na=False) for f in sorted(raw.glob("ecoli_F6_*.csv"))
              if f.stat().st_size]
    rows = pd.concat(frames, ignore_index=True)[list(COLUMNS)].rename(columns=COLUMNS)
    checks = {"pages": len(frames), "rows_fetched": int(len(rows)), "repeated_ids": int(rows["id"].duplicated().sum())}
    rows = rows.drop_duplicates("id").reset_index(drop=True)
    same = rows.duplicated(["point", "time"], keep=False)
    checks.update(rows=int(len(rows)), rows_sharing_point_and_time=int(same.sum()))
    return rows, checks


def mark(rows: pd.DataFrame) -> pd.DataFrame:
    """Adds year, month, the purpose's code where kept, `kept` (material, season and purpose) and `span`."""
    t = pd.to_datetime(rows["time"].str.slice(0, 19), errors="coerce")
    rows = rows.assign(year=t.dt.year, month=t.dt.month, purpose_code=rows["purpose"].map(squash).map(KEPT_PURPOSES))
    rows["kept"] = ((rows["material"].map(squash) == MATERIAL) & rows["month"].between(5, 9)
                    & rows["purpose_code"].notna())
    rows["span"] = "other"
    rows.loc[rows["year"].between(*HELD_OUT), "span"] = "held_out"
    rows.loc[rows["year"].between(*LATER), "span"] = "development"
    return rows


def point_table(rows: pd.DataFrame) -> pd.DataFrame:
    kept = rows[rows["kept"]]
    held, dev = kept[kept["span"] == "held_out"], kept[kept["span"] == "development"]
    first = rows.groupby("point")[["label", "easting", "northing", "region", "area", "status"]].first()
    t = first.assign(rows_all=rows.groupby("point").size(), kept_held_out=held.groupby("point").size(),
                     seasons_held_out=held.groupby("point")["year"].nunique(),
                     kept_development=dev.groupby("point").size())
    t[["kept_held_out", "seasons_held_out", "kept_development"]] = (
        t[["kept_held_out", "seasons_held_out", "kept_development"]].fillna(0).astype(int))
    t["rule1_count"] = (t["kept_held_out"] >= MIN_ROWS) & (t["seasons_held_out"] >= MIN_SEASONS)
    return t.reset_index()


def name_core(watercourse: str | None) -> str | None:
    """A watercourse name without "River", "Afon" or "The", lower case; None for an unnamed link."""
    if not isinstance(watercourse, str) or not watercourse.strip():
        return None
    core = re.sub(r"\b(river|afon|the)\b", " ", watercourse.lower())
    return re.sub(r"\s+", " ", core).strip() or None


def right_river(watercourse: str | None, label: str) -> bool:
    core = name_core(watercourse)
    return core is None or core in re.sub(r"\s+", " ", str(label).lower())


def place(points: pd.DataFrame) -> pd.DataFrame:
    """Rules 2 to 5 for the points that pass rule 1, with the site's own trace (scripts/site_profile.py)."""
    assert "DIPCAST_ROOT" in os.environ and "DIPCAST_STATE" in os.environ, "set a scratch DIPCAST_ROOT and DIPCAST_STATE"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pyproj import Transformer

    import site_profile
    from dipcast import config
    from dipcast.model.transport import lonlat_to_bng

    to_lonlat = Transformer.from_crs(27700, 4326, always_xy=True)
    bench = [lonlat_to_bng(b["lon"], b["lat"]) for b in
             json.loads((config.RAW / "bathing_waters_inland.json").read_text())]
    out = []
    for p in points.itertuples():
        x, y = float(p.easting), float(p.northing)
        lon, lat = to_lonlat.transform(x, y)
        up, where = site_profile.trace(lat, lon, "river", None)
        snap = where.get("snap_m")
        nearest = min(((x - bx) ** 2 + (y - by) ** 2) ** 0.5 for bx, by in bench)
        out.append({"point": p.point, "lat": round(lat, 5), "lon": round(lon, 5), "mode": where["mode"],
                    "watercourse": where.get("watercourse"), "snap_m": snap,
                    "overflows_upstream": int(len(up)), "bench_site_m": round(nearest),
                    "rule2_on_river": bool(where["mode"] == "river" and snap is not None and snap <= SNAP_M),
                    "rule3_right_river": right_river(where.get("watercourse"), p.label),
                    "rule4_overflow_upstream": bool(len(up) >= 1), "rule5_not_bench": bool(nearest > BENCH_M)})
    return pd.DataFrame(out)


def kill_rule(t: pd.DataFrame) -> dict:
    """The two figures of the kill rule, from the placed table (rule columns False where not placed)."""
    base = t[t["rule1_count"] & t["rule2_on_river"] & t["rule3_right_river"] & t["rule5_not_bench"]]
    passing = base[base["rule4_overflow_upstream"]]
    rows_base, rows_none = int(base["kept_held_out"].sum()), int(base.loc[~base["rule4_overflow_upstream"],
                                                                         "kept_held_out"].sum())
    share = rows_none / rows_base if rows_base else None
    return {"points_passing_all_five": int(len(passing)), "held_out_rows_at_them": int(passing["kept_held_out"].sum()),
            "development_rows_at_them": int(passing["kept_development"].sum()),
            "points_passing_1_2_3_5": int(len(base)), "held_out_rows_at_those": rows_base,
            "of_which_no_overflow_upstream": rows_none, "share_no_overflow_upstream": share,
            "killed": bool(len(passing) < MIN_POINTS or (share is not None and share > 0.5))}


def main(fetched: Path, out: Path) -> None:
    rows, checks = load_pages(fetched / "raw")
    rows = mark(rows)
    sealed = fetched / "samples.parquet"
    rows.to_parquet(sealed, index=False)
    t = point_table(rows)
    placed = place(t[t["rule1_count"]])
    t = t.merge(placed, on="point", how="left")
    for c in ("rule2_on_river", "rule3_right_river", "rule4_overflow_upstream", "rule5_not_bench"):
        t[c] = t[c].fillna(False).astype(bool)
    t["kept_point"] = t[["rule1_count", "rule2_on_river", "rule3_right_river", "rule4_overflow_upstream",
                         "rule5_not_bench"]].all(axis=1)
    out.mkdir(parents=True, exist_ok=True)
    t.sort_values(["kept_point", "kept_held_out"], ascending=False).to_csv(out / "points.csv", index=False)
    kept = rows[rows["kept"]]
    cand = t[t["rule1_count"]]
    manifest = {
        "protocol": "docs/RIVER-UNSEEN-PROTOCOL-2026-11.md", "checks": checks,
        "rows_by_year": {str(int(k)): int(v) for k, v in rows.groupby("year").size().items()},
        "rows_by_material": {k: int(v) for k, v in rows["material"].map(squash).value_counts().items()},
        "rows_by_purpose": {k: int(v) for k, v in rows["purpose"].map(squash).value_counts().items()},
        "rows_may_to_september": int(rows["month"].between(5, 9).sum()),
        "kept_rows": {"held_out": int((kept["span"] == "held_out").sum()),
                      "development": int((kept["span"] == "development").sum())},
        "kept_held_out_by_year": {str(int(k)): int(v) for k, v in
                                  kept[kept["span"] == "held_out"].groupby("year").size().items()},
        "points": {"all": int(len(t)), "rule1_count": int(len(cand)),
                   "then_rule2_on_river": int(cand["rule2_on_river"].sum()),
                   "then_rule3_right_river": int((cand["rule2_on_river"] & cand["rule3_right_river"]).sum()),
                   "then_rule5_not_bench": int((cand["rule2_on_river"] & cand["rule3_right_river"]
                                                & cand["rule5_not_bench"]).sum()),
                   "then_rule4_overflow_upstream": int(t["kept_point"].sum())},
        "kill_rule": kill_rule(t),
        "kept_points_by_region": {k: int(v) for k, v in t[t["kept_point"]]["region"].value_counts().items()},
        "sealed_samples": {"file": "swimsignal-private/river-unseen/samples.parquet", "rows": int(len(rows)),
                           "sha256": hashlib.sha256(sealed.read_bytes()).hexdigest()},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps({k: manifest[k] for k in ("checks", "kept_rows", "points", "kill_rule")}, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
