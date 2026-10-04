"""What the level rests on (src/dipcast/site/evidence.js): the two fields the build passes through for
it. The latest EA lab sample at each bathing water, read from the samples the live scoring already
holds (no request of its own), and how many overflows upstream are not reporting because their company
has no live feed. The page's words are tested in tests/site_evidence.test.cjs."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def _samples(tmp_path):
    from dipcast import forecast_log as fl
    t = pd.to_datetime(["2026-09-17 10:05", "2026-09-24 10:35", "2026-09-23 11:00", "2026-09-24 09:50"]).tz_localize("Europe/London")
    pd.DataFrame({"bw_id": ["uke4100-08901", "uke4100-08901", "ukh1201-09801", "ukd1203-45650"], "name": "n", "kind": "river",
                  "sample_time": t, "ecoli": [1500.0, 380.0, 10.0, None], "ecoli_qual": ["=", "=", "<", "="],
                  "source": "archive"}).to_parquet(tmp_path / fl.ECOLI_SAMPLES, index=False)


def test_latest_samples_reads_the_held_file_and_never_fetches(tmp_path, monkeypatch):
    from dipcast import config
    from dipcast import forecast_log as fl
    monkeypatch.setattr(config, "STATE", tmp_path)

    def no_fetch(*a, **k):
        raise AssertionError("the page's lab sample must not make a request")
    monkeypatch.setattr("dipcast.ingest.wqa.fetch_ecoli", no_fetch)
    monkeypatch.setattr("dipcast.ingest.bwq.fetch_point", no_fetch)
    assert fl.latest_samples() is None                     # no file yet: the page says the sample is not in the data
    _samples(tmp_path)
    got = fl.latest_samples()
    assert got["uke4100-08901"] == {"taken_at": "2026-09-24T10:35+01:00", "ecoli": 380}   # the latest, not the worst
    assert got["ukh1201-09801"] == {"taken_at": "2026-09-23T11:00+01:00", "ecoli": 10, "qualifier": "<"}
    assert "ukd1203-45650" not in got                      # a result without a count is no sample
    pd.DataFrame().to_parquet(tmp_path / fl.ECOLI_SAMPLES)
    assert fl.latest_samples() == {}


def test_bathing_waters_get_their_latest_sample_or_none(tmp_path, monkeypatch):
    from dipcast import config
    monkeypatch.setattr(config, "STATE", tmp_path)
    bs = _build_site()
    spots = lambda: [{"id": "bw-uke4100-08901"}, {"id": "bw-ukd1101-45800"}, {"id": "wharfe-burnsall"}]
    results = spots()
    assert bs.attach_lab_samples(results) is None          # no samples file: no spot gets the field
    assert all("lab_sample" not in r for r in results)
    _samples(tmp_path)
    results = spots()
    assert bs.attach_lab_samples(results) == 1
    assert results[0]["lab_sample"]["ecoli"] == 380
    assert results[1]["lab_sample"] is None                # a bathing water with no sample this season
    assert "lab_sample" not in results[2]                  # not a bathing water: nothing to say here


def test_no_feed_is_counted_apart_from_offline():
    """Of the eleven overflows in test_data_state's table, five report live; the six that do not are
    two on a stale feed, one on a feed that is down, one whose company has no live feed (Welsh) and two
    offline (a monitor offline, one missing from a feed that is up)."""
    from test_data_state import _table

    from dipcast.ingest.live import data_states
    from dipcast.model.forecast import live_counts
    df = _table()
    ov = df.join(data_states(df))
    c = live_counts(ov, pd.Series(0.0, index=ov.index))
    assert c["no_feed_upstream"] == 1
    offline = len(ov) - c["monitored_upstream"] - c["stale_upstream"] - c["feed_down_upstream"] - c["no_feed_upstream"]
    assert (c["monitored_upstream"], c["stale_upstream"], c["feed_down_upstream"], offline) == (5, 2, 1, 2)
    assert live_counts(ov.iloc[0:0], pd.Series(dtype=float))["no_feed_upstream"] == 0


def test_the_page_loads_the_evidence_script_from_its_build(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    page = (tmp_path / "index.html").read_text()
    assert f'<script src="evidence.js?v={stamp}">' in page
    assert page.index('src="evidence.js') < page.index("<script>\n")   # before the page script that calls evidenceTile
    assert (tmp_path / "evidence.js").read_bytes() == (bs.TEMPLATE.parent / "evidence.js").read_bytes()
    assert "`evidence.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
