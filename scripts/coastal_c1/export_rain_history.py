"""What each coastal bathing water's own samples read after rain and after dry spells: England 2012 to 2026, Wales and
Northern Ireland 2023 to 2026, the Republic of Ireland 2014 to 2026. Writes data/research/coastal_rain_history.v1.json, read by dipcast.rain_history for the
coverage page's beach cards.

    uv run python scripts/coastal_c1/export_rain_history.py \\
        --fetch "$HOME/dipcast-scratch/coastal-c1-backtest" --rain "$HOME/dipcast-scratch/coastal-c1-era5land/cache/rain" \\
        --uk "$HOME/dipcast-scratch/anywater-uk" --uk-rain "$HOME/dipcast-scratch/anywater-uk/cache/rain" \\
        --ie "$HOME/dipcast-scratch/anywater-ie" --ie-rain "$HOME/dipcast-scratch/anywater-ie/cache/rain"

Past samples split by the rain in the 48 hours before each one (ERA5-Land at the beach's cell, C1's cell rule): "after
rain" is 10 mm or more, "dry" under 1 mm. 48 hours is the window the site already publishes for each rain square, so a
card can say which group today is in. Never a forecast. Offline: England's 2012-21 samples come from C1's backtest
fetch and 2022-26 from the committed table; Wales and Northern Ireland from ANYWATER-UK's fetch; the Republic from the
committed EPA sample history with ANYWATER-IE's positions and rain. An inland water (lake or river) counts results over
900, the inland line, not 500 (docs/INLAND-RAIN-HISTORY-2026-11.md); its lines carry no tested label, because C1 was
never tested on inland waters. A Northern Irish or Irish sample has a date only and counts as taken at 12:00 local time (ANYWATER-UK
amendment 1, ANYWATER-IE statement).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import anywater_ie  # noqa: E402
import backtest  # noqa: E402
import c1  # noqa: E402

OUT = REPO / "data" / "research" / "coastal_rain_history.v1.json"
WET_MM, DRY_MM, HOURS = 10.0, 1.0, 48
MIN_GROUP = 10
COAST_LINE, INLAND_LINE = 500, 900
COAST = ("coast", "estuary")
TESTED = {
    "england": ("A frozen model with rain in it predicted results over 500 better than the same model without rain on "
                "65,350 samples from 2012 to 2021 at 403 English beaches, seasons it never saw (9 of 10 seasons better). "
                "That supports these lines; it is not a chance for today."),
    "wales": ("England's frozen model, never fitted on Welsh or Northern Irish samples, put each beach's 2023 to 2026 "
              "samples in order better with rain than without (7,019 samples at 141 beaches). That supports these lines; "
              "it is not a chance for today."),
}
TESTED["northern_ireland"] = TESTED["wales"]
TESTED["ireland"] = ("England's frozen model, never fitted on Irish samples, put each beach's 2014 to 2026 samples in "
                     "order better with rain than without (24,413 samples at 210 beaches). That supports these lines; "
                     "it is not a chance for today.")


def england(fetch: Path, rain_dir: Path) -> pd.DataFrame:
    old, _ = backtest.backtest_rows(fetch)
    new = pd.read_parquet(REPO / "data" / "research" / "coastal" / "samples.parquet")
    new = new[new["month"].isin(c1.MONTHS) & new["ecoli"].notna()]
    cols = ["site_id", "time", "year", "month", "ecoli", "ecoli_qual"]
    df = pd.concat([old[cols], new[cols]]).sort_values(["site_id", "time"]).reset_index(drop=True)
    cells = c1.site_cells(pd.read_csv(REPO / "data" / "research" / "coastal" / "sites.csv"))
    df["cell"] = df["site_id"].map(lambda s: cells.get(s))
    df["nation"], df["kind"] = "england", "coast"
    return with_rain(df, rain_dir, tuple(range(2012, 2027)))


def uk(out: Path, rain_dir: Path) -> pd.DataFrame:
    st = pd.read_csv(out / "sites.csv")
    st = st[st["lat"].notna()].set_index("id")
    df = pd.DataFrame(json.loads((out / "samples.json").read_text())["rows"])
    df = df[df["site_id"].isin(st.index)].copy()
    t = df["t"].where(df["t"].str.len() != 10, df["t"] + "T12:00:00")
    df["time"] = pd.to_datetime([pd.Timestamp(x).tz_localize("Europe/London") if pd.Timestamp(x).tzinfo is None
                                 else pd.Timestamp(x) for x in t], utc=True).tz_convert("Europe/London")
    df["year"], df["month"] = df["time"].dt.year, df["time"].dt.month
    df["ecoli_qual"] = df["q"].fillna("=")
    df = df[df["month"].isin(c1.MONTHS)]
    df["cell"] = [tuple(map(float, c1.snap([st.at[s, "lat"], st.at[s, "lon"]]))) for s in df["site_id"]]
    df["nation"] = df["site_id"].map(st["nation"])
    df["kind"] = df["site_id"].map(st["kind"])
    return with_rain(df.reset_index(drop=True), rain_dir, tuple(range(2023, 2027)))


def ireland(out: Path, rain_dir: Path) -> pd.DataFrame:
    pos = pd.read_csv(out / "sites.csv").dropna(subset=["lat", "lon"]).set_index("id")
    df = anywater_ie.samples()
    df = df[df["site_id"].isin(pos.index)].copy()
    df["time"] = df["time"].dt.tz_convert(anywater_ie.TZ)
    df["cell"] = [tuple(map(float, c1.snap([pos.at[s, "lat"], pos.at[s, "lon"]]))) for s in df["site_id"]]
    df["nation"] = "ireland"
    return with_rain(df.reset_index(drop=True), rain_dir, anywater_ie.YEARS)


def with_rain(df: pd.DataFrame, rain_dir: Path, years) -> pd.DataFrame:
    df["t_utc"] = pd.DatetimeIndex(df["time"]).tz_convert("UTC")
    df["rain"] = np.nan
    for cell, g in df.groupby("cell"):
        if cell is None:
            continue
        rain = c1.load_cell(rain_dir, cell, years)
        df.loc[g.index, "rain"] = c1.window_sums(g["t_utc"], rain, HOURS)[0]
    return df[df["rain"].notna()]


def summary(g: pd.DataFrame, line: int = COAST_LINE) -> dict:
    if len(g) < MIN_GROUP:
        return {"samples": int(len(g))}
    key = (g["ecoli"] + g["ecoli_qual"].map({"<": -0.5, ">": 0.5}).fillna(0.0)).to_numpy()
    mid = g.iloc[int(np.argsort(key, kind="stable")[(len(g) - 1) // 2])]
    median = f"{mid['ecoli_qual']}{mid['ecoli']:g}" if mid["ecoli_qual"] in ("<", ">") else float(f"{mid['ecoli']:.2g}")
    return {"samples": int(len(g)), "median": median,
            f"over_{line}": int(c1.over(g["ecoli"], g["ecoli_qual"], line).sum())}


def pooled(g: pd.DataFrame, line: int = COAST_LINE) -> dict:
    return {**summary(g, line), f"share_over_{line}": round(float(c1.over(g["ecoli"], g["ecoli_qual"], line).mean()), 4)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch", type=Path, required=True)
    ap.add_argument("--rain", type=Path, required=True)
    ap.add_argument("--uk", type=Path, required=True)
    ap.add_argument("--uk-rain", type=Path, required=True)
    ap.add_argument("--ie", type=Path, required=True)
    ap.add_argument("--ie-rain", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    df = pd.concat([england(a.fetch, a.rain), uk(a.uk, a.uk_rain), ireland(a.ie, a.ie_rain)], ignore_index=True)
    wet, dry = df["rain"] >= WET_MM, df["rain"] < DRY_MM
    inland = ~df["kind"].isin(COAST)
    sites = {}
    for sid, g in df.groupby("site_id"):
        line = INLAND_LINE if inland[g.index].all() else COAST_LINE
        sites[sid] = {"nation": g["nation"].iloc[0], "first_year": int(g["year"].min()), "last_year": int(g["year"].max()),
                      "samples": int(len(g)), "after_rain": summary(g[g["rain"] >= WET_MM], line),
                      "dry": summary(g[g["rain"] < DRY_MM], line)}
        if line == INLAND_LINE:
            sites[sid] = {**sites[sid], "line": INLAND_LINE}
    nations = {}
    for n, g in df.groupby("nation"):
        c, i = g[~inland[g.index]], g[inland[g.index]]
        nations[n] = {"period": f"May to September, {int(c['year'].min())} to {int(c['year'].max())}",
                      "beaches": int(c["site_id"].nunique()), "samples": int(len(c)),
                      "after_rain": pooled(c[wet[c.index]]), "dry": pooled(c[dry[c.index]]), "tested": TESTED[n]}
        if len(i):
            nations[n]["inland"] = {"waters": int(i["site_id"].nunique()), "samples": int(len(i)),
                                    "after_rain": pooled(i[wet[i.index]], INLAND_LINE),
                                    "dry": pooled(i[dry[i.index]], INLAND_LINE)}
    doc = {"schema": "swimsignal.coastal-rain-history", "version": "1.2.0",
           "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "rule": {"hours": HOURS, "after_rain_mm": WET_MM, "dry_mm": DRY_MM, "min_group": MIN_GROUP},
           "nations": nations,
           "sources": {"england": "Environment Agency Water Quality Archive, statutory samples (purpose MS), OGL v3.0",
                       "wales": "Natural Resources Wales in-season bathing water samples, OGL v3.0",
                       "northern_ireland": "DAERA bathing water results tables, OGL v3.0",
                       "ireland": "EPA (Ireland) Bathing Water Open Data API, in-season samples, CC BY 4.0"},
           "rain": "ERA5-Land hourly reanalysis (Copernicus Climate Change Service), the beach's 0.1 degree cell or the "
                   "nearest land point within about 30 km, summed over the 48 hours before each sample",
           "credit": "Contains Environment Agency, Natural Resources Wales and DAERA data, OGL v3.0, and data from the "
                     "Environmental Protection Agency (Ireland), CC BY 4.0. Rain generated using Copernicus Climate "
                     "Change Service information 2026.",
           "records": ["docs/COASTAL-C1-PROTOCOL-2026-11.md", "docs/ANYWATER-UK-STATEMENT-2026-11.md",
                       "docs/ANYWATER-IE-STATEMENT-2026-11.md", "docs/INLAND-RAIN-HISTORY-2026-11.md"],
           "sites": sites}
    a.out.write_bytes(c1.canonical(doc))
    print(json.dumps({n: {k: v[k] for k in ("beaches", "samples", "after_rain", "dry")} for n, v in nations.items()},
                     indent=1), len(sites), "sites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
