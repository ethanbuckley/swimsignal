# The three open position conflicts that change a listed spot: the rule, stated before the checks

Written 15 October 2026. Main was at 1da6ad0. Follows `docs/OVERFLOW-POSITIONS-2026-10.md` (#209),
whose "spot-relevant open cases" these are. This file is committed and pushed before any map tile is
read for these three. Results go under the line at the end. Nothing above that line changes afterwards.

## The three, as #209 left them

| Overflow | Receiving water (live / return) | WFD water body | Gap | #209 evidence | Counts at |
|---|---|---|---|---|---|
| TWL00418 Trumps Green Road (Virginia Water) SPS | River Bulborne / River Bulborne | Bulbourne | 42.7 km | place → live; water body → outlet | live: Ham and Kingston, 0.012. Outlet: nowhere |
| TWL00743 South lane, ash | Tributary of River Blackwater / TRIB OF BLACKWATER | Wey (Shalford to Thames) | 9.0 km | water → live; water body → outlet | live: Henley, 0.001. Outlet: Ham and Kingston, 0.017 |
| YWS00049 FIELD 0064 DARLEY RD/CSO | River Nidd (via sewer to mill race) / RIVER NIDD | Crimple Beck from Source to Park Beck | 8.0 km | water → outlet; water body → live | live: nowhere. Outlet: Knaresborough, 0.011 |

The weights are small: 0.017 at most. No level is expected to change. The point is that the map
places these overflows correctly.

## What was looked at before this was written

- The rows above, and the two positions of each, from #209's files.
- No map tile was read for these three. #209's K4 listed OpenMap Local water names within 1 km for
  TWL00743 and YWS00049. They named neither receiving water.
- **A hypothesis, formed while reading the rows.** Trumps Green Road is in Virginia Water, Surrey.
  The local stream there is the Bourne (Chertsey Bourne), not the Bulbourne, which is in
  Hertfordshire. "Bulborne" may be a mis-entry for "Bourne", and the outlet and water body may then
  have been filled in to match it. The rule below does not use this. It is listed so the reader can
  see it was formed before the checks.

## The rule

The evidence is OS OpenMap Local (Open Government Licence), tiles TQ, SU, SE and SP. Two kinds:

- **R1, the road.** The site name gives a road: Trumps Green Road, South Lane, Darley Road. An
  OpenMap Local road with that name (case ignored; "Rd" read as "Road") points to a position when it
  lies within 500 m of that position and not within 500 m of the other.
- **R2, the water.** An OpenMap Local water line or named water feature points to a position when it
  lies within 1 km of that position and not within 1 km of the other. It must carry a distinctive word
  of a receiving-water name: "Bulborne" or "Bulbourne", "Blackwater", "Nidd". For "tributary of X", X
  counts.

**Settled** when R1 points to a position and R2 does not point to the other. #209's name evidence
(E1 to E3) is not re-counted. It already conflicts in all three, which is why they are open.
- Settled to the outlet: the overflow moves to it, through the same checked list as #214
  (`FEATURE_OUTLET`, renamed `CHECKED_OUTLET`, with the road's point as the check).
- Settled to the live position: it goes in `KEEP_LIVE` with the reason.
- Otherwise it stays open, and the result says which check failed.

## Checks, run after this file is pushed

- **C1.** For each of the three: R1 and R2 at each position, with names and distances.
- **C2. Effect on spots.** Build the overflow table before (main) and after (this branch) from the same
  snapshot (13 Oct 03:20 UTC) and network. Trace every listed spot and report every change in a spot's
  set of overflows or summed weight.
- **C3. Tests.** `pytest -q` and `node --test`.

---

## Results

Added after commit 4486875, pushed at 22:45 BST on 15 October 2026 before any tile was read for these
three. Tiles TQ and SP were downloaded; SE and SU were reused from #209. All four MD5s match OS's list.

**Answer.**
- One of the three is settled: **South Lane, Ash stays at its live position**, now in `KEEP_LIVE`.
- The other two stay open.
- Nothing moves and no spot changes. All three were already at their live positions.

### C1

| Overflow | R1, the road (500 m) | R2, the water (1 km) | Outcome |
|---|---|---|---|
| TWL00418 Trumps Green Road | no road of that exact name within 3 km of either position | River Bulbourne 876 m from the outlet; none near the live position | **open**: R1 does not point, R2 points to the outlet |
| TWL00743 South lane, ash | South Lane **2 m from the live position**; none near the outlet | Blackwater River 1,966 m from the live position (outside 1 km); none near the outlet | **settled: live** |
| YWS00049 Darley Rd | Darley Road 2,195 m from the outlet (outside 500 m); none near the live position | River Nidd 1,486 m from the outlet (outside 1 km); none near the live position | **open**: neither points |

The settled case adds nothing to the map, because the live position is the default. The entry guards
it against a later rule moving it 9 km east to the Wey.

### Seen after the rule ran, not used

- **Trumps Green Road.** OS spells it **Trumpsgreen Road**, and it lies **85 m from the live
  position**. Trumps Green Avenue and Trumps Green Close are nearby too. The rule asked for the exact
  name, so the case stays open.
- **The Bourne** is labelled 2.5 km from the live position. This supports, but does not prove, the
  hypothesis stated above: "River Bulborne" is a mis-entry for the Bourne, and the outlet and water
  body were then filled in to match.
- What would settle it: a stated rule that matches road names with their spaces removed, or Thames
  Water's own record. Since the overflow already sits at its live position, nothing on the map
  depends on it today.
- **Darley Rd** has a Darley Road 2.2 km from the outlet, on the Nidd side. That leans toward the
  outlet, but only weakly, and the rule does not use it.

### C2, effect on spots

Both tables were built from the 13 Oct snapshot on network `b5724303`: main (1da6ad0) and this branch.
Both give 61 moves to the outlet. Overflows placed differently: 0. Listed spots that change: 0.

### C3, tests

- `pytest -q`: 718 passed, 4 known Pillow failures.
- `node --test`: 342 passed.
