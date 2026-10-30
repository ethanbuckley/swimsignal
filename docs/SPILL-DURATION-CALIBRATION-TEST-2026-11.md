# Spill duration with a calibration step, judged on January to August 2026: the test, stated before any run

Written 30 October 2026, before the gate below was run and before any 2026 event was downloaded. No 2026 event is on
this machine as this is written (`docs/SPILL-DURATION-DIAGNOSTICS-2026-11.md`, section 3). Committed and pushed before
the gate. Results go below the line at the end. Nothing above that line changes after a result is seen.

Harness: `scripts/spill_duration_calibration_test.py` (`gate`, `run`). Tests:
`tests/test_spill_duration_calibration_test.py`. It reuses PR #459's harness (`scripts/spill_duration_test.py`).

## Approval

Ethan approved the draft in PR #461 (`docs/SPILL-DURATION-DIAGNOSTICS-2026-11.md`, section 4) on 30 October 2026
("Yes, write and run it"), with decision 2 as option (b): United Utilities scored and reported, but left out of
conditions 3 and 4. The draft named one EA download as needed, so that is taken as approved too.

What this file fixes that the draft left open, each decided now:
- **The gate rule is exact:** see "The gate".
- **The fits are made before 2026 is read.** The gate step fits the final C1, the calibrators and B1 on 2024-25 and
  saves them. The 2026 step only predicts and scores.
- **Training issue hours run to 31 December 2025, 00:00,** for both years. #459 trained on 2024 alone.
- **Rain:** ERA5-Land from the shared and nine-company caches, tags 2023 to 2026a.

## Why

PR #459's C1 beat a company × elapsed-time table (B1) by 11.6% on 2025 but failed on reliability. PR #461 found two
faults: a 2024-to-2025 change at Anglian and Southern that B1 shares, and C1 too sharp at 12 to 24 hours. A
calibration step fitted on held-out training predictions can address the second. Neither fault can be fixed on 2025
and then judged on 2025, which has now been looked at several times. So the judge is January to August 2026.

**The question:** with a calibration step fitted on 2024-25 only, are C1's chances that a running spill is still
running 1, 3, 6, 12 and 24 hours on both better than B1's and reliable, on a period no duration model has seen?

## Seen before writing

- PR #459's statement, results and tables (2024 and 2025).
- PR #461's diagnostics on 2025: reliability by company, horizon and elapsed time; the target audit.
- `docs/NINE-COMPANY-MODEL-V2-DATA-CHECK-2026-10.md`: 2026 event counts, overflows, median event lengths and gaps,
  and spill-days by month and company. No 2026 spill duration, and no 2026 forecast for a duration, has been seen.

## Data

- **Events.** EA start/stop files: 2024 and 2025 (`data/processed/ea_events_*.parquet`, as #459), and the EA's 2026
  year-to-date zip, imported with `scripts/import_ea_events.py --years 2026` into a scratch `DIPCAST_ROOT`. Its name,
  size and SHA-256 are recorded below the line. The window is fixed now: if the zip now runs past August, nothing
  after 31 August 2026 is scored or read for a result.
- **Overflows.** Those with a position and the year before's return (`training.site_years`); 2026 rows use the 2025
  return. There is no 2026 return, so a 2026 overflow is kept when the 2026 file has an event for it.
- **Rain.** ERA5-Land hourly, from `data/cache/rain` and `data/cache/rain_nine`, tags 2023, 2023dec, 2024, 2025, 2026
  and 2026a. No Open-Meteo calls. The share of 2026 rows with missing past rain is reported.

## Rows, labels and inputs

As PR #459, with one change from PR #461:
- **Spills:** each overflow's events joined when they overlap or start less than 1 hour after the last ended.
- **Rows:** whole UTC hours *t* at which a spill began less than 72 hours before **and an EA event is running at
  *t*** (a monitor would show "discharging"). Training: *t* from 1 January 2024 to 30 December 2025 (before 31
  December 00:00). Scoring: *t* from 1 January to 30 August 2026 (before 31 August 00:00), so every label up to 24 h
  ahead lies inside the file.
- **Label:** the same spill still running at *t* + h, for h = 1, 3, 6, 12, 24.
- **Elapsed time:** from the spill's first event; on these rows that uses only events that began before *t*.
- **C1's inputs:** PR #459's list (`spill_duration_test.C1`), unchanged.

## Predictors

All fitted on the 2024-25 rows only, before 2026 is read:
- **B1:** the share still running at each horizon per company and elapsed bin.
- **C1 raw:** PR #459's model and settings, fitted on every 2024-25 row.
- **C1-cal, the candidate:** C1 raw's forecasts passed through isotonic regressions, one per company and horizon,
  then forced not to rise with the horizon. The regressions are fitted on out-of-fold forecasts: the eight calendar
  quarters of 2024-25, C1 fitted on seven and predicting the eighth (`quarter_fold`, `fit_calibrators`).

## The gate

Before anything is downloaded, on the out-of-fold forecasts of 2024-25 only: at the 24-hour horizon, all nine
together, rows forecast at 0.8 or more must come true at least **0.03** less often than forecast (`gate`). That is
the over-sharpness #461 saw on 2025, which a calibration fitted on these forecasts could remove.

- **If the gate fails,** the 2026 file is not downloaded and nothing is scored. The record says calibration fitted on
  these forecasts could not fix what failed.
- The 0.03 and the 0.8 are judgements, fixed before the out-of-fold forecasts exist. On 2025, the gap at 0.8 and above
  was about 0.1 to 0.18 (#461).

## Scoring, on 2026

PR #459's measures: integrated Brier (the mean over the five horizons), Brier and ECE per horizon, per company and for
all nine, with 95% intervals from a cluster bootstrap by ISO week (2,000 resamples, `default_rng(0)`, one set of draws
for every comparison).

**Reported, not conditions:** C1 raw's scores and checks; each predictor's signed gap (mean forecast minus observed)
per company and horizon; the Brier against "a monitor reports a discharge at +h"; C1-cal with elapsed time as hourly
polls would see it (`poll_elapsed`), and the share of rows where that is shorter than the true elapsed time.

## Conditions

**C1-cal's chances are better and reliable** if all of these hold:

1. **A gain.** All nine together: (a) C1-cal's integrated Brier is below B1's, with the interval of the difference
   wholly below zero; (b) the gain is at least 2% of B1's integrated Brier.
2. **No horizon clearly worse.** All nine: at no horizon does the interval lie wholly above zero.
3. **No company clearly worse,** at each of the eight companies other than United Utilities.
4. **Reliability.** At each of the eight and each horizon, C1-cal's ECE is no higher than B1's, or it is at most 0.02.
5. **Not worse on new spills.** All nine, rows where the spill began under 3 hours before: the interval does not lie
   wholly above zero.

**United Utilities** is scored, in the all-nine figures of conditions 1, 2 and 5, and reported on its own with every
measure. It is left out of conditions 3 and 4 because it changed how it records events in 2026 (median gap between
events 102 minutes, against 26 to 28 in 2024-25), which changes what counts as one spill there. That was seen from
event counts and gaps only.

## What a pass means, and what a fail means

- **A pass** says the duration chances held on a fresh period. It deploys nothing. It allows a proposal to show a
  chance beside the conditional clearing time, which needs its own wording test (`docs/CLEAR-TIME-WORDING-2026-11.md`)
  and a check that live polls can supply elapsed time (the poll-elapsed figures below the line are the first look).
- **A fail** is the record. Duration is not pursued again without a new input or a new reason.
- Neither result says how long the water takes to recover. That needs water samples.

## Running it

- `gate` reads only 2024-25. About 30 minutes (nine C1 fits). It writes `-gate.json` and `-gate-reliability.csv`
  beside this file and the fits to `data/processed/spill_duration/calibration_fits.pkl` (not committed).
- Then, only if the gate passed: the EA download into a scratch root, and `EVENTS_2026=<scratch>/data/processed
  uv run python scripts/spill_duration_calibration_test.py run`, once. It refuses to run if the gate failed or the
  training rows differ from the gate's. It writes `-scores.csv`, `-reliability.csv`, `-checks.json`.
- No Open-Meteo calls. Wait for `heavy-run.lock` if another session holds it.

---

## Results

**Gate run.** 30 October 2026, from harness commit 1f636fcd (statement pushed in the same commit, before the run), on
main checkout data, no network, no Open-Meteo calls. About 50 minutes (folds 2 and 3 ran slowly, inferred to be
other load on the machine). Exit 0. Files: `-gate.json`, `-gate-reliability.csv`. 4,038,032 training rows running at
the issue hour, of 4,325,636 issue hours.

### Verdict: the gate fails. Nothing was downloaded and nothing was scored on 2026

At 24 hours, all nine, the 134,299 out-of-fold rows forecast at 0.8 or more came true **0.027** less often than
forecast. The gate needed 0.03. By the statement, the 2026 file is not downloaded, the saved fits are not used, and
`run` refuses to start. The threshold is not changed after the fact.

### What the out-of-fold forecasts show (seen after the gate; a description, not a test)

- **C1 forecasts too low, at every company and every horizon.** Mean forecast minus observed share, all nine: −0.016
  at 1 h, −0.027 at 3 h, −0.033 at 6 h, −0.038 at 12 h, −0.042 at 24 h. By company at 24 h, from −0.021 (United
  Utilities) to −0.062 (Anglian, Wessex). ECE at 24 h: 0.044 for all nine, 0.029 to 0.064 by company.
- **The shortfall sits in the low and middle forecasts, not at the top.** At 24 h, all nine: forecasts of 0.05 came
  true 7.1% of the time, 0.15 came true 21.2%, 0.25 came true 32.3%; above 0.8 the gap is small (0.84 against 0.83,
  0.92 against 0.86).
- **So the fault #461 saw on 2025 (too sharp at the top) does not recur out of fold within 2024-25.** What does recur
  is a general under-forecast of how long spills go on, which differs again from 2025's pattern (too high at
  Anglian, Southern and Thames). *Inferred, not checked:* holding out a whole calendar quarter removes that season's
  storms from training, and the model then under-rates persistence in it.
- The in-sample ECE after calibration (0.0002 in `-gate.json`) is fitted and scored on the same rows. It says nothing
  about how calibration would do on new data.

### What this means

- **Nothing is adopted, and nothing further runs under this statement.** The page's conditional clearing time stays
  as it is; `docs/CLEAR-TIME-WORDING-2026-11.md` is unaffected, since it needs no model.
- The statement said a failed gate means calibration fitted on these forecasts could not fix what failed. That is
  true of the fault it tested. The out-of-fold forecasts are miscalibrated in another way, which a calibration step
  might address. Testing that now would mean choosing a new gate after seeing these numbers, so it needs a new reason
  and a new statement, and should not reuse this gate's figures to set its rule.
- The January to August 2026 duration figures are still unseen. They remain a fresh period for any later attempt.

### Stage reached, runtime and audit files (added after a review of 30 October 2026; nothing above changed)

**Stage reached:** the gate, completed and failed. A status review written while the gate was at fold 3 said the
download and the one 2026 score could proceed as written. As written, they follow only a passed gate, so neither was
done. No 2026 event file exists on this machine; the scratch root prepared for it is empty.

**Runtime.** The gate's Python process ran from about 19:03 to 19:58 UTC and exited 0. Fold times from its log:
fold 0 161 s, fold 1 168 s, fold 2 594 s, fold 3 1,205 s, folds 4 to 7 144 to 170 s each, then the final fit.
*Inferred:* folds 2 and 3 were slowed by other load on the machine; nothing failed. **One real fault, in the waiting,
not the run:** four shells waiting for the gate used `pgrep -f` with a pattern that their own command lines matched,
so they would never have ended. They were found after the gate had exited (no `spill_duration` Python process left)
and stopped by PID (74920, 76361, 76563, 77834). The training process was never signalled.

**Spills split across quarter folds** (`overlap` step, 2024-25 events only, no model; `-fold-overlap.json`). The
folds assign rows by issue time, so a spill running over a quarter boundary has rows on both sides: a held-out row
can come from a spill whose other hours were in training. On the gate's exact rows (the row hash matches):

| | Count | Share |
|---|---|---|
| Spills with rows in two or more quarters | 2,987 of 536,992 | 0.56% |
| Rows in those spills | 82,150 of 4,038,032 | 2.0% |
| By held-out quarter | from 0.0% (Q4 2025) to 6.1% (Q3 2024) | |

This is a limitation of the gate. *Inferred:* a model that saw part of a spill should predict its other hours a
little better, so the out-of-fold forecasts may be slightly more accurate than truly held-out ones. Whether it moved
the gate's 0.027 is not measured: that would need refitting with folds grouped by spill, which would be rerunning
the gate after a fail, and is not done. Nothing about the verdict changes. The independent test would have been 2026.

**Kept for audit:**
- `-gate-reliability.csv` (committed): mean forecast and observed share per company, horizon and ten-bin, so every
  signed gap above can be recomputed. `-gate.json`, `-fold-overlap.json` (committed).
- `data/processed/spill_duration/calibration_fits.pkl` in the main checkout, not committed (6.0 MB, SHA-256
  `79ebf550b199403b62c340dba976d2ab8ff4f3fec937f1270443141f81319317`): the final C1, the 45 calibrators, B1 and the
  gate's figures. Unused.
- `data/processed/spill_duration/predictions_2025.parquet`, not committed (76.5 MB, SHA-256
  `86ff3447801659fee0b17f8f738a671ff242236e9b8178b203feb628af05ae74`): PR #461's 2025 predictions with labels.
- **Not kept:** the gate's row-level out-of-fold forecasts. The gate saved only their summaries. They can be
  regenerated exactly (fixed seeds, the row hash in `-gate.json`) in about 25 minutes if an audit needs them; doing so
  would not change the verdict.
