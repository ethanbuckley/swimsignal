"""Every EA E. coli sample at a bathing water on the site (build_site.write_ecoli_evidence, attach_sample_history,
samples.html): the research export (docs/ECOLI-EVIDENCE-CONTRACT-v1.md) split into an index and one file a bathing
water, published only when it is that contract's schema and major version, and the viewer written beside the app."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "ecoli_evidence_v1_sample.json"
SPOTS = [{"id": "bw-uke4100-08901", "name": "Wharfe at Cromwheel", "kind": "river", "days": [],
          "classification": {"class": "poor", "year": 2025, "url": "https://environment.data.gov.uk/bwq/profiles/profile.html?site=uke4100-08901"}},
         {"id": "tarn", "name": "Tarn", "kind": "lake", "days": []}]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_export_is_split_into_an_index_and_a_file_a_bathing_water(tmp_path):
    bs = _build_site()
    h = bs.write_ecoli_evidence(tmp_path, SAMPLE, SPOTS)
    assert h == {"available": True, "sites": 4, "skipped_ids": 0, "version": "1.0.0"}
    index = json.loads((tmp_path / "data" / "research" / "ecoli.json").read_text())
    assert index["available"] is True and index["schema"] == "swimsignal.ecoli-evidence"
    # The index carries what the list, the claim and the official link need, never the samples.
    assert {"claim", "hindsight", "line", "warn_at", "attribution", "coverage"} <= set(index)
    assert index["hindsight"]["issued"] is False
    for x in index["sites"]:
        assert "samples" not in x and {"spot_id", "bw_id", "name", "kind", "summary", "profile"} <= set(x)
        assert x["profile"] == f"https://environment.data.gov.uk/bwq/profiles/profile.html?site={x['bw_id']}"
    # This build's rating, where the build has one; none for a bathing water the build did not rate.
    rated = {x["spot_id"]: x.get("rating") for x in index["sites"]}
    assert rated["bw-uke4100-08901"] == {"class": "poor", "year": 2025} and rated["bw-ukd1101-45800"] is None
    whole = json.loads(SAMPLE.read_text())["sites"][1]
    one = json.loads((tmp_path / "data" / "research" / "ecoli" / f"{whole['spot_id']}.json").read_text())
    assert one == whole   # one bathing water, exactly as exported


def test_nothing_is_published_from_a_missing_or_foreign_export(tmp_path):
    bs = _build_site()
    bs.write_ecoli_evidence(tmp_path, SAMPLE)
    assert bs.write_ecoli_evidence(tmp_path, tmp_path / "none.json") == {"available": False, "why": "no export in this build"}
    assert not list((tmp_path / "data" / "research" / "ecoli").iterdir())   # nothing left from an earlier build
    other = tmp_path / "v2.json"
    other.write_text(json.dumps({**json.loads(SAMPLE.read_text()), "version": "2.0.0"}))
    h = bs.write_ecoli_evidence(tmp_path, other)
    assert h["available"] is False and "not swimsignal.ecoli-evidence 1.x" in h["why"]
    assert json.loads((tmp_path / "data" / "research" / "ecoli.json").read_text())["available"] is False
    assert not list((tmp_path / "data" / "research" / "ecoli").iterdir())
    # A later minor version is read; another schema is not.
    minor = tmp_path / "v1_3.json"
    minor.write_text(json.dumps({**json.loads(SAMPLE.read_text()), "version": "1.3.0"}))
    assert bs.write_ecoli_evidence(tmp_path, minor)["available"] is True
    foreign = tmp_path / "lakes.json"
    foreign.write_text(json.dumps({**json.loads(SAMPLE.read_text()), "schema": "swimsignal.lake-observations"}))
    assert bs.write_ecoli_evidence(tmp_path, foreign)["available"] is False


def test_only_its_own_files_are_cleared(tmp_path):
    """data/research/ may hold another research export's files (the lake observations, PR #470): they are left."""
    bs = _build_site()
    (tmp_path / "data" / "research" / "lake").mkdir(parents=True)
    (tmp_path / "data" / "research" / "lakes.json").write_text("{}")
    bs.write_ecoli_evidence(tmp_path, tmp_path / "none.json")
    assert (tmp_path / "data" / "research" / "lakes.json").exists() and (tmp_path / "data" / "research" / "lake").is_dir()


def test_a_bathing_water_in_the_export_gets_its_sample_history_in_its_own_file(tmp_path):
    bs = _build_site()
    results = [dict(s) for s in SPOTS]
    assert bs.attach_sample_history(results, SAMPLE) == 1
    assert results[0]["sample_history"] == {"first": "2023-05-03", "last": "2026-09-24", "samples": 80}
    assert "sample_history" not in results[1]
    assert "sample_history" in bs.DETAIL_FIELDS   # the spot's own file, not the list's
    assert bs.attach_sample_history([dict(s) for s in SPOTS], tmp_path / "none.json") is None


def test_the_viewer_is_written_beside_the_app(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    page = (tmp_path / "samples.html").read_text()
    assert "<title>E. coli samples · SwimSignal</title>" in page and '<script src="samples.js?v=' in page
    assert (tmp_path / "samples.js").read_bytes() == (bs.TEMPLATE.parent / "samples.js").read_bytes()
    assert "<loc>https://example.org/samples.html</loc>" in (tmp_path / "sitemap.xml").read_text()
    # Written before the data page, which then lists data/research/ with its size, not "Not in this build".
    assert (tmp_path / "data" / "research" / "ecoli.json").exists()
    data = (tmp_path / "data.html").read_text()
    row = data.split('<tr data-file="research/">', 1)[1].split("</tr>", 1)[0]
    assert "Not in this build" not in row and 'href="samples.html"' in data
    # The header and foot are the other prose pages' (sites.html's), exactly.
    sites = (bs.TEMPLATE.parent / "sites.html").read_text()
    src = (bs.TEMPLATE.parent / "samples.html").read_text()
    for part in ('<header class="top">', '<footer class="site-foot">'):
        mine, theirs = src.split(part, 1)[1], sites.split(part, 1)[1]
        end = "</header>" if part.startswith("<header") else "</footer>"
        assert mine.split(end, 1)[0] == theirs.split(end, 1)[0], part
