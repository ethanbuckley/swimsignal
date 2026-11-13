"""Past-sample histories for the Republic of Ireland and Wales (src/dipcast/sample_history.py,
scripts/export_sample_histories.py, build_site.write_sample_histories, docs/SAMPLE-HISTORY-CONTRACT-v1.md): the export
reads only a fetch's raw answers and its ledger, keeps every value as the source gave it, joins NRW's two sources only
where they agree, and the build publishes only a file of this contract."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from dipcast import ireland, sample_history as sh, wales

ROOT = Path(__file__).resolve().parents[1]
IE_SAMPLE = ROOT / "tests" / "fixtures" / "sample_history_ireland_v1_sample.json"
NRW_RAW = ROOT / "data" / "raw" / "nrw_sample_history"


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_counts_keep_their_limits():
    assert sh.count("<10") == (10.0, "<")
    assert sh.count(">24196") == (24196.0, ">")
    assert sh.count(" 630 ") == (630.0, None)
    assert sh.count("0") == (0.0, None)
    for bad in ("", "n/a", None, True, "1,200"):
        assert sh.count(bad) is None


def test_over_the_line_never_reads_a_limit_as_a_count():
    assert sh.over(900, None, 900) is False          # exactly the line is not over
    assert sh.over(901, None, 900) is True
    assert sh.over(10000, "<", 900) is False         # below a limit is never over
    assert sh.over(2419, ">", 500) is True           # above a limit at or over the line is over
    assert sh.over(100, ">", 500) is False           # above 100 might be 101: not shown to be over
    assert sh.over(900, None, None) is None          # no line, no verdict


# ------------------------------------------------------------------ the export from raw pages
def _raw_ireland(tmp_path: Path, ins: list, outs: list, refuse: bool = False) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    locs = [{"beach_id": "IEWEBWC010_0000_0040", "beach_name": "Trá Mhór", "beach_type": "Identified Beach",
             "county_name": "Galway", "current_annual_water_quality_classification": "Excellent Quality",
             "current_annual_classification_year": 2025},
            {"beach_id": "BPNBF240000030001", "beach_name": "Lough Muckno", "beach_type": "Non-Identified Beach",
             "county_name": "Monaghan"}]
    files = {"locations.json": {"count": 2, "list": locs}, "in_p1.json": {"count": len(ins), "list": ins},
             "out_p1.json": {"count": len(outs), "list": outs}}
    with (raw / "ledger.jsonl").open("w") as f:
        for i, (name, body) in enumerate(files.items()):
            data = json.dumps(body).encode()
            (raw / name).write_bytes(data)
            f.write(json.dumps({"n": i + 1, "at": f"2026-11-13T15:2{i}:00+00:00", "url": f"https://data.epa.ie/{name}",
                                "status": 200, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "file": name}) + "\n")
        if refuse:
            f.write(json.dumps({"n": 4, "at": "2026-11-13T15:30:00+00:00", "url": "x", "status": 429, "bytes": 0,
                                "sha256": "", "file": None}) + "\n")
    return raw


def _m(i, key, day, ec, ie_, word="Excellent"):
    return {"monitoring_result_id": i, "beach_id": key, "beach_name": "Trá Mhór", "county_name": "Galway",
            "result_date": day, "e_coli_result": ec, "intestinal_enterococci_result": ie_, "sample_water_quality_status": word}


def test_ireland_export_keeps_every_value_as_the_epa_gave_it(tmp_path):
    ins = [_m(1, "IEWEBWC010_0000_0040", "2024-06-03", "<10", "<10"), _m(2, "IEWEBWC010_0000_0040", "2024-06-17", "620", "40", "Poor"),
           _m(3, "BPNBF240000030001", "2024-07-01", ">2419", "15", "Poor"), _m(4, "IEWEBWC010_0000_0040", "2024-07-01", "n/a", "10")]
    outs = [_m(5, "IEWEBWC010_0000_0040", "2024-10-02", "0", "1")]
    doc = sh.export_ireland(_raw_ireland(tmp_path, ins, outs))
    assert doc["schema"] == sh.SCHEMA and doc["nation"] == "ireland" and doc["dropped"] == {"e_coli": 1}
    tra = next(s for s in doc["sites"] if s["id"] == "IEWEBWC010_0000_0040")
    assert tra["kind"] == "coast" and tra["line"] == 500 and tra["rating"] == {"value": "Excellent", "year": 2025}
    assert tra["in"] == [["2024-06-03", "<10", "<10", "E"], ["2024-06-17", "620", "40", "P"]]
    assert tra["out"] == [["2024-10-02", "0", "1", "E"]]
    assert tra["summary"] == {"samples": 3, "first": "2024-06-03", "last": "2024-10-02", "over_line": 1, "below_limit": 1,
                              "above_limit": 0, "seasons": 1, "poor": 1, "out_of_season": 1}
    # The viewer's form of a water's samples, from the compact file: limits stay limits.
    rows = sh.ireland_site_samples(tra)
    assert [(r["t"], r["ecoli"], r["q"], r["season"], r["over"]) for r in rows] == [
        ("2024-06-03", 10, "<", "in", False), ("2024-06-17", 620, None, "in", True), ("2024-10-02", 0, None, "out", False)]
    lake = next(s for s in doc["sites"] if s["id"] == "BPNBF240000030001")
    assert lake["kind"] == "lake" and lake["line"] == 900 and lake["designated"] is False
    assert sh.ireland_site_samples(lake)[0]["over"] is True   # ">2419" is over 900


def test_ireland_export_refuses_a_ledger_with_a_refusal_or_a_changed_page(tmp_path):
    raw = _raw_ireland(tmp_path, [_m(1, "IEWEBWC010_0000_0040", "2024-06-03", "10", "10")], [], refuse=True)
    with pytest.raises(ValueError, match="refusal"):
        sh.export_ireland(raw)
    (tmp_path / "b").mkdir()
    raw2 = _raw_ireland(tmp_path / "b", [_m(1, "IEWEBWC010_0000_0040", "2024-06-03", "10", "10")], [])
    (raw2 / "in_p1.json").write_text(json.dumps({"count": 1, "list": []}))
    with pytest.raises(ValueError, match="differs from the ledger"):
        sh.export_ireland(raw2)


def test_ireland_export_refuses_pages_that_miss_rows(tmp_path):
    raw = _raw_ireland(tmp_path, [_m(1, "IEWEBWC010_0000_0040", "2024-06-03", "10", "10")], [])
    body = json.loads((raw / "in_p1.json").read_text())
    body["count"] = 5001   # the EPA counts more than the pages hold
    data = json.dumps(body).encode()
    (raw / "in_p1.json").write_bytes(data)
    lines = [json.loads(x) for x in (raw / "ledger.jsonl").read_text().splitlines()]
    for x in lines:
        if x["file"] == "in_p1.json":
            x["sha256"] = hashlib.sha256(data).hexdigest()
    (raw / "ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    with pytest.raises(ValueError, match="pages hold"):
        sh.export_ireland(raw)


# ------------------------------------------------------------------ Wales
def test_nrw_sources_join_only_where_they_agree():
    a = {"2025-05-07T11:41": {"t": "2025-05-07T11:41", "ecoli": 45, "q": None, "ie": 10, "ie_q": "<", "reason": "statutory"},
         "2023-08-18T10:30": {"t": "2023-08-18T10:30", "ecoli": 350, "q": None, "ie": 135, "ie_q": None, "reason": "investigation"}}
    s = {"2025-05-07T11:41": {"t": "2025-05-07T11:41", "ecoli": 45, "q": None, "ie": 10, "ie_q": "<"},
         "2026-09-18T10:36": {"t": "2026-09-18T10:36", "ecoli": 1000, "q": None, "ie": 50, "ie_q": None}}
    out = sh.merge_wales(a, s)
    assert [(x["t"], x["src"], x["reason"], x["over"]) for x in out] == [
        ("2023-08-18T10:30", ["archive"], "investigation", False), ("2025-05-07T11:41", ["archive", "service"], "statutory", False),
        ("2026-09-18T10:36", ["service"], "statutory", True)]
    s["2025-05-07T11:41"]["ecoli"] = 46
    with pytest.raises(ValueError, match="disagree"):
        sh.merge_wales(a, s)


def test_wales_export_from_the_committed_snapshot():
    doc = sh.export_wales(NRW_RAW)
    hay, llandeilo = doc["sites"]
    assert (hay["id"], hay["station"], llandeilo["id"], llandeilo["station"]) == ("ukl2400-38620", "S5520068", "ukl1401-37650", "S6020030")
    # 37 archive samples at Hay, 30 of them also in the service; 22 and 16 at Llandeilo, with two September 2026 samples
    # only in the service (the archive copy is of 4 Oct 2026).
    assert (hay["summary"]["samples"], hay["summary"]["archive"], hay["summary"]["service"]) == (37, 37, 30)
    assert (llandeilo["summary"]["samples"], llandeilo["summary"]["archive"], llandeilo["summary"]["service"]) == (24, 22, 16)
    assert [x["t"] for x in llandeilo["samples"] if x["src"] == ["service"]] == ["2026-09-09T11:45", "2026-09-18T10:36"]
    assert (hay["summary"]["first"], hay["summary"]["last"], llandeilo["summary"]["last"]) == ("2023-08-18", "2026-09-07", "2026-09-18")
    # Hay's one "<10" E. coli stays a limit; none of either water's samples is flagged deviating.
    lt = [x for x in hay["samples"] if x["q"] == "<"]
    assert [(x["t"], x["ecoli"]) for x in lt] == [("2026-05-27T13:20", 10)]
    assert not any(x["deviating"] for s in doc["sites"] for x in s["samples"] if "deviating" in x)
    assert hay["rating"]["value"] == "Sufficient" and llandeilo["rating"] is None


# ------------------------------------------------------------------ the committed files
def test_the_committed_files_are_this_contract_and_carry_their_credit():
    for nation in ("ireland", "wales"):
        doc, why = sh.read(nation)
        assert why is None, why
        assert sh.FILES[nation].stat().st_size < 1_000_000   # files over 1 MB stay out of git
        assert all(r["status"] == 200 for r in doc["requests"])
        assert doc["coverage"]["samples"] == sum(s["summary"]["samples"] for s in doc["sites"])
        assert doc["credit"] == sh.CREDITS[nation] and doc["claim"]["not_claimed"]
        assert set(doc["qualifiers"]) == {"<", ">"} and doc["methods"]
    # NRW's attribution statement, word for word as its record gives it on 13 Nov 2026.
    assert sh.CREDITS["wales"].startswith("Contains Natural Resources Wales information © Natural Resources Wales and "
                                          "Database Right. All rights Reserved.")
    ie_doc, _ = sh.read("ireland")
    assert ie_doc["epa_counts"] == {"in": 25895, "out": 1034} and ie_doc["coverage"]["samples"] == 26929
    assert ie_doc["period"] == {"first": "2014-05-22", "last": "2026-11-04"}


def test_nothing_is_read_from_a_foreign_or_missing_file(tmp_path):
    assert sh.read("ireland", tmp_path / "none.json") == (None, "no export in this build")
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"schema": sh.SCHEMA, "version": "2.0.0", "nation": "ireland"}))
    assert sh.read("ireland", p)[0] is None
    p.write_text(json.dumps({"schema": sh.SCHEMA, "version": "1.0.0", "nation": "wales"}))
    assert sh.read("ireland", p)[0] is None   # Wales's file is not Ireland's


# ------------------------------------------------------------------ the build and the coverage page
def test_the_build_splits_each_file_into_an_index_and_a_file_a_water(tmp_path):
    bs = _build_site()
    (tmp_path / "data" / "research" / "history").mkdir(parents=True)
    (tmp_path / "data" / "research" / "ecoli.json").write_text("{}")   # another writer's file is left alone
    h = bs.write_sample_histories(tmp_path, {"ireland": IE_SAMPLE})
    assert h["ireland"]["available"] and h["ireland"]["waters"] == 4 and h["wales"]["waters"] == 2
    assert (tmp_path / "data" / "research" / "ecoli.json").read_text() == "{}"
    out = tmp_path / "data" / "research" / "history"
    index = json.loads((out / "ireland.json").read_text())
    assert index["available"] and "requests" not in index and index["credit"] == sh.CREDITS["ireland"]
    for x in index["sites"]:
        assert not {"in", "out", "samples"} & set(x) and {"id", "name", "summary", "page", "line"} <= set(x)
    one = json.loads((out / "ireland" / "BPNBF070000020002.json").read_text())
    assert one["name"] == "Merrion Strand" and len(one["samples"]) == one["summary"]["samples"] == 402
    assert {"t", "ecoli", "q", "ie", "ie_q", "status", "season", "over"} <= set(one["samples"][0])
    hay = json.loads((out / "wales" / "ukl2400-38620.json").read_text())
    assert len(hay["samples"]) == 37 and hay["samples"][0]["src"] == ["archive"]
    # A file of another major version is not published; the index says why.
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": sh.SCHEMA, "version": "2.0.0", "nation": "ireland"}))
    h = bs.write_sample_histories(tmp_path, {"ireland": bad})
    assert h["ireland"]["available"] is False
    assert json.loads((out / "ireland.json").read_text())["available"] is False
    assert not list((out / "ireland").iterdir())


def test_cards_link_to_every_sample(tmp_path):
    snap = {"fetched_at": "2026-11-13T15:00:00+00:00", "state": "live", "credit": ireland.CREDIT,
            "samples": {"state": "ok", "fetched_at": "2026-11-13T15:00:00+00:00", "season": 2026},
            "alerts": {"state": "ok", "fetched_at": "2026-11-13T15:00:00+00:00"}, "locations": {"state": "ok"},
            "sites": [{"id": "BPNBF070000020002", "name": "Merrion Strand", "county": "Dublin", "designated": False, "rating": None,
                       "season_restriction": False, "page": ireland.PAGE_URL.format("BPNBF070000020002"), "sample": {"state": "none"},
                       "alerts": []},
                      {"id": "IEXXBWC999_0000_0001", "name": "Nowhere", "county": "Cork", "designated": True, "rating": None,
                       "season_restriction": False, "page": ireland.PAGE_URL.format("IEXXBWC999_0000_0001"), "sample": {"state": "none"},
                       "alerts": []}]}
    assert sh.attach(snap, "ireland", IE_SAMPLE) == 1
    assert snap["sites"][0]["history"] == {"samples": 402, "first": "2016-01-04", "last": "2026-11-04"}
    html = ireland.render(snap)
    assert '<a href="samples.html#ireland=BPNBF070000020002">Every lab sample, 2016 to 2026 (402)</a>' in html
    assert html.count("samples.html#ireland=") == 1
    snap_w = json.loads((ROOT / "data" / "raw" / "wales_bathing_waters.json").read_text())
    w = {"fetched_at": snap_w["fetched_at"], "state": "snapshot", "sites": [
        {**s, "sample": {"state": "none"}} for s in wales.parse_sites(snap_w["site_items"])]}
    assert sh.attach(w, "wales") == 2
    html = wales.render(w)
    assert 'href="samples.html#wales=ukl2400-38620">Every lab sample, 2023 to 2026 (37)</a>' in html
    assert 'href="samples.html#wales=ukl1401-37650">Every lab sample, 2023 to 2026 (24)</a>' in html
