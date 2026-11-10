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
DARTMOOR = "https://www.dartmoor.gov.uk/enjoy-dartmoor/planning-your-visit/visiting-faqs"
# Listed on 1 Nov 2026 under the owner's relaxed rule 4 (docs/SPOT-ADDITIONS-ENGLAND-2026-11.md): no owner or
# authority page saying no was found, which is not a yes. Checked that day, not on CHECKED.
NOV_SPOTS = {"osm-tame-dosthill", "osm-blackaton-shilley-pool"}
NOV_CHECKED = "2026-11-01"
# Curated English river spots listed on 10 Nov 2026 under the same relaxed rule
# (docs/SPOT-ADDITIONS-ENGLAND-2026-11-10.md): a guide, council or press page says people swim there and no owner
# or authority page saying no was found. Their positions are from OGL sources, not OpenStreetMap.
NOV10_SPOTS = {"avon-barton-farm", "windrush-minster-lovell", "little-ouse-santon-downham", "barle-landacre",
               "fowey-golitha-falls", "fowey-respryn", "swale-kisdon-force", "south-tyne-featherstone",
               "ribble-brungerley", "esk-tongue-pot"}
NOV10_CHECKED = "2026-11-10"
LAKES_SWIM = "https://www.lakedistrict.gov.uk/explore/things-to-do/on-the-water/swimming-in-the-lake-district/"
BARTON_FARM = ("https://bradfordonavontowncouncil.gov.uk/your-community/places-and-spaces/parks-green-spaces/"
               "barton-farm-country-park/wild-or-open-swimming-in-bradford-on-avon/")
SANTON = "https://www.forestryengland.uk/st-helens-picnic-site/important-historic-site"
GOLITHA = "https://www.gov.uk/government/publications/cornwalls-national-nature-reserves/cornwalls-nature-reserves"


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
    if spot.get("source") != "openstreetmap" and spot.get("id") not in PEAK_SPOTS | NOV10_SPOTS:
        return None
    checked = NOV_CHECKED if spot["id"] in NOV_SPOTS else NOV10_CHECKED if spot["id"] in NOV10_SPOTS else CHECKED
    note = {"status": "unconfirmed", "checked_at": checked,
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
    elif spot["id"] == "osm-blackaton-shilley-pool":
        note.update(url=DARTMOOR,
                    text="Dartmoor National Park Authority says you can swim in Dartmoor's rivers if you get in from land you have a right to be on. Natural England's maps put this point on Dartmoor commons, which are open to the public. No page names this pool, and nobody has checked the way in on the ground.")
    elif spot["id"] == "avon-barton-farm":
        note.update(url=BARTON_FARM,
                    text="Bradford on Avon Town Council, which manages Barton Farm Country Park, says people may be seen in the river near the park from May to September, and warns against jumping or diving into unknown water. It does not say swimming is allowed or forbidden. Permission at this point has not been confirmed: check current signs.")
    elif spot["id"] == "little-ouse-santon-downham":
        note.update(url=SANTON,
                    text="Forestry England runs the St Helen's picnic site beside the river. Its pages say nothing about entering the water, and ask visitors to help stop erosion of the riverbank, which is part of a scheduled monument. Permission at this point has not been confirmed: check current signs.")
    elif spot["id"] == "fowey-golitha-falls":
        note.update(url=GOLITHA,
                    text="Golitha Falls is a National Nature Reserve managed by Natural England. Its pages set no rule on swimming and ask for extra care after heavy rain. The river forms a series of cascades here. Permission at this point has not been confirmed: check current signs.")
    elif spot["id"] == "esk-tongue-pot":
        note.update(url=LAKES_SWIM,
                    text="The Lake District National Park Authority says you can swim in most of the lakes, tarns and rivers in the park; the Esk is not on its list of waters where swimming is not allowed. The pool sits beneath a waterfall. Permission at this particular point has not been confirmed: check the bank and any signs.")
    return note


def attach_access(spots: list[dict]) -> int:
    n = 0
    for spot in spots:
        note = access_note(spot)
        if note:
            spot["access"] = note
            n += 1
    return n
