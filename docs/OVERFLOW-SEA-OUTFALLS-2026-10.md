# Seven sea outfalls settled by the EA's bathing-water features: the rule, stated before it is applied

Written 15 October 2026. Main was at b7f930a. Follows `docs/OVERFLOW-POSITIONS-2026-10.md` (#209),
whose check K3 found seven open conflicts where the EA's features point one way. This file is
committed and pushed before the rule below is applied or any feature file is fetched again. Results
go under the line at the end. Nothing above that line changes afterwards.

**Inputs.** The same as #209, so the two can be compared: the `state` release's live snapshot
(`live_latest.parquet`, uploaded 13 Oct 2026 03:20 UTC), the annual returns 2021–2025, and the river
network as main loads it (topology key `b5724303`). Builds go into a scratch `DIPCAST_STATE`. The EA
bathing-water list and the `features.json` files are fetched again today.

**Licence.** Open Government Licence sources only, as #209. The EA consents register is not used.

## What was known before this was written

- **The seven.** #209's K3 found that an EA feature point lies within 100 m of one position and not the
  other, while #209's rule left the case open:

  | Overflow | Water (both records) | #209 class | Gap | K3 points to |
  |---|---|---|---|---|
  | AWS01190 Southend Prittle Brook Storage Tank | Thames Estuary | no evidence | 1.6 km | outlet (0 m; live 1.46 km) |
  | NWL01292 Station Road CSO, Redcar | North Sea | under 1 km apart | 0.55 km | outlet (3 m; live 550 m) |
  | SBB00698 Littlegate Road CSO, Paignton | English Channel and Victoria Park watercourse | no evidence | 1.1 km | outlet (0 m; live 482 m) |
  | SWS00474 Kings Hall, Herne Bay | North Sea | under 1 km apart | 0.37 km | outlet (0 m; live 370 m) |
  | SWS00770 Shoreham CSO | English Channel | no evidence | 2.8 km | outlet (6 m; live 2.84 km) |
  | NWL00769 Lakes CSO, Redcar | North Sea | under 1 km apart | 0.62 km | live (0 m; outlet 581 m) |
  | SWS00381 Marsh Road, Gurnard | The Solent | no evidence | 2.2 km | live (16 m; outlet 1.89 km) |

- **None counts at a listed spot** from either position (#209's snap at both positions, traced at all
  105 listed spots). So no published level is expected to change. The gain is a correct map.
- **What a feature is.** Each item in `features.json` has a type (for example "Emergency or Storm
  Overflow", "Surface Water Outfall", "River or Stream Intersection") and a point to 10 m. It has no
  name and no permit number. So a match says the EA's bathing-water profile draws an outfall of that
  type at that point. It does not say which overflow it is.
- **#209's K3 matched any feature type** at both positions. Of the seven, K3's nearest feature at the
  matching position was a storm overflow in every case. At the other position it was sometimes
  another type (Southend live: a surface water outfall; Paignton live: a river intersection).
- **The two Redcar overflows look like a pair.** Station Road's live position is about 35 m from Lakes
  CSO's outlet. Seen while drafting this, from the positions in #209's conflicts file.

Inferred, not established:
- A feature 0 m from an annual-return outlet probably shares a source with it, such as the permit's
  grid reference. Then it confirms that the EA's profile agrees with the return, not that someone
  surveyed the outfall. A match at the live position (Lakes CSO, Marsh Road, and East Worthing in
  #209) cannot be explained that way, so the profiles are not simply copies of the returns.

## The rule

A case is settled to a position when all four hold. Otherwise it stays open and is listed with the
check that failed.

- **S1. Storm overflow at one position only.** Fetch today's `features.json` for every bathing water
  whose sampling point is within 2 km of either position. A position matches when it is within 100 m
  of a feature of type "Emergency or Storm Overflow". It must match at one position, and the other
  position must have no such feature within 100 m.
- **S2. Same water.** Both records name the same receiving water (`_same_water`), and neither says
  ground (`to_ground`).
- **S3. Unclaimed.** No other overflow in the table (any id, at its live position or its outlet) lies
  within 100 m of the matched feature. Otherwise that overflow may be what the feature shows.
  This is checked at the positions after the settled ones move, so a pair like Redcar is judged as
  the build will place it.
- **S4. One feature, one overflow.** No two of the seven settle onto the same feature.

**Settled to the outlet:** the overflow moves to its annual-return outlet.
**Settled to the live position:** no change, because the live position is the default.

**In code.** A list beside `KEEP_LIVE` in `overflows.py`, as checked cases, not a rule run at each
build. The build does not fetch features. Each move carries the matched feature's point and applies
only while the outlet is still within 100 m of it. A later annual return that states a new outlet then
leaves the overflow at its live position, as before, instead of moving it somewhere unchecked. The
cases settled to the live position are added to `KEEP_LIVE` with their reason, so no later rule moves
them without saying so.

## Checks, run after this file is pushed

- **C1. The four checks** for each of the seven, with the matched feature's bathing water, type,
  point and both distances.
- **C2. Did the features change?** Compare today's features near the seven with #209's copies of
  13 October. Report any feature added, removed or moved.
- **C3. Effect on spots.** Build the overflow table twice on scratch state from the same snapshot and
  network: before (main) and after (this branch). Trace all listed spots (`spots.csv` and
  `spots-osm.csv`) with `upstream_overflows` on both. Report every spot whose set of overflows or
  summed weight changes. Expected: none.
- **C4. Tests.** `pytest -q` with the venv (4 known Pillow failures in `tests/test_cards.py`), and
  `node --test tests/*.test.cjs`.

---

## Results

Added after commit 4bba063, which was pushed at 19:38 BST on 15 October 2026 before any of this was
fetched or run. Each case, with its distances and the overflows near its feature, is in
`docs/OVERFLOW-SEA-OUTFALLS-2026-10-cases.csv`.

**Answer.**
- 3 of the 7 are settled, not 7. Station Road CSO (Redcar) and Kings Hall (Herne Bay) move to their
  outlets. Marsh Road (Gurnard) stays at its live position and is added to `KEEP_LIVE`.
- 4 stay open, all on S3: another overflow already sits within 100 m of the same feature.
- No listed spot changes. Both moved overflows are marine before and after the move, so they are
  left out of river tracing either way. What changes is where they are drawn.

### C1, the four checks

| Overflow | S1: storm overflow within 100 m | S2 | S3: other overflows within 100 m of the feature | Outcome |
|---|---|---|---|---|
| NWL01292 Station Road CSO, Redcar | outlet 3 m, live 550 m (ukc1202-06400) | yes | none | **outlet** |
| SWS00474 Kings Hall, Herne Bay | outlet 0 m, live 370 m (ukj4202-12200) | yes | none | **outlet** |
| SWS00381 Marsh Road, Gurnard | live 16 m, outlet 2.17 km (ukj3400-17700) | yes | none | **live** |
| AWS01190 Southend Prittle Brook Storage Tank | outlet 0 m, live 1.47 km (ukh3100-11902) | yes | AWS01191 and AWS01192, Southend Chalkwell/Ridgeway, both positions 10 m | open |
| SBB00698 Littlegate Road CSO, Paignton | outlet 0 m, live 694 m (ukk4200-24100) | yes | SBB00274 Clennon Valley SPS and SBB00900 Paignton Tank CSO, both positions 0–1 m | open |
| SWS00770 Shoreham CSO | outlet 6 m, live 2.84 km (ukj2401-15100) | yes | SWS00769 Albion Street, Portslade, live 10 m and outlet 6 m | open |
| NWL00769 Lakes CSO, Redcar | live 0 m, outlet 581 m (ukc1202-06300) | yes | NWL00930 New Coatham CSO, both positions 49 m | open |

S4 held: no two of the seven matched the same feature.

Established: every distance above, from today's feature files and the 13 October snapshot.

Inferred, not established:
- At Southend, Paignton and Shoreham the other overflows sit on the feature at both of their own
  positions, so that feature is most likely theirs. The overflow under test may share their sea
  outfall: a storage tank or a second overflow often spills through the same long pipe. If so, its
  outlet would be right too. The features cannot tell, because they carry no name or permit.
- What would settle these four: the company's own asset record of which outfall each overflow uses,
  or the permit number on a feature, which the EA's files do not give.
- The distances to "any storm overflow" differ from #209's K3, which took any feature type. Paignton's
  live position is 482 m from a river intersection and 694 m from the nearest storm overflow. Marsh
  Road's outlet is 1.89 km from a river intersection and 2.17 km from the nearest storm overflow.

### C2, did the features change?

The seven's positions lie within 2 km of 15 bathing waters. #209 held copies of all 15 from
13 October. Today's files are identical to those copies: 50 feature points, no feature added,
removed or moved. 27 are storm overflows, 14 river or stream intersections and 9 surface water
outfalls.

### C3, effect on spots

Both tables were built from the same snapshot (`live_latest.parquet`, MD5 5877fc61…) and network
(`b5724303`). Main's build reproduces #209: 59 moves to the outlet, 40 by the named water and 19 by
the evidence. This branch moves 61: the same 59 plus the 2 by the EA's features.

- Overflows placed differently: 2, NWL01292 and SWS00474. Both are `marine` before and after.
- Listed spots whose set of overflows or summed weight changes: 0 of all in `spots.csv` and
  `spots-osm.csv`.

### C4, tests

- `pytest -q`: 717 passed, and 4 failed in `tests/test_cards.py` (Pillow missing locally, known).
- `node --test tests/*.test.cjs`: 341 passed.

### Downloads

The EA bathing-water list and 15 `features.json` files, each one small request. No Open-Meteo
requests were made, and the EA consents register was not used.
