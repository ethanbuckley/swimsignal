"""More years of training for the spill model's layer 1 (docs/MULTI-YEAR-TEST-2026-10.md).

The boosted trees (A) and the PR #239 network (B) are trained on the same rows: every year held but 2023
(2020-2022 at Northumbrian and Wessex, 2024-2025 at the nine English companies), and scored on 2023 at
United Utilities, Northumbrian and Wessex, with Thames 2023 reported apart. Off CI, by hand, with the
main checkout's event files linked into data/processed/ and DIPCAST_CACHE at its data/cache/:

    uv run python scripts/train_multi_year.py plan     # overflows per year, rain cells, what is missing, its cost
    uv run python scripts/train_multi_year.py fetch    # the missing ERA5-Land, paced -> data/cache/rain_multi/
    uv sync --extra nn
    uv run python scripts/train_multi_year.py time     # one epoch of the network, seed 0; nothing saved
    uv run python scripts/train_multi_year.py train    # A, A24 and B's three seeds -> data/processed/multi_year/
    uv run python scripts/train_multi_year.py score    # 2023: every predictor, the bootstrap, the conditions

`plan`, `fetch`, `time` and `train` score nothing on 2023. `score` needs D2's candidate and PR #239's
networks from swimsignal-private/baselines/ (their SHA-256 prefixes are checked).
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest import rainfall
from dipcast.ingest.rainfall import _request, _to_frame, cell_key
from dipcast.model.features import ALL_FEATURES, daily_rain_features, spill_days
from dipcast.model.training import MIN_EDM_PCT, NINE, cells_of, load_events, site_years

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import _frame  # noqa: E402  D2's site-day frame (scripts/train.py)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("train_multi_year")

HIST = ["Northumbrian Water", "Wessex Water"]            # the companies with event records before 2024
TEST = ["United Utilities", "Northumbrian Water", "Wessex Water"]
SIDE = "Thames Water"                                    # 2023 from the alert stream: reported, not deciding
TEST_YEAR = 2023
TRAIN = {2020: HIST, 2021: HIST, 2022: HIST, 2024: NINE, 2025: NINE}
# The return each row year takes its covariates from: never its own year, never 2023, never a later
# return's long-term average (it covers every full year up to its return, so 2024's and 2025's include
# 2023). The latest earlier return where one is held; 2020 and 2021 rows, with none, take the next year's.
COV_RETURN = {2020: 2021, 2021: 2022, 2022: 2021, 2023: 2022, 2024: 2022, 2025: 2024}
# Row years whose lta_spills is the EA's long-term average (the 2022 return's: all its years are earlier).
# Everywhere else it is the covariate return's counted spills for its own year.
LTA_ROWS = {2023, 2024}
RETURNS = (2021, 2022, 2023, 2024, 2025)

OWN = config.CACHE / "rain_multi"
RAIN_DIRS = ("rain", "rain_nine", "rain_multi")
CALLS_PER_HOUR = 3000          # Open-Meteo's free limits are 5,000 an hour and 10,000 a day (UTC)
DAY_BUDGET = 8000              # this script's own ceiling for one UTC day
T0 = pd.Timestamp("2019-12-01", tz="UTC")
T_END = pd.Timestamp("2026-01-01", tz="UTC")
OUT = config.PROCESSED / "multi_year"
DOCS = config.ROOT / "docs" / "MULTI-YEAR-TEST-2026-10"
BASELINES = Path.home() / "Documents" / "GitHub" / "swimsignal-private" / "baselines"
D2_SHA = "1603678923cc"
NN239_SHA = {0: "2a9b45bf52da", 1: "89b3aebd9b2f", 2: "75c7f33952cf"}
D2_ROWS = {2024: 4_976_868, 2025: 5_077_150}
PRIOR_STRENGTH, RECENCY, NEG_FRAC = 15.0, 1.0, 0.25
N_BOOT = 2000
_T = time.time()


def step(msg: str) -> None:
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9   # bytes on macOS
    log.info("[%6.0fs, peak %5.1f GB] %s", time.time() - _T, rss, msg)


# ------------------------------------------------------------------ events and overflow-years
def history_events() -> pd.DataFrame:
    """Events before 2024: Northumbrian and Wessex from their own layers (PR #258), United Utilities from
    its Stream 2023 layer (edm_events.parquet), Thames from the alert stream. December 2022 is kept only
    so that an event running over New Year labels the 2023 days it touches."""
    p = config.PROCESSED
    uu = pd.read_parquet(p / "edm_events.parquet")
    parts = [
        pd.read_parquet(p / "stream_events_northumbrian_water.parquet").assign(company="Northumbrian Water"),
        pd.read_parquet(p / "stream_events_wessex_water.parquet").assign(company="Wessex Water"),
        uu[uu["source"] == "United Utilities 2023"].assign(company="United Utilities"),
        pd.read_parquet(p / "api_events_thames_water.parquet").assign(company=SIDE),
    ]
    ev = pd.concat([e[["site_id", "event_start", "event_end", "company"]] for e in parts], ignore_index=True)
    ev["site_id"] = ev["site_id"].astype(object)
    return ev[ev["event_start"] < pd.Timestamp("2024-01-01", tz="UTC")].reset_index(drop=True)


def hist_site_years(ar: pd.DataFrame, ev: pd.DataFrame, companies, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The overflows of `companies` in `year` (2020-2023). An overflow is any id with a position in a held
    return (2021-2025); its position is the covariate return's, else the latest return's. Kept as D2 keeps
    a site-year: an event in `year`, or 0 spills in the `year` return; dropped when the `year` return gives
    EDM operation under 50%. 2020 has no return, so there only an event keeps an overflow."""
    a = ar[ar["company"].isin(companies) & ar["site_id"].notna() & ar["year"].isin(RETURNS)]
    pos = a[a["lat"].notna()].assign(pref=lambda d: (d["year"] == COV_RETURN[year]).astype(int))
    sites = pos.sort_values(["pref", "year"]).drop_duplicates("site_id", keep="last")
    same = a[a["year"] == year].drop_duplicates("site_id", keep="last").set_index("site_id")
    sid = sites["site_id"]
    in_file = sid.isin(set(ev.loc[ev["event_start"].dt.year == year, "site_id"]))
    zero = sid.map(same["spills"]).eq(0)
    low_edm = sid.map(same["edm_operational_pct"]).lt(MIN_EDM_PCT)
    covered = in_file | zero
    keep = covered & ~low_edm
    counts = pd.DataFrame({"company": sites["company"], "with_position": 1,
                           "missing_from_file": (~covered).astype(int),
                           "edm_under_50": (covered & low_edm).astype(int), "kept": keep.astype(int)})
    counts = counts.groupby("company").sum()
    counts["year"] = year
    return sites.loc[keep, ["site_id", "company", "lat", "lon"]].reset_index(drop=True), counts


def with_covariates(ar: pd.DataFrame, sites: pd.DataFrame, year: int) -> pd.DataFrame:
    """`sites` with the three covariates from COV_RETURN[year] (LTA_ROWS says which lta_spills). An id the
    return lacks keeps NaN, which site_static_features fills with its company's median over the year."""
    r = ar[ar["year"] == COV_RETURN[year]].dropna(subset=["site_id"])
    r = r.drop_duplicates("site_id", keep="last").set_index("site_id")
    s = sites[["site_id", "company", "lat", "lon"]].copy()
    s["lta_spills"] = s["site_id"].map(r["lta_spills"] if year in LTA_ROWS else r["spills"])
    s["spill_hours"] = s["site_id"].map(r["spill_hours"])
    s["edm_operational_pct"] = s["site_id"].map(r["edm_operational_pct"])
    return s


def all_site_years(ar: pd.DataFrame) -> tuple[dict, dict, pd.DataFrame, pd.DataFrame]:
    """{year: sites with this test's covariates} for the training years and 2023 (Thames included),
    D2's own 2024 sites with D2's covariates (for PR #239's layer 2), the coverage counts and the counts
    of covariates each year's return lacks."""
    ev_h = history_events()
    ev_n = load_events(NINE)
    out, counts, filled = {}, [], []
    for y in (*sorted(TRAIN), TEST_YEAR):
        if y in (2024, 2025):
            s, c = site_years(ar, ev_n, NINE, y)              # D2's rows
        elif y == TEST_YEAR:
            s, c = site_years(ar, ev_h, [*TEST, SIDE], y)     # D2's rule, applied to 2023
        else:
            s, c = hist_site_years(ar, ev_h, TRAIN[y], y)
        out[y] = with_covariates(ar, s, y)
        counts.append(c)
        f = out[y].groupby("company")[["lta_spills", "spill_hours", "edm_operational_pct"]].agg(
            lambda v: int(v.isna().sum()))
        filled.append(f.assign(year=y, overflows=out[y].groupby("company").size()))
    d2_2024, _ = site_years(ar, ev_n, NINE, 2024)
    return out, {"d2_2024": d2_2024}, pd.concat(counts), pd.concat(filled)


# ------------------------------------------------------------------ rain
def cached(tag: str) -> set[tuple[float, float]]:
    got = set()
    for d in RAIN_DIRS:
        for f in (config.CACHE / d).glob(f"archive_*_{tag}.parquet"):
            p = f.stem.split("_")
            got.add((float(p[1]), float(p[2])))
    return got


def calls(n_cells: int, days: int) -> float:
    """Open-Meteo's weight for one variable: max(1, days/14 x 1/10) a location (its calculateQueryWeight)."""
    return n_cells * max(1.0, days / 14 / 10)


def missing_rain(sites_by_year: dict) -> dict[str, list]:
    """Cell-files to fetch: for each row year Y, the whole of Y and December of Y-1 for every cell of Y's
    overflows ("<Y-1>dec" is enough where Y-1 itself is not needed)."""
    need_year, need_dec = {}, {}
    for y, s in sites_by_year.items():
        need_year.setdefault(y, set()).update(cells_of(s))
        need_dec.setdefault(y - 1, set()).update(cells_of(s))
    todo = {}
    for y, cells in need_year.items():
        todo[str(y)] = sorted(cells - cached(str(y)))
    for y, cells in need_dec.items():
        whole = need_year.get(y, set())
        todo[f"{y}dec"] = sorted(cells - whole - cached(str(y)) - cached(f"{y}dec"))
    return {k: v for k, v in todo.items() if v}


def cost(todo: dict[str, list]) -> dict[str, float]:
    return {k: calls(len(v), 31 if k.endswith("dec") else 366) for k, v in todo.items()}


def fetch(todo: dict[str, list]) -> None:
    """Paced at CALLS_PER_HOUR, and stopped before DAY_BUDGET in one UTC day; run again the next day."""
    OWN.mkdir(parents=True, exist_ok=True)
    rainfall.CACHE = OWN
    day, spent = pd.Timestamp.now("UTC").date(), 0.0
    for tag in sorted(todo):
        cells = [c for c in todo[tag] if not (OWN / f"archive_{cell_key(*c)}_{tag}.parquet").exists()]
        for i in range(0, len(cells), rainfall.BATCH):
            chunk = cells[i:i + rainfall.BATCH]
            w = calls(len(chunk), 31 if tag.endswith("dec") else 366)
            if pd.Timestamp.now("UTC").date() != day:
                day, spent = pd.Timestamp.now("UTC").date(), 0.0
            if spent + w > DAY_BUDGET:
                log.warning("stopping: %.0f calls today (UTC), the budget is %d; run again after 00:00 UTC", spent, DAY_BUDGET)
                return
            if tag.endswith("dec"):
                y = int(tag[:4])
                params = {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                          "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                          "start_date": f"{y}-12-01", "end_date": f"{y}-12-31", "hourly": "precipitation",
                          "timezone": "UTC"}
                res = _request(config.OPEN_METEO_ARCHIVE, params, retry_429=False)
                for (cl, cn), r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
                    _to_frame(r, cl, cn).to_parquet(OWN / f"archive_{cell_key(cl, cn)}_{tag}.parquet", index=False)
            else:
                rainfall.fetch_archive(chunk, int(tag), strict=True)
            spent += w
            log.info("%s: %d/%d cells; %.0f calls today", tag, i + len(chunk), len(cells), spent)
            time.sleep(3600.0 * w / CALLS_PER_HOUR)
    print("FETCH DONE")


def rain_files(cells: set) -> list[Path]:
    tags = {*(str(y) for y in range(2019, 2026)), *(f"{y}dec" for y in range(2019, 2025))}
    files = []
    for d in RAIN_DIRS:
        for f in (config.CACHE / d).glob("archive_*.parquet"):
            p = f.stem.split("_")
            if len(p) == 4 and p[3] in tags and (float(p[1]), float(p[2])) in cells:
                files.append(f)
    return sorted(files)


def _key(lat, lon) -> np.ndarray:
    return (np.round(np.asarray(lat, float) * 10).astype(np.int64) * 100_000
            + np.round(np.asarray(lon, float) * 10).astype(np.int64))


class Rain:
    """Hourly ERA5-Land (mm, NaN where missing) per cell from T0, the daily features (daily_rain_features,
    one cell at a time in chunks, which gives what one call over all cells gives), and the duplicate
    hours the caches hold twice (counted, and how many disagree)."""

    def __init__(self, cells: set, chunk: int = 120):
        cells = sorted(cells)
        self.keys = pd.Index(np.unique(_key([c[0] for c in cells], [c[1] for c in cells])))
        self.n_hours = int((T_END - T0) / pd.Timedelta(hours=1))
        self.n_days = self.n_hours // 24
        self.mm = np.full((len(self.keys), self.n_hours), np.nan, np.float32)
        self.rain_d = np.full((len(self.keys), self.n_days), np.nan, np.float32)
        self.api = np.full((len(self.keys), self.n_days), np.nan, np.float32)
        self.n_duplicates = self.n_conflicts = 0
        parts = []
        for i in range(0, len(cells), chunk):
            cs = set(cells[i:i + chunk])
            r = pd.concat((pd.read_parquet(f) for f in rain_files(cs)), ignore_index=True)
            r = r[(r["time"] >= T0) & (r["time"] < T_END)]
            r["precip_mm"] = pd.to_numeric(r["precip_mm"], errors="coerce").astype(np.float32)
            dup = r.duplicated(["cell_lat", "cell_lon", "time"], keep=False)
            if dup.any():
                d = r[dup].groupby(["cell_lat", "cell_lon", "time"])["precip_mm"]
                self.n_duplicates += int(d.ngroups)
                self.n_conflicts += int(((d.max() - d.min()).abs() > 1e-6).sum())
            daily = daily_rain_features(r)
            u = r.sort_values(["cell_lat", "cell_lon", "time"])
            u = u[~u.duplicated(["cell_lat", "cell_lon", "time"], keep="last")]
            ci = self.keys.get_indexer(_key(u["cell_lat"], u["cell_lon"]))
            hi = ((u["time"] - T0) // pd.Timedelta(hours=1)).to_numpy()
            self.mm[ci, hi] = u["precip_mm"].to_numpy()
            dci = self.keys.get_indexer(_key(daily["cell_lat"], daily["cell_lon"]))
            ddi = ((daily["day"] - T0) // pd.Timedelta(days=1)).to_numpy()
            ok = (ddi >= 0) & (ddi < self.n_days)
            self.rain_d[dci[ok], ddi[ok]] = daily["rain_d"].to_numpy()[ok]
            self.api[dci[ok], ddi[ok]] = daily["api"].to_numpy()[ok]
            parts.append(daily)
            step(f"rain: {min(i + chunk, len(cells))}/{len(cells)} cells")
        self.daily = pd.concat(parts, ignore_index=True)
        self.daily_log = np.log1p(np.clip(np.nan_to_num(self.rain_d, nan=0.0), 0, None)).astype(np.float32)


KEEP_COLS = ["site_id", "company", "year", "day", "cell_lat", "cell_lon", "y", *ALL_FEATURES]


def frames(ar: pd.DataFrame, need_d2: bool = False):
    """Every row year's site-days (scripts/train.py _frame), and the rain behind them."""
    sites, extra, counts, filled = all_site_years(ar)
    every = pd.concat([*sites.values(), extra["d2_2024"]])
    rain = Rain(cells_of(every))
    step(f"rain: {len(rain.keys)} cells; {rain.n_duplicates} hours held twice, {rain.n_conflicts} disagreeing")
    lab_h = spill_days(history_events())
    lab_n = spill_days(load_events(NINE))
    out = {}
    for y, s in sites.items():
        f = _frame(s, y, rain.daily, lab_n if y in (2024, 2025) else lab_h)
        out[y] = f[KEEP_COLS].reset_index(drop=True)
        step(f"site-days {y}: {len(out[y])}")
        if y in D2_ROWS:
            assert len(out[y]) == D2_ROWS[y], f"{y}: {len(out[y])} rows, not D2's {D2_ROWS[y]}"
    d2 = _frame(extra["d2_2024"], 2024, rain.daily, lab_n)[KEEP_COLS].reset_index(drop=True) if need_d2 else None
    del rain.daily
    return out, d2, rain, counts, filled


def training_set(f: dict) -> pd.DataFrame:
    return pd.concat([f[y] for y in sorted(TRAIN)], ignore_index=True)


# ------------------------------------------------------------------ stages
def stage_plan() -> None:
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    sites, extra, counts, filled = all_site_years(ar)
    print("\n=== Overflow-years kept ===")
    print(counts.reset_index().pivot_table(index="company", columns="year", values="kept").fillna(0).astype(int).to_string())
    print("\n=== Covariates the return lacks (filled with the company median) ===")
    print(filled.to_string())
    by_year = dict(sites)
    by_year[2024] = pd.concat([sites[2024], extra["d2_2024"]])
    allc = cells_of(pd.concat(by_year.values()))
    todo = missing_rain(by_year)
    c = cost(todo)
    print(f"\n{len(allc)} cells in all")
    for y, s in sorted(sites.items()):
        print(f"{y}: {len(cells_of(s))} cells")
    print("to fetch (cells):", {k: len(v) for k, v in todo.items()})
    print("calls:", {k: round(v) for k, v in c.items()}, "total", round(sum(c.values())))


def stage_fetch() -> None:
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    sites, extra, _, _ = all_site_years(ar)
    by_year = dict(sites)
    by_year[2024] = pd.concat([sites[2024], extra["d2_2024"]])
    todo = missing_rain(by_year)
    log.info("to fetch: %s; %.0f calls", {k: len(v) for k, v in todo.items()}, sum(cost(todo).values()))
    if "--dry-run" in sys.argv:
        return
    fetch(todo)


if __name__ == "__main__":
    {"plan": stage_plan, "fetch": stage_fetch}[sys.argv[1]]()
