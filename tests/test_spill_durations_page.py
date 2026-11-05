"""Spill durations on the site (build_site.write_spill_durations, durations.html, each spot's overflow history): the
research export (docs/SPILL-DURATIONS-CONTRACT-v1.md) split into an index and one file a spot, published only when it is
that contract's schema and major version, and shown as 2024-25 history, never as a forecast and never on the spot's page.
The fixture is cut from the export (tests/site_durations.test.cjs says what is in it)."""

import json
import re
import shutil
import subprocess
import sys
from html import unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "spill_durations_v1_sample.json"
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as bs  # noqa: E402

from dipcast import profile as pf  # noqa: E402

SPOTS = [{"id": "wharfe-ilkley", "name": "Wharfe at Ilkley", "kind": "river", "upstream_summary": {"overflows": 4}, "days": []},
         {"id": "tarn", "name": "A Tarn", "kind": "lake", "upstream_summary": {"overflows": 0}, "days": []}]


def upstream(site: Path) -> None:
    """Four overflows upstream of one spot, largest weight first: three in the export, one Welsh one that is not."""
    (site / "data" / "upstream").mkdir(parents=True, exist_ok=True)
    rows = [{"site_id": "TWL00102", "site_name": "SOME STW", "company": "Thames Water", "distance_km": 1.0, "lake_distance_km": 0.0,
             "travel_h": 1.4, "weight": 0.9, "has_live": True},
            {"site_id": "DCW0001", "site_name": "Welsh/CSO", "company": "Dwr Cymru Welsh Water", "distance_km": 3.0, "lake_distance_km": 0.0,
             "travel_h": 4.0, "weight": 0.5, "has_live": False},
            {"site_id": "YWS00007", "site_name": "Bridge Lane/CSO", "company": "Yorkshire Water", "distance_km": 5.0, "lake_distance_km": 0.0,
             "travel_h": 7.0, "weight": 0.2, "has_live": True},
            {"site_id": "YWS00011", "site_name": None, "company": "Yorkshire Water", "distance_km": 9.0, "lake_distance_km": 0.0,
             "travel_h": 12.0, "weight": 0.1, "has_live": True}]
    (site / "data" / "upstream" / "wharfe-ilkley.json").write_text(json.dumps({"id": "wharfe-ilkley", "overflows": rows}))


def text(page: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", page.split("<main", 1)[1].split(">", 1)[1].split("</main>")[0]))).replace(" ,", ",")


def test_the_export_is_split_into_an_index_and_a_file_a_spot(tmp_path):
    upstream(tmp_path)
    h = bs.write_spill_durations(tmp_path, SPOTS, SAMPLE)
    assert h == {"available": True, "version": "1.1.0", "overflows": 6, "spots": 1, "spot_overflows": 3}
    index = json.loads((tmp_path / "data" / "research" / "spill_durations.json").read_text())
    doc = json.loads(SAMPLE.read_text())
    # The index is the export without its 12,908 rows, with the spots that have a file; the tarn has no upstream file.
    assert index["available"] is True and "overflows" not in index
    assert {k: v for k, v in index.items() if k not in ("available", "spots")} == {k: v for k, v in doc.items() if k != "overflows"}
    assert index["spots"] == [{"id": "wharfe-ilkley", "name": "Wharfe at Ilkley", "overflows": 3, "absent": 1}]
    one = json.loads((tmp_path / "data" / "research" / "spill_durations" / "wharfe-ilkley.json").read_text())
    assert one["period"] == doc["period"] and [r["site_id"] for r in one["overflows"]] == ["TWL00102", "YWS00007", "YWS00011"]   # the upstream order
    i = doc["overflows"]["site_id"].index("TWL00102")
    assert {k: one["overflows"][0][k] for k in bs.DURATIONS_FIELDS} == {k: doc["overflows"][k][i] for k in bs.DURATIONS_FIELDS}
    assert one["overflows"][0]["company"] == "Thames Water" and one["overflows"][0]["name"] == "Some sewage works overflow"
    assert one["overflows"][2]["name"] == "YWS00011"   # no name: its id, as the other pages give it
    assert one["absent"] == [{"site_id": "DCW0001", "name": "Welsh storm overflow", "own": "Welsh/CSO", "company": "Dwr Cymru Welsh Water"}]
    assert not (tmp_path / "data" / "research" / "spill_durations" / "tarn.json").exists()


def test_nothing_is_published_from_a_missing_or_foreign_export(tmp_path):
    upstream(tmp_path)
    bs.write_spill_durations(tmp_path, SPOTS, SAMPLE)   # an earlier build's files, which must not survive
    out = tmp_path / "data" / "research"
    assert bs.write_spill_durations(tmp_path, SPOTS, tmp_path / "none.json") == {"available": False, "why": "no export in this build"}
    assert json.loads((out / "spill_durations.json").read_text()) == {"schema": "swimsignal.spill-durations", "available": False,
                                                                      "why": "no export in this build"}
    assert not list((out / "spill_durations").iterdir())
    for name, change, why in [("v2.json", {"version": "2.0.0"}, "not swimsignal.spill-durations 1.x"),
                              ("other.json", {"schema": "swimsignal.lake-observations"}, "not swimsignal.spill-durations 1.x"),
                              ("short.json", {"overflows": {**json.loads(SAMPLE.read_text())["overflows"], "few": [True]}}, "differ in length")]:
        (tmp_path / name).write_text(json.dumps({**json.loads(SAMPLE.read_text()), **change}))
        h = bs.write_spill_durations(tmp_path, SPOTS, tmp_path / name)
        assert h["available"] is False and why in h["why"], name
        assert not list((out / "spill_durations").iterdir()), name
    (tmp_path / "bad.json").write_text("{")
    assert bs.write_spill_durations(tmp_path, SPOTS, tmp_path / "bad.json")["why"] == "export is not JSON"
    # A minor version is read: 1.x keeps the fields this site reads.
    (tmp_path / "v1_1.json").write_text(json.dumps({**json.loads(SAMPLE.read_text()), "version": "1.1.0"}))
    assert bs.write_spill_durations(tmp_path, SPOTS, tmp_path / "v1_1.json")["available"] is True


def test_the_spill_lengths_are_on_the_overflow_history_page_as_history_after_the_returns(tmp_path, monkeypatch):
    upstream(tmp_path)
    monkeypatch.setattr(bs, "SPILL_DURATIONS", SAMPLE)
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/", day="2026-10-30")
    page = (tmp_path / "spot" / "wharfe-ilkley" / "profile" / "index.html").read_text()
    words, claim = text(page), json.loads(SAMPLE.read_text())["claim"]["public_wording"]
    # Its heading names the years; the history line and the export's own sentence come before any figure, after the
    # annual returns' table and before the credits.
    at = words.index("How long their spills lasted, 2024 and 2025")
    assert words.index("A dash: no annual return") < at < words.index("Sources and credits")
    assert words[at:].startswith(f"How long their spills lasted, 2024 and 2025 History: 2024 and 2025. {claim}")
    assert "Spill lengths at 2 of the 4 overflows, 2024-25" not in words   # three of the four are in the export
    assert "Spill lengths at 3 of the 4 overflows, 2024-25" in words
    assert '<td class="num" data-l="Typical spill, 2024-25">30\u00a0min, few spills</td>' in page
    assert '<td class="num" data-l="Longest">44\u00a0days</td>' in page
    assert ("1 of the overflows upstream has no spill in these 2024-25 records: none was recorded, or there is no record "
            "(Dŵr Cymru Welsh Water's overflows are not in them). That is not the same as no spills") in words
    assert 'href="durations.html">Spill durations</a>' in page and "Open Government Licence v3.0" in words[at:]
    assert "safe" not in words.lower() and "harmless" not in words[at:].lower()
    # Never on the spot's own page, where the forecast and its "if it stops now" line are.
    spot = (tmp_path / "spot" / "wharfe-ilkley" / "index.html").read_text()
    assert "spill_durations" not in spot and "How long their spills lasted" not in spot and "durations.html" not in spot
    assert "spill_durations" not in (bs.TEMPLATE.parent / "index.html").read_text()


def test_without_an_export_the_history_page_has_no_spill_lengths(tmp_path, monkeypatch):
    upstream(tmp_path)
    monkeypatch.setattr(bs, "SPILL_DURATIONS", tmp_path / "none.json")
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/", day="2026-10-30")
    assert "How long their spills lasted" not in (tmp_path / "spot" / "wharfe-ilkley" / "profile" / "index.html").read_text()


def test_the_viewer_is_written_with_its_script_and_listed(tmp_path, monkeypatch):
    upstream(tmp_path)
    monkeypatch.setattr(bs, "SPILL_DURATIONS", SAMPLE)
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/", day="2026-10-30")
    page = (tmp_path / "durations.html").read_text()
    assert "<title>Spill durations · SwimSignal</title>" in page and '<script src="durations.js?v=' in page
    assert (tmp_path / "durations.js").read_bytes() == (bs.TEMPLATE.parent / "durations.js").read_bytes()
    assert '<link rel="canonical" href="https://example.org/durations.html">' in page
    # The shared header and foot, as the other scripted pages carry them.
    sites = (tmp_path / "sites.html").read_text()
    assert re.search(r"<nav aria-label=\"Site\">.*?</nav>", page)[0] == re.search(r"<nav aria-label=\"Site\">.*?</nav>", sites)[0]
    assert re.search(r'<footer class="site-foot">.*?</footer>', page, re.S)[0] == re.search(r'<footer class="site-foot">.*?</footer>', sites, re.S)[0]
    # History first: the lead names the years and says it is not a forecast; nothing says safe or clean.
    words = text(page)
    assert words.lstrip().startswith("Spill durations How long storm overflow spills lasted in 2024 and 2025") and "not a forecast" in words[:300]
    assert not re.search(r"\bsafe\b|\bclean\b", words, re.I)
    assert "<loc>https://example.org/durations.html</loc>" in (tmp_path / "sitemap.xml").read_text()
    data = (tmp_path / "data.html").read_text()
    assert "how long storm overflow spills lasted in 2024 and 2025" in data   # in the research/ row, which links the first research file (lakes.json)
    assert '<h2 id="research">research/</h2>' in data and "Not described here yet" not in data
    assert '<h3><a href="durations.html">Spill durations</a></h3>' in (tmp_path / "research.html").read_text()   # under Observations
    assert json.loads((tmp_path / "data" / "research" / "spill_durations.json").read_text())["available"] is True


def test_python_and_the_page_say_a_length_the_same_way():
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    cases = [0, 0.004, 0.07, 0.5, 0.73, 1.57, 2.0, 9.83, 9.99, 18.58, 47.4, 99.5, 1054.5]
    js = subprocess.run(["node", "-e", f"const D=require({json.dumps(str(bs.TEMPLATE.parent / 'durations.js'))});"
                         f"console.log(JSON.stringify({json.dumps(cases)}.map(D.durationsHours)))"], capture_output=True, text=True, check=True)
    assert json.loads(js.stdout) == [pf.hours_said(h) for h in cases]
    assert pf.hours_said(None) == "–"


def test_a_spot_whose_overflows_are_all_missing_says_none_has_a_spill_in_the_records():
    """Wye at Hereford on 30 Oct 2026: its 14 overflows are all Dŵr Cymru's, which the nine companies' records lack."""
    d = {"period": {"from": "2024-01-01", "to": "2025-12-31"}, "claim": {"public_wording": "How long this overflow's spills lasted."},
         "attribution": ["Environment Agency, OGL v3.0"], "overflows": [],
         "absent": [{"site_id": f"DCW{i}", "company": "Dwr Cymru Welsh Water"} for i in range(14)]}
    html = pf.durations_section(d)
    words = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))
    assert "History: 2024 and 2025." in words and "How long this overflow's" not in words   # no figures, so not the sentence beside them
    assert ("None of the 14 overflows upstream has a spill in these 2024-25 records: none was recorded, or there is no record "
            "(Dŵr Cymru Welsh Water's overflows are not in them). That is not the same as no spills") in words
    assert "<details" not in html


def test_a_typical_spill_under_a_minute_is_explained_and_never_said_as_nothing_discharged():
    """1.1: method.zero_length_note and events_same_start_stop. A typical length shown as under 1 min (the export's 0.0
    hours) gets the note; a page without such a row does not."""
    doc = json.loads(SAMPLE.read_text())
    method = doc["method"]
    assert method["events_same_start_stop"] == 1110 and method["zero_length_note"]
    row = {"site_id": "WSX1", "name": "A CSO", "own": "", "median_h": 0.0, "p90_h": 0.0, "longest_h": 0.2, "spills_2024": 9,
           "spills_2025": 4, "few": False}
    d = {"period": doc["period"], "claim": doc["claim"], "attribution": doc["attribution"], "method": method, "overflows": [row], "absent": []}
    words = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", pf.durations_section(d)))).replace(" ", " ")
    assert ("A typical spill shown as under 1 min means most of that overflow's spills lasted under a minute as recorded, or were "
            "recorded with the same start and stop time (1,110 such events in these records, mostly at Wessex Water and South West "
            "Water). It does not mean nothing was discharged.") in words
    assert "under a minute" not in pf.durations_section(d | {"overflows": [row | {"median_h": 0.5}]})
