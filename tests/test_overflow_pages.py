"""Each overflow's public record page, overflow/<id>/ (src/dipcast/overflow_record.py, build_site.write_overflow_pages).
Written from the spots' data/upstream/<id>.json and the EA's annual returns, permit and improvement columns, WINEP
deadlines, spill lengths, upgrade notes and dry-weather counts, all made up here. The real Addingham page was read
against the sources by hand (PR body)."""
import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import unquote

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as bs

from dipcast import overflow_record as orec

SPOTS = [{"id": "wharfe-ilkley", "name": "Wharfe at Cromwheel, Ilkley", "kind": "river", "days": []},
         {"id": "greenholme", "name": "Greenholme", "kind": "river", "days": []}]
ROW = {"site_name": "ADDINGHAM/NO 1 SPS/PRELIMINARY TREATMENT-STW/3XDWF OVERFLOW", "company": "Yorkshire Water",
       "receiving_watercourse": "Low Mills Mill Race", "lake_distance_km": 0.0, "has_live": True, "status": 0,
       "data_state": "live", "latest_event_end": "2026-05-13T11:00:00+00:00", "lat": 53.9, "lon": -1.8}


def sources(tmp: Path) -> dict:
    up = tmp / "data" / "upstream"
    up.mkdir(parents=True)
    a = {**ROW, "site_id": "YWS00144", "distance_km": 4.1, "weight": 0.812, "travel_h": 5.7}
    b = {**ROW, "site_id": "YWS00145", "site_name": "ADDINGHAM/NO 1 SPS/PRELIMINARY TREATMENT-STW/6XDWF OVERFLOW",
         "distance_km": 4.1, "weight": 0.2, "travel_h": 5.7, "status": -1, "data_state": "offline"}
    c = {**ROW, "site_id": "AWS01573", "site_name": "BOXTED-COTTAGE (SUFFOLK) STW", "company": "Anglian Water",
         "distance_km": 1.0, "weight": 0.5, "travel_h": 1.0, "has_live": False, "data_state": "no_feed"}
    odd = {**ROW, "site_id": "B2", "distance_km": 1.0, "weight": 0.1}   # an id that is not the returns' kind: no page
    (up / "wharfe-ilkley.json").write_text(json.dumps({"overflows": [a, b, c, odd]}))
    (up / "greenholme.json").write_text(json.dumps({"overflows": [{**a, "distance_km": 9.6, "weight": 0.6}]}))
    ar = []
    for y in orec.YEARS:
        ar.append({"site_id": "YWS00144", "year": y, "company": "Yorkshire Water", "site_name": ROW["site_name"],
                   "asset_type": "Storm discharge at pumping station", "spills": 40.0 + y - 2021, "spill_hours": 370.75,
                   "edm_operational_pct": 100.0, "receiving_water": "No", "wfd_waterbody_name": "Wharfe from Barben Beck",
                   "bathing_water": "Wharfe at Cromwheel, Ilkley"})
    ar.append({"site_id": "AWS01573", "year": 2025, "company": "Anglian Water", "site_name": "BOXTED-COTTAGE (SUFFOLK) STW",
               "asset_type": "Storm discharge at pumping station", "spills": 3.0, "spill_hours": 4.5, "edm_operational_pct": 51.0,
               "receiving_water": "No", "wfd_waterbody_name": "Glem - Lower", "bathing_water": "Not Applicable"})
    pd.DataFrame(ar).to_parquet(tmp / "ar.parquet")
    rec = [{"site_id": "YWS00144", "year": 2025, "company": "Yorkshire Water", "permit": "2482", "activity_ref": "A1",
            "improvement": "No improvement action in reporting period", "investigation": "UWWTR investigation ongoing"},
           {"site_id": "YWS00145", "year": 2025, "company": "Yorkshire Water", "permit": "2482", "activity_ref": "A2",
            "improvement": "Operational improvement completed", "investigation": "No investigation activity in reporting period"},
           {"site_id": "AWS01573", "year": 2025, "company": "Anglian Water", "permit": "Permit Applied For", "activity_ref": "A1",
            "improvement": "No improvement action in reporting period", "investigation": "No investigation activity in reporting period"}]
    pd.DataFrame(rec).astype({"year": "Int64"}).to_parquet(tmp / "rec.parquet")
    pd.DataFrame([{"permit": "2482 1", "company": "Yorkshire Water Service Ltd", "action_id": "08YW100038",
                   "action_name": "ADDINGHAM/NO 1 SPS", "driver": "BW_IMP1", "completion_date": "2026-03-31"},
                  {"permit": "2482", "company": "Yorkshire Water Service Ltd", "action_id": "08YW999999",
                   "action_name": "ADDINGHAM storage", "driver": "EnvAct_IMP2", "completion_date": "2030-03-31"},
                  {"permit": "Permit Applied For", "company": "Anglian Water Services Ltd", "action_id": "08AW1",
                   "action_name": "Never matched", "driver": "EnvAct_IMP2", "completion_date": "2030-03-31"}]).to_parquet(tmp / "winep.parquet")
    (tmp / "upgrades.csv").write_text(
        "site_id,company,stage,match,source_name,source_url,quote,checked,completed\n"
        "YWS00144,Yorkshire Water,upgrading,shared name,Addingham SPS CSO,https://example.org/ilkley,\"We are building\",2026-10-24,\n")
    (tmp / "dry.csv").write_text("site_id,company,year,dry_spill_days,dry_days\nYWS00145,Yorkshire Water,2025,40,120\n"
                                 "YWS00144,Yorkshire Water,2025,2,120\n")
    (tmp / "lengths.json").write_text(json.dumps({
        "schema": "swimsignal.spill-durations", "version": "1.1.0", "period": {"from": "2024-01-01", "to": "2025-12-31"},
        "claim": {"public_wording": "How long this overflow's spills lasted in 2024 and 2025."}, "attribution": ["EA, OGL"],
        "method": {}, "companies": ["Yorkshire Water"],
        "overflows": {"site_id": ["YWS00144"], "company": [0], "spills_2024": [57], "spills_2025": [40], "median_h": [5.0],
                      "p90_h": [30.0], "longest_h": [98.0], "share_over_6h": [0.4], "few": [False]}}))
    return {"returns": tmp / "ar.parquet", "record": tmp / "rec.parquet", "winep": tmp / "winep.parquet",
            "upgrades": tmp / "upgrades.csv", "dry": tmp / "dry.csv", "lengths": tmp / "lengths.json"}


def text(page: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", page.split("<main", 1)[1].split("</main>")[0])))


def write(tmp: Path) -> list[str]:
    return bs.write_overflow_pages(tmp, SPOTS, token="abcdefghij0123456789", root="https://example.org/",
                                   generated=pd.Timestamp("2026-10-31 18:00", tz="Europe/London"), **sources(tmp))


def test_a_page_for_every_overflow_upstream_of_a_spot_with_a_page(tmp_path):
    assert write(tmp_path) == ["AWS01573", "YWS00144", "YWS00145"]   # B2 is not an annual-returns id: no page
    page = (tmp_path / "overflow" / "YWS00144" / "index.html").read_text()
    assert "<title>Addingham sewage works storm tank overflow (YWS00144) · SwimSignal</title>" in page
    assert '<base href="../../">' in page and '<link rel="canonical" href="https://example.org/overflow/YWS00144/">' in page
    assert "cloudflareinsights" in page and 'class="phone-nav"' in page and "<script" not in page.split("</main>")[0].split("<main")[1]
    words = text(page)
    # The caveat first; never a breach, never safe; the credits last.
    assert words.index("It is not a water test") < words.index("The record") < words.index("Sources and credits")
    low = words.lower()
    assert not re.search(r"\b(breach|breached|illegal|unlawful|safe)\b", low.replace("not a finding that the overflow broke its permit", ""))
    assert orec.CREDITS in words
    # The record: the permit and activity as the 2025 return gives them, and why the consents register is not used.
    assert "Permit reference 2482, activity A1 (2025 return)" in words and "internal use only" in words
    assert "Bathing water named in the return Wharfe at Cromwheel, Ilkley" in words
    # Both spots, nearest first, each linked to its page and its overflow history.
    assert words.index("Wharfe at Cromwheel, Ilkley · 4.1 km upstream · model weight 81%") < words.index("Greenholme · 9.6 km")
    assert '<a href="spot/greenholme/">Greenholme</a>' in page and '<a href="spot/greenholme/profile/">every overflow there</a>' in page
    # Each year as published, and the 12/24 method.
    assert re.search(r"<tr><td>2025</td><td class=\"num\">44</td><td class=\"num\">370.75</td><td class=\"num\">100%</td></tr>", page)
    assert orec.METHOD_12_24 in words
    # Recent: the feed's status at the update and its last spill; events not published, and why.
    assert "its company's live feed showed it not discharging. The last spill the feed reported ended on 13 May 2026." in words
    assert "Typical spill 5 h Long end 30 h Longest 4.1 days Spills 2024 57 Spills 2025 40" in words
    assert "Each spill's start and stop: not published here." in words and "Yorkshire Water publishes its own files from 2021; they carry no licence" in words
    # Improvements: the returns word for word; WINEP by permit and activity number; the company's own words.
    assert "2025 No improvement action in reporting period UWWTR investigation ongoing" in words
    assert "ADDINGHAM/NO 1 SPS (08YW100038, BW_IMP1): due 31 March 2026." in words
    assert "ADDINGHAM storage (08YW999999, EnvAct_IMP2): due 31 March 2030. The programme names the permit, which 2 overflows share" in words
    assert "a deadline, not a record that it was" in words
    assert "Yorkshire Water says it is upgrading its Addingham SPS CSO, a name that could also mean another overflow nearby" in words
    # Under the note's rule (10 days, a fifth): no dry-weather section here.
    assert 'id="dry-weather"' not in page


def test_the_draft_is_neutral_has_no_address_and_links_the_page(tmp_path):
    write(tmp_path)
    page = (tmp_path / "overflow" / "YWS00144" / "index.html").read_text()
    href = unescape(re.search(r'<a class="btn primary" href="([^"]+)">Send this record</a>', page)[1])
    assert href.startswith("mailto:?subject=")   # no To: the reader adds the company's address from its contact page
    draft = unquote(href)
    assert "Dear Yorkshire Water," in draft and "(Environment Agency id YWS00144, permit 2482)" in draft
    assert "Wharfe at Cromwheel, Ilkley; Greenholme, where people swim" in draft
    assert "2024: 43 spills, 370.75 hours; 2025: 44 spills, 370.75 hours" in draft
    assert "https://example.org/overflow/YWS00144/" in draft and "Could you tell me what is planned" in draft
    assert not re.search(r"(?i)\b(breach|illegal|unlawful|demand|scandal|dumping)\b", draft)
    assert f'<a href="{orec.CONTACT["Yorkshire Water"]}">its contact page</a>' in page
    assert f'<a href="{orec.FIND_MP}">find your MP</a>' in page and "SwimSignal sends nothing" in text(page)


def test_dry_weather_is_labelled_as_swimsignals_inference(tmp_path):
    write(tmp_path)
    words = text((tmp_path / "overflow" / "YWS00145" / "index.html").read_text())
    assert "By SwimSignal's count from the EA's start/stop records, this overflow spilled on 40 of 120 dry days in 2025." in words
    assert "SwimSignal's inference, not an Environment Agency finding" in words and "not a finding that any permit was broken" in words
    assert "its company's live feed listed its monitor as offline" in words
    assert "Operational improvement completed" in words and "08YW100038" not in words   # activity 2: not the BW_IMP1 action


def test_a_placeholder_permit_is_quoted_and_matches_nothing(tmp_path):
    write(tmp_path)
    page = (tmp_path / "overflow" / "AWS01573" / "index.html").read_text()
    words = text(page)
    assert 'Permit reference None given. The 2025 return\'s permit field reads "Permit Applied For".' in words
    assert "Never matched" not in words and "Bathing water named" not in words
    assert "not in its company's live feed" in words and "2021 – – –" in words


def test_missing_sources_leave_the_pages_and_say_so(tmp_path):
    src = sources(tmp_path)
    ids = bs.write_overflow_pages(tmp_path, SPOTS, root="https://example.org/", returns=tmp_path / "none.parquet",
                                  record=tmp_path / "none.parquet", winep=tmp_path / "none.parquet",
                                  upgrades=tmp_path / "none.csv", dry=tmp_path / "none.csv", lengths=tmp_path / "none.json")
    assert ids == ["AWS01573", "YWS00144", "YWS00145"] and src
    words = text((tmp_path / "overflow" / "YWS00144" / "index.html").read_text())
    assert "No annual return in this build is filed under this id" in words and "Name in the company's live feed" in words
    assert "Not in the 2024 or 2025 returns this build holds." in words
    assert "The PR24 WINEP's deadlines are not in this build" in words and "lists no storm overflow improvement action" not in words


def test_write_pages_lists_them_in_the_sitemap_and_the_history_links_them(tmp_path):
    (tmp_path / "data").mkdir()
    sources(tmp_path)
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/", day="2026-10-31")
    sm = (tmp_path / "sitemap.xml").read_text()
    assert "<loc>https://example.org/overflow/YWS00144/</loc>" in sm and "/overflow/B2/" not in sm
    assert (tmp_path / "overflow" / "YWS00144" / "index.html").is_file()
    prof = (tmp_path / "spot" / "wharfe-ilkley" / "profile" / "index.html").read_text()
    assert '<a href="overflow/YWS00144/">Addingham sewage works storm tank overflow</a>' in prof and 'href="overflow/B2/"' not in prof
    app = (bs.TEMPLATE.parent / "index.html").read_text()
    assert '<a href="overflow/${c.site_id}/">${esc(nm.plain)}</a>' in app
    assert "overflow/" not in (bs.TEMPLATE.parent / "sw.js").read_text()   # not stored for offline use


def test_the_pages_follow_the_design_rules():
    tpl = orec.TEMPLATE.read_text()
    assert not re.search(r"box-shadow|gradient|border-radius|text-transform:\s*uppercase|letter-spacing", tpl)
    assert set(orec.CONTACT) == {"Anglian Water", "Dwr Cymru Welsh Water", "Northumbrian Water", "Severn Trent Water",
                                 "South West Water", "Southern Water", "Thames Water", "United Utilities", "Wessex Water",
                                 "Yorkshire Water"}
    assert all(u.startswith("https://") for u in orec.CONTACT.values())
