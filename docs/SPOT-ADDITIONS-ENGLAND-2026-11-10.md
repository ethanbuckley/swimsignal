# Ten English river spots added on 10 November 2026

Under Ethan's rules of 1 November 2026 (`SPOT-ADDITIONS-ENGLAND-2026-11.md`, `SPOT-ADDITIONS-2026-11.md`):
1. not a paid or managed venue;
2. not under 1 km from a listed spot on the same water;
3. placed by the river network;
4. no owner, operator or authority says no. Finding no "no" is not a yes, so each page says permission has not been
   confirmed (`access.py`, `NOV10_SPOTS`).

Each spot also has a public page (a council, charity, guidebook or magazine) naming it as a place people swim, and is
not tidal. Pages were read on 10 Nov 2026.

## 1. The Open-Meteo budget, measured before anything was added

**The rule.** Ethan's rule of 1 Nov 2026 (`SPOT-ADDITIONS-2026-11.md`): the busiest recent day plus the new spots'
planned cost stays under 8,500 calls. The 9,000 ration is enforced before every request in any case
(`rainfall.may_spend`).

**Measured days.** Each build logs the UTC day's ledger so far. The last build of each day gives the total (days whose
last build crossed midnight use the last build before it):

| Day | Calls | Builds | Spot set |
|---|---:|---:|---|
| 31 Oct | 6,827 | 32 | 112 spots |
| 1 Nov | 5,878 | 13 | 112 |
| 5 Nov | 5,578 | 12 | 112 |
| 6 Nov | 5,326 (to 23:59) | 11 | 123 from 23:00 |
| 7 Nov | 4,484 | 7 | 123 |
| 8 Nov | 5,850 | 9 | 123 |
| 9 Nov | 3,423 | 3 | 123 |

No build since 27 Oct had a request held by the ration.

**The busiest recent day** is 31 Oct, 6,827, with 32 builds. The 1 Nov doc adds the 11 spots listed on 6 Nov to it
(about 325 calls at their planned rate), so the baseline is **about 7,150**. That leaves **about 1,350 calls a day**
for new spots under the 8,500 rule.

**The planned day (a build every 30 minutes) is already past the ration.** `scripts/spot_cost.py` on today's state
gives 9,125 calls for the England spots alone (352 rain cells, 111 weather points, 1,247 click-anywhere cells, 64 soil
cells, Scotland's shadow 1,280). With the 12 Scottish spots (372 cells and 123 weather points in the build log) it is
about 9,475. So `PLANNED_DAY_CALLS` (8,750) and the 16 Oct counts in `tests/test_open_meteo_ration.py` no longer
describe the planned day. That has been true since before this change; it matters only on a day with builds every 30
minutes, when the ration holds back the last requests of the day and their users read cached rain.

**The ensemble-rain window (D4, 23 Oct to 19 Nov, read on or after 21 Nov).** It must not be shortened. Three ways
new spots could touch it:
- *Its daily cap.* The ensemble is asked for each spot cell about twice a day, against `ENSEMBLE_DAILY_CALLS` of
  1,000. Today 372 cells take 744. More than 128 new cells would cut the second refresh short.
- *Spare calls early in the UTC day.* `spare_for` holds the ensemble back when the day's calls so far eat into
  `PLANNED_DAY_CALLS` spread over the rest of the day. On 7 Nov the builds just after midnight held back 147 cells,
  which read members cached under 24 hours old. Every cell still had members ("372 of 372 cells with members" in
  every build checked, 6 to 9 Nov). New cells add a few calls to each early build.
- *Rows.* D4 scores rows per overflow. A new spot's new upstream overflows add rows from the day it is listed. They
  carry members like any other spot cell, so the comparison stays paired.

## 2. Where candidates came from

- **OpenStreetMap, refreshed.** `scripts/osm_spot_candidates.py` was run once into a scratch root on 10 Nov. Overpass
  answered all five queries (data as of 2026-11-10T00:53Z): 114 candidates against 115 on 3 Oct. Nothing new: the three
  "new" ids are re-mapped versions of features already ruled out on 1 Nov (two private ponds at Send Marsh, Kate Brook).
  The committed candidate file is unchanged. The OpenStreetMap list is used up.
- **The private research files** of 27 and 28 Oct (leads that failed the old rule 4) and the places named on 1 Nov
  (Hemingford Grey, Peterborough Embankment), plus a few well-known inland swims (Minster Lovell, Santon Downham,
  Kerne Bridge, Hoarwithy, Ellingham, Geldeston, Byron's Pool, Appleby). 23 places in all.
- `guides/` names no new place: its guides are for listed spots.

## 3. Positions

`spots.csv` must take no OpenStreetMap data (`LICENSE-DATA.md`), and `tests/test_osm_spots.py` allows only
swim-tagged OpenStreetMap candidates into `spots-osm.csv`. So each pin comes from an Open Government Licence point,
then moves onto the OS Open Rivers line the build snaps it to:
- **Historic England's National Heritage List** (open data API, OGL): the grid reference of a listed bridge or
  scheduled monument at the place.
- **OS Open Names** (OGL): two named waterfalls.
- **OS Open Rivers** itself for Tongue Pot: the node where Throstle Gill (the lower Lingcove Beck) meets the River Esk,
  30 m down the Esk.

OpenStreetMap was used only to check the pins afterwards (OSM API, small map calls), not as a source. That check is
also where Eye Bridge failed (section 5).

## 4. Added: ten

Overflows are the monitored overflows upstream on today's network. Calls are the planned most a day, each spot
priced after the ones above it (`check_pins`, built on `scripts/spot_cost.py`).

| Spot (`id`) | Reference point | Overflows upstream | New rain cells | Calls a day | Who says people swim there |
|---|---|---:|---:|---:|---|
| River Avon, Barton Farm Country Park, Bradford on Avon (`avon-barton-farm`) | NHLE 1364494 Barton Bridge, 16 m | 107, Wessex Water | 1 | 19 | [Bradford on Avon Town Council](https://bradfordonavontowncouncil.gov.uk/your-community/places-and-spaces/parks-green-spaces/barton-farm-country-park/wild-or-open-swimming-in-bradford-on-avon/), which manages the park: "you may see people in the river in Bradford on Avon between May and September, including near Barton Farm country park" |
| River Windrush, Minster Lovell Hall (`windrush-minster-lovell`) | NHLE 1015321 Minster Lovell Hall, 46 m | 1, Thames Water (Burford STW) | 0 | 11 | [Wild Swimming](https://www.wildswimming.co.uk/map/minster-lovell-windrush) (the guidebook's site): "Just deep enough to swim (1m)" |
| Little Ouse, St Helen's, Santon Downham (`little-ouse-santon-downham`) | NHLE 1015256 Santon moated site, 69 m | 17, Anglian Water | 6 | 73 | [Wild Swimming](https://www.wildswimming.co.uk/map/santon-little-ouse): "Chalky riverbed, up to 2m deep, long swim possible" |
| River Barle, Landacre Bridge (`barle-landacre`) | NHLE 1058006 Landacre Bridge, 7 m | 0 | 1 | 23 | [Wild Swimming](https://www.wildswimming.co.uk/map/sherdon-and-landacre/): "popular paddling at Landacre Bridge" |
| River Fowey, Golitha Falls (`fowey-golitha-falls`) | OS Open Names, Golitha Falls, 4 m | 1, South West Water | 1 | 21 | [Wild Swimming](https://www.wildswimming.co.uk/map/golitha-falls): "First 700m wide path provides access to shallows for paddling" |
| River Fowey, Respryn Bridge, Lanhydrock (`fowey-respryn`) | NHLE 1143087 Respryn Bridge, 3 m | 4, South West Water | 4 | 41 | [Classic Cottages, "The 5 best outdoor swim spots in Cornwall"](https://www.classic.co.uk/nas/places-to-go/the-5-best-outdoor-swim-spots-in-cornwall-327.html), undated, lists "The Respryn river". The weakest evidence of the ten |
| River Swale, Kisdon Force, Keld (`swale-kisdon-force`) | OS Open Names, Kisdon Force, 0.1 m | 0 | 1 | 23 | [Wild Things Publishing](https://wildthingspublishing.com/wild-swimming-in-the-yorkshire-dales-waterfalls-rivers-and-hidden-spots/): plunge pools "perfect for a refreshing dip" |
| River South Tyne, Featherstone Castle (`south-tyne-featherstone`) | NHLE 1370307 Featherstone Castle, 226 m | 12, Northumbrian Water | 4 | 51 | [Living North](https://www.livingnorth.com/article/best-wild-swimming-spots-across-north-east-and-yorkshire), April 2024: "Just a short stroll from Featherstone Castle, a small beach beside the South Tyne" |
| River Ribble, Brungerley Park, Clitheroe (`ribble-brungerley`) | NHLE 1072154 Brungerley Farmhouse, 168 m | 25, United Utilities and Yorkshire Water | 0 | 9 | [Ribble Rivers Trust](https://ribbletrust.org.uk/bathing-water-designation-to-ensure-ribble-valley-river-is-safe-to-splash), 28 Feb 2024: "many other swimming spots, including the River Ribble at Brungerley Park" |
| River Esk, Tongue Pot, Upper Eskdale (`esk-tongue-pot`) | OS Open Rivers confluence, 30 m | 0 | 0 | 9 | [OS guide](https://osmaps.com/discover/guides/wild-swimming-holes-in-the-lake-district), 2016: "The legendary Tongue Pot forms a long emerald pool beneath a roaring waterfall" |
| **Total** | | | **17** | **280** | |

**Owners and "no".** For each, the owner's or manager's own pages were searched for a request not to swim, a byelaw or
signs. None was found. What the owners' pages do say:
- *Barton Farm.* The town council warns "Jumping and diving into unknown water can be dangerous"; no permission either way.
- *Santon Downham.* Forestry England's St Helen's pages say nothing about entering the water. They ask visitors to help
  stop riverbank erosion beside a scheduled monument, and parking is charged (not a swim fee).
- *Golitha Falls.* Natural England's leaflet (NE164) and the GOV.UK reserve page set no swimming rule; the page says
  "Extra care should be taken when visiting after heavy rainfall."
- *Tongue Pot.* The Lake District National Park Authority: "You can swim in most of the lakes, tarns and rivers in the
  Lake District"; its "not allowed" list is Ennerdale Water and three reservoirs.
- *Respryn.* National Trust walk pages for Lanhydrock say nothing on swimming. The tidal limit is at Lostwithiel,
  downstream.
- *Kisdon Force, Featherstone, Landacre, Minster Lovell, Brungerley.* No owner page found either way. Brungerley's
  council water-safety page is general advice and does not name it.

**Checks on every pin** (the 6 Nov audit's checks, before merging; the live page checks follow the next build):
- *Pin on the water:* each is the snapped point on its named OS Open Rivers link, 0 to 0.5 m from it. Checked against
  OpenStreetMap for Brungerley (85 m from Brungerley Park, 51 m from the bridge), Featherstone (215 m from the castle,
  on the South Tyne), Santon Downham (beside St Helen's picnic site) and Eye Bridge.
- *Right water:* each snaps to the river in its `river` column, form `inlandRiver`, so `placement_check` raises no
  warning.
- *Same water under 1 km:* none. Nearest on the same river: Brungerley 1.9 km from Edisford Bridge, Barton Farm 4.8 km
  from Warleigh Weir, Landacre 6.5 km from Tarr Steps, Golitha and Respryn 12 km apart.
- *Water body:* `scripts/make_rnags.py`, rerun on 10 Nov (the Environment Agency file unchanged, same SHA-256),
  puts every one of the ten within 12 m of the Environment Agency's line for its named river (`data/raw/rnags.json`).
  The rerun also refreshed `osm-tame-dosthill`, whose pin moved on 6 Nov: same water body, 7 m from its line, not 140 m.
- *OpenStreetMap tags on the water within about 150 m:* only `boat=no` on four rivers, which is about boats.

**Four with no monitored overflow upstream** (Landacre, Kisdon Force, Tongue Pot, and Minster Lovell's one works) show
"No monitored overflow found upstream" where that is so, which claims only that none is monitored.

**Hazards named by the sources** (not assessed by the forecast): a weir about 40 m from the Featherstone pin and one at
Brungerley; jumping into Kisdon Force and Tongue Pot; fast water at Golitha Falls after rain.

## 5. Not added

| Place | Why |
|---|---|
| Eye Bridge, River Stour, Pamphill | The OpenStreetMap river way through it (way 146291677, edited Nov 2024) is tagged `swimming=no` and `access=no`, and the pin falls on the weir. On 1 Nov a tag like this was taken as pointing to no |
| Byron's Pool, River Cam | [Cam Conservancy](https://camconservancy.org/swimming): byelaws restrict swimming within 36 m of any weir; the pool is the weir pool |
| Kerne Bridge, River Wye | The operator's [risk assessment](https://walfordparishcouncil.gov.uk/wp-content/uploads/2025/04/Riversea-Holdings-RA-Kerne-Bridge-Mar-2025-v1.0.pdf) (March 2025): "Signage is displayed discouraging swimming in the river" |
| Lumb Falls, Crimsworth Dean Beck | Privately owned; Halifax Courier, 17 Aug 2022: "The privately owned falls had to be closed last year" |
| Geldeston, River Waveney | Tidal below the lock (Broads Authority), and the Broads Authority "strongly advises against entering the water unless part of an organised event" |
| Ellingham, River Waveney | The same Broads Authority advice; no swim evidence found |
| Dartmeet, River Dart | Who owns the banks was not found. The Spitchwick estate (signs: "No wild swimming please") owns 17 to 19 km of the Dart, ends not stated |
| Stour Meadows, Blandford; Hemingford Meadow; Peterborough Embankment; Hoarwithy; Burford; Appleby | No "no" found, but no page beyond crowd-sourced maps names swimming there. A council, charity, press or guidebook page would settle each |
| Grange-in-Borrowdale, River Derwent | The YHA page names paddling only |
| Hemingford Meadow (west point) | 801 m from `great-ouse-houghton` on the same river (rule 2) |

## 6. What more calls would buy

- **Free tier.** After these ten, about 7,430 of 8,500 under the rule: room for about 1,070 more calls a day, roughly
  50 spots that each bring one new rain cell, or about 120 that share cells. The limit is candidates with evidence, not
  calls.
- **Paid Standard plan** (about €29 a month, 1,000,000 calls a month, about 32,000 a day): about 24,000 more calls a day
  over today's busiest day, in the order of 1,000 spots with a new rain cell each. It does not cover the ensemble API,
  which needs Professional (€99). Not bought: Ethan chose free data only on 27 Oct.

## 7. For Ethan

- `PLANNED_DAY_CALLS` and the planned-day test describe 16 Oct. Whether to update them (which would hold the ensemble
  back more in the early hours) is better left until after the D4 read on 21 Nov.
- Respryn rests on one holiday-company page. Remove it if that is too thin.
