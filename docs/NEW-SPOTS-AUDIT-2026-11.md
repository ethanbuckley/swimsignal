# Audit of the 11 spots listed on 6 November 2026

Done on 6 Nov 2026, against the live site (build of 23:02 UK time). The spots are the nine Scottish ones of PR #595
(`spots-scotland.csv`) and the two English ones of PR #596 (`spots-osm.csv`).

## 1. What was checked, and how

For each spot:
1. **Pin on the water.** The pin against OpenStreetMap: is it inside the water polygon, or how far from the river
   line; and is it at the place the cited source names. Read with the Overpass API, a few small queries.
2. **Right water.** The snapped water body and snap distance in the live `data/spots-lite.json`.
3. **Overflow count.** The upstream overflows in the live `data/spot/<id>.json`, against Scottish Water's live
   feed of 4 Oct 2026 (`data/raw/scottish_water/near_real_time.json`, 2,074 assets) for the Scottish spots.
4. **Access wording.** Each source page opened and the quote found on it, and the rendered spot page's Access row.
5. **Headline.** The rendered spot page's level line and its testing line.

## 2. Results

| Spot | Pin | Water and count | Access source | Headline | Change |
|---|---|---|---|---|---|
| Milarrochy Bay, Loch Lomond | In Loch Lomond, ~120 m off the Park's Milarrochy Bay car park | Loch Lomond; 8, all in its catchment | VisitScotland quote found | Low; SEPA does not test | None |
| Sallochy, Loch Lomond | In the loch, ~80 m off Sallochy beach | as above | Forestry and Land Scotland: could not re-read, the site's domain did not resolve on 6 Nov | Low; SEPA does not test | None |
| Duck Bay, Loch Lomond | In the loch, ~60 m off Duck Bay beach | as above; see 3.1 | Park byelaws page: "Duck Bay" is a listed zone; quote found | Low; SEPA does not test | Trial line names emergency overflows |
| Balloch Castle Country Park, Loch Lomond | In the loch at its south end | as above; see 3.1 | same page, zone listed | Low; SEPA does not test | as above |
| Manse Bay, Balmaha, Loch Lomond | In the loch, ~70 m off a beach, 0.7 km NW of Balmaha | as above | same page, "Manse Bay" listed | Low; SEPA does not test | None |
| Rowardennan, Loch Lomond | In the loch by the war memorial | as above | same page, zone listed | Low; SEPA does not test | None |
| Tollie Bay, Loch Maree | In Loch Maree, ~110 m from OSM's Tollie Bay | Loch Maree; 0 is right: no Scottish Water asset in the catchment | VisitScotland: "take a wild swim in Tollie Bay" found | No monitored overflow found upstream; SEPA does not test | None |
| River Almond, Almondell | On Nasmyth Bridge, 3 m from the river | River Almond, 1 m snap; 33 plausible (3.2) | Forth Rivers Trust quote found; its stretch runs "from the Nasmyth Bridge upstream to the weir" | Moderate; SEPA does not test | None |
| Loch Lubnaig | In the loch, at its south end | Loch Lubnaig; 0 is right: no asset in the Balvag or Lubnaig catchment | Park page quote found | No monitored overflow found upstream; SEPA does not test | **Renamed** from "by Strathyre" (3.3) |
| River Tame, Dosthill | **On land**, 133 m east of the river | River Tame (WFD "Tame from R Blythe to River Anker"); 148 belong to the Tame | Unconfirmed note shown | Low/moderate by day; EA does not test | **Pin moved onto the river** (3.4) |
| Blackaton Brook, Shilley Pool | Inside OSM's Blackaton Brook water polygon | Snaps 1,082 m downstream on Blackaton Brook, where OS Open Rivers starts; 0 is right (moorland) | Dartmoor FAQ: "You can swim in Dartmoor's rivers as long as you access from points that are not on private land" found; "Not confirmed" shown | No monitored overflow found upstream; EA does not test | None |

## 3. Findings

### 3.1 Loch Lomond: three outfalls into the loch are not counted

**Established.** The 8 overflows are Drymen and Fintry (Endrick Water), Killearn and Strathblane (Blane Water) and
Gartocharn (Blairennich Burn). All drain into Loch Lomond. Scottish Water's feed also lists five assets in the
catchment that the trial leaves out, because their type includes "EO" (emergency overflow; `scottish_shadow.py`,
plan section 5.2):

| Asset | Type | Receiving water | From Duck Bay | From Balloch pin |
|---|---|---|---:|---:|
| CSO000498 Cameron House (rear) SPS | CSO/EO | Loch Lomond | 589 m | 953 m |
| CSO000499 Cameron House Boathouse SPS | EO | Loch Lomond | 972 m | 818 m |
| CSO000500 Balloch South Lodge GC SPS | EO | Loch Lomond | 1,395 m | 832 m |
| STW002010 Balfron WWTW | CSO/SSSO/EO | River Endrick | | |
| CSO007129 Gartocharn WWTW EO 1 | EO | Blairennich Burn | | |

Across Scotland, 102 assets are EO only and 59 are EO in a mixed type, of 2,074.

**Changed.** The Scotland trial line on every Scottish spot's page now says: "Emergency overflows are not counted,
nor outfalls that are both storm and emergency overflows."

**For Ethan.** Whether mixed types (CSO/EO, CSO/SSSO/EO) should be forecast as storm overflows is a model decision.
It was not changed here.

### 3.2 River Almond's 33

**Established.** The ten listed contributors are all on the Almond or its burns (Mid Calder, Livingston, Seafield,
Blackburn, East Whitburn, Fauldhouse, Longridge). Brox Burn, Newbridge and Kirknewton, which join below Almondell,
are not among them.
**Inferred.** The feed has about 32 to 38 non-emergency assets on the Almond above Almondell, depending on whether
Bog Burn (Bathgate) and How Burn (Harthill) are drawn into it. 33 is in that range. The full list of 33 is not
published, so it was not checked one by one.

### 3.3 Loch Lubnaig: the pin is not by Strathyre

**Established.** The pin is at the loch's south end, about 6.5 km from Strathyre village. The National Park's page
says "Strathyre, to the north of Loch Lubnaig". The nearest mapped place to the pin, 150 m away, is Forest Holidays
Strathyre, a commercial cabin site (its playground is mapped `access=private`). The November additions doc called
it "the Forestry and Land Scotland car park at Strathyre Cabins". A free public car park with a picnic site is
about 330 m south-east, on the A84 side.
**Changed.** The name is now "Loch Lubnaig, south end". The id is unchanged, so saved spots keep working.
**Not changed.** The pin. It is on the water and nothing is upstream, so the forecast does not depend on it.
`spots-scotland.csv` takes no OpenStreetMap position, so moving it to the public car park's shore needs an OS
position. Whether to move it is for Ethan.

### 3.4 River Tame, Dosthill: pin on land

**Established.** The OpenStreetMap node (`node/6646996432`, "Wild swimming", beside a mapped bench) is in a field
133 m east of the Tame. The build snapped it to the river at 52.59095, -1.69768, by a footbridge.
**Changed.** The pin is now that river point. The build's own placement code (`scripts/spot_request.py`, run
read-only on the local network) gives the same answer for both positions: the River Tame, 148 overflows, 144 with a
live feed, nearest 3.0 km. The rain cell is the same (52.6, -1.7), so no new Open-Meteo calls. No local build was
run.
**Note.** The RSPB's Middleton Lakes reserve is across the river. The Tame at Tamworth has had police and fire
service warnings against swimming (`SPOT-ADDITIONS-ENGLAND-2026-11.md`). Whether to keep the spot is for Ethan.

### 3.5 Wording that read "no overflow" as "no risk"

**Established.** Three lines said a spot with no monitored overflow upstream has "no sewage spill risk": the key on
every spot page (`index.html`), the organiser view twice ("so there will be no sewage spill risk here",
`organisers.js`), and the method page. That reads as "safe from sewage".
**Changed.** All now say "no sewage spill score". The headline itself, "No monitored overflow found upstream", with
"Other risks apply", was already right on all three spots it applies to.

## 4. Not checked

- The Sallochy quote: forestryandland.gov.scot did not resolve from here on 6 Nov.
- Manse Bay's exact place: OpenStreetMap does not name it. The pin is on the water off a beach near Balmaha.
- Whether Shilley Pool is on Dartmoor commons: Natural England's layer was not re-read.
- Entry points on the ground at any spot.
