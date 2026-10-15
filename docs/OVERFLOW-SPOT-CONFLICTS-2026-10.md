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
