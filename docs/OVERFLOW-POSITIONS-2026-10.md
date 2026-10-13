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

(Added after this file was pushed.)
