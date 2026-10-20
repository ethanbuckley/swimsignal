"""Write tests/fixtures/briefings/before.json and after.json for tests/test_briefing.py: two builds' data
for the example session's two spots (session.toml), keyed by the live file each part comes from.

    python3 tests/fixtures/briefings/make_fixtures.py <folder with spots.json, spots-lite.json, verification.json, alerts.json>

before.json is one live build (20 Oct 2026, 18:00), cut to the two spots, each with its first three
overflows, and to the verification file's live scores. after.json is made up from it: a build five
hours later with a commit, in which, for 22 October, the main spot goes from "High risk: rated poor" to
"Very high risk: sewage spills", one overflow upstream starts discharging, one record on Yorkshire
Water's feed stops updating and a new EA lab sample arrives. The backup spot does not change.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
IDS = ["bw-uke4100-08901", "wharfe-burnsall"]
KEEP = {"id", "name", "kind", "river", "source", "notes", "location", "assumptions", "now", "days", "upstream_summary",
        "contributors", "classification", "lab_sample", "algae", "river_state", "flood_alerts", "error", "detail_file"}


def cut(s: dict) -> dict:
    s = {k: v for k, v in s.items() if k in KEEP}
    if "contributors" in s:
        s["contributors"] = s["contributors"][:3]
    return s


def main(src: Path) -> None:
    d = {n: json.loads((src / n).read_text()) for n in ("spots.json", "spots-lite.json", "verification.json", "alerts.json")}
    before = {
        "spots.json": {**{k: v for k, v in d["spots.json"].items() if k != "spots"},
                       "spots": [cut(s) for s in d["spots.json"]["spots"] if s["id"] in IDS]},
        "spots-lite.json": {**{k: v for k, v in d["spots-lite.json"].items() if k != "spots"},
                            "spots": [cut(s) for s in d["spots-lite.json"]["spots"] if s["id"] in IDS]},
        "verification.json": {"live": {k: d["verification.json"]["live"][k] for k in ("generated_at", "warning_table")}},
        "alerts.json": {**d["alerts.json"], "spots": {i: d["alerts.json"]["spots"][i] for i in IDS}},
    }
    after = copy.deepcopy(before)
    later = "2026-10-20T23:00:37.619741+01:00"
    for n in ("spots.json", "spots-lite.json", "alerts.json"):
        after[n]["generated_at"] = later
    after["spots.json"]["commit"] = "f00d123"
    a = after["alerts.json"]
    a["spots"][IDS[0]]["days"][2] = ["very high", a["words"].index("Very high risk: sewage spills"), a["spots"][IDS[0]]["days"][2][2]]
    main_spot = after["spots.json"]["spots"][0]
    main_spot["now"]["discharging_upstream"] = 1
    main_spot["contributors"][0]["status"] = 1
    main_spot["now"]["stale_upstream"] = 1
    main_spot["now"]["monitored_upstream"] = 14
    main_spot["now"]["feed_stale"] = [{"company": "Yorkshire Water", "overflows": 1, "since": "2026-10-20T19:00:00+00:00", "records": True}]
    main_spot["lab_sample"] = {"taken_at": "2026-10-20T11:15+01:00", "ecoli": 1200}
    for name, doc in (("before.json", before), ("after.json", after)):
        (HERE / name).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
