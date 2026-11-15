"""docs/RADAR-ISSUE-HOUR-TEST-2026-11.md: when each Met Office radar composite reached the AWS bucket.

    latency.py <first day> <last day> <out dir> [--max-requests N]

Lists radar/YYYY/MM/DD/ for each UTC day (one request a day, more only if a listing is paged) and keeps, for every
composite, the time in its name, the bucket's LastModified and its size. Writes <out dir>/radar_publish_times.csv and
<out dir>/latency.json (the summary). Reads listings only: no composite is downloaded. Standard library only, so it
imports no build or research code. A day already in the CSV is skipped, so a stopped run resumes.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BUCKET = "https://met-office-radar-obs-data.s3.amazonaws.com/"
KEY_RE = re.compile(r"radar/\d{4}/\d{2}/\d{2}/(\d{12})_ODIM_ng_radar_rainrate_composite_1km_UK\.h5$")
PAUSE_S, TRIES, TIMEOUT_S = 0.2, 4, 30
UTC = dt.timezone.utc


def list_day(day: dt.date, budget: list[int]) -> list[tuple[str, str, int]]:
    out, token = [], None
    while True:
        if budget[0] <= 0:
            raise SystemExit("request cap reached; stopped")
        q = {"list-type": "2", "prefix": f"radar/{day:%Y/%m/%d}/"}
        if token:
            q["continuation-token"] = token
        url = BUCKET + "?" + urllib.parse.urlencode(q)
        for k in range(TRIES):
            budget[0] -= 1
            try:
                with urllib.request.urlopen(url, timeout=TIMEOUT_S) as r:
                    body = r.read()
                break
            except OSError as e:
                if k + 1 == TRIES or budget[0] <= 0:
                    raise SystemExit(f"{url}: {e!r}; stopped") from e
                time.sleep(2 * 2 ** k)
        root = ET.fromstring(body)
        ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        for el in root.iterfind(f"{ns}Contents"):
            m = KEY_RE.match(el.findtext(f"{ns}Key", ""))
            if m:
                out.append((m[1], el.findtext(f"{ns}LastModified", ""), int(el.findtext(f"{ns}Size", "0"))))
        token = root.findtext(f"{ns}NextContinuationToken")
        time.sleep(PAUSE_S)
        if not token:
            return out


def pct(v: list[float], q: float) -> float:
    return v[min(len(v) - 1, int(q * len(v)))]


def main(first: str, last: str, out_dir: str, *rest: str) -> None:
    cap = int(rest[rest.index("--max-requests") + 1]) if "--max-requests" in rest else 800
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "radar_publish_times.csv"
    done = set()
    if path.exists():
        with path.open() as f:
            done = {r["scan_time"][:8] for r in csv.DictReader(f)}
    d0, d1 = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    budget, used0 = [cap], cap
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["scan_time", "last_modified", "size"])
        day = d0
        while day <= d1:
            if f"{day:%Y%m%d}" not in done:
                for row in list_day(day, budget):
                    w.writerow(row)
                f.flush()
            day += dt.timedelta(days=1)
    rows = []
    with path.open() as f:
        for r in csv.DictReader(f):
            t = dt.datetime.strptime(r["scan_time"], "%Y%m%d%H%M").replace(tzinfo=UTC)
            lm = dt.datetime.fromisoformat(r["last_modified"].replace("Z", "+00:00"))
            rows.append((t, (lm - t).total_seconds() / 60))
    lat = sorted(x for _, x in rows)
    days = (d1 - d0).days + 1
    by_year = {}
    for t, x in rows:
        by_year.setdefault(t.year, []).append(x)
    res = {"first_day": first, "last_day": last, "requests_this_run": used0 - budget[0], "composites": len(rows),
           "expected_at_96_a_day": days * 96,
           "minutes_after_scan_time": {"min": lat[0], "median": pct(lat, 0.5), "p95": pct(lat, 0.95), "p99": pct(lat, 0.99),
                                       "p99.9": pct(lat, 0.999), "max": lat[-1]},
           "share_later_than_minutes": {str(m): sum(x > m for x in lat) / len(lat) for m in (15, 20, 30, 45, 60, 120, 360, 1440)},
           "by_year": {str(y): {"composites": len(v), "median": pct(sorted(v), 0.5), "p99": pct(sorted(v), 0.99),
                                "share_later_than_60": sum(x > 60 for x in v) / len(v)} for y, v in sorted(by_year.items())}}
    (out / "latency.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
