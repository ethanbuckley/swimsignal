"""More years of training for the spill model's layer 1 (docs/MULTI-YEAR-TEST-2026-10.md).

The boosted trees (A) and scripts/train_nn.py's network (B) are trained on the same rows: every year
held but 2023 (2020-2022 at Northumbrian and Wessex, 2024-2025 at the nine English companies), and
scored on 2023 at United Utilities, Northumbrian and Wessex, with Thames 2023 reported apart. Off CI,
by hand, with the main checkout's event files linked into data/processed/ and DIPCAST_CACHE at its
data/cache/:

    uv run python scripts/train_multi_year.py plan     # overflows per year, rain cells, what is missing, its cost
    uv run python scripts/train_multi_year.py fetch    # the missing ERA5-Land, paced -> data/cache/rain_multi/
    uv sync --extra nn
    uv run python scripts/train_multi_year.py time     # one epoch of the network, seed 0; nothing saved
    uv run python scripts/train_multi_year.py train    # A, A24 and B's three seeds -> data/processed/multi_year/
    uv run python scripts/train_multi_year.py score    # 2023: every predictor, the bootstrap, the conditions

`plan`, `fetch`, `time` and `train` score nothing on 2023. `score` needs D2's candidate and the
networks train_nn.py trained, from swimsignal-private/baselines/ (their SHA-256 prefixes are checked).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest import rainfall
from dipcast.ingest.rainfall import _request, _to_frame, cell_key
from dipcast.model.features import ALL_FEATURES, LOCAL_TZ, daily_rain_features, spill_days
from dipcast.model.spill_model import EPS
from dipcast.model.training import MIN_EDM_PCT, NINE, cells_of, load_events, site_years

sys.path.insert(0, str(Path(__file__).resolve().parent))
# D2's site-day frame (scripts/train.py).
from train import _frame

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
CHECKS: dict = {}   # what the row building measured, for rows_checks.json
_T = time.time()


def step(msg: str) -> None:
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9   # bytes on macOS
    log.info("[%6.0fs, peak %5.1f GB] %s", time.time() - _T, rss, msg)


# ------------------------------------------------------------------ events and overflow-years
def history_events() -> pd.DataFrame:
    """Events before 2024: Northumbrian and Wessex from their own layers (import_stream_events.py),
    United Utilities from its Stream 2023 layer (edm_events.parquet), Thames from the alert stream.
    December 2022 is kept only so that an event running over New Year labels the 2023 days it touches."""
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
    # An event with no id names no overflow (Thames: a location mapped neither way and without a TW: id).
    ev = ev[ev["site_id"].notna() & (ev["event_start"] < pd.Timestamp("2024-01-01", tz="UTC"))]
    return ev.reset_index(drop=True)


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
    # An id held twice in a return: the last row with a position, as training.site_years picks it.
    r = ar[(ar["year"] == COV_RETURN[year]) & ar["lat"].notna()].dropna(subset=["site_id"])
    r = r.drop_duplicates("site_id", keep="last").set_index("site_id")
    s = sites[["site_id", "company", "lat", "lon"]].copy()
    s["lta_spills"] = s["site_id"].map(r["lta_spills"] if year in LTA_ROWS else r["spills"])
    s["spill_hours"] = s["site_id"].map(r["spill_hours"])
    s["edm_operational_pct"] = s["site_id"].map(r["edm_operational_pct"])
    return s


def all_site_years(ar: pd.DataFrame) -> tuple[dict, dict, pd.DataFrame, pd.DataFrame]:
    """{year: sites with this test's covariates} for the training years and 2023 (Thames included),
    D2's own 2024 sites with D2's covariates (for train_nn.py's layer 2), the coverage counts and the counts
    of covariates each year's return lacks."""
    ev_h = history_events()
    ev_n = load_events(NINE)
    out, counts, filled = {}, [], []
    for y in (*sorted(TRAIN), TEST_YEAR):
        if y in (2024, 2025):
            s, c = site_years(ar, ev_n, NINE, y)              # D2's rows
        elif y == TEST_YEAR:
            s, c = site_years(ar, ev_h, [*TEST, SIDE], y)     # D2's rule, applied to 2023
            # site_years can keep a return row with no id, through a "0 spills" on another such row of
            # the same-year return (NaN matches NaN in its map). Such a row names no overflow.
            CHECKS["2023 overflows with no id, dropped"] = int(s["site_id"].isna().sum())
            s = s[s["site_id"].notna()].reset_index(drop=True)
        else:
            s, c = hist_site_years(ar, ev_h, TRAIN[y], y)
        if y in (2024, 2025):
            CHECKS[f"{y} overflows with no id, kept as D2 kept them"] = int(s["site_id"].isna().sum())
        out[y] = with_covariates(ar, s, y)
        if y == TEST_YEAR:   # D2's rule gives its own covariates for 2023; they should be these
            for col in ("lta_spills", "spill_hours", "edm_operational_pct"):
                d2v, v = s[col].to_numpy(float), out[y][col].to_numpy(float)
                same = (d2v == v) | (np.isnan(d2v) & np.isnan(v))
                CHECKS[f"2023 overflows whose {col} differs from D2's rule"] = int((~same).sum())
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
            r = r[(r["time"] >= T0) & (r["time"] < T_END)].copy()
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

    # The three lookups train_nn.Inputs asks a rain grid for (as train_nn.RainGrid, from this T0).
    def rows(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        ci = self.keys.get_indexer(_key(frame["cell_lat"], frame["cell_lon"]))
        assert (ci >= 0).all(), "a row's cell has no rain"
        di = ((frame["day"] - T0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
        assert di.min() >= 30, "a row's 28 daily totals start before the rain does"
        return ci.astype(np.int64), di

    def window(self, ci: np.ndarray, di: np.ndarray) -> np.ndarray:
        """The 72 hourly values (mm) from 00:00 UTC on d-2 to 23:00 UTC on d; NaN where missing."""
        return self.mm[ci[:, None], (di * 24 - 48)[:, None] + np.arange(72)]

    def days(self, ci: np.ndarray, di: np.ndarray) -> np.ndarray:
        """log(1 + daily total) for d-30 .. d-3, oldest first."""
        return self.daily_log[ci[:, None], di[:, None] + np.arange(-30, -2)]

    def save(self, path: Path) -> None:
        np.savez(path, keys=self.keys.to_numpy(), mm=self.mm, rain_d=self.rain_d, api=self.api,
                 dup=np.array([self.n_duplicates, self.n_conflicts]))

    @classmethod
    def load(cls, path: Path) -> Rain:
        z = np.load(path)
        r = cls.__new__(cls)
        r.keys, r.mm, r.rain_d, r.api = pd.Index(z["keys"]), z["mm"], z["rain_d"], z["api"]
        r.n_hours, r.n_days = r.mm.shape[1], r.rain_d.shape[1]
        r.n_duplicates, r.n_conflicts = (int(v) for v in z["dup"])
        r.daily_log = np.log1p(np.clip(np.nan_to_num(r.rain_d, nan=0.0), 0, None)).astype(np.float32)
        return r


KEEP_COLS = ["site_id", "company", "year", "day", "cell_lat", "cell_lon", "y", *ALL_FEATURES]
D2_COV = ["d2_" + c for c in ("log_lta_spills", "log_spill_hours", "edm_pct")]
ROWS, RAIN = OUT / "rows.parquet", OUT / "rain.npz"


def d2_feature_gap(rain: Rain, d2_sites: pd.DataFrame, n_cells: int = 80) -> dict:
    """The largest gap between this test's daily rain features and D2's own (training.load_rain, from
    1 December 2023), over 2024-2025, on cells of D2's 2024 overflows drawn with default_rng(0)."""
    from dipcast.model.training import load_rain
    cells = sorted(cells_of(d2_sites))
    pick = [cells[k] for k in sorted(np.random.default_rng(0).choice(len(cells), n_cells, replace=False))]
    ref = daily_rain_features(load_rain(set(pick)))
    ref = ref[ref["day"] >= pd.Timestamp("2024-01-01", tz="UTC")]
    mine = rain.daily.merge(ref[["cell_lat", "cell_lon", "day"]], on=["cell_lat", "cell_lon", "day"])
    m = ref.merge(mine, on=["cell_lat", "cell_lon", "day"], suffixes=("_d2", ""))
    feats = [f for f in ALL_FEATURES if f in ref.columns]
    return {"cells": n_cells, "cell_days": len(m), **{f: float(np.nanmax(np.abs(m[f] - m[f + "_d2"]))) for f in feats}}


def stage_rows() -> None:
    """Build every row year's site-days (scripts/train.py _frame) and the rain behind them, once."""
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    sites, extra, counts, filled = all_site_years(ar)
    rain = Rain(cells_of(pd.concat([*sites.values(), extra["d2_2024"]])))
    step(f"rain: {len(rain.keys)} cells; {rain.n_duplicates} hours held twice, {rain.n_conflicts} disagreeing")
    gap = d2_feature_gap(rain, extra["d2_2024"])
    step(f"largest gap to D2's rain features, 2024-25: {gap}")
    lab_h = spill_days(history_events())
    lab_n = spill_days(load_events(NINE))
    out = []
    for y, st in sites.items():
        f = _frame(st, y, rain.daily, lab_n if y in (2024, 2025) else lab_h)[KEEP_COLS].reset_index(drop=True)
        if y in D2_ROWS:
            assert len(f) == D2_ROWS[y], f"{y}: {len(f)} rows, not D2's {D2_ROWS[y]}"
        if y == 2024:   # D2's own covariates beside this test's, for train_nn.py's layer 2
            d2 = _frame(extra["d2_2024"], 2024, rain.daily, lab_n).reset_index(drop=True)
            assert (d2["site_id"].to_numpy() == f["site_id"].to_numpy()).all() and (d2["day"] == f["day"]).all()
            for c in D2_COV:
                f[c] = d2[c[3:]].to_numpy(np.float32)
        out.append(f)
        step(f"site-days {y}: {len(f)}, base rate {f['y'].mean():.4f}")
    del rain.daily
    OUT.mkdir(parents=True, exist_ok=True)
    rows = pd.concat(out, ignore_index=True)
    rows[["site_id", "company"]] = rows[["site_id", "company"]].astype("category")
    rows.to_parquet(ROWS, index=False)
    rain.save(RAIN)
    counts.to_csv(f"{DOCS}-coverage.csv")
    filled.to_csv(f"{DOCS}-covariates-filled.csv")
    (OUT / "rows_checks.json").write_text(json.dumps(
        {"rain_cells": len(rain.keys), "hours_held_twice": rain.n_duplicates, "hours_disagreeing": rain.n_conflicts,
         "rows": rows.groupby("year").size().to_dict(), "rain_feature_gap_vs_d2": gap, **CHECKS}, indent=1, default=int))
    step(f"saved {len(rows)} rows -> {ROWS}, rain -> {RAIN}")


def load_rows(years=None) -> pd.DataFrame:
    rows = pd.read_parquet(ROWS, filters=[("year", "in", list(years))] if years else None)
    rows[["site_id", "company"]] = rows[["site_id", "company"]].astype(str).astype(object)
    return rows


# ------------------------------------------------------------------ the network (train_nn.py's, imported)
def _nn():
    import train_nn  # PyTorch (the optional nn group): the network, its fit and helpers
    return train_nn


def training_rows(train: pd.DataFrame):
    """fit_pooled's subsample over the training rows in year order, and the inner hold-out: ISO weeks
    4, 8, ..., 52 of every training year (train_nn.training_rows, without D2's count checks)."""
    nn = _nn()
    keep = np.flatnonzero(nn.subsample(train["y"].to_numpy()))
    rows = train.iloc[keep]
    y = rows["y"].to_numpy()
    w = np.where(y == 1, 1.0, 1.0 / NEG_FRAC)
    held = rows["day"].dt.isocalendar().week.astype(int).to_numpy() % 4 == 0
    return rows, y, w, np.flatnonzero(~held), np.flatnonzero(held)


def stage_time() -> None:
    nn = _nn()
    rain = Rain.load(RAIN)
    train = load_rows(sorted(TRAIN))
    rows, y, w, fit_idx, val_idx = training_rows(train)
    mean, std = nn.standardize(rows, fit_idx)
    x = nn.Inputs(rain, rows, mean, std)
    step(f"training rows {len(fit_idx)}, inner hold-out {len(val_idx)}; {len(fit_idx) // nn.BATCH + 1} batches an epoch")
    net, hist = nn.fit_seed(0, x, y, w, fit_idx, val_idx, max_epochs=1)
    e = hist[0]
    per_seed = nn.MAX_EPOCHS * (e["fit_seconds"] + e["val_seconds"])
    t0 = time.time()
    n = 200_000
    nn.predict([net], nn.Inputs(rain, train.iloc[:n], mean, std), n)
    rate = n / (time.time() - t0)
    print(json.dumps({"epoch_fit_seconds": e["fit_seconds"], "epoch_val_seconds": e["val_seconds"],
                      "max_seconds_per_seed": per_seed, "max_hours_per_seed": per_seed / 3600,
                      "inference_rows_per_second_one_net": round(rate)}, indent=1))


def nn_layer1(nets, rain: Rain, frame: pd.DataFrame, mean, std, transform=None) -> np.ndarray:
    nn = _nn()
    return nn.predict(nets, nn.Inputs(rain, frame, mean, std), len(frame), transform=transform).mean(0)


def stage_train() -> None:
    import torch
    nn = _nn()
    from dipcast.model.spill_model import SpillModel
    OUT.mkdir(parents=True, exist_ok=True)
    train = load_rows(sorted(TRAIN))
    step(f"training rows: {len(train)} site-days, {train.groupby('year').size().to_dict()}")

    # (A) and A24: D2's settings.
    rows, *_ = training_rows(train)
    step(f"the subsample both candidates fit: {len(rows)} of {len(train)} rows")
    del rows
    a = SpillModel().fit_pooled(train, neg_frac=NEG_FRAC)
    a.fit_site_offsets(train, prior_strength=PRIOR_STRENGTH, recency=RECENCY)
    a.trained_on = "Multi-year test (A): Northumbrian, Wessex 2020-22; nine English companies 2024-25"
    a.save(OUT / "A.pkl")
    step(f"A: {a.clf.n_iter_} iterations; {len(a.site_offset)} offsets")
    t24 = train[train["year"] == 2024]
    a24 = SpillModel().fit_pooled(t24, neg_frac=NEG_FRAC)
    a24.fit_site_offsets(t24, prior_strength=PRIOR_STRENGTH, recency=RECENCY)
    a24.trained_on = "Multi-year test (A24): nine English companies 2024, this test's covariates"
    a24.save(OUT / "A24.pkl")
    step(f"A24: {a24.clf.n_iter_} iterations")
    del t24

    # (B): train_nn.py's network on the same rows.
    rain = Rain.load(RAIN)
    rows, y, w, fit_idx, val_idx = training_rows(train)
    mean, std = nn.standardize(rows, fit_idx)
    x = nn.Inputs(rain, rows, mean, std)
    short = np.isfinite(rain.window(x.ci, x.di)).sum(1) < nn.MIN_FINITE
    step(f"B: training rows {len(fit_idx)}, inner hold-out {len(val_idx)}; {int(short.sum())} under the 90% rule (kept)")
    hist, nets = [], []
    for seed in nn.SEEDS:
        net, h = nn.fit_seed(seed, x, y, w, fit_idx, val_idx)
        torch.save(net.state_dict(), OUT / f"B_seed{seed}.pt")
        nets.append(net)
        hist += h
        pd.DataFrame(hist).to_csv(f"{DOCS}-training.csv", index=False)
    meta = {"static": nn.STATIC, "mean": mean.tolist(), "std": std.tolist(), "seeds": list(nn.SEEDS),
            "fit_rows": len(fit_idx), "inner_holdout_rows": len(val_idx), "under_90pct_training_rows": int(short.sum()),
            "weights": int(sum(p.numel() for p in nets[0].parameters())), "torch": torch.__version__}
    (OUT / "B_meta.json").write_text(json.dumps(meta, indent=1))
    del x, rows

    # Layer 2 for B, on its own predictions over every training row.
    b = nn.Challenger(features=[])
    b.fit_site_offsets(train.assign(p_nn=nn_layer1(nets, rain, train, mean, std)),
                       prior_strength=PRIOR_STRENGTH, recency=RECENCY)
    b.trained_on = "Multi-year test (B): PR #239's network on A's rows"
    b.save(OUT / "B_layer2.pkl")
    step("B: layer 2")

    # The networks train_nn.py trained: layer 2 refitted as it does, on D2's 2024 rows with D2's covariates.
    nets239, meta239 = load_nn239()
    d2_24 = train[train["year"] == 2024].copy()
    for c in D2_COV:
        d2_24[c[3:]] = d2_24[c]
    c239 = nn.Challenger(features=[])
    c239.fit_site_offsets(d2_24.assign(p_nn=nn_layer1(nets239, rain, d2_24, *meta239)),
                          prior_strength=PRIOR_STRENGTH, recency=RECENCY)
    c239.save(OUT / "NN239_layer2.pkl")
    step("PR #239's networks: layer 2 refitted")


def load_nn239():
    import torch
    nn = _nn()
    d = BASELINES / "nn_challenger"
    meta = json.loads((d / "meta.json").read_text())
    nets = []
    for s in meta["seeds"]:
        sha = hashlib.sha256((d / f"seed{s}.pt").read_bytes()).hexdigest()
        assert sha.startswith(NN239_SHA[s]), f"seed{s}.pt is not PR #239's ({sha[:12]})"
        net = nn.Net()
        net.load_state_dict(torch.load(d / f"seed{s}.pt"))
        nets.append(net.eval())
    return nets, (np.array(meta["mean"], np.float32), np.array(meta["std"], np.float32))


def load_b():
    import torch
    nn = _nn()
    meta = json.loads((OUT / "B_meta.json").read_text())
    nets = []
    for s in meta["seeds"]:
        net = nn.Net()
        net.load_state_dict(torch.load(OUT / f"B_seed{s}.pt"))
        nets.append(net.eval())
    return nets, (np.array(meta["mean"], np.float32), np.array(meta["std"], np.float32))


# ------------------------------------------------------------------ scoring 2023
def stage_score() -> None:
    import pickle
    nn = _nn()
    from dipcast.model.spill_model import SpillModel
    from dipcast.model.training import ece
    from dipcast.model.verify import reliability_table, scores

    d2_path = BASELINES / "spill_model_nine_2024.pkl"
    sha = hashlib.sha256(d2_path.read_bytes()).hexdigest()
    assert sha.startswith(D2_SHA), f"{d2_path.name} is not D2's candidate ({sha[:12]})"
    d2 = SpillModel.load(d2_path)
    a, a24 = SpillModel.load(OUT / "A.pkl"), SpillModel.load(OUT / "A24.pkl")
    b = pickle.loads((OUT / "B_layer2.pkl").read_bytes())
    c239 = pickle.loads((OUT / "NN239_layer2.pkl").read_bytes())
    nets_b, stand_b = load_b()
    nets_239, stand_239 = load_nn239()
    rain = Rain.load(RAIN)
    flat = pd.read_parquet(ROWS, columns=["company", "y", "year"], filters=[("year", "in", sorted(TRAIN))])
    flat = flat.groupby("company", observed=True)["y"].mean()
    flat.index = flat.index.astype(str)

    test = load_rows([TEST_YEAR])
    x = nn.Inputs(rain, test, *stand_b)
    keep = np.isfinite(rain.window(x.ci, x.di)).sum(1) >= nn.MIN_FINITE
    dropped = test.loc[~keep, "company"].value_counts().to_dict()
    print("\n=== 2023 rows dropped by the 90% rule ===", int((~keep).sum()), dropped)
    test = test.loc[keep].reset_index(drop=True)
    seeds_b = nn.predict(nets_b, nn.Inputs(rain, test, *stand_b), len(test))
    p_b = seeds_b.mean(0)
    p_239 = nn_layer1(nets_239, rain, test, *stand_239)
    preds = {
        "B (network)": b.predict(test.assign(p_nn=p_b)),
        "A (boosted)": a.predict(test),
        "D2": d2.predict(test),
        "PR #239 network": c239.predict(test.assign(p_nn=p_239)),
        "A24": a24.predict(test),
        "flat rate": test["company"].map(flat).to_numpy(),
        "B, layer 1 only": b.predict_pooled(test.assign(p_nn=p_b)),
        "A, layer 1 only": a.predict_pooled(test),
        "D2, layer 1 only": d2.predict_pooled(test),
        "PR #239 network, layer 1 only": np.clip(p_239, EPS, 1 - EPS),
        "A24, layer 1 only": a24.predict_pooled(test),
        **{f"B seed {s}, layer 1 only": np.clip(seeds_b[j], EPS, 1 - EPS) for j, s in enumerate(nn.SEEDS)},
    }
    step("2023 predictions")
    y = test["y"].to_numpy()
    company = test["company"].to_numpy()
    week = nn.week_codes(test["day"])
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))
    groups = {c: company == c for c in TEST}
    groups["three together"] = np.isin(company, TEST)
    groups[f"{SIDE} (apart)"] = company == SIDE
    pairs = [("B (network)", "A (boosted)"), ("A (boosted)", "D2"), ("A (boosted)", "A24"), ("A24", "D2"),
             ("B (network)", "PR #239 network")]

    rows, rel, diffs = [], [], []
    for g, m in groups.items():
        for k, p in preds.items():
            sc = scores(y[m], p[m])
            rows.append({"group": g, "predictor": k, "rows": sc["n"], "base_rate": sc["base_rate"], "brier": sc["brier"],
                         "auc": sc["auc"], "ece": ece(y[m], p[m]), "log_loss": sc["log_loss"]})
        for k in ("B (network)", "A (boosted)", "D2", "PR #239 network", "A24"):
            rel.append(reliability_table(y[m], preds[k][m]).assign(group=g, predictor=k))
        for one, two in pairs:
            d = (preds[one][m] - y[m]) ** 2 - (preds[two][m] - y[m]) ** 2
            lo, hi = nn.boot_interval(d, week[m], draws)
            diffs.append({"group": g, "first": one, "second": two, "rows": int(m.sum()),
                          "brier_first": float(((preds[one][m] - y[m]) ** 2).mean()),
                          "brier_second": float(((preds[two][m] - y[m]) ** 2).mean()),
                          "difference": float(d.mean()), "ci_low": lo, "ci_high": hi})
    res, dif = pd.DataFrame(rows), pd.DataFrame(diffs)
    pd.set_option("display.width", 220)
    print("\n=== 2023, ERA5-Land rain ===")
    print(res.round(5).to_string(index=False))
    print("\n=== Brier differences, first minus second, 95% week-cluster bootstrap ===")
    print(dif.to_string(index=False, float_format=lambda v: f"{v:.5f}"))

    # Condition 5, on the three deciding companies' rows.
    t3 = test[groups["three together"]].reset_index(drop=True)
    x3 = nn.Inputs(rain, t3, *stand_b)
    p0 = b.predict(t3.assign(p_nn=p_b[groups["three together"]]))
    mono = {}
    for name, fn in (("plus 1 mm every hour", lambda mm: mm + 1.0), ("double every hour", lambda mm: mm * 2.0)):
        p1 = b.predict(t3.assign(p_nn=nn.predict(nets_b, x3, len(t3), transform=fn).mean(0)))
        drop = p0 - p1
        mono[name] = {"rows": len(t3), "lowered": int((drop > 0).sum()), "lowered_share": float((drop > 0).mean()),
                      "largest_drop": float(drop.max()), "pass": bool((drop > 0).mean() < 0.005 and drop.max() <= 0.01)}
        step(f"condition 5, {name}: {mono[name]}")

    # The conditions.
    br = res.set_index(["group", "predictor"])
    dd = dif.set_index(["group", "first", "second"])
    ba, ad = ("B (network)", "A (boosted)"), ("A (boosted)", "D2")
    q1 = {
        "1 real gain overall": bool(dd.loc[("three together", *ba), "difference"] < 0
                                    and dd.loc[("three together", *ba), "ci_high"] < 0),
        "2 no company clearly worse": not [c for c in TEST if dd.loc[(c, *ba), "ci_low"] > 0],
        "4 reliability": not [c for c in TEST if not (br.loc[(c, ba[0]), "ece"] <= br.loc[(c, ba[1]), "ece"]
                                                      or br.loc[(c, ba[0]), "ece"] <= 0.02)],
        "5 more rain does not lower the risk": all(v["pass"] for v in mono.values()),
    }
    q2 = {
        "1 lower over the three": bool(dd.loc[("three together", *ad), "difference"] < 0
                                       and dd.loc[("three together", *ad), "ci_high"] < 0),
        "2 no company clearly worse": not [c for c in TEST if dd.loc[(c, *ad), "ci_low"] > 0],
    }
    print("\n=== Question 1: does the network beat the trees? ===")
    for k, v in q1.items():
        print(f"{k}: {'PASS' if v else 'FAIL'}")
    print("YES" if all(q1.values()) else "NO")
    print("\n=== Question 2: do the trees beat D2? ===")
    for k, v in q2.items():
        print(f"{k}: {'PASS' if v else 'FAIL'}")
    print("YES" if all(q2.values()) else "NO")

    res.to_csv(f"{DOCS}-scores.csv", index=False)
    dif.to_csv(f"{DOCS}-differences.csv", index=False)
    pd.concat(rel).to_csv(f"{DOCS}-reliability.csv", index=False)
    checks = json.loads((OUT / "rows_checks.json").read_text())
    Path(f"{DOCS}-checks.json").write_text(json.dumps(
        {**checks, "dropped_by_90pct_rule": {"total": int((~keep).sum()), **{k: int(v) for k, v in dropped.items()}},
         "rows_scored": len(test), "condition_5": mono, "question_1": q1, "question_2": q2,
         "question_1_yes": all(q1.values()), "question_2_yes": all(q2.values()),
         "layer_2": {"prior_strength": PRIOR_STRENGTH, "recency": RECENCY, "A": len(a.site_offset),
                     "B": len(b.site_offset), "A24": len(a24.site_offset), "PR239": len(c239.site_offset)}},
        indent=1, default=float))
    step("tables written")


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
    if LOCAL_TZ != "UTC":   # its day indices count UTC days from T0; local days would land summer days one early
        sys.exit("train_multi_year.py indexes UTC days and the model now cuts UK local days (docs/DAY-BOUNDARY-TEST-2026-10.md): "
                 "run it from the commit its record names")
    {"plan": stage_plan, "fetch": stage_fetch, "rows": stage_rows, "time": stage_time, "train": stage_train,
     "score": stage_score}[sys.argv[1]]()
