# Dilution by urban area per overflow: the test, stated before any result

Written 11 October 2026, before any E. coli score was computed for this term. It follows PR #166,
which added `DIPCAST_DILUTION_MODE=flow` after Dr James Shucksmith's review of 9 October 2026.
#166's flow dilution gave every overflow upstream of a spot the same spill size. James's fuller
suggestion was a spill size per overflow, from the urban area that drains to it. This is that term.

## The term

`DIPCAST_DILUTION_MODE=urban`. Off by default.

For overflow i upstream of a spot:

    dilution_i = Q_i / (Q_i + Q50_spot)
    Q_i        = Q_SPILL * A_i / A_MED

- `Q50_spot`: as in `flow` mode. `Q50_PER_KM2 * catchment_km2(network length upstream of the spot)`,
  over the whole catchment, not the traced 60 km.
- `Q_SPILL` = 0.068 m³/s: the fixed spill of `flow` mode (the Q50 of a catchment with L0 = 5 km of network).
- `A_i`: urban area apportioned to overflow i, in km², clipped to [0.1, 6.0].
- `A_MED` = 0.512 km²: the median of A_i over all 14,630 overflows in the table. So the median overflow
  gets the same spill as in `flow` mode. Only the spread between overflows is new.
- An overflow missing from the lookup table gets A_i = A_MED, so it gets the spill from `flow` mode.
- The lake factor and the low-snap factor apply afterwards, as in the other modes.

Why linear in area: Quaranta et al. (2022, J. Hydrol. Reg. Stud. 41, 101080) model spill volume per unit
of impervious urban area, and the result scales linearly with that area.

## A_i, the apportioning rule

1. Each overflow in the overflow table with coordinates (14,630, snapped or not) gets the nearest
   built-up area within 1,000 m, in British National Grid.
2. A built-up area's land area is split equally between the overflows it gets.
3. No built-up area within 1,000 m: A_i = 0.1 km², half the smallest built-up area (0.2 km²).
4. Cap 6.0 km², about the 99th percentile of the shares. Most shares above it are outer London
   boroughs with one to three overflows, where most of the built area has separate sewers.

Descriptives, from the data only, with no outcome used: 13,188 overflows are within 1,000 m of a
built-up area and 1,442 are not. The assigned shares have a median of 0.56 km² and quartiles of
0.31 to 0.98 km².

What it is not: a built-up area is land with buildings. It is not the impervious area connected to a
combined sewer. An equal split ignores which overflow serves which part of a town.

## Data

ONS, Built Up Areas (December 2022) Boundaries GB BGG, 8,545 polygons, made from OS Open Built Up
Areas on a 25 m grid.
https://www.arcgis.com/home/item.html?id=ad30b234308f4b02b4bb9b0f4766f7bb
Open Government Licence v3.0 (https://www.ons.gov.uk/methodology/geography/licences).
Credit: "Source: Office for National Statistics licensed under the Open Government Licence v.3.0.
Contains OS data © Crown copyright and database right 2022."

## The evaluation

The evaluation chain is the same as PR #166's, unchanged: `validate_ecoli.py`, `replay_ecoli_leads.py`,
`validate_ecoli_combined.py`, `train_ecoli.py`.
- Each variant runs in its own scratch DIPCAST_ROOT.
- Rain comes from the cache only. Outgoing network connections are refused.
- Three fresh runs on the same inputs: default (`length`), `flow` and `urban`. Speed stays `fixed`.

Added on top, reading those outputs only, with 2,000 resamples and seed 1:
- A paired site-week bootstrap of the LOYO full-model Brier and AUC change, `urban` against default,
  over all sites and over rivers. It uses train_ecoli's `cluster_bootstrap` on the samples that both
  runs keep.
- A paired site bootstrap of the change in cross-site rho, `urban` against default. Cross-site rho is
  the Spearman correlation of site-mean exposure with site-mean log E. coli, on the rows
  validate_ecoli_combined uses. Sites are resampled with replacement.
- The same two comparisons for `flow` against default, for context only.

## What counts as better

`urban` passes only if all three hold:

1. The full model's held-out Brier is lower than default's in LOYO, LOSO and the forward test
   (point estimates).
2. For LOYO AUC, over all sites and over rivers, the paired 95% interval of the change reaches 0 or above.
3. For cross-site rho, the paired 95% interval of the change reaches 0 or above.

If it passes, it is recommended as a candidate to switch on, and the switch is Ethan's decision. If it
fails, the default stays `length`. If the formula is changed after results are seen, both results are
kept and the change is stated.
