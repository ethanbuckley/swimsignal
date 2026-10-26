# Catchment replay (prototype, 26 October 2026)

A spot page can show the last 48 hours upstream: each counted overflow's reported spills, when the feeds
were actually polled, when the model estimates each spill's water reached (or will reach) the spot, model
rain averaged over the overflows' cells, and the spot gauge's current reading. It is behind an opt-in,
`?replay=1` on a spot's address (`spot/<id>/?replay=1`). Without it the page draws nothing new and asks
for no replay file. The production model is unchanged: the replay reads what the build already has.

Code: `src/dipcast/replay.py` (data step), `src/dipcast/site/replay.js` (view), a small hook in
`src/dipcast/site/index.html` (`REPLAY`, `mountReplay`), `replay_files` and two lines in
`scripts/build_site.py`, two lines in `src/dipcast/site/sw.js`. Tests: `tests/test_replay.py`,
`tests/site_replay.test.cjs`.

## Decisions taken (Codex for Ethan, 26 October 2026)

1. The window stays 48 hours. The gauge is its current reading and that reading's time, nothing more:
   no rise, no series, so no extra EA requests.
2. The rain is the mean over the 0.1° cells holding the counted overflows, and is called that: "Model
   rain averaged over the cells of the overflows upstream". Never "catchment rainfall"; a test fails on
   the word "catchment" in the tile.
3. The per-overflow details fold under the timeline ("Details for each overflow (N)"). The timeline's
   description and a sentence above the fold give the count of overflows with spills or gaps, how many are
   still discharging, and how many reach the spot through a lake. The fold's summary is keyboard
   focusable and the table inside it is the full text alternative.
4. Lake routes: where an overflow's water passes through a lake before the spot (the model puts the lake's
   metres in `lake_distance_m`, `transport.upstream_overflows`; the replay reads `lake_distance_km > 0`),
   no arrival is drawn or timed and no travel time is given. The reported spills are still shown, with
   "Arrival through the lake not estimated here."
5. A spill whose end was not reported keeps an open-ended arrival on a river route.
6. `replay.js` loads at the build's `?v=` stamp, read off `levels.js`'s versioned tag; it is in
   `SHELL_SOURCES`, and the offline copy stores it (`sw.js` SHELL). Trade-off: the service worker downloads
   it (about 25 kB) once for every visitor who installs the worker, though only `?replay=1` runs it. The
   worker's trace prefetch skips `-replay.json` files.
7. Checked at 320, 375 and 1440 px.

## Second review (Codex, 26 October 2026)

1. **Polling is said as it happened.** The page no longer says "every 30 minutes". It says "when SwimSignal
   polled them; events between polls can be missed", and gives each company's answered polls in the window,
   the first and last, and the three longest gaps. The poll log (`poll_log.parquet`, one row per company per
   poll) is the source. On the saved state of 25 October, each company's feed answered **23 polls in 48
   hours**, not 96, with gaps of 4, 4 and 16 hours. Every gap of 90 minutes or more is drawn as "not
   polled" on that company's rows (the file keeps the 12 longest).
2. **Quiet is not proof.** A counted overflow with no poll history at all, or whose history starts inside
   the window, is counted apart ("whether they spilled in these hours is not known") and drawn as not polled
   for those hours. Without a poll log the page says how complete the hours are is not known.
3. **Ends rebuilt across gaps are spans.** An end taken from the feed's next "not discharging" is exact only
   when no poll gap and no offline spell lies between the last poll that saw the spill and that stop. Otherwise
   the spill has `end_after` (the last poll that saw it discharging) and `end_by` (the stop), is drawn as an
   outline over that span, and is said as "It stopped between ... and ...". Its arrival gets the same span.
   On real data this turned Pool (YWS00199)'s "18:04 to 21:51" into "stopped between 20:37 and 21:51".
4. **The size is enforced.** Spills (8), no-reading spans (4) and poll gaps (12) are capped per overflow or
   company, with the counts of those left out. If the file is still over 20 kB, overflows of least reach are
   dropped one by one, counted in `more_with_events`, and `truncated` is set; the page says "left out to keep
   this small". The worst case in the tests (20 overflows, 20 spills and 20 offline spells each, 20
   companies with 16 gaps each) is cut to fit.

## Benchmark, 105 spots on real saved history

Read-only state: `spots.json` of 25 October 22:49 UTC (105 spots, 80 with counted overflows; the build
passes every overflow upstream, this file has the top 10), `live_history.parquet` (91,313 rows as of then),
`poll_log.parquet` (3,609 rows), and a local rain cache. No requests.

| | Time, 105 spots | Peak (tracemalloc) | Max RSS |
|---|---|---|---|
| Before: the history grouped again for every spot | 183.7 s (under tracemalloc) | 79 MB | 306 MB |
| Grouped once, a pandas group per site | 19.1 s (under tracemalloc) | 82 MB | 264 MB |
| After: grouped once, only the counted sites, one `to_dict` | 6.5 s under tracemalloc; 1.5 s under cProfile | 3.3 MB | 142 MB |

The output files are byte-identical before and after (checked on the largest). Sizes of the 102 files written
(three spots have no forecast or no file name): smallest 0.4 kB, median 2.6 kB, 90th percentile 6.7 kB,
largest 8.2 kB (River Lune, Crook o' Lune), 324 kB in all, none over the 20 kB budget.

A failure is a warning in the build health, never a failed build: `build_site.replay_files` catches it,
announces it and records `{"written": 0, "warning": ...}` (tested).

## What it shows

| Part | Source | Label on the page |
|---|---|---|
| Spills at each counted overflow | the poll history and this build's poll | "Reported spilling Sat 18:04 to Sat 21:51." |
| An end not seen | the last poll that saw it and the feed's stop | "It stopped between Sat 20:37, the last poll that saw it discharging, and Sat 21:51" |
| Monitor gaps | status -1 rows in the history; status -3 (feed not answering) in this build | "No reading (monitor offline) from ..." |
| Polls | the poll log | "Yorkshire Water's feed answered 23 polls, from ... Its longest gaps with no poll: ..." |
| Arrival, river routes | spill start and end + `travel_h`, the shift the forecast uses | "Modelled to reach the spot around ... (estimate; ...)" |
| Arrival, lake routes | none | "Arrival through the lake not estimated here." |
| Rain | the build's rain cache | "Model rain averaged over the cells of the overflows upstream ..." |
| River level | `river_state` already on the spot | "1.52 m at Sun 21:15, the current reading. Earlier readings are not shown." |

## What it never claims

- No cause. A test fails on "caus", "because", "due to", "resulted in" or "pollut".
- No continuous observation: no "every 30 minutes", and the gaps are drawn and named.
- No filled gaps: an unreported end has no end; a rebuilt end across a gap is a span; a missing rain hour
  has no value; the gauge has no line.
- No silence read as "no spill": no current reading, no history, or late history are each counted and said.
- No arrival called observed, and none through a lake.

## Data and cost

- No new requests at build time: zero Open-Meteo calls (the rain cache files are read directly; a test makes
  any request raise) and zero EA calls.
- One file a spot, `data/spot/<id>-replay.json`, at most 20 kB; nothing added to `spots.json`,
  `spots-lite.json` or `data/spot/<id>.json`.

## Preview for QA

A small static site of three real spots from the saved state, built with this branch's pages:
`~/Documents/GitHub/swimsignal-private/replay-preview/`, served by the `replay-preview` entry
(port 8793) in this worktree's `.claude/launch.json`. Paths:

- `/spot/bw-uke4200-08904/?replay=1` (Wharfe at Wilderness Carpark, river)
- `/spot/osm-windermere-waterhead/?replay=1` (Windermere, Waterhead: both overflows through the lake)
- `/spot/bw-ukg2100-36070/?replay=1` (Severn at Ironbridge, river)
- the same without `?replay=1` shows the page as it is today.

The forecast in it is from 25 October 22:49 UTC, so the page says it is out of date. Missing files in it
(reviews, spot scores, traces) are left out on purpose.

## Open questions for Ethan

1. Where it lives if kept: a fold under "Overflows that matter most" (as now), or reached from each overflow row.
2. Whether the offline copy should store `replay.js` while it is a prototype (decision 6's trade-off).
3. The polling itself: 23 answered polls in 48 hours on 25 October against a 30-minute schedule. The replay
   now shows it; the cause (scheduler, runner minutes, feed failures) is outside this PR.
