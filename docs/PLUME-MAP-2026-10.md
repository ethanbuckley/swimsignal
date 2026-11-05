# The spill map (31 October 2026)

A river spot's page now has a tile, "Where spill water may be". It is a map of the rivers upstream with the
water from each reported spill drawn moving down towards the spot. A slider runs from 48 hours before the
update to 48 hours after it, and Play moves through it. It is shown by default, not behind a flag.

## What it draws

- **Spills, as reported.** The catchment replay's 48 hours (`src/dipcast/replay.py`, `data/spot/<id>-replay.json`):
  each overflow's spills from the poll history, with its gaps. Nothing is reconstructed in the page.
- **Where that water may be, as a model estimate.** Water released at each moment of a spill reaches the end of its
  route `travel_h` later. `travel_h` is the overflow's modelled travel time, the forecast's own
  (`model.transport.upstream_overflows`). So the drawn water arrives at the spot exactly when the replay and the
  spot's forecast say it does. The speed is the forecast's: `config.RIVER_VELOCITY_MS` (0.2 m/s) unless a fresh
  gauge reading sets another (`transport.river_velocity`). The page gives the speed the forecast used. The water fades
  with age at the model's die-off, `config.T90_HOURS` (72 h), and drops off the map once it has passed the spot. The
  words then say it "passed the spot in the last 48 hours" (`config.RECENT_SPILL_HOURS`), as long as the model still
  counts it.
- **Water the feed did not confirm, dashed.** This covers two cases. One is a spill whose end the feed never gave
  (from the last poll that saw it to the stop the feed gave, or to the update). The other is a spill running at the
  update, after the update, "as if it kept spilling".
- **Gaps, as marks of their own.** A counted overflow with no current reading or no live feed gets a grey dashed ring.
  The words give the counts and say a spill there would not show. A route through a lake has no moving water,
  because the replay gives it no travel time. The words say so.

Every line says it is a model estimate. When nothing is drawn, the words say "no reported spill's water is modelled to
be on these rivers. That is what the feeds reported, not a measurement of the water." The tile never says clean or
safe, and a test checks that. An official notice, if the spot has one, comes before everything else
(`eaTodayBrief`, `eaTodayFirst`). Spills that start after the update are not drawn: this shows reported spills, not
forecast ones.

## Data and bytes

`src/dipcast/plume.py` writes `data/spot/<id>-plume.json` for each river spot that has a replay file. The file holds
each listed overflow's route down to the pin, as an encoded polyline from the overflow's place on its link
(`frac`). It follows the links the forecast traced, taking the way with the least distance left at each node. It
also holds the pin, the speed, T90, and the gap markers. The build runs it after `replay_files`, in
`build_site.plume_files`. A failure is announced and never stops the build. It sends no request: it reads the river
network, the overflow table and the replay files already written.

Measured on 31 Oct 2026 against the live site's 18:14 UTC replay and upstream files, with the local network (61 river
spots, 283 routes):

| file | median | largest | largest gzipped |
|---|---|---|---|
| `-plume.json` (new) | 2.1 kB | 7.8 kB (Port Meadow) | 3.1 kB |
| `-trace.json` (existing) | 15.1 kB | 36.4 kB | |
| `-replay.json` (existing) | | 6.4 kB | |
| `plume.js` (new, once) | | 22.8 kB | 8.4 kB |

All 61 files came to 186 kB and took 3.6 s to write. Every route's length was within 60 m of the forecast's
`distance_km` for that overflow (283 of 283).

The page asks for `plume.js` and the three files only when the tile's place comes within a screen of view
(`IntersectionObserver`, `mountPlume` in `index.html`). It draws one extra Leaflet map with the page's own tile layer
(`tiles()`, the CARTO Voyager line the build swaps in). The offline copy stores `plume.js` (`sw.js` SHELL), and the
worker's trace prefetch skips `-plume.json`. A spot with no routes file (a lake, or one the build could not place)
loses the tile quietly.

## Motion and small screens

- `prefers-reduced-motion: reduce` hides Play and turns off Leaflet's zoom and fade animations. The slider still works.
- The slider has an `aria-valuetext` of the time in words. The sentence under the map is `aria-live="polite"` and is
  updated only when its words change, not on every frame of Play. "Spills reported upstream in the last 48 hours" is
  the full text alternative.
- At 375 px the map is 300 px tall, and 400 px from 801 px up. On a phone the tile follows "Overflows that matter
  most" (`PHONE_ORDER`).

## Code and tests

- `src/dipcast/plume.py` (`route_xy`, `encode_route`, `spot_plume`, `write_plumes`), `scripts/build_site.py`
  (`plume_files`, copy, `SHELL_SOURCES`), `src/dipcast/site/plume.js`, `src/dipcast/site/index.html` (`mountPlume`,
  one host line, `PHONE_ORDER`), `src/dipcast/site/sw.js`.
- `tests/test_plume.py`: routes take the short way, their length equals `upstream_overflows`' `distance_m`, no route
  below the pin or at a lake, gap markers, the build never fails on it.
- `tests/site_plume.test.cjs`: arrival at the travel time, running and unclosed spills dashed, lake routes not drawn,
  the slider's range, the words (estimate, gaps, never clean or safe), official notice first, reduced motion.

## Not done

- A regional or national view. The per-spot file is small enough, but a region would need the routes of every spot's
  overflows merged, and the replay is per spot.
- Forecast spills (the five days' spill probabilities) are not drawn. Drawing a probability as water on a river would
  read as a measurement.
- Only the replay's twelve overflows of most weight with spills are drawn at a spot. The rest are counted in words.
