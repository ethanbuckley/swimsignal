# Overflow positions and checked joins, October 2026: the rules and checks, stated before they are applied

Written 13 October 2026. Main was at 25e735a. Handoff items 4B and 4C (`docs/HANDOFF-2026-10-12.md`).
This file is committed and pushed before the rule below is applied to the data or any spot is
compared. Results go under the line at the end. Nothing above that line changes afterwards.

**Inputs.** The `state` release's live snapshot (`live_latest.parquet`, uploaded 13 Oct 2026 03:20
UTC), the annual returns 2021–2025 (`data/processed/annual_returns.parquet`), and the river network
as main loads it (topology key `b5724303`). Every build is into a scratch `DIPCAST_STATE`.

**Licence.** Only Open Government Licence sources are used: OS Open Rivers, OS OpenMap Local, OS
Open Names (`data/raw/places.json`), the companies' live feeds and annual returns, the WFD water
body names in the annual returns, and the EA bathing-water API (`features.json`). The EA register
*Consented Discharges to Controlled Waters with Conditions* is not used. Its licence is internal use
only, with no publishing.

## What was looked at before this was written

So the reader can judge the rule, this is what was known when it was written.

- **The 166 conflicts.** With the snapshot above, 420 overflows have a live position and an
  annual-return outlet over 300 m apart and a receiving water with a distinctive word. The 750 m
  named-water rule (#175) gives: outlet alone 40, live alone 55, both 159, neither 166. The 166 were
  listed with these columns: the gap; both receiving-water names; the WFD water body; whether a link
  carrying the receiving water's or the water body's words lies within 3 km of each position; the
  distance from each position to the place the site name gives; and which annual-return years sit
  at each position. The place rule (#179) moves 12 of them today.
- **Which ones matter to a listed spot.** Each of the 166 was snapped at its live position and at its
  outlet, with the build's two-pass snap, and traced at all 105 listed spots. 12 count at a listed
  spot from one position or the other. 5 count at a different set of spots depending on the
  position: TWL00418, TWL00743, YWS00049, AWS00023 and SWS00413 (Newick, already moved by #179).
  Earl Sterndale (SVT02723, already moved) and Farnham STW (TWL00182) change weight only.
- **The four joins.** The OS OpenMap Local traces for Benson STW, Sudbury WRC, Sudbury Bailey and
  Coates CSO and Ilkley Bridge Lane CSO were run while drafting. Section 1 records how they were
  read. Their rows are added after this commit.

## 1. Checked joins (4C)

**Tiles.** OS OpenMap Local, ESRI shapefile, tiles SU (Benson), TL (Sudbury) and SE (Ilkley), each
checked against OS's published MD5. Only `SurfaceWater_Line`, `SurfaceWater_Area` and `NamedPlace`
are read. No other tile is downloaded.

**Trace.** From the outfall's position, take every OpenMap Local water line within 30 m, and every
water area under 20,000 m² (narrow drains are drawn as areas), read as its outline. Add any line or
outline within 5 m of one already taken. Stop at the first OS Open Rivers link a piece comes within
5 m of.

**Row.** Where the trace reaches a link:
- If that link carries a word of the receiving water's own name, the overflow is already on its
  water. No row.
- Otherwise follow the network down from where the trace meets it. Take the first link carrying a
  word of the river the receiving water names ("R STOUR", "Tributary River Stour", "Spicey Gill
  (River Wharfe)"). If it is reached within 1 km with no other named river joining first, place the
  overflow 15 m down that link, from OS Open Rivers link geometry, as #188 did.
- Otherwise no row; say where the trace met the network.

Where the trace stops before any link (a culvert, or a stretch not drawn), there is no row. The
case is flagged with the gap and the nearest drawn link. The overflow stays where it is snapped.

## 2. The position rule for the 166 (4B)

These are overflows whose two positions are over 300 m apart, where neither has a link carrying the
receiving water's name within 750 m. Each is put in exactly one class, in this order.

1. **Ground.** Every receiving-water name says ground (`to_ground`). These stay off the network,
   whichever position is right. Settled; no change.
2. **Different waters.** The live and annual-return receiving waters share no distinctive word, and
   both have one (`_same_water` is false). The id may cover two assets, as at Holy Island. Open.
3. **Under 1 km apart.** At a 3 km test radius, names cannot tell two points under 1 km apart. Open.
4. **Evidence.** Three kinds of evidence are checked, each within 3 km of each position:
   - **E1 water:** a link carrying a distinctive word of either receiving-water name.
   - **E2 water body:** a link carrying a distinctive word of the annual return's WFD water body
     name. Use the part before " from ", " to " or " conf", with brackets dropped.
   - **E3 place:** a place the site name gives (OS Open Names, `_named_place`, as #179).

   A kind points to a position when that position has it and the other does not. For E1 and E2,
   these words do not count, on top of those `_tokens` and `POSITION_EXTRA` drop. They are regional
   stream words and sea words, which match unrelated links within 3 km: gill, ghyll, sike, syke,
   clough, lode, rhyne, goit, stell, dean, dene, gutter, fleet, carr, sea, estuary, channel, bay,
   harbour, sound, streams, brooks, becks, burns.
   - **Settled to the outlet**, when at least one kind points to it and none points to the live
     position. The overflow moves to the outlet.
   - **Settled to the live position**, when at least one kind points to it and none to the outlet.
     No change, because the live position is the default.
   - **Open**, when kinds point both ways ("evidence conflicts") or none points ("no evidence").

The year history is reported but not used. It shows which annual-return years give each position.
A company changing its stated position between years could be a correction or an error.

**In code.** Class 4 replaces the place-only branch of `choose_positions` (#179). The place rule is
E3 alone. The new rule adds E1 and E2, and it does not move an overflow when E1 or E2 points to the
live position. So it runs at every build, for new conflicts too. Any of the 12 that the place rule
moves today and this rule does not is listed in the results.

## 3. Checks, run after this file is pushed

- **K1. Classes.** The count in each class, and every one of the 166 with its class and reason.
- **K2. The place rule's 12.** How many stay at the outlet. Any that go back to the live position are
  listed.
- **K3. EA features.** Take the bathing waters whose sampling point is within 2 km of either position
  of any of the 166, using the EA's list of England's bathing waters, one request. Fetch each one's
  `features.json`. A position matches when it is within 100 m of a feature point, and the other
  position is not. Report agreement and disagreement with the rule's class.
- **K4. OpenMap Local.** For each conflict whose position changes a listed spot's set of overflows,
  list the OpenMap Local water names (`NamedPlace`) within 1 km of each position. Only the tiles
  already held (SE, SU, TL) are used; other cases are marked not checked.
- **Contradictions.** If K3 or K4 contradicts a move to the outlet, the move is not made. A positive
  match at the live position counts; a missing name does not. The overflow is kept at the live
  position by an explicit exception in code, which carries the reason, and it is listed.
- **K5. Effect on spots.** Build the overflow table twice on scratch state, from the same snapshot
  and network:
  - **before**, with main's code and joins file;
  - **after**, with this branch.

  Then trace all listed spots (`spots.csv` and `spots-osm.csv`, placed with `transport.spot_hints`
  and `locate_pin`) with `upstream_overflows` on both tables. Report every spot whose set of
  overflows or summed weight changes. Levels are not recomputed, because that needs rain forecasts
  and this work makes no Open-Meteo requests. So name every spot whose change is large enough that
  it could move its published level: a new overflow above 0.1 weight, or summed weight up or down
  by more than 10%.
- **K6. Tests.** `pytest -q` with the venv (4 known Pillow failures in `tests/test_cards.py`), and
  `node --test tests/*.test.cjs`.

---

## Results

Added after commit 5808340, which was pushed at 13:04 BST on 13 October 2026 before any of this was
run. Every case, with its evidence, is in `docs/OVERFLOW-POSITIONS-2026-10-cases.csv`.

**Answer.**
- Three joins are added: Sudbury WRC, Sudbury Bailey and Coates CSO, and Ilkley Bridge Lane CSO.
  Benson STW is flagged, not joined: its OpenMap Local lines stop before any river.
- Of the 166 position conflicts, 37 are settled: 19 at the outlet, 16 at the live position and 2 in
  the ground. One more move to the outlet, East Worthing CSO, is kept at the live position because
  the EA's features contradict it.
- 128 stay open.
- The position rule changes no listed spot. The joins change five spots' weights and no spot's set
  of overflows.
- With today's forecast (13 October, 11:54 BST build), no published level changes.

### Joins (section 1)

| Overflow | Spills a year | Trace (OS OpenMap Local) | Row |
|---|---|---|---|
| AWS01334 Sudbury WRC | 53 | The outfall is 11 m from a drawn channel (a water area). It runs to the head of an unnamed OS Open Rivers link, which meets the Stour 435 m below. No other drawn water touches it. The 2025 return's outlet, 130 m west, is 59 m from the same channel. | 15 m down the Stour below that link, 1.1 km above Friars Meadow |
| AWS01332 Sudbury Bailey and Coates CSO | 13 | The outfall is 3 m from a short channel. It runs about 120 m into an unnamed arm, which meets the Stour 95 m below. | 15 m down the Stour below the arm, 0.4 km above Friars Meadow |
| YWS00179 Ilkley Bridge Lane CSO | 4 | The outfall is 2 m from the reach OS Open Rivers names Ewe Croft Beck, below where Spicey Gill joins it. A water area 3 m away meets that reach 68 m above the Wharfe. | 15 m down the Wharfe below the beck's mouth, 1.1 km above Cromwheel |
| TWL00034 Benson STW | 31 | The outfall's line (54 m) and the lines it joins (928 m in all, with a 15 m gap allowed) run north-east and south-east, away from the river. They stop 288 m from the nearest link: an unnamed ditch that meets the Thames 1.0 km above Wallingford Beach. No water area joins them. OpenMap Local gives no name for Howbery Ditch. | **None: flagged.** Benson stays snapped onto that ditch, as before. It counts at Wallingford Beach at 0.006. |

Established: the traces above, and that each join point is upstream of the spot named.

Inferred:
- Benson's water probably reaches the Thames by that ditch, because it is the only drawn way out of
  the drains around the works. But the trace breaks, so this was not used.
- What would settle it: Thames Water's own asset map, or a look on the ground.

### The 166 (section 2)

| Class | Count |
|---|---|
| Settled: outlet (moved) | 19 |
| Settled: live (no change) | 16 |
| Settled: ground (off the network either way) | 2 |
| Kept live: a check contradicts the move (East Worthing CSO) | 1 |
| Open: under 1 km apart | 58 |
| Open: no evidence | 39 |
| Open: the two records name different waters | 17 |
| Open: evidence conflicts | 14 |

**K2, the place rule's 12.** Ten stay at the outlet. Two go back to the live position:
- **Scruton STW (YWS00371).** The place points to the outlet. The water body, "Ings Goit from
  Source to Burneston Beck", points to the live position through the word "ings", so the evidence
  conflicts. "Ings" is a common Yorkshire word for wet meadows, so this may be a false match.
- **East Worthing CSO (SWS00971).** See K3.

**Nine new moves to the outlet.** None counts at a listed spot from either position.
- AWS00702 Kirton Drunkards Lane STW: the water.
- AWS00829 Kibworth Meadowsbrook Rd SSO: the water body.
- AWS01217 Colchester Mile End Rd and AWS01221 Colchester North Gate: the water body (Salary Brook).
- SVT00595 Coalville Hermitage Road: the water and the water body.
- SVT00963 Desford Cross Road PS: the water.
- SWS00393 Petworth Road Hambledon: the water body.
- SWS00807 St Andrews Road Portsmouth: the water body.
- YWS00412 Tadcaster Road: the water.

A weakness shows in Colchester. Eleven Colchester overflows share one live position and one
outlet, so neither position is any one asset's own. Two of them move, on the water body. The other
nine stay open, because the place (Colchester, 0.55 km from the live position) points the other way.

**K3, EA features.** 41 bathing waters lie within 2 km of a conflict position, with 99 feature points.
25 conflicts have a feature within 2 km.
- **Contradicts a move.** East Worthing CSO. Its live position is 8 m from a storm overflow in the
  features for ukj2407-15350, and its outlet is 1.2 km from any. It is kept live (`KEEP_LIVE`).
- **Contradicts a settled-live case.** Elizabeth Street, Dover (SWS00259). Its outlet is 0 m from a
  storm overflow for ukj4208-13300, and its live position is 8.1 km away. The place points to the
  live position. The stated rule makes no exception in this direction, so it stays live. It is
  marine and counts at no listed spot.
- **Agrees.** Sandown New No. 1 SSO (outlet). Southend Southchurch Road and the two Broadstairs
  overflows have features at both positions.
- **Points one way where the rule leaves the case open.** It points to the outlet at AWS01190,
  NWL01292, SBB00698, SWS00474 and SWS00770, and to the live position at NWL00769 and SWS00381. All
  seven are sea or estuary outfalls with no listed spot either way. The rule used K3 only as a check,
  so they stay open. They are the easiest next cases.

**K4, OpenMap Local names, for the conflicts that change a listed spot.**
- **TWL00743, South Lane, Ash.** "The Ash" is 834 m from the live position, and the River Wey 647 m
  from the outlet. The receiving water, a Blackwater tributary, is named by neither. Open.
- **YWS00049, Darley Rd.** Horn Beck is 826 m from the live position, and Cockhill Beck 364 m from
  the outlet. The receiving water, the Nidd, is named by neither. Open.
- **TWL00418 and SWS00413.** Tiles not held, so not checked.
- **AWS00023, Arthingworth.** Live position not checked (tile not held). No water name lies within
  1 km of the outlet.
- No K4 result contradicts a move.

**The spot-relevant open cases.** Each counts at a listed spot from one position only, and none
moved.
- **TWL00418, Trumps Green Road (Virginia Water) SPS.** The live position counts at
  bw-uki2203-11942 at 0.012. The outlet counts nowhere. The place points to the live position, and
  the water body (Bulbourne) to the outlet.
- **TWL00743, South Lane, Ash.** The live position counts at Henley at 0.001. The outlet counts at
  bw-uki2203-11942 at 0.017.
- **YWS00049, Darley Rd.** The outlet counts at Knaresborough at 0.011. The live position counts
  nowhere.
- **Weight only:** Farnham STW (0.09 or 0.20 at the Wey at Waverley), the three Harrogate Oak Beck
  overflows, and two Wellow and Cam Brook overflows. These are all under 1 km apart.

**The weakest settled case.** AWS00023, Arthingworth TPS, is settled live by the place
(Arthingworth, 0.8 km). But both records name the Rhee, a Cam tributary, and so does the water
body, "Rhee (DS Wendy)". The outlet is 66 km away in Cambridgeshire. That it lies by the Rhee is
inferred: no link within 3 km carries the name. If the outlet were right, the overflow would count at Grantchester and
bw-ukh1201-09801 at 0.004 each. Nothing moves, so the map is as before.

**Spelling.** "Lilington" and "Lillington" Brook, and "Garman Carr" and "Garmancarr" Dike, count as
different waters under `_same_water`, so both cases stay open. Both pairs are under 1 km apart.

### K5, effect on spots

Both tables were built from the same snapshot and network (`b5724303`). The before table reproduces
the published `sum_weight` at Friars Meadow (2.155). 14 overflows are placed differently: the 3
joins, 9 new moves, and 2 moved back. Five spots change, all through the joins. No spot gains or
loses an overflow.

| Spot | Summed weight | What changed |
|---|---|---|
| Friars Meadow, River Stour (`bw-ukh1401-11051`) | 2.155 → 4.035 (+87%) | Sudbury WRC 0.022 → 0.945, Bailey and Coates 0.023 → 0.978 |
| River Stour, Dedham | 0.917 → 1.116 (+22%) | the same two, 0.003 → 0.10 each |
| Wharfe at Cromwheel, Ilkley (`bw-uke4100-08901`) | 5.031 → 5.958 (+18%) | Bridge Lane 0.022 → 0.949 |
| River Wharfe, Greenholme | 8.930 → 9.583 (+7%) | Bridge Lane 0.016 → 0.669 |
| Wharfe at Wilderness Carpark (`bw-uke4200-08904`) | 7.984 → 8.043 (+1%) | Bridge Lane 0.003 → 0.062 |

**Could levels move?**
- Friars Meadow, Dedham and Cromwheel pass the 10% test stated in K5. Greenholme has an overflow
  rising to 0.67.
- With today's published spill chances, no level changes. These come from click-anywhere's
  `overflow_days.json`, calibrated by lead; they reproduce the published contributors' chances to
  0.001.
  - Friars Meadow's highest day goes from 0.022 to 0.047. It stays Low.
  - Cromwheel moves by at most 0.002.
- On a wet day it could change. Sudbury WRC spills about 53 times a year, and it now counts at
  nearly full weight 1.1 km above Friars Meadow. So Friars Meadow will read higher on days when it
  is likely to spill.

### K6, tests

- `pytest -q`: 682 passed, and 4 failed in `tests/test_cards.py` (Pillow missing locally, known).
- `node --test tests/*.test.cjs`: 339 passed.

### Tiles and downloads

- OS OpenMap Local SE and TL were downloaded, 123 MB and 115 MB. SU was copied from a previous
  session's scratch folder. All three MD5s match OS's list.
- Other downloads, each one small request:
  - the EA bathing-water list;
  - the `features.json` of 41 bathing waters;
  - five published spot files, `spots-lite.json`, and click-anywhere's `overflow_days.json` and
    `overflow_ids.json`.
- No Open-Meteo requests were made, and the EA consents register was not used.
