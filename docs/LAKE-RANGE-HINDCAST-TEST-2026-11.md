# A likely E. coli reading and range for lakes: tested on 2012-2022 lake seasons

Written 1 November 2026, register row **3 / LAKE-CONC**, under `docs/RESEARCH-WORKFLOW.md`. Ethan asked for a way to
give lakes an E. coli estimate too. **This statement is committed and pushed before any 2012-2022 sample is joined to
rain, exposure or a model.** Nothing here changes a production model or a shown value.

## Continuation record

| Field | Content |
|---|---|
| Identity | LAKE-CONC; owner: Claude session "ecoli-estimate-lakes"; this PR; code `scripts/lake_range_hindcast/` |
| Evidence before this test | #466 and the lake spread (`CONCENTRATION-LAKE-SPREAD-2026-11.md`): on reused 2024-26 data a lake-specific noise level brought lake 80% coverage from 55-64% to 69-78%; exploratory. The over-900 chance has no ranking skill at lakes (16 exceedances in 641 lake samples) |
| Stage and claim | Development. Question: is a lake "likely reading and range" honest on lake seasons the model never read? |
| Next deliverable | This test's readout; then, by its result, a wording proposal (Ethan's decision) or a recorded reason to stop |
| Milestone and budget | This PR. EA: at most 40 requests. Open-Meteo: at most 400 weighted calls (sized below) |
| Release route | Any lake figure on the site needs Ethan's wording decision and a shadow log; the over-900 chance stays off lakes |

## 1. Why a range, not the over-900 chance

At lakes a result over 900 per 100 ml is rare: 22 of 1,258 lake samples in 2023-26. A chance of a rare event cannot be
judged with so few events, and it nearly always reads 1-5%, which looks like reassurance. A lake reader can use a
different statement: the reading a sample would most likely show today, and the range 8 in 10 samples would fall in.
That statement can be judged on every sample, not only the rare high ones.

## 2. The data it never read

- **Test rows.** Every EA statutory sample with an E. coli count, 1 May to 30 September 2012-2022, at the inland
  lake bathing waters that the site's pins (`scripts/eval_pins.py`) give monitored overflows upstream. Five qualify:
  Windermere at Fellfoot, Lakeside YMCA, Millerground Landing and Rayrigg Meadow, and Frensham Great Pond. Rutland,
  Coniston and Derwent Water were designated in 2023-24 and have no earlier samples. The other lakes have no overflow
  upstream, so the site shows them no daily figure. The API holds no E. coli count before 2012.
- **What was looked at before this statement.** On 1 November, in this session, the counts of those samples per
  site, and how many were over 235, 500 and 900 (994 samples; 52, 30 and 9). Nothing was joined to rain, exposure or
  a model. No earlier SwimSignal test used E. coli samples from before 2023.
- **Training rows.** 2023-2026 samples at every inland bathing water with overflows upstream, rivers and lakes, as
  #466 fitted. These sites and years are reused data.
- **Inputs, built the same way for both.** `scripts/validate_ecoli.py`'s hindcast: Open-Meteo archive rain at the
  spot (48 h and 24 h to the sample time) and the exposure from archive rain at every upstream overflow, through the
  spill model and transport, calibrated as lead 0. A day with more than `MAX_MISSING_SHARE` of the weight from
  overflow-days without rain gets no exposure and is dropped, as the site would show none. Repeated listings of one
  sample are kept once. "<10" is left-censored at 10 and ">10000" right-censored, as #466.

**Known weakness.** The past exposure uses today's overflow list and overflow facts, and a spill model trained on
2023-25 spills. An overflow added, removed or upgraded since 2012 makes those years' exposure inaccurate. This works
against the candidate, not for it. Windermere holds four of the five sites, so this is a test on two water bodies.

## 3. The models, fixed now

Fitted once on all training rows; nothing is refitted on test rows. The first three use
`scripts/concentration_study.py`'s `CensoredRI` unchanged; the heavy tail is a small subclass in this PR's script.

| Name | What it is | Role |
|---|---|---|
| **candidate** | Censored normal model of log10 E. coli, random intercept per bathing water, shared responses to `lrain48`, `lrain24`, `logit_risk`, `lake`, `lake_x_lrain48`, `doy_sin`, `doy_cos`, and its own lake noise level | Primary |
| background | The same with `lake` only and its own lake noise level: each site's typical level and spread, no weather | Reference |
| shared spread | The candidate's inputs with one noise level for rivers and lakes (#466's form) | Reported |
| heavy tail | The candidate with Student-t errors at lakes, its degrees of freedom fitted on training rows | Secondary, reported only |
| production | Production's over-900 logistic form (`ecoli.FEATURES`), refitted on the training rows | Over-900 Brier, reported only |

**Change from the 30 October development model:** no soil moisture. Production's lake model has none (the soil
model is for rivers), and leaving it out needs no extra fetch. Decided now, before any test row exists.

## 4. Conditions, fixed now

On the test rows, with a 95% interval from 2,000 resamples of whole ISO weeks (seed 0; one storm reaches every site):

1. **The range is honest.** The share of results inside the candidate's central 80% range (randomised PIT 0.1 to
   0.9) is between 70% and 90%.
2. **The weather adds something.** Mean log score, candidate minus background, is above zero, with the interval's
   lower end above zero.
3. **No water body is badly off.** Inside the central 80% range at Windermere and at Frensham separately: at least
   60% each.

**What each outcome means**, decided now:

- **All three pass:** a daily lake "likely reading and range" is supported for these lakes. Next: a wording proposal
  for Ethan, a shadow log at lake spots, and the 2027 lake samples as its prospective check.
- **1 and 3 pass, 2 fails:** the range is honest but the weather does not improve it. The supported lake output is the
  lake's typical range from its own samples, not a daily figure. Next: propose that as an observation feature.
- **1 or 3 fails:** no lake range on the site. The record says where the range was too narrow or too wide, and the
  heavy-tail and per-year results go to the next development step, judged on 2027 samples.

**Reported whatever the result:** PIT deciles; central 50% coverage; coverage and log score by site and by year;
within-site Spearman rho of the predicted median against the result, by site; Brier over 500 and over 900 for every
model, noting that 9 results over 900 cannot judge an over-900 chance; the heavy-tail model's coverage and log score;
rows dropped at each rule.

## 5. Caps, sized before any request

- **EA:** one paged listing per sampling point, five points, at most 40 requests.
- **Open-Meteo archive:** hourly precipitation for each 0.1° cell of the five test sites and their upstream overflows
  (about 7 cells), for each calendar year 2012-2022. One cell-year weighs 0.1 × 365 / 14 ≈ 2.6 calls, so about 200
  weighted calls. **Cap 400.** `fetch_archive`, ten cells a request, half a second apart; a cell that fails is reported
  and its rows dropped, not filled.
- **Scratch only.** `DIPCAST_ROOT`, `DIPCAST_STATE` and the cache point to a scratch copy. The main checkout's data
  files are fingerprinted before and after.

---

## Results

Run 1 November 2026 in a scratch copy, after the statement was pushed (e5840042). Every fit converged. Files:
`-scores.json` (the stated analysis), `-extra.json` (supplementary, below). The main checkout's data files had the same
fingerprint (path, size, modified time) before and after.

**Data and cost.** EA: 5 requests. Open-Meteo archive: 6 cells for 2012-2022, at most 172 weighted calls (some
cell-years were already cached), under the cap of 400. Test rows: 994 listed samples, 32 repeat listings dropped,
**962 rows** (Windermere 753 at four sites, Frensham 209); none dropped for rain or exposure. 477 of them are "<10".
28 are over 500 and 9 over 900. Training rows: 1,672 at 31 bathing waters, 2023-26 (478 dropped at sites with no
overflow upstream, 14 repeats, 1 rain window).

### The three conditions: all pass

| Condition | Result | |
|---|---|---|
| 1. Central 80% range holds 70-90% of results | **78.9%** (10% band below: 11.5%, above: 9.6%) | pass |
| 2. Log score above background, interval above zero | **+0.033** [+0.011, +0.055] | pass |
| 3. Each water body at least 60% inside | Windermere **79.3%**, Frensham **77.5%** | pass |

### Every model on the test rows

| Model | Inside 80% range | Inside 50% range | Mean log score | Brier over 900 | Brier over 500 |
|---|---|---|---|---|---|
| **candidate** (lake spread) | 78.9% | 50.1% | −0.905 | 0.00928 | 0.0282 |
| background (no weather) | 77.9% | 47.3% | −0.937 | 0.00927 | 0.0279 |
| shared spread (#466's form) | 72.3% | 41.1% | −0.973 | 0.00931 | 0.0287 |
| heavy tail (secondary) | 79.4% | 49.1% | −0.904 | 0.00928 | 0.0282 |
| production over-900 form | – | – | – | 0.00941 | – |

- **The lake's own spread matters most.** One shared noise level (#466's form) is too narrow at lakes: 72% inside the
  80% range, 13% above it. The lake spread fixes that: the fitted lake noise is 0.70 log10 units against 0.42 for
  rivers, as on the 2024-26 data.
- **The weather helps, modestly.** Candidate minus shared spread: +0.068 [+0.041, +0.095]. PIT deciles for the
  candidate: 111, 94, 92, 78, 99, 99, 110, 102, 85, 92 (about 96 each if perfect).
- **The heavy tail adds nothing here.** Its fitted degrees of freedom are 53, close to normal; +0.001 [+0.0001,
  +0.0024] over the candidate. On these lakes the tails are not heavier than normal once the lake spread is in.
- **The over-900 chance cannot be judged.** Nine results over 900; every model's Brier is about 0.009.

### By site

| Site | Rows | Over 500 | Inside 80%: candidate / background | Log score: candidate / background | Within-site rho of the predicted median (production's over-900 chance) |
|---|---|---|---|---|---|
| Windermere, Lakeside YMCA | 203 | 2 | 80.8% / 75.4% | −0.664 / −0.715 | 0.34 (0.18) |
| Windermere, Millerground Landing | 203 | 3 | 77.8% / 76.4% | −0.868 / −0.932 | 0.35 (0.23) |
| Windermere, Rayrigg Meadow | 143 | 0 | 87.4% / 80.4% | −0.789 / −0.858 | 0.44 (0.27) |
| Windermere, Fellfoot | 204 | 10 | 73.5% / 77.0% | −1.128 / −1.114 | 0.14 (−0.02) |
| Frensham Great Pond | 209 | 13 | 77.5% / 80.9% | −1.037 / −1.041 | 0.17 (−0.01) |

The weather gain comes from three Windermere sites. At Fellfoot and Frensham the candidate is no better than the
site's typical range (Fellfoot slightly worse), though its median still ranks samples in the right direction.

### By year

Inside the 80% range each year from 2014 is 76-86%. **2012 and 2013 are the exception:** 70% and 67%, with 25% and
22% of results above the range. Those seasons were dirtier than the 2023-26 levels the site intercepts were learned
from. The candidate's log score beats the background in every year except 2013 (−0.063).

### Supplementary, not in the statement

**(a) A lake with no samples of its own.** Most lake spots on the site are not bathing waters. To see how the range
behaves there, the candidate and background were refitted without Windermere and Frensham, so each test site got the
average lake's level. Inside the 80% range: **75.6%** (Windermere 74.8%, Frensham 78.5%), with 19.9% below it and 4.6%
above: for a lake it knows nothing about, the range sits a little high. The weather still helps: +0.064 [+0.033,
+0.093] over the background. Six lake sites remained in training, so this is a weak check.

**(b) What it would read.** The fitted candidate on 1 July 2026, a dry day (no rain in 48 h, the site's
10th-percentile exposure) and a wet day (25 mm in 48 h, 15 in the last 24, its 90th-percentile exposure). E. coli per
100 ml; the lab reports anything under 10 as "<10".

| Site | Dry: most likely, 8 in 10 between | Wet: most likely, 8 in 10 between |
|---|---|---|
| Windermere, Lakeside YMCA | 2; under 10 to 18 | 11; under 10 to 84 |
| Windermere, Millerground Landing | 4; under 10 to 32 | 21; under 10 to 170 |
| Windermere, Rayrigg Meadow | 5; under 10 to 41 | 28; under 10 to 220 |
| Windermere, Fellfoot | 12; under 10 to 91 | 48; under 10 to 380 |
| Frensham Great Pond | 15; under 10 to 120 | 47; under 10 to 370 |

The range is wide: lake results scatter far more than river results. A wet day raises the upper end about four
times. Values under 10 are below what the lab counts, so a page should say "under 10", not a number.

## What it means

**Established, on these data:** at five lake bathing waters on two water bodies, over 11 seasons the model never read,
a lake-specific range was honest (79% inside a stated 80% range, and 78-79% at each water body), and the rain and
spill exposure made it better than the lake's typical range alone. The over-900 chance remains unjudgeable at lakes.

**Not established:** that it holds at other lakes. Windermere is three quarters of the rows. At Fellfoot and Frensham
the weather added nothing measurable. A lake without its own samples was checked only weakly (supplementary (a)). The
past exposure used today's overflows. 2012-13 show the range can sit too low when a lake's level shifts.

**Next, by the stated rule (all three pass):** a wording proposal for Ethan, a shadow log at lake spots, and the 2027
lake samples as the prospective check. Proposed scope for any first display: lake bathing waters with overflows
upstream, May to September, worded as "a sample today would most likely read about X; 8 in 10 between A and B", with
"under 10" for values below the lab's limit, the over-900 chance kept off lakes, and the official advice first.
