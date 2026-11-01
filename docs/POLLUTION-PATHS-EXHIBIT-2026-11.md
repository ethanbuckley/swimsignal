# Where does the pollution go? Research Lab exhibit 2

Written 1 November 2026. A data export and a local prototype exhibit. **No test, no new result, no change to the
forecast.** It shows the forecast's own network geometry and transport settings, and the recorded verdicts of the
transport studies, read from `data/research/research_catalogue.v1.json`.

## What it shows

For each of the 109 listed spots (`spots.csv`, `spots-osm.csv`):
- the spot's pin, placed by the build's own `transport.locate_pin`;
- every monitored overflow upstream within 60 km along the mapped rivers, with the forecast's own distance, travel time,
  survival (decay), dilution and weight (`transport.upstream_overflows`, production settings: velocity fixed 0.2 m/s,
  T90 72 h, dilution "length", lake path "residence_spill");
- the OS Open Rivers links that join each overflow to the spot, found by walking down the mended network from the
  overflow's link inside the spot's upstream set.

## How it was made

`scripts/lab_pollution_paths.py`, offline, 17 seconds. It imports dipcast's network code, so it ran with a scratch
`DIPCAST_ROOT` whose `data/raw` and `data/processed` held symbolic links: this worktree's committed files, plus the main
checkout's caches for what git does not hold (`river_network.pkl`, `overflows.parquet`, `lakes.parquet`, the OS Open
Rivers geopackage), and a scratch `DIPCAST_STATE`. SHA-256 of those four caches before and after: unchanged. No file
was written into the scratch root during the run.

The overflow table is the main checkout's cache, last modified 30 October 2026, so a spot's list is as the forecast saw
it then. Output: `prototypes/research-lab/assets/paths/` (one file per spot, `index.json`, `overview.json`), 1.9 MB.

## Checks

- **Against the live site:** for Windermere, Waterhead and Wharfe at Cromwheel, Ilkley, the published
  `https://swimsignal.co.uk/data/upstream/<id>.json` holds the same overflows (4 and 16), with the same travel times and
  weights to the published rounding (fetched 1 November 2026).
- **Coverage:** 1,784 overflow links across 81 spots; 25 spots have no monitored overflow upstream within 60 km; 3 sit
  off the mapped network (Cotswold Country Park and Beach, Henleaze Lake, Loughrigg Tarn).
- **Drawn paths:** 1,752 of 1,784 links got an unbroken drawn path. The other 32 are drawn as overflows without a line;
  the forecast reaches them, probably through a short network repair link the drawing does not have. Listed as next
  question 2.
- **Prototype:** 1440 × 900 and 375 × 812, no horizontal scroll, no console errors; spot picker, hash links, map
  hover and table highlight, the clock's slider and play. Not checked: Safari, a real phone, screen readers.

## The clock

The brief warned that moving particles could imply known paths and timings. The exhibit moves nothing along a river.
A slider (and play) sets hours after a hypothetical simultaneous spill; each overflow is filled once the model's
travel time has passed, and faint before. Beside it, always visible: "Illustration", the assumed speed, that a real spill
moves faster in a flood and slower in a dry spell, and that no spill's path was tracked.

## The research shown

Six legs of the journey, each with today's setting and the recorded verdicts, adopted and failed alike: speed
(transport fit, wider grid), dilution (dynamic flow dilution, spill size proxies), survival (sunlight and temperature),
lakes (lake path/residence/distance, lake direction, near field, wind), rain and flow data (radar, GloFAS), and positions
(overflow positions, side channels, catchments). Verdict text comes from the catalogue at page load, not retyped.

## Proposed next questions (not started)

1. Compare model arrival times with measured ones (EA time-of-travel surveys, an outside request, or samples after
   reported spills at frequently sampled spots).
2. Draw the 32 missing paths through their repair links and check each: a data fix.
3. An exposure table: each overflow's weight summed over spots times its spills a year, published as a model observation.
4. Trace to 100 km and measure the weight the 60 km cut-off drops.

## Wording correction after review (1 November 2026)

An outside review of the prototype found that the exhibit called the model weight "the share of a spill's bacteria it
expects to arrive" and showed it as a percentage. That is wrong. The weight is survival times a dilution factor.
Dilution lowers concentration by mixing; it removes no bacteria. So the weight is a relative factor the model uses, not
the share of a spill that arrives, and without spill volumes it cannot say what share of a spot's pollution one overflow
causes. The exhibit now shows weights as factors from 0 to 1, labels the column "Survival × dilution", and explains this
above the table. The opening question now asks how strongly the forecast counts an overflow. No data changed.
