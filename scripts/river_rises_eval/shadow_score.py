"""Score the frozen C3 models on the river-shadow log: docs/RIVER-RISES-C3-2026-11.md, "Shadow scoring".

    # uptime and missing hours only (allowed at any time; no score, no label is read)
    uv run python scripts/river_rises_eval/shadow_score.py uptime --records <dir> --out <dir>
    # the read, on or after READ_ON
    uv run python scripts/river_rises_eval/shadow_score.py score --records <dir> --measures river-shadow/measures.json \
        --frozen docs/RIVER-RISES-C3-2026-11-frozen.json --labels <dir of Hydrology series> --radar <saved months> --out <dir>

<records> holds the logger's hourly records (river-shadow/scripts/export.sh writes one JSON file per hour). Offline.

Every input at an issue time t comes from the records made at or before t:
- **gauges:** the latest reading each record holds for the measure. `now` is the record at t, `then` for a rise over
  k hours the record at t - k; each counts only if its reading is at most DELAY_H + STEP_MAX_H older than its record
  (the harness's own look-back window, t - 2 h to the cut). The index needs a reading at most 24 h old. The site's
  word: "high" above index 1; "rising fast" when the rise between the oldest and newest readings the records of the
  last 6 h hold is more than 0.2 of the range, over at least 1 h (the site's rule, on hourly records instead of every
  15-minute reading).
- **radar:** an hour ending at e counts at t only if e <= t - 1 h and every composite of that hour (e - 60 min to e,
  15-minute steps) was listed in a record made at or before t. The values come from the saved months; the archive
  listing at read time must give the same ETags as the records (checked by `etag_check`).
- **labels:** the spot gauge's Hydrology 15-minute series, read after the window, with #627's label rule.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from river_rises_eval import c3  # noqa: E402
from river_rises_eval import protocol as pr  # noqa: E402

WINDOW = (pd.Timestamp("2026-12-01", tz="UTC"), pd.Timestamp("2027-03-01", tz="UTC"))   # label windows inside
READ_ON = pd.Timestamp("2027-03-08", tz="UTC")
MARGIN_B, MARGIN_H = pr.MARGIN_B, pr.MARGIN_H
FRESH_MAX_H = pr.DELAY_H + pr.STEP_MAX_H         # a reading this much older than its record still counts
HOUR = pd.Timedelta(hours=1)
QUARTER = pd.Timedelta(minutes=15)


# ------------------------------------------------------------------ the records
def load_records(records: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(readings, radar keys, hours): one row per (issue, measure) reading, per (issue, composite) listed, per record."""
    rd, rk, hrs = [], [], []
    for p in sorted(records.glob("*.json")):
        r = json.loads(p.read_text())
        if not isinstance(r, dict) or r.get("schema") != "swimsignal.river-shadow.hour":
            continue   # the export's key listing and state files sit beside the records
        t = pd.Timestamp(r["issue"])
        ea, radar = r.get("ea") or {}, r.get("radar") or {}
        hrs.append({"issue": t, "ea_ok": ea.get("status") == 200 and not ea.get("error"),
                    "radar_ok": radar.get("status") == 200 and not radar.get("error"), "items": len(ea.get("items") or [])})
        for it in ea.get("items") or []:
            rd.append({"issue": t, "measure": it["measure"], "time": pd.Timestamp(it["dateTime"]), "value": it.get("value")})
        for k in radar.get("keys") or []:
            stamp = k["key"].rsplit("/", 1)[-1][:12]
            rk.append({"issue": t, "valid": pd.Timestamp(datetime.strptime(stamp, "%Y%m%d%H%M"), tz="UTC"),
                       "key": k["key"], "etag": k.get("etag")})
    rd = pd.DataFrame(rd, columns=["issue", "measure", "time", "value"])
    rd["value"] = pd.to_numeric(rd["value"], errors="coerce")
    return rd, pd.DataFrame(rk, columns=["issue", "valid", "key", "etag"]), pd.DataFrame(hrs, columns=["issue", "ea_ok", "radar_ok", "items"])


def uptime(hours: pd.DataFrame, start=WINDOW[0], end=WINDOW[1]) -> dict:
    want = pd.date_range(start, end, freq="1h", inclusive="left")
    h = hours.set_index("issue").reindex(want)
    return {"hours": int(len(want)), "records": int(h["items"].notna().sum()),
            "ea_ok": int(h["ea_ok"].fillna(False).astype(bool).sum()), "radar_ok": int(h["radar_ok"].fillna(False).astype(bool).sum()),
            "longest_gap_h": int(_longest_run(~h["ea_ok"].fillna(False).astype(bool).to_numpy()))}


def _longest_run(x: np.ndarray) -> int:
    best = run = 0
    for v in x:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


# ------------------------------------------------------------------ inputs from the records
def mid(uri: str) -> str:
    """A measure's id, the last path segment: the records keep the URI as the EA published it."""
    return str(uri).rstrip("/").rsplit("/", 1)[-1]


def as_of(rd: pd.DataFrame, measure, issues: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """For each issue time, the (reading value, reading age in hours) the record made at that issue time holds.
    `measure` is one URI or the site's ordered list of them: the first with a reading in that record is used, as the
    site picks it."""
    order = [mid(m) for m in ([measure] if isinstance(measure, str) else measure)]
    v, age = np.full(len(issues), np.nan), np.full(len(issues), np.nan)
    ids = rd["measure"].map(mid)
    for m in order:
        s = rd[ids == m].drop_duplicates("issue").set_index("issue")
        vv = s["value"].reindex(issues).to_numpy(dtype=float)
        aa = ((issues - pd.DatetimeIndex(s["time"].reindex(issues))) / HOUR).to_numpy(dtype=float)
        take = ~np.isfinite(v) & np.isfinite(vv)
        v[take], age[take] = vv[take], aa[take]
    return v, age


def gauge_inputs(rd: pd.DataFrame, measure: str, low: float, high: float, issues: pd.DatetimeIndex, rises_h, prefix: str,
                 site: bool = False) -> dict[str, np.ndarray]:
    rng = high - low
    v, age = as_of(rd, measure, issues)
    fresh = np.where(age <= FRESH_MAX_H, v, np.nan)
    out = {f"{prefix}_index": np.where(age <= pr.MAX_AGE_H, (v - low) / rng, np.nan)}
    for k in rises_h:
        vk, agek = as_of(rd, measure, issues - pd.Timedelta(hours=k))
        out[f"{prefix}_rise{k}"] = (fresh - np.where(agek <= FRESH_MAX_H, vk, np.nan)) / rng
    if site:
        out["site_rise"] = site_rise(rd, measure, issues) / rng
    return out


def site_rise(rd: pd.DataFrame, measure: str, issues: pd.DatetimeIndex) -> np.ndarray:
    """The rise over the window the site uses, from the readings the records of (t - 6 h, t] hold: newest minus oldest
    reading inside [t - 6 h, t], if they span at least RISE_MIN_SPAN_H."""
    ids = rd["measure"].map(mid)
    m = rd[ids == mid(measure if isinstance(measure, str) else measure[0])]
    out = np.full(len(issues), np.nan)
    by_issue = {t: g for t, g in m.groupby("issue")}
    for i, t in enumerate(issues):
        parts = [by_issue[s] for s in pd.date_range(t - pd.Timedelta(hours=pr.SITE_RISE_H - 1), t, freq="1h") if s in by_issue]
        if not parts:
            continue
        g = pd.concat(parts).drop_duplicates("time")
        g = g[(g["time"] >= t - pd.Timedelta(hours=pr.SITE_RISE_H)) & (g["time"] <= t) & g["value"].notna()].sort_values("time")
        if len(g) >= 2 and (g["time"].iloc[-1] - g["time"].iloc[0]) >= pd.Timedelta(hours=pr.SITE_MIN_SPAN_H):
            out[i] = round(float(g["value"].iloc[-1] - g["value"].iloc[0]), 3)
    return out


def usable_rain_hours(rk: pd.DataFrame, issues: pd.DatetimeIndex) -> dict[pd.Timestamp, set]:
    """For each issue time, the hour-ending times whose five composites (e - 60 min .. e) were all listed by then."""
    listed: set = set()
    by_issue = {t: set(g["valid"]) for t, g in rk.groupby("issue")}
    out = {}
    for t in issues.sort_values():
        listed |= by_issue.get(t, set())
        ends = {v.ceil("h") for v in listed}
        out[t] = {e for e in ends if e <= t - pd.Timedelta(hours=pr.RADAR_DELAY_H)
                  and all(e - QUARTER * k in listed for k in range(5))}
    return out


def rain_inputs(rain: pd.Series | None, usable: dict, issues: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    out = {f"rain{k}": np.full(len(issues), np.nan) for k in pr.RAIN_SUMS_H}
    if rain is None:
        return out
    s = c3.cut(rain, issues.max() + HOUR)
    for i, t in enumerate(issues):
        last = t - pd.Timedelta(hours=pr.RADAR_DELAY_H)
        for k in pr.RAIN_SUMS_H:
            hours = pd.date_range(last - pd.Timedelta(hours=k - 1), last, freq="1h")
            if all(h in usable[t] for h in hours):
                vals = s.reindex(hours)
                if vals.notna().all():
                    out[f"rain{k}"][i] = float(vals.sum())
    return out


def build_rows(rd, rk, measures: dict, frozen: dict, rains: dict, labels: dict, issues: pd.DatetimeIndex) -> pd.DataFrame:
    """One row per (spot gauge, issue time), in the harness's columns, from the records only (labels apart)."""
    usable = usable_rain_hours(rk, issues)
    meas = {(s["station"], s["role"], s["spot_gauge"]): s.get("site_order") or [s["measure"]] for s in measures["stations"]}
    out = []
    for g in frozen["gauges"]:
        ref = g["gauge"]
        mspot = meas.get((ref, "spot", ref))
        if mspot is None:
            continue
        cols = pr.fill_missing(gauge_inputs(rd, mspot, g["low"], g["high"], issues, pr.SPOT_RISES_H, "spot", site=True), "spot")
        site_index = gauge_inputs(rd, mspot, g["low"], g["high"], issues, (), "spot")["spot_index"]
        cols["spot_index"] = site_index
        site = gauge_inputs(rd, mspot, g["low"], g["high"], issues, (), "x", site=True)["site_rise"]
        for slot in ("same", "trib"):
            up = g.get(slot)
            mu = meas.get((up["ref"], slot, ref)) if up else None
            raw = (gauge_inputs(rd, mu, up["low"], up["high"], issues, pr.UP_RISES_H, slot) if mu
                   else pr.missing_inputs(len(issues), pr.UP_RISES_H, slot))
            cols.update(pr.fill_missing(raw, slot))
        cols.update(pr.fill_missing(rain_inputs(rains.get(ref), usable, issues), "rain"))
        df = pd.DataFrame(cols)
        df.insert(0, "issue", issues)
        df.insert(1, "gauge", ref)
        df.insert(2, "system", g["system"])
        df["fold"] = frozen["folds"].get(g["system"], 0)
        df["month"] = issues.month
        word = np.full(len(issues), "none", dtype=object)
        known = np.isfinite(site_index)
        word[~known] = "unknown"
        with np.errstate(invalid="ignore"):
            word[known & (site_index <= pr.HIGH_INDEX) & (site > pr.SHARE)] = "rising fast"
            word[known & (site_index > pr.HIGH_INDEX)] = "high"
        df["word"] = word
        df["in_P"] = known & (word == "none")
        lab = labels.get(ref)
        df[f"y{frozen['horizon_h']}"] = (pr.labels(pr.Readings.of(lab), issues, frozen["horizon_h"], g["high"] - g["low"])
                                         if lab is not None else np.nan)
        out.append(df)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def etag_check(rk: pd.DataFrame, archive: pd.DataFrame) -> dict:
    """The composites the records listed, against a listing of the archive made at read time (columns key, etag):
    every listed key must still be there with the same ETag, or the radar values read later are not the files that
    existed at issue time."""
    logged = rk.drop_duplicates("key")[["key", "etag"]]
    m = logged.merge(archive[["key", "etag"]], on="key", how="left", suffixes=("", "_now"))
    gone = m["etag_now"].isna()
    changed = ~gone & (m["etag"].astype(str).str.strip('"') != m["etag_now"].astype(str).str.strip('"'))
    return {"listed": int(len(m)), "gone": m.loc[gone, "key"].tolist(), "changed": m.loc[changed, "key"].tolist(),
            "ok": bool(not gone.any() and not changed.any())}


def judge(ev: dict) -> dict:
    """The stated comparisons: C3 against R1 and against R3, river-system interval, B and H, the near-miss labels."""
    out = {}
    for ref in ("R1", "R3"):
        b = ev["pairs"].get(f"C3 vs {ref}", {}).get("by_system")
        if b:
            out[f"C3 vs {ref}"] = {**b, "label": pr.nearmiss_label(b["d"], b["L"], b["U"], MARGIN_B, MARGIN_H)}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("uptime", "score"))
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--measures", type=Path)
    ap.add_argument("--frozen", type=Path)
    ap.add_argument("--labels", type=Path, help="Hydrology 15-minute series, <measure>.parquet (fetch.py's format)")
    ap.add_argument("--radar", type=Path, help="saved radar months")
    ap.add_argument("--archive-listing", type=Path, help="score: CSV (key, etag) of the bucket listed at read time")
    args = ap.parse_args(argv)
    rd, rk, hours = load_records(args.records)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.stage == "uptime":
        u = uptime(hours)
        (args.out / "shadow_uptime.json").write_text(json.dumps(u, indent=1))
        print(json.dumps(u, indent=1))
        return
    if datetime.now(UTC) < READ_ON:
        raise SystemExit(f"the shadow is read on or after {READ_ON:%d %B %Y}; before that only `uptime` runs")
    from river_rises_eval import score as sc
    if not args.archive_listing or not args.archive_listing.exists():
        raise SystemExit("the read needs --archive-listing, to check the logged radar ETags against the archive")
    tags = etag_check(rk, pd.read_csv(args.archive_listing, dtype=str))
    if not tags["ok"]:
        raise SystemExit(f"radar files changed or gone since issue time: {len(tags['changed'])} changed, {len(tags['gone'])} gone")
    frozen = json.loads(args.frozen.read_text())
    measures = json.loads(args.measures.read_text())
    issues = pd.date_range(WINDOW[0], WINDOW[1] - pd.Timedelta(hours=frozen["horizon_h"] - 1), freq="1h", inclusive="left")
    hyd = {g["gauge"]: g.get("hydrology_measure") for g in frozen["gauges"]}
    labels = {k: sc.read_series(args.labels / f"{m}.parquet") for k, m in hyd.items() if m and (args.labels / f"{m}.parquet").exists()}
    cells = {g["gauge"]: g.get("radar_cells", []) for g in frozen["gauges"]}
    rains = {k: sc.read_rain(pd.DataFrame({"cell": v}), args.radar) for k, v in cells.items() if v}
    rows = build_rows(rd, rk, measures, frozen, rains, labels, issues)
    res = c3.predict_frozen(frozen, rows)
    y = f"y{frozen['horizon_h']}"
    ev = c3.evaluate(res[res["gauge"].isin(frozen["models"]["C3"]["gauges"])], y, c3.MODELS["own"], c3.PAIRS["own"])
    out = {"made": datetime.now(UTC).isoformat(timespec="seconds"), "frozen_sha256": pr.sha256(args.frozen),
           "uptime": uptime(hours), "own": ev, "judged": judge(ev),
           "all": c3.evaluate(res, y, c3.MODELS["all"], c3.PAIRS["all"])}
    (args.out / "shadow_result.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out["judged"], indent=1, default=str))


if __name__ == "__main__":
    main()
