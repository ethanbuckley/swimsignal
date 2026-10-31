# Water temperature everywhere, all year: the provisional baseline (31 October 2026)

Issue #492 (rivers #477, lakes #478, coasts #479). **Ethan's decision of 30 October 2026:** clearly labelled water
temperature estimates at every SwimSignal spot, all year. He accepts initial error, and wants it measured and reduced
over time.

This file records the first stage: the named inland spots. It records how each estimate is made, what is known about
its error, what is not, and what remains. Historical verdicts are unchanged: the river model passed for rivers in May to
September, and the lake model failed (`docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md`).

## What the estimate is

- **What it estimates.** The water near the surface at the spot, on the day of the update. It is daytime water, as the
  EA spot samples the model learned from were mostly taken in the working day.
- **What it is not.** It is not a sensor reading, and not a measurement where you get in. A sensor reading, where there
  is one, is shown as a measurement, apart from the estimate. Monthly historical measurements (the lake temperature
  pages, #529) are context, not today's water.
- **Inputs.** A weather model's air temperature for the spot's 0.1° cell over the last 30 days, today's forecast
  included. The air comes from the rain request the build already makes, which asks for every spot's own cell with 31
  past days, so the estimate adds **no Open-Meteo call**. To that are added the date, and either the river's network
  length upstream and the cell's height, or the lake's area.
- **Never part of the pollution level.**

## Routes (`water_temp.estimate_any`)

| Route | Where and when | How | What is known about its error |
|---|---|---|---|
| `river_model` | rivers, May–September | the tested model | **Passed:** typical error (RMSE) 1.56 °C on 3,798 unseen rivers, bias +0.27 °C. Shown as "typically within 2 °C", as before |
| `lake_model` | lakes under 1 km², or of unknown area, May–September | the same model, as a lake | Lakes **failed** the test as a whole (1.82 °C). At lakes under 1 km² or unmatched, its typical error was 1.70 °C, bias −0.25 °C |
| `lake_curve` | lakes of 1 km² or more, May–September | the lake curve in the 7-day air alone | At large lakes it did better than the full model: 1.98 °C against 2.18 °C, bias −0.58 °C |
| `river_off_season`, `lake_off_season` | any river or lake, October–April | the type's curve in the 7-day air | **Not measured.** Every test row was May–September |

Notes on these figures and rules:

- **Exploratory figures.** The lake figures are from the test's held-out rows (cached in the private
  `water-temperature/work/predictions_primary.parquet`). The lake routes were chosen after seeing those rows, so their
  figures are exploratory. They describe the route; they are not a new test.
- **Why the 7-day air, not 30 days, for lakes.** With the 30-day mean the lake curve did worse overall: 2.60 °C
  against 1.93 °C with the 7-day mean, on the same rows.
- **Floor.** Water is never estimated below 0 °C.
- **What the page says, by route:**
  - `river_model`: "estimated, typically within 2 °C".
  - Lake routes in summer: "provisional estimate; typical error 1.7 (or 2.0) °C at lakes in a summer test", and that
    the lake test failed.
  - October to April: "provisional estimate, not yet checked in these months". No error is claimed where none was
    measured.
- **Expected winter direction (inferred, not measured).** The curves were fitted on summer samples. With air near
  freezing they give 7–8 °C water, which is probably too warm in cold spells. The first winter readout below is meant
  to show how far.

## Missing and stale inputs

- **Air incomplete.** A spot without all 30 days of air in this update gets `water_temp_est_missing` (`why`: `air` or
  `error`). The page says "No estimate in this update: the air temperatures it is worked out from did not all arrive".
  It never shows an older estimate as today's.
- **Estimate from another day.** The page shows an estimate only on its own day. A page opened the next day, before a
  new update, shows none.
- **Prefetch fallback.** If the rain prefetch falls back to a forecast up to a day old, the last day of air is missing,
  and the spot says so.

## Measuring the error from now on

Every build that forecasts appends each spot's estimate to `state/water_temp_estimates.parquet`. A row has the spot,
day, route, the estimate and the 7-day air, and the EA sensor reading beside it where the spot has one. The rows are
only ever added to, and the rolling state release carries the file.

The log saves estimates before the observations arrive, so it measures operational error, in winter too. The sensors
beside named spots are few: 3 today (Bures Mill, Boxted Mill, Gaters Mill). So the first readout will be thin.

Next sources for winter error, none needing a new account or paid service:

- the EA Hydrology API's other temperature sensors, compared at their own cells (this needs those cells' air: the cost
  is stated before any request);
- the Water Quality Archive's winter spot samples (determinand 0076), against archived air;
- HadUK-Grid winter months, which need Ethan's CEDA token, so are not used yet.

## Coverage matrix

Live data, 31 Oct 2026.

| Catalogue | Waters | Water types | Estimate route | State |
|---|---|---|---|---|
| Named spots (spot pages, list, map, planner) | 109 | 72 rivers, 37 lakes (18 of 1 km² or more, 9 smaller, 10 of unknown area; 3 isolated) | this PR: every one, all year, where the air arrives | before: 0 estimates (May–September rivers only, now November), 3 sensor readings |
| Coastal directory (England) | 426 | 373 coast, 53 estuary | #479: sea surface; needs a source and its offshore distance said | none yet |
| Wales directory | 114 | 107 coast, 3 estuary, 2 river, 2 lake | inland: these routes, once their cells' air is costed; coast: #479 | none yet |
| Scotland directory | 90 | not typed in the file | to classify, then by type | none yet |
| Ireland directory | 243 | not typed in the file | to classify, then by type | none yet |
| Northern Ireland directory | 33 | 32 coast, 1 inland | #479; inland by type | none yet |
| Click-anywhere (any river or lake point) | any | river or lake | these routes, in the page, from the point's cell air | none yet |

A partial rollout is progress, not the end of #492. Each remaining row is tracked on #477, #478 and #479 until it has a
route and a published value.

## Shown where

- **The spot page's Water temperature tile.** A sensor reading comes first where there is one, and the estimate is
  worded by its route.
- **Plan a swim.** Each outing column's line gains "water about N °C today, estimated" (or "provisional estimate").

The conditions panel (#491) is to use the same field when it is built.

## Not done here

- **Other catalogues.** The directories and click-anywhere, as in the matrix above.
- **Winter error.** Not yet measured; the readout comes after the log has a few weeks of rows beside sensor readings.
- **Better lake routes.** A longer air memory, or depth, for large lakes. These are separate improvement candidates,
  kept apart from the frozen pollution studies.
