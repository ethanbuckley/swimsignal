# More years of training data for the spill model: the test, stated before any run

Written 19 October 2026. At that point no rain had been fetched for it, no model had been trained on its rows, and
no 2023 score had been computed for any candidate. Results go below the line at the end. Nothing above
that line changes after a result is seen.

## Why

The neural challenger lost to the boosted spill model on 2025 (PR #239). Its Brier over the nine
companies was 0.0372 against 0.0362. In every seed the inner hold-out loss was lowest after the first
epoch. *Inferred there, not checked:* the network fitted the particular storms of its one training year,
2024. Ethan asked whether more years of training data could fix that.

PR #258 found and fetched open event-level records before 2024:
- Northumbrian Water, 2020 to 2024;
- Wessex Water, 2020 to 2023;
- Thames Water, from December 2022.

United Utilities 2023 was already held. This test asks two questions, stated separately:

1. **With more years, does the network beat the boosted trees?**
2. **With more years, do the boosted trees beat D2's single-year model?**

2025 has already judged candidates, among them D2's nine-company model (PR #251), the PR #239
network and the PR #254 live-status input. So it is no longer a fresh test year. 2023 has judged none,
so it is the test year here.

## Seen before writing

- **Annual returns.**
  - The EA's annual-returns layer holds 2021 to 2025 only. A distinct-values query on
    `annual_return_year` on 19 Oct 2026 returned those five years.
  - The 2021 return has no long-term average on any row.
  - A return's long-term average covers every full year of monitoring up to that return's year. The
    layer's `data_start_calendar_year` and `no_full_years_edm_data` fields show this. So the 2024 and
    2025 returns' long-term averages include 2023's count.
- **Ids in the 2021 and 2022 returns.** Many rows have no id that resolves to a current one:

  | Company | 2021 | 2022 |
  |---|---|---|
  | Northumbrian | 550 | 545 |
  | Wessex | 351 | 260 |
  | United Utilities | 184 | 190 |
  | Thames | 83 | 293 |

  Matching them by position within 20 m resolves at most 174 per company-year, so they stay unresolved.
- **Event ids** (counted, in the PR #258 files):
  - Northumbrian: 99.5% of 2020 to 2023 events carry current ids.
  - Wessex: 94 to 95% of overflows per year carry annual-returns ids through PR #258's crosswalk.
  - United Utilities' Stream 2023 layer: 3 ids unmapped, holding 4,412 events.
  - Thames: overflows mapped neither way keep a `TW:` id.
- **The counts of `scripts/train_multi_year.py plan`.** It reads events and returns only, with no rain
  and no model. Its counts of overflows, covariate gaps, rain cells and fetch cost are quoted below.
- **Earlier results.** D2's and PR #239's published 2025 scores.

No model has been scored on 2023. D2's candidate and the PR #239 networks have never been run on 2023
rows.

## The rows

The label is D2's: "the overflow spilled that day". A spill-day is any UTC day an event touches
(`features.spill_days`). Days are floored in UTC, and the features are D2's (`features.ALL_FEATURES`).

### Test year: 2023

- **Deciding companies.** United Utilities, Northumbrian and Wessex.
  - United Utilities: the Stream 2023 layer (`edm_events.parquet`), the same route production was
    trained on. In 2024 that route and the EA's file shared 76,958 spill-days, against 846 and 1,333
    in one only (D2).
  - Northumbrian: the Stream layer (PR #258). Its 2024 is identical to the EA's file.
  - Wessex: Wessex's own layer, crosswalked to annual-returns ids (PR #258).
- **Thames is reported apart, not deciding.** Its source is the alert stream. In 2024 the stream
  shared about 90% of the EA file's spill-days on common overflows, missing about 13% of the EA's.
  And only 85% of the overflows that spilled in the 2023 returns have an event in it (419 of 494).
- **Which overflow-years count.** D2's own code (`training.site_years`), applied to 2023:
  - a position in the 2022 return;
  - then either an event in 2023, or 0 spills in the 2023 return;
  - dropped when the 2023 return gives EDM operation under 50%.

  `plan` counts 1,895 overflows at United Utilities, 966 at Northumbrian, 983 at Wessex and 403 at
  Thames. That is about 1.4 million site-days for the three deciding companies.
- **New Year.** Events that began in December 2022 label the 2023 days they run into, where the
  source holds December 2022 (Northumbrian, Wessex, Thames).
- **The 2023 return is used for that coverage rule only**, as D2 used the 2025 return for its 2025
  rows. It is never an input to any model.

### Training years: every other year held

| Year | Companies | Events |
|---|---|---|
| 2020, 2021, 2022 | Northumbrian, Wessex | their own layers (PR #258) |
| 2024, 2025 | all nine English companies | the EA's start/stop files: D2's rows exactly |

- **No 2023 rows from any company.** One storm hits every company at once, so a 2023 row from any
  company would carry the test year's weather and outcomes into training. United Utilities 2023 and
  Thames 2023 are therefore left out too.
- **Thames's December 2022.** It is not training. The 2022 training year holds Northumbrian and
  Wessex only. Thames's 2022 is a pre-go-live snapshot (607 discharges, 522 of them in December), not
  a year's record. Its December events are used only to label the 2023 days they run into, in the
  Thames 2023 rows.
- **The 2024 and 2025 rows are D2's** (`training.site_years`). The script stops unless it gets D2's
  counts: 4,976,868 and 5,077,150 site-days. Only their covariates change (next section).
- **2020 to 2022 rows (Northumbrian, Wessex).**
  - An overflow is any id with a position in a held return, 2021 to 2025. Its position comes from its
    covariate return, else from the latest return that gives one. A position only picks the rain
    cell.
  - The year is kept as D2 keeps one: an event in the year, or 0 spills in that year's return, and
    dropped when that year's EDM operation is under 50%.
  - 2020 has no return. So in 2020 only an event keeps an overflow, and no EDM filter applies.
  - An overflow whose Wessex events kept Wessex's own id has no event under its annual-returns id, so
    this rule drops it in any year its return says it spilled.
- **Training overflow-years** (`plan`):

  | | 2020 | 2021 | 2022 | 2024 | 2025 |
  |---|---|---|---|---|---|
  | Northumbrian | 1,226 | 1,350 | 1,371 | 1,370 | 1,540 |
  | Wessex | 784 | 959 | 1,094 | 1,291 | 1,281 |

  The other seven companies have D2's 2024 and 2025 rows only.
- **Rain windows cross year ends.** January 2024 training rows read December 2023 rain as antecedent
  rain, and January 2023 test rows read December 2022 rain. Only labels are split by year, as in D2.
  *Inferred:* weather that enters training only as antecedent rain, never paired with a 2023 label,
  gives nothing usable about 2023 outcomes.

### Site covariates: no 2023 value

The three covariates are `log_lta_spills`, `log_spill_hours` and `edm_pct`. They come from the annual
returns (`features.site_static_features`). Each row takes them from one return, chosen by the row's
year:

| Row year | Return | lta_spills is |
|---|---|---|
| 2020 | 2021 | the 2021 return's counted spills |
| 2021 | 2022 | the 2022 return's counted spills |
| 2022 | 2021 | the 2021 return's counted spills |
| 2023 (test) | 2022 | the 2022 return's long-term average |
| 2024 | 2022 | the 2022 return's long-term average |
| 2025 | 2024 | the 2024 return's counted spills |

The rules behind the table:
- **Never the 2023 return**, and never a long-term average that includes 2023 (the 2024 and 2025
  returns').
- **Never the row's own year.**
- **Which return.** The latest earlier return that qualifies. Rows of 2020 and 2021 have no earlier
  return held, so they take the next year's.
- **The long-term average** is used only where every year it covers is before the row's year and none
  is 2023. That leaves only the 2022 return's average, for rows of 2023 and 2024. Elsewhere the same
  return's counted spills for its own year stand in. That is one year's count where the average is
  several years' mean.
- **`spill_hours` and `edm_operational_pct`** always come from the chosen return.
- **A value the return lacks stays missing.** The id may be absent from that return, or the return may
  give no value. `site_static_features` then fills it with the company's median over that year's
  overflows, as now.

How many values are filled (`plan`, `lta_spills` / `spill_hours`):
- **2024 rows**, which take the 2022 return. Examples:
  - United Utilities: 538 / 447 of 2,199;
  - Northumbrian: 401 / 432 of 1,370;
  - Anglian: 422 / 424 of 1,399;
  - Wessex: 343 / 343 of 1,291.
- **2025 rows**: 0 to 26 per company.
- **The 2023 test rows:**
  - United Utilities: 223 / 129 of 1,895;
  - Northumbrian: 5 / 30 of 966;
  - Wessex: 84 / 84 of 983.

  These come from D2's own rule for 2023, so D2's candidate would see the same fills.

For the 2023 test rows this table and D2's rule give the same covariates, the 2022 return's. Every
predictor below therefore gets identical inputs on 2023.

### Rain

- **What is needed.** ERA5-Land hourly for each row year's cells, from 1 December of the year before
  to 31 December, from the 0.1° Open-Meteo archive as in D2. 1,623 cells in all.
- **What is missing**, by `plan`, against `data/cache/rain/` and `data/cache/rain_nine/`:

  | File | Cells | Calls |
  |---|---|---|
  | 2020 | 246 | 643 |
  | 2021 | 245 | 640 |
  | 2022 | 251 | 656 |
  | 2023 | 304 | 795 |
  | December 2019 | 246 | 246 |
  | December 2020 | 9 | 9 |
  | December 2021 | 6 | 6 |
  | December 2022 | 334 | 334 |
  | **Total** | | **3,330** |

  A call is Open-Meteo's weight for one variable, max(1, days/14 × 1/10) a location.
- **Pacing.** 3,000 calls an hour, and the fetch stops at 8,000 in one UTC day. The free limits are
  5,000 an hour and 10,000 a day.
- **Where it goes.** Every new file goes to `data/cache/rain_multi/`, never to `data/cache/rain/` or
  `data/cache/rain_nine/`. The E. coli validation and the hindcasts read every file in the shared
  folder, and the D2 and PR #239 scripts read `rain_nine/`. A new file in either would change what
  they compute.
- **Reading.** This test reads all three folders. An hour held twice is counted, with how many of
  those hours disagree. December files are named `archive_<cell>_<year>dec.parquet`, as D2 did.
- **Not fetched.** Lead forecasts. Open-Meteo's previous-runs archive has no lead-1 to lead-4 rain for
  2023 (README, E. coli section).

## The candidates, trained on the same rows

The training rows are all of 2020 to 2022 and 2024 to 2025 above, in year order. Both candidates use
`fit_pooled`'s subsample: every spill-day, and dry days kept with `numpy.random.default_rng(0)` at
`neg_frac` 0.25 over those rows in that order, weighted 1/0.25. It is the same mask for both.

- **(A) The boosted model.** D2's features and settings: `SpillModel.fit_pooled(neg_frac=0.25, seed=0)`.
  That is the same `HistGradientBoostingClassifier`, monotone in rain, with early stopping on a random
  10% of its rows.
- **(B) The PR #239 network, unchanged.**
  - The same inputs: 72 hourly values, 28 daily totals and the 5 static inputs.
  - The same layers (5,681 weights) and loss.
  - The same fit: Adam at learning rate 0.001, batch 1,024, at most 20 epochs, patience 3.
  - The same three seeds (0, 1, 2), with the mean of their probabilities clipped to [0.0001, 0.9999].
  - The code is `scripts/train_nn.py`'s, imported, not copied.
  - The inner hold-out is by ISO week as before: every fourth ISO week (4, 8, …, 52) of every training
    year, by the ISO week of the UTC day. It is held out from training and used only to stop.
  - The static inputs are standardized over the training rows, inner hold-out excluded.
- **Layer 2 for both.** `SpillModel.fit_site_offsets`, prior strength 15, fitted on each candidate's
  own layer-1 predictions over every training row.
  - **Recency 1:** every training year counts the same.
  - **Why.** The test year sits inside the training span: 2022 and 2024 are each one year from it.
    Recency below 1 would weight years by their distance from 2025, the newest, which has nothing to
    do with 2023.
- **The epoch timing.** As PR #239's step 3: one epoch of one seed is timed first. If 20 epochs of
  one seed would take more than 2 hours, the run stops and the timing is written below the line. Any
  smaller network would then be stated here as a new candidate, before 2023 is scored.

## Context rows, scored on the same 2023 rows, not deciding

| Predictor | What it is |
|---|---|
| D2 | `spill_model_nine_2024.pkl` (SHA-256 begins `1603678923cc`), from `swimsignal-private/baselines/`, as it is |
| PR #239 network | its three networks as published (SHA-256 `2a9b45bf52da`, `89b3aebd9b2f`, `75c7f33952cf`), with layer 2 refitted exactly as PR #239 did, on D2's 2024 rows |
| A24 | A's settings on the 2024 rows alone, with this test's covariates, and layer 2 on those rows |
| Flat rate | the company's spill-day rate over its training rows |

- **The single-year models have touched 2023 in one way.** D2 and the PR #239 network were trained on
  2024 rows whose covariates came from the 2023 return. They have seen 2023 annual-return values as
  inputs, never a 2023 daily label. *Inferred:* this cannot tell them which 2023 days spilled. It is a
  caveat on question 2 all the same.
- **What A24 is for.** A differs from D2 in two ways at once: more years, and the covariate rule above.
  A24 has the rule without the extra years. So A against A24 shows the years alone, and A24 against
  D2 shows what the rule costs.
- **What the PR #239 network row is for.** B against it shows whether more years helped the network.
- None of these three comparisons decides anything.

## Scoring on 2023

- **The 90% rule.** A row whose 72-hour window has fewer than 65 finite hours is dropped from every
  predictor's scoring, as in PR #239. The count is reported. Missing hours inside a kept window are 0
  with the missing flag set, for both networks.
- **What is reported.** For each of the three companies, the three together, and Thames apart:
  - rows and base rate;
  - Brier score and AUC;
  - ECE (D2's definition) and a 10-bin reliability table.
- **Uncertainty.** Paired differences in Brier get 95% intervals from a week-cluster bootstrap:
  - weeks are ISO (year, week) of the UTC day;
  - 2,000 resamples of weeks with `default_rng(0)`, every row of a week drawn together;
  - one set of draws serves every company;
  - the interval runs from the 2.5th to the 97.5th percentile.

  The differences are B − A and A − D2. As context: A − A24, A24 − D2, and B − the PR #239 network.

## Question 1: with more years, does the network beat the trees?

PR #239's conditions, adapted to the three deciding companies. Its numbers are kept, so 3 and 6
are absent.

1. **A real gain overall.** Over United Utilities, Northumbrian and Wessex together, B's Brier is lower
   than A's, and the 95% interval of B − A lies wholly below zero.
2. **No company clearly worse.** At none of the three is B's Brier higher than A's with the interval of
   B − A wholly above zero.
4. **Reliability.** At each of the three, B's ECE is no higher than A's, or it is at most 0.02.
5. **More rain does not lower the risk.** On the 2023 rows of the three, adding 1 mm to every finite
   hour of the 72-hour window lowers B's final probability (with layer 2) on fewer than 0.5% of rows,
   and by no more than 0.01 on any row. The same holds for doubling every finite hour.

- **Condition 3 (not worse with forecast rain) cannot be scored on 2023.** Open-Meteo's previous-runs
  archive has no lead-1 to lead-4 rain for 2023.
- **Condition 6 (cheap to run) is not re-measured.** The network is the same size as PR #239's, which
  took 5.7 s.

The answer to question 1 is **yes only if conditions 1, 2, 4 and 5 all hold**. A fail on condition 1
alone answers it **no**.

## Question 2: with more years, do the trees beat D2's single-year model?

1. Over the three deciding companies together, A's Brier is lower than D2's, and the 95% interval of
   A − D2 lies wholly below zero.
2. At none of the three is A's Brier higher than D2's with the interval of A − D2 wholly above zero.

The answer is **yes only if both hold**.

## What follows from either answer

Nothing is deployed, whatever the result. `spill_model.pkl` and `lead_calibration.json` do not change.

A "yes" to either question would not be an adoption. It would be grounds for a pre-stated adoption
test of its own. That test would use forecast rain and the conditions this one cannot score, on data
no candidate has seen (2026, once its files are out).

## Order of work

1. Commit and push this statement and open a draft PR against main, before any rain is fetched.
2. Fetch the missing rain: about 3,330 calls, paced as above.
3. Build the rows. Check D2's 2024 and 2025 counts, and report the coverage and the filled covariates.
   Report the largest gap between these 2024 rows' rain features and D2's, on a sample of cells. The
   antecedent index runs from the start of each cell's series, which now starts earlier for
   Northumbrian and Wessex cells.
4. Time one epoch of B (seed 0).
5. Train A, A24 and B's three seeds. Push the training log before 2023 is scored.
6. Score 2023, check both questions' conditions, and write the results below the line.

Run nothing while another evaluation or build is running on this Mac (`pgrep -fl`, never `pkill`).
The models go off-repo to `swimsignal-private/baselines/multi_year/`. The tables go beside this file:
`-scores.csv`, `-differences.csv`, `-reliability.csv`, `-coverage.csv`, `-training.csv` and
`-checks.json`.

---

## Results

### Choices the statement leaves open, fixed before any training

Written 19 October 2026, while the rain was being fetched. At that point no row had been built, no
model trained, and no 2023 score computed. The code is `scripts/train_multi_year.py`.

- **Stages.** `plan`, `fetch`, `rows`, `time`, `train` and `score`.
  - `rows` builds every year's site-days once, the 2023 rows included, and saves them with the rain
    arrays (`data/processed/multi_year/`).
  - Only `score` reads the 2023 rows' labels or predicts them.
- **An id held twice in one return.** The covariates come from the last row with a position, as
  `training.site_years` picks it.
- **One 2023 Thames row is dropped.** `site_years` kept a return row with no id. It got a "0 spills"
  from another row with no id in the 2023 return, because NaN matches NaN in its lookup. That row names
  no overflow. With it gone, `plan` finds 0 overflows of 2023 whose covariates differ from D2's rule.
  D2's 2024 and 2025 rows hold no such row.
- **Events with no id are dropped.** There are none in these files.
- **Rain read.** The files tagged 2019 to 2025, and the December files, from `rain/`, `rain_nine/`
  and `rain_multi/`. No 2026 file, and nothing from `rain_w10/`.
- **The check against D2's rain features.** 80 cells of D2's 2024 overflows, drawn with
  `default_rng(0)`. D2's features are rebuilt from `training.load_rain`, which starts on 1 December
  2023, and compared over 2024 and 2025. A smoke test on 6 Severn Trent cells, which have no new
  files, gave 0 difference in every rain feature. On the same cells the network's hourly windows and
  daily totals equalled `train_nn.RainGrid`'s.
- **Row order, which fixes the subsample.**
  - The years go 2020, 2021, 2022, 2024, 2025. Within a year the rows are in the order `_frame`
    builds them.
  - `fit_pooled` and `train_nn.subsample` draw the same mask from `default_rng(0)` over that order.
- **PR #239's network as context.**
  - Its static inputs are standardized with its own 2024 means and deviations (its `meta.json`).
  - Its layer 2 is refitted on D2's 2024 rows with D2's covariates, built here. The rows are D2's (the
    count is checked). The network's inputs come from the same hourly and daily rain, which the smoke
    test reproduced exactly.
- **Bootstrap.** One set of 2,000 draws over the ISO weeks of every scored 2023 row, Thames included,
  serves every group.
- **Condition 5.** It is checked on the scored rows of the three deciding companies.
- **Also reported, as observations.** Layer-1-only scores for every model, and each seed of B alone.
- **Software.** PyTorch 2.14.1, from the `nn` group.
