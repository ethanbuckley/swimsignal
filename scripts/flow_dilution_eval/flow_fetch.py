"""EA flow data for docs/FLOW-DILUTION-TEST-2026-10.md, through one capped client.

    python scripts/flow_dilution_eval/flow_fetch.py stations --cache <dir> [--fetch]
    python scripts/flow_dilution_eval/flow_fetch.py flows --cache <dir> --gauges <gauges.csv> [--fetch]
    python scripts/flow_dilution_eval/flow_fetch.py latest --cache <dir> --stations <station cache> --coverage <csv> --fetch

`stations` (outcome-blind prep, allowed before approval): the EA Hydrology flow station list and the
real-time flood-monitoring flow station list, two requests. Metadata only: no reading.
`flows` (the run, after approval): for each gauge in gauges.csv (written by score.py `map`), its daily
mean flow from REF_FROM to REF_TO (the reference flow) and its 15-minute flow for each sampling season
in SEASONS. One request each.

The caps, fixed here before any request:
- at most MAX_REQUESTS requests per run, all together; cached answers do not count;
- one request in flight, PAUSE_S apart (the EA Hydrology guidance asks for one request in flight;
  another worker may query the EA the same night, so the pause is not shortened);
- https to environment.data.gov.uk only; no Open-Meteo request at all;
- stop at the first 403, 429, 5xx, redirect or connection error, with no retry;
- every answer cached under --cache; without --fetch a missing answer stops the run;
- every request logged (UTC time, status, bytes, URL) to <cache>/requests.log.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

MAX_REQUESTS = 200           # per run; the prep used 2 (stations), the run needs about 4 a gauge
PREP_MAX_REQUESTS = 150      # the brief's cap for the outcome-blind metadata prep
PAUSE_S = 1.5
HOST = "environment.data.gov.uk"
HY = f"https://{HOST}/hydrology"
FM = f"https://{HOST}/flood-monitoring"
READINGS_LIMIT = 100_000     # the Hydrology soft limit per call; a season of 15-minute readings is about 14,700
REF_FROM, REF_TO = "2014-01-01", "2023-12-31"
SEASONS = (2024, 2025, 2026)
LATEST_MAX_REQUESTS = 12     # the lag check: one request per archive-only spot gauge (9 expected)
SEASON_FROM, SEASON_TO = "04-15", "10-01"   # May-September plus the archive lag (315 h) and the 24 h window
STOP_STATUS = (403, 429)


class CapReached(SystemExit):
    pass


class CappedClient:
    """GET JSON with a file cache, a request cap, a pause and a stop rule. `transport` is for the tests."""

    def __init__(self, cache: Path, fetch: bool, max_requests: int = MAX_REQUESTS, pause_s: float = PAUSE_S,
                 transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        self.cache, self.fetch, self.max, self.pause_s, self.sleep = Path(cache), fetch, max_requests, pause_s, sleep
        self.cache.mkdir(parents=True, exist_ok=True)
        self.n = 0
        self.http = httpx.Client(timeout=180, follow_redirects=False, transport=transport,
                                 headers={"User-Agent": "swimsignal-research (flow dilution test)"})

    def _name(self, url: str, params: dict) -> str:
        key = url + ("?" + urlencode(sorted(params.items())) if params else "")
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key.split("://", 1)[1])
        return safe[:200] + ".json"

    def get_json(self, url: str, params: dict | None = None) -> dict:
        params = params or {}
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname != HOST:
            raise SystemExit(f"refused: {url} is not https://{HOST}")
        f = self.cache / self._name(url, params)
        if f.exists():
            return json.loads(f.read_text())
        if not self.fetch:
            raise SystemExit(f"{f.name} is not cached; rerun with --fetch to request it")
        if self.n >= self.max:
            raise CapReached(f"cap of {self.max} requests reached; rerun to resume from the cache")
        if self.n:
            self.sleep(self.pause_s)
        self.n += 1
        try:
            r = self.http.get(url, params=params)
        except httpx.HTTPError as e:
            self._log("ERR", 0, url, params)
            raise SystemExit(f"{url}: {type(e).__name__}: stopping") from e
        self._log(str(r.status_code), len(r.content), url, params)
        if r.status_code in STOP_STATUS or r.status_code >= 500 or 300 <= r.status_code < 400:
            raise SystemExit(f"{url} answered {r.status_code}: stopping")
        r.raise_for_status()
        f.write_text(r.text)
        return r.json()

    def _log(self, status: str, size: int, url: str, params: dict) -> None:
        line = f"{datetime.now(UTC).isoformat(timespec='seconds')}\t{status}\t{size}\t{url}?{urlencode(params)}\n"
        with open(self.cache / "requests.log", "a") as fh:
            fh.write(line)


def stations(client: CappedClient) -> tuple[dict, dict]:
    """The Hydrology flow stations (with their measures) and the real-time flow stations. Two requests."""
    hy = client.get_json(f"{HY}/id/stations.json", {"observedProperty": "waterFlow", "_limit": 10000})
    fm = client.get_json(f"{FM}/id/stations", {"parameter": "flow", "_limit": 10000})
    return hy, fm


def measure_ids(station: dict) -> dict[str, str | None]:
    """The station's daily-mean and 15-minute flow measure ids ('...-flow-m-86400-m3s-qualified',
    '...-flow-i-900-m3s-qualified'), or None for a missing one."""
    out = {"daily": None, "q15": None}
    for m in station.get("measures") or []:
        mid = str(m.get("notation") or m.get("@id") or "").rsplit("/", 1)[-1]
        if mid.endswith("-flow-m-86400-m3s-qualified"):
            out["daily"] = mid
        elif mid.endswith("-flow-i-900-m3s-qualified"):
            out["q15"] = mid
    return out


def flows(client: CappedClient, gauges_csv: Path) -> None:
    import pandas as pd
    g = pd.read_csv(gauges_csv)
    for r in g.drop_duplicates("station").itertuples(index=False):
        if isinstance(r.daily, str):
            client.get_json(f"{HY}/id/measures/{r.daily}/readings.json",
                            {"mineq-date": REF_FROM, "maxeq-date": REF_TO, "_limit": READINGS_LIMIT})
        if isinstance(r.q15, str):
            for y in SEASONS:
                client.get_json(f"{HY}/id/measures/{r.q15}/readings.json",
                                {"mineq-date": f"{y}-{SEASON_FROM}", "maxeq-date": f"{y}-{SEASON_TO}",
                                 "_limit": READINGS_LIMIT})


def latest(client: CappedClient, station_cache: Path, coverage_csv: Path) -> list[dict]:
    """The lag check (statement, "The lag check"): each archive-only spot gauge's latest 15-minute flow reading.
    One request a gauge; the age is the request time minus the end of that reading's quarter hour."""
    import pandas as pd
    hy = json.loads(next(Path(station_cache).glob("*hydrology_id_stations*")).read_text())
    by_label = {str(st.get("label")): st for st in hy["items"]}
    cov = pd.read_csv(coverage_csv)
    out = []
    for r in cov[cov["gauge"].notna() & ~cov["realtime"].astype(bool)].drop_duplicates("gauge").itertuples():
        q15 = measure_ids(by_label[r.gauge])["q15"]
        asked = datetime.now(UTC)
        js = client.get_json(f"{HY}/id/measures/{q15}/readings.json", {"latest": ""})
        items = js.get("items") or []
        last = max((i["dateTime"] for i in items), default=None)
        age_h = None
        if last:
            end = datetime.fromisoformat(last.replace("Z", "+00:00"))
            end = (end if end.tzinfo else end.replace(tzinfo=UTC)) + pd.Timedelta(minutes=15)   # EA times are UTC
            age_h = round((asked - end).total_seconds() / 3600, 2)
        out.append({"gauge": r.gauge, "status": r.status, "q15": q15, "asked": asked.isoformat(timespec="seconds"),
                    "latest": last, "age_h": age_h})
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["stations", "flows", "latest"])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--gauges", type=Path)
    ap.add_argument("--stations", type=Path)
    ap.add_argument("--coverage", type=Path)
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args(argv)
    if a.step == "stations":
        c = CappedClient(a.cache, a.fetch, max_requests=PREP_MAX_REQUESTS)
        hy, fm = stations(c)
        print(f"hydrology flow stations: {len(hy.get('items', []))}; real-time flow stations: "
              f"{len(fm.get('items', []))}; requests made: {c.n}")
    elif a.step == "latest":
        c = CappedClient(a.cache, a.fetch, max_requests=LATEST_MAX_REQUESTS)
        print(json.dumps(latest(c, a.stations, a.coverage), indent=1))
        print(f"requests made: {c.n}", file=sys.stderr)
    else:
        c = CappedClient(a.cache, a.fetch)
        try:
            flows(c, a.gauges)
        finally:
            print(f"requests made: {c.n}", file=sys.stderr)


if __name__ == "__main__":
    main()
