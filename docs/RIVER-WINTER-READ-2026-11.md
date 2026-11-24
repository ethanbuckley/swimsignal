# River E. coli in winter: does the hidden estimate order a river's days?

Statement written 24 November 2026 against main `65ed8967`, and pushed **before any October to April sample result
was read or joined to rain, exposure or a model figure**. Project ID: RIVER-WINTER. Owner: the Claude session that
wrote the [next research shortlist](NEXT-RESEARCH-SHORTLIST-2026-11.md). It extends
[RIVER-UNSEEN](RIVER-UNSEEN-PROTOCOL-2026-11.md) and changes none of its rules, results or files.

Nothing on the site, in a frozen file, in an active window or in the 2027 primary evaluation changes because of
this read. A pass leads to a proposal for Ethan, not to a change.

## Why this, why now

- From October to April the site works out production's E. coli chance at every river spot and hides it. The tile
  reads "Out of season" (`ECOLI_OFF` in `levels.js`, DESIGN "The E. coli estimate out of season", 20 October 2026).
  The level comes from the spill forecast alone (#32). The river line "higher or lower than usual here" (#709) is in
  season only.
- Every reader between now and May is out of season. No test here has scored a winter river sample. The estimate is
  hidden because it is untested, not because it was shown to fail.
- The Environment Agency's archive holds winter river E. coli results at the same points RIVER-UNSEEN used. The
  sealed table (`swimsignal-private/river-unseen/samples.parquet`, SHA-256 `95ca8c9f…`) already contains them. No
  script has parsed them: RIVER-UNSEEN kept May to September rows only.
- Published measurements say winter differs. On the River Leam, modelled field-runoff load was larger than overflow
  load in three winter and spring events and smaller in August (Suslovaite and others 2024, Water Research). So a
  model fitted on summer samples may not carry over. That is a reason to test, not a prediction of the result.

## What was known when this was written

- Everything in RIVER-UNSEEN's record: at these points in May to September 2012-22, production as deployed ordered a
  point's days at 0.376, the candidate `river-range-v0e` at 0.360 (0.314 to 0.394), rain alone at 0.355.
- Counts of winter rows by point, month, year and purpose, made from every column of the sealed table **except the
  result** (`winter_read.py counts`).
- The row builder, run in this session's scratch root, rebuilds RIVER-UNSEEN's 6,322 summer rows with the same
  inputs (largest difference 4e-16). Those rows were read on 16 November.
- The read script was tried with `--dev` on 1,621 of those summer rows (four river systems, five seasons), to check
  that it runs. Summer rows are seen. Their figures are development and are not quoted here.
- No winter result, by me. The repository's scripts that open the sealed table filter on `kept`, which requires May
  to September.

## Rows

From the sealed table, a row is in this study when all of these hold. Each is decided without a result.

- Material "RIVER / RUNNING SURFACE WATER".
- Sampling purpose MS, MP, MU, MN, PI or PN (RIVER-UNSEEN's kept purposes).
- Sample taken in October to April.
- Calendar years 2012 to 2022 (RIVER-UNSEEN's held-out span).
- At one of RIVER-UNSEEN's 59 kept points (`docs/river-unseen/points.csv`, `kept_point`). The points were chosen
  from positions, names and summer row counts. No new point rule.

A winter is named by the year of its January: October to December of year Y belong to winter Y + 1.

**Two halves, fixed now.**

| Half | Winters | Rows | Points | Points with 15 or more rows | Rows at them |
|---|---|---|---|---|---|
| Read (this statement) | 2012, 2014, 2016, 2018, 2020, 2022 | 2,855 | 39 | 28 | 2,825 |
| Reserve (not opened) | 2013, 2015, 2017, 2019, 2021, 2023 | 2,561 | 41 | 27 | 2,543 |

The reserve stays sealed. It is the unseen set for any winter model fitted after this read. `winter_read.py` loads
results for the read half's row ids only.

The read half's 28 points with 15 or more rows: 18 in the South West, 5 Anglian, 4 North West, 1 Southern. They sit
in 8 river systems (11 points in the Hampshire Avon and Dorset Stour system). 17 medium catchments, 8 large, 3
small. 84% of rows have purpose MU. Winter 2012 holds January to April only.

## Inputs

Built by `scripts/river_unseen/build_rows.py`, unchanged, in a scratch root (clones of the main checkout's
`data/raw` and `data/processed` with this commit's tracked data laid over, scratch `DIPCAST_STATE`, and a scratch
`DIPCAST_CACHE` holding clones of the ERA5-Land cell files for these points and their overflows, 2012-22).

- Rain in the 48 and 24 hours before the sample time, ERA5-Land at the point's cell.
- Upstream exposure: the lead-0 hindcast through the committed spill model and transport settings.
- Rows the builder drops (no full rain window, no exposure) are counted in the audit file. January 2012 will lose
  rows whose window reaches into December 2011, which is not on disk.

Known differences from what a build has at issue time, as in RIVER-UNSEEN: the rain is reanalysis, not a forecast;
the exposure uses the whole sample day's rain; there is no soil moisture before 2023, so production is scored
without it; the spill model was trained on 2024-25 and is fed ERA5-Land. Lead 0 only.

## The figure that decides

**Production's river chance of a sample over 900, as deployed**: `data/processed/ecoli_model.json`, SHA-256
`7daf7c8e…`, committed before RIVER-UNSEEN's read and unchanged. River form, lake terms zero, its day-of-year terms
included. This is the figure the site computes and hides today, and the figure #709's words are made from.

## Conditions, both needed for a pass

Fixed before the read. Seed 20261124.

1. **Raw order.** The mean, over points with 15 or more rows, of the within-point Spearman correlation between the
   figure and the measured log10 count. Pass: the 95% interval lies wholly above **0.15**. This is RIVER-UNSEEN's
   metric and bar.
2. **Order beyond the calendar.** The same, after taking off, from both the figure's log-odds and the log10 count,
   the point's own mean for that calendar month (point-months with fewer than 3 rows are left out). Pass: the 95%
   interval lies wholly above **0.15**.

Condition 2 is there because winter spans seven months with a strong calendar trend. A figure that only knew
December from April would pass condition 1 and tell a swimmer nothing about which day to pick.

The interval: 2,000 resamples of river-system winters drawn with replacement, RIVER-UNSEEN's method. A drawn
system-winter brings every row at every point of that system in that winter. Month means are recomputed inside each
resample. There are 8 systems, so the interval rests on few independent rivers; the read reports each condition with
each system left out in turn.

**Not run** if, after the builder's drops, fewer than 20 points have 15 or more rows or fewer than 1,500 rows
remain.

## Reported, deciding nothing

- The same two figures for: rain in 48 hours alone; exposure alone (the driver of the live winter level); the
  candidate `river-range-v0e` (`3c8bfe59…`); production without its day-of-year terms. Each with its month-removed
  interval, and production less each as a paired difference.
- Level: the share of results over 900 and the median count, beside production's mean chance and its Brier score.
  The Brier of a constant set to this half's own rate is given beside it; that constant uses the results, so it
  flatters itself.
- By month group (October and November; December to February; March and April), by era (winters to 2016; from
  2018), by catchment band and by purpose.
- The 23 points with no monitored overflow upstream (read half: 1,184 rows, 12 points, 8 with 15 or more), where
  exposure is 0 as production gives: rain alone and production.
- The summer rows already read, scored by the same code at all 59 points and at this read's points. Development.

## What each outcome leads to

- **Both pass.** A proposal for Ethan: run the river line ("higher or lower than usual here") from October to April
  at river spots, with winter cut-points made the way #709 made the summer ones. Whether a percentage could show is
  judged from the level figures and said in the proposal. The reserve half stays sealed as the check on any later
  change. Nothing shows until he decides.
- **Condition 1 passes, condition 2 fails.** The winter order is mostly the calendar. No day-to-day line is
  proposed. Next deliverable: a winter candidate with the same inputs, fitted on the read half, frozen, then scored
  once on the reserve under its own statement.
- **Condition 1 fails.** The measurements support keeping the estimate hidden out of season, and the record says
  so with the month groups. If rain alone or exposure alone has a month-removed interval wholly above zero, the next
  deliverable is the winter candidate above. If neither does, "a winter river E. coli line from rain and spills" is
  archived; it reopens with winter samples at swim spots (DENSE's Yorkshire samples run all year).
- **Too few rows.** Recorded as not run; the reserve is not opened to make up numbers.

In every case the exposure-alone figure is passed to whoever owns the winter level: it is the first measurement of
whether the thing a winter reader is shown tracks bacteria at all. It decides nothing here.

## Limits, stated before the read

- These are monitoring points, not swim spots. 18 of 28 are in the South West. Most rows are one purpose (MU).
- 8 river systems. A pass is confirmation at these points and little evidence about a northern or a chalk river.
- Lead 0, reanalysis rain. A pass does not show that a forecast made days ahead orders winter days.
- A pass supports an order within a place. It does not support a count, a range or "safe".
- The bar and metric were set for summer. This statement was written knowing the summer result at these points.
- Winter samples sit unevenly: 2012 to 2016 hold most rows.

## How to rerun

```
export DIPCAST_ROOT=<scratch>/root DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<scratch>/cache PYTHONPATH=src
python scripts/river_winter/winter_read.py counts <sealed samples.parquet>
python scripts/river_winter/winter_read.py build <sealed samples.parquet> <private out dir>
python scripts/river_winter/winter_read.py read <private out dir> <RIVER-UNSEEN's held-out summer rows>
```

`build` and `read` refuse to run unless this file, the scripts and the two frozen files are committed. `read` writes
`docs/river-winter/result.json` and appends to `docs/river-winter/reads.jsonl` whatever it shows. Built rows hold
results and stay out of git, in the session's scratch folder. They rebuild from the sealed table with the commands
above, and `result.json` records their SHA-256.

---

## Amendment 1, 24 November 2026: two builder fixes, before any winter result is scored

Pushed before the rows were built. It changes no row rule other than the one named below, no point, no figure, no
condition, no bar and no outcome.

**What happened.** The first `build` (statement commit `bcdb9155`) stopped with an error inside the row builder at
one of the first points: "Cannot infer dst time from 2015-10-25 01:00:00". It had loaded the read half's results
into memory to shape the rows. It wrote no row and printed, summarised and scored no result. `read` then found no
rows and stopped. Nothing is in `docs/river-winter/`.

**Cause.** `lake_range_hindcast.build_rows` finds the first day of a hindcast by stepping back multiples of 24 hours
from a local midnight. Across the October clock change that lands on 01:00, which cannot be placed; across the March
change it lands on 23:00, which matches no sample day and would have silently dropped rows. May to September rows
never cross a clock change, so RIVER-UNSEEN's read was not affected.

**Fix 1: calendar days.** `winter_read.build_rows_calendar_days` is that function with one line changed: it steps
back whole calendar days. `lake_range_hindcast.py` and `river_unseen/build_rows.py` are untouched. Check, on rows
already read: `winter_read.py selftest` rebuilds RIVER-UNSEEN's 6,322 summer rows with the changed builder and
matches the stored rows on every input (6,322 of 6,322; largest difference 4e-16 in exposure, 0 in rain).

**Fix 2: no row sampled before 1 February 2012.** The ERA5-Land files on disk start on 1 January 2012. One spill
model input is the rain of the last 30 days, summed over whatever days exist, so a January 2012 row would be fed a
short sum. Those rows are left out before the build: 101 of the read half's 2,855 rows at the kept points and 42 of
1,184 at the no-overflow points (counted from sample times, no result). The read half is then 2,754 rows before the
builder's own drops. The "not run" rule is unchanged (20 points with 15 or more rows, 1,500 rows).

**Run time.** The intervals take about 15 minutes for the read half. No change to the 2,000 resamples.
