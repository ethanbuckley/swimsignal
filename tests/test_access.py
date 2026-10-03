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
