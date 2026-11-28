# Does the average-lake range hold at a lake the model knows nothing about?

Plan written 28 November 2026 and pushed before any figure below "Results" was computed. Development work on seen
rows (2023-26): it decides what the site shows at spots whose range has no test of its own, not a forecast claim.
Ethan said "Yes, check it" on 28 November 2026.

## Why

The redesign now shows the lake range as a row (#771), so from 1 May 2027 the 17 lake spots on the average-lake basis
show a likely reading and 8-in-10 range on the main site (they had it at `classic/` since #585). Live on 28 November:
Ullswater ×3, Bassenthwaite, Grasmere, Rydal Water, Elter Water, Windermere Waterhead, Derwent Water Calfclose Bay,
Loch Ness (Dores) and Loch Lomond ×7. None has samples of its own. What is known says the basis can miss either way:
at Windermere and Frensham treated as unknown it sat high (#584, supplementary: 75.6% inside, 19.9% below); at the 7
bathing lakes with no level it sat low on seen years (bench read 2: 59% inside, 38% above).

## What is computed

Rows: the bench's seen rows (`seen.parquet`, sha256 in the bench manifest), lake rows only for scoring. Coverage is
the bench's `inside80` (#584's condition 1). Each fit is lake-range-v1's form and fitting code
(`concentration_study.CensoredRI(ecoli.FEATURES, lake_sigma=True)`) on the seen rows at sites with an overflow upstream,
the rows lake-range-v1 was fitted on.

- **A. The average-lake basis as shown.** Leave one water body out: for each of the 5 lake water bodies in the fit
  (Windermere, Coniston, Derwent Water, Rutland Water, Frensham), refit without it and score its rows with the
  refit's prior (the average lake). For the 5 lake water bodies never in the fit (the Serpentine, Hampstead Heath,
  Henleaze, Cotswold, Colwick), score with the full fit's prior.
- **B. A typical lake from the known lakes.** The same folds, but the unknown lake's level is an equal-weight mixture
  over the water bodies the fit has a level for (each water body the mean of its sites' node weights), in place of
  the fitted prior.
- **C. Another site on the same lake.** Leave one site out within a water body with two or more sites (Windermere ×4,
  Coniston ×3, Rutland ×2, Hampstead Heath ×3): the left-out site's level is the mean of the other sites' node
  weights, from the full fit (and, for Hampstead, from the own levels' rule on the seen rows without that site).

## Decision rule, fixed now

The bar is #584's: overall inside the 8-in-10 range between 70% and 90%, and every water body (for C, every site)
60% or more.

- **Spots on a lake with no sampled site** (Ullswater, Bassenthwaite, Grasmere, Rydal, Elter, Loch Ness, Loch
  Lomond): if A meets the bar, nothing changes. If A fails and B meets it, these spots move to B. If both meet it,
  the one nearer 80%. If neither, these spots stop showing a likely reading and range; the row says the estimate is
  not shown because a typical lake's range did not hold where it was checked.
- **Spots on a lake with a sampled site elsewhere** (Windermere Waterhead, Derwent Water Calfclose Bay): if C meets
  the bar, they take their lake's level (the mean of its sites' node weights); otherwise the rule above.
- Scottish lochs are not in any fitted row. Whatever passes here is evidence from English lakes; the record will say so
  beside any change there.
- Nothing about lake-range-v1, the 11 lakes, the 5 with own levels, the shadow table or any frozen window changes.

## Results

Computed on 28 November 2026 by `scripts/lake_average_check.py` from the plan at `f1833891` (pushed 15:03 UTC, before
the run); figures in `docs/lake-average-check/results.json`. Seen rows only; no held-out row and no request. The refit
on the 1,675 training rows (31 sites) reproduces lake-range-v1: tau 0.2838 against 0.2845, lake noise 0.6966 against
0.6966 (lake-range-v1 was fitted on 1,672 rows; the bench rebuilt 3 more).

| Basis | Inside the 8-in-10 range, all lake rows | Lowest water body (site, for C) | Bar met |
|---|---|---|---|
| A: the average lake, as shown | **69.4%** | 41% (the Serpentine) | no |
| B: equal mixture of the known lakes' levels | **77.4%** | 53% (Derwent Water) | no |
| C: the same lake's other sampled sites | **82.6%** | 68% (Windermere, Fellfoot) | yes |

| Lake water body | Rows | A: average lake | B: known lakes' mixture |
|---|---|---|---|
| Colwick Country Park (West Lake) | 64 | 69.6% | 80.5% |
| Coniston Water | 171 | 82.2% | 83.6% |
| Cotswold Country Park and Beach | 54 | 68.7% | 76.6% |
| Derwent Water | 58 | 51.3% | 53.0% |
| Frensham Great Pond | 54 | 83.0% | 89.1% |
| Hampstead Heath | 205 | 61.4% | 77.8% |
| Henleaze Lake | 76 | 56.6% | 84.2% |
| Rutland Water | 141 | 78.6% | 80.1% |
| The Serpentine - Hyde Park | 79 | 40.9% | 73.7% |
| Windermere | 308 | 75.0% | 73.6% |

A misses both ways: too low at the London ponds, Henleaze, Cotswold and Colwick (up to 58% above it at the
Serpentine), and too high at Windermere (22% below). Derwent Water is above both A and B nearly half the time (its
summer-long rise, `DERWENT-WATER-DIAGNOSIS-2026-11.md`). B helps at the no-overflow lakes and still fails at Derwent.

| Site left out | Rows | C: the lake's other sites |
|---|---|---|
| Coniston Water, Brown Howe | 57 | 84.0% |
| Coniston Water, Boating Centre | 57 | 81.0% |
| Coniston Water, Monk Coniston | 57 | 77.4% |
| Hampstead Heath (Ladies Pond) | 78 | 92.3% |
| Hampstead Heath (Mens Pond) | 59 | 88.4% |
| Hampstead Heath (Mixed Pond) | 68 | 96.8% |
| Rutland Water Whitwell Creek | 73 | 77.8% |
| Rutland Water Sykes Lane | 68 | 80.6% |
| Windermere, Lakeside YMCA | 77 | 75.9% |
| Windermere, Millerground Landing | 77 | 85.0% |
| Windermere, Rayrigg Meadow | 77 | 85.1% |
| Windermere, Fellfoot | 77 | 68.3% |

## What follows, by the rule above

- **The 15 spots on a lake with no sampled site** (Ullswater ×3, Bassenthwaite, Grasmere, Rydal Water, Elter Water,
  Loch Ness, Loch Lomond ×7): A and B both fail, so the likely reading and range are no longer shown. The redesign's row
  says "Not given here" and why; `classic/` says the same in its own row. The range is still computed and logged in
  `shadow_lake_range_v1` exactly as before, so the 2027 read is untouched (`ecoli_range_withheld` marks the spot).
- **Windermere Waterhead and Derwent Water Calfclose Bay:** C meets the bar, so each shows its lake's level (the mean
  of Windermere's four sites' node weights; Derwent's Crow Park). Derwent has one site, so C was not checked there;
  the decision rests on the four lakes where it was. Neither spot has a usual line.
- **Limits.** Seen rows, so development evidence: the decision is about not showing a range that failed, and about
  showing one that held on the same rows, not a forecast claim. The Scottish lochs were never in any fitted row; the
  failure of the average lake at English lakes is the reason they lose the range too.
