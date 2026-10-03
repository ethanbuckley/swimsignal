"""Source-backed access notes; a map feature is not evidence of permission to enter water.

These are remote desk checks, not inspections of paths, entry points or current signs.
Lake-wide permission is deliberately distinguished from permission at a particular bank.
"""

CHECKED = "2026-10-03"
PEAK = "https://www.peakdistrict.gov.uk/visiting/planning-your-visit/swimming"
LAKES = "https://lakedistrict.gov.uk/explore/things-to-do/on-the-water/lakes-activities-guide/"
OXFORD = "https://www.oxford.gov.uk/news/article/1860/new-signage-to-be-installed-to-improve-water-safety-in-oxford"
PEAK_SPOTS = {"osm-burbage-padley-gorge", "osm-wye-chee-dale", "osm-dane-three-shires-head",
              "osm-lathkill-dale", "osm-bradford-youlgrave"}
LAKE_SPOTS = {"osm-ullswater-sandwick", "osm-windermere-waterhead"}


def access_note(spot: dict) -> dict | None:
    if spot.get("source") != "openstreetmap":
        return None
    note = {"status": "unconfirmed", "checked_at": CHECKED,
            "text": "Permission to enter the water at this point has not been confirmed. A mapped swimming place or public footpath does not establish swimming permission. Check current signs and the landowner's rules."}
    if spot["id"] in PEAK_SPOTS:
        note.update(status="restricted_guidance", url=PEAK,
                    text="The Peak District authority says river swimming requires explicit on-site signs and designated areas. Permission at this point has not been confirmed. Check the signs and the landowner's rules before entering.")
    elif spot["id"] in LAKE_SPOTS:
        note.update(url=LAKES,
                    text="The Lake District authority allows swimming in this lake. Access and permission at this particular entry point have not been confirmed; check the bank, current signs and boat traffic.")
    elif spot["id"] == "osm-thames-long-bridges":
        note.update(url=OXFORD,
                    text="Oxford City Council lists Longbridges among places receiving water-safety signs and discourages wild swimming. Check the current signs; listing this place does not confirm permission or a maintained entry point.")
    elif spot["id"] == "osm-teign-drogo-weir":
        note.update(url="https://www.nationaltrust.org.uk/visit/devon/castle-drogo/teign-gorge-classic-circuit",
                    text="The National Trust describes Drogo Weir on its walking route. That does not establish permission to swim. This point is beside a weir; the pollution forecast does not assess the weir, currents or access.")
    return note


def attach_access(spots: list[dict]) -> int:
    n = 0
    for spot in spots:
        note = access_note(spot)
        if note:
            spot["access"] = note
            n += 1
    return n
