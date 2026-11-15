# EA sonde readings on a spot's page: the observation contract, version 1

Written 13 November 2026, register row **Sonde signal #403** (`docs/RESEARCH-RECOVERY-2026-10.md`), route "public
research observations" (`docs/RESEARCH-WORKFLOW.md`). It is the deliverable that row names: "show correctly located,
dated sensor readings where useful". It is an observation beside the forecast. It is not test #403, does not run or
relabel it, and scores nothing. A separate session is checking the same sondes offline (arrival times); nothing here
uses or reads its work.

Made by the build: `build_site.attach_sondes`, with `src/dipcast/ingest/sondes.py`. File `data/sonde-readings.json`
(4.5 kB on 13 November). The spot page reads the same block from `spots-lite.json` (`sonde`), and draws it as the
"Ammonium sensor" tile (`index.html`, `sondeTile`; `docs/DESIGN.md`, "Ammonium sensor").

## Identity and source

- **What.** The latest readings of an Environment Agency water-quality sonde (a sensor left in a river that measures
  it every 15 minutes and publishes the readings before anyone has checked them): ammonium (mg/L), dissolved oxygen
  (% saturation) and turbidity (NTU). Plus the ammonium readings of the last day, for a line on the page.
- **Source.** The EA Hydrology API. Readings: `/hydrology/data/readings.json`. Stations: `/hydrology/id/stations.json`.
  Times carry no zone; they are UTC (`water_temperature.py`, checked 3 October 2026).
- **Licence.** Open Government Licence v3.0, named in every answer's `meta` (`"licenseName": "OGL 3"`, read again on
  13 November 2026). Credit on the page and in the file: "Contains Environment Agency data licensed under the Open
  Government Licence v3.0."
- **Measures.** `<station>-amm-i-subdaily-mgL`, `<station>-do-i-subdaily-pct`, `<station>-turb-i-subdaily-ntu`, each
  with period 900 s. The same sondes also give dissolved oxygen in mg/L (`-do-i-subdaily-mgL`), which is not read.

## Requests: two a build, never one per spot

| Request | Parameters | 13 Nov 2026 |
|---|---|---|
| readings | `observedProperty` three times (ammonium, dissolved-oxygen, turbidity), `mineq-date` the start of yesterday (UTC), `_limit` 100,000 | 18,669 readings, 3.5 MB, 5.6 s |
| stations | the same three `observedProperty`, `status=statusActive`, `_limit` 10,000 | 154 stations, 0.4 MB, 0.5 s |

- **Measured on a real run**, 13 November 2026 at 15:22 UTC, the build's own function over the live site's 133 spots
  (scratch `DIPCAST_ROOT`, the main checkout's river network read only): `fetch.requests` = **2**. The count does not
  change with the number of spots: a test runs 40 river spots on one fetch (`tests/test_sondes.py`).
- The API answers a key given more than once as "any of these" (checked 13 November 2026: one request returned all
  three properties). Every measure in the readings answer had its station in the stations answer (335 of 335).
- **Retries.** A 403, 429 or 5xx is tried once more after 5 s, as the water-temperature line does, and counts twice.
  So at most four requests.
- **Fail soft.** Any error leaves `status` "unavailable" with `fetch.error`, no spot gets the tile, the build carries on,
  and its health lists a warning. Nothing is kept from an earlier build.
- **Before this was written,** working out the request shape took 3 requests to the API (one `latest` list, which
  ignored `_limit` and took 39 s for 1,704 rows, so it was not used; then the two above). With the real run, 5 in all.

## Which sonde a spot gets

All of these, in this order (`sondes.nearest_on_river`):

1. **A river spot.** Lakes get none: a beck's sonde reads the beck, not the lake (Mill Beck by Windermere,
   `docs/LAKE-TEMPERATURE-SENSORS-2026-10.md`).
2. **The spot's own river by name**: the sonde's river, from its label or `riverName` (`water_temperature.parse_label`),
   shares a distinctive word with the spot's (`names.same_river`). A spot or sonde with no river name gets nothing.
3. **Joined along the river network**, on the same side of the tidal limit (`water_temperature.river_relation`).
4. **Upstream at most 20 km along the river, or within 0.25 km of the spot either way** ("at the spot"). Never
   further downstream: water there has passed the spot. 20 km is #403's own cap, chosen there before the network was
   loaded. Straight-line distance only narrows the list first (20 km): a sonde 20 km along the river is never further
   than 20 km in a straight line.
5. **The nearest along the river**, then the station id.
6. **Only stations with an ammonium measure.** Their dissolved oxygen and turbidity ride along. A station with
   turbidity alone is not shown.

A station listed as active whose ammonium sent nothing in the last day still counts, with no readings, so the page
can say it has gone quiet.

## Which readings count

- The latest reading of each property no more than 24 h before the build (`flows.MAX_READING_AGE_H`, the site's rule
  for a gauge or a temperature sensor) and no more than 1 h after it.
- Plausible values only: ammonium 0 to 100 mg/L, dissolved oxygen 0 to 300% saturation, turbidity 0 to 4,000 NTU (#403
  used the same bounds for the first and last). On 13 November 314 readings fell outside (157 ammonium over 100 mg/L,
  157 negative turbidity).
- Readings the EA labels "Suspect" or "Missing" are not used. Every other label is shown as the EA writes it. On 13
  November all 18,669 readings were "Unchecked": raw data the EA has not inspected.
- On the page the age is counted again when the page is read. A reading over 24 h old by then shows no figure and says
  how old it is ("Last reading … 26 h ago: too old to use.").

## What it may and may not say

- **May say:** the sonde's name and place, its river, how far upstream along the river (or at the spot), the reading,
  its unit, how long ago it was taken, the EA's label for it; the range of the last day's ammonium readings.
- **Says every time it shows a figure:** "Ammonium is a marker that can come from sewage. It is not a count of bacteria
  and not a sign that the water is fit to swim in." Where there is no current reading: "No reading does not mean clean
  water." The fold says both, that the sensor is not at the spot, and that the reading is not part of the pollution
  level.
- **May not say or do:** a bacteria count or an E. coli figure; a swimming clearance or "safe"; a level, a colour, a
  band or advice worked out from any reading; that a low or missing reading means clean water; that the reading is the
  water at the spot. No reading enters the forecast, the level, the alerts or any other file. The tile is in ink, with
  no level colour, and its drawing starts from zero.
- Who decides the public wording: Ethan. The PR is a draft for that reason.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version`, `generated_at` | `"swimsignal.sonde-readings"`, `"1.0.0"`, the build's time (UTC) |
| `status` | `ok`, or `unavailable` when the EA did not answer |
| `source` | the two addresses, the licence and the attribution sentence |
| `rules` | `properties` (key, unit, measure pattern, plausible range), `max_age_h` (24), `up_km` (20), `at_km` (0.25), `drop_quality`, `kinds` (`["river"]`) and the rule in words |
| `claim` | `public_wording`, the sentence above, and `not_claimed` |
| `fetch` | `requests` (retries included), `readings`, `since` (the day the readings start), `dropped` (readings not used, by reason), `error` |
| `coverage` | `river_spots`, `with_sonde`, `with_ammonium_reading`, `sondes_listed` (active stations with an ammonium measure), `sondes_with_ammonium_reading` |
| `spots[]` | `spot_id`, `name`, `sonde` |
| `sonde` | `station_id`, `station`, `where`, `river`, `url` (the EA's page), `direction` (`upstream` or `at`), `river_km`, `readings` by property (`value`, `unit`, `observed_at` in UTC, `age_hours` at the build, `quality` as the EA writes it), `series` (`[[time, mg/L], …]`, the last day's ammonium, oldest first) |

## Coverage, 13 November 2026 (the recount)

- **73 of 134** active ammonium stations sent a reading in the last day.
- **12** of those are within 5 km in a straight line of a listed spot, the same count as the source inventory's (25
  October). Seven are on becks or the Leven around Windermere, all beside lake spots (the inventory said eight); two on
  the tidal Thames, beside the Serpentine; two on the Stour by Dedham; one on the Fowey.
- **Under the rule above, 2 of 85 river spots get the tile:**
  - River Stour, Dedham: Boxted Mill (`E06651A`), 7.4 km upstream. Ammonium 1.89 mg/L at 15:06 UTC, Unchecked.
  - River Tame, Dosthill, Tamworth: Lea Marston (`E06141A`), 7.5 km upstream. Ammonium 1.22 mg/L at 15:01 UTC,
    Unchecked.
- Why the others do not: Respryn Bridge's Restormel sonde is 1.3 km downstream; Golitha Falls's is 19.1 km downstream;
  Friars Meadow's Stour sondes are 10.9 and 24.6 km downstream; Dedham's Cattawade sonde is 6.0 km downstream (Boxted
  Mill is shown); Bures Mill is 21.1 km above Dedham, past the cap; Ham and Kingston's six Thames sondes are on tidal
  water; the network does not join Compton Lock to its Itchen sonde (Portswood STW) on the same side of the tidal limit. The
  lakes are out by rule 1.
- The live sondes report hourly here, not every 15 minutes: 24 ammonium readings in the day at both.

## Not done, and what would change it

- **Lake spots.** The seven Cumbrian sondes are the largest group near listed spots. A beck flowing into Windermere is
  not the lake's water, so this version shows none. A version for lakes needs its own rule (an inflow whose mouth is
  near the spot, say) and its own words, which are Ethan's to decide.
- **Turbidity-only stations** (11 active on 13 November) are not shown. They would need their own sentence: turbidity
  rises with any rain.
- **No history is kept.** Each build writes the latest; nothing is logged for later scoring. A research use would need
  its own protocol (#403's gate stays as written).
- **Not checked:** Safari, a screen reader, 320 px, and a build run on GitHub's runners (the EA gateway refused some
  runner requests before, `water_temperature._get`). Fail-soft covers a refusal; it was not seen here.
