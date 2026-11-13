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

*(Filled in as the stages run.)*

---

## Results

*(Added after the one scoring run.)*
