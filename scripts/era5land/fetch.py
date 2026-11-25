"""Bulk ERA5-Land hourly rain from the Copernicus Climate Data Store (docs/ERA5-LAND-BULK-RAIN-2026-11.md), from this
Mac, never from CI. It sends no Open-Meteo request and spends none of the site's Open-Meteo ration.

    uv run python scripts/era5land/fetch.py --out "$HOME/dipcast-scratch/era5land" --dry-run
    uv run --extra era5 --with "cdsapi>=0.7.7" python scripts/era5land/fetch.py --out "$HOME/dipcast-scratch/era5land"
    uv run python scripts/era5land/fetch.py --out "$HOME/dipcast-scratch/era5land" --status

What it asks for: dataset reanalysis-era5-land, variable total_precipitation, every hour, as NetCDF, over the area
(default 61.0 N, 8.3 W, 49.8 S, 2.0 E: Great Britain and Northern Ireland), one request per month. By default from
January 1990 to the month three months before today, newest first, so the years the match check needs come first.

The rules:
  * --dry-run and --status send nothing and need no CDS key.
  * A month whose file is on disk is never asked for again, so the same command resumes. A file is written as
    <name>.part and renamed only when the download is whole and starts like NetCDF (or a zip of it).
  * The first failure stops the run: a missing licence or key fails every month alike, so going on would only repeat it.
    The CDS client retries passing errors itself.
  * Ceilings: --max-requests, --max-gb (bytes downloaded in this run), --max-hours (this run's wall time), and 2 GB of
    free disk kept. Reaching one stops the run cleanly; run it again later to carry on.
  * Every request is one line of <out>/ledger.jsonl: the request, start time, seconds, bytes, SHA-256, outcome.
  * --out must not be inside a data/cache folder: the shared caches are read-only for this work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import era5land_core as core  # noqa: E402

# Exit codes, so the record's steps can say what each means.
OK, NO_KEY, FAILED, CEILING, BAD_OUT = 0, 2, 3, 4, 5
MIN_FREE_BYTES = 2 * 1024 ** 3
DEFAULT_MAX_REQUESTS = 480      # every month from 1990 to 2026 is 440
DEFAULT_MAX_GB = 30.0
DEFAULT_MAX_HOURS = 24.0
# Minutes a request may take, for the dry run's time range only. Not measured: the CDS queue varies. The ledger
# measures the real figure and --status projects from it.
ASSUMED_MINUTES = (3.0, 20.0)
NEW_CDS_URL = "https://cds.climate.copernicus.eu/api"


# ------------------------------------------------------------------ setup checks
def cds_config(env: dict | None = None, home: Path | None = None) -> tuple[str | None, str | None, str]:
    """(url, key, where) as the cdsapi client would find them: CDSAPI_URL and CDSAPI_KEY, else the file named by
    CDSAPI_RC, else ~/.cdsapirc. The key is returned only so it can be checked, never printed."""
    env = os.environ if env is None else env
    url, key = env.get("CDSAPI_URL"), env.get("CDSAPI_KEY")
    if url and key:
        return url, key, "environment"
    rc = Path(env.get("CDSAPI_RC", str((home or Path.home()) / ".cdsapirc"))).expanduser()
    if not rc.exists():
        return url, key, str(rc)
    for line in rc.read_text().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip() == "url" and not url:
                url = v.strip()
            elif k.strip() == "key" and not key:
                key = v.strip()
    return url, key, str(rc)


def config_problem(url: str | None, key: str | None, where: str) -> str | None:
    """None when the settings look like the new CDS's, else what to fix. Nothing here contacts the CDS."""
    if not url or not key:
        return (f"No CDS key found ({where}). Make {Path.home() / '.cdsapirc'} with two lines:\n"
                f"url: {NEW_CDS_URL}\nkey: <your Personal Access Token from your CDS profile page>")
    if url.rstrip("/").endswith("/api/v2"):
        return f"{where}: url ends /api/v2, the old CDS. Use {NEW_CDS_URL}"
    if ":" in key:
        return (f"{where}: the key has a colon (UID:KEY), the old CDS's form. The new CDS uses the Personal Access "
                "Token from your profile page, with no colon.")
    return None


# ------------------------------------------------------------------ the ledger
def ledger_rows(out: Path) -> list[dict]:
    f = out / "ledger.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def _log(out: Path, row: dict) -> None:
    with (out / "ledger.jsonl").open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def classify(error: str) -> tuple[str, str]:
    """(outcome, hint) for a failed request, from the error text."""
    e = error.lower()
    if "licence" in e or "license" in e or "terms" in e:
        return "licence", ("Accept the ERA5-Land licence: open the dataset's page on the CDS, Download tab, "
                           "'Terms of use', and accept. Then run again.")
    if "401" in e or "unauthori" in e or "authentication" in e or "invalid token" in e:
        return "auth", f"Check the key in ~/.cdsapirc (url: {NEW_CDS_URL}, key: your Personal Access Token)."
    if "too large" in e or "cost limit" in e or "request too" in e:
        return "too_large", "The CDS refused the request size. Use a smaller --area."
    return "failed", "Read the error. Running again resumes from the first month not on disk."


# ------------------------------------------------------------------ the plan
def plan(start: str, end: str, newest_first: bool = True) -> list[str]:
    months = core.month_list(start, end)
    return months[::-1] if newest_first else months


def todo(out: Path, months: list[str]) -> list[str]:
    return [m for m in months if not core.raw_file(out, m).exists()]


def dry_run(out: Path | None, start: str, end: str, area, newest_first: bool = True) -> dict:
    months = plan(start, end, newest_first)
    left = todo(out, months) if out is not None else months
    rows, cols = core.area_points(area)
    ub = core.upper_bytes(months, area)
    lo, hi = ASSUMED_MINUTES
    return {"dataset": core.DATASET, "variable": core.VARIABLE, "area_N_W_S_E": list(area),
            "grid_rows": rows, "grid_cols": cols, "grid_points": rows * cols,
            "months": len(months), "first_request": months[0], "last_request": months[-1],
            "on_disk": len(months) - len(left), "requests_left": len(left),
            "upper_bound_gb_all_months": round(ub / 1e9, 1),
            "upper_bound_gb_per_31_day_month": round(rows * cols * 744 * 4 / 1e9, 3),
            "assumed_minutes_per_request": [lo, hi],
            "hours_one_at_a_time": [round(len(left) * lo / 60, 1), round(len(left) * hi / 60, 1)],
            "example_request": core.month_request(left[0] if left else months[0], area)}


def status(out: Path, start: str, end: str, newest_first: bool = True) -> dict:
    months = plan(start, end, newest_first)
    left = todo(out, months)
    rows = ledger_rows(out)
    ok = [r for r in rows if r.get("outcome") == "ok"]
    mean_s = sum(r["seconds"] for r in ok) / len(ok) if ok else None
    mean_b = sum(r["bytes"] for r in ok) / len(ok) if ok else None
    return {"months": len(months), "on_disk": len(months) - len(left), "left": len(left),
            "requests_logged": len(rows), "failures_logged": sum(r.get("outcome") != "ok" for r in rows),
            "last_outcome": rows[-1].get("outcome") if rows else None,
            "gb_downloaded": round(sum(r.get("bytes", 0) for r in ok) / 1e9, 3),
            "mean_minutes_per_request": round(mean_s / 60, 1) if mean_s else None,
            "mean_mb_per_month": round(mean_b / 1e6, 1) if mean_b else None,
            "projected_hours_left": round(len(left) * mean_s / 3600, 1) if mean_s else None,
            "projected_gb_left": round(len(left) * mean_b / 1e9, 1) if mean_b else None}


# ------------------------------------------------------------------ the run
def _client():
    try:
        import cdsapi
    except ImportError:
        raise SystemExit('cdsapi is not installed. Run with: uv run --extra era5 --with "cdsapi>=0.7.7" python '
                         "scripts/era5land/fetch.py ...") from None
    return cdsapi.Client()


def run(out: Path, start: str, end: str, area, newest_first: bool = True, *,
        max_requests: int = DEFAULT_MAX_REQUESTS, max_gb: float = DEFAULT_MAX_GB,
        max_hours: float = DEFAULT_MAX_HOURS, client_factory: Callable = _client,
        now: Callable[[], datetime] = lambda: datetime.now(UTC), clock: Callable[[], float] = time.monotonic,
        free_bytes: Callable[[Path], int] = lambda p: shutil.disk_usage(p).free,
        config: tuple | None = None) -> int:
    problem = core.out_ok(out)
    if problem:
        print(problem)
        return BAD_OUT
    url, key, where = config if config is not None else cds_config()
    problem = config_problem(url, key, where)
    if problem:
        print(problem)
        return NO_KEY
    out.mkdir(parents=True, exist_ok=True)
    left = todo(out, plan(start, end, newest_first))
    if not left:
        print("Every month is on disk. Nothing to do.")
        return OK
    client = client_factory()
    t_start, got_bytes, sent = clock(), 0, 0
    for month in left:
        if sent >= max_requests:
            print(f"Stopped at the request ceiling ({max_requests}). Run again to carry on.")
            return CEILING
        if got_bytes >= max_gb * 1e9:
            print(f"Stopped at the download ceiling ({max_gb} GB this run). Run again to carry on.")
            return CEILING
        if max_hours and clock() - t_start >= max_hours * 3600:
            print(f"Stopped at the time ceiling ({max_hours} h). Run again to carry on.")
            return CEILING
        if free_bytes(out) < MIN_FREE_BYTES:
            print("Stopped: under 2 GB of free disk.")
            return CEILING
        req = core.month_request(month, area)
        final = core.raw_file(out, month)
        final.parent.mkdir(parents=True, exist_ok=True)
        part = final.with_name(final.name + ".part")
        part.unlink(missing_ok=True)
        at, t0 = now(), clock()
        sent += 1
        row = {"at": at.isoformat(timespec="seconds"), "month": month, "dataset": core.DATASET, "request": req,
               "file": str(final.relative_to(out))}
        try:
            client.retrieve(core.DATASET, req, str(part))
        except Exception as e:   # the client raises plain Exceptions with the CDS's message
            outcome, hint = classify(str(e))
            row.update(outcome=outcome, seconds=round(clock() - t0, 1), bytes=0, error=str(e)[:500], hint=hint)
            _log(out, row)
            part.unlink(missing_ok=True)
            print(f"{month}: {outcome}. {hint}\nError: {str(e)[:300]}")
            return FAILED
        data = part.read_bytes() if part.exists() else b""
        kind = core.file_kind(data[:8])
        row.update(seconds=round(clock() - t0, 1), bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                   kind=kind)
        if kind not in ("netcdf4", "netcdf3", "zip"):
            row.update(outcome="bad_file", error=f"starts {data[:16]!r}")
            _log(out, row)
            part.unlink(missing_ok=True)
            print(f"{month}: the file is not NetCDF ({data[:16]!r}). Stopped.")
            return FAILED
        part.replace(final)
        got_bytes += len(data)
        row["outcome"] = "ok"
        _log(out, row)
        print(f"{month}: {len(data) / 1e6:.1f} MB in {row['seconds'] / 60:.1f} min")
    print("Every month asked for is on disk.")
    return OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="a scratch folder outside every checkout's data/cache")
    ap.add_argument("--start", default=core.FIRST_MONTH, help="first month, YYYY-MM (default %(default)s)")
    ap.add_argument("--end", default=None, help="last month, YYYY-MM (default: three months before today)")
    ap.add_argument("--area", default=",".join(str(a) for a in core.DEFAULT_AREA), help="N,W,S,E in degrees")
    ap.add_argument("--oldest-first", action="store_true", help="ask for the oldest month first")
    ap.add_argument("--dry-run", action="store_true", help="print the requests and their size; send nothing")
    ap.add_argument("--status", action="store_true", help="print progress from the ledger; send nothing")
    ap.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    ap.add_argument("--max-gb", type=float, default=DEFAULT_MAX_GB, help="downloaded in this run")
    ap.add_argument("--max-hours", type=float, default=DEFAULT_MAX_HOURS, help="this run's wall time; 0 for none")
    a = ap.parse_args(argv)
    end = a.end or core.default_end(date.today())
    area = tuple(float(x) for x in a.area.split(","))
    if len(area) != 4:
        ap.error("--area takes four numbers: N,W,S,E")
    newest = not a.oldest_first
    if a.end and a.end > core.default_end(date.today()):
        print(f"Note: months after {core.default_end(date.today())} may still be ERA5-Land-T (preliminary). A month "
              "on disk is never asked for again, so delete its file to take the final version later.")
    if a.dry_run:
        print(json.dumps(dry_run(a.out, a.start, end, area, newest), indent=1))
        return OK
    if a.status:
        print(json.dumps(status(a.out, a.start, end, newest), indent=1))
        return OK
    rc = run(a.out, a.start, end, area, newest, max_requests=a.max_requests, max_gb=a.max_gb, max_hours=a.max_hours)
    s = status(a.out, a.start, end, newest)
    print(f"On disk: {s['on_disk']} of {s['months']} months. Left: {s['left']}.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
