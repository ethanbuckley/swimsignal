# Winter water temperature: a frozen-model backtest of the October–April estimate

Written 6 November 2026, under the workflow's "Backtest instead of waiting" (Ethan, 6 November 2026, PR #629).
Issue #492 (rivers #477, lakes #478). This file states the test **before any request is made and before any winter
outcome is read**. Results go below the line at the end. Nothing above the line changes after a result is seen; any
change is an amendment, dated, with both results kept.

## Why this candidate

Since 31 October every river and lake spot shows a water-temperature estimate all year (#536, #538, #548). From
October to April it comes from the `river_off_season` or `lake_off_season` route: the water type's curve in the
7-day air. The page says "provisional estimate, not yet checked in these months". The baseline record
(`docs/WATER-TEMPERATURE-BASELINE-2026-10.md`) says why: every test row was May to September. Its plan for the
winter error is a readout from the live log, `state/water_temp_estimates.parquet`, as the winter goes on. Three EA
sensors sit beside named spots, so that readout will be thin, and it would finish after the winter it describes.

History can answer now. The model was fitted on May–September 2000–2022 (`trained_on` in the model file) and scored
on May–September only. No October–April water temperature has been fitted, scored, summarised or plotted for it by
anyone in this project (checked: the model test, the lake test, the sensor replay and the baseline record are all
May–September; the sensor replay's 2023–25 daily series returned no readings). So every past winter is a held-out
year in the workflow's sense.

The candidate table (step 1 of the task) is in the PR body and in the register; it lists the others and why they
were not picked.

## The frozen model

Nothing is refitted. The test reads these files at these hashes; the harness refuses to score if either differs.

| File | SHA-256 |
|---|---|
| `data/processed/water_temp_model.json` | `637674ae2b60631d0589a9eceec1ef4fd7fc9ed21d344c397dff7820e0e2087d` |
| `src/dipcast/model/water_temp.py` | `938060d0d6588c7bb0e73e5f0d815174c59d21ef6023c64808935717254a3f5a` |

Both are as on main `0f79ebd8`. The route under test is `estimate_any`'s off-season branch:

- London calendar-day means of hourly air (`water_temp.daily_air`: a day counts only with all its hours);
- the model's bridge, `0.5013 + 0.9792 × air`;
- `a7`, the mean of the 7 days to the day;
- the type's Mohseni curve in `a7` (river or lake parameters in the model file);
- shown as `int(round(max(0, t)))`, whole degrees.

The harness calls the module's own functions for each step (`scripts/water_temp_winter_backtest.py`). A test checks
that its shown value equals `estimate_any`'s `temp_c` for both types (`tests/test_water_temp_winter_backtest.py`).

The same curve, in a cell's 7-day air, is what a map click (`river_air_curve`, `lake_air_curve`) and a directory
water in Wales, Scotland and Ireland show off-season. The score applies to them with one difference: they use the
nearest cell's air, up to a ring away, not always the point's own cell.

## Held-out data

- **Primary winters:** 2023, 2024 and 2025, where winter Y is 1 October Y to 30 April Y+1. So 1 October 2023 to
  30 April 2026.
- **Reserved winter:** 2022 (1 October 2022 to 30 April 2023). Not fetched and not read unless the candidate step
  below runs. It is then fetched only after that candidate is frozen and its hash committed.
- **Water:** EA Water Quality Archive, determinand 0076 (temperature of water), fresh-water materials `2AZZ,2GZZ`,
  one query a month, paged by 2,500 (the model test's client and parsing). One row per sampling point and local day,
  the mean of that day's readings. Rows with a result that is not a number, outside −1 to 35 °C, or not in Celsius
  are dropped, as in the model test.
- **Points:** only points already in the water-temperature tests' point tables (the model test's 20,430 points, then
  the lake test's), which give each point its type (river or lake), its 0.1° cell and its water group (named river,
  WFD lake, OS lake, or its own). Points not in them are counted and left out. Sea points are left out.
- **Cells:** the record's rule, applied by `plan` before any air is fetched and without reading any result: cells with
  a primary-winter row, lake cells first in a fixed hash order up to 75, then river cells in the same hash order to
  149 cells in all. The same cells are used for every winter. Rows outside these cells are not scored.

## Issue-time inputs

- **Air:** Open-Meteo's Historical Forecast API, `hourly=temperature_2m`, `timezone=UTC`, the default model. Open-Meteo
  describes it as the forecast API's archived runs, stitched from each run's first hours: that is what the live
  build's past days are. Each winter is asked for from 23 September to 30 April, so `a7` exists from 30 September.
- **Known differences from the live input:**
  1. The live build's today includes forecast hours. Here every hour is an analysis. This touches 1 of the 7 days.
  2. The forecast models have changed since 2023. Open-Meteo says the archive is "not suitable for long time series
     due to model version changes". So older winters stand for today's models only as far as they have not changed.
  3. A spot's own cell is used here; the live spot uses its own cell too, so this matches. Map clicks and directory
     waters may use a neighbouring cell.
  4. The EA sample is one reading, mostly in the working day. The estimate is for the day.
- The bridge and curves are from the model file. Nothing is fitted to these winters in the primary test.

## Metric, intervals and rule

Per water type (river, lake), on the shown whole-degree estimate minus the EA reading:

- **Primary:** root-mean-square error (RMSE). Also the bias (mean error).
- **Intervals:** 95%, a two-way cluster bootstrap: water groups and calendar months (year-month) are drawn with
  replacement independently; a row's weight is the product of its group's and its month's counts. 2,000 draws, seed
  20261106. A group-only bootstrap is also reported.
- **Gate:** at least 30 water groups and 300 rows for the type. Below it: "too few to judge".
- **Pass:** RMSE ≤ 2.0 °C and its upper end ≤ 2.5 °C.
- **Fail:** RMSE > 2.5 °C.
- **Inconclusive:** anything else past the gate.
- **Material bias:** |bias| ≥ 0.5 °C and its interval excludes zero.
- **Reported, deciding nothing:** the unrounded curve's error; a reference "water equals last week's air" (bridged
  `a7`, floored at 0); mean absolute error; share within 2 °C and 3 °C; and each of these by winter, by month, by
  `a7` band (under 3, 3–6, 6–9, 9 and over °C), and by lake size or river catchment band.

2.0 °C is the limit the river model was held to in summer, and what the page's tested wording ("typically within
2 °C") promises.

## What each outcome leads to

The release is wording about the estimate's measured error. It is not a forecast of swimming conditions, and it is
never part of any pollution level. The estimate itself does not change in any branch except the last.

- **Pass, no material bias (per type):** the off-season wording for that type changes from "not yet checked in these
  months" to "provisional estimate; in past winters' EA samples typically within N °C", N the RMSE rounded up to a
  whole degree, as the summer river wording was. The route keeps `tested: false` (the river model's summer pass is
  the only tested route) and gains the winter figure. Spot pages, map clicks and directory waters all get it.
- **Pass with material bias, inconclusive, or fail (per type):** the page gives the measured figures instead of "not
  yet checked": "provisional estimate; in past winters' EA samples typically X °C out, reading about Y °C too warm
  (or cold)", with no "within". The candidate step then runs.
- **Too few to judge:** the wording stays. The record says what data would answer (more winters, or more cells
  within a new cap).

**The candidate step (only if a type's result is not a clean pass).** Development on the primary winters, which by
then are seen:

- W1: the frozen curve plus one constant per type, the mean error on the training rows;
- W2: the same Mohseni form refitted to October–April rows per type (`wt_protocol.fit_mohseni`).
- Each is scored by 5-fold group-out cross-validation on the primary winters (`wt_protocol.fold_of`). The lower CV
  RMSE is chosen; a tie within 0.05 °C goes to W1.
- The chosen one is fitted on all primary rows, frozen, its file hashed and committed, and only then is the reserved
  winter 2022 fetched and scored, with the rules above.
- **Adopt** (as the off-season route for that type, worded by the reserved winter's figure under the rules above) if,
  on winter 2022, its RMSE is at least 0.3 °C below the frozen route's, the two-way interval of the difference is
  wholly below zero, and its own RMSE passes. Otherwise the frozen route stays, with its measured wording, and the
  candidate is recorded with what would reopen it.

## Monitoring after any release

- The live log `state/water_temp_estimates.parquet` keeps running; its sensor rows are read at the end of the 2026–27
  winter, as the baseline record planned.
- After 30 April 2027, this script is run once more on winter 2026 (October 2026 to April 2027) with the same cells.
  **Rollback:** if a type's RMSE there is more than 0.5 °C above the figure on the page, the page goes back to the
  wording before this release until a new record says otherwise.
- The 2027 primary evaluation and every active window are untouched: water temperature is in none of them.

## Caps

Fixed here, in the harness, before any request.

- **EA:** at most 160 requests and 600 MB for this backtest (primary and reserved winters together), one in flight,
  1.5 s apart, `environment.data.gov.uk` only. Stop at the first 403, 429, 5xx or redirect. Expected: about 60 for the
  primary winters (21 months, 2–3 pages each), inferred from the 2026 summer fetch (13 requests for 5 months).
- **Open-Meteo:** at most **1,000 weighted calls** in all, at most 500 in a rolling hour, one request in flight, 25 s
  apart, batches of 25 cells, `historical-forecast-api.open-meteo.com` only, logged on the tag
  `winter-backtest=2026-11`. Any answer but 200 stops the run. Weight by Open-Meteo's rule: 221 days is 1.58 a cell, so
  149 cells cost about 235 a winter: about 704 for the primary winters and 235 for the reserved one. The process
  waits while another local Python job names Open-Meteo. The site's builds run on GitHub's runners, not this Mac, so
  the D4 ensemble window's ration is not touched; this Mac's other sessions are not visible to this client, which is
  why the cap is a tenth of the free daily limit.
- **Lock:** the group's `heavy-run.lock` is taken for each fetch and released after.
- **Nothing paid, no new account.** Both sources are open (OGL v3; Open-Meteo free tier, non-commercial).

## Isolation

- A separate worktree; `DIPCAST_ROOT`, `DIPCAST_STATE` and `DIPCAST_CACHE` point at this session's scratchpad before
  any import.
- New caches go to new folders, `swimsignal-private/water-temperature/winter-2026-11/{ea,air}`. The point tables in
  `swimsignal-private/water-temperature/work/` and `lake-test/work/` are read only; their SHA-256 is recorded before
  and after.
- No live file, state release, issued forecast or shadow log is read or written.

## Limits, stated now

- EA monitoring points are not swim spots. Most are on rivers; winter lake samples are fewer.
- One reading a day at a point, at a time of day the estimate does not know.
- Three winters for the primary result, chosen as the most recent with the Historical Forecast API's current model
  mix. A cold winter or a mild one could move the figure; it is reported by winter.
- The result says how far the estimate has been from samples. It says nothing about whether water is safe to swim
  in, or about cold-water risk.

---

## Results

### Run log

- Protocol `52128118` pushed at 19:58 UTC, 6 November 2026, before any request.
- **EA:** 19:59 UTC, 56 requests, all HTTP 200, 42.1 MB; 109,736 rows (cap 160 requests, 600 MB).
- **Plan** (no result read): 268 lake cells and 1,469 river cells had a primary-winter row; the rule took 75 lake
  and 74 river cells. 715 point-days were at points in neither point table and were left out.
- **Open-Meteo:** 20:00 to 21:04 UTC, 18 requests, all HTTP 200, **703.5 weighted calls** (cap 1,000; the 500-an-hour
  cap paused it once). Historical Forecast API only. The group's heavy-run lock was held from 19:58 to 21:04 UTC.
- **Score:** one run at 21:04 UTC from `52128118`, frozen hashes checked by the harness. Full output:
  `docs/WATER-TEMP-WINTER-BACKTEST-2026-11-primary.json` (SHA-256 `93da0667…`).
- **Shared inputs unchanged:** the two point tables hash the same before and after (`d532f140…`, `1c0f8298…`).
- Rows: 11,129 point-days in the planned cells, every one with `a7`; 9,990 river rows, 1,139 lake rows.

### Primary result

Shown estimate minus EA reading, October to April 2023–26. Intervals: two-way (water group and month).

| | Rows | Water groups | RMSE | Bias (too warm +) | Within 2 °C | Verdict |
|---|---|---|---|---|---|---|
| Rivers | 9,990 | 494 | **2.27 °C** [2.05, 2.49] | **+1.54 °C** [+1.22, +1.87] | 60% | **inconclusive**, material bias |
| Lakes | 1,139 | 137 | **3.64 °C** [3.17, 4.08] | **+3.08 °C** [+2.34, +3.71] | 23% | **fail**, material bias |

Group-only intervals are narrower: rivers RMSE [2.19, 2.33], lakes [3.55, 3.74].

**What this establishes.** In the last three winters the off-season estimate read too warm, at rivers by about
1.5 °C and at lakes by about 3 °C on average. Rivers miss the pass on the point (2.27 against 2.0); the upper end,
2.49, is just inside 2.5, so the result is inconclusive, not a fail. Lakes fail outright.

**Reported, deciding nothing:**

- **Worst in midwinter.** Rivers: January RMSE 3.0 °C, bias +2.5; October 1.6, +0.6; April 1.9, +0.6. Lakes: December
  and January 4.7 °C, bias +4.5; April 1.8, +0.2.
- **Worst in cold air.** Rivers with `a7` under 3 °C: 3.0 °C, bias +2.4 (749 rows). Lakes with `a7` 3 to 6 °C: 4.2 °C,
  bias +3.9.
- **The same each winter.** Rivers 2.24 / 2.39 / 2.15 °C; lakes 3.53 / 3.64 / 3.74 °C (winters 2023 / 2024 / 2025).
- **Lake size makes no difference.** Lakes under 1 km² 3.70, 1 km² and over 3.61, unmatched 3.61 °C.
- **Rounding makes no difference.** Unrounded curve: rivers 2.25, lakes 3.64 °C.
- **The reference "water equals last week's air" did better** than the curve: rivers RMSE 1.94 °C, bias −0.88; lakes
  1.98 °C, bias −0.71. The summer curves flatten towards about 7–8 °C as the air cools, while the water keeps falling.

*Inferred, not tested:* the curves were fitted on May–September water, which never sees cold air, so their lower arm
is set by the bounds of the fit, not by data. That matches the error growing with colder air.

### What follows, as stated above

- Both types: the page stops saying "not yet checked in these months" and gives the measured figures, with the
  direction ("reads too warm"), and no "within".
- Both types: **the candidate step runs.** W1 and W2 are developed on the primary winters (now seen), the chosen one
  is frozen and committed, and only then is winter 2022 fetched and scored.

### The candidate step: development on the primary winters (seen), 6 November 2026, 21:05 UTC

`water_temp_winter_backtest.py candidate` on the primary rows (`rows.parquet` of the scoring run). 5-fold group-out
cross-validation (`wt_protocol.fold_of` on the water group), RMSE of the shown whole-degree value. **Development
figures on seen winters, not a test.**

| | Frozen route | W1 (frozen curve less a constant) | W2 (curve refitted to winter rows) | Chosen |
|---|---|---|---|---|
| Rivers (9,990 rows, 494 groups) | 2.27 °C, bias +1.54 | 1.66 °C, bias 0.00 | **1.57 °C**, bias −0.01 | W2 (beats W1 by more than 0.05) |
| Lakes (1,139 rows, 137 groups) | 3.64 °C, bias +3.07 | 1.97 °C, bias +0.03 | **1.84 °C**, bias −0.02 | W2 (beats W1 by more than 0.05) |

Every W2 fold's fit converged (5 of 5 for each type). W2, refitted on all primary rows, is frozen in
`data/research/water_temp_winter_candidate.v1.json`, SHA-256 `c86720d0c1557f2fb14c6733ab0d5e0014ba122366be64e1e2847a74808d729d`,
committed and pushed **before** any request for winter 2022.

Next, as stated: fetch winter 2022 (EA about 19 requests; Open-Meteo about 235 weighted calls, which keeps the total
under the 1,000 cap) and score the frozen route and W2 on it with the rules above.

### Reserved winter 2022: the frozen-model backtest of W2 (6 November 2026, 21:07 to 21:10 UTC)

- **Fetch** under the group lock: EA 13 requests (69 in all, cap 160), all 200, 22,992 rows; Open-Meteo 6 requests,
  all 200, 234.1 weighted calls (**937.6 in all**, cap 1,000).
- **Score:** one run at 21:09 UTC, `water_temp_winter_backtest.py reserved`, frozen hashes and the candidate's
  (`c86720d0…`) checked. Output `docs/WATER-TEMP-WINTER-BACKTEST-2026-11-reserved.json` (SHA-256 `e7886eba…`). Point
  tables unchanged. 2,734 point-days in the planned cells. (Its `counts` before the winter filter include the primary
  winters' pages, which the run read and then dropped.)

1 October 2022 to 30 April 2023, the same 149 cells. Intervals two-way (water group and month; 7 months).

| | Rows | Groups | Frozen route | W2 | W2 − frozen | Rule |
|---|---|---|---|---|---|---|
| Rivers | 2,468 | 325 | 2.43 °C [1.89, 2.92], bias +1.70 | **1.63 °C [1.43, 1.85]**, bias +0.07 [−0.35, +0.49] | **−0.80 °C [−1.14, −0.39]** | W2 passes; gain beyond 0.3, interval below zero: **adopt** |
| Lakes | 266 | 41 | 3.33 °C [2.58, 4.03], bias +2.81 | 1.64 °C [1.23, 2.07], bias −0.36 | −1.69 °C [−2.63, −0.62] | **too few to judge** (266 rows, gate 300): **not adopted** |

- Rivers, W2 by month: 1.3 to 2.0 °C in every month; bias from −0.9 (April) to +0.9 (February). The frozen route:
  3.3 °C in January and February.
- Lakes, W2 by month: 1.0 to 2.3 °C. It reads cold in March and April (−1.3, −2.0) and slightly warm in January and
  February (+0.5).
- The reference "water equals last week's air": rivers 2.13 °C, lakes 2.03 °C.

**What this establishes.** For rivers, a winter curve chosen and frozen on 2023–26 was typically 1.6 °C out on a winter
it had never seen, with no material bias. Today's route was 2.4 °C out and read 1.7 °C too warm. That is the
frozen-model backtest the workflow asks for. For lakes the direction and size are the same, but the stated gate was not
met, so nothing is adopted for lakes on this result.

**What follows, as stated.** The river off-season route becomes W2, worded "typically within 2 °C" (RMSE 1.63 rounded
up), with this test named. The lake off-season route stays the frozen curve, with its measured wording (typically
3.6 °C out, reading about 3 °C too warm), until amendment 1 decides.

## Amendment 1, 6 November 2026, about 21:20 UTC: more unseen lake rows (before any of its requests)

**Why.** Lakes were "too few to judge" on the reserved winter. The protocol's answer for that case is more winters or
more cells under a new cap. Winter 2022 holds 402 lake rows in all, but 266 are already scored. Counted without reading
any result: the other 136 (26 groups) are too few alone.

**What is unchanged.** The frozen route, W2 (`c86720d0…`, not refitted), the metric, the intervals, the gate, the pass
rule and the adoption rule. The river decision stands as scored. The 266 lake rows already scored are not reused.

**Rows.** Lake points only, from three sets, none used to fit, choose or score anything so far:

- winter 2022 at lake cells outside the 149 already scored (the 136 rows above);
- winters 2020 and 2021 (1 October 2020 to 30 April 2022) at every lake cell with a lake row in that winter.

The same point tables, parsing and cell rule (hash order). The gate and both rules apply to the union of these rows.

**Air.**

- **The Historical Forecast API, as before,** for each winter it serves. Before anything else, one probe request
  decides this: one cell (54.4, −3.0), hourly `temperature_2m`, 1 to 2 October 2020 and 1 to 2 October 2021 (two
  requests, weight 1 each). A winter uses the Historical Forecast API if its probe answers 200 with all 48 hours present.
- **Otherwise ERA5-Land hourly** through the archive API (`models=era5_land`, the same hourly request), and the record
  says which winters used it. *Known difference:* in the 2025 season the archived forecast ran about 0.25 °C cooler
  than ERA5-Land, and about 0.5 °C cooler in late September and October 2026. So an ERA5-Land winter feeds the curves
  slightly warmer air than the live site would have had. Nothing is corrected for it. The effect is reported by winter.
- Days with any hour missing give no `a7`, as before, and are counted.

**Cap.** A new, separate cap of **400 weighted calls** for this amendment, on its own cache log
(`winter-2026-11/air-lakes`), probes included, with the same pace, hour cap and stop rules. With the first 937.6 that is
at most 1,337.6 from this Mac today. If the cells would pass it, cells are dropped from the end of the oldest winter's
hash order. EA: winters 2020 and 2021, about 28 more requests, inside the existing cap of 160.

**What follows.**

- **W2 passes and the adoption rule holds on these rows:** the lake off-season route becomes W2 as well, worded by these
  rows' figure.
- **Otherwise,** or too few again: the lake route keeps its measured wording. W2 for lakes is then scored, unchanged,
  on winter 2026 (October 2026 to April 2027) with this script after 30 April 2027. The Historical Forecast API keeps
  that winter's air, so no live logger is needed.
