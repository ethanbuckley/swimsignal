"""Past-sample histories for the Republic of Ireland and Wales (docs/SAMPLE-HISTORY-CONTRACT-v1.md): every published
lab sample at a bathing water, dated, from the official body that took it. Observations only: no forecast, no model.
Off CI, by hand, from a home connection (NRW's bathing-water service refuses GitHub's runners). Two steps:

    # 1. fetch: raw answers and a ledger into a directory outside the repo (or data/raw/... for the small Welsh one)
    uv run python scripts/export_sample_histories.py fetch ireland --raw <dir>
    uv run python scripts/export_sample_histories.py fetch wales --raw data/raw/nrw_sample_history \\
        --wqa <dir with NRW's Water Quality Archive zips: Wye and Carmarthen Bay and the Gower, 2020s and 2010s>
    # 2. export: the versioned file the site reads, from those raw answers only (no request)
    uv run python scripts/export_sample_histories.py export ireland --raw <dir>
    uv run python scripts/export_sample_histories.py export wales --raw data/raw/nrw_sample_history

Fetch rules (the brief of 13 Nov 2026): every request is sized before the run, counted against CAPS, paced PACE_S
apart and written to <raw>/ledger.jsonl with its status, bytes and SHA-256. The first answer that is not HTTP 200 stops
the fetch: nothing is retried and the export refuses a raw directory whose ledger ends in a refusal.

Ireland, sized 13 Nov 2026 15:19 UTC: 25,895 in-season and 1,034 out-of-season results, 5,000 a page, so 6 + 1 pages
and the list of waters (757 KB): 8 requests, about 11 MB, under a minute. Cap 16.
Wales: NRW's bathing-water service answers a filter by bathing water (`bwq_bathingWater.eubwidNotation`): one request
for each of the two waters (30 and 16 samples on 13 Nov). Cap 6. The Water Quality Archive is read from zips already
downloaded (DataMapWales's ShareFile folder has no plain download address): nothing is fetched for it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

from dipcast import config, sample_history as sh

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("export_sample_histories")

CAPS = {"ireland": 16, "wales": 6}
PACE_S = 2.0
EPA_PER_PAGE = 5000
NRW_SAMPLES = "https://environment.data.gov.uk/wales/bathing-waters/doc/bathing-water-quality/in-season/sample.json"


class Ledger:
    """Requests against a cap, each logged; the first answer that is not 200 stops the run."""

    def __init__(self, raw: Path, cap: int):
        self.raw, self.cap, self.n = raw, cap, 0
        self.path = raw / "ledger.jsonl"

    def get(self, c: httpx.Client, url: str, params: dict, name: str) -> bytes:
        if self.n >= self.cap:
            raise RuntimeError(f"stopped at the cap of {self.cap} requests")
        if self.n:
            time.sleep(PACE_S)
        self.n += 1
        at = datetime.now(UTC).isoformat(timespec="seconds")
        r = c.get(url, params=params, timeout=120)
        body = r.content
        entry = {"n": self.n, "at": at, "url": str(r.request.url), "status": r.status_code, "bytes": len(body),
                 "sha256": hashlib.sha256(body).hexdigest(), "file": name if r.status_code == 200 else None}
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} from {r.request.url}: stopped, nothing more fetched")
        (self.raw / name).write_bytes(body)
        log.info("%d. %s %d bytes", self.n, name, len(body))
        return body


def fetch_ireland(raw: Path) -> None:
    led = Ledger(raw, CAPS["ireland"])
    with httpx.Client(headers={"User-Agent": config.USER_AGENT}) as c:
        led.get(c, sh.EPA_LOCATIONS, {"page": 1, "per_page": EPA_PER_PAGE}, "locations.json")
        for kind, url in (("in", sh.EPA_IN_SEASON), ("out", sh.EPA_OUT_SEASON)):
            first = json.loads(led.get(c, url, {"page": 1, "per_page": EPA_PER_PAGE}, f"{kind}_p1.json"))
            pages = -(-first["count"] // EPA_PER_PAGE)
            for p in range(2, pages + 1):
                led.get(c, url, {"page": p, "per_page": EPA_PER_PAGE}, f"{kind}_p{p}.json")


def fetch_wales(raw: Path, wqa: Path) -> None:
    led = Ledger(raw, CAPS["wales"])
    with httpx.Client(headers={"User-Agent": config.USER_AGENT}) as c:
        for w in sh.WALES_WATERS:
            led.get(c, NRW_SAMPLES, {"_pageSize": 200, "bwq_bathingWater.eubwidNotation": w["bw_id"]}, f"bwq_{w['bw_id']}.json")
    # The archive's rows at the two bathing-water stations, every parameter, from the zips as downloaded.
    stations = {w["station"] for w in sh.WALES_WATERS}
    rows, header, zips = [], None, []
    for z in sorted(wqa.glob("*_Water_Quality_Archive.zip")):
        with zipfile.ZipFile(z) as zf:
            name = zf.namelist()[0]
            with zf.open(name) as f:
                for i, line in enumerate(f):
                    text = line.decode("utf-8-sig")
                    if i == 0:
                        header = header or text
                        continue
                    if text.split(",", 1)[0] in stations:
                        rows.append(text)
        zips.append({"file": z.name, "bytes": z.stat().st_size, "sha256": hashlib.sha256(z.read_bytes()).hexdigest(),
                     "csv_modified": "{:04d}-{:02d}-{:02d}".format(*zipfile.ZipFile(z).infolist()[0].date_time[:3])})
    if header is None:
        raise RuntimeError(f"no Water Quality Archive zips in {wqa}")
    (raw / "wqa_rows.csv").write_text(header + "".join(rows))
    (raw / "wqa_zips.json").write_text(json.dumps(zips, indent=1) + "\n")
    log.info("archive: %d rows at %s from %d zips", len(rows), sorted(stations), len(zips))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=("fetch", "export"))
    ap.add_argument("nation", choices=("ireland", "wales"))
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--wqa", type=Path)
    ap.add_argument("--out", type=Path, help="default: data/research/sample_history_<nation>.v1.json")
    a = ap.parse_args()
    if a.step == "fetch":
        a.raw.mkdir(parents=True, exist_ok=True)
        if any(a.raw.iterdir()):
            sys.exit(f"{a.raw} is not empty: fetch into a new directory")
        fetch_ireland(a.raw) if a.nation == "ireland" else fetch_wales(a.raw, a.wqa)
        return
    doc = sh.export_ireland(a.raw) if a.nation == "ireland" else sh.export_wales(a.raw)
    out = a.out or sh.FILES[a.nation]
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    out.write_text(text + "\n")
    log.info("%s: %d samples at %d waters, %d bytes -> %s", a.nation, doc["coverage"]["samples"],
             doc["coverage"]["waters"], len(text), out)


if __name__ == "__main__":
    main()
