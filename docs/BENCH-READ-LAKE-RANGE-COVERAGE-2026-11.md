# Bench read 2: does lake-range-v1's 8-in-10 range hold at the 7 lakes without their own level, given one?

Statement written 28 November 2026 and pushed before the read. Nothing below the line "Result" existed when it was
pushed. Candidate: `scripts/backtest_bench/candidates/lake_range_v1_ownlevel.py`. Bench:
[BACKTEST-BENCH-2026-11.md](BACKTEST-BENCH-2026-11.md). The register's next step after
[bench read 1](BENCH-READ-LAKE-RANGE-2026-11.md) and the [lake word](LAKE-ORDER-NO-OVERFLOW-2026-11.md): "a coverage
read for the range".

## What was found first, on seen rows (development, decides nothing)

The bench gained a coverage score for this read (`bench.inside80`: #584's condition 1, the share of results whose
randomised PIT lies in 0.1 to 0.9, taken as its expectation; a "<10" or ">10000" result counts by the chance the
model gives below or above the lab's limit). On the seen rows (2023-26) at the 7 lake bathing waters lake-range-v1 has
no level for, its range on the average-lake basis held **59%** of results, with **38% above it** (478 rows). At the 11
with their own level it held 81% (732 rows). The average lake's likely reading there is about 12; the 7 lakes'
measured medians are 27 to 150 (the Serpentine 150, Henleaze and the Ladies Pond 110). So the average-lake range is
too low at these lakes. That basis is not tested further here.

## The candidate

lake-range-v1 with every parameter frozen (beta, tau, the lake noise level 0.697, the nodes, the prior), plus a level
for each lake bathing water the file has none for, learned from the training rows by the rule that made the 11
levels in the file: prior node weights plus the summed censored-normal log-likelihood of the lake's own samples,
normalised (`concentration_study.CensoredRI._site_post`). In `final` the training rows are the seen rows, 2023-26,
so each of the 7 gets a level from its 2023-26 samples. Nothing in it was chosen after looking at any coverage figure:
the rule is the existing one, and the range is the page's 10th to 90th centile.

Season-out on the seen rows (development, levels learned from the other three seasons): **90.2%** inside, 5.0% below,
4.8% above at the 7; by lake 70% (Cotswold) to 100% (Henleaze). The range is a little wide there. This is known before
the read and is why the result may fall either side of the upper bar.

## What is fixed

- **Rows.** The bench's frozen held-out rows (`heldout.parquet`, sha256 `b3a30b5e…`), subset `lake_not_read_before`:
  the 7 lake bathing waters, 2012-22, 1,373 rows. Read once before (ledger read 1) for order and Brier; no coverage or
  quantile figure was computed on them.
- **Conditions,** #584's conditions 1 and 3, the bar the range at the 11 lakes met:
  1. The share of results inside the candidate's 8-in-10 range (`cover80`) is between 70% and 90%.
  2. At each of the 5 water bodies, at least 60% inside (`cover80_by_water_body`).
- **Interval.** 95%, water-body seasons (`ci95_season`, seed 20261115), reported; the conditions are on the point
  figures, as in #584.
- **One read.** Ledger read 2. No variant follows on these rows under this statement.

## What each outcome leads to

- **Both pass.** At the 5 with daily inputs (the Serpentine, the three Hampstead ponds, Colwick), the likely reading
  and 8-in-10 range on each lake's own level, as the 11 lakes show it, May to September; the levels frozen from
  2023-26 samples by this rule into a new versioned file beside lake-range-v1, which stays unchanged. The lake word
  stays. Cotswold and Henleaze have no daily forecast and get nothing.
- **Either fails.** No range at these lakes. The record says where it missed (too wide or too narrow, which lakes).
  Next candidate: a noise level fitted for lakes like these, judged on the 2027 season under its own statement.
- **Either way:** lake-range-v1, the 11 lakes' range, the lake word, its 2027 judging and every frozen window stay as
  they are. The finding that the average-lake range sits low at these 7 goes to the register for the 20 average-lake
  spots the site already shows a range at (they have overflows upstream and no samples, so this does not test them).

## Reported, deciding nothing

`cover80`, `below80`, `above80` with intervals on `lake_not_read_before`, all held-out lake rows, and the 2017 split;
coverage by water body; the order and Brier figures as the bench prints them.
