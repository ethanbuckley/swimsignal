# The overflow's own spill status as an input to the spill model: the test, stated before any run

Written 18 October 2026, before any candidate was trained and before any 2025 row was scored with a status input.
It is committed and pushed before the first training run. Results go below the line at the end. Nothing above that
line changes after a result is seen.

## Why

The neural challenger (PR #239, 18 Oct 2026) lost to the boosted model: 2025 Brier 0.0372 against 0.0362. Reviewing
why, the conclusion was that better inputs are a better bet than a new architecture.
- **Rain-forecast error dominates.** On #239's lead rows the boosted model scored 0.0378 at lead 0 and 0.0492 at
  lead 4.
- **The model has no input for the overflow's current state.** Today's inputs are ten rain summaries, two season
  terms and three fixed figures from the annual return (`features.ALL_FEATURES`). Nothing tells the model that an
  overflow is already spilling. Groundwater-fed overflows can spill for weeks, and rain totals cannot see that.

This test adds one idea: the overflow's own recent spill status, known at the time the forecast is issued. No other
input is added.

## Seen before writing

- **D2's and #239's results.** Every 2025 score of the baseline below is already published in
  `docs/NINE-COMPANY-MODEL-TEST-2026-10.md` and in #239's results.
- **How status persists in 2024.** 2024 only: the 2024 file's events and the kept 2024 overflow-days, 4,976,868 of
  them, which are D2's training rows. Tables: `-persistence-2024.csv` and `-spells-2024.csv`, made by
  `scripts/live_status_test.py describe` (log not committed). Measured:

  | Status at issue (all nine, 2024) | Share of rows, lead 0 | Spill rate, lead 0 | Lead 1 | Lead 4 |
  |---|---|---|---|---|
  | All rows | 100% | 0.087 | 0.087 | 0.087 |
  | Spilling at issue | 2.8% | 1.000 | 0.721 | 0.527 |
  | Not spilling at issue | 97.2% | 0.061 | 0.068 | 0.071 |
  | 7 spill-days in the 7 before issue | 1.3% | 0.889 | 0.830 | 0.724 |
  | Dry start: not spilling, 0 spill-days in the 7 before | 72.1% | 0.028 | 0.035 | 0.042 |

  | Company (2024) | Spill-days running at 00:00 UTC | Spill-days in runs of 7+ days | In runs of 30+ days |
  |---|---|---|---|
  | Anglian | 43% | 38% | 11% |
  | Northumbrian | 23% | 9% | 2% |
  | Severn Trent | 29% | 21% | 5% |
  | South West | 38% | 39% | 14% |
  | Southern | 42% | 30% | 12% |
  | Thames | 53% | 47% | 19% |
  | United Utilities | 23% | 15% | 2% |
  | Wessex | 38% | 28% | 8% |
  | Yorkshire | 25% | 18% | 6% |
  | All nine | 32% | 25% | 8% |

  "Running at 00:00 UTC" means an event ran through the midnight that starts the day, so at lead 0 the label was
  already certain. *Inferred, not checked:* the long runs at Thames, South West, Southern and Anglian include the
  groundwater-fed overflows; Thames's merged events (D2, step 1) lengthen its runs too.
- **The files' new-year convention.** Counts of events that start or end exactly at 00:00 on 1 January, in both
  files, and nothing else about 2025:
  - 64 to 408 events per company start at exactly 2024-01-01 00:00 and none starts earlier. *Inferred:* the files
    cut an event running over the new year at 00:00 on 1 January, so "spilling at 00:00 on 1 January 2024" is known.
  - At the 2024/25 new year the companies differ. Some cut the event in both files (Northumbrian: 105 end and 109
    start at 00:00). Some start it again at 00:00 in the 2025 file while the 2024 file's event runs on into 2025
    (United Utilities: 1,007 start, 0 end). Overlapping events are therefore merged before status is computed.
- **The live state** (the `state` release, 18 Oct 2026 11:36 UTC), for the feasibility section below.

No candidate was trained and nothing from 2025 was scored with a status input.

## The candidate (one per lead, fixed now)

- **Three status inputs**, for overflow *i*, target day *d* and lead *k*. The issue time is 00:00 UTC of day
  *d*−*k*. All come from the EA start/stop events of both files, with each overflow's overlapping events merged
  first:
  - `spilling_at_issue`: 1 if an event runs at the issue time (start ≤ 00:00 < stop), else 0.
  - `spill_hours_24h`: hours spilled in the 24 hours before the issue time, which is UTC day *d*−*k*−1. At most 24.
  - `spill_days_7d`: spill-days among days *d*−*k*−7 to *d*−*k*−1, from `features.spill_days`, the label's own rule.
    0 to 7.
- **Why 00:00 UTC of day *d*−*k*, and not the build hour.**
  1. **Nothing of the target day leaks in at lead 0.** With the build hour, a spill from 02:00 to 03:00 seen by a
     14:00 build makes day *d* a spill-day for certain. Only a spill still running at midnight does that here.
  2. **It is fixed.** The site builds at irregular times (GitHub runs the schedule a few times a day), so a build
     hour would make the test depend on a timetable.
  3. **It is conservative.** Production issues a day's forecast at the build hour, which is later. So production's
     status is fresher than the test's, apart from one case: in British Summer Time, a build between 23:00 and
     00:00 UTC calls the next UTC day "today", and its status is at most an hour older than the test's.
  4. **At lead 0 the build-hour status already reaches the page.** The hold-only "right now" rule counts every
     spill seen at the build (feasibility, below).

  The rain inputs are unchanged. The lead-*k* rain for an hour of day *d* is the forecast issued *k* days before
  that hour, so it is never older than the status.
- **Unknown status.** An input is missing (NaN) where any day it reads falls in a year in which the overflow's status
  is not known. Known means: an event in that year's file, or 0 spills in that year's return, and EDM operation not
  under 50% (`training.site_years`' rule, without its need for a position in the year before). Days before
  1 January 2024 are not known. So 2024 rows in the first days of January have missing inputs, and so do 2025 rows in
  early January whose overflow is not covered in 2024. The boosted model takes a missing value as it is
  (`HistGradientBoostingClassifier`). The counts are reported.
- **Monotone.** Each status input may only raise the probability, as each rain input may (`features.MONOTONE`).
- **Rows.** Exactly D2's rows, built by D2's code (`train._frame`): 4,976,868 site-days in 2024 and 5,077,150 in
  2025. The script stops if it gets other counts, or a subsample other than D2's 1,569,401 rows.
- **Fit.** One candidate per lead *k* from 0 to 4, because the status is a different age at each lead. Each is fitted
  on the 2024 rows with lead *k*'s status inputs and D2's settings: `fit_pooled` with `neg_frac` 0.25 and seed 0,
  then `fit_site_offsets` with prior strength 15 and recency 1 on the candidate's own 2024 predictions. **Nothing is
  tuned on 2025.** If any setting above is changed after a 2025 score is seen, the run is void and the change is
  recorded below the line.
- **Production, if it ever gets there,** would run lead *k*'s candidate for the day *k* days ahead.

## The baseline

D2's candidate, `spill_model_nine_2024.pkl`, SHA-256 `1603678923ccdd15…`, kept off-repo in
`~/Documents/GitHub/swimsignal-private/baselines/`. It is the same model with the same rows, settings and layer 2,
without the status inputs. Two checks of the code:
- on the 2025 rows with ERA5-Land rain it must give D2's 0.0362 for the nine together;
- on the lead rows it must give #239's boosted Brier at each lead: 0.03784, 0.04153, 0.04376, 0.04578, 0.04919.

## Verification on 2025

Every predictor is scored on the same rows, against the label "the overflow spilled that day".

**ERA5-Land rain.** D2's 2025 rows. For each lead's candidate, per company and for the nine together: rows, base
rate, Brier, AUC, ECE (D2's definition) and a 10-bin reliability table. Rain is the reanalysis, so only the status
age differs between leads.

**Forecast rain.** #239's lead rows and rule, with its code copied into `scripts/live_status_test.py`:
- 2025 site-days in cells with archived lead forecasts;
- for lead *k*, days *d*, *d*−1 and *d*−2 come from the forecasts issued *k*, *k*−1 and *k*−2 days ahead (floored
  at 0), and every earlier day from ERA5-Land;
- the ten rain features come from that one series, for both models;
- a row is kept when its 72-hour forecast window has at least 65 finite hours and its day-*d* total is known;
- a missing rain feature becomes 0; there is no isotonic map.

The status inputs are those of lead *k*. Brier and AUC are reported per lead, overall and per company.

**Uncertainty.** #239's method. Paired differences in Brier (candidate minus baseline) get 95% intervals from a
cluster bootstrap by ISO calendar week of the UTC day: 2,000 resamples from `numpy.random.default_rng(0)`, every row
of a week drawn together, and one set of draws for every company, lead and subset.

**Reported, not conditions:**
- layer 1 alone, for both models;
- the candidate with every status input missing: what a forecast would be if a feed went down;
- the difference on rows spilling at issue, and on rows not spilling at issue. At lead 0, an overflow spilling at
  00:00 UTC of day *d* has spilled on day *d* by the label's definition, so part of any lead-0 gain is given away by
  the definition (32% of 2024's spill-days were of that kind). The rows not spilling at issue show the rest.
  `spill_days` also counts the day an event ends at exactly 00:00, so the overlap is a little larger than that share.

## Conditions, lead by lead

At lead *k*, **the status input helps** if all five hold for lead *k*'s candidate:

1. **A gain with forecast rain.** On the lead rows, all nine together, the candidate's Brier is lower than the
   baseline's, and the 95% interval of the difference lies wholly below zero.
2. **A gain with ERA5-Land rain.** On the 2025 rows, all nine together, the same.
3. **No company clearly worse.** On the 2025 rows with ERA5-Land rain, at no company is the candidate's Brier higher
   with the 95% interval of the difference lying wholly above zero.
4. **Reliability.** On the same rows, at each company, the candidate's ECE is no higher than the baseline's, or it is
   at most 0.02.
5. **Not worse at a dry start.** On the 2025 rows with ERA5-Land rain whose overflow was not spilling at issue and
   had no spill-day in the 7 days before, the 95% interval of the difference does not lie wholly above zero. These
   are the rows where a storm starts a spill. A model that leaned on persistence and stopped answering to the rain
   would lose here.

## What a pass means, and what a fail means

- **2025 has already judged two candidates.** D2's candidate was chosen against the hold-out on 2025 (17 Oct), and
  the neural challenger was judged against D2 on 2025 (18 Oct). Each look at 2025 is a chance to fit its storms.
  **So a pass here deploys nothing.** It earns a confirmation on 2026 data, stated before it runs: either live 2026
  data with the status computed from SwimSignal's own polls, as production would compute it, or the EA 2026
  start/stop files once all nine companies' files are out. Nothing deploys before that confirmation, and the
  production change is Ethan's call.
- **A fail at every lead** is the record. The input is not pursued again without a new reason.
- Any description of persistence below the line uses 2024 only. 2025 is used for the stated scores and nothing else.

## Production feasibility (checked before the run)

**Do the live feeds give current status for all nine companies? Yes, for nearly every overflow, with gaps.**
`config.LIVE_FEEDS` reads all nine. Measured from the `state` release of 18 Oct 2026:

| Company | In the feed | Status known (0/1) and current, 18 Oct 11:29 UTC poll | Polls with the feed current (≤ 6 h), 28 Sep to 18 Oct |
|---|---|---|---|
| Anglian | 1,438 | 96.0% | 99.2% |
| Northumbrian | 1,575 | 97.7% | 96.0% |
| Severn Trent | 2,416 | 99.6% | 99.2% |
| South West | 1,342 | 96.7% | 59.9% |
| Southern | 996 | 99.9% | 87.7% |
| Thames | 573 | 94.8% | 99.2% |
| United Utilities | 2,255 | 98.9% | 99.2% |
| Wessex | 1,427 | 98.4% | 99.2% |
| Yorkshire | 2,177 | 98.5% | 98.8% |

- "Current" is `ingest.live.data_states`' `live` state. The rest are offline monitors (-1) or records or feeds that
  stopped updating.
- South West Water's poll log has no feed age at 40% of polls, and Southern Water stamps a record only when it
  changes, so a quiet Southern feed reads as stale (`ingest.live`, `feed_on_change`).
- There were 252 poll runs in 21 days, 12 a day. The median gap was 53 minutes and the longest 7.7 hours.

**How production would compute the three inputs:**
- `spilling_at_issue`: status 1 at the build's poll.
- `spill_days_7d`: spill-days from `live_history.parquet` by `forecast_log.observed_spill_days`, the method the live
  scores use. PR #253 measured that this method finds 99.7% of EDM spill-days over a year and 98.9% in its autumn
  window, and adds none.
- `spill_hours_24h`: from the history's status starts and latest event times. An event that starts and ends between
  two polls, and is not the latest at the next poll, is lost. *Inferred, not measured:* hours are under-counted
  most where events are short and close together (Wessex's median event is 2 minutes, Anglian's 6; D2, step 1).

So the model would be trained on the EA's events and run on SwimSignal's polls. That difference is not tested here.
The 2026 confirmation must use poll-derived status to measure it.

**Unknown status in production.** Offline monitors, stale or failed feeds, and overflows missing from a feed give no
status. The candidate learns what to do with a missing input from few rows: only early January has them. If status
is ever deployed, the design would use the baseline for any overflow whose status inputs are missing. That rule is
not tested here. The candidate's score with every input missing is reported to show what happens without it.

**How this meets the hold-only "right now" rule at lead 0.**
- Right now (PR #105, hold-only by Ethan's choice on 4 Oct 2026) counts each spill seen at the build at full weight
  from its start until its water has passed the spot, then for less over 48 hours (`transport.live_now_risk`).
- The page lifts today's level to right now's when right now is higher (`levels.js`, `risk`, the `lift` line).
- So at lead 0, production already uses the build-hour status for overflows discharging or stopped lately. A status
  input would raise today's forecast for the same overflows. The page takes the higher of the two levels, not a sum,
  so the two do not add up to double counting.
- What a status input adds at lead 0 that right now cannot: a higher risk for overflows that spilled lately and may
  start again today, and a lower one for overflows dry for a week. Right now says nothing about spills that have not
  started.
- At leads 1 to 4 nothing in production uses the status today.
- *Inferred, not checked:* through travel time (`combine_daily`), a day-0 probability near 1 for an overflow already
  spilling would also raise tomorrow's level at spots far downstream. Right now holds that spill too, but right now
  never lifts tomorrow.

## Order of work

1. Commit and push this statement and `scripts/live_status_test.py` before any training run. Open a draft PR against
   main.
2. Check that no other evaluation or build runs on this Mac (`pgrep -fl`, never `pkill`).
3. `uv run python scripts/live_status_test.py run`: fits the five candidates on 2024, scores 2025 with ERA5-Land rain
   and then with forecast rain, checks conditions 1 to 5 at each lead and writes the tables beside this file.
4. Write the results below the line. The five candidates go off-repo to
   `swimsignal-private/baselines/live_status/`.

---

## Results
