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

Run 18 October 2026 on this Mac, from commit `5c59059`, which holds the statement above. The script did not change
after that commit. Nothing else was running. The run took 8.4 minutes. The log is
`logs/live_status_run_2026-10-18.log` in the worktree (not committed). The tables are committed beside this file:
- `-scores.csv`: every predictor, company and lead, ERA5-Land rain
- `-differences.csv`: candidate minus baseline, with the bootstrap intervals
- `-subsets.csv`: rows spilling at issue, not spilling, dry starts, and rows with a missing input
- `-leads.csv`: forecast rain, per lead, for the nine together and per company
- `-reliability.csv`
- `-checks.json`: row counts, missing inputs, the conditions

### Checks of the code

All measured.
- **Rows.** 4,976,868 training and 5,077,150 test site-days, and a subsample of 1,569,401: D2's counts.
- **The baseline reproduces.** 0.03615 on the 2025 rows with ERA5-Land rain (D2: 0.0362). On the lead rows,
  0.03784, 0.04153, 0.04376, 0.04578 and 0.04919: #239's table to five decimals.
- **Lead rows.** 1,939,245 site-days for 5,313 overflows in 544 cells, with 1,928,619 scored at each lead, as in #239.
- **Status.** 14,147 overflows and 2,756,717 events after merging.
- **Missing inputs.** In the training rows, from 0 (`spilling_at_issue`, lead 0) to 149,578 (`spill_days_7d`,
  lead 4). In the 2025 rows, from 0 to 3,080.
- **Fit.** Each candidate ran the full 300 iterations, in about 30 seconds.
- **Before the run,** the status code was checked on hand-made events: 8 rows at leads 0 and 1, 48 values, each
  worked out by hand. All matched. That check is not committed.

The five candidates are kept off-repo in `swimsignal-private/baselines/live_status/`. Their SHA-256 begins
`deb5e1e5ee64`, `e0756b1e9748`, `ed5bb2b9a39e`, `5180de7086c6` and `ecc835c96d70` (leads 0 to 4).

### Verification on 2025, ERA5-Land rain

All nine companies, 5,077,150 rows, base rate 0.057. The baseline is the same at every lead.

| Lead | Candidate | Baseline | Difference [95%] | Change | AUC candidate / baseline | ECE candidate / baseline |
|---|---|---|---|---|---|---|
| 0 | **0.0265** | 0.0362 | −0.0096 [−0.0125, −0.0070] | −27% | 0.960 / 0.929 | 0.003 / 0.008 |
| 1 | **0.0315** | 0.0362 | −0.0047 [−0.0062, −0.0033] | −13% | 0.950 / 0.929 | 0.004 / 0.008 |
| 2 | **0.0323** | 0.0362 | −0.0039 [−0.0053, −0.0025] | −11% | 0.946 / 0.929 | 0.003 / 0.008 |
| 3 | **0.0328** | 0.0362 | −0.0034 [−0.0046, −0.0021] | −9% | 0.945 / 0.929 | 0.003 / 0.008 |
| 4 | **0.0332** | 0.0362 | −0.0030 [−0.0041, −0.0019] | −8% | 0.943 / 0.929 | 0.003 / 0.008 |

Per company: the difference in Brier, candidate minus baseline, with its 95% interval.

| Company | Lead 0 | Lead 1 | Lead 2 | Lead 3 | Lead 4 |
|---|---|---|---|---|---|
| Anglian | −0.0087 [−0.0115, −0.0060] | −0.0047 [−0.0062, −0.0034] | −0.0040 [−0.0054, −0.0027] | −0.0035 [−0.0047, −0.0022] | −0.0033 [−0.0045, −0.0020] |
| Northumbrian | −0.0061 [−0.0088, −0.0037] | −0.0014 [−0.0029, −0.0001] | −0.0013 [−0.0027, +0.0001] | −0.0019 [−0.0033, −0.0006] | −0.0023 [−0.0039, −0.0009] |
| Severn Trent | −0.0071 [−0.0102, −0.0046] | −0.0035 [−0.0051, −0.0019] | −0.0031 [−0.0050, −0.0014] | −0.0025 [−0.0042, −0.0009] | −0.0022 [−0.0037, −0.0007] |
| South West | −0.0184 [−0.0230, −0.0140] | −0.0110 [−0.0140, −0.0082] | −0.0087 [−0.0114, −0.0061] | −0.0069 [−0.0094, −0.0045] | −0.0054 [−0.0077, −0.0032] |
| Southern | −0.0076 [−0.0103, −0.0051] | −0.0031 [−0.0045, −0.0018] | −0.0024 [−0.0035, −0.0012] | −0.0021 [−0.0030, −0.0011] | −0.0017 [−0.0027, −0.0005] |
| Thames | −0.0153 [−0.0202, −0.0108] | −0.0092 [−0.0121, −0.0066] | −0.0074 [−0.0100, −0.0048] | −0.0057 [−0.0084, −0.0026] | −0.0051 [−0.0077, −0.0023] |
| United Utilities | −0.0095 [−0.0123, −0.0069] | −0.0044 [−0.0062, −0.0026] | −0.0035 [−0.0054, −0.0018] | −0.0038 [−0.0054, −0.0023] | −0.0032 [−0.0048, −0.0018] |
| Wessex | −0.0100 [−0.0137, −0.0067] | −0.0052 [−0.0070, −0.0035] | −0.0041 [−0.0060, −0.0022] | −0.0024 [−0.0042, −0.0006] | −0.0021 [−0.0039, −0.0004] |
| Yorkshire | −0.0094 [−0.0127, −0.0063] | −0.0039 [−0.0059, −0.0020] | −0.0035 [−0.0055, −0.0017] | −0.0032 [−0.0051, −0.0013] | −0.0029 [−0.0046, −0.0013] |

At lead 1, the first lead where the label's definition gives nothing away, Brier candidate / baseline: Anglian
0.0225 / 0.0272, Northumbrian 0.0318 / 0.0332, Severn Trent 0.0249 / 0.0284, South West 0.0409 / 0.0519, Southern
0.0246 / 0.0277, Thames 0.0211 / 0.0303, United Utilities 0.0413 / 0.0456, Wessex 0.0274 / 0.0326, Yorkshire
0.0364 / 0.0403.

**Reliability.** The candidate's ECE is lower than the baseline's at seven companies and every lead. Thames, where D2
failed its reliability condition, goes from 0.024 to 0.002-0.003. At two companies it is higher, though under 0.02:
- Northumbrian: 0.004-0.005 against 0.003.
- Yorkshire: 0.0064 at lead 0, rising to 0.0105 at lead 4, against 0.0052.

**Subsets** (all nine; difference with its 95% interval):

| Lead | Not spilling at issue | Spilling at issue | Dry start (condition 5) |
|---|---|---|---|
| 0 | −0.0051 [−0.0066, −0.0038] | −0.307 [−0.368, −0.257] | −0.0039 [−0.0050, −0.0028] |
| 1 | −0.0037 [−0.0047, −0.0026] | −0.073 [−0.112, −0.036] | −0.0028 [−0.0038, −0.0019] |
| 2 | −0.0032 [−0.0042, −0.0020] | −0.052 [−0.082, −0.025] | −0.0026 [−0.0035, −0.0016] |
| 3 | −0.0027 [−0.0036, −0.0016] | −0.050 [−0.079, −0.026] | −0.0023 [−0.0031, −0.0014] |
| 4 | −0.0024 [−0.0033, −0.0015] | −0.041 [−0.061, −0.023] | −0.0020 [−0.0028, −0.0011] |

- About 76,000 rows (1.5%) were spilling at issue at each lead. At lead 0 their label is certain, and the candidate
  gives them a Brier of 0.00000 against the baseline's 0.307.
- The dry-start rows are 4.08 million (80%), base rate 0.020 at lead 0 and 0.031 at lead 4. The candidate's AUC
  there is 0.934 at lead 0 and 0.933 at lead 4, against the baseline's 0.910 and 0.924.
- 1,960 to 3,080 rows had a missing input, all in the first two ISO weeks of 2025. Their intervals cannot be
  computed. About one draw in eight holds neither week ((51/53)^53, from 53 weeks), so its mean is 0/0, and a
  percentile over draws with a missing value is missing. The script's `RuntimeWarning` comes from this. Their Brier
  differences are −0.039 to −0.005.

### Verification on 2025, forecast rain

All nine companies, 1,928,619 rows at each lead, base rate 0.063.

| Lead | Candidate | Baseline | Difference [95%] | Change | AUC candidate / baseline |
|---|---|---|---|---|---|
| 0 | **0.02868** | 0.03784 | −0.0092 [−0.0118, −0.0067] | −24% | 0.961 / 0.932 |
| 1 | **0.03706** | 0.04153 | −0.0045 [−0.0059, −0.0031] | −11% | 0.933 / 0.911 |
| 2 | **0.03965** | 0.04376 | −0.0041 [−0.0056, −0.0026] | −9% | 0.926 / 0.907 |
| 3 | **0.04187** | 0.04578 | −0.0039 [−0.0054, −0.0023] | −9% | 0.910 / 0.890 |
| 4 | **0.04510** | 0.04919 | −0.0041 [−0.0058, −0.0024] | −8% | 0.897 / 0.879 |

Per company, Brier candidate / baseline. A star marks an interval of the difference that reaches above zero (5 of
45). No interval lies wholly above zero.

| Company | Rows | Lead 0 | Lead 1 | Lead 2 | Lead 3 | Lead 4 |
|---|---|---|---|---|---|---|
| Anglian | 91,113 | 0.0197 / 0.0283 | 0.0251 / 0.0293 | 0.0261 / 0.0295 | 0.0266 / 0.0297 | 0.0285 / 0.0317 |
| Northumbrian | 144,837 | 0.0256 / 0.0313 | 0.0310 / 0.0332 | 0.0356 / 0.0369 | 0.0358 / 0.0373 * | 0.0401 / 0.0423 |
| Severn Trent | 253,737 | 0.0231 / 0.0291 | 0.0299 / 0.0320 | 0.0306 / 0.0329 | 0.0321 / 0.0342 | 0.0336 / 0.0355 |
| South West | 107,448 | 0.0295 / 0.0423 | 0.0387 / 0.0453 | 0.0432 / 0.0484 | 0.0477 / 0.0501 * | 0.0506 / 0.0527 * |
| Southern | 55,539 | 0.0197 / 0.0264 | 0.0276 / 0.0295 | 0.0297 / 0.0310 | 0.0312 / 0.0320 * | 0.0340 / 0.0345 * |
| Thames | 74,415 | 0.0153 / 0.0370 | 0.0257 / 0.0392 | 0.0289 / 0.0393 | 0.0338 / 0.0426 | 0.0357 / 0.0436 |
| United Utilities | 821,469 | 0.0339 / 0.0429 | 0.0432 / 0.0478 | 0.0459 / 0.0503 | 0.0483 / 0.0534 | 0.0525 / 0.0580 |
| Wessex | 99,825 | 0.0223 / 0.0333 | 0.0294 / 0.0359 | 0.0324 / 0.0377 | 0.0348 / 0.0378 | 0.0371 / 0.0404 |
| Yorkshire | 280,236 | 0.0304 / 0.0397 | 0.0396 / 0.0437 | 0.0422 / 0.0465 | 0.0445 / 0.0483 | 0.0471 / 0.0511 |

The candidate's Brier is lower at every company and every lead.

### The conditions

| Condition | Lead 0 | Lead 1 | Lead 2 | Lead 3 | Lead 4 |
|---|---|---|---|---|---|
| 1. A gain with forecast rain | PASS | PASS | PASS | PASS | PASS |
| 2. A gain with ERA5-Land rain | PASS | PASS | PASS | PASS | PASS |
| 3. No company clearly worse | PASS | PASS | PASS | PASS | PASS |
| 4. Reliability | PASS | PASS | PASS | PASS | PASS |
| 5. Not worse at a dry start | PASS | PASS | PASS | PASS | PASS |

- Condition 3: at no company and no lead does the interval lie wholly above zero. Every company's difference is
  below zero. Northumbrian at lead 2 is the only interval that reaches zero (upper end +0.0001).
- Condition 4: Northumbrian and Yorkshire pass by the 0.02 clause, not by being no worse than the baseline.

**The status input helps at every lead, 0 to 4.** As stated above, nothing deploys on this. 2025 has now judged
three candidates. The next step is a confirmation on 2026 data, stated before it runs, with the status computed from
SwimSignal's own polls. The production change is Ethan's call after that.

### Observations, not tested and not grounds for any change

- **With every status input missing, the candidate is worse than the baseline.** Measured on the 2025 rows:
  0.0537 at lead 0, 0.0634 at lead 1 and 0.0653 at lead 4, against the baseline's 0.0362 and the company flat rate's
  0.0547. *Inferred, not checked:* the model saw missing inputs only in the first days of January 2024, a wet spell
  (the 2024 rows with an unknown 7-day count spilled at 0.31 at lead 0). So it reads "missing" as "wet spell".
  **Any production use needs the fallback stated above: the baseline for any overflow whose status is missing.**
  At the 18 Oct poll that was 0.1% to 5.2% of each feed's overflows.
- **About half of the lead-0 gain is the label's definition.** On rows not spilling at issue, the lead-0 difference
  is −0.0051, against −0.0096 on all rows. In production, the hold-only "right now" rule already lifts today's level
  for most of those rows (feasibility, above).
- **Status buys about a day of lead.** With forecast rain, the candidate at each lead beats the baseline one lead
  earlier: 0.0371 at lead 1 against 0.0378 at lead 0, then 0.0397 against 0.0415, 0.0419 against 0.0438, and
  0.0451 against 0.0458. Measured, on the same rows.
- **The gain is largest where 2024's spells were longest.** Thames (47% of 2024 spill-days in runs of 7 or more) and
  South West (39%) gain most at every lead: −30% and −21% at lead 1. Northumbrian (9%) gains least: −4% at lead 1.
  *Inferred:* the input mostly carries persistence the rain totals miss, such as groundwater. Not checked overflow by
  overflow.
- **Layer 1 carries the gain.** Without offsets, the candidate scores 0.0269 at lead 0 and 0.0337 at lead 4, against
  the baseline's layer 1 alone at 0.0364.
- **Untested here:** status from polls instead of EA events, which is what production would read; the fallback rule;
  an isotonic lead map for the candidates.

### What was not done

- `spill_model.pkl` and `lead_calibration.json` are unchanged. Nothing reads the candidates.
- No code in `src/` computes the status inputs from the live feeds.
