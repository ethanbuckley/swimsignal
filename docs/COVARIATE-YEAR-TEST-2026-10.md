# Do the spill model's site covariates carry their return year's wetness? The test, stated before any run

Written 19 October 2026. At that point no model had been trained for it, no row had been built, and
no score had been computed. Results go below the line at the end. Nothing above that line changes
after a result is seen. It runs only after Ethan approves this statement.

## Why

The spill model reads three covariates from the EA annual returns: `log_lta_spills`, `log_spill_hours`
and `edm_pct` (`features.site_static_features`). PR #259 (open) saw this on 2023, at United Utilities,
Northumbrian and Wessex:

- *Measured:*
  - D2's 2024 training rows carry the 2023 return's covariates. Their mean `log_spill_hours` is 3.46.
    The same rows with the 2022 return's covariates (PR #259's A24) give 2.84.
  - The 2023 test rows carry the 2022 return's: 2.92.
  - Median spill hours per overflow were 41.5 in the 2023 return and 18.6 in the 2022 return.
  - Mean forecast on 2023: D2 0.075, A24 0.0885, observed 0.102.
  - A24 beat D2 by −0.00329 Brier [−0.00485, −0.00185]. Both were fitted on D2's 2024 rows. They
    differ in which return those rows' covariates come from, and by at most 0.13 mm in the
    antecedent rain index.
- *Inferred there, not tested:* covariates from a wet return year, read later from a dry one, make the
  model forecast too low.

Production takes covariates the same way. `scripts/train.py` and `training.site_years` give each row
year the return of the year before. The live forecast gives each overflow its latest return
(`overflows.latest_annual_returns`), so forecasts in 2026 read the 2025 return.

This test asks two questions, stated separately:

1. **Do the covariates carry the wetness of the return year they come from into the forecasts?**
2. **Does expressing them relative to their own return year fix that?**

## Seen before writing

- **Company-year medians of the covariates.** Computed on 19 Oct 2026 from `annual_returns.parquet`
  (returns 2021 to 2025). Each return has one row per id (the last, as `training.site_years` keeps).
  The median runs over every overflow of the company in that return with a value. No event file and
  no model was read.

  Median `log1p(spill_hours)`:

  | Company | 2021 | 2022 | 2023 | 2024 | 2025 |
  |---|---|---|---|---|---|
  | Anglian | 3.39 | 2.77 | 3.23 | 4.16 | 2.67 |
  | Dŵr Cymru (England) | 3.54 | 2.83 | 3.82 | 4.27 | 3.40 |
  | Northumbrian | 3.06 | 2.62 | 3.52 | 3.54 | 2.81 |
  | Severn Trent | 2.52 | 2.18 | 3.01 | 3.32 | 2.84 |
  | South West | 3.60 | 2.72 | 3.83 | 3.79 | 3.70 |
  | Southern | 3.36 | 3.23 | 4.04 | 3.68 | 2.89 |
  | Thames | 4.79 | 3.55 | 3.59 | 4.48 | 3.08 |
  | United Utilities | 3.88 | 3.10 | 3.93 | 3.66 | 3.40 |
  | Wessex | 3.15 | 2.81 | 3.80 | 4.08 | 2.99 |
  | Yorkshire | 3.63 | 3.06 | 3.73 | 3.81 | 3.66 |

  - Within a company, this median moves by 0.74 to 1.71 log units over the five returns. A log unit
    is a factor of e, about 2.7.
  - The 2025 return's median is below both the 2023 and 2024 returns' at all ten companies.
  - Median `log1p(lta_spills)` moves less: 0.15 to 0.43 log units over 2022 to 2025. It is a
    multi-year average. The 2021 return gives none.
  - Median `edm_operational_pct` is 97.6 to 100 in every company-year.
- **Rain held** (file names in `data/cache/rain/`, `rain_nine/` and `rain_multi/`, against each
  company-year return's 0.1° cells):
  - 2024 and 2025: every cell of every company.
  - 2023: United Utilities 100%, Wessex 99%, Thames 94%, Northumbrian 87%; 3% to 29% elsewhere.
  - 2021 and 2022: Wessex 97% and 100%, Northumbrian 91% and 93%; under 4% elsewhere.
  - PR #259 built 2023 rows at United Utilities, Northumbrian and Wessex, and D2's 2024 and 2025 rows,
    with no row lacking rain. So the folds below need no new rain until 2026.
- **2024 has never judged the spill model.** The README, every doc under `docs/` and the git log hold
  no spill-model score on 2024 held out (searched 19 Oct 2026). The model has been verified on 2025
  (United Utilities 2023-24 hold-out, D2, PR #239, PR #254) and on 2023 (PR #259).
- **D2's published 2025 results** (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`). It failed condition 1
  at Anglian and condition 3 at Thames. In the table above, those are the two companies whose median
  rose most from the 2023 return to the 2024 return (+0.93 and +0.89). This was noticed while writing.
  It is one reason 2025 is a fold below. It also means the 2025 predictions at Anglian and Thames are
  not blind. D2's per-company mean forecasts on 2025 were not computed.
- **Label sources across years** (PR #258):
  - United Utilities 2024, Stream against the EA file: 76,958 spill-days shared, 1,333 in the EA's
    only, 846 in Stream's only.
  - Northumbrian 2024: Stream and the EA file are the same record.
  - Wessex 2024, its own layer (crosswalked) against the EA file: 44,422 spill-days shared, 258 in the
    EA's only, 0 in Wessex's only.
- **When the 2026 files come out is not known.** D2 found the 2024 and 2025 files last modified on
  21 Sep 2026, and a Thames 2026 file modified on 29 Sep. PR #253 found that Thames file ends on
  31 Jul 2026. The EA's dataset page gives no date for the next files (it did not load as text on
  19 Oct 2026).

## Which years judge, and why

Every fold has one shape: **train on one year, judge the next.** That is how production uses a
model: fitted on past years and run forward. The judged rows take covariates from the training year's
return, as production would.

| Fold | Train | Judge | Companies | Spill-hours shift | Role |
|---|---|---|---|---|---|
| — | — | 2023 | — | — | **Not used to judge** |
| F24 | 2023 | 2024 | United Utilities, Northumbrian, Wessex | up at all three (+0.83 to +0.99) | deciding |
| F25 | 2024 | 2025 | the nine English companies | mixed (−0.36 to +0.93) | deciding |
| F26 | 2025 | 2026 | the nine English companies | down at all nine (−0.09 to −1.48) | confirmation, once its files are out |

The shift is the judged rows' return median minus the training rows' return median, `log1p(spill_hours)`.

- **2023 does not judge.** PR #259 scored on it, and the question comes from what it showed there.
  2023 enters only as F24's training year.
- **2024 judges (F24).** Nothing has been scored on it held out. Its rows read the 2023 return, which
  is much wetter than the 2022 return the 2023 training rows read. Only United Utilities,
  Northumbrian and Wessex have 2023 events, so only they are judged. Thames 2023 is not used: its alert
  stream has events for 85% of the overflows that spilled in its 2023 return (PR #259).
- **2025 judges (F25).** It has judged D2, PR #239 and PR #254, so it is reused, and its predictions at
  Anglian and Thames are not blind (above). It is kept because its shifts go both ways. So the test
  predicts a direction at each company, not one direction for all. Its rows are D2's, so F25's raw
  model is D2's own setup.
- **2026 confirms (F26).** It is fresh, its shift is the largest, and it is production's own case
  now. It cannot run until the EA's full-year 2026 start/stop files for all nine companies, and the
  EA's 2026 annual return, are out. The 2026 return is needed for D2's coverage rule only.
- **Why not a full leave-one-year-out.** Holding out year Y while training on year Y+1 would put the
  Y return into the training covariates. That return is Y's annual counts at every overflow. It would
  also judge backward in time, which production never does.
- **Why no earlier fold.** A 2022 fold would train on 2021 rows, whose covariates need the 2020
  return, which is not held. A 2021 fold has the same gap.

*Inferred:* the effect is between years. Each fold is one change of return year, so two deciding
folds are two samples of it. The week-cluster intervals below measure the noise within a judged year,
not between years. A pass says the fix worked on these changes of return year. It does not say it
works for every one.

## The rows

The label is D2's: "the overflow spilled that day". Days are floored in UTC. The features are D2's
(`features.ALL_FEATURES`). Rows with no rain that day are dropped, as `scripts/train.py` `_frame` does.

- **F24 training: 2023** at United Utilities (Stream 2023 layer), Northumbrian (Stream layer) and
  Wessex (its own layer, crosswalked). These are PR #259's 2023 rows: D2's rule (`training.site_years`)
  applied to 2023. PR #259 counted 691,675, 352,590 and 358,795 site-days. Covariates come from the 2022
  return, with its long-term average.
- **F24 judged: 2024** at the same three companies. These are D2's 2024 rows (EA files), with D2's
  covariates from the 2023 return.
- **F25 training: 2024**, D2's rows at the nine companies (4,976,868 site-days, covariates from the
  2023 return).
- **F25 judged: 2025**, D2's rows (5,077,150 site-days, covariates from the 2024 return).
- **F26 training: 2025**, D2's rows. **F26 judged: 2026**, by D2's rule: a position in the 2025 return;
  an event in 2026 or 0 spills in the 2026 return; dropped when the 2026 return gives EDM operation
  under 50%. Covariates come from the 2025 return.
- **Rain.** ERA5-Land hourly from Open-Meteo's archive, read from `rain/`, `rain_nine/` and
  `rain_multi/` as PR #259 read them. F24 and F25 need no fetch, and the script stops if a row's cell
  lacks rain. F26 needs 2026 for the nine companies' cells, and the December 2025 files already held.
  That fetch goes to a new folder, never `rain/` or `rain_nine/`, and is asked of Ethan when the files
  are out. D2's 2025 fetch for the same cells was about 3,280 calls.

## The covariates

Each covariate value comes from one return, as above. Its **population** is every overflow of the
same company in that return with a value, one row per id.

- **A: raw**, as today. `log1p(lta_spills)`, `log1p(spill_hours)`, `edm_operational_pct / 100`. A
  missing value takes the company median over the rows' overflows (`site_static_features`).
- **R2: log ratio to the company-year median (primary, decides).** For `lta_spills` and `spill_hours`:
  `log1p(x)` minus the median of `log1p(x)` over the population. A missing value becomes 0, the
  median. `edm_pct` is as in A.
- **R1: percentile rank within the company-year (secondary, reported).** For `lta_spills` and
  `spill_hours`: (average rank of x in the population − 0.5) / population size. Ties take the
  average rank. A missing value becomes 0.5. `edm_pct` is as in A.

Rules for all three:
- **The values go in the same columns** (`log_lta_spills`, `log_spill_hours`). So `ALL_FEATURES`, the
  monotone constraints (rain only) and `SpillModel` are unchanged.
- **Why `edm_pct` stays raw.** It measures monitor uptime, not spills, and its median is 97.6 to 100
  in every company-year.
- **Why R2 decides.** It is the smaller change: today's value minus one number per company-year, so
  the spread within a year is kept. *Inferred:* R1 also removes year-to-year changes in the spread,
  but it flattens the tails, and many overflows tie at 0 spills.
- **What both forms cost.** They remove each company's level from layer 1 as well as each year's.
  Layer 1 can then no longer tell that one company's overflows spill more than another's. Layer 2's
  offsets carry that for overflows with training rows. Layer-1-only scores are reported to show the
  cost.

## The models

In each fold, A, R2 and R1 are fitted on the same training rows with D2's settings:
- `SpillModel.fit_pooled(neg_frac=0.25, seed=0)`, so the same subsample mask for all three;
- layer 2: `fit_site_offsets`, prior strength 15, recency 1, on each model's own layer-1 predictions
  over its training rows.

Context rows, scored on the same judged rows, not deciding:

| Predictor | What it is |
|---|---|
| A, training-year return | A, with the judged rows' covariates taken from the training rows' return instead (F24: 2022; F25: 2023; F26: 2024). No new fit. It removes the shift by using an older return. An overflow the older return lacks takes the company median (`site_static_features`) |
| D2's candidate | `spill_model_nine_2024.pkl` (SHA-256 begins `1603678923cc`), in F25 only. It checks that F25's A reproduces D2. The largest difference in forecast is reported |
| Flat rate | the company's spill-day rate over the training rows |

## Scoring

- **What is reported**, per fold, for each company, the deciding companies together, and both
  deciding folds together:
  - rows, base rate and mean forecast;
  - Brier score and AUC;
  - ECE (D2's definition) and a 10-bin reliability table;
  - the same for layer 1 alone, as observations.
- **Uncertainty.** Paired differences in Brier get 95% intervals from a week-cluster bootstrap:
  - weeks are ISO (year, week) of the UTC day;
  - 2,000 resamples of weeks with `numpy.random.default_rng(0)`, every row of a week drawn together;
  - one set of draws over every week of 2024 and 2025 serves F24 and F25 and every group;
  - F26 gets its own set over 2026, drawn the same way;
  - the interval runs from the 2.5th to the 97.5th percentile.
- **The differences:** R2 − A (deciding); as context R1 − A, R2 − R1, and "A, training-year return"
  − A.
- **The forecast shift** at company c: s_c = mean forecast of A − mean forecast of R2, both with
  layer 2, over the judged rows. It reads no label.

## Question 1: do the covariates carry their return year's wetness into the forecasts?

**1a. The level follows the weather.** From returns and rain only, with no model and no label.
- For 18 pairs of a company's consecutive return years, compare two changes:
  - the change in the company-year median of `log1p(spill_hours)` (table above);
  - the change in mean calendar-year ERA5-Land rain over the company's cells in that year's return.
    A cell counts only when its file holds at least 95% of the year's hours. A company-year counts
    only when at least 85% of its cells have a file.
- The pairs:
  - Northumbrian and Wessex: 2021-22, 2022-23, 2023-24, 2024-25 (8);
  - United Utilities and Thames: 2023-24, 2024-25 (4);
  - Anglian, Dŵr Cymru (England), Severn Trent, South West, Southern and Yorkshire: 2024-25 (6).
- **Condition:** the two changes have the same sign in at least 14 of the 18 pairs. Spearman's rank
  correlation over the 18 is reported too.
- This is a reading rule, not a significance test. Pairs of the same years share their weather.
  Ten of them are 2024-25.

**1b. The level moves the forecast.** At the company-folds where the spill-hours shift is at least
0.25 log units either way, s_c has the sign of the shift:

| Fold | Company | Spill-hours shift | Long-term-average shift | Predicted sign of s_c |
|---|---|---|---|---|
| F24 | United Utilities | +0.832 | −0.013 | + |
| F24 | Northumbrian | +0.899 | +0.272 | + |
| F24 | Wessex | +0.989 | +0.120 | + |
| F25 | Anglian | +0.929 | −0.276 | + |
| F25 | Severn Trent | +0.308 | +0.078 | + |
| F25 | Southern | −0.358 | +0.078 | − |
| F25 | Thames | +0.892 | −0.111 | + |
| F25 | United Utilities | −0.263 | −0.094 | − |
| F25 | Wessex | +0.276 | −0.042 | + |

No sign is predicted at F25's Northumbrian (+0.021), South West (−0.034) or Yorkshire (+0.081). Their
s_c is reported.

- **Condition:** the predicted sign holds in at least 8 of the 9.
- At Anglian and Thames the long-term average moved the other way. The prediction follows spill hours,
  the larger shift.
- 1b is close to mechanical. A model whose forecast rises with a covariate forecasts higher when every
  value of it rises. 1b measures whether, and by how much, the return year moves the forecast. Whether
  that move is an error is question 2.

The answer to question 1 is **yes only if 1a and 1b both hold**.

## Question 2: does R2 fix it?

R2 against A, on F24 and F25:

1. **A real gain overall.** Over the deciding rows of both folds together, R2's Brier is lower than
   A's, and the 95% interval of R2 − A lies wholly below zero.
2. **Neither fold clearly worse.** In neither fold, over its deciding companies, does the interval of
   R2 − A lie wholly above zero.
3. **No company clearly worse.** At none of the 12 company-folds does the interval of R2 − A lie wholly
   above zero.
4. **Reliability.** At each of the 12 company-folds, R2's ECE is no higher than A's, or it is at most
   0.02.

The answer is **yes only if all four hold**. A fail on condition 1 alone answers it **no**.

R1 is checked against the same four conditions. Its result is reported as an observation and cannot
make the answer yes.

## The 2026 confirmation (F26), stated now

- **It runs whatever F24 and F25 find,** once the EA's full-year 2026 start/stop files for all nine
  companies and the EA's 2026 annual return are out. The rain fetch is asked of Ethan then.
- **Conditions:** question 2's condition 1 over the nine companies together, conditions 3 and 4 at
  each of the nine, and 1b on these predictions, holding in at least 6 of the 7:

  | Company | Spill-hours shift (2025 − 2024 return) | Predicted sign of s_c |
  |---|---|---|
  | Anglian | −1.484 | − |
  | Northumbrian | −0.732 | − |
  | Severn Trent | −0.475 | − |
  | Southern | −0.790 | − |
  | Thames | −1.397 | − |
  | United Utilities | −0.260 | − |
  | Wessex | −1.086 | − |

  No sign is predicted at South West (−0.094) or Yorkshire (−0.150).
- **Nothing about F26 changes after F24 and F25 are seen.** Any change would be a new test, stated
  before the 2026 files are read.

## What follows from either answer

- Nothing is deployed, whatever the result. `spill_model.pkl` and `lead_calibration.json` do not
  change.
- A yes to question 2 and to F26 would be grounds for an adoption test of its own. That test would
  need forecast rain, D2's Welsh test set, the lead map, and the same relative forms for Wales
  (`ingest/wales_annual.py`) and Scotland (`ingest/sw_covariates.py`). It would be stated before
  anything runs. It can share 2026 with F26 if it is stated before the 2026 files are read.
- **On production, inferred and not tested here.** If question 1 is yes, live forecasts in 2026 are
  pulled toward a dry year's level, because they read the 2025 return. The live page shows 2026
  forecasts too high (D2's lead calibration section). So if this effect is real, it is not what drives
  that, or something larger outweighs it.

## Not in this test

- A normaliser over all of England for each year, which would keep company levels in layer 1.
- A relative form for `edm_pct`.
- Training on two years or more.
- The network.
- Forecast rain. Open-Meteo's previous-runs archive has no lead-1 to lead-4 rain for 2023, and F24
  trains on 2023.
- Dŵr Cymru, Wales and Scotland as judged companies.

## Order of work

1. Commit and push this statement, and open a draft PR against main. Run nothing until Ethan approves.
2. Write `scripts/test_covariate_year.py` with stages `plan`, `rain`, `rows`, `train` and `score`, and
   `f26` for later. Only `score` reads a judged year's labels. Push the script, and any choice this
   statement leaves open, before any training. PR #259 is not merged. Its 2023 row rule is imported
   from `scripts/train_multi_year.py` only if PR #259 is merged first; otherwise it is rewritten here,
   and the 2023 site-day counts above must match.
3. `plan`: rows per fold and company, covariates filled, and a check that no row lacks rain.
4. `rain`: question 1a. It reads rain and returns only.
5. `train`: A, R2 and R1 for F24 and F25. Push the training log before any judged year is scored.
6. `score`: F24 and F25. Check both questions' conditions and write the results below the line.
7. F26, once its files are out.

Run nothing while another evaluation or build is running on this Mac (`pgrep -fl`, never `pkill`).
The models go off-repo to `swimsignal-private/baselines/covariate_year/`. The tables go beside this
file: `-scores.csv`, `-differences.csv`, `-reliability.csv`, `-shifts.csv`, `-rain.csv` and
`-checks.json`.

---

## Results

Ethan approved the statement on 19 October 2026: "Design approved as stated in PR #260. Write the script,
push it before training, then run F24 and F25."

### Choices the statement leaves open, fixed before any training

Written 19 October 2026, after the rows were built and before any model was trained or any judged
year scored. The code is `scripts/test_covariate_year.py`.

- **Stages.** `rows`, `rain`, `train` and `score`, and `f26`, which only says what it waits for.
  - `plan` and `rows` are one stage: the rows are counted by building them.
  - `rows` builds the judged years' site-days with their labels and saves them, as PR #259 did. Only
    `score` predicts a judged year or scores one.
- **PR #259's 2023 rule is rewritten here,** because PR #259 is not merged. The events are PR #259's
  `history_events` without Thames. The overflows are `training.site_years(returns, events, three
  companies, 2023)`. The script stops unless it gets PR #259's 2023 site-day counts.
- **F25's rain is D2's loader,** `training.load_rain`: `rain/` and `rain_nine/`, from 1 December 2023.
  So F25's A should reproduce D2.
- **F24's rain is one series per cell from 1 December 2022 to 31 December 2024,** from all three
  folders (files tagged 2022, 2022dec, 2023, 2023dec and 2024).
  - F24's judged rows are D2's 2024 rows at the three companies. The script stops unless their counts
    equal D2's there.
  - Their antecedent index can differ slightly from D2's own, because the series starts a year
    earlier. PR #259 measured at most 0.13 mm for an earlier start.
- **The population behind R2 and R1** is a return's rows with an id, the last row per id, with or
  without a position. That is the rule behind the statement's medians table, and the script's shift
  table reproduces it to three decimals.
- **A row's own value** is the one `site_years` gives: the last row for the id with a position. Its rank
  is placed in the population by value, on `log1p` values (the same order as the raw ones). So an id
  held twice in a return still gets a rank.
- **The context row's older return:** the last row per id with a position, for all three covariates.
- **Flat rate:** each company's spill-day rate over the fold's training rows.
- **The bootstrap.** One set of 2,000 draws over every ISO week of F24's and F25's judged rows. ISO
  week 2025-W01 holds 30 and 31 December 2024 (F24) and 1 to 5 January 2025 (F25). Those days are drawn
  together.
- **Question 1a.**
  - A cell's year is every file tagged with that year in the three folders, with repeated hours
    dropped, cut to the calendar year in UTC.
  - A full year is 8,760 hours, or 8,784 in a leap year.
  - A company-year's cells are those of its return's rows with a position that year.
  - The stage stops if any of the 18 pairs lacks rain.
- **The D2 check.** The largest difference between F25's A and D2's candidate, in any forecast on 2025,
  is reported.
- **Software.** scikit-learn 1.9.1, pandas 3.0.5, SciPy 1.18.1.

### Training log, pushed before any judged year was scored

- All six models ran their full 300 iterations, in 6 to 18 seconds each (`-training.csv`).
- Layer 2 gave 3,844 offsets in F24 and 13,598 in F25.
- The models are off-repo in `swimsignal-private/baselines/covariate_year/`. Their SHA-256 prefixes:
  - F24: A `ee0671fc8fd0`, R2 `085aa5cb7d59`, R1 `d1be3c4b53be`;
  - F25: A `0bebcd97aef6`, R2 `b753f0b50c7b`, R1 `8123175a6e05`.
- Question 1a had already been run, from returns and rain only (`-rain.csv`, below).

### The answers

1. **Do the covariates carry their return year's wetness into the forecasts? No, as stated.**
   - 1a passes. In 17 of the 18 pairs, the change in spill hours has the sign of the change in
     rain. Spearman's ρ is 0.95.
   - 1b fails. The predicted sign of the forecast shift held at 7 of 9 company-folds, and 8 were
     needed. The two misses, F25's Severn Trent (+0.31) and United Utilities (−0.26), are the two
     smallest predicted shifts.
2. **Does R2 fix it? No, as stated.**
   - Conditions 1 and 2 pass. Over both folds, R2 − A is −0.00099 [−0.00137, −0.00063].
   - Conditions 3 and 4 fail, both at Southern in 2025. There R2 − A is +0.00108 [+0.00048,
     +0.00180], and R2's ECE is 0.0213 against A's 0.0110.
   - R1, reported as an observation, passes all four: −0.00085 [−0.00121, −0.00052] over both folds.
     As stated, that cannot make the answer yes.

### The run

Run 19 October 2026 on this Mac. The statement was pushed at `74138ab`, the script and the choices
above at `10bc3b8`, and the training log at `d7f34df`, before either judged year was scored. The
script did not change after `10bc3b8`. The logs are `logs/*_covyear_2026-10-19.log` in the worktree
(not committed). No other evaluation or build ran.

- **Rows.** Every count check passed, and no row lacked rain.

  | Fold | Company | Training site-days | Training base rate | Judged site-days | Judged base rate |
  |---|---|---|---|---|---|
  | F24 | United Utilities | 691,675 | 0.119 | 804,834 | 0.096 |
  | F24 | Northumbrian | 352,590 | 0.077 | 501,420 | 0.068 |
  | F24 | Wessex | 358,795 | 0.092 | 472,506 | 0.094 |
  | F25 | the nine | 4,976,868 | 0.087 | 5,077,150 | 0.057 |

  - F24's training rows equal PR #259's 2023 rows at each company.
  - F24's judged rows equal D2's 2024 rows at the three companies.
  - F25's rows equal D2's.
- **The context row's older return lacks many overflows.** In F24, 1,381 of 4,860 judged overflows
  have no value for some covariate in the 2022 return. In F25, 1,110 of 13,910 lack one in the 2023
  return. They take company medians.
- **Question 1a** (`-rain.csv`). Mean calendar-year rain fell from 2024 to 2025 at all ten
  companies, by 129 to 274 mm. Median spill hours fell at all ten too. The one pair that disagrees is
  Northumbrian 2023-24: spill hours +0.02 log units, rain −17 mm.
- **D2 check.** F25's A gives the same forecast as D2's candidate on every 2025 row: the largest
  difference is 0.

### Scores on the judged years, ERA5-Land rain

Brier, with ECE in brackets for A and R2. Mean forecast is with layer 2.

| Fold | Company | Rows | Base rate | Mean forecast A / R2 | A | R2 | R1 | A, training-year return |
|---|---|---|---|---|---|---|---|---|
| F24 | United Utilities | 804,834 | 0.0959 | 0.1279 / 0.1000 | 0.0667 (0.032) | **0.0618** (0.008) | 0.0625 | 0.0632 |
| F24 | Northumbrian | 501,420 | 0.0677 | 0.0635 / 0.0574 | 0.0448 (0.008) | **0.0440** (0.013) | 0.0439 | 0.0499 |
| F24 | Wessex | 472,506 | 0.0944 | 0.0857 / 0.0826 | 0.0554 (0.010) | **0.0543** (0.015) | 0.0548 | 0.0606 |
| F24 | **the three** | 1,778,760 | 0.0876 | 0.0985 / 0.0834 | 0.0575 (0.011) | **0.0548** (0.010) | 0.0552 | 0.0588 |
| F25 | Anglian | 512,825 | 0.0331 | 0.0438 / 0.0434 | 0.0272 (0.011) | **0.0270** (0.010) | 0.0271 | 0.0262 |
| F25 | Northumbrian | 562,100 | 0.0505 | 0.0508 / 0.0527 | 0.0332 (0.003) | **0.0329** (0.003) | 0.0336 | 0.0348 |
| F25 | Severn Trent | 880,380 | 0.0417 | 0.0462 / 0.0522 | 0.0284 (0.005) | **0.0284** (0.011) | 0.0282 | 0.0286 |
| F25 | South West | 493,845 | 0.0938 | 0.1032 / 0.1022 | 0.0519 (0.009) | **0.0509** (0.008) | 0.0501 | 0.0523 |
| F25 | Southern | 343,465 | 0.0444 | 0.0554 / 0.0658 | **0.0277** (0.011) | 0.0288 (0.021) | 0.0276 | 0.0276 |
| F25 | Thames | 209,875 | 0.0429 | 0.0669 / 0.0520 | 0.0303 (0.024) | **0.0296** (0.009) | 0.0294 | 0.0281 |
| F25 | United Utilities | 825,995 | 0.0746 | 0.0921 / 0.0880 | 0.0456 (0.018) | **0.0449** (0.013) | 0.0457 | 0.0459 |
| F25 | Wessex | 467,565 | 0.0525 | 0.0661 / 0.0641 | 0.0326 (0.014) | **0.0322** (0.012) | 0.0322 | 0.0319 |
| F25 | Yorkshire | 781,100 | 0.0667 | 0.0622 / 0.0597 | 0.0403 (0.005) | **0.0396** (0.007) | 0.0396 | 0.0403 |
| F25 | **the nine** | 5,077,150 | 0.0573 | 0.0653 / 0.0652 | 0.0362 (0.008) | **0.0358** (0.008) | 0.0358 | 0.0362 |
| | **both folds** | 6,855,910 | 0.0651 | 0.0739 / 0.0699 | 0.0417 (0.009) | **0.0407** (0.005) | 0.0408 | 0.0420 |

Bold marks the better of A and R2 at five decimals. Paired differences in Brier, first minus second,
with 95% week-cluster intervals (2,000 draws over 105 ISO weeks):

| Fold | Company | R2 − A (deciding) | R1 − A | A, training-year return − A |
|---|---|---|---|---|
| F24 | United Utilities | −0.00483 [−0.00636, −0.00335] | −0.00412 [−0.00549, −0.00287] | −0.00348 [−0.00567, −0.00142] |
| F24 | Northumbrian | −0.00086 [−0.00169, +0.00009] | −0.00096 [−0.00175, −0.00004] | +0.00512 [+0.00314, +0.00728] |
| F24 | Wessex | −0.00108 [−0.00275, +0.00067] | −0.00055 [−0.00199, +0.00093] | +0.00526 [+0.00199, +0.00885] |
| F24 | **the three** | −0.00272 [−0.00368, −0.00170] | −0.00228 [−0.00308, −0.00149] | +0.00127 [−0.00056, +0.00326] |
| F25 | Anglian | −0.00026 [−0.00076, +0.00020] | −0.00013 [−0.00047, +0.00022] | −0.00107 [−0.00154, −0.00063] |
| F25 | Northumbrian | −0.00037 [−0.00083, +0.00002] | +0.00034 [−0.00032, +0.00101] | +0.00152 [+0.00089, +0.00223] |
| F25 | Severn Trent | −0.00005 [−0.00069, +0.00043] | −0.00018 [−0.00080, +0.00035] | +0.00014 [−0.00018, +0.00056] |
| F25 | South West | −0.00100 [−0.00153, −0.00046] | −0.00176 [−0.00258, −0.00098] | +0.00043 [−0.00008, +0.00101] |
| F25 | Southern | **+0.00108 [+0.00048, +0.00180]** | −0.00013 [−0.00055, +0.00033] | −0.00016 [−0.00047, +0.00016] |
| F25 | Thames | −0.00069 [−0.00226, +0.00112] | −0.00092 [−0.00231, +0.00060] | −0.00222 [−0.00345, −0.00104] |
| F25 | United Utilities | −0.00071 [−0.00126, −0.00019] | +0.00007 [−0.00064, +0.00081] | +0.00033 [−0.00019, +0.00097] |
| F25 | Wessex | −0.00037 [−0.00110, +0.00029] | −0.00040 [−0.00102, +0.00016] | −0.00069 [−0.00107, −0.00036] |
| F25 | Yorkshire | −0.00067 [−0.00113, −0.00028] | −0.00069 [−0.00132, −0.00011] | +0.00003 [−0.00032, +0.00041] |
| F25 | **the nine** | −0.00038 [−0.00066, −0.00010] | −0.00035 [−0.00067, −0.00006] | +0.00002 [−0.00024, +0.00032] |
| | **both folds** | −0.00099 [−0.00137, −0.00063] | −0.00085 [−0.00121, −0.00052] | +0.00034 [−0.00016, +0.00093] |

Layer 1 alone, over both folds: A 0.04201, R2 0.04105, R1 0.04104. All tables are in `-scores.csv`,
`-differences.csv`, `-reliability.csv`, `-shifts.csv`, `-rain.csv` and `-checks.json`.

### Question 1: the conditions

**1a. The level follows the weather: PASS.** 17 of 18 pairs agree in sign; 14 were needed.
Spearman's ρ is 0.950 over the 18. As stated, the pairs share their weather, so this is a reading
rule, not a significance test.

**1b. The level moves the forecast: FAIL.** 7 of 9 predicted signs held; 8 were needed.

| Fold | Company | Spill-hours shift | Predicted sign | s_c = mean A − mean R2 | Held |
|---|---|---|---|---|---|
| F24 | United Utilities | +0.832 | + | +0.0278 | yes |
| F24 | Northumbrian | +0.899 | + | +0.0061 | yes |
| F24 | Wessex | +0.989 | + | +0.0031 | yes |
| F25 | Anglian | +0.929 | + | +0.0005 | yes |
| F25 | Severn Trent | +0.308 | + | −0.0060 | **no** |
| F25 | Southern | −0.358 | − | −0.0104 | yes |
| F25 | Thames | +0.892 | + | +0.0149 | yes |
| F25 | United Utilities | −0.263 | − | +0.0041 | **no** |
| F25 | Wessex | +0.276 | + | +0.0019 | yes |

No sign was predicted at F25's Northumbrian (s_c −0.0019), South West (+0.0010) or Yorkshire
(+0.0025).

**The answer to question 1 is no, as stated.** 1a holds and 1b does not.

### Question 2: the conditions (R2 against A)

1. **A real gain overall: PASS.** 0.04071 against 0.04169; −0.00099 [−0.00137, −0.00063].
2. **Neither fold clearly worse: PASS.** F24 −0.00272 [−0.00368, −0.00170]; F25 −0.00038 [−0.00066,
   −0.00010]. Both lie below zero.
3. **No company clearly worse: FAIL** at Southern 2025, +0.00108 [+0.00048, +0.00180]. No other
   company-fold's interval lies above zero.
4. **Reliability: FAIL** at Southern 2025. R2's ECE is 0.0213, against A's 0.0110, and over the 0.02
   allowance. It passes at the other 11.

**The answer to question 2 is no, as stated.**

**R1, the observation**, passes all four:
1. −0.00085 [−0.00121, −0.00052];
2. F24 −0.00228 [−0.00308, −0.00149], F25 −0.00035 [−0.00067, −0.00006];
3. no company-fold's interval lies above zero;
4. its ECE is no higher than A's, or at most 0.02, at all 12.

The statement says R1's result cannot make the answer yes.

### Observations, not tested and not grounds for any change

- **Where both covariates moved the same way by a lot, A's forecast moved with them, and it was the
  wrong way.**
  - *Measured:*
    - F24 United Utilities (shift +0.83): A's mean forecast was 0.128 against 0.096 observed. R2's
      was 0.100.
    - F25 Thames (+0.89): A 0.067, R2 0.052, observed 0.043. A's ECE there, 0.024, is the failure
      D2 recorded.
  - *Inferred:* this is the effect PR #259 saw on 2023, here in the other direction.
- **Where the shift was small, the two forms differed for some other reason.** At F25's Severn Trent
  (+0.31) and United Utilities (−0.26), s_c had the wrong sign. *Inferred:* removing company levels
  changes the fitted function, and that change is as large as what a shift of about 0.3 log units
  does. The 0.25 threshold was too low for 1b to read the shift alone.
- **At Southern the raw level pointed the right way.**
  - *Measured:*
    - Southern's median spill hours fell 0.36 log units from the 2023 to the 2024 return.
    - Its 2025 rain was 215 mm below 2024's (`-rain.csv`).
    - A forecast 0.055 and R2 0.066, against 0.044 observed. A was already too high, and R2 raised
      it further.
    - In every reliability bin from 0.1 up, fewer of R2's site-days spilled than A's. In the 0.4 to
      0.5 bin, 31.0% of R2's spilled against 37.2% of A's, for forecasts averaging 0.448.
  - *Inferred:* a return's level carries its own year's wetness. When the next year moves the same
    way, as at Southern, that carry-over helps the raw model. When it reverses, as at Thames and at
    United Utilities in F24, it hurts. R2 assumes no carry-over. Over these 12 company-folds, R2's
    Brier is lower at 11, but the effect is not simply an error.
- **Using the training year's return is not a fix.** It was worse than A at F24's Northumbrian and
  Wessex (+0.00512, +0.00526), and level over both folds (+0.00034 [−0.00016, +0.00093]). Many
  overflows lack a value in the older return (above). So it mixes stale values with company medians.
- **No cost of removing company levels showed in layer 1.** R2's pooled layer alone scored 0.04105
  against A's 0.04201 over both folds. It was slightly worse than A's at Anglian, Severn Trent,
  Southern and Thames in 2025, by 0.00014 to 0.00103.
- **Every form forecast 2025 too high.** Over the nine, A's mean forecast was 0.0653 against 0.0573
  observed. R2 and R1 were at 0.0652 and 0.0666. *Inferred:* this is D2's carry-over of 2024's
  offsets, which no covariate form here touches.
- **F24's gain is mostly United Utilities.** There R2 − A is −0.00483. At Northumbrian and Wessex
  it is −0.00086 and −0.00108, and both intervals include zero.

### What follows

- Nothing is deployed. `spill_model.pkl` and `lead_calibration.json` are unchanged.
- **F26 runs as stated** once the 2026 files are out, whatever F24 and F25 found. Its conditions are
  for R2.
- **R1 passed every condition of question 2.** But it was the observation, so this is not a yes.
  Making R1 the decider would be a new test. It would have to be stated before the 2026 files are
  read, and judged on 2026. That is Ethan's decision.
