# Scotland hindcast, Stage A: Gate A result, 1 November 2026

Task S3 of [the Scotland plan](SCOTLAND-PLAN-2026-10.md), section 6. The rule is Gate A in the docstring of
`scripts/hindcast_scotland.py`, committed on its own on 11 October 2026 (106d1d6) before any Scottish forecast was
scored. Nothing in it was changed. Summary scores, no rows: `SCOTLAND-HINDCAST-2026-11.json`. Contains Scottish Water
data licensed under the Open Government Licence v3.0.

## Verdict: PASS

All four parts were tested and all four pass. The English spill model, trained on United Utilities and not refitted,
beats each Scottish overflow's own earlier-years spill rate, at lead 0 and at forecast leads 1 to 3.

This is Stage A only. It does not release a Scottish forecast. Stage B (live shadow scores) and Stage C (outside
review) still come first. And the model forecasts about 28% fewer spill-days than happened (section 4), which a page
would have to fix or say.

## 1. What ran

- Code: main at 4deeedd3, unchanged. The 21 tests in `tests/test_hindcast_scotland.py` pass.
- Run: 1 November 2026, from a worktree. `DIPCAST_ROOT` on the main checkout, read only; `DIPCAST_CACHE` and
  `DIPCAST_STATE` in a scratch folder. The scratch rain folder linked to the main checkout's rain files and held the
  new ones. Output written to scratch, then copied here.
- Inputs checked by SHA-256 before and after the run, all unchanged: `sw_events.parquet`, `sw_covariates.parquet`
  (identical to the copy committed 11 Oct in d0656520), `scotland_rain_cells.csv`, `spill_model_holdout_2025.pkl`
  and `spill_model.pkl` (both dated 12 Sep, before Gate A was written), and S1's cached API answer.
- The gate's model is the 12 Sep holdout model. The deployed model has changed since (soil moisture, 26 Oct, among
  others). This result is about the 12 Sep model; the production model of 12 Sep is the check row.
- Model code changed since S3 was committed (5c105464) only in ways this path does not use: `features.py` gained
  `fill_covariates` for the build, with the same defaults; `spill_model.py` gained two stored settings.
- Rain fetched for the run, from this Mac, on 1 Nov 13:30-15:25 UTC: 139 ERA5-Land cell-years (about 3,630 calls)
  and 133 files of 2025 archived forecasts (about 3,620 calls). About 7,250 Open-Meteo calls, no 429. Two stops were
  this Mac's DNS failing and one a truncated reply; each was resumed, and cached files are never asked for twice.

## 2. Gate A, part by part

Brier skill score (BSS) of the Scottish-covariates arm against the earlier-years baseline. 95% intervals from 2,000
cluster-bootstrap draws (overflows × ISO weeks, seed 0). A part passes if the lower end is above zero.

| Part | Overflows | Spill-days | BSS | 95% interval | Result |
|---|---:|---:|---:|---|---|
| G1. Set G, 2022-25, lead 0 | 254 | 52,891 | 0.18 | 0.13 to 0.23 | Pass |
| G2. 2025, lead 1 | 233 | 15,604 | 0.18 | 0.11 to 0.24 | Pass |
| G3. 2025, lead 2 | 233 | 15,604 | 0.15 | 0.08 to 0.21 | Pass |
| G4. 2025, lead 3 | 233 | 15,604 | 0.13 | 0.06 to 0.20 | Pass |

Set G is the 693 overflow-years of 2022 to 2025 that have a count in that year and the year before, emergency
overflows left out. Every 2025 row of G had archived forecasts, so the lead tests use all of them. At lead 0 on the
same 2025 rows, BSS is 0.21 (0.15 to 0.28). Skill falls with lead, as in England.

## 3. Arms and baselines, set G, lead 0

Base rate: 20.9% of overflow-days had a spill (253,140 overflow-days, 210 weeks).

| Forecast | Brier | BSS vs earlier years | BSS vs flat | AUC | Log loss | Level |
|---|---:|---|---|---:|---:|---:|
| Scottish covariates (the gated arm) | 0.114 | 0.18 (0.13 to 0.23) | 0.31 (0.28 to 0.34) | 0.87 | 0.373 | 0.72 |
| Default covariates (20 spills, 100 h, 90%) | 0.179 | −0.28 (−0.38 to −0.20) | −0.08 (−0.12 to −0.04) | 0.76 | 0.706 | 0.20 |
| Production model of 12 Sep, Scottish covariates (check) | 0.117 | 0.17 (0.10 to 0.22) | 0.29 (0.26 to 0.33) | 0.86 | 0.393 | 0.69 |
| Earlier years (the gate's baseline) | 0.140 | 0 | 0.15 (0.12 to 0.19) | 0.78 | 0.432 | 1.01 |
| Flat (uses the answer) | 0.165 | −0.18 | 0 | 0.50 | 0.513 | 1.00 |

Level is the sum of forecasts divided by spill-days: 1 is right on average.

**The covariates carry the result.** With England's defaults the model loses to both baselines and forecasts a fifth
of the spill-days. Scotland needs each overflow's own published spill count from the year before. S2 provides it,
and the live shadow (S5) already uses it.

**Not run.** The calibration arm needs 92 more cell-years of rain (about 2,400 calls). Set N (overflows first counted
in 2025, mostly) needs 409 (about 10,600 calls). Both are reported-only parts of the pre-stated rule, so fetching
their rain and running them later changes no verdict.

## 4. The level: the model forecasts too few spills

Reliability, Scottish covariates:

| Forecast band | Overflow-days | Mean forecast | Observed |
|---|---:|---:|---:|
| 0.0-0.1 | 168,254 | 0.027 | 0.065 |
| 0.1-0.2 | 27,166 | 0.143 | 0.269 |
| 0.2-0.3 | 14,257 | 0.246 | 0.397 |
| 0.3-0.4 | 9,495 | 0.347 | 0.498 |
| 0.4-0.5 | 7,302 | 0.448 | 0.580 |
| 0.5-0.6 | 6,193 | 0.549 | 0.634 |
| 0.6-0.7 | 5,649 | 0.650 | 0.702 |
| 0.7-0.8 | 5,563 | 0.750 | 0.756 |
| 0.8-0.9 | 5,650 | 0.849 | 0.832 |
| 0.9-1.0 | 3,611 | 0.941 | 0.886 |

In the bands from 0.1 to 0.6, spills happened 8 to 15 points more often than forecast. In the lowest band they happened 2.4 times as often. Overall
the model forecasts 72% of the spill-days that happened.

Gate A's docstring inferred the opposite: labels here drop events of 15 min 30 s or less, while the training labels
keep them, so the model should forecast about 1.16 times too many. It forecasts too few instead. Why is not known.
The same docstring names one effect that pushes this way: S2 counts last year's spills after the short-event cut, so
a Scottish overflow reads quieter to the model than an English one with the same discharges. That has not been
measured.

What it means for a page: the ranking is good (AUC 0.87), but a Scottish probability shown as it stands would
understate the chance of a spill. The calibration arm is the pre-stated test of a fix and has not run.

## 5. Groups (reported, not gated)

| Group | Overflows | Spill-days | BSS vs earlier years |
|---|---:|---:|---|
| 2022 | 92 | 7,971 | 0.23 (0.15 to 0.31) |
| 2023 | 173 | 14,086 | 0.14 (0.05 to 0.21) |
| 2024 | 195 | 15,230 | 0.17 (0.10 to 0.25) |
| 2025 | 233 | 15,604 | 0.20 (0.14 to 0.27) |
| Wet days (over 10 mm on the day and the day before; base rate 42.8%) | | 28,707 | 0.25 (0.20 to 0.30) |
| Dry days (base rate 13.0%) | | 24,184 | 0.13 (0.06 to 0.19) |
| CSO | 160 | 24,656 | 0.23 (0.19 to 0.27) |
| SSSO | 80 | 25,810 | 0.14 (0.05 to 0.22) |
| Not in the live API | 14 | 2,425 | 0.12 (−0.10 to 0.34) |

Every year passes on its own. SSSOs spill on 32% of their days and are forecast less well than CSOs.

By local authority (in the JSON): 18 have scores. In 8 the interval reaches below zero: Argyll and Bute, Dumfries and
Galloway, East Lothian, Perth and Kinross, Renfrewshire, Scottish Borders, Stirling, and the overflows not in the
API. Only Perth and Kinross has a point estimate below zero: −0.07 (−0.39 to 0.20), 7 overflows. Four of the eight
are flagged small. This is a description, not a finding about those places.

## 6. Next

| Field | Content |
|---|---|
| Stage | Stage A passed. Stage B (shadow, `scottish_shadow.py`) has been on since 11 Oct (`DIPCAST_SCOTTISH_WATER=1`); the 1 Nov 08:36 UTC build scored 86,368 shadow rows. Gate B's readout is in the build's state, not in the log, and was not read here |
| Supported claim | The 12 Sep English model, with Scottish covariates, ranks Scottish overflow-days better than their own history, to 3 days ahead, 2022-25. It forecasts about 28% too few spill-days |
| Next deliverable | 1. The calibration arm and set N: fetch their rain (about 13,000 calls, two days on the free tier) and rerun; the verdict cannot change. 2. Gate B's readout from state at the end of the shadow window (plan: Nov 2026 to Jan 2027, at least 200 scored spill-days). 3. Outside review (Stage C) |
| Owner | Claude for 1 and 2; Ethan for the reviewer invitation (Stirling, drafted, unsent) |
| Milestone | Proposed here: Gate B read in February 2027, after the plan's window; review before the 2027 pre-registration deadline, 30 April 2027 |
| Release route | Nothing Scottish is published until Gates A and B pass and a reviewer agrees. A Scottish page would also need the level fixed or stated (section 4) |
