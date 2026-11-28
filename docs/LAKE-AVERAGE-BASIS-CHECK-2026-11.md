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

(Not computed when this plan was pushed.)
