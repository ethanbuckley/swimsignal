# Overflow positions by the water body's catchment: the rule, stated before it is applied

Written 15 October 2026. Main was at 1da6ad0. Follows `docs/OVERFLOW-POSITIONS-2026-10.md` (#209)
and `docs/OVERFLOW-SEA-OUTFALLS-2026-10.md` (#214). This file is committed and pushed before any
catchment is fetched for a case. Results go under the line at the end. Nothing above that line
changes afterwards.

## Why

125 of #209's 166 position conflicts are open. Their evidence so far is names: the receiving
water's, the WFD water body's and the place's, each looked for within 3 km. Names fail when they
are generic or when the two positions are under 1 km apart.

Each annual return also gives the overflow's **WFD water body ID** (`wfd_waterbody_id`, for example
GB104027057510). The EA publishes each river water body's catchment as a polygon: the land that
drains to it. An overflow that spills into a water body should lie in or at the edge of that water
body's catchment. That is a test of position that uses no names.

## Source and licence

*WFD River Water Body Catchments Cycle 3 Classification 2022 (Full Resolution)*, Environment Agency,
**Open Government Licence v3.0**, as its catalogue entry states (read 15 Oct 2026). Each polygon carries
`water_body_id`. The polygons are fetched one ID at a time from the EA's OGC features API
(`environment.data.gov.uk/spatialdata/wfd-river-water-body-catchments-cycle-3-classification-2022`).
Attribution: © Environment Agency copyright and/or database right 2024.

## What was looked at before this was written

- One feature of the dataset, to read its fields. It was the first in the API's order, a coastal
  catchment unrelated to any case.
- No catchment was fetched for any of the 166, and no position was tested against one.

## The rule

**Inputs.** As #209 and #214:
- the 166 conflicts in `docs/OVERFLOW-POSITIONS-2026-10-cases.csv`;
- each one's live position from the 13 Oct 03:20 UTC snapshot;
- its outlet and water body ID from its latest annual return.

**E4, the catchment.**
- A position is **in** when it lies inside the water body's catchment polygon or within 50 m of it.
  The margin allows for an outfall on the river at the catchment's edge.
- A position is **out** when it is over 250 m outside.
- E4 points to a position when that position is in and the other is out. Otherwise E4 points nowhere.
- Cases with no water body ID, or whose ID has no polygon, get no E4.

**V, a check on E4 itself, before anything moves.**
- Apply E4 to the 38 cases already settled by other evidence: #209's 19 outlet and 16 live (the 2
  ground cases are left out), and #214's 3.
- Where E4 points, count how often it agrees.
- **If it disagrees in more than 10% of the cases where it points, or in more than 2 when it points in
  fewer than 20, E4 is not used.** Nothing moves, and the results say so.

**Settling, only if V passes.** An open case is settled to the position E4 points to when all of
these hold:
- it is in #209's class "no evidence" or "under 1 km apart";
- the two receiving waters agree (`_same_water`), and neither says ground;
- no other kind of evidence points to the other position: E1 to E3 of #209, or the EA features (#214).

"Evidence conflicts" and "different waters" stay open whatever E4 says.

**Outcome.**
- Settled to the outlet: the overflow moves to its annual-return outlet.
- Settled to the live position: no move, and the case is recorded so later rules leave it.

**In code.**
- The settled cases go in a data file, `data/raw/overflow_positions_checked.csv`. It holds the site
  id, the position, the outlet's BNG point as checked, the source and the reason. It is read by
  `choose_positions` beside `FEATURE_OUTLET` and `KEEP_LIVE`.
- An outlet move holds only while the outlet stays within 100 m of the point checked. So a later
  return that gives a new outlet is not moved unchecked.
- The build does not fetch catchments.

## Checks, run after this file is pushed

- **V**, as above, with every disagreement listed.
- **K1.** The count settled each way, and every case with its E4 result, in a cases file.
- **K2. Effect on spots.** Build the overflow table before (main) and after (this branch) from the
  same snapshot and network, then trace every listed spot. Report every spot whose set of overflows
  or summed weight changes, and name any change large enough to move a level: a new overflow above
  0.1 weight, or a summed weight up or down by more than 10%.
- **K3. Tests.** `pytest -q` (4 known Pillow failures in `tests/test_cards.py`) and `node --test`.

---

## Results
