# The live-status input in shadow: the test, stated before any shadow forecast is read

Written 20 October 2026. It is committed and pushed before any shadow forecast is logged by a build whose rows
count, and before any shadow row is read, a local build's included. Results go below the line at the end.
Nothing above that line changes after a result is seen, except the window's dates, which are written under
the line when the code goes live. **Ethan approves this statement by merging the PR that carries it.** Nothing
is logged on the live site before that merge.

## Why

PR #254 (`docs/LIVE-STATUS-FEATURE-TEST-2026-10.md`) added each overflow's own recent spill status to the
spill model as three inputs, one candidate per lead 0 to 4, fitted on the EA's 2024 start/stop files. On 2025
it passed all five of its conditions at every lead. It deployed nothing, and named two blocks:
1. **No confirmation on 2026 data with the status read from SwimSignal's own polls.** The candidates were
   trained on EA events; production would read the live feeds.
2. **No rule for a missing status.** With every status input missing, a candidate scored 0.0537 to 0.0653 on
   2025, worse than no status at all. It reads "missing" as "wet spell".

This test is the confirmation #254 asked for. The fallback rule is part of the candidate.

### What #254 compared with, and what this compares with

#254's baseline was D2's model (`spill_model_nine_2024.pkl`, Brier 0.0362 on 2025), not production. D2 was not
adopted (PR #251). Production is `spill_model.pkl`, fitted on United Utilities 2023-25, then the lead
calibration map (`lead_calibration.json`). On 2025 it scored 0.0356 for the nine companies, in-sample at
United Utilities (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`). So #254 showed the status inputs help D2's
model. It did not show the candidates beat what the site shows. **This test compares the candidates with what
the site shows**: the calibrated chance `p_cal` in the forecast log.

## Seen before writing

All from the `state` release of 20 Oct 2026 05:44 UTC, downloaded read-only.
- **The poller's cadence** (`poll_log.parquet`). The poll runs inside the site build. 339 polls from 16 Sep;
  over 28 Sep to 20 Oct, 266 gaps between polls: median 1.05 h, 95th percentile 6.43 h, 99th 7.30 h, longest
  7.71 h. 58 gaps over 4 h, 20 over 6 h, none over 8 h. From 6 Oct the median gap was 2.11 h. Polls per day
  ranged from 4 (8 and 9 Oct) to 31 (3 Oct).
- **How many overflows would have a known status** under the rule below, at the poll of 20 Oct 05:35 UTC,
  computed by the code in this PR on that state. 88.7% of the 14,199 overflows in the live feeds.

  | Company | In the feed | Data state "live" | Status known (the rule below) |
  |---|---|---|---|
  | Anglian | 1,438 | 95.8% | 91.9% |
  | Northumbrian | 1,575 | 98.0% | 94.3% |
  | Severn Trent | 2,416 | 99.4% | 97.6% |
  | South West | 1,342 | 96.9% | 94.6% |
  | Southern | 996 | 99.9% | **0.0%** |
  | Thames | 573 | 94.9% | 90.6% |
  | United Utilities | 2,255 | 98.8% | 97.3% |
  | Wessex | 1,427 | 98.6% | 94.0% |
  | Yorkshire | 2,177 | 98.4% | 96.6% |

  Southern Water stamps a record only when it changes (`ingest.live`, `feed_on_change`). In a quiet spell its
  freshest stamp is over 6 hours old, so the coverage file counts its polls as stale, and every Southern
  overflow had a stretch over 8 hours without a current reading in its week. So Southern falls back to
  production throughout, and the test says nothing about Southern. Of the 12,593 known, 8 were spilling at
  the poll. The distribution of the inputs was looked at (mean spill-days in the week 0.29, the most 7);
  nothing was compared with any outcome.
- **The published live scores** (`verification_live.json`, production only): 19 scored target days, 29 Sep
  to 19 Oct, 18,786 to 19,275 scored rows and 492 to 506 spills at each lead. Spill rows by company over all
  leads: United Utilities 1,107, Yorkshire 450, Anglian 278, Severn Trent 199, Wessex 128, South West 88,
  Thames 85, Northumbrian 53, Southern 51.
- **The forecast log**: 2,934,555 overflow rows from 12 Sep, about 17,700 a build.

No shadow forecast had been computed for a scored day, and no shadow row had been read.

## The candidate (fixed now)

**The five models.** PR #254's candidates, unchanged, SHA-256 beginning `deb5e1e5ee64`, `e0756b1e9748`,
`ed5bb2b9a39e`, `5180de7086c6` and `ecc835c96d70` (leads 0 to 4). They move from `swimsignal-private` into
`data/processed/live_status/`. The code runs them only if each file's hash matches. No lead calibration map:
#254 scored them without one.

**The three inputs, from the polls**, as #254's "How production would compute the three inputs" said, for a
forecast issued on local day *D* (`model/live_status.py`):
- `spilling_at_issue`: 1 if the build's own poll reads the overflow as discharging (status 1), else 0.
- `spill_days_7d`: spill-days among local days *D*−7 to *D*−1, by `forecast_log.observed_spill_days`, the rule
  the live labels use.
- `spill_hours_24h`: hours spilled on local day *D*−1, at most 24. The intervals are the ones
  `observed_spill_days` uses (each poll's latest event, a running spill ending at the poll that saw it),
  with overlapping intervals merged. *Why the day before and not the 24 hours before the build:* in training
  the two were the same, and every training row with hours above 0 had at least one spill-day in its week.
  The last 24 hours would include this morning, which `spill_days_7d` leaves out.
- Lead *k*'s candidate gives the chance for the local day *k* days after *D*. Rain, season and covariates
  are production's own for that day, from the same site-day table (`forecast.spill_probabilities`).

**When the status is known, and when it is stale.** An overflow's status is known only if all three hold:
1. The build's poll gives it a current status: data state `live` (status 0 or 1, from a feed that updated
   within 6 hours, the record not frozen; `ingest.live.data_states`).
2. Its latest current reading is at most **8 hours** before the forecast is issued.
3. Over its seven-day window, from 00:00 on *D*−7 to its latest reading, there is no stretch longer than
   **8 hours** without a current reading. The stretch running over *D*−7's first midnight counts whole.
   Readings are the half-hour slots in `live_coverage.parquet`.

**Why 8 hours.** It is the poller's cadence above: every gap between polls since 28 Sep was under 7.71 hours,
and 8 is the first whole hour above all of them. So the poller's timetable alone never makes a status stale.
A feed that stops, a frozen record, an offline monitor, or a run of polls that missed the overflow does. It is
also the scorer's `MAX_GAP_H`, set on 1 Oct from the same cadence. So the inputs trust the same polls the
labels are scored on. If GitHub runs the build less often than every 8 hours, statuses go stale and fall back.
That is counted, not prevented.

Slots are local half-hours, so on 25 Oct, when the clocks go back, a stretch that day can read up to an
hour short.

**The fallback.** Where the status is not known, the shadow forecast for that overflow, at every lead, is
production's `p_cal`, the figure the site shows. Where the day has no rain at the overflow's cell, the shadow
is NaN, as production is.

**Cost.** The shadow runs on the site-day table production has already built, so it makes **no Open-Meteo
request** (`tests/test_live_status_shadow.py` checks the request count is the same with it on and off). The
status table is read once per issue day per build, from files the build already holds.

## What is logged, and what is not published

`forecast_overflows` gains five columns, one value per overflow, target day and lead:
- `p_status`: the shadow forecast, with the fallback applied. NULL where there was no rain, and NULL in every
  build before this code.
- `status_known`: whether the overflow's status was known.
- `spilling_at_issue`, `spill_hours_24h`, `spill_days_7d`: the inputs. NULL where the status was not known.

**Nothing reads them but the check below.** The headline, the bar, the five days, alerts, cards,
`spots.json`, `verification_live.json` and `data/verification_live.csv` are unchanged.
`tests/test_live_status_shadow.py` checks that `forecast_point` returns the same result with the shadow on and
off. The forecast log is in the `state` release, which is public, as the ensemble members already are.

## The rows, the labels and the score

**Rows.** The scored live rows the build publishes (`data/verification_live.csv`), as
`forecast_log.verify_live` selects them: the latest forecast issued by 08:00 local on the issue day, overflows
with a live feed, the coverage rules, rain present. Each is joined to its `forecast_overflows` row by the same
selection (`scripts/live_status_shadow_check.py`). Both forecasts are scored on the same rows.

**Labels.** The poll-based live labels, PR #253's method: an overflow-day is a spill if a poll saw an event
touching that day; it is a dry day only if the coverage rules hold (at least 6 known polls, no gap over 8 hours,
seen again the next day). PR #253 measured that this method finds 99.7% of EDM spill-days over 2025 and adds
none. These are the labels `verify_live` already gives.

**Score.** The Brier score at each lead, 0 to 4, all nine companies together, shadow and production. The
difference is shadow minus production, row by row. Its 95% interval is **#254's bootstrap**: the ISO week of
the target day as the cluster, every row of a week drawn together, 2,000 draws from
`numpy.random.default_rng(0)`, one set of draws for every lead, company and subset, the 2.5th and 97.5th
percentiles.

*A caution, stated now.* A 28-day window holds 4 or 5 ISO weeks. A bootstrap over 4 or 5 clusters is crude:
roughly, the interval lies below zero only when the shadow wins in nearly every week. The same interval with
the target day as the cluster is reported beside it, not deciding. This is a choice for Ethan to confirm
before merging.

## Conditions, lead by lead

At lead *k* the shadow **is better** if all four hold, on the window's rows at lead *k*:

1. **A gain.** All nine together, the shadow's Brier is lower than production's, and the 95% interval of
   the difference lies wholly below zero.
2. **No company clearly worse.** At no company with at least 50 spill rows at that lead does the interval lie
   wholly above zero.
3. **Reliability.** At each such company, the shadow's ECE (`training.ece`, 10 equal bins, D2's definition)
   is no higher than production's, or it is at most 0.02.
4. **Not worse at a dry start.** On rows with a known status, not spilling at issue and no spill-day in the
   seven days before, the interval does not lie wholly above zero.

These are #254's conditions 1, 3, 4 and 5, with forecast rain only (the live window has no ERA5-Land
version) and production as the baseline.

## What follows

- **All four pass at lead *k*.** The shadow is eligible to become the default at lead *k*: the candidate where
  the status is known, production where it is not. The switch is its own PR, Ethan's call, and changes the
  model stamp, so the live scores split at it. Before it, the page's wording for the source of a day's risk
  needs a look: a spill already running would now raise the next days' levels too.
- **Any fails at lead *k*.** Production stays at lead *k*. The columns keep logging until a PR removes them.
- **Not enough data** (below). The window extends by 14 days, once. Then it is called inconclusive and nothing
  changes.

## The window

- **Opens** on the first target day whose 08:00 forecasts carried the shadow at every lead 0 to 4: four days
  after the first issue day with a shadow by 08:00 local. That is about four days after the merge. The date is
  written under the line once the code is live.
- **Runs** 28 target days. Read on or after the second day after the last, so the next-day coverage rule has
  run.
- **Minimum data.** At least 200 spill rows with a known status at each lead. The 19 scored days to 19 Oct had
  about 500 spill rows at each lead.
- **Sanity checks, run first** (the check stops on any failure): at least 99% of the window's scored rows have
  a logged `p_status`; the logged `p_cal` matches the published `forecast_calibrated` (mean absolute
  difference under 0.0001, the CSV's rounding); every fallback row's `p_status` equals its `p_cal`.

**The other windows.** The shadow changes no published figure, no `p_cal` and no member, so it does not disturb
the lead-calibration B window (`docs/LEAD-CALIBRATION-B-TEST-2026-10.md`, 18 Oct to 14 Nov) or the
ensemble-rain window (`docs/ENSEMBLE-RAIN-TEST-2026-11.md`). If the B map is adopted inside this window,
production's `p_cal` changes on that date. The comparison stays paired, since each row's shadow and production
come from the same build, and fallback rows take the new map too. The date is written under the line, and the
results are also given before and after it.

**If the candidates, the inputs or the fallback rule change** inside the window, the window ends the day
before. If that leaves fewer than 14 days, it restarts.

## Reported, not deciding

- The day-cluster interval beside the week-cluster one.
- Rows with a known status only, beside all rows.
- Rows spilling at issue and rows not spilling at issue. At lead 0 a spill still running at 00:00 makes the
  day a spill-day, so part of a lead-0 gain is the label's definition, as in #254. Here the status is the
  build's poll, later than 00:00, so that share is larger.
- The share of scored rows with a known status, by company and lead, and how many builds had no shadow.
- Per company at every lead: Brier, difference, both intervals, ECE.

## Expected, stated now (inferred, not conditions)

- **Lead 0 passes.** Most of #254's lead-0 gain came from rows spilling at issue, whose label is all but
  certain. The page's "right now" level already shows those spills, so a lead-0 pass says less about the page
  than about the overflow-day chance.
- **Leads 1 to 4 are open.** #254 gained 8% to 13% over D2 there. Production differs from D2: it is in-sample
  at United Utilities, the largest company in the live rows, and it carries a lead map. Poll-based hours
  under-count short events (Wessex's median event is 2 minutes). And the autumn window over-forecast in both
  2025 and 2026 (PR #253), which a candidate without a map may do more of.

## Not chosen, and why

- **Refitting the candidates on poll-shaped inputs.** There is no year of polls to fit on. #254's candidates
  are what was judged.
- **A lead map for the candidates.** It would be fitted on 2025, which has now judged three candidates.
- **Shadow only where the status is known, NULL elsewhere.** The forecast that would ship has a fallback, so
  the logged figure includes it. `status_known` gives the known-only rows.
- **Status at 00:00 instead of the build's poll.** #254 named the build's poll as what production would use.

---

## Results

Not yet run. The window's dates are written here once the code is live.
