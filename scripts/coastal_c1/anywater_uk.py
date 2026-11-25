"""ANYWATER-UK (docs/ANYWATER-UK-STATEMENT-2026-11.md): England's frozen C1 scored on Welsh and Northern Irish samples.

    uv run python scripts/coastal_c1/anywater_uk.py fetch --out "$HOME/dipcast-scratch/anywater-uk"
    # convert rain for <out>/sites.csv with scripts/era5land/to_cells.py --points ... --max-step 3
    uv run python scripts/coastal_c1/anywater_uk.py score --out "$HOME/dipcast-scratch/anywater-uk" \\
        --rain "$HOME/dipcast-scratch/anywater-uk/cache/rain" --result docs/coastal-c1/anywater_uk.json

`fetch` sends about 30 requests (NRW's catalogue and in-season samples, DAERA's layer and yearly tables), counted
against caps. `score` makes no request and refuses unless C1's own read is "supported on unseen seasons".
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))
import c1  # noqa: E402

FROZEN = REPO / "data" / "research" / "coastal" / "c1_frozen.v1.json"
FROZEN_SHA = "90b390ba251c5ddb48ac9783902dfa1480cf822261f0edfd7e4736c3d99515e6"
C1_RESULT = REPO / "docs" / "coastal-c1" / "result.json"
SEED = 20261125
RESAMPLES = 2000
MIN_ROWS = 20
PASS_ABOVE = 0.10


# ------------------------------------------------------------------ fetch
def fetch(out: Path) -> int:
    import httpx

    import export_typical_readings as ex
    from dipcast import northern_ireland as ni
    from dipcast import wales as w

    out.mkdir(parents=True, exist_ok=True)
    b = ex.Budget(130)
    sites = []
    with httpx.Client(headers=ex.UA, timeout=60) as c:
        page = 0
        while True:   # NRW's catalogue with each water's sampling point
            res = b.call(c, "GET", w.SITES, params={"_pageSize": 500, "_page": page}).json()
            items = res["result"].get("items") or []
            for it in items:
                sp = it.get("samplingPoint") or {}
                sites.append({"id": it.get("eubwidNotation"), "nation": "wales", "lat": sp.get("lat"),
                              "lon": sp.get("long")})
            if len(items) < 500:
                break
            page += 1
        feats = b.call(c, "GET", ni.LAYER, params={"where": "1=1", "outFields": ni.FIELDS, "f": "json",
                                                    "returnGeometry": "true", "outSR": 4326}).json()["features"]
    for s in ni.parse(feats):
        sites.append({"id": s["id"], "nation": "northern_ireland", "lat": s.get("lat"), "lon": s.get("lon")})
    wal, wal_kinds, wal_meta = ex.wales(b)
    nir, nir_kinds, nir_meta = ex.northern_ireland(ex.Budget(10))
    kinds = {**wal_kinds, **nir_kinds}
    st = pd.DataFrame(sites).dropna(subset=["id"]).drop_duplicates("id")
    st["kind"] = st["id"].map(kinds)
    st.to_csv(out / "sites.csv", index=False)
    rows = [{"site_id": sid, "t": x["t"], "ecoli": x["ecoli"], "q": x.get("q")}
            for by in (wal, nir) for sid, smp in by.items() for x in smp.values()]
    (out / "samples.json").write_text(json.dumps({"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                                                  "requests": b.n if hasattr(b, "n") else None,
                                                  "wales": wal_meta, "northern_ireland": nir_meta, "rows": rows}))
    print(f"{len(st)} sites, {len(rows)} samples")
    return 0


# ------------------------------------------------------------------ score
def ranks_within(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("site_id")[col].rank(method="average")


def site_rhos(df: pd.DataFrame, col: str) -> pd.Series:
    out = {}
    for sid, g in df.groupby("site_id"):
        if g[col].nunique() < 2 or g["count_rank"].nunique() < 2:
            continue
        out[sid] = spearmanr(g[col], g["count_rank"]).statistic
    return pd.Series(out, dtype=float)


def boot(df: pd.DataFrame, cols: list[str], rng) -> dict[str, np.ndarray]:
    """Two-way bootstrap of the mean within-site rho (sites and seasons drawn independently); a drawn season set is
    applied inside each drawn site, and a site with too few rows in the draw drops out of that draw."""
    sites = df["site_id"].unique()
    seasons = np.sort(df["year"].unique())
    groups = {(s, y): g for (s, y), g in df.groupby(["site_id", "year"])}
    out = {c: np.empty(RESAMPLES) for c in cols}
    for b in range(RESAMPLES):
        ds = rng.choice(sites, len(sites))
        dy = rng.choice(seasons, len(seasons))
        vals = {c: [] for c in cols}
        for s in ds:
            parts = [groups[(s, y)] for y in dy if (s, y) in groups]
            if not parts:
                continue
            g = pd.concat(parts)
            if len(g) < 5 or g["count_rank"].nunique() < 2:
                continue
            for c in cols:
                if g[c].nunique() >= 2:
                    vals[c].append(spearmanr(g[c], g["count_rank"]).statistic)
        for c in cols:
            out[c][b] = np.nanmean(vals[c]) if vals[c] else np.nan
    return out


def score(out: Path, rain_dir: Path, result: Path) -> int:
    verdict = json.loads(C1_RESULT.read_text()).get("verdict") if C1_RESULT.exists() else None
    if verdict != "supported on unseen seasons":
        print(f"Gate shut: C1's own read is {verdict!r}. Nothing scored.")
        return 2
    if c1.sha256(FROZEN) != FROZEN_SHA:
        print("Frozen file hash differs. Stopped.")
        return 3
    frozen = json.loads(FROZEN.read_text())
    st = pd.read_csv(out / "sites.csv")
    st = st[st["kind"].isin(["coast", "estuary"]) & st["lat"].notna()]
    raw = json.loads((out / "samples.json").read_text())["rows"]
    df = pd.DataFrame(raw)
    df = df[df["site_id"].isin(st["id"])].copy()
    date_only = df["t"].str.len() == 10
    t = df["t"].where(~date_only, df["t"] + "T12:00:00")     # amendment 1: a date with no time is 12:00 UK time
    df["time"] = [pd.Timestamp(x).tz_localize("Europe/London") if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x)
                  for x in t]
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["date_only"] = date_only
    df["year"], df["month"] = df["time"].dt.tz_convert("Europe/London").dt.year, df["time"].dt.tz_convert("Europe/London").dt.month
    df = df[df["month"].isin(c1.MONTHS)]
    df["ecoli_qual"] = df["q"].fillna("=")
    n = df.groupby("site_id").size()
    df = df[df["site_id"].isin(n[n >= MIN_ROWS].index)].sort_values(["site_id", "time"]).reset_index(drop=True)
    pos = st.set_index("id")
    df["cell"] = [tuple(c1.snap([pos.at[s, "lat"], pos.at[s, "lon"]])) for s in df["site_id"]]
    hours = frozen["window"]["hours"]
    for h in hours:
        df[f"r{h}"] = np.nan
    for cell, g in df.groupby("cell"):
        rain = c1.load_cell(rain_dir, (float(cell[0]), float(cell[1])), tuple(range(2023, 2027)))
        for h in hours:
            df.loc[g.index, f"r{h}"] = c1.window_sums(g["time"], rain, h)[0]
    cov = np.all([df[f"r{h}"].notna() for h in hours], axis=0)
    info = {"rows": len(df), "covered": int(cov.sum()), "sites": int(df["site_id"].nunique()),
            "rows_date_only_at_noon": int(df["date_only"].sum()),
            "by_nation": {k: int(v) for k, v in df["site_id"].map(pos["nation"]).value_counts().items()}}
    df = df[cov].reset_index(drop=True)
    last = c1.last_sample(df)
    tab = frozen["site_tables"]["over_500"]
    rate = np.full(len(df), tab["p0"])          # every site is new to the frozen model
    mod = frozen["models"]["over_500"]
    month = df["month"].to_numpy()
    rainx = df[[f"r{h}" for h in hours]].to_numpy()
    df["C1"] = c1.predict(mod["C1"], c1.design(rate, month, last, rainx))
    df["C0"] = c1.predict(mod["C0"], c1.design(rate, month, last, None))
    df["month_R"] = c1.predict(mod["R"], c1.design(rate, month, None, None))
    # a '<' result ranks below every count at its value; '>' above
    df["count_key"] = df["ecoli"] + df["ecoli_qual"].map({"<": -0.5, ">": 0.5}).fillna(0.0)
    df["count_rank"] = ranks_within(df, "count_key")
    df["over_500"] = c1.over(df["ecoli"], df["ecoli_qual"], 500).astype(int)
    df["nation"] = df["site_id"].map(pos["nation"])
    cols = ["C1", "C0", "month_R"]
    rng = np.random.default_rng(SEED)
    res = {"read_at": datetime.now(UTC).isoformat(timespec="seconds"), "info": info,
           "over_500": int(df["over_500"].sum())}
    for name, part in [("pooled", df), *[(k, g) for k, g in df.groupby("nation")]]:
        point = {c: float(site_rhos(part, c).mean()) for c in cols}
        bs = boot(part, cols, rng)
        diff = {"C1_minus_C0": bs["C1"] - bs["C0"], "C1_minus_month": bs["C1"] - bs["month_R"]}
        res[name] = {"rows": len(part), "sites": int(part["site_id"].nunique()), "mean_within_site_rho": point,
                     "interval": {c: c1_ci(bs[c]) for c in cols},
                     "differences": {k: {"value": point["C1"] - point["C0" if k == "C1_minus_C0" else "month_R"],
                                         "interval": c1_ci(v)} for k, v in diff.items()},
                     "brier_over_500": {c: c1.brier(part[c].to_numpy(), part["over_500"].to_numpy()) for c in cols}}
    lo = res["pooled"]["interval"]["C1"][0]
    res["verdict"] = "pass" if lo > PASS_ABOVE else "fail"
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_bytes(c1.canonical(res))
    print(json.dumps({"verdict": res["verdict"], "pooled": res["pooled"]["mean_within_site_rho"],
                      "interval": res["pooled"]["interval"]}, indent=1))
    return 0


def c1_ci(x: np.ndarray) -> list[float]:
    x = x[np.isfinite(x)]
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["fetch", "score"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rain", type=Path)
    ap.add_argument("--result", type=Path, default=REPO / "docs" / "coastal-c1" / "anywater_uk.json")
    a = ap.parse_args(argv)
    return fetch(a.out) if a.stage == "fetch" else score(a.out, a.rain, a.result)


if __name__ == "__main__":
    sys.exit(main())
