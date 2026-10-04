"""Make the frozen inputs of the May-September 2027 evaluation (docs/PREREGISTRATION-2027.md):
data/eval2027/sites.csv, the eligible overflows and bathing waters, and data/eval2027/climatology.json,
the training-only reference forecasts. Run once, on 4 October 2026; the outputs are committed and
their SHA-256 recorded in the protocol. Rerunning on the same inputs writes the same bytes.

Inputs, none fetched here:

* --spots: a published spots.json (the 4 Oct 2026 15:29 BST build's), for the spot list and each
  spot's kind (river or lake).
* --upstream: the same build's data/upstream/<spot id>.json files, one per spot with anything
  upstream: every overflow within 60 km upstream along the river network, with `has_live`.
* data/raw/bathing_waters_inland.json: the 38 inland designated bathing waters the live E. coli
  scorer reads (forecast_log._bathing_sites).
* --edm: United Utilities' event history 2023-2025 (data/processed/edm_events.parquet in a training
  checkout; git-ignored, made by the training pipeline from Stream's EDM layers), for the spill
  forecasts' month factor.
* --ecoli-samples: the EA samples at the 38 bathing waters, 2023-2026 (data/processed/
  ecoli_validation_rows.parquet in a training checkout; git-ignored, made by
  scripts/validate_ecoli.py), for each site's share of samples over 900.
* data/processed/ecoli_model.json: the E. coli model's rate over 900 by water type, which the live
  scorer uses as its baseline.

    uv run python scripts/make_eval2027.py --spots <spots.json> --upstream <dir> \\
        --edm <edm_events.parquet> --ecoli-samples <ecoli_validation_rows.parquet>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "eval2027"
BATHING = ROOT / "data" / "raw" / "bathing_waters_inland.json"
ECOLI_MODEL = ROOT / "data" / "processed" / "ecoli_model.json"
LOCAL_TZ = "Europe/London"
ECOLI_THRESHOLD = 900          # E. coli per 100 ml: forecast_log.verify_ecoli's y = ecoli > 900
EDM_YEARS = (2023, 2024, 2025)  # the spill model's training years (United Utilities)
CLIM_YEARS = (2023, 2026)       # E. coli samples before the evaluation season, first and last year
SITE_COLUMNS = ["unit", "id", "name", "company", "water", "spots"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dir_sha256(files: list[Path]) -> str:
    """One hash for a set of files: SHA-256 of the lines '<name> <sha256>\\n', sorted by name."""
    lines = "".join(f"{f.name} {sha256(f)}\n" for f in sorted(files, key=lambda f: f.name))
    return hashlib.sha256(lines.encode()).hexdigest()


def water_of(kinds: set[str]) -> str:
    """river, lake or both: the kinds of the spots an overflow can reach."""
    return "both" if len(kinds) > 1 else next(iter(kinds))


def eligible_overflows(spots: list[dict], upstream: dict[str, list[dict]]) -> pd.DataFrame:
    """Every overflow with a live feed (`has_live`) upstream of at least one listed spot, once,
    with the spots it reaches. Overflows with no live feed are forecast but cannot be scored."""
    kind = {s["id"]: s["kind"] for s in spots}
    rows: dict[str, dict] = {}
    for sid, ovs in upstream.items():
        for o in ovs:
            if not o.get("has_live"):
                continue
            r = rows.setdefault(o["site_id"], {"name": o.get("site_name") or "", "company": o.get("company") or "",
                                               "spots": set(), "kinds": set()})
            r["spots"].add(sid)
            r["kinds"].add(kind[sid])
    out = pd.DataFrame([{"unit": "overflow", "id": k, "name": v["name"], "company": v["company"],
                         "water": water_of(v["kinds"]), "spots": ";".join(sorted(v["spots"]))} for k, v in rows.items()],
                       columns=SITE_COLUMNS)
    return out.sort_values("id", kind="stable").reset_index(drop=True)


def eligible_bathing_waters(spots: list[dict], bathing: list[dict]) -> pd.DataFrame:
    """The inland designated bathing waters, each of which must be a listed spot (id 'bw-' + the EA id)."""
    listed = {s["id"] for s in spots}
    missing = [b["id"] for b in bathing if f"bw-{b['id']}" not in listed]
    if missing:
        raise SystemExit(f"bathing waters with no spot: {missing}")
    out = pd.DataFrame([{"unit": "bathing_water", "id": b["id"], "name": b["name"], "company": b.get("undertaker") or "",
                         "water": b["kind"], "spots": f"bw-{b['id']}"} for b in bathing], columns=SITE_COLUMNS)
    return out.sort_values("id", kind="stable").reset_index(drop=True)


def spill_days_local(events: pd.DataFrame, max_span_days: int = 60) -> pd.DataFrame:
    """(site_id, local day) with at least one spill, as forecast_log.observed_spill_days counts a
    live spill: every Europe/London day from an event's start to its end, spans capped at 60 days."""
    ev = events.dropna(subset=["event_start"])
    start = pd.to_datetime(ev["event_start"], utc=True).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    end = pd.to_datetime(ev["event_end"], utc=True).fillna(pd.to_datetime(ev["event_start"], utc=True))
    end = end.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    d0, d1 = start.dt.floor("D"), end.dt.floor("D")
    n = ((d1 - d0).dt.days.clip(lower=0, upper=max_span_days) + 1).to_numpy()
    base = np.repeat(d0.to_numpy().astype("datetime64[D]"), n)
    offs = np.concatenate([np.arange(k) for k in n]) if len(n) else np.array([], dtype=int)
    out = pd.DataFrame({"site_id": np.repeat(ev["site_id"].to_numpy(), n), "day": base + offs.astype("timedelta64[D]")})
    return out.drop_duplicates()


def month_factors(events: pd.DataFrame, years: tuple[int, ...] = EDM_YEARS) -> dict:
    """How much likelier a spill-day is in each calendar month than on an average day of the year,
    pooled over every overflow in the event history: (share of spill-days in month m) / (share of
    calendar days in month m), over `years`. A factor of 1.2 for June means June had 20% more
    spill-days per day than the year's average. Over a year the factors average 1 (by days)."""
    sd = spill_days_local(events)
    day = pd.to_datetime(sd["day"])
    sd = sd[day.dt.year.isin(years)]
    by_month = pd.to_datetime(sd["day"]).dt.month.value_counts().reindex(range(1, 13), fill_value=0)
    cal = pd.Series(pd.date_range(f"{min(years)}-01-01", f"{max(years)}-12-31", freq="D").month).value_counts().reindex(range(1, 13))
    f = (by_month / by_month.sum()) / (cal / cal.sum())
    return {"factor": {str(m): round(float(f[m]), 4) for m in range(1, 13)},
            "spill_days": {str(m): int(by_month[m]) for m in range(1, 13)},
            "calendar_days": {str(m): int(cal[m]) for m in range(1, 13)},
            "n_overflows": int(sd["site_id"].nunique()), "years": list(years)}


def ecoli_site_rates(samples: pd.DataFrame, sites: pd.DataFrame, years: tuple[int, int] = CLIM_YEARS) -> dict:
    """Each bathing water's share of samples over the threshold in `years` (all in May-September,
    when the EA samples), smoothed as (over + 0.5) / (n + 1) so that a site with none over still
    gets a chance above 0. A site with no samples gets null and the evaluation uses its type's rate."""
    t = pd.to_datetime(samples["sample_time"], utc=True).dt.tz_convert(LOCAL_TZ)
    s = samples[(t.dt.year >= years[0]) & (t.dt.year <= years[1]) & samples["ecoli"].notna()]
    months = sorted(int(m) for m in t[s.index].dt.month.unique())
    out = {}
    for bw in sites["id"]:
        g = s[s["bw_id"] == bw]
        n, over = len(g), int((g["ecoli"] > ECOLI_THRESHOLD).sum())
        out[bw] = {"n": n, "over_900": over, "rate": round((over + 0.5) / (n + 1), 4) if n else None}
    return {"rate": out, "years": list(years), "months_seen": months}


def header(spots_path: Path, generated_at: str, up_files: list[Path], counts: dict) -> str:
    lines = [
        "SwimSignal 2027 evaluation: the frozen eligible sites (docs/PREREGISTRATION-2027.md). Made by",
        "scripts/make_eval2027.py on 4 October 2026. Do not edit: the protocol records this file's SHA-256.",
        "unit: overflow (spill forecasts, scored against the water company's live feed) or bathing_water (the",
        "E. coli estimate, scored against Environment Agency samples). id: the company's overflow id as in the live",
        "feed and data/verification_live.csv, or the EA bathing-water id. company: the water company (for a bathing",
        "water, the EA's named sewerage undertaker). water: the kind of spot it reaches: river, lake or both.",
        "spots: the listed spots it reaches (overflows) or is (bathing waters), separated by ';'.",
        f"Inputs: spots.json generated_at {generated_at}, SHA-256 {sha256(spots_path)};",
        f"{len(up_files)} upstream/<spot id>.json files from the same build, combined SHA-256 {dir_sha256(up_files)};",
        f"data/raw/bathing_waters_inland.json SHA-256 {sha256(BATHING)}.",
        f"Counts: {counts['overflow']} overflows, {counts['bathing_water']} bathing waters.",
        "Lines that start with # are notes: skip them when reading. Some names hold a '#', so do not read the",
        "file with pandas' comment='#', which would cut those lines short; evaluate_2027.read_published skips them.",
    ]
    return "".join(f"# {x}\n" for x in lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spots", type=Path, required=True)
    ap.add_argument("--upstream", type=Path, required=True)
    ap.add_argument("--edm", type=Path, required=True)
    ap.add_argument("--ecoli-samples", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)

    sj = json.loads(a.spots.read_text())
    spots = sj["spots"]
    up_files = sorted(a.upstream.glob("*.json"), key=lambda f: f.name)
    upstream = {}
    for f in up_files:
        d = json.loads(f.read_text())
        if d.get("generated_at") != sj["generated_at"]:
            raise SystemExit(f"{f.name} is from {d.get('generated_at')}, spots.json from {sj['generated_at']}")
        upstream[d["id"]] = d["overflows"]
    unknown = sorted(set(upstream) - {s["id"] for s in spots})
    if unknown:
        raise SystemExit(f"upstream files for spots not in spots.json: {unknown}")
    bathing = json.loads(BATHING.read_text())
    ov = eligible_overflows(spots, upstream)
    bw = eligible_bathing_waters(spots, bathing)
    sites = pd.concat([ov, bw], ignore_index=True)
    a.out.mkdir(parents=True, exist_ok=True)
    counts = sites["unit"].value_counts().to_dict()
    with open(a.out / "sites.csv", "w", newline="") as fh:
        fh.write(header(a.spots, sj["generated_at"], up_files, counts))
        sites.to_csv(fh, index=False, lineterminator="\n")

    meta = json.loads(ECOLI_MODEL.read_text())["meta"]
    clim = {
        "about": ("Training-only reference forecasts for the 2027 evaluation (docs/PREREGISTRATION-2027.md). "
                  "Made by scripts/make_eval2027.py on 4 October 2026 from data before 2027. Do not edit."),
        "spill_month": {**month_factors(pd.read_parquet(a.edm)),
                        "use": "season/site climatology = clip(climatology column x factor[month of target day], 0.001, 0.95)",
                        "source": "United Utilities event history (Stream EDM layers, CC BY 4.0), the spill model's training data",
                        "input_sha256": sha256(a.edm)},
        "ecoli_site": {**ecoli_site_rates(pd.read_parquet(a.ecoli_samples), bw),
                       "threshold": ECOLI_THRESHOLD, "smoothing": "(over + 0.5) / (n + 1)",
                       "source": "Environment Agency bathing-water samples, OGL v3.0",
                       "input_sha256": sha256(a.ecoli_samples)},
        "ecoli_type": {"rate": {k: float(v) for k, v in meta["base_rate_by_type"].items()},
                       "source": "data/processed/ecoli_model.json meta.base_rate_by_type: the live scorer's baseline",
                       "input_sha256": sha256(ECOLI_MODEL)},
    }
    (a.out / "climatology.json").write_text(json.dumps(clim, indent=1, sort_keys=False) + "\n")
    print(f"sites.csv: {counts}; overflows by water {ov['water'].value_counts().to_dict()}; "
          f"bathing waters by water {bw['water'].value_counts().to_dict()}")
    print("month factors:", clim["spill_month"]["factor"])
    print("SHA-256 sites.csv", sha256(a.out / "sites.csv"), "climatology.json", sha256(a.out / "climatology.json"))


if __name__ == "__main__":
    main()
