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

### The answers

1. **With more years, does the network beat the trees? No.** Over United Utilities, Northumbrian and
   Wessex in 2023:
   - the network's (B) Brier is 0.0624, the boosted model's (A) 0.0617;
   - B − A is +0.00075, with a 95% interval of −0.00002 to +0.00158;
   - conditions 1, 4 and 5 fail; condition 2 passes.
2. **With more years, do the trees beat D2's single-year model? Yes, as stated.**
   - A − D2 is −0.00395 [−0.00537, −0.00252], and every company's interval lies below zero.
   - **But most of that gain does not come from the extra years.** A24, trained on 2024 alone with
     this test's covariates, already beats D2 by −0.00329 [−0.00485, −0.00185].
   - The extra years on their own (A − A24) give −0.00066 [−0.00149, +0.00013]. Over the three together,
     that interval includes no gain.

### The run

Run 19 October 2026 on this Mac. The statement was pushed at `16e6e1c` and the choices above at
`6c2a922`. The script did not change after that commit. The training log was pushed at `048531b`
before 2023 was scored. The logs are in `logs/*_multi_*2026-10-19.log` in the worktree (not
committed). No other evaluation or build ran. An iOS Simulator started during training; it is not a
SwimSignal job.

- **Rain.**
  - 1,641 new files (3,330 calls, as planned, and one test request) went to `data/cache/rain_multi/`.
    Every hour of every file is present.
  - The first fetch stopped at about 15:44 UTC when DNS failed ("nodename nor servname provided"). It had
    finished December 2019 and 2020. The restart skipped the files already saved.
  - The caches hold 226,176 hours twice, and 0 of them disagree. That is 304 cells × 744 hours: the new
    2023 files overlap D2's December 2023 files.
- **Rows.**

  | | 2020 | 2021 | 2022 | 2023 (test) | 2024 | 2025 |
  |---|---|---|---|---|---|---|
  | Site-days | 735,660 | 842,785 | 899,725 | 1,549,790 | 4,976,868 | 5,077,150 |
  | Base rate | 0.084 | 0.070 | 0.057 | 0.100 | 0.087 | 0.057 |

  - The 2024 and 2025 rows match D2's counts exactly. On 80 cells of D2's 2024 overflows (58,480
    cell-days), every rain feature equals D2's except the antecedent index. That differs by at most
    0.13 mm, because those series now start earlier.
  - The 2023 rows' covariates equal D2's rule's for every overflow.
  - The 90% rule dropped no row, in training or in 2023. Overflow-years kept and covariates filled are
    in `-coverage.csv` and `-covariates-filled.csv`.
- **Timing (step 4).** One epoch of seed 0 took 93 s to train (2,803 batches) and 9 s to score the
  inner hold-out. Twenty epochs would take 34 minutes, under the 2-hour limit, so no smaller network
  was needed.
- **Training.**
  - 12,532,188 training site-days. Both candidates fit the same subsample of 3,808,010: B used
    2,869,335 of them and held out 938,675 for stopping.
  - A and A24 each ran their full 300 iterations, as D2 did.
  - **The network's best epoch moved later** (measured). The inner hold-out loss was lowest after epoch
    2, 4 and 2 (seeds 0, 1, 2), against epoch 1 for every seed in PR #239. Each seed then stopped three
    epochs later. The best losses were 0.16362, 0.16361 and 0.16369 (`-training.csv`).
  - Swap ran almost full (7.2 of 8 GB) while B's layer 2 was fitted. That step took 35 minutes instead
    of about 7. *Inferred:* this changes no number, since the run is on the CPU with fixed seeds.
  - The models are off-repo in `swimsignal-private/baselines/multi_year/` (SHA-256 prefixes: A
    `24b876016959`, A24 `f6464ee46368`, B seeds `ea8c71fdee9c`, `c44550cb2633`, `b7fa499d2078`).

### Scores on 2023, ERA5-Land rain

Brier, with ECE in brackets. Bold marks the better of B and A.

| Company | Rows | Base rate | B (network) | A (boosted) | D2 | PR #239 network | A24 | Flat rate | AUC B / A |
|---|---|---|---|---|---|---|---|---|---|
| United Utilities | 691,675 | 0.119 | 0.0730 (0.018) | **0.0723** (0.012) | 0.0761 (0.024) | 0.0765 (0.017) | 0.0734 (0.012) | 0.1059 | 0.867 / 0.869 |
| Northumbrian | 352,590 | 0.077 | 0.0496 (0.020) | **0.0490** (0.019) | 0.0529 (0.033) | 0.0515 (0.027) | 0.0498 (0.019) | 0.0711 | 0.914 / 0.918 |
| Wessex | 358,795 | 0.092 | 0.0545 (0.020) | **0.0536** (0.016) | 0.0578 (0.029) | 0.0569 (0.022) | 0.0532 (0.009) | 0.0843 | 0.923 / 0.924 |
| **The three** | 1,403,060 | 0.102 | 0.0624 (0.019) | **0.0617** (0.014) | 0.0656 (0.027) | 0.0652 (0.021) | 0.0623 (0.013) | 0.0916 | 0.892 / 0.894 |
| Thames (apart) | 146,730 | 0.088 | **0.0561** (0.024) | 0.0563 (0.024) | 0.0603 (0.031) | 0.0568 (0.018) | 0.0545 (0.010) | 0.0804 | 0.908 / 0.907 |

Paired differences in Brier, first minus second, with 95% week-cluster intervals:

| Group | B − A | A − D2 | A − A24 (context) | A24 − D2 (context) | B − PR #239 network (context) |
|---|---|---|---|---|---|
| United Utilities | +0.00066 [−0.00052, +0.00192] | −0.00382 [−0.00541, −0.00229] | −0.00110 [−0.00203, −0.00023] | −0.00272 [−0.00405, −0.00143] | −0.00349 [−0.00468, −0.00240] |
| Northumbrian | +0.00068 [−0.00072, +0.00221] | −0.00394 [−0.00601, −0.00199] | −0.00084 [−0.00213, +0.00022] | −0.00310 [−0.00513, −0.00142] | −0.00185 [−0.00285, −0.00082] |
| Wessex | +0.00098 [−0.00003, +0.00208] | −0.00423 [−0.00643, −0.00232] | +0.00038 [−0.00072, +0.00153] | −0.00460 [−0.00740, −0.00212] | −0.00231 [−0.00352, −0.00126] |
| **The three** | +0.00075 [−0.00002, +0.00158] | −0.00395 [−0.00537, −0.00252] | −0.00066 [−0.00149, +0.00013] | −0.00329 [−0.00485, −0.00185] | −0.00278 [−0.00360, −0.00201] |
| Thames (apart) | −0.00013 [−0.00097, +0.00065] | −0.00399 [−0.00578, −0.00232] | +0.00172 [+0.00024, +0.00332] | −0.00571 [−0.00850, −0.00299] | −0.00064 [−0.00169, +0.00039] |

Layer 1 alone, over the three: B 0.06429, A 0.06402, A24 0.06454, PR #239 network 0.06577, D2 0.06617.
B's seeds alone scored 0.06462, 0.06459 and 0.06519. All tables are in `-scores.csv`,
`-differences.csv`, `-reliability.csv` and `-checks.json`.

### Question 1: the conditions

1. **A real gain overall: FAIL.** B's Brier is higher, not lower: 0.06240 against 0.06165. The
   difference is +0.00075 [−0.00002, +0.00158]. That interval does not lie below zero. It only just
   reaches it.
2. **No company clearly worse: PASS.** No company's interval lies wholly above zero. Wessex comes
   closest, at [−0.00003, +0.00208].
4. **Reliability: FAIL** at Northumbrian and Wessex. B's ECE is 0.0202 at both, against A's 0.0191 and
   0.0163. Both are 0.0002 over the 0.02 allowance. It passes at United Utilities (0.0183).
5. **More rain does not lower the risk: FAIL**, on size, not share.
   - Adding 1 mm to every hour lowered B's probability on 72 of 1,403,060 rows (0.005%). The largest
     drop was 0.039, and the limit is 0.01.
   - Doubling every hour lowered it on 301 rows (0.02%), by at most 0.017.
   - PR #239's network passed this condition on 2025.

Condition 3 (forecast rain) cannot be scored on 2023. Condition 6 was not re-measured.

**The network does not beat the trees with more years.** It is 1.2% worse over the three companies.
On 2025 PR #239's network was 3% worse. Those were different years and rows, so the two gaps cannot
be compared directly.

### Question 2: the conditions

1. **Lower over the three: PASS.** A 0.06165 against D2 0.06560; −0.00395 [−0.00537, −0.00252].
2. **No company clearly worse: PASS.** All three intervals lie below zero.

**The trees trained here beat D2 on 2023.** The context rows say why, and it is mostly not the extra
years:
- **A24 against D2** (same 2024 rows, different covariates): −0.00329. That is 83% of A's whole gain
  over D2. Its interval lies below zero at every company.
- **A against A24** (the extra years alone): −0.00066 over the three, with an interval that includes no
  gain.
  - It is clear only at United Utilities, −0.00110 [−0.00203, −0.00023]. There the only extra year is
    2025.
  - At Northumbrian and Wessex, which gained four years each, it is −0.00084 [−0.00213, +0.00022] and
    +0.00038 [−0.00072, +0.00153].

### Observations, not tested and not grounds for any change

- **The year a covariate comes from moved the forecasts.**
  - *Measured:*
    - D2's 2024 training rows carry the 2023 return's covariates. Their mean `log_spill_hours` is
      3.46. A24's same rows carry the 2022 return's: 2.84.
    - The 2023 test rows carry the 2022 return's: 2.92.
    - The median spill hours per overflow, over these four companies' returns, were 18.6 in 2022 and
      41.5 in 2023.
    - Over the three companies, D2's mean forecast on 2023 was 0.075, A24's 0.0885 and A's 0.088,
      against 0.102 observed.
  - *Inferred:* D2 learned the link between spill hours and spill-days from a wet year's returns. It
    then read a dry year's returns at test time, so it rated every overflow as less spill-prone and
    forecast too low. The same would hold in production, which also takes covariates from the
    previous year's return. A covariate expressed relative to its own return year (a rank within the
    year, say) might remove this. That needs its own pre-stated test.
- **The network's gain over PR #239's network cannot be split the same way.** B beats it by −0.00278
  [−0.00360, −0.00201]. But PR #239's network was trained on D2's covariates. For the trees, the
  covariate change alone was worth −0.00329. No network was trained on 2024 alone with this test's
  covariates. So this test cannot say how much of B's gain is more years. *Inferred:* much of it is
  probably the covariates, as for the trees.
- **More years delayed the network's overfitting by one to three passes, no more.** The best epochs
  were 2, 4 and 2 against 1, 1 and 1 (measured). In every seed the hold-out loss then rose while the
  training loss kept falling.
- **The network's layer 1 nearly matches the trees'.** It scores 0.06429 against 0.06402. The gap
  widens with layer 2: offsets improve A by 0.00237 and B by 0.00189.
- **B forecasts too low in the middle of the range.** Over the three, its forecasts of 0.4 to 0.5
  averaged 0.447, and 54.2% of those site-days spilled. A's averaged 0.448, and 48.1% spilled.
- **Every model forecast 2023 too low.** Mean forecasts over the three ran from 0.075 to 0.089,
  against 0.102 observed. 2023 has the highest base rate of any year here. *Inferred:* something about
  2023 beyond its rain is not in the inputs, or offsets averaged over drier years pull the level down.
  At Wessex, A24's mean forecast (0.083) is closer to the observed 0.092 than A's (0.076). Not checked
  further.
- **Thames (apart).** B and A are level: −0.00013 [−0.00097, +0.00065]. A24 scores best (0.0545). Adding
  years made A worse there: A − A24 is +0.00172 [+0.00024, +0.00332]. The alert stream missed about 13% of
  the EA's spill-days in 2024, so these labels likely count too few.

### What was not done

- No forecast-rain scoring. There is no lead-1 to lead-4 rain for 2023.
- No network on 2024 alone with this test's covariates (see above). It was not in the statement, and
  adding it now would be chosen after seeing the results.
- Nothing is deployed. `spill_model.pkl` and `lead_calibration.json` are unchanged.
