# A summer lake temperature model that knows the lake: a frozen-model backtest

Written 13 November 2026 under the research workflow's "Develop promising work now" and "Backtest instead of waiting"
(Ethan, 6 November 2026). Register row LAKE-TEMP. This file states the test **before any model in it is fitted and
before any outcome of the test years is read**. Results go below the line at the end. Nothing above the line changes
after a result is seen; any change is a dated amendment, with both results kept.

Earlier lake records: the first model test (#414, `docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md`), the second lake test
(#419, `docs/LAKE-TEMPERATURE-TEST-2026-10.md`), the sensor audit and buoy checks
(`docs/LAKE-TEMPERATURE-SENSORS-2026-10.md`) and the winter backtest (#638, `docs/WATER-TEMP-WINTER-BACKTEST-2026-11.md`).
Their verdicts and the 1.5 °C lake limit stand. Nothing here changes them.

## The question

#419 failed worst at large, deep lakes: on 2026, WFD lakes of 1 km² and over scored 2.79 °C against 2.14 to 2.19 for the
plain baselines, about 1.2 °C too cold, and its boosted correction made lakes with a depth figure worse. It knew depth
only as one input among ten, inside one model for every lake.

This test asks: **does a model that treats each lake by its type (mean depth, else "no depth figure") and season, fitted
on other lakes and other years, read summer lake temperature better than what the site shows today?** It is judged
against the existing 1.5 °C limit, and reported by depth class and lake size.

## What is seen, and why a backtest is possible

| Years (May-Sep) | Lake outcomes scored before? | Use here |
|---|---|---|
| 2023-2025 | Yes: #414's test, #419's secondary arm (aggregates by year, month, size) | development |
| 2026 | Yes: #419's primary arm | development (a seen-data report only, below) |
| 2016-2019 | Buoy series at Blelham Tarn and Windermere South were scored for #419's model (not EA rows) | development |
| 2012-2015, 2020-2022 | Trained on by #414 and #419; never scored for any lake model | development |
| **2000-2011** | **Trained on by #414 and #419; never scored, summarised or plotted for any lake model** | **test** |

Checked for this statement: #414 reports lake scores for 2023-25 only; #419 for 2023-25 and 2026; the buoy checks are
2016-19; the winter backtest is October to April. Two things touched 2000-2011 outcomes and are stated plainly:

1. #419's inner window scores (for example "`e5` 1.99, `a14` 2.19") pooled training rows from 2000 to 2025, so they
   include these years, mixed with all other years and every lake. Nothing in this test is taken from them: every
   window here is chosen inside the development years.
2. The measured-observations export (`data/research/lake_temperature_obs.v1.json`) publishes monthly medians per lake,
   pooled over 2000-2026. They are observations, not model errors. They were not read for this design.

The design choices below (depth classes, a season term per class, holding connected basins together) come from #419's
2026 and 2023-25 group results and from physics, not from any 2000-2011 result. So **2000-2011 are held-out years in the
workflow's sense**, and a frozen-model backtest is possible now. The 2027 season is then monitoring, not a gate.

**One bias, stated now.** The deployed live model (`data/processed/water_temp_model.json`) was fitted on every water's
rows from 2000 to 2022. On 2000-2011 it is **in-sample**: it has seen these lakes and these years. That favours the live
route. So the live route is scored twice: as deployed (in-sample), and refitted with the same recipe on the development
years without the test lakes (out-of-sample). Both are reported. The verdict needs both.

## Data

All already held. No download, no EA request, **no Open-Meteo call**.

- **Rows:** #419's features file, `swimsignal-private/water-temperature/lake-test/work/features.parquet`, SHA-256
  `fe42bd203ed50251909bab23220547843224177eccd6f03171cfd1befb436dc3` (EA determinand 0076, lake points, May-Sep, one row
  per point and local day; HadUK-Grid 5 km air windows from 1 April). Rows with HadUK air (`hk_ok`), 2000-2025.
  Counted before writing this (no temperature read): **test 2000-2011, 8,007 rows at 282 waters; development
  2012-2025, 7,336 rows at 466 waters** (before the basin merge below).
- **The live route's refit:** #414's features file, `swimsignal-private/water-temperature/work/features.parquet`, SHA-256
  `4e9ca630a8658aaea7eb69890571def6ab55f5e5e7d95c985d261ff7a77f936d` (river, lake and sea rows, as the live model was
  trained).
- **Lake outlines:** `data/processed/lakes.parquet` (EA WFD lakes, cycle 3, 564 polygons, British National Grid).
- **Point positions:** #419's `points.parquet` (same folder).
- **Depth:** HydroLAKES v1.0 mean depth (`Depth_avg`, CC-BY 4.0), already joined in the features file (`depth_m`) from
  `data/raw/lake_residence.csv`. Modelled from area and surrounding slope for most British lakes, not measured.
- **Elevation:** the features file's `elevation`, the Open-Meteo 0.1° cell's elevation (not the lake surface).
- **The deployed model:** `data/processed/water_temp_model.json` and `src/dipcast/model/water_temp.py` as on main
  `a58ea835`.

Every shared file above is read only. Their SHA-256 are checked before and after each stage. Outputs go to a scratch
folder outside the repo, with `DIPCAST_ROOT` and `DIPCAST_STATE` pointed at scratch.

### Where lake facts come from, and what is missing

| Fact | Held | Coverage of rows (2000-2025, HadUK) |
|---|---|---|
| WFD lake area | `lakes.parquet` | WFD-matched waters only (210 waters, 10,872 rows) |
| Mean depth | HydroLAKES via `lake_residence.csv` (282 of 564 WFD lakes) | 133 waters; none for OS-link or own waters |
| Altitude | Open-Meteo 0.1° cell elevation | every row, but it is the cell's mean height (Coniston's cell reads 736 m; the lake is at about 44 m) |
| Season | day of year, month | every row |

**Missing, and what would supply it:**
- **Lake surface altitude.** HydroLAKES' `Elevation` field is in `HydroLAKES_points_v10_shp.zip` (78.7 MB, CC-BY), which
  was checked on 13 October and kept only in a scratch folder. It is no longer on disk. Downloading it again needs
  Ethan's OK. Without it, upland lakes whose air cell sits far above the water cannot be corrected by height.
- **Measured depth.** No open source found (13 October search: UK Lakes Portal states no licence; Wikidata has two).
- **Depth for small and unmatched waters.** HydroLAKES covers lakes of 10 ha and more; most own waters and OS-link
  lakes have no depth. They form their own class here.
- **WFD typology depth class.** Not held.
- **Air before 1 April.** HadUK files on disk are April to September, so long memories are cut short in May (as in #419).
  More files need Ethan's CEDA account.

## Water bodies: connected basins held out together

A lake must not be in training while it is being tested. #419 grouped points by WFD polygon, which put Windermere's two
basins in different folds; the buoy check showed the gain at Windermere South depended on the North Basin being in
training. So groups are merged before folds are assigned:

1. Two WFD lakes with rows whose outlines are within **50 m** of each other are one water (union-find; Windermere North
   and South must merge; the run log lists every merge).
2. An OS-link or own-water group with any point within **500 m** of a WFD outline with rows joins that WFD lake's water
   (nearest outline). 500 m is generous on purpose: an extra merge only makes the hold-out stricter.
3. Folds: `int(sha256("lake-local-v1:" + water id), 16) % 5`.

Merging changes only which rows are held out together and how they are resampled. Each row keeps its own lake facts.

## Classes, fixed now from lake facts only

| Class | Rule | Test rows / waters (counted, before the merge) |
|---|---|---|
| deep | HydroLAKES mean depth ≥ 10 m | 1,711 / 17 |
| mid | 3 m ≤ depth < 10 m | 1,924 / 47 |
| shallow | depth < 3 m | 1,608 / 34 |
| no depth | no HydroLAKES depth (small WFD lakes, OS-link lakes, own waters) | 2,764 / 184 |

10 m is where a British lake with a mean depth that size is expected to stratify through summer; 3 m is where wind mixes
it to the bottom. Both are physical rules of thumb, not tuned. The deep class is the 17 lakes from Derwent Water (10.7 m)
to Haweswater (23.0 m), including Windermere, Ullswater, Coniston and Rutland Water.

## The candidate forms, and how one is chosen

For a row at local date d, with τ in #419's grid (5, 10, 15, 20, 30, 45, 60, 90 days) and `e_τ` the exponentially
weighted HadUK air mean from 1 April (as in #419):

- **K0, pooled:** `T = a + b·e_τ + s·sin(2π·doy/365.25) + c·cos(2π·doy/365.25) + g·elevation`, one fit for all lakes,
  one τ.
- **K1, by class:** the same form fitted separately for each class, with its own τ.
- **K2, by class with month offsets:** K1 with an offset for each month (May to September) in place of the sine and
  cosine.

Ordinary least squares. Inside each outer fold, using only that fold's training rows (other folds' waters, development
years):

- **Inner splits:** each of the four training folds in turn is held out; fit on the other three, predict it. Score: the
  pooled RMSE over the four.
- **τ:** for K0, the τ with the lowest inner score; for K1 and K2, for each class separately, the τ with the lowest inner
  score on that class's rows. A tie goes to the shorter τ.
- **Form:** the lowest inner score over all rows. A more complex form (order K0, K1, K2) is chosen only if it beats every
  simpler one by more than **0.02 °C**.
- **Small class fallback:** a class with fewer than 5 training waters or 100 training rows in a fold uses K0's fit for
  its rows in that fold.

The chosen form is then fitted on all of that fold's training rows. That is the frozen fold model.

## The comparators

All scored on the same test rows, unrounded.

| Name | What | Fitted on |
|---|---|---|
| **live (deployed)** | today's summer lake route in `estimate_any`: under 1 km² or no area, the #414 model as a lake (`lake_model`); 1 km² and over, the lake curve in 7-day air (`lake_curve`). Fed HadUK air directly (the model was trained on HadUK) | frozen file, all waters 2000-2022: **in-sample** |
| **live (refit)** | the same recipe (`wt_protocol.fit_candidate` on river, lake and sea rows; then the same size routing), refitted per fold | #414 rows with HadUK air in development years, minus every row of the fold's test waters (by point, and by WFD id) |
| **7-day air** | `T = a + b·a7` on lake rows | fold's training rows |
| **#419 model** | #419's lake-only recipe (`lt_protocol.fit_fold`: chosen window line plus boosted correction) | fold's training rows |
| day of year | the mean by day of year (from `lt_protocol.fit_fold`) | fold's training rows; reported only |

## Freezing, then one score

1. `prepare`: merge, folds, split. Writes the development rows, the test **inputs** (no temperature column) and the test
   **truth** (point, date, temperature) as separate files. Prints counts only. The truth file's SHA-256 is written to
   the run log below, and committed, before any model is fitted.
2. `freeze`: fits every fold model (candidate and comparators) on development rows only, writes their parameters, and
   predicts the test inputs. It never opens the truth file. It also reports the development cross-validation (labelled
   development; development years only). The SHA-256 of the frozen parameters and of the test predictions are committed
   to the run log before step 3.
3. `score`: refuses unless the three committed hashes match. Joins the truth and scores once.

## Metric, intervals, and the verdict

On the 2000-2011 test rows of all five folds together:

- RMSE, bias, mean absolute error and P90 (90th percentile of the absolute error) for every model.
- **Intervals, 95%, two-way cluster bootstrap:** water bodies and years drawn with replacement independently; a row's
  weight is its water's draw count times its year's. 2,000 draws, numpy `default_rng(20261113)`. Gains (comparator RMSE
  minus candidate RMSE) and the candidate's own RMSE. A water-only bootstrap is also reported.

**Conditions:**

1. gate: at least 30 held-out waters and 300 test rows;
2. candidate RMSE ≤ **1.5 °C** (the existing limit);
3. candidate P90 ≤ **2.5 °C** (#419's tail rule);
4. gain over live (deployed): lower end of the interval above 0;
5. gain over live (refit): lower end above 0;
6. gain over 7-day air: lower end above 0;
7. gain over the #419 model: lower end above 0.

**Answers, fixed now:**

- **Meets the lake limit:** 1, 2, 3, 6 and 7 all hold.
- **Better than the live route:** 4 and 5 both hold. If only one holds, the record says which and does not call it
  better.
- **By class and size** (deep, mid, shallow, no depth; WFD 1 km² and over): the same gains against both live versions,
  with two-way intervals when the group has at least 10 waters (marked "few" below 20). A group is **better** when both
  lower ends are above 0, and **not harmed** when both lower ends are above −0.1 °C.

## Reported, deciding nothing

- Rounded whole degrees (what the page shows) for the candidate and the live route.
- By month, May against June to September, by test year, by fold, reservoirs, #419's size bands, Windermere (merged),
  the Lake District deep lakes as a list with rows and RMSE each.
- The forms and τ chosen in each fold.
- **Seen-data report:** the frozen fold models applied to the 2026 rows of their held-out waters with #419's bridged
  Open-Meteo air (`_om` windows), beside #419's published 1.97 °C. Seen; decides nothing.
- Rows dropped at each rule.

## What each outcome leads to

Nothing on the live site changes in this PR, whatever the result.

- **Better than the live route, and meets the limit:** a separate PR proposes the candidate as the summer lake route,
  worded "typically within X °C" with X the backtest RMSE rounded up to the next 0.5 °C. Ethan decides; it changes what a
  swimmer reads.
- **Better than the live route (overall, or in some classes), but misses 1.5 °C:** a separate draft PR proposes routing
  the classes that are better and the rest not harmed to the candidate, still labelled provisional, with the backtest's
  typical error per class and no "tested" claim. Classes that are not better keep the live route. Ethan merges.
- **Not better:** the live route stays. The record names which class failed and why, if the scores show it. Next
  deliverable: the lake-altitude input (HydroLAKES re-download, Ethan's OK), March HadUK air (Ethan's CEDA account), or
  an archive of the class approach with what would reopen it.
- **Too few to judge (gate fails):** as "not better", and the record says what data would answer.
- **Monitoring, any release:** the frozen fold models (or one refitted on all development rows, if released) are scored
  once on EA lake rows May to September 2027, after 31 October 2027. Rollback rule for any released route: RMSE more than
  0.5 °C above the backtest figure sends that class back to the live route.

## What is expected, stated now

Guesses, not results. The candidate will beat the live route and #419 at deep lakes, by roughly 0.3 to 0.8 °C, because
it lets deep lakes have their own lag and seasonal offset. Overall it will be within about 0.1 °C of the live route,
since most rows are small lakes where the live model already does well. It will probably still miss 1.5 °C overall
(#419's 7-day line scored about 1.9 to 2.0 °C). K1 is the most likely form; deep lakes will pick a long τ (30 days or
more), small ones a short one.

## Order of work and budget

1. This statement, committed and pushed before any fit.
2. The harness (`scripts/lake_temp_local_model/`) with synthetic tests (`tests/test_lake_temp_local_model.py`).
3. `prepare`, `freeze`, `score`, each run once from committed code, hashes committed between them.
4. Results below the line; register row and catalogue entry.

Compute: under 15 minutes on this Mac, offline. No network request of any kind.

## Run log (written before any score)

Code: this branch. Outputs: a scratch folder outside the repo (`DIPCAST_ROOT` and `DIPCAST_STATE` in scratch too).
Statement committed in `af8555a3` and pushed; harness and synthetic tests in `c1f5f99c`, both before any fit.

**Prepare** (`llm_run.py prepare`, 13 November 23:56 UTC, commit `c1f5f99c`, a few seconds). Counts only.

- 16,679 rows read (all with air for their span). Shared inputs' SHA-256 were the same before and after.
- **Merges:** 8 pairs of WFD lakes within 50 m, among them Windermere North and South (GB31247007 + GB31247008) and
  three chained basins (GB30547009 to GB30547012). 24 OS-link or own-water groups joined a WFD lake within 500 m (for
  example a Coniston point, `NW-88021529`). 22 merged waters in all hold more than one #419 group. No water is in two
  folds. The full list is in `docs/LAKE-TEMP-LOCAL-MODEL-2026-11-prepare.json` (copied from the scratch `prepare.json` after the score; counts only).
- **Test, 2000-2011:** 8,007 rows at **265 waters** (282 before the merge). Deep 1,711 rows / 16 waters; mid 1,924 / 47;
  shallow 1,608 / 30; no depth 2,764 / 180. WFD 1 km² and over: 2,359 / 26.
- **Development, 2012-2025:** 7,336 rows at 450 waters. Deep 1,107 / 15; mid 967 / 57; shallow 1,525 / 32; no depth
  3,737 / 352.
- **Seen 2026:** 1,336 rows at 214 waters.
- **Test truth file SHA-256: `1e58fc382cba5b13e3e6a865f94d0231440153a433800aec16614722222bcb73`**, committed here
  before any model is fitted. Test inputs (no temperature) `b5bb6cf0a6dc4397d9aa1247ccd6a7f8cada7bc33630140f8f721c49b4075f58`;
  development rows `6c0d45867ac0ed455b325db4dbbdd293b04cdce05b98ccc0775a0fbefe246275`.

**Freeze** (`llm_run.py freeze`, 13 November 23:57 UTC, commit `7403565c`, 26 s). The truth file was not opened.
Shared inputs (#414 features, the live model file, `water_temp.py`) had the same SHA-256 before and after.

- Forms chosen inside training rows: **K1 in folds 0, 1, 2 and 4; K0 in fold 3** (K1 beat K0 by 0.017 there, under the
  0.02 margin). τ: 5 days pooled in every fold; by class, deep 10 days in folds 0 and 2 and 5 in folds 1 and 4; every
  other class 5 days. K2 never beat K1.
- #419's recipe chose `e5` in every fold. The live refit trained on about 300,000 river, lake and sea rows a fold.
- **Frozen parameters `frozen.json`: `f2bd4d5dc15012026d382a0eee090e9fc576fb9f89f262ce09b9562eec4c37f5`** (it records the
  SHA-256 of the fitted scikit-learn models, `models.pkl`: `e9ccccf6375329b7ca1bbe87e651ccd096f5a11b520e71108de03732e365314a`).
- **Test predictions `predictions_test.parquet`: `c3db84b09077cb15b4356c4e7d2c30f8a8f31fc32c2716f9fcfbca34b352ff8f`.**
- **Development cross-validation** (development years 2012-2025, each fold's waters held out; seen data, development
  evidence only; the deployed live route is in-sample for 2012-2022). RMSE °C (bias):

  | rows | candidate | live (deployed) | live (refit) | 7-day air | #419 recipe |
  |---|---|---|---|---|---|
  | all, 7,336 | 1.65 | 1.61 | 1.63 | 1.85 | **1.55** |
  | deep, 15 waters | 1.52 (+0.04) | 1.61 (−0.11) | 1.60 (+0.05) | 1.60 | **1.34** (−0.20) |
  | mid, 57 | 1.68 | **1.65** | 1.66 | 1.81 | 1.66 |
  | shallow, 32 | 1.33 | 1.32 | 1.34 | 1.66 | **1.27** |
  | no depth, 352 | 1.79 | 1.70 | 1.74 | 2.00 | **1.67** |
  | WFD 1 km² and over | 1.52 | 1.62 | 1.61 | 1.62 | **1.37** |

  So before any test-year outcome: the candidate beats both live versions at deep and large lakes, loses at small lakes
  with no depth figure, and #419's recipe is best in every development class. This is stated before scoring so it
  cannot be read as hindsight. Nothing in the test was changed because of it: the protocol's class answers already ask
  whether a deep-lakes-only route is supported.

---

## Results

Added 14 November 2026 after the one scoring run: 13 November 23:58 UTC, under a second, commit `2f2178c9`, offline. The
truth, frozen-parameter and prediction SHA-256 matched the ones committed above, and so did `models.pkl`. Aggregates
only: `docs/LAKE-TEMP-LOCAL-MODEL-2026-11-score.json`. Per-row predictions stay in the scratch folder. No deviation
from the statement. The heavy-run lock of the earlier lake tests was not used: it lives in another session group's
notes folder, and every stage here took under 30 seconds.

**Plain answer: the lake-type model is not better than the live route, and it misses 1.5 °C.** On 265 lakes it never
saw, in May to September 2000-2011, it read 2.01 °C typical error against 1.93 °C for the live route as deployed.
At deep lakes, the group it was built for, it tied the live route (2.36 against 2.40, interval of the gain
−0.15 to +0.15 °C). At small lakes and lakes with no depth figure it was worse. The live route stays.

### Verdict (test years 2000-2011, held-out waters)

| | candidate | live (deployed, in-sample) | live (refit) | 7-day air | #419 recipe | day of year |
|---|---|---|---|---|---|---|
| RMSE °C | **2.01** [1.75, 2.34] | 1.93 | 2.03 | 2.16 | 2.04 | 2.78 |
| bias °C | +0.25 | +0.14 | +0.29 | +0.26 | +0.21 | |
| P90 °C | 3.03 | 2.89 | 3.03 | 3.34 | 3.08 | |
| gain of the candidate [95%, two-way] | | **−0.08** [−0.17, −0.01] | +0.02 [−0.04, +0.07] | +0.15 [+0.09, +0.21] | +0.03 [−0.02, +0.09] | |

265 waters, 8,007 rows. A negative gain means the candidate is worse.

| condition | result |
|---|---|
| 1. gate (30 waters, 300 rows) | yes |
| 2. RMSE ≤ 1.5 °C | **no** (2.01; the interval's lower end, 1.75, is above 1.5 too) |
| 3. P90 ≤ 2.5 °C | **no** (3.03) |
| 4. beats live (deployed) | **no**: the deployed route is better, interval wholly below 0 |
| 5. beats live (refit) | **no**: +0.02, interval includes 0 |
| 6. beats 7-day air | yes |
| 7. beats #419's recipe | **no**: +0.03, interval includes 0 |
| **meets the lake limit** | **no** |
| **better than the live route** | **no** |

The water-only bootstrap gives the same answers (gain over the deployed route −0.15 to −0.02). Rounded to whole degrees,
as the page shows: candidate 2.03, live 1.95.

**The in-sample point.** The deployed route had seen these lakes and years. Refitted without them, the live recipe
scored 2.03, level with the candidate. So the honest comparison of methods is a tie (+0.02 [−0.04, +0.07]); the
deployed route's 0.08 lead is partly that it was fitted on these rows. Either way the candidate is not better.

### By class and size (two-way intervals; "answer" uses both live versions, as stated)

| group | waters | rows | candidate | live | live refit | #419 recipe | gain over live | gain over refit | answer |
|---|---|---|---|---|---|---|---|---|---|
| deep (≥ 10 m) | 16 | 1,711 | 2.36 | 2.40 | 2.42 | 2.35 | +0.04 [−0.15, +0.15] | +0.06 [−0.10, +0.18] | harm not ruled out (few waters) |
| mid (3-10 m) | 47 | 1,924 | 1.75 | **1.61** | 1.79 | 1.81 | −0.14 [−0.35, −0.02] | +0.04 [−0.03, +0.12] | harm not ruled out |
| shallow (< 3 m) | 30 | 1,608 | 1.71 | 1.65 | 1.74 | 1.75 | −0.06 [−0.16, +0.05] | +0.02 [−0.06, +0.13] | harm not ruled out |
| no depth | 180 | 2,764 | 2.10 | **1.95** | 2.07 | 2.15 | −0.15 [−0.22, −0.08] | −0.03 [−0.09, +0.04] | harm not ruled out |
| WFD 1 km² and over | 26 | 2,359 | 2.20 | 2.26 | 2.28 | 2.19 | +0.06 [−0.08, +0.16] | +0.07 [−0.05, +0.17] | not harmed |

- **No group is "better".** Deep and large lakes come closest, with point gains of 0.04 to 0.07 °C and intervals
  that include 0. The deep group's own RMSE interval runs from 1.50 to 3.27 °C: 16 waters, of which two (Windermere, both
  basins, and Rutland Water) hold 1,270 of the 1,711 rows.
- At mid-depth and no-depth lakes the deployed route is better. Against the refit, those groups tie.

**Deep lakes one by one** (RMSE °C; candidate / live / #419 recipe; candidate bias):

| lake | depth (HydroLAKES) | rows | candidate | live | #419 | bias |
|---|---|---|---|---|---|---|
| Windermere South Basin | 15.5 m | 566 | 2.09 | 2.24 | 2.18 | 0.00 |
| Windermere North Basin | 15.5 m | 438 | 2.65 | 2.71 | 2.65 | +0.24 |
| Rutland Water | 11.0 m | 266 | 3.22 | 3.09 | 3.03 | **+1.47** |
| Bewl Water | 12.3 m | 71 | 1.24 | 1.43 | 1.40 | −0.46 |
| Bassenthwaite Lake | 12.6 m | 63 | 1.41 | 1.44 | 1.45 | +0.45 |
| Roadford Lake | 13.7 m | 53 | 1.38 | 1.27 | 1.46 | +0.67 |
| Coniston Water | 12.4 m | 42 | 2.04 | 1.97 | 2.02 | +0.45 |
| Ennerdale Water | 17.2 m | 40 | 1.26 | 1.58 | 1.36 | −0.28 |
| Cow Green Reservoir | 14.2 m | 39 | 1.73 | 1.82 | 1.59 | +0.77 |
| Wast Water | 15.9 m | 25 | 2.43 | 2.54 | 2.49 | **+1.84** |
| Ullswater | 18.2 m | 24 | 1.75 | 1.86 | 1.75 | +1.11 |
| Derwent Water | 10.7 m | 23 | 1.31 | 1.52 | 1.19 | +0.18 |
| Haweswater Reservoir | 23.0 m | 22 | 2.64 | 2.51 | 2.72 | **+1.78** |
| Thirlmere | 14.0 m | 17 | 1.40 | 1.37 | 1.44 | −0.27 |
| Derwent Reservoir | 15.8 m | 16 | 1.70 | 1.70 | 1.55 | −0.77 |
| Selset Reservoir | 14.9 m | 4 | 0.99 | 1.23 | 1.93 | +0.53 |
| Crummock Water | 12.4 m | 2 | 3.67 | 2.80 | 3.45 | +3.00 |

**Months** (candidate / live, RMSE; candidate bias): May 2.06 / 2.01 (+0.57), June 2.25 / 2.15, July 2.23 / 2.10,
August 1.84 / 1.72, September 1.55 / 1.58. **Years:** 2000-2003 were the worst for every model (candidate 2.21 to
3.08, bias +0.29 to +0.83; live 2.05 to 2.90); 2004-2011 ran 1.55 to 2.04. **Folds:** 1.80 to 2.22.

### The development and seen-data figures, for comparison

- **Development** (2012-2025, waters held out; stated in the run log before the score): candidate 1.65, live deployed
  1.61, live refit 1.63, #419 recipe 1.55. Deep lakes there: candidate 1.52 against 1.61 and 1.60 for the two live
  versions. **That deep-lake lead did not hold on the test years** (2.36 against 2.40 and 2.42, intervals across 0).
- **Seen 2026** (frozen fold models, bridged Open-Meteo air; decides nothing): candidate 1.94, live deployed 1.82, live
  refit 1.77, #419 recipe refit on development years 1.82 (#419's own published figure on 2026 was 1.97). Deep lakes in
  2026: candidate 2.59 (bias −0.63), live 2.26 (bias −0.96).

### What the scores establish

1. **A depth class with its own line and season term does not fix large, deep lakes.** Inside training rows, every
   class chose a short air memory (τ 5 days; deep lakes 5 or 10), not the long lag the design expected, and the
   by-month form (K2) never beat sine and cosine.
2. **The deep-lake error is lake-specific and changes sign between eras.** In 2000-2011 deep lakes read too warm
   (candidate +0.39 °C, live +0.27); in 2026 they read too cold (candidate −0.63, live −0.96; #419's large lakes −1.24).
   A fixed offset per class cannot follow that. Three lakes (Wast Water, Haweswater, Rutland Water) read 1.1 to 1.9 °C
   too warm on average in 2000-2011 under both the candidate and the live route, while others (Bewl Water, Derwent
   Reservoir) read 0.5 to 1.0 °C too cold.
3. **Small lakes are better served by the live route's boosted model than by a straight line** in this backtest (mid:
   1.61 against 1.75; no depth: 1.95 against 2.10). Against the same recipe refitted out of sample, they tie.
4. **No model reaches 1.5 °C on these years.** The best, the deployed route with an in-sample advantage, scores 1.93.

**Inferred, not tested:**
- HydroLAKES depth is modelled from area and slope. Published lake surveys give Wast Water a mean depth of roughly 40 m and
  Ullswater roughly 25 m (from memory of those surveys, not checked against a source in this PR), against 15.9 and
  18.2 here. The deepest lakes may be put in the right class for the wrong reasons, and their
  depth order is not trusted.
- The early-year warm bias (2000-2003, every model) may come from how or when the EA sampled then, or from HadUK's
  early grids. Nothing here separates the two.
- Lake-specific offsets (point 2) may be fixed facts of a sampling point (a sheltered bay, an outflow, a sampling depth)
  or drift with years. Only a lake's own readings over time can tell.

### What this does not show

- Every test row is an EA spot sample, mostly in the working day, not a reading at a swim entry.
- The test air is HadUK analysis, not the forecast-API air the live build reads through the bridge. The live inputs
  would add the forecast error on top.
- Lake surface altitude, measured depth and air before 1 April were not available (listed above).
- 16 deep lakes, with two lakes holding over half their rows: the deep-lake figures are wide.

### What follows

As stated for "not better": **the live route stays. Nothing on the live site changes.**

- **No clean summer years are left for lakes.** 2000-2011 are now scored, 2012-2026 were seen before. Any new summer
  lake candidate is judged on May to September 2027 (EA rows, read after 31 October 2027), with its protocol, hashes and
  frozen fold models committed before May 2027. A buoy series not yet scored (for example Esthwaite or Windermere North
  from EIDC) could serve as a partial check for a few lakes, if one exists for years outside those already used.
- **Next deliverable (development, now): a per-lake "own history" candidate for the listed lake spots.** Finding 2 says
  the large-lake error is a lake's own offset, not its class. For the 15 lakes linked to 20 listed spots in the
  measured-observations export, a candidate can learn each lake's offset from its own earlier readings and be tested,
  forward in time, on its later ones (development evidence on seen years), then frozen for 2027. It holds out years,
  not lakes, so it would only ever apply at lakes with a record.
- **Inputs that need Ethan:** the HydroLAKES points file again for lake surface altitude (78.7 MB, CC-BY, a download
  he approved once before); measured depths for the Lake District lakes (no open source found); March HadUK files
  (his CEDA account).
- The class approach is archived as tested: reopen it only with measured depths or a lake-altitude input, judged on
  2027.
