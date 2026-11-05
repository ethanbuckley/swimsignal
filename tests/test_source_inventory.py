"""The source inventory (#486) is hand-written; these checks keep it to its contract
(docs/SOURCE-INVENTORY-CONTRACT-v1.md) and in step with the readable doc."""

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "research" / "source_inventory.v1.json"
READABLE = ROOT / "docs" / "SOURCE-INVENTORY-2026-11.md"

STATUSES = {"ready_to_integrate", "needs_permission", "unavailable", "stale_archive", "already_used"}
KINDS = {"measurement", "proxy", "model", "metadata", "directory"}
RESULTS = {"unchanged", "changed", "could_not_verify", "not_rechecked"}
THEMES = {"samples_sondes", "discharge_load", "rain_flow", "upgrade_metadata", "spill_history",
          "regional_directory", "coastal_model"}
FIELDS = {"id", "rank", "rank_reason", "name", "publisher", "region", "theme", "measures", "measurement_kind",
          "measurement_note", "coverage", "date_range", "latency", "licence", "access", "local_cache", "status",
          "enables", "recheck", "docs"}


def load():
    return json.loads(INVENTORY.read_text())


def test_header():
    d = load()
    assert d["schema"] == "swimsignal.source-inventory"
    assert re.fullmatch(r"1\.\d+\.\d+", d["version"])
    assert set(d["statuses"]) == STATUSES
    assert set(d["measurement_kinds"]) == KINDS
    assert set(d["recheck"]["results"]) == RESULTS
    date.fromisoformat(d["recheck"]["checked_on"])


def test_entries_follow_the_contract():
    sources = load()["sources"]
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    assert sorted(s["rank"] for s in sources) == list(range(1, len(sources) + 1))
    for s in sources:
        assert FIELDS <= set(s), s["id"]
        assert re.fullmatch(r"[a-z0-9-]+", s["id"])
        assert s["status"] in STATUSES, s["id"]
        assert s["measurement_kind"] in KINDS, s["id"]
        assert s["theme"] in THEMES, s["id"]
        assert s["measures"] and s["rank_reason"] and s["enables"], s["id"]
        assert {"name", "url", "permits"} <= set(s["licence"]), s["id"]
        assert s["licence"]["url"].startswith("http"), s["id"]
        assert isinstance(s["access"]["account"], bool), s["id"]
        cache = s["local_cache"]
        if cache is not None:
            assert {"path", "bytes", "files", "newest"} <= set(cache), s["id"]
            date.fromisoformat(cache["newest"])
        r = s["recheck"]
        assert r["result"] in RESULTS, s["id"]
        if r["result"] in {"unchanged", "changed", "could_not_verify"}:
            assert r["urls"] and all(u.startswith("http") for u in r["urls"]), s["id"]
        if r["result"] == "changed":
            assert r["changes"], s["id"]
            for c in r["changes"]:
                assert {"claim", "was", "now", "doc"} <= set(c), s["id"]
        for doc in s["docs"]:
            assert (ROOT / doc.split("#")[0]).exists(), (s["id"], doc)


def test_every_bucket_and_theme_the_issue_asks_for_is_present():
    sources = load()["sources"]
    assert {s["status"] for s in sources} == STATUSES
    assert {"samples_sondes", "discharge_load", "upgrade_metadata", "spill_history", "regional_directory"} <= {
        s["theme"] for s in sources}
    regions = " ".join(s["region"] for s in sources)
    for nation in ("Wales", "Scotland", "Ireland"):
        assert nation in regions


def test_readable_doc_lists_every_source_at_its_rank():
    text = READABLE.read_text()
    for s in load()["sources"]:
        assert f"| {s['rank']} | `{s['id']}` |" in text, s["id"]


def test_follow_on_issues_name_real_sources():
    d = load()
    ids = {s["id"] for s in d["sources"]}
    assert d["follow_on_issues"]
    for f in d["follow_on_issues"]:
        assert f["title"] and set(f["sources"]) <= ids
