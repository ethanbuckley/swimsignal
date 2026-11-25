"""The overflow ledger's season figure (LEDGER stage 2). Contract: docs/OVERFLOW-LEDGER-SEASON-CONTRACT-v1.md. The
statement, pushed before the run: docs/OVERFLOW-LEDGER-SEASON-2026-11.md.

For each overflow in ledger v1 and each bathing season (15 May to 30 September, 2025 and 2024): the spot-days at the
listed spots it reaches that sit at the model's high level with it and below high without it. An account of the
model, not of measured bacteria.

It makes no exposure calculation and holds no transport code. Each link's weight and travel time are ledger v1's (the
exhibit 2 export). Each overflow's modelled daily chance, each spot's risk and the removal rule are CATCH-SIM's
(scripts/lab_catch_sim.py, class Hindcast), called and not copied. Recorded spill days come from the EA's start/stop
files. Ledger v1's file, contract and script are not changed.

Offline; nothing is fetched. Run once, in scratch (AGENTS.md):

    DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state PYTHONPATH=src python scripts/export_overflow_ledger_season.py \
        --cache <main checkout>

--cache is the checkout whose data/cache/rain and data/cache/rain_nine (archive rain) and data/processed event files
(ea_events_<company>.parquet, dcww_ea_events.parquet) are read. They are hashed before and after, and never written.

    python scripts/export_overflow_ledger_season.py --check     # the committed file against its contract
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LEDGER = REPO / "data" / "research" / "overflow_ledger.v1.json"
OUT = REPO / "data" / "research" / "overflow_ledger_season.v1.json"
WHATIF = REPO / "prototypes" / "research-lab" / "workspace" / "whatif" / "data"
STATEMENT = "docs/OVERFLOW-LEDGER-SEASON-2026-11.md"
STATEMENT_COMMIT = "c06bc356"
SCHEMA, VERSION = "swimsignal.overflow-ledger-season", "1.0.0"

TZ = "Europe/London"
SEASONS = (2025, 2024)           # the headline first
GRID_FROM, FIRST, LAST = "05-01", "05-15", "09-30"
EDM_MIN = 90.0                   # a record is usable from this EDM uptime in the year's return
LEVELS = ("low", "moderate", "high", "very high")
MODERATE, HIGH = 1, 2            # level indices
RUNS = ("recorded", "modelled")  # run A: recorded where usable, else modelled; run B: modelled throughout
COMMITTED = ("spill_model.pkl", "lead_calibration.json")
MODEL_MD5 = {"spill_model.pkl": "808da63d", "lead_calibration.json": "9b3cc24c"}   # CATCH-SIM's and the log's stamp
RAIN_CACHES = ("rain", "rain_nine")
REPRODUCE = {"cromwheel": "bw-uke4100-08901", "waterhead": "osm-windermere-waterhead"}
WELSH = "Dwr Cymru Welsh Water"

CLAIM = {
    "public_wording": (
        "An account of SwimSignal's forecast model, not of measured bacteria. For each monitored storm overflow it "
        "counts the days in a past bathing season when the model would have put a listed swim spot at its high level "
        "with this overflow and below high without it. Where the EA's spill record is usable the overflow's spill days "
        "are the recorded ones; elsewhere they are modelled from rain. The weights, the travel times and the levels "
        "are the model's. No sample is used."),
    "not_claimed": [
        "that any spot-day had bad water, or any sample result",
        "any share of the bacteria at a spot: the figures do not add up to a spot's days",
        "that any overflow or company broke a permit or a rule",
        "how much any overflow discharged: a recorded spill day is 1 however long the spill",
        "any comparison or ranking of companies",
        "that the model's level is right: travel times, dilution and the levels are the model's settings",
        "that a spot the table leaves out is clean, or that an overflow it leaves out reaches no swimmer",
    ],
    "evidence": {
        "text": ("At 59 river points no model here had seen, the production estimate put a point's days in order "
                 "with a within-point correlation of 0.376. Rain in the last 48 hours alone gave 0.355. So the "
                 "overflow chain adds little to the order at rivers."),
        "record": "docs/RIVER-UNSEEN-PROTOCOL-2026-11.md",
        "read": "2026-11-16",
    },
}

DEFINITIONS = {
    "season": "15 May to 30 September, local days (Europe/London), 139 days. 2025 is the headline; 2024 shows the spread.",
    "recorded": ("1 on a UTC day the EA start/stop file holds an event at the overflow (features.spill_days, the model's "
                 "training label), placed on the local day of the same date; else 0."),
    "usable": ("A record is used for a season when the company's EA file for that year covers the season, the year's "
               "return gives EDM operational 90% or more, and the file holds an event at it that year or the return "
               "gives 0 spills that year."),
    "modelled": ("The production spill model's lead-0 calibrated chance on archive rain, with the covariates of the "
                 "return of the year before, by CATCH-SIM's Hindcast."),
    "runs": ("recorded: run A, recorded states where usable and modelled chances elsewhere (the headline). modelled: "
             "run B, modelled chances throughout."),
    "level": "The page's level from the shown score: low under 15, moderate under 40, high under 70, else very high.",
    "high": ("The season figure: spot-days at high or very high with every overflow and below high with this overflow's "
             "state set to 0 on every day (CATCH-SIM's removal rule), added over the spots it reaches. Spot-days."),
    "moderate": "Spot-days at moderate or above with every overflow and low with this overflow taken out.",
    "lowered": "Spot-days whose level falls at all with this overflow taken out.",
    "high_no_single": "A spot's high days that no single removal brings below high: they need two or more overflows out.",
    "not_additive": ("An overflow's figure is not a share. A day that needs two overflows counts at each; a day that "
                     "several overflows each reach alone counts at none. The figures at a spot do not sum to its days."),
    "spill_days": "Recorded spill days in the season, where the record is usable; null elsewhere, never 0.",
    "expected_days": "The sum of the modelled daily chances over the season's days, for every overflow.",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ------------------------------------------------------------------ pure parts (tested on made-up rows)
def season_grid(year: int) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Local midnights from 1 May to 30 September, built as dates and then localised (a clock change never shifts a
    day), and which of them are the season's."""
    grid = pd.date_range(f"{year}-{GRID_FROM}", f"{year}-{LAST}", freq="D").tz_localize(TZ)
    return grid, np.asarray(grid >= pd.Timestamp(f"{year}-{FIRST}").tz_localize(TZ))


def recorded_states(days: pd.DataFrame, ids: list[str], grid: pd.DatetimeIndex) -> np.ndarray:
    """(overflows, grid days): 1 where `days` (features.spill_days rows: site_id, UTC day) marks a spill on the date."""
    col = {d.date(): j for j, d in enumerate(grid)}
    row = {s: i for i, s in enumerate(ids)}
    out = np.zeros((len(ids), len(grid)))
    for s, d in zip(days["site_id"], days["day"], strict=True):
        if s in row and d.date() in col:
            out[row[s], col[d.date()]] = 1.0
    return out


def usable_records(ids: list[str], company: list[str], covered: set[str], returns: pd.DataFrame,
                   with_events: set[str]) -> np.ndarray:
    """Which overflows' EA records are used for a season (statement, "Recorded"). `returns` is that year's annual
    return indexed by site_id; `with_events` the ids with an event in the company's file that year."""
    r = returns.reindex(ids)
    up = r["edm_operational_pct"].to_numpy(float) >= EDM_MIN
    zero = r["spills"].to_numpy(float) == 0
    events = np.array([s in with_events for s in ids], dtype=bool)
    held = np.array([c in covered for c in company], dtype=bool)
    return held & up & (events | zero)


def account(X: np.ndarray, risk, level, keep: np.ndarray) -> dict:
    """CATCH-SIM's removal rule at one spot. X: (overflows, grid days) daily states. risk(X, drop): the spot's risk on
    each grid day with overflow `drop` taken out (None for none). level(r): a level index, 0 low to 3 very high.
    keep: the season's days in the grid."""
    def levels(drop):
        return np.array([level(v) for v in risk(X, drop)[keep]])

    base = levels(None)
    n = X.shape[0]
    high, moderate, lowered = np.zeros(n, int), np.zeros(n, int), np.zeros(n, int)
    single = np.zeros(base.size, bool)   # high days that some single removal brings below high
    for i in range(n):
        without = levels(i)
        assert (without <= base).all(), "removing an overflow raised a level"
        below = (base >= HIGH) & (without < HIGH)
        high[i], lowered[i] = below.sum(), (without < base).sum()
        moderate[i] = ((base >= MODERATE) & (without < MODERATE)).sum()
        single |= below
    return {"high_days": int((base >= HIGH).sum()), "high_no_single": int(((base >= HIGH) & ~single).sum()),
            "moderate_days": int((base >= MODERATE).sum()), "high": high, "moderate": moderate, "lowered": lowered}


def spearman(a, b) -> float | None:
    """Rank correlation over the overflows with a figure above 0 in either (statement, "Reported beside")."""
    a, b = pd.Series(a, dtype=float), pd.Series(b, dtype=float)
    m = (a > 0) | (b > 0)
    return None if m.sum() < 3 else round(float(a[m].corr(b[m], method="spearman")), 3)


def check(doc: dict, ledger: dict | None = None) -> list[str]:
    """Faults in a season file against the contract; empty when it holds. With `ledger`, also against ledger v1."""
    bad = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        bad.append("schema or major version")
    ids, spots = doc["overflows"]["site_id"], doc["spots"]
    n = len(ids)
    if ledger is not None:
        if ids != ledger["overflows"]["site_id"]:
            bad.append("overflows differ from ledger v1")
        if [s["id"] for s in spots] != [s["id"] for s in ledger["spots"]]:
            bad.append("spots differ from ledger v1")
    for y, sea in doc["seasons"].items():
        cols = [sea["source"], sea["spill_days"], sea["expected_days"], sea["covariates_filled"], sea["links"],
                *(sea[f][r] for f in ("high", "moderate", "lowered") for r in RUNS)]
        if any(len(c) != n for c in cols):
            bad.append(f"{y}: columns differ in length")
            continue
        at_spot = {r: [0] * len(spots) for r in RUNS}
        for i in range(n):
            links = sea["links"][i]
            if ledger is not None and [ln[0] for ln in links] != [ln[0] for ln in ledger["overflows"]["links"][i]]:
                bad.append(f"{y} {ids[i]}: links differ from ledger v1")
            for k, (f, r) in enumerate((f, r) for f in ("high", "moderate", "lowered") for r in RUNS):
                if sum(ln[1 + k] for ln in links) != sea[f][r][i]:
                    bad.append(f"{y} {ids[i]}: {f} {r} does not match its links")
            for ln in links:
                for r, (h, m, lo) in zip(RUNS, ((ln[1], ln[3], ln[5]), (ln[2], ln[4], ln[6])), strict=True):
                    if lo < max(h, m):
                        bad.append(f"{y} {ids[i]}: lowered under high or moderate at a link")
                    at_spot[r][ln[0]] += h
            if sea["source"][i] not in RUNS or (sea["source"][i] == "modelled") != (sea["spill_days"][i] is None):
                bad.append(f"{y} {ids[i]}: source and spill days")
        if sea["source"].count("recorded") != sea["usable"]:
            bad.append(f"{y}: usable count")
        for s, rec in enumerate(spots):
            block = rec.get(y)
            if rec["overflows"] == 0:
                if block is not None:
                    bad.append(f"{y} {rec['id']}: a spot with no overflow has figures")
                continue
            for r in RUNS:
                b = block[r]
                if not b["high_no_single"] <= b["high_days"] <= b["moderate_days"]:
                    bad.append(f"{y} {rec['id']}: spot counts out of order")
                if at_spot[r][s] < b["high_days"] - b["high_no_single"]:
                    bad.append(f"{y} {rec['id']}: a high day that depends on one overflow is counted at none")
    for k in ("public_wording", "not_claimed", "evidence"):
        if not doc.get("claim", {}).get(k):
            bad.append(f"claim.{k}")
    c = doc.get("checks", {})
    for k in ("inputs_unchanged", "no_missing_day", "removal_never_raised"):
        if c.get(k) is not True:
            bad.append(f"checks.{k}")
    return bad


# ------------------------------------------------------------------ the run (scratch only)
def _inputs(cache: Path, ledger: dict) -> tuple[dict[str, Path], dict[str, Path]]:
    """The shared files the run reads: event files and rain files, each by name."""
    from dipcast.ingest.rainfall import cell_key, grid_cell
    proc = cache / "data" / "processed"
    events = {}
    for name in ledger["companies"]:
        f = proc / ("dcww_ea_events.parquet" if name == WELSH else f"ea_events_{name.lower().replace(' ', '_')}.parquet")
        assert f.is_file(), f"no EA file for {name}: {f}"
        events[name] = f
    o = ledger["overflows"]
    la, lo = grid_cell(np.array(o["lat"], float), np.array(o["lon"], float))
    rain = {}
    for cl, cn in sorted(set(zip(la.tolist(), lo.tolist(), strict=True))):
        key = cell_key(cl, cn)
        for tag in ("2023", "2023dec", "2024", "2025"):   # 2023 (or its December) is history for the 2024 season
            name = f"archive_{key}_{tag}.parquet"
            hit = next((cache / "data" / "cache" / c / name for c in RAIN_CACHES
                        if (cache / "data" / "cache" / c / name).is_file()), None)
            if hit is not None:
                rain[name] = hit
        if f"archive_{key}_2023.parquet" in rain:
            rain.pop(f"archive_{key}_2023dec.parquet", None)
        for tag in ("2024", "2025"):
            assert f"archive_{key}_{tag}.parquet" in rain, f"no {tag} rain for cell {key}"
    return events, rain


def _season_class(lcs):
    class Season(lcs.Hindcast):
        """CATCH-SIM's Hindcast for any overflows and one season. chances(), daily() and risk() are CATCH-SIM's,
        inherited unchanged. Only the inputs differ (statement, "Modelled"): the rain, model and returns are passed in,
        each overflow keeps its own company, and the day grid is the season's."""

        def __init__(self, up: pd.DataFrame, rain: pd.DataFrame, model, ar: pd.DataFrame):
            self.place, self.up, self.rain, self.model, self.ar = "ledger", up.reset_index(drop=True), rain, model, ar
            self.w = self.up["weight"].to_numpy(float)
            self.t = self.up["travel_h"].to_numpy(float)
            self.missing_returns: list[str] = []

        def days(self, year: int):
            return season_grid(year)

        def sites(self, year: int) -> pd.DataFrame:
            """CATCH-SIM's covariates (the return of year - 1, unchanged; a gap left for site_static_features to fill),
            with each overflow's own company."""
            rows = []
            for _, u in self.up.iterrows():
                key = (u["site_id"], year - 1)
                a = self.ar.loc[key] if key in self.ar.index else None
                if a is None:
                    self.missing_returns.append(u["site_id"])
                r = {"site_id": u["site_id"], "lat": u["cell_lat"], "lon": u["cell_lon"], "company": u["company"]}
                for c in ("lta_spills", "spill_hours", "edm_operational_pct"):
                    r[c] = np.nan if a is None else a[c]
                rows.append(r)
            return pd.DataFrame(rows)
    return Season


def run(cache: Path) -> dict:
    assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE"), "set scratch DIPCAST_ROOT and DIPCAST_STATE"
    root = Path(os.environ["DIPCAST_ROOT"]).resolve()
    assert not root.is_relative_to(REPO.resolve()) and not root.is_relative_to(cache.resolve()), "DIPCAST_ROOT must be scratch"
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(HERE))
    from dipcast import config
    assert config.ROOT.resolve() == root and config.PROCESSED.resolve().is_relative_to(root), "config is not the scratch root"

    ledger = json.loads(LEDGER.read_text())
    events_f, rain_f = _inputs(cache, ledger)
    committed = {n: REPO / "data" / "processed" / n for n in (*COMMITTED, "annual_returns.parquet")}
    shared = {**{f"events/{k}": v for k, v in events_f.items()}, **{f"rain/{k}": v for k, v in rain_f.items()},
              **{f"committed/{k}": v for k, v in committed.items()}, "ledger": LEDGER,
              **{f"whatif/{p}": WHATIF / f"{p}.json" for p in REPRODUCE}, "catch_sim": HERE / "lab_catch_sim.py"}
    before = {k: sha256(p) for k, p in shared.items()}
    for n in COMMITTED:   # the model and its calibration, copied into the scratch root they are read from
        assert hashlib.md5(committed[n].read_bytes()).hexdigest().startswith(MODEL_MD5[n]), f"{n} is not the stated file"
        config.PROCESSED.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(committed[n], config.PROCESSED / n)
    copies = {config.PROCESSED / n for n in COMMITTED}

    import lab_catch_sim as lcs
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.features import spill_days
    from dipcast.model.forecast import _lead_calibration
    from dipcast.model.spill_model import SpillModel
    assert _lead_calibration(), "the lead calibration was not read"
    Season = _season_class(lcs)
    model = SpillModel.load()
    ar_all = pd.read_parquet(committed["annual_returns.parquet"]).dropna(subset=["site_id"])
    ar = ar_all.drop_duplicates(["site_id", "year"], keep="last").set_index(["site_id", "year"])

    o, spots_v1 = ledger["overflows"], ledger["spots"]
    ids = list(o["site_id"])
    company = [ledger["companies"][c] for c in o["company"]]
    cl, cn = grid_cell(np.array(o["lat"], float), np.array(o["lon"], float))
    up_all = pd.DataFrame({"site_id": ids, "company": company, "cell_lat": cl, "cell_lon": cn,
                           "weight": 0.0, "travel_h": 0.0})
    assert max(ln[2] for L in o["links"] for ln in L) < 24 * 13, "a travel time reaches before the grid"

    ev = pd.concat([pd.read_parquet(f, columns=["site_id", "event_start", "event_end"]).assign(company=k)
                    for k, f in events_f.items()], ignore_index=True)
    ev["event_end"] = ev["event_end"].fillna(ev["event_start"])
    level = lambda r: LEVELS.index(lcs.level(r))   # noqa: E731

    seasons, spot_blocks, comparison, reproduction = {}, {s["id"]: {} for s in spots_v1}, {}, {}
    for year in SEASONS:
        tags = (f"_{year - 1}.parquet", f"_{year - 1}dec.parquet", f"_{year}.parquet")
        rain = pd.concat([pd.read_parquet(p) for k, p in rain_f.items() if k.endswith(tags)], ignore_index=True)
        rain = rain.assign(time=rain["time"].dt.tz_convert(TZ))
        nat = Season(up_all, rain, model, ar)
        grid, keep = season_grid(year)
        P, _ = nat.chances(year, nat.daily(1.0))
        assert not np.isnan(P).any(), f"{year}: a grid day has no modelled chance"
        gaps = nat.sites(year)[["lta_spills", "spill_hours", "edm_operational_pct"]].isna().any(axis=1).to_numpy()

        # recorded states, and which records are usable. A file covers the season when its events (all overflows,
        # not only the ledger's) run from before 15 May to 30 September or later.
        y0, y1 = pd.Timestamp(f"{year}-01-01", tz="UTC"), pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
        s0, s1 = pd.Timestamp(f"{year}-{FIRST}", tz="UTC"), pd.Timestamp(f"{year}-{LAST}", tz="UTC")
        in_year = ev[(ev["event_start"] < y1) & (ev["event_end"] >= y0)]
        records, covered = {}, set()
        for k in events_f:
            mine = in_year[in_year["company"] == k]
            first, last = mine["event_start"].min(), mine["event_end"].max()
            ok = bool(len(mine)) and first <= s0 and last >= s1
            covered |= {k} if ok else set()
            records[k] = {"first_event": str(first), "last_event": str(last), "covers_season": ok}
        in_year = in_year[in_year["site_id"].isin(set(ids))]
        ret = ar_all[ar_all["year"] == year].drop_duplicates("site_id", keep="last").set_index("site_id")
        use = usable_records(ids, company, covered, ret, set(in_year["site_id"]))
        R = recorded_states(spill_days(in_year), ids, grid)
        long_events = int(((in_year["event_end"] - in_year["event_start"]) > pd.Timedelta(days=60))
                          [in_year["site_id"].isin({s for s, u in zip(ids, use, strict=True) if u})
                           & (in_year["event_end"] >= s0)].sum())
        X = {"recorded": np.where(use[:, None], R, P), "modelled": P}

        # every spot, both runs
        n = len(ids)
        fig = {f: {r: np.zeros(n, int) for r in RUNS} for f in ("high", "moderate", "lowered")}
        links = [[] for _ in range(n)]
        link_of = {}   # (overflow index, spot) -> its counts
        for si, s in enumerate(spots_v1):
            mine = [(i, ln[1], ln[2]) for i in range(n) for ln in o["links"][i] if ln[0] == si]
            if not mine:
                continue
            rows = [m[0] for m in mine]
            up = pd.DataFrame({"site_id": [ids[i] for i in rows], "company": [company[i] for i in rows],
                               "cell_lat": cl[rows], "cell_lon": cn[rows],
                               "weight": [m[1] for m in mine], "travel_h": [m[2] for m in mine]})
            view = Season(up, rain, model, ar)
            w = up["weight"].to_numpy(float)
            block = {"weight_share_recorded": round(float(w[use[rows]].sum() / w.sum()), 3) if w.sum() else None}
            for r in RUNS:
                acc = account(X[r][rows], view.risk, level, keep)
                block[r] = {k: acc[k] for k in ("high_days", "high_no_single", "moderate_days")}
                for j, i in enumerate(rows):
                    link_of.setdefault((i, si), {})[r] = (int(acc["high"][j]), int(acc["moderate"][j]), int(acc["lowered"][j]))
                    for f in ("high", "moderate", "lowered"):
                        fig[f][r][i] += int(acc[f][j])
                if r == "modelled" and s["id"] in REPRODUCE.values():
                    reproduction[f"{s['id']} {year}"] = _reproduce(lcs, s["id"], year, view.risk(X[r][rows], None)[keep], keep)
            spot_blocks[s["id"]][str(year)] = block
        for i in range(n):
            for ln in o["links"][i]:
                c = link_of[(i, ln[0])]
                a, b = c["recorded"], c["modelled"]
                links[i].append([ln[0], a[0], b[0], a[1], b[1], a[2], b[2]])

        exp_days = P[:, keep].sum(axis=1)
        rec_days = R[:, keep].sum(axis=1)
        seasons[str(year)] = {
            "first_day": f"{year}-{FIRST}", "last_day": f"{year}-{LAST}", "days": int(keep.sum()),
            "records": records, "usable": int(use.sum()), "covariates_filled_count": int(gaps.sum()),
            "events_over_60_days": long_events,
            "source": ["recorded" if u else "modelled" for u in use],
            "spill_days": [int(rec_days[i]) if use[i] else None for i in range(n)],
            "expected_days": [round(float(v), 2) for v in exp_days],
            "covariates_filled": [bool(g) for g in gaps],
            **{f: {r: fig[f][r].tolist() for r in RUNS} for f in fig}, "links": links,
        }
        by_co = {}
        for k in events_f:
            m = use & np.array([c == k for c in company])
            e = float(exp_days[m].sum())
            by_co[k] = {"usable": int(m.sum()), "recorded_days": int(rec_days[m].sum()), "expected_days": round(e, 1),
                        "ratio": round(float(rec_days[m].sum()) / e, 2) if e else None}
        comparison[str(year)] = {"by_company": by_co,
                                 "spearman_recorded_vs_modelled": spearman(fig["high"]["recorded"], fig["high"]["modelled"])}
        print(f"{year}: {int(use.sum())} usable records, chances {P.shape}, covariates filled {int(gaps.sum())}")
    comparison["spearman_2024_vs_2025_recorded"] = spearman(seasons["2024"]["high"]["recorded"], seasons["2025"]["high"]["recorded"])
    comparison["note"] = ("Descriptive, deciding nothing. United Utilities is in-sample: the model was fitted on its "
                          "2023-25 spills. The other companies' spills were never in the model's fit, but earlier tests "
                          "here saw them.")

    after = {k: sha256(p) for k, p in shared.items()}
    assert before == after, "a shared input changed during the run"
    wrote = [p for p in root.rglob("*") if p.is_file() and p not in copies]
    assert not wrote, f"files written into the scratch root: {wrote[:3]}"
    rain_digest = hashlib.sha256("".join(f"{k}{before[k]}" for k in sorted(before) if k.startswith("rain/")).encode()).hexdigest()
    caches = {c: sum(1 for p in rain_f.values() if p.parent.name == c) for c in RAIN_CACHES}

    spots = []
    for s in spots_v1:
        rec = {"id": s["id"], "name": s["name"], "status": s["status"], "overflows": s["overflows"]}
        rec.update({y: spot_blocks[s["id"]].get(y) for y in (str(y) for y in SEASONS)})
        spots.append(rec)
    return {
        "schema": SCHEMA, "version": VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "stage": "development: model accounting from a hindcast of past seasons; not a measurement, a test or a confirmation",
        "statement": {"doc": STATEMENT, "commit": STATEMENT_COMMIT},
        "code_commit": subprocess.run(["git", "rev-parse", "--short=8", "HEAD"], cwd=REPO, capture_output=True,
                                      text=True).stdout.strip(),
        "code_sha256": sha256(Path(__file__)), "catch_sim_sha256": before["catch_sim"],
        "ledger": {"file": "data/research/overflow_ledger.v1.json", "sha256": before["ledger"],
                   "version": ledger["version"], "generated_at": ledger["generated_at"]},
        "inputs": {"events": [{"company": k, "file": f"data/processed/{p.name}", "sha256": before[f"events/{k}"]}
                              for k, p in events_f.items()],
                   "committed": {n: {"sha256": before[f"committed/{n}"],
                                     "md5": hashlib.md5(committed[n].read_bytes()).hexdigest()} for n in committed},
                   "rain": {"files": len(rain_f), "by_cache": caches, "digest_sha256": rain_digest,
                            "source": "ERA5-Land hourly archive via Open-Meteo, cached by the forecast and by fetch_rain_nine.py"},
                   "reproduction_targets": {p: before[f"whatif/{p}"] for p in REPRODUCE},
                   "unchanged_after": True, "fetches": 0},
        "attribution": [*ledger["attribution"],
                        "Spill events: Environment Agency Event Duration Monitoring start/stop data, Open Government Licence v3.0.",
                        "Weather data by Open-Meteo.com (CC BY 4.0).",
                        "Contains modified Copernicus Climate Change Service information 2026 (ERA5-Land). Neither the "
                        "European Commission nor ECMWF is responsible for any use that may be made of the Copernicus "
                        "information or data it contains."],
        "claim": CLAIM, "definitions": DEFINITIONS,
        "checks": {"inputs_unchanged": True, "no_missing_day": True, "removal_never_raised": True,
                   "reproduction": {"rule": ("Run B at Cromwheel and Waterhead against CATCH-SIM's committed series: every "
                                             "level equal, every shown score within 1, at least 99% equal"),
                                    "spots": reproduction,
                                    "passed": all(v["passed"] for v in reproduction.values()) and len(reproduction) == 4}},
        "comparison": comparison,
        "companies": ledger["companies"],
        "spots": spots,
        "overflows": {"site_id": ids, "company": o["company"]},
        "seasons": seasons,
    }


def _reproduce(lcs, spot: str, year: int, risk: np.ndarray, keep: np.ndarray) -> dict:
    """Run B's season at a CATCH-SIM spot against CATCH-SIM's committed series (x1.0, nothing removed)."""
    place = next(p for p, s in REPRODUCE.items() if s == spot)
    series = json.loads((WHATIF / f"{place}.json").read_text())["series"][str(year)]["1.0"]["none"]
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    theirs = np.array(series)[(days >= f"{year}-{FIRST}") & (days <= f"{year}-{LAST}")]
    mine = np.array([lcs.shown_score(v) for v in risk])
    lv = lambda s: np.array([LEVELS.index(lcs.level(v / 100)) for v in s])   # noqa: E731
    assert len(mine) == len(theirs) == int(keep.sum())
    diff = np.abs(mine - theirs)
    out = {"days": int(len(mine)), "levels_equal": int((lv(mine) == lv(theirs)).sum()),
           "scores_equal": int((diff == 0).sum()), "max_score_diff": int(diff.max()),
           "high_days_mine": int((lv(mine) >= HIGH).sum()), "high_days_catch_sim": int((lv(theirs) >= HIGH).sum())}
    out["passed"] = bool(out["levels_equal"] == out["days"] and out["max_score_diff"] <= 1
                         and out["scores_equal"] >= 0.99 * out["days"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, help="the checkout whose rain caches and EA event files are read")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="check the file at --out against the contract; write nothing")
    a = ap.parse_args()
    if a.check:
        bad = check(json.loads(a.out.read_text()), json.loads(LEDGER.read_text()))
        print("\n".join(bad) or f"ok: {a.out}")
        sys.exit(1 if bad else 0)
    assert a.cache, "give --cache"
    doc = run(a.cache.resolve())
    bad = check(doc, json.loads(LEDGER.read_text()))
    assert not bad, bad[:10]
    a.out.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False) + "\n")
    rep = doc["checks"]["reproduction"]
    print(f"{a.out}: {len(doc['overflows']['site_id'])} overflows, reproduction passed {rep['passed']}, "
          f"{a.out.stat().st_size / 1024:.0f} kB")


if __name__ == "__main__":
    main()
