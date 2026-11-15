"""Build the coastal sample table, its joins and the explorer tables (docs/COASTAL-BASELINES-2026-11.md,
sections 2 to 4). Scores nothing: scripts/coastal_baselines/score.py does that, from the table written here.

    DIPCAST_ROOT=<scratch root> DIPCAST_STATE=<scratch> uv run python scripts/coastal_baselines/build.py \
        <fetch dir> <main data dir> <per-overflow radar dir> <out dir>

<fetch dir> is fetch.py's output. <main data dir> is a checkout's data/ folder, read only: processed/overflows.parquet,
processed/ea_events_*.parquet, processed/dcww_ea_events.parquet. The river network is loaded from
$DIPCAST_ROOT/data/processed/river_network.pkl (a copy or a link; run.sh puts it there). <per-overflow radar dir>
holds radar_overflows_<day>.parquet (scripts/fetch_met_office_radar.py --overflows), read only.

Writes to <out dir>: sites.csv, site_year.csv, year_summary.csv, samples.parquet (the samples with the open-licence
joins), features.parquet (the same rows with radar rain as well; not for publishing without the Met Office credit)
and build_summary.json. Sample data: Environment Agency, Open Government Licence v3.0. Rain: contains Met Office
data, British Crown copyright, CC BY-SA 4.0.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pyproj import Transformer
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
TZ = "Europe/London"
ID = re.compile(r"uk[a-z0-9]+-\d{5}\Z")
KINDS = {"CoastalBathingWater": "coast", "TransitionalBathingWater": "estuary"}
YEARS = (2022, 2023, 2024, 2025, 2026)
SEASON = ((5, 15), (9, 30))
NEAR_KM, RING_KM, RAIN_KM = 2.0, 5.0, 5.0
RIVER_NODE_KM, RIVER_MAX_KM = 2.0, 30.0
WINDOW_H = 72
MIN_COVERAGE = 0.9
SPILL_YEARS = (2024, 2025)
RAIN_YEARS = (2025, 2026)
ECOLI_LINES = (250, 500)
IE_LINES = (100, 185, 200)
TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)


def val(x):
    return x.get("_value") if isinstance(x, dict) else x


def count(text: str | None) -> tuple[float | None, str]:
    """'620' -> (620.0, '='); '<10' -> (10.0, '<'): the archive's result text."""
    s = (text or "").strip()
    q = s[0] if s[:1] in ("<", ">") else "="
    try:
        return float(s.lstrip("<>= ")), q
    except ValueError:
        return None, q


def local(series: pd.Series) -> pd.Series:
    """Times published with no offset are UK local time."""
    return pd.to_datetime(series).dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward")


# ------------------------------------------------------------------ sites
def sites(fetch: Path) -> pd.DataFrame:
    items = []
    for f in sorted((fetch / "raw").glob("catalogue_p*.json")):
        items += json.loads(f.read_bytes())["result"]["items"]
    mapping = json.loads((REPO / "data" / "raw" / "coastal_wqa_points.json").read_text())["points"]
    rows = []
    for it in items:
        kinds = [KINDS[t.rsplit("/", 1)[-1]] for t in it.get("type", []) if t.rsplit("/", 1)[-1] in KINDS]
        key, sp = it.get("eubwidNotation", ""), it.get("samplingPoint") or {}
        if not kinds or not ID.fullmatch(key):
            continue
        district = next((val(d.get("name")) for d in it.get("district") or [] if isinstance(d, dict)), None)
        m = mapping.get(key) or {}
        rows.append({"site_id": key, "name": str(val(it.get("name")) or "").strip(), "kind": kinds[0],
                     "region": val((it.get("regionalOrganization") or {}).get("name")),
                     "company": val((it.get("appointedSewerageUndertaker") or {}).get("name")),
                     "district": district, "lat": sp.get("lat"), "lon": sp.get("long"),
                     "wqa_point": m.get("point"), "wqa_evidence": m.get("evidence")})
    df = pd.DataFrame(rows).sort_values("site_id").reset_index(drop=True)
    x, y = TO_BNG.transform(df["lon"].to_numpy(float), df["lat"].to_numpy(float))
    return df.assign(x=x, y=y)


# ------------------------------------------------------------------ samples
def observations(fetch: Path, name: str) -> tuple[pd.DataFrame, dict]:
    """Every fetched result of one determinand, with a check that each request group's pages add up to the
    archive's own total."""
    groups: dict[str, list[Path]] = {}
    for f in sorted((fetch / "raw").glob(f"{name}_*.json")):
        groups.setdefault(f.name.rsplit("_s", 1)[0], []).append(f)
    rows, short = [], []
    for g, files in groups.items():
        got, total = 0, None
        for f in files:
            d = json.loads(f.read_bytes())
            total = d.get("totalItems") if total is None else total
            for o in d.get("member") or []:
                got += 1
                v, q = count(o.get("hasSimpleResult"))
                sampling = ((o.get("hasSample") or {}).get("isResultOf") or {})
                rows.append({"wqa_point": (o.get("hasSamplingPoint") or {}).get("notation"),
                             "sample_id": str(o.get("id", "")).split("/sample/")[-1].split("/")[0],
                             "time": o.get("phenomenonTime"), "value": v, "qual": q, "unit": o.get("hasUnit"),
                             "purpose": (sampling.get("samplingPurpose") or {}).get("notation"),
                             "material": ((o.get("hasSample") or {}).get("sampleMaterialType") or {}).get("notation")})
        if total is not None and got != total:
            short.append({"group": g, "got": got, "total": total})
    df = pd.DataFrame(rows)
    info = {"request_groups": len(groups), "results": len(df), "groups_short_of_total": short}
    if df.empty:
        return df, info
    info.update(purposes=dict(Counter(df["purpose"])), units=dict(Counter(df["unit"])),
                materials=dict(Counter(df["material"])), no_number=int(df["value"].isna().sum()))
    df = df[df["value"].notna() & (df["purpose"] == "MS")].copy()
    df["time"] = local(df["time"])
    info["no_time"] = int(df["time"].isna().sum())
    return df[df["time"].notna()], info


def one_per_minute(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Section 2's rule for two results at one site and minute: equal, keep one; different, keep the higher."""
    key = ["site_id", "time"]
    dup = df[df.duplicated(key, keep=False)]
    differ = int((dup.groupby(key)["value"].nunique() > 1).sum()) if len(dup) else 0
    same = int(dup.groupby(key).ngroups - differ) if len(dup) else 0
    out = df.sort_values([*key, "value"]).drop_duplicates(key, keep="last")
    return out, {"minutes_with_equal_results": same, "minutes_with_different_results": differ}


def samples(fetch: Path, st: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    site_of = st.dropna(subset=["wqa_point"]).set_index("wqa_point")["site_id"]
    info = {}
    ec, info["ecoli"] = observations(fetch, "ecoli")
    ec["site_id"] = ec["wqa_point"].map(site_of)
    info["ecoli"]["rows_at_unmapped_points"] = int(ec["site_id"].isna().sum())
    ec, d = one_per_minute(ec.dropna(subset=["site_id"]))
    info["ecoli"].update(d)
    out = ec.rename(columns={"value": "ecoli", "qual": "ecoli_qual"})[["site_id", "wqa_point", "sample_id", "time",
                                                                      "ecoli", "ecoli_qual"]]
    ie, info["enterococci"] = observations(fetch, "enterococci")
    if len(ie):
        ie["site_id"] = ie["wqa_point"].map(site_of)
        ie, d = one_per_minute(ie.dropna(subset=["site_id"]))
        info["enterococci"].update(d)
        out = out.merge(ie.rename(columns={"value": "ie", "qual": "ie_qual"})[["site_id", "time", "ie", "ie_qual"]],
                        on=["site_id", "time"], how="left")
        info["enterococci"]["rows_with_no_ecoli_row"] = int(len(ie) - out["ie"].notna().sum())
    else:
        out["ie"], out["ie_qual"] = np.nan, None
    out = out.sort_values(["site_id", "time"]).reset_index(drop=True)
    out["year"], out["month"] = out["time"].dt.year, out["time"].dt.month
    out["date"] = out["time"].dt.date
    return out[out["year"].isin(YEARS)].reset_index(drop=True), info


def over(value: pd.Series, qual: pd.Series, line: float) -> pd.Series:
    """Section 4's rule: a '<' result is never over a line; a '>' result is over it when its value reaches it."""
    return ((qual == "=") & (value > line)) | ((qual == ">") & (value >= line))


# ------------------------------------------------------------------ overflows near each site
def river_links(net, st: pd.DataFrame) -> dict[str, dict[str, float]]:
    """For each site, the river links from which the network runs downstream, within RIVER_MAX_KM, to a network node
    within RIVER_NODE_KM of the sampling point: link -> metres along the network (RiverNetwork.upstream_edges, from
    several nodes at once)."""
    pts = net.node_points()
    nodes = np.array(pts.index)
    tree = cKDTree(np.c_[pts.x.to_numpy(), pts.y.to_numpy()])
    g, cap, out = net.graph, RIVER_MAX_KM * 1000, {}
    for s in st.itertuples():
        start = nodes[tree.query_ball_point([s.x, s.y], RIVER_NODE_KM * 1000)]
        dist = {n: 0.0 for n in start}
        links: dict[str, float] = {}
        stack = list(start)
        while stack:
            n = stack.pop()
            dn = dist[n]
            for pred in g.predecessors(n):
                ed = g.edges[pred, n]
                lid, d_pred = ed["link"], dn + ed["length"]
                if lid not in links or dn < links[lid]:
                    links[lid] = dn
                if d_pred <= cap and d_pred < dist.get(pred, np.inf):
                    dist[pred] = d_pred
                    stack.append(pred)
        out[s.site_id] = links
    return out


def overflow_groups(st: pd.DataFrame, main: Path) -> tuple[dict, pd.DataFrame, dict]:
    """Each site's overflows in section 4's three groups, and the 5 km set the rain is averaged over."""
    ov = pd.read_parquet(main / "processed" / "overflows.parquet",
                         columns=["site_id", "company", "lat", "lon", "link_id", "snap_confidence"])
    ox, oy = TO_BNG.transform(ov["lon"].to_numpy(float), ov["lat"].to_numpy(float))
    ok = np.isfinite(ox) & np.isfinite(oy)
    ov, ox, oy = ov[ok].reset_index(drop=True), ox[ok], oy[ok]
    from dipcast.network.rivers import RiverNetwork
    net = RiverNetwork.load()
    rl = river_links(net, st)
    on_link = ov[~ov["snap_confidence"].isin(["marine", "ground"]) & ov["link_id"].notna()]
    by_link = on_link.groupby("link_id").indices
    ids = ov["site_id"].to_numpy()
    groups, rows = {}, []
    for s in st.itertuples():
        d = np.hypot(ox - s.x, oy - s.y) / 1000
        near = np.flatnonzero(d <= NEAR_KM)
        ring = np.flatnonzero((d > NEAR_KM) & (d <= RING_KM))
        river = sorted({on_link.index[i] for lid in rl[s.site_id] if lid in by_link for i in by_link[lid]
                        if d[on_link.index[i]] > RING_KM})
        groups[s.site_id] = {"near": ids[near].tolist(), "ring": ids[ring].tolist(), "river": ids[river].tolist()}
        rows.append({"site_id": s.site_id, "nearest_overflow_km": round(float(d.min()), 3),
                     "overflows_2km": len(near), "overflows_5km": len(near) + len(ring), "river_overflows": len(river),
                     "river_links": len(rl[s.site_id])})
    info = {"overflows": len(ov), "network_key": net.topology_key()}
    return groups, pd.DataFrame(rows), info


# ------------------------------------------------------------------ rain
def season_hours(year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{year}-04-27", f"{year}-10-01 23:00", freq="h", tz="UTC")


def site_rain(groups: dict, radar: Path) -> tuple[dict[int, pd.DataFrame], dict[int, pd.DataFrame], dict]:
    """Hourly rain and radar coverage per site and RAIN_YEARS year: the mean over the site's overflows within
    RAIN_KM. An hour with no radar file keeps rain NaN and coverage 0."""
    near5 = {s: g["near"] + g["ring"] for s, g in groups.items() if g["near"] or g["ring"]}
    wanted = sorted({o for v in near5.values() for o in v})
    rain, cov, missing_days = {}, {}, []
    for year in RAIN_YEARS:
        hours = season_hours(year)
        parts = []
        for day in pd.date_range(hours[0].date(), hours[-1].date(), freq="D"):
            f = radar / f"radar_overflows_{day.date().isoformat()}.parquet"
            if not f.exists():
                missing_days.append(day.date().isoformat())
                continue
            parts.append(pq.read_table(f, columns=["site_id", "time", "radar_mm", "coverage"],
                                       filters=[("site_id", "in", wanted)]).to_pandas())
        d = pd.concat(parts, ignore_index=True)
        mm = d.pivot_table(index="time", columns="site_id", values="radar_mm", aggfunc="mean").reindex(hours)
        cv = d.pivot_table(index="time", columns="site_id", values="coverage", aggfunc="mean").reindex(hours).fillna(0.0)
        rain[year] = pd.DataFrame({s: mm[[o for o in v if o in mm.columns]].mean(axis=1) for s, v in near5.items()})
        cov[year] = pd.DataFrame({s: cv[[o for o in v if o in cv.columns]].mean(axis=1) for s, v in near5.items()})
    return rain, cov, {"overflows_read": len(wanted), "sites_with_rain": len(near5), "days_with_no_radar_file": missing_days}


def rolling(df: pd.DataFrame, hours: int, how: str) -> pd.DataFrame:
    """Per column, the sum (or mean) of the `hours` values ending at each hour label. An hour with no radar value adds
    nothing to a sum; whether a window is usable is decided by its mean coverage (MIN_COVERAGE), where such an hour
    counts as its own coverage. The first `hours` - 1 labels of the series have no full window and stay NaN."""
    r = df.rolling(hours, min_periods=1)
    out = r.sum() if how == "sum" else r.mean()
    out.iloc[:hours - 1] = np.nan
    return out


def rain_at(sm: pd.DataFrame, rain: dict, cov: dict) -> pd.DataFrame:
    """r24, r72 and the 72-hour mean coverage for each sample: hours labelled at or before the sample time."""
    out = pd.DataFrame(index=sm.index, columns=["r24", "r72", "rain_cov"], dtype=float)
    for year in RAIN_YEARS:
        r24, r72 = rolling(rain[year], 24, "sum"), rolling(rain[year], 72, "sum")
        c72 = rolling(cov[year], 72, "mean")
        rows = sm[(sm["year"] == year) & sm["site_id"].isin(rain[year].columns)]
        hour = rows["time"].dt.tz_convert("UTC").dt.floor("h")
        pos = r24.index.get_indexer(hour)
        for i, p, s in zip(rows.index, pos, rows["site_id"]):
            if p >= 0:
                out.loc[i] = [r24[s].iat[p], r72[s].iat[p], c72[s].iat[p]]
    return out


# ------------------------------------------------------------------ spills
def spill_hours(sm: pd.DataFrame, groups: dict, main: Path) -> tuple[pd.DataFrame, dict]:
    """Recorded spill hours in the WINDOW_H hours before each SPILL_YEARS sample, per overflow group."""
    files = sorted((main / "processed").glob("ea_events_*.parquet")) + [main / "processed" / "dcww_ea_events.parquet"]
    wanted = {o for g in groups.values() for v in g.values() for o in v}
    ev = pd.concat([pd.read_parquet(f, columns=["site_id", "event_start", "event_end"]) for f in files], ignore_index=True)
    ev = ev[ev["site_id"].isin(wanted) & ev["event_end"].notna() & ev["event_start"].notna()]
    ev = ev[(ev["event_start"] >= "2023-12-25") & (ev["event_start"] < "2026-01-01")]
    start = ev["event_start"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[s]").astype("int64")
    end = ev["event_end"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[s]").astype("int64")
    order = np.argsort(ev["site_id"].to_numpy(), kind="stable")
    sid, start, end = ev["site_id"].to_numpy()[order], start[order], end[order]
    uniq, idx, n = np.unique(sid, return_index=True, return_counts=True)
    first, last = dict(zip(uniq, idx)), dict(zip(uniq, idx + n))
    out = pd.DataFrame(np.nan, index=sm.index, columns=["near_h", "ring_h", "river_h"])
    rows = sm[sm["year"].isin(SPILL_YEARS)]
    t = rows["time"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[s]").astype("int64")
    for (i, s), ts in zip(rows["site_id"].items(), t):
        for name in ("near", "ring", "river"):
            total = 0.0
            for o in groups[s][name]:
                if o in first:
                    a, b = start[first[o]:last[o]], end[first[o]:last[o]]
                    total += np.clip(np.minimum(b, ts) - np.maximum(a, ts - WINDOW_H * 3600), 0, None).sum()
            out.at[i, f"{name}_h"] = total / 3600
    return out, {"event_files": [f.name for f in files], "events_read": int(len(ev)),
                 "overflows_with_events": int(len(first)), "overflows_in_groups": len(wanted)}


# ------------------------------------------------------------------ the EA's risk predictions
def level(x) -> str | None:
    """'normal' or 'increased', from the risk level's URI (a string in the daily list, an object elsewhere)."""
    return str((x.get("_about") if isinstance(x, dict) else x) or "").rsplit("/", 1)[-1] or None


def predictions(fetch: Path) -> pd.DataFrame:
    rows = []
    for f in sorted((fetch / "raw").glob("prf_*.json")):
        for x in json.loads(f.read_bytes())["result"].get("items", []):
            bw = str(x.get("stp_bathingWater") or "").rsplit("/", 1)[-1]
            if bw:
                rows.append({"site_id": bw, "predicted_on": val(x.get("predictedOn")),
                             "published_at": val(x.get("publishedAt")), "expires_at": val(x.get("expiresAt")),
                             "origin": x.get("prfOriginType"), "level": level(x.get("riskLevel"))})
    df = pd.DataFrame(rows, columns=["site_id", "predicted_on", "published_at", "expires_at", "origin", "level"])
    if len(df):
        df = df.drop_duplicates()
        for c in ("published_at", "expires_at"):
            df[c] = local(df[c])
        df["year"] = pd.to_datetime(df["predicted_on"]).dt.year
    return df


def prediction_at(sm: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    """The prediction in force at each sample: the latest published at or before the sample time and not expired
    (scripts/compare_prf.py, ea_at_samples)."""
    out = pd.DataFrame({"prf_level": pd.Series(None, index=sm.index, dtype=object),
                        "prf_published_at": pd.Series(pd.NaT, index=sm.index, dtype=sm["time"].dtype)})
    if pred.empty:
        return out
    by_site = {k: g.sort_values("published_at") for k, g in pred.dropna(subset=["published_at", "expires_at"]).groupby("site_id")}
    for i, s, t in zip(sm.index, sm["site_id"], sm["time"]):
        g = by_site.get(s)
        if g is None:
            continue
        live = g[(g["published_at"] <= t) & (g["expires_at"] > t)]
        if len(live):
            out.at[i, "prf_level"] = live["level"].iat[-1]
            out.at[i, "prf_published_at"] = live["published_at"].iat[-1]
    return out


# ------------------------------------------------------------------ explorer tables
def gaps(dates: list[date], year: int) -> tuple[int, int]:
    """The longest run of days with no sample in the season, ends included, and the calendar weeks with none."""
    a, b = date(year, *SEASON[0]), date(year, *SEASON[1])
    inside = sorted({d for d in dates if a <= d <= b})
    edges = [a - timedelta(days=1), *inside, b + timedelta(days=1)]
    longest = max((y - x).days - 1 for x, y in zip(edges, edges[1:]))
    weeks = {(a + timedelta(days=i)).isocalendar()[:2] for i in range((b - a).days + 1)}
    return longest, len(weeks - {d.isocalendar()[:2] for d in inside})


def share(k, n):
    return round(float(k) / float(n), 4) if n else None


def site_year_table(sm: pd.DataFrame, st: pd.DataFrame, rain: dict, pred: pd.DataFrame) -> pd.DataFrame:
    noon = {}
    for year in RAIN_YEARS:   # every season day at 12:00 UTC: how wet the season was, to set beside the sampling days
        r24, r72 = rolling(rain[year], 24, "sum"), rolling(rain[year], 72, "sum")
        days = pd.date_range(f"{year}-{SEASON[0][0]:02d}-{SEASON[0][1]:02d} 12:00",
                             f"{year}-{SEASON[1][0]:02d}-{SEASON[1][1]:02d} 12:00", freq="D", tz="UTC")
        noon[year] = (r24.reindex(days), r72.reindex(days))
    prf_seasons = set()
    any_pred = set()
    if len(pred):
        any_pred = set(map(tuple, pred[["site_id", "year"]].drop_duplicates().to_numpy()))
        prf_seasons = set(map(tuple, pred.loc[pred["origin"] == "PRF_PROVIDED", ["site_id", "year"]].drop_duplicates().to_numpy()))
        origin_years = set(pred.loc[pred["origin"].notna(), "year"])
    rows = []
    for (s, year), g in sm.groupby(["site_id", "year"]):
        longest, weeks = gaps(list(g["date"]), year)
        n, ie = len(g), g[g["ie"].notna()]
        r = {"site_id": s, "year": year, "samples": n, "first": g["date"].min().isoformat(),
             "last": g["date"].max().isoformat(), "share_below_detection": share((g["ecoli_qual"] == "<").sum(), n)}
        for line in ECOLI_LINES:
            k = int(over(g["ecoli"], g["ecoli_qual"], line).sum())
            r[f"ecoli_over_{line}"], r[f"share_ecoli_over_{line}"] = k, share(k, n)
        r["enterococci_samples"] = len(ie)
        for line in IE_LINES:
            k = int(over(ie["ie"], ie["ie_qual"], line).sum())
            r[f"enterococci_over_{line}"], r[f"share_enterococci_over_{line}"] = k, share(k, len(ie))
        r["longest_gap_days"], r["season_weeks_without_sample"] = longest, weeks
        wet = g[g["rain_ok"]]
        r["samples_with_rain"] = len(wet)
        r["share_samples_1mm_24h"] = share((wet["r24"] >= 1).sum(), len(wet))
        r["share_samples_10mm_72h"] = share((wet["r72"] >= 10).sum(), len(wet))
        r["share_season_days_1mm_24h"] = r["share_season_days_10mm_72h"] = None
        if year in noon and s in noon[year][0].columns:
            a, b = noon[year][0][s].dropna(), noon[year][1][s].dropna()
            r["share_season_days_1mm_24h"] = share((a >= 1).sum(), len(a))
            r["share_season_days_10mm_72h"] = share((b >= 10).sum(), len(b))
        r["spill_files_cover_year"] = year in SPILL_YEARS
        r["samples_with_prediction_in_force"] = int(g["prf_level"].notna().sum())
        r["samples_under_increased_prediction"] = int((g["prf_level"] == "increased").sum())
        r["ea_predictions_that_season"] = (s, year) in any_pred
        r["ea_own_forecast_that_season"] = ((s, year) in prf_seasons) if len(pred) and year in origin_years else None
        rows.append(r)
    out = pd.DataFrame(rows)
    return st[["site_id", "name", "kind", "region", "company"]].merge(out, on="site_id", how="right")


def site_table(sm: pd.DataFrame, st: pd.DataFrame, near: pd.DataFrame, rain_sites: set) -> pd.DataFrame:
    g = sm.groupby("site_id")
    agg = pd.DataFrame({"samples": g.size(), "years_with_samples": g["year"].nunique(),
                        "first": g["date"].min().astype(str), "last": g["date"].max().astype(str),
                        "ecoli_over_500": g.apply(lambda d: int(over(d["ecoli"], d["ecoli_qual"], 500).sum()), include_groups=False),
                        "share_below_detection": g.apply(lambda d: share((d["ecoli_qual"] == "<").sum(), len(d)), include_groups=False)})
    agg["share_ecoli_over_500"] = (agg["ecoli_over_500"] / agg["samples"]).round(4)
    out = st.drop(columns=["x", "y"]).merge(agg.reset_index(), on="site_id", how="left").merge(near, on="site_id", how="left")
    out["samples"] = out["samples"].fillna(0).astype(int)
    out["radar_rain"] = out["site_id"].isin(rain_sites)
    out["why_no_samples"] = np.where(out["samples"] > 0, "",
                                     np.where(out["wqa_point"].isna(), "no archive point mapped",
                                              "mapped point has no statutory E. coli result in 2022-26"))
    out["lat"], out["lon"] = out["lat"].round(5), out["lon"].round(5)
    return out


def year_table(sm: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, g in sm.groupby("year"):
        ie = g[g["ie"].notna()]
        rows.append({"year": year, "samples": len(g), "sites": g["site_id"].nunique(), "first": g["date"].min().isoformat(),
                     "last": g["date"].max().isoformat(), "outside_may_september": int((~g["month"].between(5, 9)).sum()),
                     "share_below_detection": share((g["ecoli_qual"] == "<").sum(), len(g)),
                     **{f"ecoli_over_{line}": int(over(g["ecoli"], g["ecoli_qual"], line).sum()) for line in ECOLI_LINES},
                     "enterococci_samples": len(ie),
                     **{f"enterococci_over_{line}": int(over(ie["ie"], ie["ie_qual"], line).sum()) for line in IE_LINES},
                     "samples_with_rain": int(g["rain_ok"].sum()), "samples_with_spill_hours": int(g["near_h"].notna().sum()),
                     "samples_with_prediction_in_force": int(g["prf_level"].notna().sum())})
    return pd.DataFrame(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(fetch: Path, main_data: Path, radar: Path, out: Path) -> None:
    sys.path.insert(0, str(REPO / "src"))
    out.mkdir(parents=True, exist_ok=True)
    st = sites(fetch)
    sm, info = samples(fetch, st)
    print(f"{len(st)} sites, {len(sm)} samples at {sm['site_id'].nunique()} sites", flush=True)
    groups, near, ov_info = overflow_groups(st, main_data)
    print("overflow groups done", flush=True)
    rain, cov, rain_info = site_rain(groups, radar)
    sm = sm.join(rain_at(sm, rain, cov))
    sm["rain_ok"] = sm["r24"].notna() & sm["r72"].notna() & (sm["rain_cov"] >= MIN_COVERAGE)
    print("rain done", flush=True)
    sp, spill_info = spill_hours(sm, groups, main_data)
    sm = sm.join(sp)
    print("spills done", flush=True)
    pred = predictions(fetch)
    sm = sm.join(prediction_at(sm, pred))
    own = set(map(tuple, pred.loc[pred["origin"] == "PRF_PROVIDED", ["site_id", "year"]].drop_duplicates().to_numpy())) if len(pred) else set()
    sm["ea_own_forecast"] = [(s, y) in own for s, y in zip(sm["site_id"], sm["year"])]
    prev = sm.groupby(["site_id", "year"])["ecoli"].shift(1)
    sm["prev_ecoli"] = prev
    sm["exceeds_500"] = over(sm["ecoli"], sm["ecoli_qual"], 500)
    sm["exceeds_250"] = over(sm["ecoli"], sm["ecoli_qual"], 250)
    sm["site_group"] = [int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) % 5 for s in sm["site_id"]]

    sy = site_year_table(sm, st, rain, pred)
    sites_out = site_table(sm, st, near, set(rain[RAIN_YEARS[0]].columns))
    yr = year_table(sm)
    sy.to_csv(out / "site_year.csv", index=False)
    sites_out.to_csv(out / "sites.csv", index=False)
    yr.to_csv(out / "year_summary.csv", index=False)
    keep = ["site_id", "wqa_point", "sample_id", "time", "year", "month", "ecoli", "ecoli_qual", "ie", "ie_qual",
            "exceeds_500", "exceeds_250", "prev_ecoli", "near_h", "ring_h", "river_h", "prf_level", "prf_published_at",
            "ea_own_forecast", "site_group"]
    sm[keep].to_parquet(out / "samples.parquet", index=False)
    sm[[*keep, "r24", "r72", "rain_cov", "rain_ok"]].to_parquet(out / "features.parquet", index=False)
    summary = {"sites": len(st), "sites_by_kind": dict(Counter(st["kind"])),
               "sites_with_archive_point": int(st["wqa_point"].notna().sum()),
               "sites_with_samples": int(sm["site_id"].nunique()), "samples": len(sm), "observations": info,
               "overflows": ov_info, "rain": rain_info, "spills": spill_info,
               "predictions": {"rows": len(pred), "days": int(pred["predicted_on"].nunique()) if len(pred) else 0,
                               "by_year": {int(k): int(v) for k, v in pred.groupby("year").size().items()} if len(pred) else {},
                               "origin_by_year": {int(y): dict(Counter(g["origin"].fillna("absent")))
                                                  for y, g in pred.groupby("year")} if len(pred) else {},
                               "levels": dict(Counter(pred["level"].fillna("none"))) if len(pred) else {}},
               "rule": {"near_km": NEAR_KM, "ring_km": RING_KM, "rain_km": RAIN_KM, "river_node_km": RIVER_NODE_KM,
                        "river_max_km": RIVER_MAX_KM, "window_h": WINDOW_H, "min_coverage": MIN_COVERAGE},
               "outputs": {f.name: {"bytes": f.stat().st_size, "sha256": sha256(f),
                                    "rows": (len(pd.read_parquet(f)) if f.suffix == ".parquet" else sum(1 for _ in open(f)) - 1)}
                           for f in sorted(out.glob("*")) if f.suffix in (".csv", ".parquet")}}
    (out / "build_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("sites", "sites_with_samples", "samples")}), flush=True)


if __name__ == "__main__":
    main(*(Path(a).resolve() for a in sys.argv[1:5]))
