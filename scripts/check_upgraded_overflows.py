"""Upgraded storm overflows and the spill forecast, at the Cromwheel bathing water in Ilkley
(bw-uke4100-08901). The numbers behind docs/UPGRADED-OVERFLOWS-2026-10.md. Off CI, run by hand:

    uv run python scripts/check_upgraded_overflows.py --state DIR --ea-2026 FILE [--ea-events FILE] \
        [--rain DIR] [--rain-2026 DIR] [--last-day YYYY-MM-DD] [--forecast-rain FILE] [--out PREFIX]

A record of checks, not a test: it changes no model setting and writes nothing the build reads.

- --state: dipcast.duckdb, live_latest.parquet and live_history.parquet from the `state` release
  (`gh release download state -D DIR -p dipcast.duckdb -p live_latest.parquet -p live_history.parquet`).
  The 16 overflows upstream of Cromwheel, with the weight and travel time the live forecast gave each,
  are read from the last build in its forecast log.
- --ea-2026: "Yorkshire Water Detailed Data 2026.xlsx", from "2026 year to August Detailed EDM Start-Stop
  Data.zip" in the EA's start/stop dataset (environment.data.gov.uk/dataset/e9677ac1-fd32-4ceb-88a0-2735be5f27c7),
  through the signed-link route in scripts/import_ea_events.py. 2024 and 2025 come from --ea-events,
  data/processed/ea_events_yorkshire_water.parquet by default (not in git; scripts/import_ea_events.py).
- --rain, --rain-2026: folders of ERA5-Land archive files (archive_<cell>_<year>.parquet, as
  rainfall.fetch_archive writes them) for 2023-2025 and for 2026. The 2026 files must reach mid-October.
- --forecast-rain: an Open-Meteo forecast for the same cells (rainfall.fetch_forecast's frame), for the
  week of 21-25 October 2026. Without it the week is left out.

The hindcast runs the production spill model as the build does (features.build_site_days, the model's
predict, local-midnight days), every day at lead 0 (forecast.calibrate_at_lead), with the covariates of
the return year before (as train.py and the live build use them), and combines the 16 overflows with
transport.combine_daily. Scenarios change only lta_spills (and, in one, spill_hours) of named overflows.

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed under
the Open Government Licence v3.0. Rain: Open-Meteo (ERA5-Land, ECMWF), CC BY 4.0.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.edm_events import read_ea_events
from dipcast.ingest.rainfall import cell_key, grid_cell
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features, spill_days
from dipcast.model.forecast import calibrate_at_lead, calibrate_by_lead
from dipcast.model.spill_model import SpillModel
from dipcast.model.transport import combine_daily, risk_label

SPOT = (53.93189, -1.81618)   # Cromwheel's query point in spots.json and the forecast log
TZ = "Europe/London"
LEVELS = ["low", "moderate", "high", "very high"]

# The overflows on Yorkshire Water's Addingham and Ilkley page that are upstream of Cromwheel, matched by
# name. Low Mill Lane 179 is taken for its "Low Mill Lane CSO" (Low Mill Lane 27 has no spills on record);
# the two Addingham No 1 SPS overflows for its "Addingham SPS CSO". Both matches are inferred from names.
MIDDLETON = "YWS00176"
CSOS = {"YWS00176": "Ilkley Middleton CSO", "YWS00674": "Rivadale View CSO", "YWS00179": "Bridge Lane CSO",
        "YWS00191": "Low Mill Lane 179 CSO"}
ADDINGHAM = {"YWS00144": "Addingham No 1 SPS 3xDWF", "YWS00145": "Addingham No 1 SPS 6xDWF"}
NAMED = CSOS | ADDINGHAM

SCENARIOS = {
    "live": {},
    "middleton_10": {MIDDLETON: {"lta_spills": 10.0}},
    "middleton_10_hours": {MIDDLETON: {"lta_spills": 10.0, "spill_hours_scale": 10.0 / 36.0}},
    "middleton_1": {MIDDLETON: {"lta_spills": 1.0}},
    "csos_10": {s: {"lta_cap": 10.0} for s in CSOS},
    "csos_1": {s: {"lta_cap": 1.0} for s in CSOS},
    "csos_addingham_10": {s: {"lta_cap": 10.0} for s in NAMED},
    "csos_addingham_1": {s: {"lta_cap": 1.0} for s in NAMED},
}
LTA_GRID = [0, 1, 2, 5, 10, 15, 20, 25, 30, 36, 40, 50, 75, 100]

# The 21 Oct 2026 21:50 BST build (spots.json, commit b91fa97): Cromwheel's risk and Middleton's
# calibrated chance for 21-25 Oct, for the week's swap.
PUBLISHED_RISK = [0.272, 0.245, 0.652, 0.915, 0.779]
PUBLISHED_P_MIDDLETON = [0.039, 0.046, 0.212, 0.416, 0.153]


def upstream(state: Path) -> pd.DataFrame:
    """Cromwheel's upstream overflows at the last build in the forecast log, with each one's weight, travel
    time, latest return values and rain cell (from its live position, as the build places it)."""
    con = duckdb.connect(str(state / "dipcast.duckdb"), read_only=True)
    where = f"lat = {SPOT[0]} and lon = {SPOT[1]}"
    last = con.sql(f"select cast(max(issued_at) as varchar) from forecast_overflows where {where}").fetchone()[0]
    up = con.sql(f"""select distinct site_id, weight, travel_h from forecast_overflows
                     where {where} and cast(issued_at as varchar) = '{last}'""").df()
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    a = ar[ar["year"] == 2025].drop_duplicates("site_id", keep="last").set_index("site_id")
    live = pd.read_parquet(state / "live_latest.parquet").set_index("site_id")
    up["site_name"] = up["site_id"].map(a["site_name"])
    for c in ("lta_spills", "spills", "spill_hours"):
        up[f"{c}_2025_return"] = up["site_id"].map(a[c])
    lat = up["site_id"].map(live["lat"]).fillna(up["site_id"].map(a["lat"]))
    lon = up["site_id"].map(live["lon"]).fillna(up["site_id"].map(a["lon"]))
    up["cell_lat"], up["cell_lon"] = grid_cell(lat.to_numpy(), lon.to_numpy())
    up["named_by_yorkshire_water"] = up["site_id"].isin(NAMED)
    up["log_issued_at"] = last
    return up.sort_values(["travel_h", "site_id"]).reset_index(drop=True)


class Hindcast:
    def __init__(self, up: pd.DataFrame, rain: pd.DataFrame):
        self.up = up
        self.model = SpillModel.load()
        assert not set(up["site_id"]) & set(self.model.site_offset), "an overflow here has a site offset"
        ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet").dropna(subset=["site_id"])
        self.ar = ar.drop_duplicates(["site_id", "year"], keep="last").set_index(["site_id", "year"])
        self.daily = daily_rain_features(rain.assign(time=rain["time"].dt.tz_convert(TZ)))

    def sites(self, year: int, scenario: dict) -> pd.DataFrame:
        """The covariates the forecast for `year` reads: the return of year - 1, changed by `scenario`."""
        rows = []
        for _, u in self.up.iterrows():
            key = (u["site_id"], year - 1)
            a = self.ar.loc[key] if key in self.ar.index else None
            r = {"site_id": u["site_id"], "lat": u["cell_lat"], "lon": u["cell_lon"], "company": "Yorkshire Water"}
            for c in ("lta_spills", "spill_hours", "edm_operational_pct"):
                r[c] = np.nan if a is None else a[c]
            ch = scenario.get(u["site_id"], {})
            if "lta_spills" in ch:
                r["lta_spills"] = ch["lta_spills"]
            if "lta_cap" in ch:
                r["lta_spills"] = min(r["lta_spills"], ch["lta_cap"])
            if "spill_hours_scale" in ch:
                r["spill_hours"] *= ch["spill_hours_scale"]
            rows.append(r)
        return pd.DataFrame(rows)

    def raw(self, sites: pd.DataFrame, days: pd.DatetimeIndex, daily: pd.DataFrame | None = None) -> pd.DataFrame:
        """Uncalibrated chances, overflows x days, NaN where the day has no rain."""
        sd = build_site_days(sites, self.daily if daily is None else daily, days)
        for f in ALL_FEATURES:
            sd[f] = sd[f].astype(np.float32)
        sd["p"] = np.where(sd["rain_d"].notna(), self.model.predict(sd.fillna({f: 0.0 for f in ALL_FEATURES})), np.nan)
        return sd.pivot(index="site_id", columns="day", values="p").reindex(index=self.up["site_id"], columns=days)

    def lead0(self, year: int, scenario: dict, days: pd.DatetimeIndex) -> pd.DataFrame:
        p = self.raw(self.sites(year, scenario), days)
        return pd.DataFrame(calibrate_at_lead(p.to_numpy(float), 0), index=p.index, columns=p.columns)


def year_days(year: int, last_2026: str) -> tuple[pd.Timestamp, pd.DatetimeIndex]:
    """The first day of `year`, and its days with four days before it (the travel-time history the live
    forecast keeps for Cromwheel, transport.history_days)."""
    start = pd.Timestamp(f"{year}-01-01", tz=TZ)
    end = pd.Timestamp(f"{year}-12-31" if year < 2026 else last_2026, tz=TZ)
    return start, pd.date_range(start - pd.Timedelta(days=4), end, freq="D")


def load_rain(up: pd.DataFrame, rain_dir: Path, rain_2026: Path) -> pd.DataFrame:
    frames = []
    for cl, cn in sorted(set(zip(up["cell_lat"], up["cell_lon"], strict=True))):
        for y in (2023, 2024, 2025, 2026):
            frames.append(pd.read_parquet((rain_2026 if y == 2026 else rain_dir) / f"archive_{cell_key(cl, cn)}_{y}.parquet"))
    return pd.concat(frames, ignore_index=True)


def local_days(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True).dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--ea-2026", type=Path, required=True)
    p.add_argument("--ea-events", type=Path, default=config.PROCESSED / "ea_events_yorkshire_water.parquet",
                   help="Yorkshire Water's 2024 and 2025 EA events (scripts/import_ea_events.py)")
    p.add_argument("--rain", type=Path, default=config.CACHE / "rain")
    p.add_argument("--rain-2026", type=Path, default=config.CACHE / "rain")
    p.add_argument("--last-day", default="2026-10-15", help="last day of the 2026 hindcast (the archive's last whole day)")
    p.add_argument("--forecast-rain", type=Path)
    p.add_argument("--out", default=str(config.ROOT / "docs" / "UPGRADED-OVERFLOWS-2026-10"))
    args = p.parse_args()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)

    up = upstream(args.state)
    up.to_csv(f"{args.out}-upstream.csv", index=False)
    print(f"{len(up)} overflows upstream of Cromwheel (forecast log, build of {up['log_issued_at'].iloc[0]})")

    last_2026 = args.last_day
    hc = Hindcast(up, load_rain(up, args.rain, args.rain_2026))

    # Hindcast: every overflow, every day, every scenario; Cromwheel's risk and level per day.
    chances, spot = [], []
    for year in (2024, 2025, 2026):
        start, days = year_days(year, last_2026)
        w, t = up["weight"].to_numpy(float), up["travel_h"].to_numpy(float)
        for name, scen in SCENARIOS.items():
            P = hc.lead0(year, scen, days)
            risk = combine_daily(np.nan_to_num(P.to_numpy(float)), w, t)
            keep = days >= start
            spot.append(pd.DataFrame({"day": days[keep].tz_localize(None), "scenario": name, "risk": risk[keep],
                                      "rain_missing": P.isna().any(axis=0).to_numpy()[keep]}))
            long = P.loc[:, keep].stack().rename("p").reset_index()
            chances.append(long.rename(columns={long.columns[1]: "day"}).assign(scenario=name))
    spot = pd.concat(spot, ignore_index=True)
    spot["level"] = [risk_label(r) for r in spot["risk"]]
    assert not spot["rain_missing"].any(), "a hindcast day has no rain"
    ch = pd.concat(chances, ignore_index=True)
    ch["day"] = local_days(ch["day"])
    live = ch[ch["scenario"] == "live"]

    # Observed spill days (features.spill_days, UK local days as the model trains on): the EA's start/stop files.
    e26 = read_ea_events([args.ea_2026])
    print(f"EA 2026 file: {len(e26):,} events, starts {e26['event_start'].min()} to {e26['event_start'].max()}")
    ev = pd.concat([pd.read_parquet(args.ea_events), e26], ignore_index=True)
    obs = spill_days(ev[ev["site_id"].isin(up["site_id"])])
    obs["day"] = obs["day"].dt.tz_localize(None)

    def expected(sid, a, b) -> float:
        return round(float(live.loc[(live["site_id"] == sid) & live["day"].between(a, b), "p"].sum()), 1)

    def observed(sid, a, b) -> int:
        return int(((obs["site_id"] == sid) & obs["day"].between(a, b)).sum())

    # 1. Expected against observed, January-March and April-August, 2024 to 2026.
    rows = []
    for _, u in up.iterrows():
        r = {"site_id": u["site_id"], "site_name": u["site_name"], "named_by_yorkshire_water": u["named_by_yorkshire_water"]}
        for y in (2024, 2025, 2026):
            for span, a, b in (("jan_mar", "01-01", "03-31"), ("apr_aug", "04-01", "08-31")):
                a, b = pd.Timestamp(f"{y}-{a}"), pd.Timestamp(f"{y}-{b}")
                r[f"expected_{span}_{y}"] = expected(u["site_id"], a, b)
                r[f"observed_{span}_{y}"] = observed(u["site_id"], a, b)
        rows.append(r)
    obs_tab = pd.DataFrame(rows)
    obs_tab.to_csv(f"{args.out}-observed.csv", index=False)
    totals = obs_tab.groupby("named_by_yorkshire_water")[[c for c in obs_tab if c.startswith(("expected_", "observed_"))]].sum()
    print("\nExpected and observed spill days, by group (True: named by Yorkshire Water)\n", totals.T.round(1).to_string())

    # 2. Since each named overflow's last discharge: expected to the hindcast's last day; observed from the
    #    EA file to 31 Aug and from SwimSignal's polls (live_history) after it.
    hist = pd.read_parquet(args.state / "live_history.parquet")
    hist = hist[hist["site_id"].isin(NAMED)].dropna(subset=["latest_event_start"])
    latest = pd.read_parquet(args.state / "live_latest.parquet").set_index("site_id")
    rows = []
    end = pd.Timestamp(last_2026)
    for sid, name in NAMED.items():
        ea_last = e26.loc[e26["site_id"] == sid, "event_end"].max()
        feed_last = hist.loc[hist["site_id"] == sid, "latest_event_end"].max()
        last = max(x for x in (ea_last, feed_last) if pd.notna(x))
        a = local_days(pd.Series([last])).iloc[0] + pd.Timedelta(days=1)
        polled = {d for _, e in hist[hist["site_id"] == sid].iterrows()
                  for d in pd.date_range(local_days(pd.Series([e["latest_event_start"]])).iloc[0],
                                         local_days(pd.Series([e["latest_event_end"] if pd.notna(e["latest_event_end"])
                                                               else e["latest_event_start"]])).iloc[0])
                  if pd.Timestamp("2026-09-01") <= d <= end}
        r = {"site_id": sid, "overflow": name, "last_in_ea_file": ea_last, "last_in_live_feed": feed_last,
             "feed_status_now": int(latest.loc[sid, "status"]), "feed_status_since": latest.loc[sid, "status_start"],
             "window": f"{a:%d %b %Y} to {end:%d %b %Y}"}
        for y in (2024, 2025):
            r[f"expected_{y}"] = expected(sid, a.replace(year=y), end.replace(year=y))
            r[f"observed_{y}"] = observed(sid, a.replace(year=y), end.replace(year=y))
        r["expected_2026"] = expected(sid, a, end)
        r["observed_2026"] = observed(sid, a, min(end, pd.Timestamp("2026-08-31"))) + len(polled)
        rows.append(r)
    since = pd.DataFrame(rows)
    since.to_csv(f"{args.out}-since-last.csv", index=False)
    print("\nSince each named overflow's last discharge\n", since.drop(columns=["site_id"]).to_string(index=False))

    # 3. The live forecast's own lead-0 chances (forecast log) against the feed, 14 Sep to 20 Oct 2026.
    con = duckdb.connect(str(args.state / "dipcast.duckdb"), read_only=True)
    ids = tuple(up["site_id"])
    f = con.sql(f"""select distinct cast(issued_at as varchar) as issued, site_id, target_day, p_cal
                    from forecast_overflows where site_id in {ids} and lead = 0""").df()
    f["target_day"] = pd.to_datetime(f["target_day"])
    a, b = pd.Timestamp("2026-09-14"), pd.Timestamp("2026-10-20")
    f = f[f["target_day"].between(a, b)].groupby(["site_id", "target_day"])["p_cal"].mean().groupby("site_id").sum()
    allh = pd.read_parquet(args.state / "live_history.parquet")
    allh = allh[allh["site_id"].isin(ids)].dropna(subset=["latest_event_start"]).drop_duplicates(["site_id", "latest_event_start"])
    seen = {}
    for _, e in allh.iterrows():
        d0 = local_days(pd.Series([e["latest_event_start"]])).iloc[0]
        d1 = local_days(pd.Series([e["latest_event_end"] if pd.notna(e["latest_event_end"]) else e["latest_event_start"]])).iloc[0]
        seen.setdefault(e["site_id"], set()).update(d for d in pd.date_range(d0, d1) if a <= d <= b)
    log_tab = up[["site_id", "site_name", "named_by_yorkshire_water"]].assign(
        logged_expected=up["site_id"].map(f).round(1), observed_by_feed=up["site_id"].map(lambda s: len(seen.get(s, ()))))
    log_tab.to_csv(f"{args.out}-log.csv", index=False)
    print("\nLive forecast log (lead 0, mean over each day's builds) against the feed, 14 Sep - 20 Oct 2026\n",
          log_tab.groupby("named_by_yorkshire_water")[["logged_expected", "observed_by_feed"]].sum().round(1).to_string())

    # 4. Middleton's expected spill days against its lta_spills, all else as the forecast had it.
    rows = []
    for year in (2024, 2025, 2026):
        start, days = year_days(year, last_2026)
        days = days[days >= start]
        own_p = hc.lead0(year, {}, days).loc[MIDDLETON].to_numpy()
        own = float(hc.sites(year, {}).set_index("site_id").loc[MIDDLETON, "lta_spills"])
        wet = own_p >= 0.3
        for g in LTA_GRID:
            pg = hc.lead0(year, {MIDDLETON: {"lta_spills": float(g)}}, days).loc[MIDDLETON].to_numpy()
            rows.append({"forecast_year": year, "return_year": year - 1, "own_lta_spills": round(own, 2), "lta_spills": g,
                         "expected_spill_days": round(float(np.nansum(pg)), 1),
                         "mean_chance_on_wet_days": round(float(np.nanmean(pg[wet])), 3), "wet_days": int(wet.sum()),
                         "days_above_own": int((pg > own_p + 1e-9).sum()), "days_below_own": int((pg < own_p - 1e-9).sum())})
    curve = pd.DataFrame(rows)
    curve.to_csv(f"{args.out}-lta-curve.csv", index=False)
    print("\nMiddleton: expected spill days by lta_spills\n",
          curve.pivot(index="lta_spills", columns="forecast_year", values="expected_spill_days").to_string())

    # 5. Cromwheel's levels under each scenario, and how many days each scenario moves.
    spot["year"] = spot["day"].dt.year
    base = spot[spot["scenario"] == "live"].set_index("day")
    rows = []
    for (y, name), g in spot.groupby(["year", "scenario"], sort=False):
        g = g.set_index("day")
        b = base.loc[g.index]
        moved = g["level"].ne(b["level"])
        rows.append({"year": y, "scenario": name, **{lv.replace(" ", "_"): int(g["level"].eq(lv).sum()) for lv in LEVELS},
                     "days": len(g), "moderate_or_above_live": int(b["level"].ne("low").sum()),
                     "level_changed": int(moved.sum()),
                     "level_raised": int((moved & (g["risk"] > b["risk"])).sum()),
                     "risk_raised_days": int((g["risk"] > b["risk"] + 1e-9).sum()),
                     "mean_risk_drop": round(float((b["risk"] - g["risk"]).mean()), 4),
                     "max_risk_drop": round(float((b["risk"] - g["risk"]).max()), 3)})
    levels = pd.DataFrame(rows)
    levels.to_csv(f"{args.out}-levels.csv", index=False)
    print("\nCromwheel levels by scenario\n", levels.to_string(index=False))

    # 6. How common is a silence like Middleton's among Yorkshire Water overflows with a similar long-term
    #    average? Live feed (not offline), latest event before the date or none.
    yw = latest[latest["company"] == "Yorkshire Water"]
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    lta = ar[ar["year"] == 2025].drop_duplicates("site_id", keep="last").set_index("site_id")["lta_spills"]
    yw = yw[yw["status"].ne(-1)].assign(lta=lambda d: d.index.map(lta))
    rows = []
    for lo, hi in ((30, 45), (20, 60)):
        g = yw[yw["lta"].between(lo, hi)]
        for cut in ("2026-04-01", "2026-05-09"):
            silent = g["latest_event_start"].isna() | (g["latest_event_start"] < pd.Timestamp(cut, tz="UTC"))
            rows.append({"lta_spills_2025_return": f"{lo}-{hi}", "no_discharge_since": cut, "overflows_with_live_feed": len(g),
                         "silent": int(silent.sum()), "share": round(float(silent.mean()), 3),
                         "silent_since_before_2025": int((g["latest_event_start"] < pd.Timestamp("2025-01-01", tz="UTC")).sum())})
    silence = pd.DataFrame(rows)
    silence.to_csv(f"{args.out}-silence.csv", index=False)
    print("\nSilences among Yorkshire Water overflows (feed of", latest["fetched_at"].max(), ")\n", silence.to_string(index=False))

    # 7. The week of 21-25 Oct 2026: every scenario on one fresh forecast, and Middleton's term swapped in the
    #    published risk (1 - prod(1 - w p) splits exactly; Middleton's travel time is 0.02 h).
    if args.forecast_rain:
        fr = pd.read_parquet(args.forecast_rain)
        daily = daily_rain_features(fr.assign(time=fr["time"].dt.tz_convert(TZ)))
        hist_days = 4
        days = pd.date_range(pd.Timestamp("2026-10-21", tz=TZ) - pd.Timedelta(days=hist_days), periods=hist_days + 5, freq="D")
        w, t = up["weight"].to_numpy(float), up["travel_h"].to_numpy(float)
        i_mid = list(up["site_id"]).index(MIDDLETON)
        w_mid = float(up.loc[i_mid, "weight"])
        rows, mine = [], {}
        for name, scen in SCENARIOS.items():
            pc = calibrate_by_lead(hc.raw(hc.sites(2026, scen), days, daily).to_numpy(float), first_lead=-hist_days)
            risk = combine_daily(np.nan_to_num(pc), w, t)[hist_days:]
            mine[name] = pc[i_mid, hist_days:]
            for d, r, pm in zip(days[hist_days:], risk, mine[name], strict=True):
                rows.append({"source": "fresh forecast", "scenario": name, "day": d.date(), "risk": round(float(r), 3),
                             "level": risk_label(r), "p_middleton": round(float(pm), 3)})
        # Swap: Middleton's published chance scaled by the fresh forecast's ratio for the scenario.
        for name in ("live", "middleton_10", "middleton_10_hours", "middleton_1"):
            for j, d in enumerate(days[hist_days:]):
                ratio = mine[name][j] / mine["live"][j] if mine["live"][j] > 0 else 1.0
                p_new = PUBLISHED_P_MIDDLETON[j] * ratio
                r = 1 - (1 - PUBLISHED_RISK[j]) / (1 - w_mid * PUBLISHED_P_MIDDLETON[j]) * (1 - w_mid * p_new)
                rows.append({"source": "published build, Middleton swapped", "scenario": name, "day": d.date(),
                             "risk": round(float(r), 3), "level": risk_label(r), "p_middleton": round(float(p_new), 3)})
        week = pd.DataFrame(rows)
        week.to_csv(f"{args.out}-week.csv", index=False)
        print("\nThe week of 21-25 Oct 2026\n", week.pivot_table(index=["source", "scenario"], columns="day",
                                                                values="level", aggfunc="first").to_string())


if __name__ == "__main__":
    main()
