# A lake word where no overflow is upstream: what bench read 1 supports, on the site

Written 27 November 2026. Rank 6 of the [forecast map](FORECAST-MAP-2026-11.md). Ethan said "Yes, lakes next" on
27 November 2026, in answer to "Start lakes without their own samples next?". The register left the choice of what to
show at these lakes to him ([bench read 1](BENCH-READ-LAKE-RANGE-2026-11.md), "Correction"). His standing brief leaves
everything but the fixed rules to this work, so this record makes the choice and says which part he may want to
overrule.

## What was tested

Bench read 1 (15 November 2026, statement pushed before the read): lake-range-v1's likely reading, on the
average-lake basis, at the 7 lake bathing waters it has no own level for, on 1,373 samples from 2012 to 2022 that no
model was fitted on. Within-lake rho 0.289, against production's −0.015; difference +0.304 [+0.197, +0.409] over
water-body seasons. Pass. Its chance over 900 was no better, and the bench does not measure its range's coverage.

At these lakes nothing upstream is monitored, so the figure reads only rain at the lake (48 and 24 hours to midday)
and the date. The read supports order within a lake, nothing about level.

## What the site now says

At 5 of the 7: the Serpentine, Hampstead Heath's Ladies, Mens and Mixed Ponds, and Colwick Country Park (West Lake).
Cotswold Country Park and Henleaze Lake are isolated lakes with no daily forecast, so they get nothing.

On today's day only, May to September only, one sentence under the plain level, after the line that says no
overflow was found upstream:

- "Today E. coli is estimated higher than usual for this lake."
- "Today E. coli is estimated about usual for this lake."
- "Today E. coli is estimated lower than usual for this lake."

After "Other risks apply", what it rests on:

> Higher or lower than usual comes from the rain here and the time of year, as nothing upstream is monitored. Only its order is
> tested: on past summer samples kept back to test it, at this lake and six other lake bathing waters with no overflow
> upstream, days it put higher tended to read higher. Its size is not tested, so it gives no figure. This is not a
> level.

No figure, colour, band or level. The plain level, its words and the past-samples line stay. Nothing is logged.
From now to 30 April 2027 nothing on the site changes, because the word is in season only.

## Usual

The middle third of the spot's own figures on every May to September day of 2023 to 2026, hindcast at lead 0 from
Open-Meteo's archive rain at the spot's cell (`scripts/lake_order.py freeze`): the river order line's rule
(`RIVER-ORDER-LINE-PROPOSAL-2026-11.md`, decided 17 November 2026). Higher is above two thirds, lower below one
third, compared on log10 of the figure at 3 decimal places. Frozen in `data/processed/lake_order.v1.json`
(`93174f9b…`), tied to lake-range-v1's hash. 588 days per spot. The three Hampstead ponds share one rain cell, so
they share cut-points and always read alike.

The proposal's own threshold (twice usual or half, `LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md`) was checked first, on
the bench's seen rows: at these lakes it read "about usual" on 402 of 403 sample days, because rain alone moves the
figure little (at most about 3 times from driest to wettest). A word that never moves says nothing, so the thirds
rule replaced it here. The 11 lakes with their own level keep the proposal's rule.

No request was made. The 12 archive files were copied to a scratch cache; their hashes are in the file and were the
same before and after.

## How the word did on seen years (development, decides nothing)

On the bench's seen rows at these 5 lakes (2023 to 2026, the same years the cut-points come from), measured samples:

| Word on the sample's day | Samples | Geometric mean E. coli | Over 500 |
|---|---|---|---|
| Higher | 120 | 100 | 10 |
| About | 122 | 72 | 2 |
| Lower | 106 | 61 | 1 |

Higher over lower within each lake: 2.66 at the Serpentine, 2.91 Ladies, 1.21 Mens, 2.40 Mixed, and **0.49 at
Colwick**, which went the wrong way. Pooled within lake 1.62. Colwick stays: the test pooled all 7 lakes, and dropping
one on its 64 seen samples would choose a subgroup after looking. Its 2012-22 figure alone was not reported by the
bench and is not computed here, because that would read held-out rows outside the bench's ledger. This is the part
Ethan may want to overrule.

## How strong it is, said plainly

A within-lake rho of 0.29 ranks two days at a lake the right way round about 60% of the time (0.597 from the
normal-theory conversion; inferred, not measured). It is a gentle comparison, not a warning. "Lower than usual" is
not a clearance.

## How it stands to what is decided (docs/DESIGN.md)

- **Reverses, at these 5 lakes only:** "no E. coli estimate at these spots" (3 and 11 October 2026, "Where the model has
  nothing to forecast"). The reason: that rule was made because nothing had tested an estimate there; bench read 1 now
  has, for order. The word gives no figure, so the estimate is still not shown as a number.
- **Already decided, followed:** a spot's own thirds, a word with no colour, level or figure, today only where the test
  was at lead 0, none of "safe", "clean", "exceed" or "breach" (#709, #736, #763). Where it sits on the page and how
  its basis is said follow the rain word (#763).
- **New:** the words themselves.

## How it will be judged

On or after 15 October 2027, at these 5 bathing waters, with the 2027 season's Environment Agency samples: each
sample's word recomputed from the frozen model, the frozen file and Open-Meteo's archive rain at lead 0 (no log is
needed: the word is a fixed function of those). The geometric mean of samples on "higher" days over that on "lower"
days, pooled within lake, interval from lake-weeks. It stays in 2028 only if that ratio is above 1 with its interval
above 1. Few samples (about 100 a season over 5 lakes) may leave the interval wide; if so the record will say the
season could not judge it, not that it passed.

## Files

`src/dipcast/lake_order.py`, `data/processed/lake_order.v1.json`, `scripts/lake_order.py`,
`src/dipcast/model/forecast.py` (`lake_order` on today's row), `src/dipcast/site/levels.js` (`LAKE_ORDER`,
`LAKE_ORDER_SAID`, `lakeOrder`), `src/dipcast/site/preview/model.js` (`answer`), `src/dipcast/pages/methods.html`
(`#lake-word`), `tests/test_lake_order.py`, `tests/site_preview.test.cjs`. The classic pages are unchanged, as for the
rain word.
