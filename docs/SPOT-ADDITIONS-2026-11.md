# Spots added in November 2026: evidence, budget and what was not added

Written 1 November 2026, after Ethan asked for more spots in Scotland and England. Two decisions of his, the same day,
change how spots are added. Earlier additions and the four inclusion rules are in `SPOT-ADDITIONS-2026-10.md`.

## 1. Two decisions

**Scottish access.** For the Scotland trial's spots, the Scottish Outdoor Access Code is the access evidence (rule 4).
A page per spot is no longer needed. Its swimming page, read 1 Nov 2026, says: "Access rights extend to swimming
(subject to any local byelaws)" ([outdooraccess-scotland.scot](https://www.outdooraccess-scotland.scot/index%2Ephp/practical-guide-all/watersports/swimming)).
Each Scottish spot still needs:
- a public body's or a charity's own page saying people swim at that place;
- not to be a reservoir with byelaws, a private fishery, a paid venue or tidal water.

The page cites the Code (`access.py`, `statutory_access`) and says it is not a check of the entry point.

**Open-Meteo budget.** New spots are budgeted on measured use, not on a build every 30 minutes, and the cap is still
enforced before every request. The day's totals, from each build's ledger:

| Day | Calls | Builds |
|---|---:|---:|
| 29 Oct | 6,672 | 8 |
| 30 Oct | 5,631 | 13 |
| 31 Oct | 6,827 | 32 |

The busiest day left about 2,170 of the 9,000 ration free. The rule from now: **the busiest recent day plus the new
spots' planned cost stays under 8,500.** If it is broken, the enforced ration holds back the shadow's and the
spare-only requests first, then late-day spot requests reuse cached rain. The free tier's cap is never passed.

## 2. Scotland: nine spots added (trial)

Researched 1 Nov 2026. Each quote was checked word for word against the page. No position is from OpenStreetMap.
Positions came from:
- the National Park's 6 kph zone maps, read off their OS grid;
- OS Open Names and OS OpenMap Local (OGL);
- Historic Environment Scotland's Canmore record.

| Spot | Who says people swim there | Overflows upstream (1 Nov, offline) |
|---|---|---:|
| Milarrochy Bay, Loch Lomond | [VisitScotland](https://www.visitscotland.com/things-to-do/active-adventure/watersports/wild-swimming): "one of the area's most scenic and accessible swim spots" | 8 |
| Sallochy, Loch Lomond | [Forestry and Land Scotland](https://forestryandland.gov.scot/visit/destinations/sallochy/trails): "a popular place for wild swimming" | 8 |
| Duck Bay, Loch Lomond | [National Park byelaws page](https://www.lochlomond-trossachs.org/loch-lomond-byelaws/), after its zone list: "expect to see ... swimmers in the water" | 8 |
| Balloch Castle Country Park, Loch Lomond | same page | 8 |
| Manse Bay, Balmaha, Loch Lomond | same page | 8 |
| Rowardennan, Loch Lomond | same page | 8 |
| Tollie Bay, Loch Maree | [VisitScotland](https://www.visitscotland.com/things-to-do/nature-outdoors/lochs/deepest-lochs): "take a wild swim in Tollie Bay" | 0 |
| River Almond, Almondell | [Forth Rivers Trust](https://forthriverstrust.org/river-almond-bathing-waters/) (a charity): "People are regularly seen swimming" | 33 |
| Loch Lubnaig, by Strathyre | [National Park](https://www.lochlomond-trossachs.org/things-to-see/lochs-in-the-national-park/loch-lubnaig/): "open water and wild swimmers are discovering" the loch | 0 |

**Weaker evidence, said plainly.**
- **Four Loch Lomond bays** (Duck Bay, Balloch, Balmaha, Rowardennan): the byelaws page names them as zones, then says to expect swimmers. It does not call each one a swim spot.
- **Loch Lubnaig:** no source names an entry point. The pin is the shore nearest the Forestry and Land Scotland car park at Strathyre Cabins.
- **Almondell:** the source is a charity, not a public body. The pin is in the river by Nasmyth Bridge, at the downstream end of the stretch the Trust describes.

**Left out.**
- **Gairlochy, Loch Lochy:** the quote does not mention swimming, and which lighthouse it means is a guess.
- **Lake of Menteith:** a private trout fishery.
- **Not found on a public-body page:** the Tweed at Peebles, the Dee, the Spey, the Ness Islands, Glen Nevis and the Coe. Only tourism or commercial pages name them.
- **Tay at Perth:** tidal.
- **Loch Katrine:** a Scottish Water reservoir.

**Cost.** The nine add one new rain area: Almondell's six cells, 72 calls a day at the spots' rate. With nine
weather points (about 81) that is about 153 calls a day at most. The six Loch Lomond spots share Luss Bay's cells.

## 3. England: none added yet

The 99 unlisted OpenStreetMap candidates (`data/raw/osm_swim_candidates.csv`) were checked against rule 4 on 1 Nov 2026:
63 examined, 36 not.
- **1 passes, borderline:** Shilley Pool on Blackaton Brook, Dartmoor. The National Park says you can swim in Dartmoor's rivers from land you may access, and Natural England's layer puts the point on Dartmoor Commons Act land. No page names the pool. Nothing is upstream.
- **44 fail:**
  - 23 are paid or managed venues;
  - 17 are under 1 km from a listed spot on the same water;
  - 5 are on water whose owner or authority says no: the Canal & River Trust ("We do not permit swimming"), and the Peak District's advice to swim only in supervised activity.
- **18 have no owner's page either way.** These include the more useful ones, with towns upstream: the Great Ouse at Hemingford Grey and Godmanchester, the Wye at Backney Common, the Itchen at Gunner's Hole, the Tame at Dosthill, the Nene at Peterborough and the Exe at Countess Wear.

Rule 4 in its 28 October form is what stops England. Whether to change it is Ethan's decision; nothing is added
before it.
