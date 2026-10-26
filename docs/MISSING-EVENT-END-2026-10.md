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

(Not run yet.)
