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

Written 25 October 2026, from the outputs of the runs below.

The statement was committed in `f7a5318` (24 Oct 22:29 BST). The code commit `9e6168d` (22:38 BST) also
edited three passages above the line, before any run:
- which hourly stamps fall in which day (the stamp 23:00 UTC, and a spill from 23:00 to 00:00 UTC);
- the paragraph saying `train_nn.py`, `live_status_test.py` and `train_multi_year.py` refuse to run at this
  commit;
- the acceptance test's wording ("rain stamped 23:00 UTC").

The first run started 25 Oct 11:31 GMT. Nothing above the line changed after that.

### Verdict: PASS

N1 holds, and N2 holds at every one of leads 0 to 4. Each upper bound is below its 1% margin. A pass says
the local-day model is not worse than the UTC-day one within the stated margin. It does not authorise a
deployment: that is Ethan's decision, after the dependencies below.

| Set | Rows | Brier, old (UTC days) | Brier, new (local days) | ΔBrier | 95% interval, ISO weeks | Limit (1% of old) | Pass |
|---|---|---|---|---|---|---|---|
| N1 United Utilities, reanalysis | 826,725 | 0.04472 | 0.04480 | +0.000081 (+0.18%) | −0.000078 to +0.000238 | 0.000447 | yes |
| N2 nine companies, lead 0 | 1,939,245 | 0.03959 | 0.03950 | −0.000095 (−0.24%) | −0.000216 to +0.000007 | 0.000396 | yes |
| N2 lead 1 | 1,939,245 | 0.04240 | 0.04233 | −0.000072 (−0.17%) | −0.000186 to +0.000038 | 0.000424 | yes |
| N2 lead 2 | 1,939,245 | 0.04409 | 0.04404 | −0.000054 (−0.12%) | −0.000237 to +0.000122 | 0.000441 | yes |
| N2 lead 3 | 1,939,245 | 0.04551 | 0.04547 | −0.000044 (−0.10%) | −0.000224 to +0.000133 | 0.000455 | yes |
| N2 lead 4 | 1,939,245 | 0.04763 | 0.04761 | −0.000020 (−0.04%) | −0.000223 to +0.000149 | 0.000476 | yes |

Both arms are scored on local-day labels with local-day features, paired, on the same rows. N1 is United
Utilities' own 2025, where the old model was fitted on UTC-day labels of the same company. N2 covers 5,313
overflows in 544 lead cells: United Utilities 2,263, Yorkshire 772, Severn Trent 699, Northumbrian 399,
South West 296, Wessex 275, Anglian 251, Thames 205, Southern 153. Table:
`DAY-BOUNDARY-TEST-2026-10-scores.csv`; checks: `-checks.json`.

### Reported, not deciding

**The 2025 table, before and after** (`DAY-BOUNDARY-TEST-2026-10-verification.csv`). Each arm is scored on
its own day definition, so these are different targets: a continuity check, not the test.

| Model | Before: UTC features, UTC labels | After: local features, local labels |
|---|---|---|
| dipcast (pooled + site offsets) | 0.04474 | 0.04480 |
| pooled only | 0.04517 | 0.04516 |
| climatology (site rate) | 0.06693 | 0.06712 |
| rain rule (>10 mm/48 h) | 0.06214 | 0.06217 |
| rain rule (>5 mm/48 h) | 0.06326 | 0.06341 |
| base rate | 0.07453 | 0.07472 |
| rows | 826,725 | 826,725 |

**The harness's N1 rows are `train.py`'s.** The new model scores 0.0447995553 on 826,725 rows here and in
`train.py`'s own `verification_2025.csv`.

**Interval with day clusters** (95%): N1 −0.000106 to +0.000261; N2 leads 0 to 4: −0.000198 to +0.000005,
−0.000190 to +0.000034, −0.000217 to +0.000098, −0.000196 to +0.000102, −0.000187 to +0.000147.

**Calibration (ECE, ten bins), old then new:** N1 0.0108, 0.0103. N2 by lead: 0.0072, 0.0073; 0.0093, 0.0092;
0.0117, 0.0117; 0.0136, 0.0135; 0.0160, 0.0161. Mean forecasts move by under 0.0005 everywhere.

**N2 at lead 0 by company** (`-companies.csv`). Seven of nine improve. Southern (+0.000067) and United
Utilities (+0.000120) are slightly worse.

| Company | Rows | Brier old | Brier new | Δ |
|---|---|---|---|---|
| Anglian | 91,615 | 0.02976 | 0.02934 | −0.00042 |
| Northumbrian | 145,635 | 0.03428 | 0.03415 | −0.00013 |
| Severn Trent | 255,135 | 0.03137 | 0.03114 | −0.00024 |
| South West | 108,040 | 0.04716 | 0.04634 | −0.00082 |
| Southern | 55,845 | 0.02829 | 0.02836 | +0.00007 |
| Thames | 74,825 | 0.04114 | 0.04102 | −0.00012 |
| United Utilities | 825,995 | 0.04291 | 0.04303 | +0.00012 |
| Wessex | 100,375 | 0.03633 | 0.03575 | −0.00057 |
| Yorkshire | 281,780 | 0.04334 | 0.04329 | −0.00005 |

**How much moves** (`-moves.csv`, United Utilities 2025). In summer time, 1,815 of 28,142 spill-day labels
(6.4%) and 11,903 of 39,060 cell rain totals (30.5%) differ between UTC and local days. In winter none do,
which checks the code. A smoke test of the harness on 30 overflows, run before the arms, showed the same
kind of counts (8.9% and 29.3%) and nothing else.

**The production refits** on the N1 rows: mean 0.0797 (old arm) and 0.0802 (new arm); mean absolute
difference 0.0072, 99th percentile 0.082.

**My prediction** was |ΔBrier| under 0.2% with B slightly better. Partly wrong: N2 lead 0 moved 0.24%, and
in N1 the new model is slightly worse (+0.18%), not better. Every interval straddles zero, as predicted.

### Reproduction: main's model files are not reproduced

The old arm, `train.py` at `9be5601` on the frozen inputs, does not reproduce the files on main.
- `verification_2025.csv`: "pooled only" matches main's file to every digit (0.04516644980683494). The
  model with site offsets does not: 0.04474 here against 0.04453 on main, a gap of 0.00021, over the
  0.0001 stated.
- The pooled models are the same. On 2,000 random feature rows, main's hold-out and production models and
  the old arm's give identical pooled probabilities, and the same rows per overflow (`site_n`). Only the
  site offsets differ: correlation 0.90 for the hold-out, a largest gap of 1.46 in log odds for production.
- **Cause found (#348, `docs/MODEL-PROVENANCE-2026-10.md`): main's files were fitted at layer-2 recency
  0.25; both arms here used `train.py`'s default, 1.** Recomputed from each file's own layer 1, only 0.25
  matches every stored offset (2,241 of 2,241 in the hold-out, 2,271 of 2,271 in production). My reruns
  at 0.5 and 0.7 (0.04460 and 0.04466) did not try 0.25.
- Scored on the N1 local-day rows (`-checks.json`, "reported"): main's hold-out 0.04451, the old arm's
  0.04472, the new arm's 0.04480. So main's offsets score better than this code reproduces, by more than
  the day-boundary effect. Recency 0.25 explains it; whether the pass holds at 0.25 has not been run.
- The comparison stands, because both arms run the same code on the same inputs and differ only in the day
  boundary. A deployment would move production further than that, though: against the live
  `spill_model.pkl` on the N1 rows, the new refit differs by 0.0097 on average (99th percentile 0.109), of
  which the old-arm rebuild alone is 0.0059 (0.069).

### Runs

- **Code:** old arm `git archive 9be5601`, new arm `git archive 9e6168d`, `src` and `scripts`. Main
  checkout's `.venv`: scikit-learn 1.9.1, pandas 3.0.5, numpy 2.5.3.
- **Times** (25 Oct 2026, GMT, after the radar backfill, one step at a time under the group's
  `heavy-run.lock`): old arm `train.py 2025 --refit-all` 11:31:08 to 11:31:39; new arm 12:22:43 to 12:23:22;
  harness 12:32:23 to 12:34:22. All exit 0. `train.py` peaked at 3.9 GB in each arm. No Open-Meteo call.
- **Models written** (scratch only, not committed): new hold-out SHA-256 beginning `6e5e7aaa00e8263f`; new
  production `bd22f16a10460095` (MD5 `ebcb9653`, the stamp's `spill=` part); old-arm rebuild `5ebe1ec61f09a748`.
- **Frozen inputs**, APFS clones taken 24 Oct 22:5x BST. The rain caches had last changed on 12 and 17 Oct.
  - `data/cache`: 3,337 files in `rain` and 3,926 in `rain_nine` (`archive_*` and `leads_*`). Their
    SHA-256 list (7,263 lines) has SHA-256 `36e222696b52856eb7c282ada739ef8b4e2d811bd410d7be9582b8b534ba2691`.
  - `data/processed`, SHA-256:

        9f8604f9bbea29b993deadaf70ca92ae9a08050aaa717a731c58e8269db45065  annual_returns.parquet
        91cdc58c1d3f7abd538bc7cf85c4270a40ac041b2b206cd3cfeedd9cbe06d84e  dcww_ea_events.parquet
        9d6b7f9d245e8ef7c0158d8c7a76bc67fa7369c9c71263f4d82a2f3ab8e96505  ea_events_anglian_water.parquet
        db27541813d2798672113a73a0703c87cd1309550f13cc697a162dc4ef0cd237  ea_events_northumbrian_water.parquet
        750c3482b16bb320c5b9b655ae3dd3ff96535d8e06397f9a514726889f96e504  ea_events_severn_trent_water.parquet
        b6452a8038c70d96c2b27adf6821c442553542b75dfda5547afd0a5ecc12ce51  ea_events_south_west_water.parquet
        0dc7648a1f1736a2c168749ffaa05c8edf41751fe9df7f0f2de2d5a81b0ea525  ea_events_southern_water.parquet
        4c8afc5a013c943034b9ee916911154eadd826514eb621e6a9fb012478e6ef2e  ea_events_thames_water.parquet
        c245fb7cd382d3f42c4603f7d8b7f98ce6cf119422f13b4ba6b09f56c5809d9c  ea_events_united_utilities.parquet
        26ca5cd0a0060d0e85b1314cea8509cf6037fea4d85ecccafdb68a17c35a02e3  ea_events_wessex_water.parquet
        dca57cf63abca6781224c608b85f509b715b150b57b5aa5f0e901da1c8cbbe78  ea_events_yorkshire_water.parquet
        4ef2c254706f06ce619371a8e8061c1da2a8b5c6f2a39e9b4f5c791c18f31983  edm_events.parquet

### Not done here, on purpose

"What follows" above says a pass puts the new model files in this pull request. On 25 Oct Ethan's
instruction, through the parent session, was to commit the results and the small tables only, not the
models. So `data/processed` is unchanged here, and production is unchanged. The models can be rebuilt
from the recipe and inputs above, and their hashes checked against the ones listed. With the new files in
place, two tests fail that pass on main: `test_live_status_shadow::test_the_published_forecast_and_the_rain_requests_do_not_change`
and `test_methods_csv_prf::test_the_method_page_tables_are_the_committed_test_results`. Both pin the
current model's outputs, so a deployment must update them in the same change.

### Limitations

- One test year (2025) and one training company. N2 judges other companies with a model fitted only on
  United Utilities.
- The margin is non-inferiority at 1%. The test does not show the local-day model is better: every
  interval includes zero.
- Both arms used recency 1; main's models were fitted at 0.25 (#348). The test isolates the day boundary;
  it does not test the model a deployment would replace. Whether the pass holds at 0.25 has not been run.
- N2's longer windows use ERA5-Land, as `verify_leads.py` does, not the forecast.
- Rain-cell totals near midnight depend on where Open-Meteo puts the hour ending at 00:00. The day holds
  the stamps 00:00 to 23:00 in both arms, so this is the same in both and not tested here.

### Dependencies before any deployment

1. **Ethan decides.** A pass is not authorisation to deploy.
2. **Lead calibration B** (`LEAD-CALIBRATION-B-TEST-2026-10.md`). Its live window runs 18 Oct to 14 Nov on
   the model with SHA-256 beginning `faa7917e2be725a9`, read on or after 16 Nov. A new model must not reach
   production before that read.
3. **Refit the lead maps for the new model.** `lead_calibration.json` is refitted with
   `verify_leads.py --model spill_model.pkl`, by whichever recipe B's verdict leaves, so its `model` field
   records the new `trained_on` ("... UK local days ..."). Until then the strict xfail in
   `tests/test_training.py` still fails as it should.
4. **Live-status shadow** (`LIVE-STATUS-SHADOW-TEST-2026-10.md`). It compares its candidates with production
   on target days 25 Oct to 21 Nov (to 5 Dec if extended), read on or after 23 Nov. Its fallback rows take
   production's probability, so swapping the model inside the window would disturb it.
5. **Company calibration** (PR #333, `COMPANY-CALIBRATION-TEST-2026-11.md`). Its offsets are frozen as
   ln((n + 15) / (e + 15)), with e the logged `forecast_raw` of the current model at lead 0, 29 Sep to
   23 Oct. Its window is 26 Oct to 22 Nov, read on or after 25 Nov. A new model changes `forecast_raw`, so
   inside that window it would change what the offsets correct and break the comparison. After it, the
   offsets were fitted for the old model: if adopted, they would need refitting on the new model's
   `forecast_raw` before both run together. The same holds for option B of the upgraded-overflows test,
   which refits layer 2 on or after 2 Dec.
6. **Update the two tests** that pin the current model's outputs (above) in the same change as the model.
7. **E. coli.** Rerun `validate_ecoli.py` and `train_ecoli.py` after the swap; the exposure they read comes
   from the spill model.
8. **The 2027 stamp.** The new model changes `spill=808da63d` to `spill=ebcb9653`, and the refitted map
   changes `cal=`. `src/dipcast/model/` is in `MODEL_PATHS`, so this branch's code is a model change too.
   Allowed only before the freeze tag.
9. **The reproduction gap.** Cause found (#348): main's files were fitted at recency 0.25; both arms here
   used 1. The day-boundary comparison stands. A deployable refit must use recency 0.25, and whether the
   pass holds at 0.25 has not been run.

The earliest date that clears items 2, 4 and 5 is 25 Nov 2026, if the shadow's window is not extended.

---

## Addendum, 25 October 2026: recency

Written 25 Oct 2026, committed as `ec9c297` at 20:01 GMT, and pushed before any result at recency 0.25 is
computed. The statement and the Results above stay exactly as they are.

### The error

Main's model files (`spill_model_holdout_2025.pkl` from `8ac835f`, and `spill_model.pkl`) were fitted with
layer-2 recency 0.25. PR #348 (`docs/MODEL-PROVENANCE-2026-10.md`) shows this by reproducing every stored
site offset exactly from each file's own layer 1 at 0.25, and at no other value tried. Both arms of the
first run used `train.py`'s default, recency 1.0. So the first run compared two models built differently
from production.

### What was already seen

The recency-1.0 results above: **PASS**. N1 ΔBrier +0.000081 (95% interval −0.000078 to +0.000238, limit
0.000447). N2 leads 0 to 4: ΔBrier from −0.000095 to −0.000020, every upper bound inside its limit.

### The corrected comparison

- **Both arms run with `--recency 0.25`**, passed explicitly:
  `scripts/train.py 2025 --refit-all --recency 0.25`. This branch's `train.py` still defaults to 1.0,
  because #348 is not merged.
- **Unchanged from the statement:** the conditions N1 and N2, their rows, the metrics, the margin (1% of the
  old arm's Brier, upper end of the 95% interval), the interval method (ISO-week clusters, 2,000 resamples,
  seed 1), the seeds of the fits, and the harness `scripts/day_boundary_eval.py` at `9e6168d`.
- **The same code:** old arm `git archive 9be5601`, new arm `git archive 9e6168d`.
- **The same frozen inputs:** the first run's `run/cache` copy and processed copies, whose hashes are listed
  in the Results above. Their hashes are checked again before the run, and any difference is reported
  separately.
- **New folders**, so the first run's outputs and models stay as they are: `run/old25`, `run/new25`,
  `run/out25`.
- No retuning, and no recency value other than 0.25.
- The same machine rules: one step at a time under the group's `heavy-run.lock`, ten quiet minutes, at
  least 35% memory free.

### A face check, stated before running

The old arm at 0.25 must reproduce main's `data/processed/spill_model.pkl` and
`spill_model_holdout_2025.pkl`, as tracked at `origin/main` (`b37bfa6`):
- identical layer-1 probabilities on 2,000 random feature rows (seed 0);
- `site_n` equal;
- every site offset within 1e-9.

If it does not, the input differences are reported separately, and the result is not presented as a
comparison with production.

### The verdict

The verdict is read from the 0.25 run. The 1.0 run stays as a record.

### Results at recency 0.25

None yet.
