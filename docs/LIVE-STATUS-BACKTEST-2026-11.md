# The live-status candidates on 2026: a frozen-model backtest, stated before any score

Written 6 November 2026, before any 2026 forecast from these models was computed or read. Committed and pushed
before the run. Results go below the line at the end. Nothing above that line changes after a result is seen.

The rule this follows is "Backtest instead of waiting" in `docs/RESEARCH-WORKFLOW.md` (Ethan, 6 Nov 2026).

## Why

PR #254 (`docs/LIVE-STATUS-FEATURE-TEST-2026-10.md`) added each overflow's own recent spill status to the spill
model: three inputs, one candidate per lead 0 to 4, fitted on the EA's 2024 start/stop files. On held-out 2025 it
passed all five of its conditions at every lead. It deployed nothing. It said a pass "earns a confirmation on 2026
data", from either SwimSignal's polls or "the EA 2026 start/stop files once all nine companies' files are out".

PR #262 put the candidates in shadow, with a fallback, against production. That window runs 25 Oct to 21 Nov 2026
and is read on or after 23 Nov. It is not touched here.

The EA's 2026 file now covers all nine companies from 1 January to 31 August. This test scores the frozen
candidates on it. It is the second of three periods: 2025 (#254), January to August 2026 (this test), and the
autumn 2026 shadow (#262).

## Is 2026 independent of the candidates?

**Established, from the code and the files:**
- The five candidates were fitted on 18 Oct 2026 from 2024 rows only (`scripts/live_status_test.py`, `fit_candidate`).
  That script's `load_events` read `ea_events_<company>.parquet` from the 17 Oct import, which holds 2024 and 2025
  only: the latest event start in each of the nine files is in 2025 (checked 6 Nov on the main checkout's copies,
  which the hashes below fix). The script stops unless it gets D2's 2024 and 2025 row counts.
- Their settings (`neg_frac` 0.25, seed 0, prior strength 15, recency 1) are D2's, fixed on 17 Oct with 2025 as the
  hold-out. The three inputs and the 00:00 UTC issue time were fixed in #254's statement, written from 2024 only.
- The files have not changed since. Their SHA-256 today equals #254's prefixes and the files in
  `data/processed/live_status/` (committed in #262) and in `swimsignal-private/baselines/live_status/`.
- #262's fallback rule (production where the status is unknown) was written on 20 Oct. Its 8-hour stale limit came
  from the poller's cadence from 28 Sep to 20 Oct. It used no January to August 2026 outcome.
- Production (`spill_model.pkl`, last changed 13 Sep 2026) and its lead map (`lead_calibration.json`, 15 Sep,
  `fitted_on` 2025) were fitted before the EA's 2026 file was imported anywhere in this project.

**Already seen of January to August 2026, by me or in records, before this was written:**
- PR #357's data check and results (25 Oct): spill-days per company and month, United Utilities' low January, and
  production's 2026 Brier per company on UK local days (nine together 0.0420). Those score production, not these
  candidates.
- This session's `count` stage (below): rows per company and lead, and how many rows have an unknown status. It
  computed no forecast and read no label.

So nothing about these candidates or their fallback was chosen after seeing 2026. The workflow allows reusing a
period already scored for a different model in that case. 2026 was used to judge PR #357's v2 model against
production. That does not touch these candidates.

**Not known:** whether any person looked at 2026 status-versus-outcome tables informally between 17 and 18 Oct.
Nothing in the records says so.

## Frozen inputs

| What | File | SHA-256 |
|---|---|---|
| Candidate, lead 0 | `data/processed/live_status/candidate_lead0.pkl` | `deb5e1e5ee64df0e48e789b9b8eba9bb0be76fba4a23e6745f6a259cec436d00` |
| Candidate, lead 1 | `candidate_lead1.pkl` | `e0756b1e97485d458bafb868480d73b8c95c502f4136aa05937cb166d3909c3e` |
| Candidate, lead 2 | `candidate_lead2.pkl` | `ed5bb2b9a39ee222303e3c923b824deffde00e1c63eca89371a3800e51c894da` |
| Candidate, lead 3 | `candidate_lead3.pkl` | `5180de7086c682fcfebcc9b02e12e197bbd7fb09d5aeb7dfeb940350d8a1360f` |
| Candidate, lead 4 | `candidate_lead4.pkl` | `ecc835c96d707534d88dbecf6f286c59adb90839f31985926110b85ec4824066` |
| #254's baseline (D2) | `swimsignal-private/baselines/spill_model_nine_2024.pkl` | `1603678923ccdd1553830fa67c2069714c0a836c9df7e8c52578aabd729b5bcc` |
| Production | `data/processed/spill_model.pkl` | `faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e` |
| Production's lead map | `data/processed/lead_calibration.json` | `734202bc7f22af38fd72d65c4038bb51828b11f5436ed1de40ffa0f381ad0f09` |
| EA 2026 events | `2026 year to August Detailed EDM Start-Stop Data.zip`, downloaded 6 Nov 22:48 UTC | `d0dbf32fb8622f98fe072466598d706590e5f8e667619cba7d0639c6555a1a8f` (29,672,650 bytes; the same bytes as #357's) |
| EA 2024-25 events | the 17 Oct import, `ea_events_<company>.parquet` on the main checkout | hashes in the run's `checks.json` |
| Annual returns | `data/processed/annual_returns.parquet` | `9f8604f9bbea29b993deadaf70ca92ae9a08050aaa717a731c58e8269db45065` |
| Poll coverage, for the dead-monitor check | `live_coverage.parquet`, `state` release of 6 Nov 15:43 UTC | `67731cce7d8cbb422ea8b840c5816267ce57e67a463a14467066f053c1a0d446` |

The harness (`scripts/live_status_backtest_2026.py`) stops if any model, the lead map or the zip differs.

## The period and the rows

- **Days.** UTC days, 1 January to 31 August 2026. UTC, not UK local, because #254's candidates were fitted on UTC
  days with the issue time at 00:00 UTC. Local days with a 00:00 UTC status would let up to an hour of the target
  day into the lead-0 status in summer. The EA's 2026 file ends on 31 August for every company. The EA's dataset
  list on 6 Nov still names only "2026 year to August".
- **Overflows.** PR #357's window E: the nine English companies' overflows with a position in the 2025 return, EDM
  operation of at least 50% in 2025, not the 16 overflows upstream of Cromwheel (PR #298 published their 2026
  outcome), and a monitor that passes option B's dead-monitor check over its **full** reference period, 5 Oct to
  1 Nov 2026 (28 days; a known poll on at least 20). #357 had only 20 of those days.
- **Covariates** from the 2025 return, as D2 took the year before's return.
- **Rain.** ERA5-Land, PR #357's files: for each cell, one 2026 file (the shared cache's `_2026` if present, else
  `rain_nine/…_2026a`) and December 2025 from the 2025 file. A row is kept when its day's rain is finite.
- **Labels.** A UTC day is a spill-day if an EA event touches it (`features.spill_days`, #254's label).

Counted before writing (the `count` stage; no label and no forecast read):

| Company | Overflows | Rows, ERA5-Land rain | Rows, forecast rain (each lead) |
|---|---|---|---|
| Anglian | 1,315 | 319,545 | 20,726 |
| Northumbrian | 1,475 | 358,425 | 0 |
| Severn Trent | 2,388 | 580,284 | 161,711 |
| South West | 1,292 | 313,956 | 482 |
| Southern | 892 | 216,756 | 0 |
| Thames | 529 | 128,547 | 46,031 |
| United Utilities | 2,219 | 539,217 | 12,773 |
| Wessex | 1,255 | 304,965 | 61,696 |
| Yorkshire | 2,061 | 500,823 | 46,754 |
| **All nine** | **13,426** | **3,262,518** | **350,173** |

- 13,426 of 13,972 overflows pass the dead-monitor check.
- 3,935,563 EA events were read: 2,952,154 from the 2024-25 files and 983,409 from the 2026 file.
- Rain: 1,606 cells, 196 from the shared cache's 2026 files and 1,410 from #357's fetch.

## Status at issue time: #254's rule, rebuilt from the EA records

The harness imports #254's `Status` class and `merged_intervals` unchanged and moves the grid to start on
1 January 2025. For overflow *i*, target day *d* and lead *k*, the issue time is 00:00 UTC of day *d*−*k*:
- `spilling_at_issue`: 1 if a merged event runs at the issue time;
- `spill_hours_24h`: hours spilled on UTC day *d*−*k*−1, at most 24;
- `spill_days_7d`: spill-days among days *d*−*k*−7 to *d*−*k*−1, by the label's own rule.

Each overflow's events from the 2025 and 2026 files are merged first, as #254 merged 2024 and 2025. Some companies
start a running event again at 00:00 on 1 January in the new file.

**When the status is known.** #254's rule: a day in year *y* is known if the overflow has an event in year *y*'s
file, or 0 spills in year *y*'s return, and EDM operation is not under 50%.
- For 2025 days (the windows of early January 2026) the rule is applied as written, with the 2025 return.
- For 2026 there is no return yet. Every window-E overflow counts as known in 2026. Its monitor passed the
  dead-monitor check, which stands in for the return, as in #357.
- An input reading any unknown day is missing. The count stage found 21 to 33 rows with a missing input (leads 0
  to 4), all in the first days of January.

**The fallback (#262's rule).** Where any status input is missing, the forecast is production's.
- On ERA5-Land rows that is production's raw chance. On forecast-rain rows it is production's chance after the
  lead-*k* map, what the site shows.
- **What this backtest cannot test.** #262's "stale" rule (no current reading for over 8 hours) is about polls.
  The EA file is a complete record compiled after the fact, so nothing in it is stale. SwimSignal's polls start on
  11 September, after the file ends. So the poll-based status, its under-counted short events and the 8-hour rule
  are tested only by #262's shadow.
- **Reported, not deciding:** the same comparison with every Southern Water row on the fallback. #262 found
  Southern 0% known on the polls, so this is the mix the site would actually ship.

## The predictors

| Name | What |
|---|---|
| Candidate *k* | #254's lead-*k* candidate, no lead map (as #254 and #262 run it) |
| Candidate *k* with fallback | the same, with production where the status is missing (#262's rule) |
| D2 | #254's baseline: the same model without the status inputs |
| Production, raw | `spill_model.pkl`, United Utilities 2023-25. Out of sample for 2026 at every company |
| Production, mapped | production raw, then the lead-*k* isotonic map from `lead_calibration.json` (`forecast._apply`). This is `p_cal`, what the site shows and #262's comparator |

## Two questions, both stated now

**Q1. Does the status input still help D2's model on 2026?** This repeats #254 on a new year: the candidate exactly
as #254 scored it (a missing input left as it is) against D2.

**Q2. Does the candidate, with the fallback, beat production? This one decides what follows.** It is the change
that adoption would make.
- On ERA5-Land rows: the candidate with fallback against production raw. That is how #357 scored production. The
  lead map is fitted for forecast rain, so it is not applied to reanalysis rows.
- On forecast-rain rows: the candidate with fallback against production mapped.

## The metric and the rain

- **Brier score** by lead 0 to 4. AUC, log loss, ECE and the mean forecast are reported.
- **ERA5-Land rain:** every row above. Only the status age differs between leads.
- **Forecast rain:** #254's rule and code, unchanged. Rows in the 206 cells with archived 2026 lead forecasts
  (`data/cache/rain/leads_<cell>_2026.parquet`, 1 Jan to at least 13 Sep). For lead *k*, days *d*, *d*−1 and *d*−2
  come from the forecasts issued *k*, *k*−1 and *k*−2 days ahead (floored at 0), every earlier day from ERA5-Land. A
  row needs 65 of its 72 hours finite and a day-*d* total. A missing rain feature becomes 0. The same rain feeds
  every predictor.
- **Known difference from production's live rain.** Live, production reads the forecast API's own recent past
  hours, not ERA5-Land, for days before today. The archived forecasts here are Open-Meteo's previous-run archive,
  read by cell. This is #239's and #254's approximation, kept for comparability.
- **The forecast-rain rows hold seven companies, mostly Severn Trent.** Northumbrian and Southern have no cached
  lead cells, and South West has 482 rows. Condition 1 is all forecast-rain rows together, as in #254. Its company
  lines are reported, not deciding.

## Intervals

- **Deciding: two-way cluster bootstrap by overflow and by ISO week** of the target day. This is PR #357's and
  the 2027 protocol's method. Each draw resamples overflows with replacement and, independently, ISO weeks with
  replacement. A row counts (times its overflow was drawn) × (times its week was drawn). 2,000 draws from
  `numpy.random.default_rng(20261106)`, overflows first, then weeks. One set of draws serves every question, lead,
  rain source, company and subset. 95% interval: the 2.5th and 97.5th percentiles.
- **Reported beside it:** #254's own interval, ISO weeks alone, from the same week draws.
- **Why this differs from #254.** #254 clustered by week only. Errors are shared within an overflow across its days
  as well as across overflows within a storm. So the two-way interval is wider. That makes a pass harder, not
  easier. No margin changes.

## The conditions: #254's five, unchanged

At lead *k*, for each question, "the baseline" is D2 (Q1) or production (Q2). **The candidate helps at lead *k*** if
all five hold:

1. **A gain with forecast rain.** On the forecast-rain rows, all together, the candidate's Brier is lower than the
   baseline's, and the 95% interval of the difference lies wholly below zero.
2. **A gain with ERA5-Land rain.** On the ERA5-Land rows, all nine together, the same.
3. **No company clearly worse.** On the ERA5-Land rows, at no company is the candidate's Brier higher with the 95%
   interval of the difference lying wholly above zero.
4. **Reliability.** On the same rows, at each company, the candidate's ECE is no higher than the baseline's, or it is
   at most 0.02.
5. **Not worse at a dry start.** On the ERA5-Land rows not spilling at issue and with no spill-day in the 7 days
   before, the 95% interval of the difference does not lie wholly above zero.

ECE is `training.ece`: 10 equal-width bins, weighted by rows. No minimum-data rule is added: every company has
over 128,000 ERA5-Land rows.

## Reported, not deciding

- Per company, at every lead and for both rain sources: Brier, AUC, ECE, mean forecast, and the difference with
  both intervals. Company lines never choose anything and no company result is called confirmatory.
- Subsets: spilling at issue; not spilling at issue; dry start; status unknown. At lead 0 a spill running at 00:00
  makes the day a spill-day, so part of a lead-0 gain is the label's definition, as in #254.
- Q2 with every Southern Water row on the fallback.
- Q2 without United Utilities' January (#357 flagged it; cause unknown).
- Production with forecast rain but no lead map.
- By month, point estimates only.

## What follows

- **Q2's five conditions hold at lead *k*.** Established: the candidate beat production on two held-out periods
  (2025 against D2, 2026 against production). The adoption change is then drafted as a switch that defaults off:
  lead *k*'s candidate where the status is known, production where it is not. **It is not switched on.** Ethan
  decides after the shadow read on or after 23 Nov. Risk levels keep the full public evidence bar. Wording about
  the source of a day's risk needs a look before any switch (#262, "What follows").
- **Q2 fails at lead *k*.** Production stays at lead *k*. The record states what is supported, and the next
  deliverable follows the workflow's "Develop promising work now".
- **Q1 is reported with its own verdict line.** A Q1 pass with a Q2 fail would mean the status helps, but this
  candidate (D2's 2024-only base) does not beat production. The next candidate would then add the status to a
  stronger base, with its own statement.

## Expected, stated now (inferred, not conditions)

- Q1 passes at every lead. Status persistence is a property of overflows and groundwater, not of one year.
- Q2 passes at leads 0 and 1. Q2 is open at leads 2 to 4, mainly at United Utilities: there production was fitted on
  three years of the company's own records, and #357's v2 lost to it by 3.4% on 2026.
- The status gain shrinks with lead, as in #254 (−27% at lead 0 to −8% at lead 4 against D2).

## Network, resources and isolation

- **Open-Meteo: 0 calls.** All rain is cached. The ensemble-rain test D4 (to 19 Nov) is not touched.
- **EA: one zip**, downloaded once through `scripts/import_ea_events.py --years 2026` into a scratch root before this
  was written (4 HTTPS requests). No other EA call.
- **GitHub: one release asset**, `live_coverage.parquet` (308,938 bytes), read-only. The shadow log
  (`forecast_overflows` in the `state` release) is **not** downloaded or read before 23 Nov.
- **Isolation.** A scratch `DIPCAST_ROOT`, `DIPCAST_STATE` and output folder. `DIPCAST_CACHE` points at the main
  checkout's rain cache, read-only. The main checkout's event files, models and cache listings are fingerprinted
  before and after the run. Nothing is written to the main checkout.
- **Lock.** The run holds the group's `heavy-run.lock`. The count stage took 34 seconds and 2.8 GB.

## Order of work

1. Commit and push this statement and the harness. Open a draft PR against `main`.
2. Check no other heavy run holds the lock (`pgrep -fl`, never `pkill`).
3. `scripts/live_status_backtest_2026.py run` under the lock.
4. Write the results below the line. Commit the tables beside this file.
5. Update the register row and the catalogue entry.

---

## Results

Not yet run.
