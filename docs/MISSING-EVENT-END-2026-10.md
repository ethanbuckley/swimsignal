# Finished spills with no event end: how much they miss from "right now"

Stated 26 Oct 2026, before any replay was run. The results go below the line at the end.
Nothing in the live model changes in this work. `transport.py`, `levels.js`, the live code and
the shadow windows stay as they are.

## The gap

`transport._counted` counts a finished spill from `latest_event_end` alone. It takes
`hrs_since = now - latest_event_end`. A row whose end is missing (NaT) counts only while it is
running (`running`: status 1, or a feed-down row whose last status was 1). So a record with
status 0 ("not discharging") and no event end is never counted, even if it stopped an hour ago.

A monitoring review on 26 Oct 2026 found 28 United Utilities records like this, 5 of them
stopped 10 to 19 h before the poll. This note measures what that costs.

## What the feeds give (read in `src/dipcast/ingest/live.py`)

- Each poll row has `status` (1 discharging, 0 not, -1 offline), `status_start`,
  `latest_event_start`, `latest_event_end`, `last_updated` and `fetched_at` (read).
- `live_history.parquet` keeps `site_id, company, status, status_start, latest_event_start,
  latest_event_end, fetched_at`, one row per distinct (site, status, status_start), the last poll's
  copy kept (read, `save_live`). Rows with no `status_start` are kept once per local day.
- No field says what the status was before. The history shows it, where the change happened in
  the window (read).
- A first look at the downloaded state (counts only, no risk computed): status-0 rows with no end
  exist at every company but Southern Water. At Anglian, Wessex and most of South West Water the
  row has no `status_start` either, so no end time can be had from the row (read).

## The candidate rule

When a row has status 0 and no `latest_event_end`, take its end as its `status_start`: the time
the status became "not discharging". With no `status_start`, leave it uncounted, as now. Every
other row keeps today's rule. This is done in the measurement script, as a wrapper that fills
`latest_event_end` before calling the unchanged `live_now_risk`.

A status-0 `status_start` can also follow an offline spell, not a spill. So a strict variant (B)
fills the end only where there is evidence of a spill: `latest_event_start` is present and not
after `status_start`, or the site's previous history row is status 1. The broad rule is A.
Results are given for both. If the effect rests on A alone, that is said.

## Data and window

- State downloaded from the `state` release on 26 Oct 2026: `live_history.parquet` (polls from
  11 Sep 20:18 UTC to 26 Oct 11:06 UTC), `live_latest.parquet` and `dipcast.duckdb`.
- Builds: each build's per-spot `now_risk` in `forecast_points` (lead 0 rows), grouped into builds
  by gaps over 10 minutes.
- Primary window: builds from 17 Oct 2026 09:35 UTC (the merge of the transport fit, PR #248, the
  last change to weights and travel times) to 26 Oct 11:08 UTC. Today's code matches the live model
  over this stretch, so the replay can be checked against it.
- Secondary window: every build from 12 Sep. Today's trace is used throughout, so before 17 Oct
  this is "what today's model would have said", not what the site said. Reported apart.

## How the replay works

1. Trace once with today's code: `build_overflows(net)` on the downloaded live snapshot, then per
   spot (`build_site.load_spots()`) `locate_pin(..., kind_hint, river_hint, name)` and
   `upstream_overflows(..., velocity_ms=river_velocity(None))`, gauge off as in the build.
   Keep site_id, weight, travel_h per spot.
2. State as of a build at time T: per site, the history row with the largest begin at or before T.
   Begin is `status_start`, else the event start (status 1) or end (status 0), else `fetched_at`.
   The build's first `issued_at` is T for the state; each spot's own `issued_at` is `now`.
3. Check first: today's rule on the replayed state against `forecast_points.now_risk`, as the
   shown level (`risk_label`, cuts 15/40/70 on the shown score). The 4 Oct replay matched 99.6% of
   levels. If the primary window matches under 97% of spot-builds, stop and report, not measure.
4. Then per spot-build: right-now risk with today's rule, with rule A, with rule B.

## What is counted

- Records per build: status-0 rows with no end, by company; how many have a `status_start`; how
  many of those stopped within 48 h (the counting window, `RECENT_SPILL_HOURS`) and within 72 h.
  Over every overflow, and over those that carry weight at some spot.
- Spot-builds whose right-now risk changes (any change over 0.0005), and by how much.
- Spot-builds whose right-now level changes (low, moderate, high, very high, from `risk_label`).
- Spot-builds whose headline spill level changes. Taken here as the worst of right now, today and
  tomorrow, with today and tomorrow from `forecast_points.risk` at leads 0 and 1 and the same cuts.
  This leaves out E. coli, ratings, samples and algae, which can only hide a change. So it is an
  upper bound on headline changes.
- Distinct spots affected, and which companies' records cause it.

## What would make it worth fixing (set now)

In the primary window, with rule B (the one with evidence of a spill):

- Fix if 0.5% or more of spot-builds change their right-now level, or
- Fix if 3 or more spot-builds have their headline spill level raised from Low.
- Do not fix if neither holds and 99% of spot-builds move by under 0.01.
- Anything between is a call for Ethan, with the numbers.

If only rule A passes, the fix needs a check of what those status-0 starts follow before it ships.

## Limits known before the run

- The history keeps the last poll's copy of each (site, status, status_start). If a company filled
  in an end later, the history shows the end at every earlier build too. That hides some of the gap
  from today's rule in the replay; the match check against production will show how much.
- A row is seen as of its begin time, which can be before the poll that first saw it.
- Feed-down carry-forward rows are not in the history, so a spill running through an outage is
  missed in the replay.

---

## Results

Run 26 Oct 2026 with `scripts/measure_missing_event_end.py`, on the state downloaded that day. One
process, 80 s for the replay, about 275 MB while replaying (the trace step's peak was not measured).
The full figures are in `MISSING-EVENT-END-2026-10-summary.json`.

One change after the first run: UU lists some status changes twice, with status starts under a second
apart. So rule B's "previous row" is read as the last earlier row with another status. Every figure
below came out the same with and without this.

### Decision for Ethan: do not fix now (by the thresholds set above)

With rule B, in the primary window, no spot-build changed its right-now level or its headline, and
every spot-build moved by under 0.01. All three "do not fix" conditions hold. Rule A would pass the
headline threshold, but every one of its level changes comes from a monitor coming back from
"offline" with no spill before it. Counting those would add risk for spills that did not happen.

The case for fixing anyway is two real false Lows at Grasmere (below). They are rare: 2 spot-builds in
six weeks. A fix would be one line in `_counted`, described at the end. It was not made.

### The check against production

- Primary window (17 Oct 09:35 to 26 Oct 11:08 UTC): 7,255 spot-builds, 79 builds, 80 spots.
  Today's rule on the replayed state gave the same level as `forecast_points.now_risk` in **99.3%**
  of them (51 differ), and the same risk to 0.005 in 95.0%. That is over the 97% bar, so the
  measurement went on (read).
- All 51 mismatches have the replay higher than production. They spread over eight companies, not
  over status-0 rows with no end. 11 are at the first build in the window, 17 Oct 09:35. Many others
  are spills that began under 3 h before the build. Likely causes are the history keeping each
  record's last copy and rows dated before the poll that first saw them (inferred, not checked
  row by row).
- Whole window (13 Sep to 26 Oct): 30,458 spot-builds, 85.2% level match. That is expected, since
  today's trace replaces the model of the time (the transport fit and lake changes). Figures from
  that window are "what today's model would have said", not what the site said.
- 25 of the 105 spots have no traced overflow upstream (isolated lakes, upland rivers) and are left
  out. Their right-now risk is 0 under any rule. Shares below are of the 80 traced spots.

### Records per build (as-of state at each build, mean per build)

Status 0 with no event end:

| Company | no end | with a status start | stopped ≤ 48 h | ≤ 48 h, spill shown before (B) | ≤ 48 h, upstream of a spot | same, B |
|---|---|---|---|---|---|---|
| United Utilities | 148 | 120 | 11.3 | 4.0 | 0.26 | 0.09 |
| Severn Trent | 198 | 198 | 2.5 | 0 | 0.10 | 0 |
| Thames | 31 | 31 | 0.4 | 0 | 0.44 | 0 |
| Northumbrian | 41 | 41 | 0.1 | 0 | 0 | 0 |
| Yorkshire | 41 | 41 | 0 | 0 | 0 | 0 |
| Anglian | 23 | 0 | 0 | 0 | 0 | 0 |
| Wessex | 222 | 0 | 0 | 0 | 0 | 0 |
| South West | 871 | 0 | 0 | 0 | 0 | 0 |
| Southern | 0 | 0 | 0 | 0 | 0 | 0 |

Primary window. "Upstream of a spot" means it carries weight at one or more of the 80 spots.

- **Only United Utilities has finished spills with no end**, as far as the feeds show (read). The
  Severn Trent, Thames and Northumbrian rows with a recent status start show no spill before them:
  no event start, and no status 1 before in the history. The two looked at (UUP00418, SVT02033)
  follow an offline spell; the rest were not looked at one by one. Anglian, Wessex and South West
  rows have no status start, so no rule can date them.
- The UU count is not steady. Records stopped within 48 h with a spill shown before were 1 to 6 per
  build most days, 14 on 10 Oct, and **16 to 19 on 25 and 26 Oct** (read, daily means). The
  26 Oct review's 28 fits this: the 11:06 UTC snapshot has 27 UU rows with status 0, an event start
  and no end (read).
- Most of these overflows are not upstream of a listed spot. On average 0.09 per build were, in the
  primary window.
- A related form, not measured for risk: UU rows with status 0 whose end is older than their event
  start (a stale end), about 4 per build (read). Today's rule dates those spills from the older end.

### Effect on right now

| | Primary, rule B | Primary, rule A | Whole window, rule B | Whole window, rule A |
|---|---|---|---|---|
| Spot-builds | 7,255 | 7,255 | 30,458 | 30,458 |
| Risk changed (> 0.0005) | 19 (0.26%) | 194 (2.7%) | 479 (1.6%) | 792 (2.6%) |
| Median change, where changed | +0.003 | +0.006 | +0.016 | +0.016 |
| Largest change | +0.005 | +0.494 | +0.308 | +0.768 |
| Moved under 0.01 | 100% | 98.8% | 98.7% | 98.1% |
| Right-now level changed | 0 | 30 (0.41%) | 8 (0.03%) | 54 (0.18%) |
| Headline raised from Low | 0 | 28 | 2 | 30 |
| Spots with a level change | none | 3 | 4 | 7 |
| Companies adding risk | UU | Thames, UU, Severn Trent | UU | UU, Thames, Severn Trent |

Headline here is the worst spill level of right now, today and tomorrow (an upper bound, as stated).

- **Rule A's changes are not spills.** Its 30 primary-window level changes are at Devil's Bridge and
  Crook o' Lune on the Lune (16 and 13 spot-builds) and one Severn Trent bathing water. They come
  from UUP00418, which went offline (-1) on 15 Oct and came back as status 0 at 16:16 on 16 Oct, and
  SVT02033, offline then status 0 on 25 Oct. Neither row has an event start (read).
- **Rule B's level changes** (whole window, today's model): Eden at Lazonby and Armathwaite and a
  UU bathing water, each moving one level up between moderate, high and very high (6 spot-builds).
  And Grasmere twice, below.
- **Grasmere, 20 Sep 16:39 and 16 Oct 01:36 UTC.** UUP00829 (weight 0.31, 1.6 h upstream) spills
  many times a day. Each time it stopped with no end on the record, the record's earlier end was
  replaced too, so nothing counted. Production showed right-now risk **0.000** at both builds
  (read). With rule B it would be 0.308, Moderate. Each lasted one build, until the next poll
  brought a new record. These are the only two headline changes from Low under rule B.

### What a fix would be (not made)

In `transport._counted`, before `hrs_since`: for a row with status 0, no `latest_event_end`, a
`status_start`, and a `latest_event_start` no later than that `status_start`, use the `status_start`
as the end. That is rule B's first test. Its second test (previous status 1) needs the history,
which the build does not read. In this replay the first test alone covers the rule-B records
upstream of the spots: Grasmere's both have an event start (read); the rest was not checked
separately. Not rule A: it would count monitors returning from offline as spills.

If it ships, `clear_time` reads `_counted` too and would change with it, and the page's counts follow
`live_now_risk`'s contributions (read). Map clicks work from `ended_h`, which
`scripts/build_any_point.py` takes from `latest_event_end` directly (read), so it would need the
same fill there.

### Limits

- The history keeps each (site, status, status_start) once, as last seen. An end filled in later
  shows at every earlier build, so the replay may undercount today's gap. The match check shows the
  replay running high, not low, which suggests this is small (inferred).
- The primary window is nine days and has only a day and a half of the 25 to 26 Oct rise in UU
  records. If that rise lasts, the effect at spots could grow. Re-running this script on a later
  state would settle it.
- Only the 80 traced listed spots. Map clicks anywhere can sit below any UU overflow, and were
  not measured.
- Headline changes leave out E. coli, ratings, samples and algae.

## Decision, 26 October 2026

Ethan adopted the recommendation ("Adopt all the recommendations as my decisions"):
- **Do not fix now.**
- **Measure again in about two weeks** (on or after 9 November 2026), with `scripts/measure_missing_event_end.py` on a
  fresh state, because United Utilities' count of such records rose on 25-26 October.
- **Fix if,** in that run, rule B changes the right-now level at more than 1% of spot-builds in its primary window.
- **Whenever it is fixed,** `scripts/build_any_point.py` (`ended_h`, map clicks) is fixed in the same PR.
