# One day boundary for training and inference: the test, stated before any run

Written 24 October 2026. Nothing has been trained or scored on the new day boundary. Results go below the
line at the end. Nothing above it changes after a result is seen. Review task A11
(`docs/REVIEW-2026-10-16.md`, finding 3.9).

## Why

The spill model reads daily rain features and is fitted to daily spill labels. Training and the live
forecast cut the day at different moments.
- **Training** (`scripts/train.py`, both `main` and `main_nine`) builds rain features with
  `features.daily_rain_features` on the archive's UTC timestamps, so its days are UTC days. Its labels come
  from `features.spill_days`, which floors event times in UTC. Its grid of days is
  `pd.date_range(..., tz="UTC")`.
- **The lead calibration** (`scripts/verify_leads.py`) does the same.
- **The live forecast** (`forecast.spill_probabilities`) converts the rain to Europe/London before
  `daily_rain_features`, so its days are UK local days.
- **Live scoring** (`forecast_log.observed_spill_days`) counts a spill on the local day it touches. The 2027
  evaluation does the same (`docs/PREREGISTRATION-2027.md`: "target days ... as Europe/London dates";
  "a poll saw an event touching that local day").

In winter the two are the same. In British Summer Time, from the last Sunday in March to the last Sunday
in October, a local day runs from 23:00 UTC the day before to 23:00 UTC. So for seven months the model
is fed features whose day is an hour earlier than the days it was fitted on. A day holds the hourly
stamps 00:00 to 23:00, each the rain of the hour ending then. The stamp 23:00 UTC (rain from 22:00 to
23:00 UTC) falls in the next day's rain in the forecast and in the same day's rain in training. The same
holds for `max1h_d` to `max6h_d`, the lags, the rolling sums and the antecedent index. A spill from 23:00
to 00:00 UTC is on the next local day, and on the same UTC day in training's labels.

**The E. coli path is already on local days.** `ecoli.rain_windows` sums the 48 h and 24 h before a time
(noon on the sample or target day), so it has no day boundary of its own. `train_ecoli.py` converts the
lead forecasts to Europe/London before it calls it. `validate_ecoli.py` and `replay_ecoli_leads.py`
convert the rain and the events to Europe/London before their daily features and labels. Their spill
exposure comes from the spill model, so it inherits the model's training days. That is a knock-on of this
test, stated below; nothing in the E. coli code changes.

## The boundary adopted: UK local days

- **What swimmers read.** Every day the site shows is a Europe/London date. The forecast grid already is.
- **What the live labels use.** `observed_spill_days` and the 2027 scoring use local days.
- **What the training labels allow.** The events are instants. The EA start/stop files head their times
  "(GMT)", and `ingest/edm_events.ea_times` reads them as UTC. United Utilities' layer gives epoch
  milliseconds, read as UTC by `ingest/common.to_utc`. Northumbrian's Stream text is GMT all year (checked
  19 Oct 2026, `edm_events.dmy_times`). So `edm_events.parquet` and `ea_events_*.parquet` hold true UTC
  instants. The day an event touches is a choice made at `spill_days`, not a property of the files. It can
  be cut on local days without loss.

The other direction, the forecast on UTC days, would show swimmers a "today" that ends at 01:00 in summer
and would be scored against local-day labels. It is not tested here.

## Seen before writing

- `data/processed/verification_2025.csv` on main (last changed 13 Sep 2026): the hold-out model, trained on
  United Utilities 2023-24 on UTC days and scored on United Utilities 2025 on UTC days: Brier 0.04453,
  pooled only 0.04517, site climatology 0.06693, n = 826,725 site-days, base rate 0.0745.
- The 2025 lead replay tables in `docs/LEAD-CALIBRATION-B-TEST-2026-10.md` (UTC days throughout).
- Nothing on local days. No model has been trained on local days, and no model has been scored against
  local-day labels for 2025.

## The code change

1. **`features.LOCAL_TZ = "Europe/London"`**, the model's day. `forecast.py` takes its `LOCAL_TZ` from here.
2. **`features.daily_rain_features`** converts `time` to `LOCAL_TZ` before it floors to days. Fed UTC or
   local timestamps, it gives the same local days. This is the one place the rain's day is cut.
3. **`features.spill_days`** counts the local days an event touches.
4. **`features.build_site_days`** raises when the grid's days, the rain's days or the labels' days are in
   different zones. A UTC grid merged with local days does not fail in pandas: it silently finds no rain on
   every summer day (local midnight is 23:00 UTC). Checked 24 Oct 2026 on pandas 3.0.5.
5. **`scripts/train.py`** (`main` and `_frame`, which `main_nine` and `scripts/test_covariate_year.py`
   share) and **`scripts/verify_leads.py`** build their grids on `LOCAL_TZ`.
6. **`hindcast_wales.py` and `hindcast_scotland.py`** say they build features "as train.py builds them".
   Their grids and labels move to local days with it, so that stays true.
7. **The model's `trained_on`** gains "UK local days". The lead map records the `trained_on` of the model it
   was fitted for (`verify_leads.py`), so a map fitted for a UTC-day model no longer matches the new one by
   name.

Not changed: `scripts/train_nn.py`, `scripts/live_status_test.py` and `scripts/train_multi_year.py` build
their own day indices on UTC (`DAY0`, `T0`). They are the records of finished tests, run from their own
commits, and their results stand as written. Fed local days, their `(day - T0) // 1 day` would put every
summer day one index early, without an error. So at this commit they refuse to run and say to use the
commit their record names. Rerunning one on the new model would need the same change as here.
The live-status shadow's candidates (`data/processed/live_status/`) were trained by `live_status_test.py`
on UTC days and are fed local days in the shadow, the same mismatch as production's. They are not touched
while their window runs.

**Tests.**
- **The acceptance test.** One hourly series spanning a BST day, with rain stamped 23:00 UTC.
  `daily_rain_features` gives the same `rain_d`, `max1h_d` to `max6h_d` and lags for that day by the
  training path (UTC timestamps, as `train.py` passes them) and by the forecast path (converted to
  Europe/London, as `spill_probabilities` passes them). The hour counts in the local day it belongs to.
- **Labels.** An event from 23:30 to 23:45 UTC on a BST day is a spill on the next local day. In winter it
  is a spill on the same day.
- **The guard.** `build_site_days` with a UTC grid and local rain raises.
- **The clock-change days.** 29 March 2026 (23 local hours) and 25 October 2026 (25) are whole days by
  `MIN_HOURS_PER_DAY`.

## The retrain

From frozen inputs, so both arms read the same files:
- **Inputs.** APFS clones (`cp -c`) of the main checkout's `data/cache/rain` and `data/cache/rain_nine`, and
  of `edm_events.parquet`, `annual_returns.parquet` and the ten `ea_events_*.parquet` /
  `dcww_ea_events.parquet` in `data/processed`, taken once before the first run. Their SHA-256 list is
  written under the line.
- **Old arm:** `git archive 9be5601` (main when this was written), UTC days.
- **New arm:** `git archive` of this branch's commit that adds the code change and the harness, local days.
- **Each arm** runs in its own scratch `DIPCAST_ROOT`, with `DIPCAST_CACHE` on the frozen clone and the main
  checkout's `.venv` (scikit-learn 1.9.1, pandas 3.0.5, numpy 2.5.3):

      DIPCAST_ROOT=<arm root> DIPCAST_CACHE=<frozen cache> PYTHONPATH=<archive>/src \
        .venv/bin/python <archive>/scripts/train.py 2025 --refit-all

  This writes the hold-out model (trained on 2023-24) as `spill_model_holdout_2025.pkl`,
  `verification_2025.csv` and `reliability_2025.csv` on the 2025 test year, and the production refit on
  2023-25 as `spill_model.pkl`. That is the recipe of the current production model (`trained_on` "United
  Utilities 2023-2025 (refit on all years; verified on 2025 before refit)"). Fits are seeded
  (`SpillModel.fit_pooled`, seed 0), so each arm is deterministic.
- **Nothing is written to the main checkout's `data/processed`.** No Open-Meteo call is made; every input is
  cached.
- **Machine.** Run alone, with the group's `heavy-run.lock`, after the radar backfill, with at least 35%
  memory free.

## The comparison

The target is the label production is scored on: **local-day spill labels.** Both hold-out models are
scored on the same rows, against the same labels, fed the same local-day features. Model A is fed local
features though it was trained on UTC days. That is exactly what production does today.

- **A:** the old arm's hold-out model (UTC days in training).
- **B:** the new arm's hold-out model (local days in training).
- **ΔBrier = Brier(B) − Brier(A).** Negative is better for B.
- **Interval:** a paired bootstrap of ΔBrier over clusters of ISO weeks of the target day (rain and spills
  on one day are shared across overflows, and weather runs for days), 2,000 resamples, seed 1, the 2.5th
  and 97.5th percentiles.

**N1, United Utilities 2025, reanalysis rain.** Rows: the new arm's 2025 test frame from `train.py` (United
Utilities overflows with a 2024 return position, the same-year EDM filter, the target day's rain known),
features from ERA5-Land on local days.

**N2, nine English companies 2025, forecast rain by lead.** Rows and features as `verify_leads.py` builds
them, on local days: the 2025 overflows of the nine companies in cells with archived lead forecasts
(`training.site_years`, no company excluded), the target day's rain and intensity from the lead-k forecast,
the two previous days from leads k-1 and k-2 (floored at 0), the longer windows from ERA5-Land. Leads 0 to
4. Raw model probabilities: no lead map, because each map belongs to one model. Both hold-out models are
out of sample on every 2025 row here, United Utilities' included.

### Within noise: the pass condition

Non-inferiority at a margin of 1% of A's Brier. **Both are required:**
- **N1.** The upper end of the 95% interval of ΔBrier is at most 0.01 × Brier(A).
- **N2.** At each of leads 0 to 4, the upper end of the 95% interval of ΔBrier is at most 0.01 × Brier(A)
  at that lead.

Why 1%: past tests treated a 2% per-company loss as tolerable (`LEAD-CALIBRATION-B`, L2). Over all rows, 1%
is tighter. On the 2025 hold-out it is about 0.00045, a tenth of the gap between the model and pooled-only
(0.00064 on main) and well under the gap to climatology (0.0224).

### Reported, not deciding

- **The before and after of `verification_2025.csv`**, each arm scored on its own definition: A on UTC
  features against UTC labels (the file on main today, recomputed), B on local features against local
  labels. These are different targets, so the pair is a continuity check, not the test.
- **Reproduction.** The old arm's `verification_2025.csv` against the file on main. A Brier difference over
  0.0001 is reported with its cause where it can be found (inputs that changed since 13 Sep). Both arms read
  the same frozen inputs, so the comparison stands either way.
- ECE (ten equal-width bins) for A and B in N1 and in N2 by lead.
- N2 at lead 0 by company: Brier(A), Brier(B), ΔBrier.
- The interval with day clusters beside the week clusters.
- **The production refits.** The mean absolute difference between the old and new refits' probabilities on
  the N1 rows, and the mean of each.
- **How much moves.** The share of 2025 local-day labels and of `rain_d` values that differ from the UTC-day
  ones on the same overflow and date, summer and winter apart. Winter should be zero, which checks the code.

### My prediction (inferred, not a condition)

The change is one hour on seven months' days. I expect |ΔBrier| under 0.2% of Brier in N1 and at every lead.
B should be slightly better on summer days, where the features and labels A was fitted to are an hour off.
The interval should straddle zero.

## What follows

- **If N1 and N2 hold:** the pull request carries the new arm's `spill_model.pkl`,
  `spill_model_holdout_2025.pkl`, `verification_2025.csv` and `reliability_2025.csv`. It does not carry a
  new `lead_calibration.json` (below).
- **If either fails:** no model file changes. The pull request keeps this statement, the harness and the
  results as the record, and A11 stays open. Moving the forecast to UTC days instead would need its own
  statement.

## Interactions, stated now

- **Lead calibration, option B** (`docs/LEAD-CALIBRATION-B-TEST-2026-10.md`). Its live window is 18 Oct to
  14 Nov 2026, read on or after 16 Nov, on the production model with SHA-256 beginning `faa7917e2be725a9`.
  "If `spill_model.pkl` changes on main inside the window, the window ends the day before." So a new model
  must not reach main before the read.
- **The lead map must be refitted for the new model** before the model lands. Whichever map B's verdict
  leaves (B's recipe with `--exclude "United Utilities"` if it passes, the current recipe if it fails) is
  fitted again with `verify_leads.py --model spill_model.pkl` on the new model, so its `model` field equals
  the new `trained_on`. The new `trained_on` names local days, so a stale map shows by name.
- **The live-status shadow** (`docs/LIVE-STATUS-SHADOW-TEST-2026-10.md`) compares its candidates with
  production on target days 25 Oct to 21 Nov 2026 (to 5 Dec if extended). Its fallback rows take
  production's probability. A model change inside that window changes its baseline. So the pull request
  should land after 21 Nov, or after 5 Dec if that window is extended.
- **Ensemble rain** (`docs/ENSEMBLE-RAIN-TEST-2026-11.md`, 23 Oct to 19 Nov): a model change keeps its
  comparison paired; the date goes under its line. No conflict.
- **The E. coli model** reads overflow exposure computed with the spill model. After the swap,
  `validate_ecoli.py` and `train_ecoli.py` should be rerun so its fit and the published validation use the
  new model. That is not part of this test.
- **The 2027 stamp** (`docs/PREREGISTRATION-2027.md`). A new `spill_model.pkl` changes the stamp's `spill=<8>`
  part, and a refitted map changes `cal=<8>`. `src/dipcast/model/` is in `evaluate_2027.MODEL_PATHS`, so the
  code change is a model change too. All of this is allowed before the freeze tag. It means the frozen
  model's stamp is whatever is on main at the tag, as for any model change.

## Order

1. Push this statement.
2. Push the code change, the tests and the harness (`scripts/day_boundary_eval.py`).
3. Freeze the inputs, run both arms and the harness from `git archive`s.
4. Write the results under the line, and open the pull request.

---

## Results

None yet.
