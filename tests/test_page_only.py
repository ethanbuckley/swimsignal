"""A page-only build (docs/PAGE-ONLY-BUILDS-2026-11.md): a push to main that changes only what the pages are made
from writes the pages over the last build's published site and does not forecast again. The danger is a wrong yes,
which would leave a forecast change unpublished until the next scheduled build, so everything here is about the
no: what scripts/page_only.py refuses, that the paths it allows are read by the pages alone, that
build_site.rebuild_pages refuses a state or settings that are not the published forecast's, and that site.yml
builds in full on any no."""
import ast
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import page_only as po  # noqa: E402

BUILD_SRC = (ROOT / po.BUILD_SCRIPT).read_text()
WF = (ROOT / ".github" / "workflows" / "site.yml").read_text()
JOB = WF.split("\n  build:\n", 1)[1].split("\n  deploy:\n", 1)[0]


def _step(name: str) -> str:
    return JOB.split(f"      - name: {name}\n", 1)[1].split("\n      - ", 1)[0]


# ---- the paths ----

def test_page_sources_alone_are_a_page_only_change():
    ok, why = po.verdict(["src/dipcast/site/index.html", "src/dipcast/site/preview/home.js", "src/dipcast/pages/about.html",
                          "scripts/prerender_spots.js", "src/dipcast/pages/fonts/x.woff2", "src/dipcast/site/icons/icon.svg",
                          "docs/DESIGN.md", "tests/test_x.py", "README.md", "scripts/preview_redesign.py"])
    assert ok, why


@pytest.mark.parametrize("path", [
    "src/dipcast/model/forecast.py", "src/dipcast/cards.py", "src/dipcast/config.py", "spots.csv", "spots-osm.csv",
    "data/raw/overflow_joins.csv", "data/processed/lead_calibration.json", "data/research/research_catalogue.v1.json",
    "guides/openings/openings.toml", "prototypes/research-lab/index.html", "scripts/build_any_point.py",
    "scripts/lab_pollution_paths.py", ".github/workflows/site.yml", "pyproject.toml", "uv.lock", "a-new-file.txt",
    "src/dipcast/site/levels.js", "scripts/alerts.js"])   # the last two: the level rules, a full build by choice
def test_anything_else_is_a_full_build(path):
    ok, why = po.verdict(["src/dipcast/site/index.html", path])
    assert not ok and path in " ".join(why)


def test_no_changed_file_is_a_full_build():
    assert po.verdict([])[0] is False


def test_the_build_script_changed_and_unread_is_a_full_build():
    assert po.verdict([po.BUILD_SCRIPT])[0] is False
    assert po.verdict([po.BUILD_SCRIPT], None, BUILD_SRC)[0] is False


# ---- scripts/build_site.py, by definition ----

SMALL = '''
import os
from lib import forecast_point, render
LIMIT = 10
TEMPLATE = "index.html"
SOURCES = [TEMPLATE]
SOURCES.append("levels.js")
def site_url(): return os.environ.get("URL", "")
def health(results): return len(results) < LIMIT
def write_alerts(site): return render(site, "alerts")
def write_spot_cards(site): return {}
def write_cards(site): return {}
def write_lab_refresh(site): return {}
def stamp(): return hash(tuple(SOURCES))
def write_pages(site, results):
    """Every page."""
    return render(site, TEMPLATE, stamp(), site_url())
def write_site_pages(site, results): return write_pages(site, results)
def rebuild_pages(site):
    write_alerts(site); write_spot_cards(site); write_site_pages(site, []); write_cards(site); write_lab_refresh(site)
def build():
    results = [forecast_point(1, 2)]
    health(results)
    write_alerts("site"); write_spot_cards("site"); write_site_pages("site", results); write_cards("site")
    write_lab_refresh("site")
    return site_url()
'''


def _edit(old: str, new: str) -> tuple[bool, str]:
    assert old in SMALL
    return po.build_script_verdict(SMALL, SMALL.replace(old, new))


@pytest.mark.parametrize("old, new", [
    ('return render(site, TEMPLATE, stamp(), site_url())', 'return render(site, TEMPLATE, stamp(), site_url(), "new")'),   # a page writer
    ('def stamp(): return hash(tuple(SOURCES))', 'def stamp(): return hash(tuple(sorted(SOURCES)))'),   # what only it calls
    ('TEMPLATE = "index.html"', 'TEMPLATE = "home.html"'),                                              # a constant only the pages read
    ('SOURCES.append("levels.js")', 'SOURCES.append("levels.js")\nSOURCES.append("plan.js")'),          # a statement that binds nothing
    ('def write_alerts(site): return render(site, "alerts")', 'def write_alerts(site): return render(site, "alerts", 2)'),  # run again
    ('def write_cards(site): return {}', 'def write_cards(site): return {"a": 1}'),
    ('    """Every page."""', '    """Every page, and the sitemap."""   # a comment'),                   # words, not code
])
def test_a_change_the_forecast_half_cannot_reach_is_page_only(old, new):
    ok, why = _edit(old, new)
    assert ok, why


@pytest.mark.parametrize("old, new, name", [
    ('results = [forecast_point(1, 2)]', 'results = [forecast_point(1, 3)]', "build"),                 # the forecast itself
    ('def health(results): return len(results) < LIMIT', 'def health(results): return len(results) <= LIMIT', "health"),
    ('LIMIT = 10', 'LIMIT = 12', "LIMIT"),                                                             # a constant it reads
    ('def site_url(): return os.environ.get("URL", "")', 'def site_url(): return os.environ.get("URL", "/")', "site_url"),   # both halves use it
    ('from lib import forecast_point, render', 'from lib2 import forecast_point, render', "forecast_point"),   # an import it uses
    ('def health(results): return len(results) < LIMIT', '', "health"),                                # removed
    ('LIMIT = 10', 'LIMIT = 10\nLIMIT += 1', "LIMIT"),                                                  # bound again
    ('SOURCES.append("levels.js")', 'SOURCES.append("levels.js")\nos.environ.setdefault("URL", "x")', "os"),   # a loose statement on a name it uses
])
def test_a_change_the_forecast_half_can_reach_is_a_full_build(old, new, name):
    ok, why = _edit(old, new)
    assert not ok and name in why


def test_a_function_new_to_the_forecast_half_is_a_full_build():
    ok, why = _edit('    health(results)\n', '    health(results)\n    stamp()\n')
    assert not ok


@pytest.mark.parametrize("old, new, word", [
    ('write_cards(site); write_lab_refresh(site)\ndef build', 'write_lab_refresh(site)\ndef build', "write_cards"),   # rebuild_pages lost a step
    ('def stamp(): return hash(tuple(SOURCES))', 'def stamp(): return globals()["SOURCES"]', "globals"),
    ('def stamp(): return hash(tuple(SOURCES))', 'def stamp(: return 1', "could not be read"),
    ('def rebuild_pages(site):', 'def rebuild_all(site):', "rebuild_pages"),
])
def test_a_build_script_this_cannot_follow_is_a_full_build(old, new, word):
    ok, why = _edit(old, new)
    assert not ok and word in why


def test_the_same_script_twice_changes_nothing():
    assert po.changed_names(po.Module(BUILD_SRC), po.Module(BUILD_SRC)) == set()
    assert po.build_script_verdict(BUILD_SRC, BUILD_SRC)[0]


# ---- the real build script: the assumptions the paths rest on ----

MOD = po.Module(BUILD_SRC)
FORECAST = MOD.reach(po.FULL_ENTRY, po.RERUN)


def test_the_real_script_can_be_followed_and_rebuild_pages_runs_every_step_again():
    assert MOD.unreadable == []
    assert set(po.RERUN) <= MOD.reach(po.PAGES_ENTRY)
    assert set(po.RERUN) <= MOD.reach(po.FULL_ENTRY)   # and each is a step of the full build


def test_the_forecast_half_reads_no_page_source():
    # TEMPLATE is src/dipcast/site/index.html and STATIC src/dipcast/pages: every other page source in the script
    # is built from one of them. If the forecast half reached either, a change under PAGE_DIRS could change the data.
    assert "TEMPLATE" not in FORECAST and "STATIC" not in FORECAST
    assert {"write_pages", "write_site_pages", "spot_page", "write_preview", "shell_stamp"}.isdisjoint(FORECAST)
    # rebuild_pages itself is in it (the script's last lines name it beside build), so a change to how a page-only
    # build works is published by a full one.
    assert "rebuild_pages" in FORECAST
    assert {"build", "prefetch_rain", "build_health", "write_app_data", "write_upstream"} <= FORECAST
    tree = ast.parse(BUILD_SRC)
    named = lambda s: s in ("pages", "docs") or bool(re.fullmatch(r"prerender_\w+\.js", s))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FORECAST:
            found = [c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str) and named(c.value)]
            assert not found, f"{node.name}() in the forecast half names a page source: {found}"


# The modules outside the script that read a page source, and the functions of each that do. Every use of them in
# the script must be on the pages' side. A module new to this list fails the first test below: decide which side
# reads it before adding it.
READERS = {"cards": "RERUN", "signs": "pages", "overflow_record": "pages", "profile": "pages", "quality": "pages"}
SOURCE_DIRS = ("site", "pages", "docs")


def _path_parts(tree: ast.AST) -> set[str]:
    """The strings joined to a path with / in a module: Path(...) / "site" / "sign.html" gives both."""
    return {n.right.value for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
            and isinstance(n.right, ast.Constant) and isinstance(n.right.value, str)}


def test_the_modules_that_read_page_sources_are_the_known_ones():
    found = set()
    for f in sorted((ROOT / "src" / "dipcast").rglob("*.py")):
        if set(SOURCE_DIRS) & _path_parts(ast.parse(f.read_text())):
            found.add(f.stem)
    assert found == set(READERS)


def test_the_forecast_half_uses_none_of_those_modules():
    tree = ast.parse(BUILD_SRC)
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in FORECAST:
            continue
        for n in ast.walk(node):
            mods = []
            if isinstance(n, ast.ImportFrom) and n.module:
                mods = [n.module.split(".")[-1], *[a.name for a in n.names]] if n.module.startswith("dipcast") else []
            elif isinstance(n, ast.Import):
                mods = [a.name.split(".")[-1] for a in n.names]
            hit = set(mods) & set(READERS)
            assert not hit, f"{node.name}() in the forecast half imports {hit}, which reads the page sources"
    # and at the top of the file, where an import is a name the forecast half would have to reach
    for name, side in READERS.items():
        assert name not in FORECAST, f"{name} ({side}) is imported at the top and the forecast half reaches it"


def test_what_is_called_not_read_is_named_nowhere_in_the_build():
    for p in po.NOT_READ:
        if p.endswith("/") or p in (".gitignore", "README.md"):
            continue
        assert Path(p).stem not in BUILD_SRC and p not in WF, f"{p} is named by the build"
    assert '"tests"' not in BUILD_SRC and "'tests'" not in BUILD_SRC


def test_a_real_page_writer_and_a_real_forecast_step():
    old = 'def robots(root: str) -> str:\n'
    assert old in BUILD_SRC and "robots" not in FORECAST
    ok, why = po.build_script_verdict(BUILD_SRC, BUILD_SRC.replace(old, old + "    root = root.strip()\n"))
    assert ok, why
    old = "def prefetch_rain(spots"
    assert old in BUILD_SRC
    i = BUILD_SRC.index(":\n", BUILD_SRC.index(old)) + 2
    ok, why = po.build_script_verdict(BUILD_SRC, BUILD_SRC[:i] + "    spots = spots.head(10)\n" + BUILD_SRC[i:])
    assert not ok and "prefetch_rain" in why


# ---- how old the kept forecast may be ----

def test_only_a_young_forecast_is_kept(tmp_path):
    now = datetime(2026, 11, 24, 20, 0, tzinfo=UTC)
    f = tmp_path / "spots.json"
    for minutes, keep in ((5, True), (po.MAX_AGE_MIN - 1, True), (po.MAX_AGE_MIN, False), (600, False), (-5, False)):
        f.write_text(json.dumps({"generated_at": (now - timedelta(minutes=minutes)).isoformat()}))
        assert po.young_enough(f, now)[0] is keep, minutes
    f.write_text(json.dumps({"generated_at": "2026-11-24T19:55:00"}))   # no zone: not known to be young
    assert po.young_enough(f, now)[0] is False
    f.write_text("{}")
    assert po.young_enough(f, now)[0] is False
    assert po.young_enough(tmp_path / "missing.json", now)[0] is False
    # BST and UTC are the same moment
    f.write_text(json.dumps({"generated_at": "2026-11-24T19:55:00+00:00"}))
    assert po.young_enough(f, now)[0] is True


# ---- build_site.rebuild_pages ----

GENERATED = "2026-11-24T19:46:42.814270+00:00"
SPOTS = [{"id": "warleigh-weir", "name": "Warleigh Weir", "kind": "river", "upstream_summary": {"overflows": 3}, "days": []}]


@pytest.fixture
def bs(monkeypatch, tmp_path):
    import build_site
    from dipcast import reviews
    for k in [k for k in __import__("os").environ if k.startswith("DIPCAST_")]:
        monkeypatch.delenv(k)
    monkeypatch.setattr(build_site, "_overflows", lambda: None)   # the river network is not in the repository
    monkeypatch.setattr(reviews, "CACHE", tmp_path / "reviews-cache")
    return build_site


def _published(bs, site: Path) -> Path:
    """A small published site as build() leaves one: the data, then the pages, then what is written after them."""
    (site / "data").mkdir(parents=True)
    doc = {"generated_at": GENERATED, "commit": "abc1234", "credits": bs.data_credits(bs.site_url()), "spots": SPOTS}
    (site / "data" / "spots.json").write_text(json.dumps(doc))
    for name in ("coastal", *bs.NATIONS):
        (site / "data" / f"{name}.json").write_text(json.dumps({"state": "ok", "sites": []}))
    import pandas as pd
    generated = pd.Timestamp(GENERATED)   # the steps below in build()'s order
    alerts_ok = bs.write_alerts(site, bs.site_url(), False)
    cards = bs.write_spot_cards(site, SPOTS, generated.isoformat(), alerts_ok)
    bs.write_site_pages(site, SPOTS, generated, cards, coastal={"state": "ok", "sites": []},
                        **{n: {"state": "ok", "sites": []} for n in bs.NATIONS})
    from dipcast.reviews import write_reviews
    write_reviews(site, spot_ids=[r["id"] for r in SPOTS], fetch=False)
    bs.write_cards(site, SPOTS, generated.isoformat(), bs.site_url(), alerts_ok)
    (site / "data" / "since-last.json").write_text("{}")
    note = site.parent / "site_build.json"
    note.write_text(json.dumps({"generated_at": GENERATED, "settings": bs.build_settings()}))
    return note


def _files(site: Path) -> dict[str, bytes]:
    return {str(f.relative_to(site)): f.read_bytes() for f in sorted(site.rglob("*")) if f.is_file()}


def test_rebuild_pages_writes_the_pages_a_build_wrote_and_leaves_the_data(tmp_path, bs):
    site = tmp_path / "site"
    note = _published(bs, site)
    before = _files(site)
    out = bs.rebuild_pages(site, built=note)
    after = _files(site)
    assert out["pages_only"] is True and out["generated_at"] == GENERATED and out["spot_pages"] == 1
    assert set(before) == set(after)
    differ = {k for k in before if before[k] != after[k]}
    # The two files that carry the time they were written: the Lab's dates and the reviews' list.
    assert differ <= {"lab/refresh.json", "reviews/index.json"}, differ
    assert len(before) > 300 and "spot/warleigh-weir/index.html" in before and "data/alerts.json" in before
    assert json.loads(after["data/spots.json"])["generated_at"] == GENERATED   # the forecast's own issue time
    assert "since-last.json" not in after["data.html"].decode()   # as in a build, which writes it after the page


@pytest.mark.parametrize("spoil, word", [
    (lambda site, note, mp: (site / "data" / "spots.json").unlink(), "cannot be read"),
    (lambda site, note, mp: (site / "data" / "wales.json").write_text("not json"), "cannot be read"),
    (lambda site, note, mp: note.unlink(), "no note"),
    (lambda site, note, mp: note.write_text(json.dumps({**json.loads(note.read_text()), "generated_at": "2026-11-24T21:00:00+00:00"})), "the state is the forecast of"),
    (lambda site, note, mp: mp.setenv("DIPCAST_RIVER_WINTER_LINE", "1"), "setting has changed"),
    (lambda site, note, mp: mp.setenv("DIPCAST_REDESIGN", "1"), "setting has changed"),
])
def test_rebuild_pages_refuses_before_it_writes_anything(tmp_path, bs, monkeypatch, spoil, word):
    site = tmp_path / "site"
    note = _published(bs, site)
    spoil(site, note, monkeypatch)
    before = _files(site)
    with pytest.raises(bs.PagesOnlyUnsafe, match=word):
        bs.rebuild_pages(site, built=note)
    assert _files(site) == before


def test_the_settings_hash_holds_no_secret_and_ignores_the_machine(bs, monkeypatch):
    base = bs.build_settings()
    monkeypatch.setenv("DIPCAST_STATE", "/somewhere/else")
    monkeypatch.setenv("DIPCAST_ROOT", "/somewhere")
    monkeypatch.setenv("DIPCAST_KOFI_URL", "  ")   # set and empty is unset, as the build reads it
    assert bs.build_settings() == base
    monkeypatch.setenv("DIPCAST_OPEN_METEO_KEY", "one-key")
    with_key = bs.build_settings()
    monkeypatch.setenv("DIPCAST_OPEN_METEO_KEY", "another-key")
    assert with_key == bs.build_settings() != base   # that it is set, never what it is
    monkeypatch.setenv("DIPCAST_TILES", "stadia")
    assert bs.build_settings() != with_key


def test_only_a_build_that_forecast_leaves_the_note():
    src = BUILD_SRC[BUILD_SRC.index("def build(refresh"):]
    i = src.index("config.state_write(BUILT_FILE)")
    assert src[:i].rstrip().endswith("if refresh:   # what rebuild_pages checks before it writes pages from this build's data")
    assert BUILD_SRC.count("state_write(BUILT_FILE)") == 1


# ---- site.yml ----

PLAN, FETCH, BUILD = "Can this push rebuild the pages only?", "Fetch the last build's published site (page-only build)", "Build forecasts and site"


def test_only_a_push_to_main_is_ever_page_only():
    plan = _step(PLAN)
    assert re.search(r"^        if: github\.event_name == 'push' && github\.ref == 'refs/heads/main'$", plan, re.M)
    assert re.search(r"^        if: steps\.plan\.outputs\.run != ''$", _step(FETCH), re.M)
    assert "PAGES_ONLY: ${{ steps.published.outputs.ready }}" in _step(BUILD)


def test_every_no_and_every_failure_is_the_full_build():
    plan, fetch, build = _step(PLAN), _step(FETCH), _step(BUILD)
    for step in (plan, fetch):   # a step that fails writes no output; the job goes on to the full build
        assert re.search(r"^        continue-on-error: true\b", step, re.M)
        assert step.count(">> \"$GITHUB_OUTPUT\"") == 1 and step.rstrip().endswith('>> "$GITHUB_OUTPUT"')
    assert 'python3 scripts/page_only.py changes "$base" "$GITHUB_SHA" || full' in plan
    assert '[ "$cmp" = "ahead 0" ] || full' in plan   # the last build's commit is an ancestor of this one
    assert "python3 scripts/page_only.py age site/data/spots.json || full" in fetch
    run = build.split("        run: |\n", 1)[1]
    pages, full = run.index("scripts/build_site.py --pages-only"), run.rindex("uv run python scripts/build_site.py")
    assert pages < run.index("rm -rf site") < full   # nothing of the fetched site is left under a full build
    assert run.rstrip().endswith("uv run python scripts/build_site.py")


def test_a_page_only_build_saves_and_publishes_no_state():
    save = JOB.split("      - name: Save mutable state\n", 1)[1].split("\n      - ", 1)[0]
    assert "if: always() && steps.build.outputs.pages_only != 'true'" in save
    publish = JOB.split("      - name: Publish state to the rolling release", 1)[1].split("\n      - ", 1)[0]
    assert "if: steps.build.outputs.pages_only != 'true'" in publish


def test_the_tests_are_skipped_only_for_the_same_files():
    ask = _step("Did Test Python already pass this commit on main?")
    for needed in ('[ "$np" = 2 ]', '--jq .commit.tree.sha)" = "$tree" ]', 'compare/$p1...$p2" --jq .behind_by)" = 0 ]',
                   "head_sha=$p2&event=pull_request&status=success"):
        assert needed in ask, needed
