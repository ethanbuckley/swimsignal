# Radar to the issue hour, in shadow: the models, the window and the bar, stated before any row is logged

Written 13 November 2026. Committed and pushed before the logger's code and before any build logged a radar
shadow row. Results go below the line at the end. Nothing above that line changes after a row is read, except the
window's first date, which is written under the line once the logger is live, the measured fetch cost (a
measurement of the radar step, not a score; its own section, filled before any row is logged), and a plain bug fix,
listed under "Changes after this statement" with what it changed.

Register rows: "Radar to the issue hour #694" and "Radar plus status #697" (`docs/RESEARCH-RECOVERY-2026-10.md`).
The rule this follows is "Shadow logging, when it is justified" in `docs/RESEARCH-WORKFLOW.md`.

**This changes no forecast.** The logger writes to its own table. No page, alert, level, card or published score
reads it. It does not touch the 2027 forecast stamp or any open window. **It is off until Ethan sets the repository
variable `DIPCAST_RADAR_SHADOW` to `1`** (see "What Ethan does to start it"). Merging the PR alone logs nothing and
fetches nothing.

## Why

Two development results on 2025 labels that had been scored before:

- [#694](RADAR-ISSUE-HOUR-TEST-2026-11.md): a spill model refitted on cell radar up to the issue hour, with forecast
  rain for the rest of the day, beat the same model form on forecast rain alone by 3.3% (fresh forecast for the
  rest of the day) and 1.9% (day-old), both intervals below zero. Thames 2026 did not confirm it.
- [#697](RADAR-PLUS-STATUS-TEST-2026-11.md): with the overflow's live status as at the issue hour in both arms, radar
  still added 3.2% and 2.5%, both intervals below zero. Status took the evening gain. What was left sat from 03 to
  15 UTC, on overflows not yet spilling.

Both records name a shadow log as the missing piece: fresh days, the forecast a build really holds for the rest of
the day, the build's own long-range rain, status from SwimSignal's own polls, and the real gaps between builds. No
backtest on history can give those, because the issued forecasts the builds held are cached only from late 2026.

## What has been seen, and what has not

- **Seen:** every figure in #694 and #697, including the by-hour, by-company and by-season tables and the Thames
  2026 checks; #254's, #639's and #695's results; the combined-v1 statement (#686).
- **Not seen:** any live radar composite read for a build; any shadow table; any live-status read (due on or after
  23 November 2026). No shadow row of any kind was opened to write this.

## The models, frozen

Nothing is fitted here. Eighteen files, all fitted on all of 2025 by #694's and #697's code, go into
`data/processed/radar_shadow/` in this PR. The logger is off unless every one is present with this SHA-256.

| Role | Arm | File | SHA-256 |
|---|---|---|---|
| Candidate with status, issue hour H | R0S@H | `R0S_00.pkl` | `74d47d0e8e5fb6975f5774848d488cec929892df590dfb076cbcb62065b5473a` |
| | | `R0S_03.pkl` | `3dd17a6999eb55f97d12e95e080b1dcfdd727a9e4da2db395b41e8b76f4dd5dc` |
| | | `R0S_06.pkl` | `5cb09f3f73b6aa0f517f1a493b6088524aeda8927b393752210b6a83cb23ab7e` |
| | | `R0S_09.pkl` | `152d835b3e66884bdc872eed869d0e26afe9e3d951a7ddbc0fb93014f3748789` |
| | | `R0S_12.pkl` | `df2f94d1220a903b2e8bb832992e4bedbe3934e247f46bc53f8b3de32d05c71a` |
| | | `R0S_15.pkl` | `c627bf428eb83edef8b283a7585f5f83be4890c76439bab2d3d0135d18409d9e` |
| | | `R0S_18.pkl` | `1156963e6d0d24cf0b48ef164a66219adbf6e9e84cd3a62dd911981e89f3ad5d` |
| | | `R0S_21.pkl` | `67e3018f4be081f11596c851c946a55b4516f7adf53d70eff729672f40adbbae` |
| Reference with status, issue hour H | PS@H | `PS_00.pkl` | `dac992dd33db1c1248b18dee64dac660dcca8cd17cf3becf42034a6b91ac7bf3` |
| | | `PS_03.pkl` | `d866420024a4cec9f2932eb979a577c05de1593d41852eaaaf91c45941bd5abb` |
| | | `PS_06.pkl` | `c7bd7dfcaec090afc5a26e38fa552d1884172c76d85dea732f17fdbb498a1e85` |
| | | `PS_09.pkl` | `dd6dceef21d38ab34d62dbc13ab0e012e9fc556a44529115a42e0d8f4f08df49` |
| | | `PS_12.pkl` | `49a7dab9cb10333f10b5cb243937198e00bf8271dc9107b6fa719a1b83d2a8ca` |
| | | `PS_15.pkl` | `1220eb2b9ba46c385e3368d8be31c28bfafb732fa9693e83b0a751483210fb4d` |
| | | `PS_18.pkl` | `85814677c30888e20d36eb88922b6d54cb63c06a4a971f3c0777f86d26cd89e5` |
| | | `PS_21.pkl` | `befaf801c6758850cf1199268122d7f2f3437187577acbad5f927458ffecf512` |
| Candidate without status (#694's one-model form) | C | `C.pkl` | `d157a268220e28f4915a2ea39c4f2b89452ec708b16859aba84efb25ee598f8c` |
| Reference without status | P | `P.pkl` | `70b0898e3dd3c0b33bfac89100b6493863c381340b7655c584147e53998b093f` |

**Where they came from.**
- `C.pkl` and `P.pkl` are #694's `model_2025_C.pkl` and `model_2025_P.pkl`, copied byte for byte from the session
  notes folder `radar-issue-hour-test-models/`, where #694 left them. Their hashes equal #694's score file.
- #697 kept no pickles, only hashes. The sixteen status fits were rebuilt on 13 November 2026 by
  `scripts/radar_shadow/freeze_models.py` (run by `freeze.sh`, from a `git archive` of `d1278adb` with
  `uv sync --offline`: scikit-learn 1.9.1, numpy 2.5.4, pandas 3.1.0, 4 threads). It runs #697's own code, imported
  and not edited, up to the status inputs and the scored rows, then fits only these sixteen arms on all 1,374,430
  rows (88,567 spill days). **All sixteen are byte-identical to the hashes in #697's score file.** 155 seconds,
  peak 2.8 GB, 0 network attempts, the shared inputs' fingerprints the same before and after.
- About 1.2 MB each, 19.5 MB for the sixteen and 2.4 MB for the pair. Git stores them compressed (about 0.5 MB
  each), so the repository grows by about 9 MB.

### Which model a build uses: the nearest issue hour

#697 fitted one model per issue hour, and builds run at no fixed hour. **The logger uses the model of the issue
hour nearest the build's own hour (option (a) in #697's "What follows").** A single status-plus-radar fit (option
(b)) would need its own test, and option (a) needs none: each model is used exactly as #697 scored it.

- The build's hour is the hours since 00:00 local on its target day (lead 0). In GMT this is the UTC hour, which is
  what #697's issue hour meant. H is that, rounded to the nearest multiple of 3 (a half rounds up), and 21 for
  anything from 22:30 on.
- Days are local in the build (`forecast.spill_probabilities`) and were UTC in #694 and #697. They are the same
  until 28 March 2027. From then the build's day starts at 23:00 UTC. Rows from British Summer Time are reported
  separately.

## The candidate and the reference, on one row

Every overflow of the nine English companies upstream of a listed spot, at lead 0 (today), on every build inside
the window. Both sides read **the site-day frame the production forecast has already built**, so the shadow costs
no rain request.

| | Reference | Candidate |
|---|---|---|
| Rain features | the frame as production built it: the build's own forecast rain, with the 31 past days `fetch_forecast` holds | the same frame with seven features rebuilt (below) |
| Status inputs | as at the issue time (below) | the same |
| Model, status known | PS@H | R0S@H |
| Model, status not known | P | C |

**The seven rebuilt features** are #694's: `rain_d`, `max1h_d`, `max3h_d`, `max6h_d` (today), `rain_d1`, `rain_d2`
and `rain_3d`. They are recomputed by `features.daily_rain_features` from an hourly series that is the build's
forecast rain with radar put in where it counts. The longer features (`rain_7d`, `rain_30d`, `api`) stay as the
frame has them, from the forecast rain, on both sides. In #694 they came from ERA5-Land on both sides.

**An hour takes radar** when its label (hour-ending, UTC, as Open-Meteo labels its hours) falls from 00:00 local
two days before today up to the time the build listed the bucket, and the cell's hour has coverage at least 0.9
(#694's rule). Coverage under 0.9 covers a composite that was not yet published, missing or unreadable. Every
other hour keeps the forecast. Missing radar is never zero rain.

**The status inputs** are #697's, built from the build's own poll files:
- `spilling_at_issue`: the build's own poll of the overflow (the live-status shadow's input, unchanged);
- `spill_hours_24h`: hours spilled in the 24 hours before the issue time, from the poll intervals merged as the
  live-status shadow merges them (`live_status.poll_events`, `_merge`). #697 ended this window at the issue
  instant. The live-status shadow ends it at local midnight; that is not used here;
- `spill_days_7d`: spill-days in the seven local days before today (the live-status shadow's input, unchanged).

The status is **known** by the live-status shadow's rule (`live_status.status_known`: a current status, the latest
reading at most 8 hours old, no gap over 8 hours in the seven-day window). Where it is known, the row takes the
status pair. Where it is not, both sides fall back to the pair without status (C against P). The pair a row used is
logged.

**Fallback when radar is late or missing,** in three steps:
1. An hour not published, or under 0.9 coverage: that hour keeps the forecast (the rule #694 tested).
2. The whole build's radar is not used (`radar_state` = `fallback`) when the listing fails, its newest composite is
   more than 90 minutes older than the listing, a cap is passed, h5py is missing, or any error occurs. The
   candidate's chance is then the reference's on every row (`p_candidate = p_reference`).
3. Three builds in a row over a cap stop the radar step (`stopped`) until the counter file is deleted. Rows are
   still logged, with the candidate equal to the reference.

**The fallback is part of the candidate.** The read scores `p_candidate` as logged, and reports the `ok` rows apart.

### United Utilities (#695)

#695 found that at United Utilities the status uplift lands only on rows already spilling. #697 found radar with
status gains at United Utilities as elsewhere (3.2%), and all of it on rows not spilling. So United Utilities stays
in the deciding pool, with the same models. It is reported apart, and so is every row by `spilling_at_issue`.

## What is logged

Table **`shadow_radar_v1`** in the state database (`dipcast.duckdb`). It is not the issued-forecast table. The logger
reads no other shadow table. **One row per overflow per build**: an overflow upstream of two spots is logged once,
from the first spot's forecast.

| Column | What |
|---|---|
| `issued_at`, `issue_day`, `target_day` | the forecast's issue time, its local day, the target day (= issue day, lead 0) |
| `build_at` | when this build listed the bucket (the same for every row of a build) |
| `site_id`, `company` | the overflow |
| `issue_hour` | H, the model's issue hour |
| `p_candidate`, `p_reference`, `pair` | the two sides, and `status` or `no_status` |
| `p_r0s`, `p_ps`, `p_c`, `p_p` | all four models on the row, so either pair can be read whatever happens to the status switch |
| `radar_state` | `ok`, `partial` (some hour labelled 15 minutes or more before the listing kept the forecast), `fallback`, `stopped` |
| `radar_hours`, `forecast_hours` | the window's hours (two days before to the listing) that took radar, and that kept the forecast |
| `radar_newest_scan`, `radar_newest_modified` | the newest composite listed: its scan time and when it reached the bucket |
| `status_known`, `spilling_at_issue`, `spill_hours_24h`, `spill_days_7d` | the status inputs, NULL where not known |
| `rain_issued_at` | when the rain forecast at the overflow's cell was fetched |
| `p_raw`, `p_cal`, `p_shown` | production's raw chance, after the lead map, and what the site published, from the same forecast |
| `rule`, `models`, `version` | `radar-v1`, a stamp of the eighteen files, production's version stamp |

**No radar value is logged.** The table holds chances, counts and times. The composites' per-cell sums are carried
between builds in `radar_snapshots_v1.parquet` in the state folder, which the build's actions cache keeps. The state
release's upload list does not name it, so no radar rain is published. The radar is CC BY-SA 4.0. Whether a chance
computed from it inherits the licence is the open question already on the solicitor's list
(`docs/MET-OFFICE-DATA-2026-10.md` §8), the same one that applies to the Met Office forecast rain the site already
uses. The carried file and this statement carry the credit.

**Issue-time inputs only.** Radar: only composites in a listing the build read before the forecast, each hour with
the time its last composite reached the bucket. Rain and status: what the forecast itself had read. The log keeps
each input's time beside `issued_at`.

## Cost and caps

- **Open-Meteo: 0 calls.** Both sides read the frame production built. A test counts rain requests with the logger
  on and off.
- **Met Office bucket: no account, no key.** Per build: at most 5 listing requests and **300 composites**, one
  request at a time, 0.2 seconds apart, no retry, and **240 seconds** for the whole step. Over a cap: `fallback`.
- **Where it runs.** Inside the site build, after the rain prefetch and before the spots' forecasts, once. Then each
  spot's forecast adds four model passes on its lead-0 rows. No new Worker, scheduler, service or secret.
- **h5py** (the optional `radar` group) is installed by the build only when `DIPCAST_RADAR_SHADOW` is `1`.
- **Stop rule: nothing is logged for an issue day after 31 August 2027.** Extending it is its own PR.
- Size, inferred: about 1,300 overflows a build, four to six builds a day, so about 6,000 rows a day and 1.7 million
  by the stop date. At 40 to 95 bytes a row (#686's measured range), 70 to 160 MB.

The measured fetch and time figures are in the next section.

## Measured fetch cost

To be filled from a real run on this Mac before any row is logged.

## The rows, the labels and the comparator

**Rows.** Every logged row whose overflow-day has a live label, one per overflow per build. A target day with
several builds gives several rows, each scored. Every predictor is scored on the same rows.

**Labels.** The poll-based labels the live-status shadow and the Accuracy page use (`forecast_log.observed_spill_days`
on `live_history`, dry only on overflow-days the coverage rules count as watched). A missing or stale status is
unknown, never a dry day.

**Comparator.** The reference on the same row (`p_reference`). The claim under test is radar to the issue hour,
not a change of model. Production (`p_cal`) is reported beside it, since both sides differ from production by being
2025 nine-company fits with no lead map.

## The window

- **Opens** on the first issue day with a logged row, once Ethan has set the variable. Written under the line from
  the first logged rows, before any label is joined.
- **Closes** after issue day 31 August 2027 (the stop rule).
- **Interim read** on or after 8 April 2027, on the rows to 31 March 2027, so a result exists before the 1 May 2027
  date for any amendment to the 2027 stamp.
- **Final read** on or after 8 September 2027, on the whole window.

**Why the window runs into summer.** #697's winter rows (December to February 2025) gave an interval that included
zero (−0.00044, −0.00121 to +0.00023), on 3,778 overflows with the EA's complete labels. The shadow logs about a
third as many overflows, with poll labels. So a winter-only window is unlikely to show a gain of 2025's size.
Summer and autumn carried the clearer gains in 2025. (Inferred from #697's intervals, not simulated.)

It does not touch the live-status read (23 November 2026), the combined-v1 or regional windows, A8, lead
calibration B, ensemble rain, option B or the 2027 primary evaluation.

## The bar

**D** = the mean over scored rows of Brier(`p_candidate`) − Brier(`p_reference`). Skill = 1 − mean Brier of the
candidate / mean Brier of the reference. The margin is 1% of the reference's Brier, as #694 and #697.

**Interval.** A two-way cluster bootstrap over overflows and ISO weeks, 2,000 draws, `numpy.random.default_rng(20261113)`,
the 2.5th and 97.5th percentiles (final read) or the 0.5th and 99.5th (interim read).

**Verdict, at each read:**
- **W. Worse:** the interval lies wholly above zero.
- **H. Radar to the issue hour helps on fresh days:** the interval lies wholly below zero and the skill is at
  least 1%.
- **S. A small gain:** the interval lies wholly below zero and the skill is under 1%.
- **N. Not shown:** the interval includes zero. The record says whether it also rules out a 1% gain. **An interval
  that includes zero shows neither a gain nor "no worse".** No non-inferiority margin is stated, so no
  non-inferiority claim will be made.
- **Too few:** fewer than 12 ISO weeks with logged rows, or fewer than 1,000 labelled spill rows. No verdict.

The interim read uses the 99% interval, because it is a second look at the same window. Only H or W at the interim
read is acted on; anything else waits for the final read. The final read decides.

**Reported, not deciding:** D by issue hour; by `radar_state` (and the `ok` rows alone); by `pair`; rows spilling at
the issue time and the rest; United Utilities and each company; by month; GMT and BST rows apart; the candidate
against production (`p_cal`); the no-status pair on every row (`p_c` against `p_p`); the share of hours that kept
the forecast; builds in each state.

**Checks run first,** on a copy of the state database, reading only this table and no label: every row has the
rule and stamp; `p_candidate` equals `p_r0s` or `p_c` as `pair` says, and `p_reference` equals `p_ps` or `p_p`; every
`fallback` and `stopped` row has `p_candidate` equal to `p_reference`; `issue_hour` matches `issued_at`; no
`radar_newest_modified` is after `build_at`, and no `build_at` after `issued_at`. The read stops if any fails.

## What follows, by outcome

Nothing on the site or in production changes, whatever the result. Any live use of radar would change the 2027
forecast stamp (`docs/PREREGISTRATION-2027.md` §2) and need a dated amendment before 1 May 2027.

- **H.** The first fresh-day evidence. Next: a refitted production candidate with radar to the issue hour (status
  in it if the switch is on), shown no worse than production by a frozen-model backtest, in its own PR. #694 found
  the production model gains nothing from radar without a refit.
- **S.** Record it and the hours that carry it. Next: a diagnosis from the logged parts (hours, fallback share,
  status pair) before any new candidate.
- **N.** Not shown on fresh days. Next: the EA's 2026 start/stop files, when published, scored by #697's harness
  with these frozen models unchanged. That backtest runs whatever this window shows.
- **W.** A diagnosis of the join between radar and forecast hours (time labels, local days, the publish rule) in
  the read's PR, since a loss here would point at a fault in the method.
- **Too few.** No verdict. The EA 2026 backtest above is the next deliverable.

**If a frozen file, the hour rule or the fallback changes inside the window,** the window ends the day before and a
new one starts with a new statement.

## Not chosen, and why

- **One fit for every hour with status.** It would need its own test (#697). The per-hour models are scored as
  they are.
- **Only #694's pair, without status.** Status will be in production if Ethan switches it on after 23 November.
  Logging both pairs on every row covers either decision at the cost of two model passes.
- **Builds by 08:00 only** (as #686). The radar gain changes with the hour, and #697's gain sits from 03 to 15 UTC.
- **A separate Worker or schedule.** The build's cadence is adequate for a per-build log, and its availability
  and cost are known.
- **Publishing the radar rain.** Not needed for the read, and a licence question nobody has to answer for a log.

## What Ethan does to start it

1. Merge the PR.
2. Set the repository variable `DIPCAST_RADAR_SHADOW` to `1` (GitHub, Settings, Secrets and variables, Actions,
   Variables).

The next scheduled build installs h5py, fetches the radar and logs. Unset the variable to stop it.

## Changes after this statement

None yet.

---

## Results

Not yet run. No row has been logged.

### The window's first date

To be written from the first state release that holds logged rows, before any label is joined.

### Data credits

Contains Met Office data © Crown copyright 2024–2026, licensed under CC BY-SA 4.0 (AWS Open Data: Met Office UK
Radar Observations). Environment Agency event duration monitoring data, Open Government Licence v3.0. Weather data
by Open-Meteo.com (CC BY 4.0).
