import csv
from pathlib import Path

from dipcast.access import attach_access


def test_all_osm_spots_distinguish_map_features_from_permission():
    root = Path(__file__).resolve().parents[1]
    spots = list(csv.DictReader((root / "spots-osm.csv").open()))
    for spot in spots:
        spot["source"] = "openstreetmap"
    assert len(spots) == attach_access(spots) == 16
    assert all(s["access"]["checked_at"] == "2026-10-03" for s in spots)
    by_id = {s["id"]: s["access"] for s in spots}
    assert by_id["osm-wye-chee-dale"]["status"] == "restricted_guidance"
    assert "particular entry point" in by_id["osm-ullswater-sandwick"]["text"]
    assert "weir" in by_id["osm-teign-drogo-weir"]["text"]
    assert "current signs" in by_id["osm-thames-long-bridges"]["text"]
    assert attach_access([{"id": "designated", "source": "designated"}]) == 0


def test_peak_district_guidance_reaches_its_curated_spots_too():
    curated = [{"id": "dove-dovedale", "source": "curated"}, {"id": "derwent-slippery-stones", "source": "curated"},
               {"id": "dart-spitchwick", "source": "curated"}]
    assert attach_access(curated) == 2
    for spot in curated[:2]:
        a = spot["access"]
        assert a["status"] == "restricted_guidance" and a["url"].startswith("https://www.peakdistrict.gov.uk/")
        assert "supervised, organised event" in a["text"] and "has been confirmed at this point" in a["text"]
    assert "access" not in curated[2]
