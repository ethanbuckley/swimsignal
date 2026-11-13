# Scotland's mapped forecast in shadow, 13 November 2026

Written and pushed on 13 November 2026, before the arm's code was written and before it logged anything. It says
what the arm logs, how and when it will be read, and what the read can and cannot support. Nothing in it changes the
existing Scottish shadow, Gate B, an issued forecast or anything a swimmer sees. `DIPCAST_SCOTLAND_TRIAL` stays off.

Arm: `scotland-map-v1`. Code: `src/dipcast/scottish_shadow_map.py`. Read: `scripts/scotland_map_arm_read.py`.
Contains Scottish Water data licensed under the Open Government Licence v3.0 (the map and covariates).

## 1. Why

The Scotland trial ([record](SCOTLAND-TRIAL-2026-11.md)) would show spill chances that have been through
Scotland's calibration map. The live shadow ([Gate B](SCOTLAND-PLAN-2026-10.md), `scottish_shadow.py`, on since
11 October) scores the same raw chances through England's lead calibration instead. So Gate B scores a forecast the
trial would not show. On Scottish Water's records England's calibration leaves the level at 0.58 to 0.66, and the
map brings it to 0.98 to 1.03 (2025, leads 0 to 3).

The map passed a frozen-model backtest on 2021 at lead 0, with the rain that fell
([record](SCOTLAND-2021-BACKTEST-2026-11.md)). Leads 1 to 3 rest on the 2025 check, which is exploratory. No live
score of the mapped forecast exists. This arm collects one.

## 2. What is logged

A new file in the state directory, `scottish_water_map_v1.duckdb`, with one table, `shadow_scotland_map_v1`. It
sits beside the existing shadow's `scottish_water_forecasts.duckdb`. The existing file, its table, its rows, its
version stamp, its rules and its scores are not touched.

One row per overflow, issue and target day (today and four more). A build's rows are logged only when the existing
shadow logged that same build, so the two logs hold the same issues.

| Column | What it is | Its time |
|---|---|---|
| `issued_at`, `issue_day`, `target_day`, `lead` | As the existing shadow's row | The build's own clock |
| `site_id` | Scottish Water's asset | |
| `p_raw` | The production spill model's chance, Scottish covariates, before any calibration. The same number the existing shadow logs | Issue time |
| `p_prod` | `p_raw` through England's lead calibration. This is the existing shadow's `p_cal`: production's unmapped forecast, the comparator | Issue time |
| `p_map` | `p_raw` through Scotland's map (`scotland_trial.apply_map`). What the trial would show. Empty when the map could not be applied | Issue time |
| `map_applied`, `fallback` | Whether the map was applied, and if not, why | |
| `rain_available`, `rain_mm`, `rain_age_h` | Whether the overflow's cell had rain, the target day's rain, and how old the rain forecast was | The rain forecast's own issue time |
| `covariates` | `sw2025` where the overflow has its own count from the year before, `filled` where it took the median | |
| `arm` | `scotland-map-v1;spill=<stamp>;cov=<file hash>;map=<file hash>` | |
| `version` | The existing shadow's full stamp for the same build | |

Every input exists when the build runs. No outcome is read by the logger. The log is never backfilled.

**The map is pinned.** v1 is the file `data/processed/scotland_calibration.json` committed on 1 November 2026
(42efc002), SHA-256 `447a02a1556fd811719bc49776131ef1a2e386020ad5449030624755b172811d`: a = 0.449, b = 0.750, fitted
for spill model `808da63d`. A different map is a different arm and needs its own table and statement.

**The arm's label** names only what changes the mapped number: the spill model, the covariate file and the map.
A new E. coli model or a new England lead calibration does not start a new arm. (A new England calibration changes
`p_prod`, the comparator. The read reports the comparison by England's calibration stamp as well as overall.)

## 3. Comparator and fallback

- **Comparator.** `p_prod`, logged in the same row. The read also checks it against the existing shadow's own row for
  the same overflow, issue and target day. They must be equal.
- **No rain for the cell.** The row is logged with `rain_available` false and is never scored. Both forecasts are
  missing there, as in England and in the existing shadow.
- **No map.** If the map file is missing, is not the pinned file, or was fitted for another spill model, the row is
  logged with `map_applied` false, `p_map` empty and `fallback` naming the reason. In that state the trial switches
  itself off and production's forecast is what remains, so the row keeps `p_prod`. These rows are counted and kept
  out of the mapped scores.
- **The logger fails.** It is called inside its own guard after the existing shadow's rows are written. A failure is
  reported in the build log and changes nothing else. That build's mapped rows are lost, not rebuilt later.

## 4. How this differs from what the trial would show

Established by reading the code, not by a run:

- **Same numbers where they overlap.** The raw chance comes from the same function with the same model and the same
  Scottish covariate table. The map is applied by the trial's own function.
- **All forecast overflows, not the trial's.** About 1,485 overflows. The trial uses only those upstream of its
  twelve listed spots: 5 at Dores and 8 at Luss Bay on 1 November. The nine spots added that evening were not
  counted here.
- **One position differs.** The trial moves Dores Village CSO (CSO005667) to its checked point. The shadow keeps
  Scottish Water's position.
- **Rain can be older.** The shadow's rain is rationed and can be up to 24 hours old. The trial's spots ask first.
  Each row logs the age.
- **Overflow-days, not spots.** The swimmer-facing level at a loch (travel, dilution, the E. coli estimate) is not
  scored here.
- **Leads 0 to 4.** The trial also shows a sixth day.

## 5. How and when it will be read

**When.** Once, on or after **3 February 2027**, with Gate B. Target days from the arm's first logged issue to
31 January 2027. The state directory lives in the Actions cache only, so the read needs a copy of it, as Gate B's
does.

**Before then.** Counts only: rows, issue days, the share with the map applied, rain availability, fallback reasons
and whether `p_prod` equals the existing shadow's row. `scripts/scotland_map_arm_read.py` refuses to join outcomes
before the read date. No one reads a score early.

**Scoring rules.** Gate B's, unchanged: the forecast issued latest by 08:00 local on the issue day, England's
coverage rules on Scottish Water's polls, stuck monitors left out, the climatology baseline from the Scottish
overflow table. Rows are scored where the map was applied and the cell had rain.

**Three measures, at leads 1 to 3 together.** Intervals are Gate B's: 2,000 resamples of target days (all overflows
of a day together), seed 0, 95% percentile.

| | Measure | Holds when |
|---|---|---|
| M1 | Brier skill of `p_map` against the climatology baseline (Gate B's own figure, on this arm) | Lower end above zero, with at least 200 spill-days |
| M2 | Level: sum of `p_map` / spill-days | Between 0.9 and 1.1 (the map's own band) |
| M3 | 1 − Brier(`p_map`) / Brier(`p_prod`) on the same rows | Lower end above zero |

M3's margin is zero and it is a test of "better", not of "not worse". An interval that includes zero shows neither.

**Reported beside them, not gated.** Each lead 0 to 4 on its own. By calendar month. By `covariates` (own count or
filled). Wet and dry target days (10 mm). Rain under and over 12 hours old. By England's calibration stamp. The
existing shadow's Gate B figure on the same rows. Reliability by tenths.

## 6. Starting mid-window: what it does to the sample

Gate B's window is 1 November to 31 January, 92 target days. This arm starts when its PR is merged and the next
build runs. If that is 16 November it has 77 of the 92 days, 84%.

- **Fewer days, wider intervals.** The interval resamples days. Fewer days, and any wet spell before the start, are
  lost. 200 spill-days is not the limit: about 1,485 overflows reach it in days. The number of distinct days is.
- **Two windows.** Gate B's figure and this arm's are over different days unless restricted. So the read compares
  the two forecasts only on this arm's rows, where both are logged.
- **A derived series, kept apart.** For issue days from 2 November (the first after the map was committed) to this
  arm's first, the existing shadow logged `p_raw` at issue time. The pinned map is a fixed function of `p_raw`. The
  read applies it to those rows and reports the three measures on the full window as **derived, not logged**. It is
  never mixed into the logged figures and never written into the log. It is valid only if, on days both exist, the
  derived value equals the logged `p_map` to 1e-9 on every row, and the row's spill stamp is `808da63d`. If either
  check fails the derived series is dropped and the reason reported.
- **Which one counts.** The logged series is the read. The derived series is context. If they disagree in sign, the
  record says so and does not pick one.

## 7. What the read can and cannot support

**Can.** Whether the mapped forecast, on issue-time rain, beat the climatology baseline and production's unmapped
forecast at leads 1 to 3 over one winter at Scottish Water's monitored overflows, and whether its level held. This is
the first live evidence for the forecast the trial would show, and the first unseen evidence at leads 1 to 3.

**Cannot.**

- It is not Gate B. Gate B's rule, arm and verdict are its own. This arm is monitoring of a limited release.
- One winter, part of it. No summer, when SEPA's bathing season runs.
- Overflow-days, not the level a swimmer sees at a loch.
- Live polls, not Scottish Water's annual record. The polls miss what the feed misses.
- Not E. coli. Not a statement about any one loch: few of the 1,485 overflows sit upstream of the trial's spots.
- A failed M3 does not show the map is worse. A passed M1 does not show the trial is safe to rely on.

## 8. What follows each outcome

- **All three hold.** Recorded as live support for the trial's forecast at leads 1 to 3. The trial's page line "Not
  yet confirmed on live data" may then be reworded, which is Ethan's decision. Outside review is still owed.
- **M1 does not hold, with at least 200 spill-days.** The mapped forecast is not shown better than the baseline
  live. Ethan is told the live evidence does not support the trial being on. Next deliverable: a diagnosis by lead,
  month, rain age, data state and covariates.
- **M2 does not hold, M1 does.** The ranking held and the winter level did not. Next deliverable: the mapped
  hindcast's level by calendar month on 2022 to 2025, offline. Any refitted map gets its own protocol and its own
  arm. The pinned map is not refitted on this window.
- **M3 does not hold, M1 does.** The map is not shown better than England's calibration live. The trial's case for
  the map then rests on the hindcasts. Recorded and reported to Ethan.
- **Fewer than 200 spill-days, or under 30 target days.** Too few to say. Logging continues and the read moves to
  the first week of April 2027, stated here so it is not chosen after a look.

## 9. Cost, limits and stopping

- **Open-Meteo: no calls.** The arm reuses the rows the existing shadow has already computed. If a later change
  needs rain of its own, it stops and the number is recorded first.
- **Build time.** One insert of about 7,400 rows on a build the existing shadow logs. Measured in section 12.
- **Size.** About 7,400 rows a logged build. Measured in section 12.
- **Stop rule.** The arm stops by itself when the map or spill model changes (fallback rows only). To stop it by
  hand, revert the PR. The file can be deleted without touching the existing shadow.
- **Nothing is published.** The file is in the state directory only. No page, release asset or site file reads it.

## 10. Found on the way, not acted on

**From 1 January 2027 every Scottish forecast falls to default covariates.** Established: the covariate rule takes
the return year before the forecast's year, and the committed file ends at 2025
(`sw_covariates.covariates_for(cov, 2027)` returns 0 rows; 1,287 for 2026). Scottish Water plans its 2026 file for
March 2027. So from 1 January the existing shadow, this arm and the trial itself would all run on the median fill,
with the arm's stamp unchanged (`cov=sw:c2f2f654`). On Gate A's rows default covariates gave a level of 0.20 and a
BSS of −0.28. This touches Gate B's January rows. It needs a decision before 1 January 2027: for example "the
latest return year the file holds", stated as a dated amendment to the shadow's rule before it takes effect. Not
changed here, because the brief forbids altering the existing arm's rules. This arm logs `covariates` per row, and
its read reports November to December and January apart.

**Gate B's arm breaks into a new piece whenever the E. coli model changes.** Established: its arm is the version
stamp less the code part, and the stamp carries `ecoli=`. The E. coli model was refitted on 12, 13, 17 and 25
October. *Inferred:* that is why the 1 November read found five pieces of 3 to 7 days, each too short. The E. coli
model does not enter a spill chance. How Gate B's pieces are combined in February is a decision to state before the
read. Not changed here.

## 11. Continuation

| Field | Content |
|---|---|
| Identity | SCOT-TRIAL, arm `scotland-map-v1`; this file; `src/dipcast/scottish_shadow_map.py` |
| Evidence so far | None from this arm. The map: 2025 check (exploratory), 2021 backtest at lead 0 (confirmation, 83 overflows) |
| Stage | Running comparison (shadow), from the first build after the PR merges |
| Next deliverable | The read, on or after 3 February 2027, with Gate B. Before it: a counts-only readiness check one week after logging starts |
| Budget | No Open-Meteo calls. State file size in section 12 |
| Release route | None from this arm alone. It informs Ethan's decision on the trial's switch and wording |

## 12. Added after the arm was built, 13 November 2026

Sections 1 to 11 are as pushed in b9128bb2, before any arm code. Nothing in them was changed. This section holds
what was measured afterwards. No real forecast or outcome was used: the rows were made up, in the shape of a real
build (1,485 overflows, five days).

- **Tests.** 14 in `tests/test_scottish_shadow_map.py`. One runs the same build with and without the new arm and
  finds the existing shadow's rows and stamp identical.
- **Build time.** 0.05 s for a build's insert (median of 160; the first, which makes the file, 1.5 s).
- **Size.** 39 MB for 1,188,000 rows: 80 days at two logged builds a day, 0.24 MB a build. The made-up chances were
  random, which compresses worst. *Inferred:* builds run about every 2.9 hours and the existing shadow logs those
  issued by 08:00, so two or three a day, 40 to 60 MB by 31 January. The state directory is saved to the Actions
  cache on every run.
- **Open-Meteo.** No call. The module does not import the rain code, and a test checks that.
- **To start logging.** Merge the PR. `DIPCAST_SCOTTISH_WATER` has been `1` since 11 October, and the arm rides on
  that shadow's run. The first build after the merge that the existing shadow logs is the arm's first issue.
