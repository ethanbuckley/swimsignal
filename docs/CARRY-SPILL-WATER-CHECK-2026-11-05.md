# Carrying right now's spills onto later days: retrospective check, 5 November 2026

**Decision under the rule: NOT SUPPORTED.** The candidate lowers the mean squared error on affected cells by 1.6%.
The 95% interval for that change includes zero. It fails two of the three conditions. Exact level agreement falls
from 404 to 396 of 632 cells. At the High line it gains 2 hits and adds 6 false alarms.

This is a **retrospective, pre-specified check on logged data, not a prospective evaluation.** The outcomes
(12 October to 4 November 2026) had already been published on the Accuracy page before the protocol was written.
They were not used to choose the candidate or the protocol.

Code: `transport.carried_risk` (branch `claude/carry-spill-water-2026-11-05`, 8feec425). Replay and scoring:
[`scripts/replay_carried_risk.py`](../scripts/replay_carried_risk.py).

## The question

A spot's later days (lead 1-4) are forecast from rain-driven spill chances only. Spills already reported are
carried only onto today. Right now's live risk (`transport.live_now_risk`) counts each spill at full weight until
its water passes the spot, then dies off with T90, for 48 h. Candidate: for each later target day, use
max(day forecast risk, carried_risk at 12:00 Europe/London on the target day). `carried_risk` is right now's spills
run forward with no new spill (`transport.carried_risk(ov, now, [t])`). Does the candidate score at least as well
as the logged forecast against what was observed?

## Protocol (as fixed before any outcome was looked at, verbatim)

- Population: the spot-day cells the Accuracy page scores in `forecast_log.verify_spots` (latest forecast issued by
  08:00, target day, lead), restricted to leads 1-4, from the first day with travel times logged to the latest
  scored day. "Affected" cells: those where the issuing build's right-now live risk at a spot was at or above
  transport.CLEAR_CUT (0.1445), i.e. where a carry could apply.
- Baseline: the logged forecast index (`risk` in verify_spots). Candidate: max(baseline, carried risk at 12:00
  local on the target day from that issuing build's live state). Observed: verify_spots' `observed` index.
- Primary, on affected cells with both forecast and observation: mean squared error against observed (candidate vs
  baseline), and exact level agreement (forecast_log.spot_levels on both sides). Report counts, both metrics for
  both, and a cluster bootstrap (resampling spots, 2,000 draws, fixed seed) 95% interval for the MSE difference.
- Guard, on all scored lead 1-4 cells: hits, misses and false alarms at the High line (observed level High or
  above), baseline vs candidate.
- Decision rule: SUPPORT the change if on affected cells the candidate's MSE is not worse than the baseline's by
  more than 5% relative AND level agreement does not fall AND High-line false alarms do not rise by more than the
  hits gained. If fewer than 30 affected cells: report "too few to judge" with the numbers; the decision is then
  the owner's. Otherwise NOT SUPPORTED, with numbers.
- Label it a retrospective, pre-specified check on logged data, not a prospective evaluation.

### Details fixed in the script before scoring

The brief left these open. They were set in the script before it was first run, and were not changed afterwards.

- **"The issuing build's right-now live risk"** is the logged `now_risk` in `forecast_points` for that build and
  spot. The count using the replayed value is reported beside it (639 against 632).
- **T90.** The primary candidate calls `carried_risk` with its default T90, 72 h, as the brief's call does. Builds
  before PR #248's commit (b84cc771, 17 October) ran with T90 = 30 h. A sensitivity run uses the T90 in force at
  each issuing build, read from the commit in the logged `version`. The replay check uses the T90 in force.
- **Bootstrap.** Spots resampled with replacement, 2,000 draws, seed 20261105. The interval is the 2.5th and 97.5th
  percentiles of the pooled MSE difference.
- **Candidate rounding.** Candidate values are rounded to 6 decimal places, as `as_published` does for the baseline.

## Data and setup

- State release `state`, assets uploaded 5 Nov 2026 12:44 UTC: `dipcast.duckdb`, `live_history.parquet`,
  `live_latest.parquet`, `live_coverage.parquet`, `poll_log.parquet` and `verification_live.json`. They were
  downloaded to a git-ignored scratch directory, and the run used copies. SHA-256 hashes of the downloads were the
  same before and after the run. The main checkout was not read or written. No network calls were made apart from
  the download.
- `DIPCAST_ROOT` was the worktree. `DIPCAST_STATE` and `DIPCAST_CACHE` were scratch directories.
  `verify_spots(as_of=2026-11-05)` reproduces the published Accuracy page's in-advance block exactly: 3,101 cells,
  136 hits, 148 misses and 89 false alarms.
- The overflow list for each issue comes from the logged `forecast_overflows`: site_id, weight and travel_h, every
  row the build logged for its smallest lead. No river network trace was needed.
- The live state at issue time T comes from `live_history.parquet`. For each site it is the row with the largest
  begin <= T. Begin is status_start; if that is missing, the event start (status 1) or end (status 0); if that is
  missing too, fetched_at.

## Replay check

| | Issues (build x spot) | Match |
|---|---:|---:|
| Replayed right-now level = logged level (T90 in force) | 1,027 | **1,023 (99.6%)** |
| Same, issues logged at or above the cut | 234 | 233 (99.6%) |
| Replayed value within 0.001 of logged | 1,027 | 996 (97.0%) |
| Level match with T90 = 72 h at every issue | 1,027 | 97.7% |

Four issues differ by level. Three were logged Low and replayed Moderate (2) or Very high (1). One was logged High
and replayed Low. These were not investigated. A likely cause, not checked: the feed snapshot each build saw is not
stored, and the history keeps only the last fetch of each status row, so a status near the issue time can fall on
the other side of it in the replay. The match is close enough to score.

## Results

Scored lead 1-4 cells: 3,101 at 68 spots, target days 12 Oct to 4 Nov 2026. Affected cells: **632 at 47 spots**.
The candidate raises 253 cell values in all: 135 affected and 118 not affected, where the carry is below the cut but
above a low forecast. It changes the level of 50 cells, all of them affected, at leads 1 (41) and 2 (9).

### Primary, affected cells (n = 632, 47 spots)

| | Baseline | Candidate (T90 72 h) | Sensitivity: T90 in force |
|---|---:|---:|---:|
| MSE against observed | 0.05455 | 0.05370 | 0.05298 |
| Change in MSE (relative) | | -0.00085 (-1.6%) | -0.00157 (-2.9%) |
| 95% spot-cluster interval for the change | | [-0.00332, +0.00156] | [-0.00376, +0.00051] |
| Exact level agreement | 404 | **396** | 399 |

### Guard, all scored lead 1-4 cells (n = 3,101), High line

| | Hits | Misses | False alarms | Quiet correct |
|---|---:|---:|---:|---:|
| Baseline | 136 | 148 | 89 | 2,728 |
| Candidate (T90 72 h) | 138 (+2) | 146 | **95 (+6)** | 2,722 |
| Sensitivity: T90 in force | 138 (+2) | 146 | 93 (+4) | 2,724 |

### By lead, affected cells (candidate, T90 72 h)

| Lead | Cells | MSE base | MSE cand | Agree base | Agree cand | Hits b/c | False alarms b/c |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 186 | 0.0582 | 0.0555 | 109 | 104 | 27 / 29 | 4 / 9 |
| 2 | 178 | 0.0509 | 0.0506 | 115 | 112 | 19 / 19 | 5 / 6 |
| 3 | 150 | 0.0419 | 0.0419 | 99 | 99 | 10 / 10 | 5 / 5 |
| 4 | 118 | 0.0704 | 0.0704 | 81 | 81 | 5 / 5 | 3 / 3 |

At leads 3 and 4 the candidate changes almost nothing: lead 3's MSE rises by 0.00002 and lead 4 is unchanged. All
50 level changes are at leads 1 and 2.

### Decision

| Condition | Result |
|---|---|
| MSE not worse by more than 5% relative | Pass (1.6% better) |
| Level agreement does not fall | **Fail** (404 to 396) |
| False alarms rise by no more than the hits gained | **Fail** (+6 false alarms, +2 hits) |

**NOT SUPPORTED.** The sensitivity run with T90 in force also fails both conditions (399 against 404; +4 false
alarms against +2 hits).

### Exploratory reading (not part of the decision)

Of the 50 level changes, 25 went from right to wrong, 17 from wrong to right, and 8 stayed wrong. 42 moved up to
Moderate and 8 to High. In 43 of the 50 the observed level was Low or Moderate. Across the 253 raised cells, the
mean forecast rose from 0.061 to 0.118 against a mean observed 0.105. Across the 632 affected cells it rose from
0.161 to 0.181 against a mean observed 0.210. The carry lifts the average toward what was observed but puts the
increase on the wrong cells often enough to lose on levels. The six new false alarms are at five spots on 17, 22 and
30 October, mostly at lead 1, where right now was 0.74 to 0.99.

## Limitations

- **Retrospective, on outcomes already published.** About three weeks, 47 affected spots, mostly UK autumn storm
  days. A prospective shadow log would be needed to confirm any variant.
- **The observed index cannot see the die-off tail.** `verify_spots` scores whether a spill touched each source day,
  shifted by travel time. Bacteria still dying off from a spill whose water passed before the target day count in
  the candidate but never in the observation. The comparison therefore leans against the candidate. Whether that
  matters for swimmers is a separate question from this check.
- **Replay, not the build's own inputs.** The live state is rebuilt from a deduplicated history. Four of 1,027
  issues differ by level. The carry from the replay may differ from what the build would have computed in a few more.
- **T90 changed during the window.** 335 of the 1,027 issues ran with T90 = 30 h. The logged weights and baseline
  for those issues reflect T90 = 30 h. The primary candidate's carry uses 72 h. Both versions fail.
- **Level agreement is a blunt count.** It weighs a Low/Moderate swap the same as Low/Very high. The rule fixed it in
  advance, so it stands.
- The rule's conditions were met or failed by small counts: 8 cells of agreement and a net 4 false alarms. A
  different three weeks could reverse them. This check does not show that the carry is harmful. It shows that it
  did not meet the pre-stated bar on this data.

## Reproduce

```
gh release download state -R ethanbuckley/swimsignal -p dipcast.duckdb -p live_history.parquet \
  -p live_latest.parquet -p live_coverage.parquet -p poll_log.parquet -D <scratch>/state
DIPCAST_ROOT=<worktree> DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<scratch>/cache PYTHONPATH=src \
  python scripts/replay_carried_risk.py --as-of 2026-11-05 --out <scratch>/out
```

The state release is overwritten by every build. A later download has more days and gives different counts. The
results above are from the assets uploaded on 5 November 2026 at 12:44 UTC. The SHA-256 of `dipcast.duckdb` was
3d8e70c9026f8ed85cba308b24dc5d4088bfb5850ae73e6f26afcd4fe5b8be86, and of `live_history.parquet`
56119868a42bc0a99e6d07ff50028e54807d42932d300e4e82e824aa19c62408.

## What the project does next (5 November 2026)

This section is the development decision, kept apart from the verdict above (RESEARCH-WORKFLOW.md).

- **Supported claim.** On these three weeks, carrying right now's spills onto later days moved the average forecast
  toward the observed index but did not get more levels right, and at the High line it added more false alarms than
  hits. The display rule is not adopted. Day levels stay as they were.
- **Uncertainty.** The margins were small (8 cells of agreement, a net 4 false alarms), and the observed index cannot
  see the die-off the candidate models. The check shows the change did not clear the bar on this data, not that it is
  harmful.
- **Already on the site instead.** The contradiction that started this (Swale above Richmond Falls, "Back to low risk
  tomorrow" beside "should have passed and died off by Saturday 13:02") was fixed in words in
  [#609](https://github.com/ethanbuckley/swimsignal/pull/609): the five days give the clearing time when the first low
  day comes before right now's spills have passed. The day rows are unchanged.
- **Kept.** `transport.carried_risk` and its test stay in the code for later checks. The display change (forecast.py
  writing `now.carried`, levels.js lifting a later day to it) is kept on branch `claude/carry-display-not-adopted`
  (ee08e4e0), not merged.
- **Next useful deliverable.** A check against what the carry is about: measured bacteria. Lab E. coli samples taken
  on a day that right now's spills would have carried, from bathing waters in the 2027 season, scored as a separate
  log that does not touch the frozen 2027 primary evaluation. Owner: Claude, with Ethan's review. Milestone: protocol
  written before 1 May 2027; read once 30 such samples exist or on 30 September 2027, whichever is first.
