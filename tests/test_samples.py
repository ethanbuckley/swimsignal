"""Lab results an organisation sends (src/dipcast/samples.py, samples/README.md): the format's checks; the
split by permission, so nothing without publish = true reaches samples/ or spots.json; the build's
window; the page's script in the build; and the pairing with the forecast log (scripts/evaluate_samples.py)."""

import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from dipcast import config, forecast_log
from dipcast import samples as sm

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 20, 17, 0, tzinfo=sm.UK)
SPOT = "bw-uke4100-08901"   # Wharfe at Cromwheel, Ilkley


def _script(name: str):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


def row(**kw) -> dict:
    r = {"spot_id": SPOT, "sampled_at": "2026-10-17 08:30", "timezone": "Europe/London", "ecoli_per_100ml": "1200",
         "enterococci_per_100ml": "<10", "lab": "Example Water Lab", "ukas_accredited": "yes", "method": "",
         "lab_ref": "L-1", "supplier": "Example Swim Club", "received": "2026-10-19", "publish": "", "evaluate": ""}
    return r | kw


def parse(**kw):
    return sm.parse_row(row(**kw), {SPOT}, NOW)


def test_a_good_row_is_stored_with_its_offset_and_both_permissions_off_by_default():
    r = parse()
    assert r["sampled_at"] == "2026-10-17T08:30+01:00"
    assert (r["publish"], r["evaluate"]) == ("false", "false")
    assert r["_ecoli"] == (1200, "") and r["_ent"] == (10, "<")
    assert parse(sampled_at="17/10/2026 08:30")["sampled_at"] == "2026-10-17T08:30+01:00"   # a UK lab's day first
    assert parse(sampled_at="2026-02-01 08:30", received="2026-02-02")["sampled_at"] == "2026-02-01T08:30+00:00"   # GMT in winter
    # A lab system on GMT all year: 07:30 UTC in October is 08:30 on the UK clock.
    assert parse(sampled_at="2026-10-17 07:30", timezone="UTC")["_at"] == parse()["_at"]
    assert parse(ecoli_per_100ml="1,200")["ecoli_per_100ml"] == "1200"
    assert parse(ecoli_per_100ml="> 24196")["ecoli_per_100ml"] == ">24196"


@pytest.mark.parametrize("kw, message", [
    ({"spot_id": "nowhere"}, "no spot has the id"),
    ({"spot_id": "a b"}, "not a spot id"),
    ({"timezone": "BST"}, "timezone must be"),
    ({"sampled_at": "2026-10-17"}, "a date and a time"),
    ({"sampled_at": "2026-10-21 08:30", "received": "2026-10-20"}, "in the future"),
    ({"received": "2026-10-16"}, "before the sample was taken"),
    ({"received": "2026-10-21"}, "received 2026-10-21 is in the future"),
    ({"sampled_at": "2026-05-01 08:30"}, "check the year"),
    ({"ecoli_per_100ml": "", "enterococci_per_100ml": ""}, "neither"),
    ({"ecoli_per_100ml": "12 cfu"}, "count per 100 ml"),
    ({"ecoli_per_100ml": "<0"}, "not a count"),
    ({"ecoli_per_100ml": "20000000"}, "extra nought"),
    ({"ukas_accredited": "certified"}, "ukas_accredited must be"),
    ({"supplier": ""}, "supplier"),
    ({"publish": "maybe"}, "publish must be true or false"),
    ({"colour": "blue"}, "unknown column"),
    # The clocks go back at 02:00 on 25 Oct 2026: 01:30 happens twice. They went forward at 01:00 on 29 Mar.
    ({"sampled_at": "2026-10-25 01:30", "received": "2026-10-25"}, "happened twice"),
    ({"sampled_at": "2026-03-29 01:30", "received": "2026-03-30"}, "does not exist"),
    ({"sampled_at": "2026-10-17 08:30+00:00"}, "is not Europe/London's"),
])
def test_rows_that_break_the_format_are_refused_with_the_reason(kw, message):
    now = datetime(2026, 10, 26, 12, tzinfo=sm.UK) if "2026-10-25" in kw.get("sampled_at", "") else NOW
    with pytest.raises(sm.SampleError, match=message):
        sm.parse_row(row(**kw), {SPOT}, now)


def test_an_offset_settles_the_hour_the_clocks_go_back_and_old_samples_need_asking():
    now = datetime(2026, 10, 26, 12, tzinfo=sm.UK)
    first = sm.parse_row(row(sampled_at="2026-10-25 01:30+01:00", received="2026-10-25"), {SPOT}, now)
    second = sm.parse_row(row(sampled_at="2026-10-25 01:30+00:00", received="2026-10-25"), {SPOT}, now)
    assert second["_at"] - first["_at"] == timedelta(hours=1)
    assert sm.parse_row(row(sampled_at="2026-05-01 08:30"), {SPOT}, NOW, allow_old=True)["sampled_at"] == "2026-05-01T08:30+01:00"


def test_the_private_folder_is_never_inside_the_public_repository(tmp_path, monkeypatch):
    with pytest.raises(sm.SampleError, match="inside the public repository"):
        sm.private_dir(config.ROOT / "samples" / "private")
    monkeypatch.setenv(sm.PRIVATE_ENV, str(tmp_path / "p"))
    assert sm.private_dir() == (tmp_path / "p").resolve()
    monkeypatch.delenv(sm.PRIVATE_ENV)
    assert sm.private_dir() == sm.PRIVATE_DEFAULT.resolve()


def _three(tmp_path) -> tuple[Path, Path, list[dict]]:
    rows = [sm.parse_row(row(sampled_at=f"2026-10-{d} 08:30", publish=p, evaluate=e, lab_ref=f"L-{d}"), {SPOT}, NOW)
            for d, p, e in (("17", "true", "false"), ("18", "false", "true"), ("19", "false", "false"))]
    return tmp_path / "private", tmp_path / "public", rows


def test_only_rows_with_publish_reach_the_public_file_and_without_their_private_columns(tmp_path):
    private, public, rows = _three(tmp_path)
    assert sm.write_supplier(private, public, "example-swim-club", rows) == 1
    with (private / "example-swim-club.csv").open() as fh:
        assert len(list(csv.DictReader(fh))) == 3
    text = (public / "example-swim-club.csv").read_text()
    assert text.splitlines()[0] == ",".join(sm.PUBLIC_COLUMNS)
    assert "2026-10-17T08:30" in text and "2026-10-18T08:30" not in text and "2026-10-19T08:30" not in text
    assert "L-17" not in text and "lab_ref" not in text and "evaluate" not in text and "publish" not in text


def test_taking_back_publish_in_the_private_file_takes_the_row_out_on_sync(tmp_path):
    private, public, rows = _three(tmp_path)
    sm.write_supplier(private, public, "example-swim-club", rows)
    p = private / "example-swim-club.csv"
    p.write_text(p.read_text().replace("true,false\n", "false,false\n"))   # the 17th's publish taken back
    assert sm.sync_public(private, public, {SPOT}, NOW) == {"example-swim-club": 0}
    assert not (public / "example-swim-club.csv").exists()   # nothing left to publish: no public file
    with pytest.raises(sm.SampleError, match="no private folder"):
        sm.sync_public(tmp_path / "elsewhere", public)


def test_the_intake_script_checks_everything_before_writing_and_splits_by_permission(tmp_path, capsys):
    add = _script("add_samples")
    private, public = tmp_path / "private", tmp_path / "public"
    lab = tmp_path / "lab.csv"
    lab.write_text("Sample point,Date/time sampled,E. coli,Lab ref,Client\n"
                   f"{SPOT},17/10/2026 08:30,1200,L-1,Example Swim Club\n"
                   f"{SPOT},10/10/2026 08:10,>24196,L-2,Example Swim Club\n")
    base = ["--private", str(private), "--public", str(public), "--supplier", "Example Swim Club", "--received", "2026-10-20",
            "--column", "spot_id=Sample point", "--column", "sampled_at=Date/time sampled", "--column", "ecoli_per_100ml=E. coli",
            "--column", "lab_ref=Lab ref"]
    assert add.main([*base, "--evaluate", "--dry-run", str(lab)]) == 0
    assert not private.exists() and not public.exists()
    assert "Ignored, not in the format: Client" in capsys.readouterr().out
    assert add.main([*base, "--evaluate", str(lab)]) == 0                      # agreed to testing only
    assert (private / "example-swim-club.csv").exists() and not (public / "example-swim-club.csv").exists()
    assert add.main([*base, str(lab)]) == 1                                      # the same samples again
    assert "already in example-swim-club.csv" in capsys.readouterr().err
    typed = ["--private", str(private), "--public", str(public), "--supplier", "Example Swim Club", "--received", "2026-10-20",
             "--publish", "--spot", SPOT, "--sampled", "2026-10-18 09:00", "--ecoli", "40", "--lab", "Example Water Lab", "--ukas", "yes"]
    assert add.main(typed) == 0
    pub = (public / "example-swim-club.csv").read_text()
    assert pub.count("\n") == 2 and "2026-10-18T09:00+01:00" in pub and "Example Water Lab,yes" in pub


def test_one_bad_row_writes_nothing(tmp_path, capsys):
    add = _script("add_samples")
    lab = tmp_path / "lab.csv"
    lab.write_text(f"spot_id,sampled_at,ecoli_per_100ml\n{SPOT},2026-10-17 08:30,1200\nnowhere,2026-10-17 09:30,5\n")
    args = ["--private", str(tmp_path / "private"), "--public", str(tmp_path / "public"), "--supplier", "S", "--received", "2026-10-20", "--publish"]
    assert add.main([*args, str(lab)]) == 1
    assert "row 2: no spot has the id 'nowhere'" in capsys.readouterr().err
    assert not (tmp_path / "private").exists() and not (tmp_path / "public").exists()


def _public(tmp_path, lines: list[str], name="example-swim-club") -> Path:
    root = tmp_path / "samples"
    root.mkdir(exist_ok=True)
    (root / f"{name}.csv").write_text(",".join(sm.PUBLIC_COLUMNS) + "\n" + "\n".join(lines) + "\n")
    return root


def line(at: str, ecoli="1200", ent="<10", supplier="Example Swim Club", received="2026-10-19", spot=SPOT) -> str:
    return f"{spot},{at},Europe/London,{ecoli},{ent},Example Water Lab,yes,membrane filtration,{supplier},{received}"


def test_the_build_attaches_recent_published_samples_newest_first_and_warns_on_bad_rows(tmp_path):
    root = _public(tmp_path, [line("2026-10-03T07:55+01:00", "85", "12", received="2026-10-04"),
                              line("2026-10-17T08:30+01:00"),
                              line("2026-09-10T08:00+01:00", received="2026-09-12"),           # over 30 days old
                              line("2026-10-12T08:00+01:00", spot="nowhere"),                  # no such spot
                              line("2026-10-17T08:30+01:00"),                                  # the same sample twice
                              line("2026-10-11T08:00+01:00", supplier="Another Centre")])      # not this file's
    results = [{"id": SPOT}, {"id": "other"}]
    out = sm.attach_measured(results, root, NOW)
    assert (out["spots"], out["samples"]) == (1, 2)
    assert len(out["warnings"]) == 3
    assert any("line 5" in w and "no spot" in w for w in out["warnings"])
    assert any("line 6" in w and "same spot, time and supplier" in w for w in out["warnings"])
    assert any("line 7" in w and "not this file's" in w for w in out["warnings"])
    m = results[0]["measured"]
    assert [x["sampled_at"] for x in m] == ["2026-10-17T08:30+01:00", "2026-10-03T07:55+01:00"]
    assert m[0] == {"sampled_at": "2026-10-17T08:30+01:00", "ecoli": 1200, "enterococci": 10, "enterococci_qualifier": "<",
                    "lab": "Example Water Lab", "ukas": True, "method": "membrane filtration", "supplier": "Example Swim Club",
                    "received": "2026-10-19"}
    assert "measured" not in results[1]


def test_a_public_file_with_private_columns_is_left_out_whole(tmp_path):
    root = tmp_path / "samples"
    root.mkdir()
    (root / "example-swim-club.csv").write_text(",".join(sm.COLUMNS) + "\n")
    results = [{"id": SPOT}]
    out = sm.attach_measured(results, root, NOW)
    assert out["samples"] == 0 and "left out" in out["warnings"][0] and "measured" not in results[0]


def test_at_most_ten_a_spot(tmp_path):
    root = _public(tmp_path, [line(f"2026-10-{d:02d}T08:00+01:00", received="2026-10-20") for d in range(1, 21)])
    results = [{"id": SPOT}]
    sm.attach_measured(results, root, NOW)
    assert len(results[0]["measured"]) == sm.SHOW_MAX
    assert results[0]["measured"][0]["sampled_at"].startswith("2026-10-20")


def test_the_repository_publishes_nothing_but_valid_rows():
    spots = {r["id"] for f in ("spots.csv", "spots-osm.csv") for r in csv.DictReader((ROOT / f).open())}
    _, warnings = sm.load_published(spots, ROOT / "samples")
    assert warnings == []


def test_measured_is_in_the_spot_files_and_not_the_lite_file(tmp_path):
    bs = _script("build_site")
    assert "measured" in bs.DETAIL_FIELDS
    doc = {"generated_at": "2026-10-20T17:00:00+01:00", "credits": {}, "spots": [
        {"id": SPOT, "name": "Cromwheel", "days": [], "contributors": [], "measured": [{"sampled_at": "2026-10-17T08:30+01:00", "ecoli": 5}]}]}
    bs.write_app_data(tmp_path, doc)
    lite = json.loads((tmp_path / "data" / "spots-lite.json").read_text())
    assert "measured" not in lite["spots"][0]
    assert json.loads((tmp_path / "data" / "spot" / f"{SPOT}.json").read_text())["measured"] == doc["spots"][0]["measured"]


def test_the_page_loads_the_measured_script_from_its_build(tmp_path):
    bs = _script("build_site")
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    page = (tmp_path / "index.html").read_text()
    assert f'<script src="measured.js?v={stamp}" defer>' in page
    assert page.index('src="evidence.js') < page.index('src="measured.js') < page.index('src="app.js')   # its ages are evidence.js's
    assert (tmp_path / "measured.js").read_bytes() == (bs.TEMPLATE.parent / "measured.js").read_bytes()
    assert "`measured.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "measured.js" in bs.SHELL_SOURCES


def test_the_data_page_describes_the_field_and_the_page_keeps_the_same_window():
    assert "<dt><code>measured</code></dt>" in (ROOT / "src" / "dipcast" / "pages" / "data.html").read_text()
    js = (ROOT / "src" / "dipcast" / "site" / "measured.js").read_text()
    assert f"const MEASURED_DAYS = {sm.WINDOW_DAYS};" in js


def test_evaluation_pairs_each_sample_with_the_forecasts_issued_before_it(tmp_path):
    ev = _script("evaluate_samples")
    db = tmp_path / "dipcast.duckdb"
    con = forecast_log._conn(db)   # the forecast log's own tables
    lat, lon = ev.spot_points()[SPOT]
    t = datetime.fromisoformat
    rows = [  # issued, target day, lead, p_ecoli
        (t("2026-10-16T07:40+01:00"), date(2026, 10, 17), 1, 0.30),
        (t("2026-10-16T19:40+01:00"), date(2026, 10, 17), 1, 0.35),   # the latest lead 1 before the sample
        (t("2026-10-17T07:40+01:00"), date(2026, 10, 17), 0, 0.40),   # live when the sample was taken, 08:30
        (t("2026-10-17T09:10+01:00"), date(2026, 10, 17), 0, 0.90),   # after the sample: not a forecast of it
        (t("2026-10-17T07:40+01:00"), date(2026, 10, 18), 1, 0.10),   # another day
    ]
    con.executemany("INSERT INTO forecast_points (issued_at, lat, lon, target_day, lead, p_ecoli, risk, version) VALUES (?, ?, ?, ?, ?, ?, 0.2, 'v1')",
                    [(i, lat + 0.00001, lon, d, k, p) for i, d, k, p in rows])
    con.close()
    private = tmp_path / "private"
    samples = [sm.parse_row(row(evaluate="true"), {SPOT}, NOW),                                         # paired
               sm.parse_row(row(sampled_at="2026-10-15 08:30", evaluate="true", ecoli_per_100ml="<1000"), {SPOT}, NOW),  # no forecast
               sm.parse_row(row(sampled_at="2026-10-17 09:00", evaluate="false", publish="true"), {SPOT}, NOW)]  # not for testing
    sm.write_supplier(private, tmp_path / "public", "example-swim-club", samples)
    out = tmp_path / "pairs.csv"
    assert ev.main(["--db", str(db), "--private", str(private), "--out", str(out)]) == 0
    got = list(csv.DictReader(out.open()))
    assert {r["sampled_at"] for r in got} == {"2026-10-17T08:30+01:00", "2026-10-15T08:30+01:00"}   # never the evaluate=false one
    paired = sorted((r for r in got if r["lead"]), key=lambda r: r["lead"])
    assert [(r["lead"], r["p_ecoli"], r["live_at_sample"]) for r in paired] == [("0", "0.4", "True"), ("1", "0.35", "False")]
    assert paired[0]["issued_at"] == "2026-10-17T07:40+01:00" and paired[0]["over_900"] == "1"
    gap = next(r for r in got if r["sampled_at"].startswith("2026-10-15"))
    assert gap["lead"] == "" and gap["over_900"] == ""   # "<1000" does not settle it
    assert ev.over_900((900, "")) == 0 and ev.over_900((900, ">")) == 1 and ev.over_900((10, "<")) == 0
