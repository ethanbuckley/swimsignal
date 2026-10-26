# Catchment replay (prototype, 26 October 2026)

A spot page can show the last 48 hours upstream: each counted overflow's reported spills, when the model
estimates each spill's water reached (or will reach) the spot, rain over the overflows, and the spot
gauge's latest reading. It is behind an opt-in, `?replay=1` on a spot's address
(`spot/<id>/?replay=1`). Without it the page is unchanged: no script tag, no request, no new tile.

Code: `src/dipcast/replay.py` (data step), `src/dipcast/site/replay.js` (view), a small hook in
`src/dipcast/site/index.html` (`REPLAY`, `mountReplay`), two lines in `scripts/build_site.py`. Tests:
`tests/test_replay.py`, `tests/site_replay.test.cjs`.

## What it shows

| Part | Source | Label on the page |
|---|---|---|
| Spills at each counted overflow | `live_history.parquet` (the poll history) and this build's poll | "Reported spilling Sat 18:04 to Sat 21:51." Observed. |
| Monitor gaps | status -1 rows in the history; status -3 (feed not answering) in this build | "No reading (monitor offline) from ..." |
| Arrival at the spot | spill start and end + the overflow's `travel_h` (`model.transport`), the shift the forecast uses | "Modelled to reach the spot around ... (estimate; passed / arriving now / not there yet)" |
| Rain | the build's own rain cache, `data/cache/rain/forecast_<cell>.parquet`, the cells holding the counted overflows | "Open-Meteo's model record, not rain gauges"; hours after the cache's issue time drawn as forecast |
| River level | `river_state` already on the spot (latest reading, six-hour rise where fetched) | "Earlier readings are not held, so no line is drawn for it." |
| Overflows with nothing to show | counted overflows with no spill and no gap, by data state | "1 counted overflow has no current reading, so a spill there would not show here." |

The drawing (SVG) repeats the table: a solid bar for a reported spill, a hatched, dashed-outline bar
for the modelled arrival, a grey bar for no reading, a short grey strip for an hour of rain not held.
Each mark has its words in the key, so colour is never the only cue. The table is the text
alternative: one row an overflow, `th scope="row"`, a caption, in a focusable scrolling region; under
480 px its rows stack. The tile is a fold like "Overflows that matter most", open on arrival because the
reader asked for it.

## What it never claims

- No cause. The words are "reported upstream" and "modelled to reach the spot". The tile's first
  paragraph says the arrival times "say nothing about what any spill did to the water here". A test
  fails on "cause", "because", "due to", "resulted in" or "pollut".
- No filled gaps. A spill whose end the feed never reported has no end: a start mark and "Its end was
  not reported". Its arrival has no end either ("when it passed is not known"). An hour of rain
  missing at any cell has no value. The gauge has no line, because only one reading (and a six-hour
  rise) is held.
- No silence read as "no spill". Counted overflows with no current reading are counted and said.
- Arrival is never called observed. Every arrival sentence carries "(estimate; ...)".

## How a spill is rebuilt from the history

The history keeps one row per distinct (site, status, status start), each with the feed's latest
event start and end. A spill is a latest-event pair, or a "discharging" status start. A start with no
end is closed by the feed's next "not discharging" status start. Yorkshire Water needed this: its
"latest event" is only the last part of a spill (YWS00199 on 24 October 2026: discharging from
17:04:39, stopped 20:51:50, latest event 20:51:20 to 20:51:50). An event inside a longer one is
dropped as part of it. A start still open at the end stays open: running if this build's poll says
discharging, otherwise "end not reported".

Known limit, said on the tile: if two spills start and stop between two polls (30 minutes), only the
second is recorded. South West Water's feed gives no status start; its spills come from the
latest-event pairs alone (not checked against real South West Water rows in this prototype).

## Data, requests and cost

- No new requests at build time. The step reads the poll history (state), the rain cache files
  directly (it never calls `rainfall.fetch_forecast`, so it cannot spend Open-Meteo calls; a test
  makes any request raise), and the build's results. Zero Open-Meteo calls, zero EA calls.
- One file a spot, `data/spot/<id>-replay.json`, written after `write_app_data` (which clears
  `data/spot/`). Nothing is added to `spots.json`, `spots-lite.json` or `data/spot/<id>.json`; a test
  checks the results the build writes from are unchanged.
- Size: the three real spots below were 1.8 to 6.6 kB. A file is capped by design at 12 overflows and
  their latest 8 spills each; that worst case is 19.6 kB in the test, under the 20 kB budget
  (`REPLAY_MAX_BYTES`). Over it, the build log gets a warning. Only a reader who opts in downloads one.
- The step is wrapped so that a failure is a line in the build log, never a failed build.

## What was checked, and on what

Real (read only, no pipeline run): the published `spots.json` of 25 October 2026 22:49 UTC (89 spots),
the poll history as of that time (state saved 26 October 11:06 UTC, rows that had begun by 22:49), and a
rain cache from a local build issued 26 October 00:17 UTC (after the spots file, so every hour shown is
the model's record of the past). Rendered: Wharfe at Wilderness Carpark (Ilkley), Windermere at
Waterhead, Severn at Ironbridge. The Ilkley file is `tests/fixtures/replay_ilkley.json`.

Synthetic (tests): a finished spill, a running spill, an end never reported with the monitor offline,
an offline spell closed by the next reading, a feed not answering, the Yorkshire tail case, two spills
that must stay two, water already passed and water still due, rain with a missing hour, a busy
catchment at the size cap, no history at all.

Not done: a real build with this branch (another worker runs builds), and a 320 px check.

## Open questions for Ethan

1. Gauge history. A 48-hour level line needs one EA request a spot (`/id/measures/<m>/readings?_limit=192`):
   about 90 requests a build (one a spot with a gauge; time not measured). Worth it, or keep the latest reading?
2. Rain area. Now the plain mean over the 0.1° cells holding the counted overflows. Weight by reach instead,
   or show the spot's own cell?
3. Lake hold. Arrival uses `travel_h` alone, as "about N hours away" does. For a lake spot the forecast also
   holds bacteria in the lake; the replay does not show that holding. Say so on lake spots, or leave lakes out?
4. Where it lives if kept: a fold under "Overflows that matter most" (as now), or reached from each overflow row.
5. The 48-hour window. The forecast counts a spill until 48 h after its water passed; a longer window (72 h)
   would show more of what the level still counts, at a larger file.
6. Whether a running spill's arrival should show an end at all. Now it is "from around ...", open.
