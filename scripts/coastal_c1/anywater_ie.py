"""ANYWATER-IE (docs/ANYWATER-IE-STATEMENT-2026-11.md): England's frozen C1 scored on the EPA's Irish samples.

    uv run python scripts/coastal_c1/anywater_ie.py fetch --out "$HOME/dipcast-scratch/anywater-ie"
    uv run --extra era5 --with "cdsapi>=0.7.7" python scripts/era5land/fetch.py --out "$HOME/dipcast-scratch/era5land-ie" \\
        --start 2014-05 --end 2014-09 --area 55.5,-10.7,51.3,-5.9      # and so on, each year 2014 to 2026
    uv run --extra era5 python scripts/era5land/to_cells.py --out "$HOME/dipcast-scratch/era5land-ie" \\
        --cells-out "$HOME/dipcast-scratch/anywater-ie/cache/rain" --points "$HOME/dipcast-scratch/anywater-ie/sites.csv" \\
        --max-step 3
    uv run python scripts/coastal_c1/anywater_ie.py score --out "$HOME/dipcast-scratch/anywater-ie" \\
        --rain "$HOME/dipcast-scratch/anywater-ie/cache/rain"

`fetch` sends one request (the EPA's list of waters, for positions). The samples are the committed
data/research/sample_history_ireland.v1.json. `score` makes no request and refuses unless C1's own read is
"supported on unseen seasons" and the frozen file's hash matches.
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
import anywater_uk as uk  # noqa: E402
import c1  # noqa: E402

HISTORY = REPO / "data" / "research" / "sample_history_ireland.v1.json"
RESULT = REPO / "docs" / "coastal-c1" / "anywater_ie.json"
SEED = 20261127
YEARS = tuple(range(2014, 2027))
TZ = "Europe/Dublin"
COAST = ("coast", "estuary")


def fetch(out: Path) -> int:
    import httpx

    from dipcast import config
    from dipcast import ireland as ie

    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": config.USER_AGENT}, timeout=120) as c:
        body = ie._page(c, ie.LOCATIONS, 1, ie.PER_PAGE)
    if len(body["list"]) != body["count"]:
        raise SystemExit("EPA list of waters incomplete")
    items = body["list"]
    kinds = {s["id"]: s["kind"] for s in json.loads(HISTORY.read_text())["sites"]}
    rows = [{"id": s["id"], "lat": s.get("lat"), "lon": s.get("lon"), "kind": kinds.get(s["id"])}
            for s in ie.parse_locations(items)]
    pd.DataFrame(rows).to_csv(out / "sites.csv", index=False)
    print(f"1 request, {len(rows)} waters, {sum(r['lat'] is not None for r in rows)} with a position")
    return 0


def samples() -> pd.DataFrame:
    """The committed in-season rows, one per sample, timed at 12:00 Irish time (the statement's rule)."""
    rows = []
    for s in json.loads(HISTORY.read_text())["sites"]:
        for day, ec, *_ in s["in"]:
            q = ec[0] if ec[:1] in ("<", ">") else "="
            val = ec[1:] if q != "=" else ec
            try:
                rows.append({"site_id": s["id"], "kind": s["kind"], "day": day, "ecoli": float(val), "ecoli_qual": q})
            except ValueError:
                continue
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["day"] + "T12:00:00").dt.tz_localize(TZ).dt.tz_convert("UTC")
    local = df["time"].dt.tz_convert(TZ)
    df["year"], df["month"] = local.dt.year, local.dt.month
    return df[df["month"].isin(c1.MONTHS) & df["year"].isin(YEARS)]


def figures(df: pd.DataFrame, rng) -> dict:
    cols = ["C1", "C0", "month_R"]
    point = {c: float(uk.site_rhos(df, c).mean()) for c in cols}
    bs = uk.boot(df, cols, rng)
    diff = {"C1_minus_C0": bs["C1"] - bs["C0"], "C1_minus_month": bs["C1"] - bs["month_R"]}
    return {"rows": len(df), "sites": int(df["site_id"].nunique()), "over_500": int(df["over_500"].sum()),
            "mean_within_site_rho": point, "interval": {c: uk.c1_ci(bs[c]) for c in cols},
            "differences": {k: {"value": point["C1"] - point["C0" if k == "C1_minus_C0" else "month_R"],
                                "interval": uk.c1_ci(v)} for k, v in diff.items()},
            "brier_over_500": {c: c1.brier(df[c].to_numpy(), df["over_500"].to_numpy()) for c in cols}}


def score(out: Path, rain_dir: Path, result: Path) -> int:
    verdict = json.loads(uk.C1_RESULT.read_text()).get("verdict") if uk.C1_RESULT.exists() else None
    if verdict != "supported on unseen seasons":
        print(f"Gate shut: C1's own read is {verdict!r}. Nothing scored.")
        return 2
    if c1.sha256(uk.FROZEN) != uk.FROZEN_SHA:
        print("Frozen file hash differs. Stopped.")
        return 3
    if result.exists():
        print(f"{result} exists: this test is scored once. Stopped.")
        return 4
    frozen = json.loads(uk.FROZEN.read_text())
    pos = pd.read_csv(out / "sites.csv").dropna(subset=["lat", "lon"]).set_index("id")
    df = samples()
    df = df[df["site_id"].isin(pos.index)]
    n = df.groupby("site_id").size()
    df = df[df["site_id"].isin(n[n >= uk.MIN_ROWS].index)].sort_values(["site_id", "time"]).reset_index(drop=True)
    df["cell"] = [tuple(c1.snap([pos.at[s, "lat"], pos.at[s, "lon"]])) for s in df["site_id"]]
    hours = frozen["window"]["hours"]
    for h in hours:
        df[f"r{h}"] = np.nan
    for cell, g in df.groupby("cell"):
        rain = c1.load_cell(rain_dir, (float(cell[0]), float(cell[1])), YEARS)
        for h in hours:
            df.loc[g.index, f"r{h}"] = c1.window_sums(g["time"], rain, h)[0]
    cov = np.all([df[f"r{h}"].notna() for h in hours], axis=0)
    info = {"rows": len(df), "covered": int(cov.sum()), "sites": int(df["site_id"].nunique()),
            "rows_by_kind": {k: int(v) for k, v in df["kind"].value_counts().items()}}
    df = df[cov].reset_index(drop=True)
    last = c1.last_sample(df)
    tab = frozen["site_tables"]["over_500"]
    rate = np.full(len(df), tab["p0"])
    mod = frozen["models"]["over_500"]
    month = df["month"].to_numpy()
    rainx = df[[f"r{h}" for h in hours]].to_numpy()
    df["C1"] = c1.predict(mod["C1"], c1.design(rate, month, last, rainx))
    df["C0"] = c1.predict(mod["C0"], c1.design(rate, month, last, None))
    df["month_R"] = c1.predict(mod["R"], c1.design(rate, month, None, None))
    df["count_key"] = df["ecoli"] + df["ecoli_qual"].map({"<": -0.5, ">": 0.5}).fillna(0.0)
    df["count_rank"] = uk.ranks_within(df, "count_key")
    df["over_500"] = c1.over(df["ecoli"], df["ecoli_qual"], 500).astype(int)
    rng = np.random.default_rng(SEED)
    coast = df[df["kind"].isin(COAST)]
    res = {"read_at": datetime.now(UTC).isoformat(timespec="seconds"), "info": info, "seed": SEED,
           "coast": figures(coast, rng)}
    res["verdict"] = "pass" if res["coast"]["interval"]["C1"][0] > uk.PASS_ABOVE else "fail"
    res["reported"] = {"coast_2014_2021": figures(coast[coast["year"] <= 2021], rng),
                       "coast_2022_2026": figures(coast[coast["year"] >= 2022], rng)}
    inland = df[~df["kind"].isin(COAST)]
    if inland["site_id"].nunique() >= 3:
        res["reported"]["inland"] = figures(inland, rng)
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_bytes(c1.canonical(res))
    print(json.dumps({"verdict": res["verdict"], "coast": {k: res["coast"][k] for k in
                                                          ("rows", "sites", "mean_within_site_rho", "interval")}},
                     indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["fetch", "score"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rain", type=Path)
    ap.add_argument("--result", type=Path, default=RESULT)
    a = ap.parse_args(argv)
    return fetch(a.out) if a.stage == "fetch" else score(a.out, a.rain, a.result)


if __name__ == "__main__":
    sys.exit(main())
