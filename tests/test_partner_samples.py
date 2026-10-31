"""Partner water samples (docs/PARTNER-SAMPLES-CONTRACT-v1.md, scripts/partner_samples.py): the checker refuses what
the contract forbids, holds a held-out result to an agreement made before sampling, and the Waterhead file is the
published export, value for value."""

import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import partner_samples as ps  # noqa: E402

TODAY = date(2026, 10, 31)
GOOD = {
    "partner_id": "example-club", "sample_id": "EC-001", "site_name": "Example Lake, north shore",
    "site_lat": "54.40000", "site_lon": "-2.95000", "site_confirmed": "yes",
    "sampled_on": "2027-06-03", "sampled_time": "08:30", "timezone": "Europe/London",
    "determinand": "ecoli", "result": "10", "qualifier": "<", "unit": "mpn/100ml",
    "method_type": "mpn", "method": "Colilert-18 Quanti-Tray/2000", "lower_limit": "10", "upper_limit": "2419.6",
    "limits_written": "qualifier", "lab": "Example Water Lab", "lab_accredited": "yes", "sampler": "club coach",
    "licence": "CC-BY-4.0", "attribution": "Example Club", "publish_consent": "yes", "publish_consent_on": "2027-05-01",
    "test_use": "holdout", "test_consent_on": "2027-05-01", "consent_ref": "email 1 May 2027", "received_on": "2027-06-06",
    "notes": "",
}


def errors(**change):
    return ps.check_rows([{**GOOD, **change}], today=date(2027, 7, 1))[0]


def warnings(**change):
    return ps.check_rows([{**GOOD, **change}], today=date(2027, 7, 1))[1]


def test_the_template_is_the_checker_s_columns():
    assert ps.COLUMNS == tuple(GOOD) and len(ps.COLUMNS) == 30
    assert (ROOT / "docs" / "partner-samples-template-v1.csv").read_text().count("\n") == 1   # the header alone
    for c in ps.COLUMNS:   # every column is described in the contract
        assert f"`{c}`" in (ROOT / "docs" / "PARTNER-SAMPLES-CONTRACT-v1.md").read_text(), c


def test_a_good_row_passes():
    assert ps.check_rows([GOOD, {**GOOD, "determinand": "intestinal_enterococci", "result": "35", "qualifier": ""}],
                         today=date(2027, 7, 1)) == ([], [])


@pytest.mark.parametrize("change, says", [
    ({"site_lat": "-2.95", "site_lon": "54.4"}, "Great Britain or Ireland"),   # swapped
    ({"site_lon": "2.95"}, "Great Britain or Ireland"),                        # a dropped minus sign
    ({"sampled_on": "2027-02-30"}, "sampled_on is not a real"),
    ({"received_on": "2027-07-02"}, "received_on is in the future"),
    ({"sampled_on": "2027-06-07"}, "sampled after it was received"),
    ({"sampled_time": "8.30"}, "sampled_time must be HH:MM"),
    ({"timezone": ""}, "needs a timezone"),
    ({"timezone": "BST"}, "timezone"),
    ({"determinand": "e. coli"}, "determinand"),
    ({"unit": "cfu/ml"}, "bacteria are cfu/100ml or mpn/100ml"),
    ({"unit": "cfu/100ml"}, "method_type mpn does not give cfu/100ml"),
    ({"result": "-1"}, "result must be a number"),
    ({"result": "TNTC"}, "result must be a number"),
    ({"qualifier": "~"}, "qualifier"),
    ({"result": "0", "qualifier": ""}, "write <limit instead"),
    ({"limits_written": "zero", "lower_limit": ""}, "needs the lower_limit"),
    ({"licence": "none"}, "needs a licence other than none"),
    ({"attribution": ""}, "needs an attribution"),
    ({"publish_consent_on": ""}, "publish_consent_on must be"),
    ({"test_consent_on": "2027-08-01"}, "test_consent_on is in the future"),
    ({"consent_ref": ""}, "needs consent_ref"),
    ({"sampler": ""}, "sampler is blank"),
    ({"partner_id": "Example Club"}, "partner_id must be"),
])
def test_what_the_contract_forbids_is_refused(change, says):
    assert any(says in e for e in errors(**change)), errors(**change)


def test_a_held_out_result_needs_an_agreement_made_before_it_was_sampled():
    # Agreed the day of sampling, or after: a held-out set could then be chosen by its results.
    for agreed in ("2027-06-03", "2027-06-05"):
        assert any("use exploratory" in e for e in errors(test_consent_on=agreed, publish_consent_on=agreed))
    assert errors(test_consent_on="2027-06-02") == []
    # The same late agreement is fine for exploratory use, and for publication.
    assert errors(test_use="exploratory", test_consent_on="2027-06-05", publish_consent_on="2027-06-05") == []
    assert errors(test_use="none", test_consent_on="") == []


def test_a_file_is_one_partner_and_each_sample_one_place_and_time():
    other = {**GOOD, "partner_id": "another", "sample_id": "X"}
    assert any("one partner per file" in e for e in ps.check_rows([GOOD, other], today=date(2027, 7, 1))[0])
    twice = ps.check_rows([GOOD, GOOD], today=date(2027, 7, 1))[0]
    assert any("has ecoli twice" in e for e in twice)
    moved = {**GOOD, "determinand": "intestinal_enterococci", "sampled_time": "09:30"}
    assert any("two sites, days or times" in e for e in ps.check_rows([GOOD, moved], today=date(2027, 7, 1))[0])
    assert ps.check_rows([{**GOOD, "colour": "green"}])[0][0].startswith("columns: missing [], unknown ['colour']")


def test_the_warnings_carry_what_is_not_known():
    assert any("may be a below-limit result" in w for w in warnings(result="0", qualifier="", limits_written="not_stated"))
    assert warnings(result="0", qualifier="", limits_written="zero") == []   # a 0 the lab says stands for "below 10"
    assert any("not the stated lower_limit" in w for w in warnings(result="5"))
    assert any("approximate" in w for w in warnings(site_confirmed="no"))
    assert any("not an issue time" in w for w in warnings(sampled_time="", timezone=""))


def test_a_spreadsheet_byte_order_mark_is_read(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("﻿" + ps.to_csv([GOOD]), encoding="utf-8")
    assert ps.check_rows(ps.read(p), today=date(2027, 7, 1)) == ([], [])


# ---- Waterhead ----

def test_waterhead_is_the_published_export_value_for_value():
    doc = json.loads(ps.WET.read_text())
    committed = ps.WATERHEAD.read_text()
    assert ps.check_waterhead(doc, committed) == []
    rows = list(csv.DictReader(io.StringIO(committed)))
    assert len(rows) == 118 and len({r["sample_id"] for r in rows}) == 59
    by = {(r["sampled_on"], r["determinand"]): r["result"] for r in rows}
    for s in doc["samples"]:
        assert by[(s["date"], "ecoli")] == str(s["ecoli"]) and by[(s["date"], "intestinal_enterococci")] == str(s["ie"])
    assert {r["qualifier"] for r in rows} == {""} and {r["unit"] for r in rows} == {"cfu/100ml"}
    assert {r["test_use"] for r in rows} == {"exploratory"}   # seen before any Waterhead test was designed
    assert {r["lab"] for r in rows if r["sampled_on"] < "2026"} == {"Simplex Health"}
    assert {r["lab"] for r in rows if r["sampled_on"] > "2026"} == {"not_stated"}


def test_waterhead_passes_the_checker_with_its_open_questions_as_warnings():
    errs, warns = ps.check_rows(ps.read(ps.WATERHEAD), today=TODAY)
    assert errs == []
    zeros = [w for w in warns if "below-limit" in w]
    assert zeros == [f"row {n}: a 0 with limits_written not_stated: it may be a below-limit result, not no bacteria" for n in (8, 10, 77)]
    assert sum("approximate" in w for w in warns) == 118 and sum("issue time" in w for w in warns) == 118


def test_a_changed_count_in_the_file_is_caught():
    doc = json.loads(ps.WET.read_text())
    rows = list(csv.DictReader(io.StringIO(ps.WATERHEAD.read_text())))
    i = next(i for i, r in enumerate(rows) if r["sampled_on"] == "2026-06-01" and r["determinand"] == "ecoli")
    assert rows[i]["result"] == "649"
    rows[i]["result"] = "64"
    problems = ps.check_waterhead(doc, ps.to_csv(rows))
    assert problems[0].endswith("run `partner_samples.py waterhead`")
    assert "2026-06-01 ecoli: file has '64', the export 649" in problems
