"""Source-backed access notes; a map feature is not evidence of permission to enter water.

These are remote desk checks, not inspections of paths, entry points or current signs.
Lake-wide permission is deliberately distinguished from permission at a particular bank.
"""

CHECKED = "2026-10-03"
PEAK = "https://www.peakdistrict.gov.uk/visiting/planning-your-visit/swimming"
LAKES = "https://lakedistrict.gov.uk/explore/things-to-do/on-the-water/lakes-activities-guide/"
OXFORD = "https://www.oxford.gov.uk/news/article/1860/new-signage-to-be-installed-to-improve-water-safety-in-oxford"
# Inside the Peak District National Park, so its swimming guidance applies: the five from OpenStreetMap and
# two curated spots, Dovedale and Slippery Stones (Upper Derwent).
PEAK_SPOTS = {"osm-burbage-padley-gorge", "osm-wye-chee-dale", "osm-dane-three-shires-head",
              "osm-lathkill-dale", "osm-bradford-youlgrave", "dove-dovedale", "derwent-slippery-stones"}
LAKE_SPOTS = {"osm-ullswater-sandwick", "osm-windermere-waterhead"}


# Scotland: the statutory right of responsible access (Land Reform (Scotland) Act 2003, Part 1) and the Scottish
# Outdoor Access Code, which the owner took as the access evidence for the Scotland trial's spots on 1 Nov 2026.
# Its swimming page, read 1 Nov 2026: "Access rights extend to swimming (subject to any local byelaws)."
SCOTLAND_CODE = "https://www.outdooraccess-scotland.scot/index%2Ephp/practical-guide-all/watersports/swimming"
SCOTLAND_CHECKED = "2026-11-01"


def access_note(spot: dict) -> dict | None:
    if spot.get("trial") == "scotland":
        return {"status": "statutory_access", "checked_at": SCOTLAND_CHECKED, "url": SCOTLAND_CODE,
                "text": "The Scottish Outdoor Access Code says access rights extend to swimming, subject to any local "
                        "byelaws, and asks swimmers to keep away from water intakes, abstraction points and spillways. "
                        "That is not a check of this entry point, its currents or the cold: follow the Code and any "
                        "signs at the water."}
    if spot.get("source") != "openstreetmap" and spot.get("id") not in PEAK_SPOTS:
        return None
    note = {"status": "unconfirmed", "checked_at": CHECKED,
            "text": "Permission to enter the water at this point has not been confirmed. A mapped swimming place or public footpath does not establish swimming permission. Check current signs and the landowner's rules."}
    if spot["id"] in PEAK_SPOTS:
        note.update(status="restricted_guidance", url=PEAK,
                    text="The Peak District National Park Authority says river swimming is not permitted unless on-site signs allow it in a designated area, and advises entering open water only as part of a supervised, organised event. No such sign or designated area has been confirmed at this point. Check the signs and the landowner's rules before entering.")
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
