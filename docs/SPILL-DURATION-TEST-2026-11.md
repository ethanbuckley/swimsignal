# How long a running spill goes on: the test, stated before any 2025 score

Written 30 October 2026, before any candidate was scored on 2025. It is committed and pushed before the first `run`.
Results go below the line at the end. Nothing above that line changes after a 2025 result is seen.

Harness: `scripts/spill_duration_test.py` (`describe`, `check`, `run`). Tests: `tests/test_spill_duration_test.py`.

## Why

The spot page's "When will it clear?" comes from `transport.clear_time`. It assumes every overflow discharging now
stops now, and says so: "If the overflow discharging upstream stops now, the spill should have passed and died off by
Saturday 22:47" (`levels.js`, `clearWords`; `index.html`, `clearSentence`). The wording is honest. The time it gives
is the earliest the risk could clear, and the 2024 figures below show that most running spills do not stop now.

A proposal of 30 October ("forecast pollution events from onset through recovery") suggested learning spill onset
and spill duration separately, and starting with duration. Onset is what the spill model already forecasts each day.
Duration is not modelled anywhere. The live-status work (#254, #262) uses "spilling at 00:00 UTC" as an input to the
daily chance, which is a related idea at a coarser grain: it asks whether a day will see a spill, not when a running
spill will end.

This test asks one question: **given that an overflow is spilling now and has been for e hours, can the chance that it
is still spilling 1, 3, 6, 12 and 24 hours from now be told better than by its company and e alone?**

A pass would let a later change say "if it stops when spills like it usually stop" next to "if it stops now". That
wording is not part of this test.

## Seen before writing

- **The EA summary of 2024 and 2025 events** (`data/processed/ea_events_summary.csv`): per company and year, event
  counts, median event length, the share under 15 minutes and the median gap between events. Both years were seen.
  These are raw-event figures, not scores of anything below.
- **The live-status test's 2024 tables** (`docs/LIVE-STATUS-FEATURE-TEST-2026-10-spells-2024.csv`,
  `-persistence-2024.csv`).
- **`describe`, 2024 only** (`-describe-2024.csv`, `-describe-2024-gaps.csv`). No 2025 event, rain or score was read.

  Merging changes the count a lot. All nine, 2024:

  | Events joined when the gap is under | Spills | Median length | 90th percentile | Share over 24 h |
  |---|---|---|---|---|
  | 0 (overlaps only) | 1,838,005 | 0.13 h | 2.5 h | 1.2% |
  | 15 minutes | 797,366 | 0.5 h | 7.75 h | 3.4% |
  | **1 hour (chosen)** | **483,102** | **1.27 h** | **15.1 h** | **5.9%** |
  | 3 hours | 372,536 | 2.25 h | 19.75 h | 8.3% |

  At a 1-hour gap, the whole UTC hours at which a spill was running (first 72 hours of each spill only), and the share
  still running h hours later:

  | Spill had run for | Issue hours | +1 h | +3 h | +6 h | +12 h | +24 h |
  |---|---|---|---|---|---|---|
  | any time under 72 h | 2,798,353 | 0.88 | 0.74 | 0.61 | 0.46 | 0.31 |
  | under 1 h | 352,378 | 0.65 | 0.41 | 0.27 | 0.16 | 0.08 |
  | 3 to 6 h | 375,225 | 0.87 | 0.69 | 0.53 | 0.35 | 0.20 |
  | 24 to 48 h | 472,813 | 0.97 | 0.91 | 0.83 | 0.70 | 0.52 |

  By company, still running 6 hours later: from 0.52 (United Utilities) to 0.68 (Anglian, Thames, Wessex).

  **What this already says, without a model.** At a typical hour a spill is running, it is more likely than not to
  be running 6 hours later. So the page's "if it stops now" time is usually early, often by many hours. This is a
  description of 2024, not a forecast test.

## Choices fixed now

- **Spills.** Each overflow's EA start/stop events (2024 and 2025 files, `training.load_events`), joined when they
  overlap or when one starts less than **1 hour** after the spill so far ended (`merge_spells`). Why 1 hour: the
  site's poller runs inside the build, with a median gap of 1.05 h between polls (28 Sep to 20 Oct 2026,
  `live_status.MAX_GAP_H`'s note). A stop and restart under an hour apart is mostly invisible to the site, and to a
  swimmer it is one spill. The table above shows the choice matters. It was made after seeing 2024 only.
- **Rows.** Every whole UTC hour *t* at which a spill runs (start ≤ *t* < end) and began less than **72 hours**
  before (`issue_rows`). Training: *t* in 2024, before 31 Dec 00:00. Scoring: *t* in 2025, before 31 Dec 00:00, so
  every label up to 24 hours ahead lies inside the files. A spill begun in 2024 and running into 2025 keeps its true
  elapsed time. Why 72 hours: past three days the overflow is a long-runner (often groundwater-fed) and the page
  already treats it as discharging; the clearing time matters for storm spills.
- **Overflows.** Only those with a position and the year before's return (`training.site_years`), as in every
  model test. The year before's return gives the site figures, filled as `features.site_static_features` fills them.
- **Labels.** For each horizon h in 1, 3, 6, 12, 24 hours: 1 if the same spill is still running at *t* + h
  (remaining time > h), else 0 (`labels`).

## Predictors

All are fitted on the 2024 rows only.

- **B0, stops now.** Every probability 0. The page's present assumption. Reported, not a hurdle: any sensible
  predictor beats it.
- **B1, company × elapsed.** The 2024 share still running at each horizon, per company and elapsed bin (0-1, 1-2,
  2-3, 3-6, 6-12, 12-24, 24-48, 48-72 h). A cell with no 2024 rows takes the company's all-bins share. **This is the
  hurdle.** It is what a page could show tomorrow from a lookup table.
- **C1, the candidate.** One `HistGradientBoostingClassifier` per horizon (300 iterations, learning rate 0.05, 31
  leaves, at least 200 rows a leaf, seed 0; company as a category), then forced not to rise with the horizon
  (`monotone`). Inputs, each known at the issue hour:
  - elapsed hours; company; UTC hour of day; day of year as sine and cosine;
  - from the year before's return: log spills, log spill hours, log hours per spill, EDM operation;
  - hours this overflow spilled in the 7 days before this spill began (`history_hours`);
  - ERA5-Land rain at the overflow's cell in the 6, 24 and 72 hours before *t*.
- **C2, reported only.** C1 plus ERA5-Land rain in the next 1, 3, 6, 12 and 24 hours. This is perfect future rain, so
  it is an upper bound on what forecast rain could add. It is not a candidate for production and has no conditions.

No setting above is tuned on 2025. If one is changed after a 2025 score is seen, the run is void and the change is
recorded below the line.

## Scoring

On the 2025 rows:
- **Integrated Brier score:** the mean over the five horizons of the Brier score. Lower is better.
- Per horizon: Brier and ECE (10 equal-width bins).
- Per company, and for all nine.
- **Uncertainty.** Paired differences (candidate minus B1) get 95% intervals from a cluster bootstrap by ISO week of
  the issue hour: 2,000 resamples from `numpy.random.default_rng(0)`, every row of a week drawn together. The same
  draws serve every company, horizon and subset.
- **Reported, not conditions:** B0's scores; C2's scores; scores with one weight per spill instead of one per hour
  (each hour-row counts 1, so long spills count more; the per-spill view shows whether a gain only comes from them).

## Conditions

**Duration is predictable beyond company and elapsed time** if all of these hold for C1:

1. **A gain.** All nine together:
   - (a) C1's integrated Brier is lower than B1's, with the 95% interval of the difference wholly below zero;
   - (b) the gain is at least **2%** of B1's integrated Brier. With millions of rows a tiny gain can be "significant".
     2% is a judgement, not derived: below it, the windows a page would show would barely move.
2. **No horizon clearly worse.** At no horizon does the interval of the difference lie wholly above zero.
3. **No company clearly worse.** At no company does the interval of the integrated difference lie wholly above zero.
4. **Reliability.** At every company and horizon, C1's ECE is no higher than B1's, or it is at most 0.02.
5. **Not worse on new spills.** On rows where the spill began less than 3 hours before the issue hour, the interval of
  the difference does not lie wholly above zero. These are the spills where a clearing time first appears on a page.

## What a pass means, and what a fail means

- **2025 has been used to judge other models** (D2, the neural challenger, the live-status test, nine-company v2).
  None of them predicted duration, so their choices were not tuned to this target. Still, 2025's storms have been
  looked at many times. **A pass deploys nothing.** It earns a wording proposal and a confirmation on 2026 data,
  stated before it runs: spills read from SwimSignal's own polls (`live_history.parquet`), or the EA 2026 files when
  all nine are out.
- **A fail with B1 well calibrated** still leaves B1. A lookup table by company and elapsed time is simple enough to
  show without a model, and B1's calibration on 2025 is reported. Whether to put it on the page is a separate
  decision, with its own wording test.
- **A fail of both** is the record. Duration is not pursued again without a new input (for example, live river
  level at the overflow).

## Production feasibility (stated, not checked)

- **Elapsed time is available.** The live feeds give `latest_event_start` for each overflow (`live_latest.parquet`).
  *Not checked:* whether the feeds' event start matches the start of a spill merged at 1 hour. A feed that splits a
  spill into short events would make elapsed time look short. Production would need to merge from
  `live_history.parquet`, which the poller already keeps.
- **Rain before *t*** is what the forecast already fetches (the past hours of the Open-Meteo call). No new calls.
- **Future rain (C2)** would need forecast rain at hourly lead, which the forecast already has for the five days.
  C2 is not tested with forecast rain here.

## Running it

- No network. No Open-Meteo calls. Reads `data/processed/ea_events_*.parquet`, `annual_returns.parquet` and the
  ERA5-Land caches under `data/cache/rain` and `data/cache/rain_nine`.
- Wait for `heavy-run.lock` if another session holds it.
- `DIPCAST_ROOT=<checkout with data> uv run python scripts/spill_duration_test.py check` runs the whole pipeline on
  2024 alone (first half fits, second half scores) and writes nothing to docs.
- `run` writes `-scores.csv` and `-checks.json` beside this file. **It waits for approval of this statement.**

## Check of the code, 2024 only (run after the conditions above were written; nothing above was changed)

`check`, 30 October 2026, 208 s on the main checkout's data: 2,732,148 issue hours in 2024 for overflows with a
position and a 2023 return; every rain input finite (no missing hours). Fitted on issue hours before 1 July 2024,
scored on the rest of 2024:

| Predictor | Integrated Brier, 2024 July-December |
|---|---|
| B1, company × elapsed | 0.1738 |
| C1 | 0.1667 (4.0% lower) |
| C2, perfect future rain | 0.1535 (11.6% lower) |

This is a split inside the training year, with no interval and no other condition checked. It shows the harness runs
end to end. It is not evidence for or against the conditions, which are judged on 2025 only.

---

## Results

**Approval.** Ethan approved the statement as written, 30 October 2026 about 17:50 UTC ("Approved, run it"), on
statement head 2c8cae0. Nothing above the line was changed after that.

**Run.** 30 October 2026, about 17:55-18:02 UTC, on main checkout data, commit 6cb3b5d. One run. No network, no
Open-Meteo calls, no setting changed. 2,952,154 events in both files became 802,781 spills; 2,732,148 issue hours in
2024 (training) and 1,582,953 in 2025 (scoring). Files: `-scores.csv`, `-checks.json`.

### Verdict: C1 fails as stated (condition 4, reliability)

| Condition | C1 |
|---|---|
| 1a gain, interval below zero | pass |
| 1b gain at least 2% of B1 | pass (11.6%) |
| 2 no horizon clearly worse | pass |
| 3 no company clearly worse | pass |
| 4 reliability | **fail** |
| 5 not worse on new spills | pass |

### Scores, 2025, all nine

| Predictor | Integrated Brier | Difference from B1 | 95% interval |
|---|---|---|---|
| B0, stops now (the page's assumption) | 0.3544 | +0.1838 | |
| B1, company × elapsed | 0.1705 | 0 | |
| **C1** | **0.1507** | **−0.0198** | −0.0242 to −0.0148 |
| C2, perfect future rain (reported only) | 0.1332 | −0.0373 | −0.0405 to −0.0338 |

- **Every company gains**, each with its interval wholly below zero: from −0.0135 (Yorkshire) to −0.0292 (Thames).
- **Every horizon gains:** −0.0083 at 1 h, −0.0189 at 3 h, −0.0260 at 6 h, −0.0279 at 12 h, −0.0179 at 24 h.
- **New spills** (begun under 3 h before): −0.0245 (−0.0288 to −0.0203).
- **One weight per spill** (reported): B1 0.1535, C1 0.1251. The gain does not come only from long spills.

### Where condition 4 fails

Condition 4 needs, at every company and horizon, C1's ECE no higher than B1's or at most 0.02. It fails in 24 of the
45 company-horizon cells:

| Company | Horizons failing | C1 ECE at 24 h | B1 ECE at 24 h |
|---|---|---|---|
| Anglian | all five | 0.086 | 0.069 |
| Yorkshire | all five | 0.052 | 0.037 |
| United Utilities | 3, 6, 12, 24 h | 0.050 | 0.016 |
| Thames | 3, 6, 12, 24 h | 0.023 | 0.015 |
| South West | 6, 12, 24 h | 0.066 | 0.015 |
| Northumbrian, Severn Trent, Wessex | 24 h only | 0.026, 0.029, 0.032 | 0.025, 0.025, 0.006 |
| Southern | none | 0.033 | 0.067 |

All nine together, C1's ECE is 0.021 at 12 h and 0.030 at 24 h (B1: 0.014 and 0.019).

**B1 is not well calibrated at every company either.** Its ECE is over 0.02 at Anglian, Southern, Yorkshire,
Northumbrian and Severn Trent at the longer horizons (up to 0.070). All nine together, it stays under 0.02 at every
horizon.

*Not checked:* whether C1's chances are too high or too low where it misses. The run kept scores, not predictions.

### What this means

- **The page's assumption is the worst of everything scored.** "Stops now" scores 0.354, twice B1's 0.171. This is
  the one firm product finding: the "if it stops now" time is the earliest possible, not a typical one.
- **Duration is predictable beyond company and elapsed time.** The gain is large, holds at every company and horizon,
  and holds on new spills. What fails is how well the chances match outcomes, mostly at 12 and 24 hours and at five
  companies.
- **By the statement, nothing is adopted.** C1 is not pursued as written. The statement said a fail of C1 with B1
  well calibrated leaves B1 as an option; B1 is well calibrated for the nine together but not at every company.
- **Perfect future rain roughly doubles the gain** (C2). Forecast rain would give less; how much is not tested.

### What could follow (not decided, each needs its own statement)

1. **A recalibrated C1:** C1 with a calibration step fitted on 2024 only (for example per company and horizon).
   It cannot be judged on 2025, which has now judged C1. It would need 2026 data: the EA 2026 files when all nine are
   out, or spills read from SwimSignal's own polls.
2. **Page wording without a model:** a dated, plain sentence beside the clearing time, from 2024-25 counts only, for
   example how often a spill already running is still running six hours later. That is a description, not a
   forecast, and needs its own wording check.
3. **Leave it.** The present wording already says "if it stops now".

### Correction and diagnostics, 30 October 2026 (after the verdict; the verdict is unchanged)

- **"The one firm product finding" above was wrong.** The page says "if it stops now", a stated scenario. Scoring B0
  as a forecast that every spill stops at once is a deliberately weak baseline, and it does not measure how accurate
  the page's clearing times are. The firm evidence is C1 against B1. How long the water takes to recover is a
  separate question this test does not touch.
- **The target joined events across pauses under an hour.** 6.9% of the 2025 issue hours fall in such a pause, when a
  monitor would show "not discharging". On rows a monitor would show as discharging, C1 still gains 11.7% over B1
  (10.7% with "monitor reports a discharge" as the label). Details, the calibration breakdown, the January-August
  2026 records and a draft follow-up: `docs/SPILL-DURATION-DIAGNOSTICS-2026-11.md`.
