# Bench read 1: lake-range-v1 at lakes without their own level, 2012-22

Statement written 15 November 2026 and pushed before the read. Nothing below the line "Result" existed when it was
pushed. Candidate: `scripts/backtest_bench/candidates/lake_range_v1.py`. Bench: [BACKTEST-BENCH-2026-11.md](BACKTEST-BENCH-2026-11.md).

## The question

lake-range-v1 is the frozen lake model behind the likely reading and 8-in-10 range on every lake spot's page, and
behind the "higher / lower than usual for this lake" line (#585, #630). It has its own level at 11 lake bathing
waters. At any other lake the page shows it on the "average lake" basis. Its 2012-22 test (#584) and the 2012-22
lake-line check read only Windermere's four bathing waters and Frensham, all with their own level.

The bench's held-out lake rows that no test has read are the 7 lake bathing waters without their own level in
lake-range-v1: the Serpentine, Hampstead Heath's Ladies, Mens and Mixed Ponds, Cotswold Country Park, Henleaze Lake
and Colwick (West Lake). 5 water bodies, May to September 2012-22. None has a monitored overflow upstream on its pin,
so both models' figures there move with rain and season only.

**Does lake-range-v1's likely reading order a lake's own samples better than production's E. coli chance at lakes
it has no own level for, in years neither model was fitted on?** The "higher / lower than usual" line is a statement
about order within a lake. It is shown only at the 11 lakes with their own level. A pass supports offering it at
these 7.

## What is fixed

- **Candidate.** lake-range-v1 unchanged (`data/processed/ecoli_lake_range.json`, sha256 `5566b12e…`, frozen 1 Nov
  2026, fitted on 2023-26 rows that did not include these 7 bathing waters). `rank` is its predictive median; `p900`
  and `p500` are its chance over 900 and over 500. At rivers the wrapper gives production's figure, so river
  differences are zero by construction and decide nothing.
- **Reference.** `production_deployed`: `data/processed/ecoli_model.json` as deployed (the lake model), sha256 in the
  bench manifest.
- **Rows.** The bench's frozen held-out rows (`heldout.parquet`, sha256 `b3a30b5e…`), subset `lake_not_read_before`.
- **Primary metric.** Mean over bathing waters (15 rows or more) of the within-site Spearman correlation between the
  figure and the measured log10 count (`rho_site`): candidate's minus `production_deployed`'s.
- **Interval.** 95%, 2,000 resamples of water-body seasons (`ci95_season`, seed 20261115). The water-body interval
  (`ci95`) is reported but does not decide: 5 water bodies are too few to resample alone.
- **Pass.** The primary difference's `ci95_season` lies wholly above 0.
- **Fail.** It includes 0 or lies below it.

One primary comparison. This is the first final read on these rows (ledger read 1).

## What each outcome leads to

- **Pass.** A PR, for Ethan's review, that offers the "higher / lower than usual" line at these 7 lake bathing
  waters: their usual reading from their own 2023-26 sample-day inputs, as `lake_range_usual.py` computes it for the
  11, on the average-lake basis, with the line's wording and thresholds unchanged. The 2027 read of
  `shadow_lake_range_v1` continues as monitoring.
- **Fail.** The line stays at the 11. The record says the average-lake likely reading was not shown to order samples
  better than production at lakes without their own level. A wording note for the average-lake range goes to Ethan
  as a proposal.
- **Either way** the range shown today, its 2027 read, every level, colour and alert, and every frozen window stay
  as they are.

## Reported, deciding nothing

On `lake_not_read_before`: the candidate's own `rho_site` and its interval; Brier for over 900 and over 500 against
`production_deployed` and `month_rate`; the within-site AUC for over 900; the water-body interval. On all held-out
lake rows and on the bench's seasons-to-2016 and seasons-from-2017 subsets, the same figures, because the archive
rain most likely changes source at 2017 (bench record, "Limits"). The 2017 split subsets hold the rivers and the
rows read before as well, so they describe the bench, not this question alone.

## Known before the read

- At staging I printed, for each held-out bathing water, its row count, its number of results over 900 and its mean
  exposure (bench record, "Disclosure"). No model figure was computed against a held-out outcome.
- `dev` on the seen rows (2023-26, where lake-range-v1 was fitted on 11 of the 18 lakes, so development evidence
  only): `rho_site` at lakes 0.285 against production's 0.007; difference +0.278, water-body-season interval
  [+0.171, +0.390].
- The 2012-22 lake-line check found lake-range-v1 0.286 against production's form refitted 0.132 at Windermere and
  Frensham (deployed 0.102). Those rows are not in this read's subset.

## Result
