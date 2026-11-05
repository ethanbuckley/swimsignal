# Water temperature on spot pages (27 Oct 2026)

Scope and coverage check. Branch `feat/water-temperature`.

**The tile already exists and is live.** Roadmap task 9 added it on 3 Oct 2026 (commit 1ec864d,
then e6bc1fd for upstream-first): `build_site.attach_water_temperature`,
`src/dipcast/ingest/water_temperature.py`, the `waterTile` function in `src/dipcast/site/index.html`,
the Terms credit and the `water_temp` field on the Data page. This branch adds no second tile. It adds
a read-only coverage script (`scripts/water_temperature_coverage.py`), its tests, and this note.

## Request caps (written before any fetch)

Every request this work makes to the Environment Agency, by hand or by
`scripts/water_temperature_coverage.py`, keeps to these caps:

- At most 300 requests per run.
- One request in flight. Another worker may query EA Hydrology at the same time.
- At least 1.5 s between the end of one request and the start of the next.
- Stop the run on HTTP 429 or any 5xx. Do not retry.
- EA hosts only: `environment.data.gov.uk`. No Open-Meteo, no other host.
- Every answer cached on disk. A cached answer is never asked again.
- The `User-Agent` is the project's own (`config.EA_HEADERS`).

The script's `CappedClient` enforces all of these, and `tests/test_water_temperature_coverage.py`
checks it.

**Requests used on 27 Oct 2026, 01:02 to 01:06 UTC: 10.** None was refused. They were the two
reference pages, the flood-monitoring temperature measures and stations, the Hydrology temperature
measures and stations, one week of Hydrology temperature readings, the latest reading of the 16
gauge temperature series (one request), and two single-series reads to tell water from air.

## Licence

Both APIs are Open Government Licence v3.0. Each JSON answer says so in its `meta` block.

- **Flood-monitoring API.** Its reference page asks users to acknowledge the data with this
  statement: "this uses Environment Agency flood and river level data from the real-time data API
  (Beta)". The Terms page already carries it for river levels.
- **Hydrology API.** Its reference page gives the licence (`"licenseName": "OGL 3"`) and a fair-use
  note (readings calls have a 100,000-row soft limit and a 2,000,000-row hard limit). I found no
  attribution statement on it. The Terms page credits it as "© Environment Agency copyright and/or
  database right 2026. All rights reserved.", under the heading that says all EA data there is OGL
  v3.0. Not checked tonight: the OGL page itself (not an EA host, so outside the caps). OGL's
  default, where a provider gives no statement, is "Contains public sector information licensed
  under the Open Government Licence v3.0."

## Air or water

**Established (27 Oct 2026):**

- Hydrology API: 2,012 temperature measures at 1,964 stations.
  - 1,948 measures are at 1,948 `WaterQualityStation`s: sondes in the water. Each deployment is a
    new station. Grouped by label without the team and start month, they are 1,859 sites.
    157 stations are Active and 1,791 are Closed.
  - 64 measures are at 16 `RiverStation`s (level or flow gauges in the Midlands): one 15-minute
    series each, plus daily min, mean and max. None is current. Their latest readings are from
    2013 (Evesham), July 2024 (4 gauges) and 20-21 Nov 2025 (6 gauges); 5 returned no latest
    reading.
  - Derby St Marys' series moved by a median 0.6 °C a day (maximum 1.8 °C) over 174 days from
    June to November 2025. Air moves several degrees a day, so this one is water.
- Flood-monitoring API: 25 temperature measures. 23 are air (22 "Dry Bulb", 1 "Wet Bulb"). The
  API's own reference says `temperature` is dry-bulb air temperature. 2 are qualified "Water", at
  stations 151816001 ("Romsey Broadlands Estate", on the Test) and 152206005 (labelled "Rainfall
  station", 4.3 km from River Itchen, Compton Lock). Both had a reading in the last day.

**Inferred, not checked:** the other 15 gauge series are water too, since they are the same kind
of station as Derby. It does not matter for the site, since none is current.

So the split the brief asked about is by **station type**, not by measure metadata. Every Hydrology
temperature measure has `parameterName` "Temperature", and none says air or water. The site uses
only sondes and gauges. The script calls anything else "unknown".

## Coverage

Spots: the 105 in `spots.csv` and `spots-osm.csv` (72 river, 33 lake; 38 designated bathing
waters). The rule is the site's: a sensor whose river name matches the spot's river, at most
15 km away in a straight line, joined to the spot by the river network on the same side of the
tidal limit, and read in the last 24 hours. An upstream sensor is taken before a nearer one
downstream. For lakes, the sensor must carry the lake's own name. A beck flowing into the lake does
not count. The network is the local `river_network.pkl` of 11 Sep 2026.

Measured at 01:05 UTC, 27 Oct 2026:

| | count |
|---|---|
| Sensors with a reading in the last 24 h | 98 (all of the 98 that reported in the last 7 days) |
| Age of their latest reading | median 1.1 h, maximum 16.1 h |
| Reporting interval | hourly 78, 15 min 14, 30 min 5, other 1 |
| Spots with a same-water sensor within 2 km | 0 |
| ... within 5 km (straight line) | 1 (Dedham, Boxted Mill at 5.0 km) |
| ... within 15 km | **3 of 105** (3 of 72 river spots, 0 of 33 lakes) |
| ... of which designated bathing waters | 1 of 38 (Friars Meadow) |
| ... of which upstream | 1 |
| Spots with only a past (closed) deployment on their water within 15 km | 35 |

The three spots:

| Spot | Sensor | Straight line | Along the river | Reading |
|---|---|---|---|---|
| Friars Meadow, River Stour | Bures Mill | 8.1 km | 10.9 km downstream | 10.5 °C, 1.1 h old |
| River Stour, Dedham | Boxted Mill | 5.0 km | 7.4 km upstream | 10.4 °C, 4.0 h old |
| River Itchen, Compton Lock | Gaters Mill | 10.1 km | 13.1 km downstream | 12.7 °C, 0.3 h old |

Without the network check, a fourth spot matched: Ham and Kingston, by the Brentford Barge sonde.
That sonde is on the tidal Thames, so the site's rule passes it over, as it should.

**History.** Sonde deployments are short: most of the 35 "past only" spots had one deployment
lasting weeks to months. Examples: Nidd at the Lido, Knaresborough, had a sonde 0.3 km away from
Jan to Dec 2025; Wharfe at Cromwheel, Ilkley, 0.1 km away from Jun 2019 to Mar 2020; Wolvercote and
Port Meadow, Eynsham Lock from Apr to Aug 2025; the Serpentine in summer 2012. One lake spot had any
past same-water sonde. There is no long record to build a seasonal figure on for any spot.

**"Active" is not "reporting".** 172 stations are Active, but 98 reported in the last week.
For example, TEST_HOUGHTON_E_202504 (9.1 km from Chilbolton) is Active with no readings in 7 days.
WSX_AVON_HAMPS_E_202605 (0.8 km from Fordingbridge) opened 5 May 2026 and has `dateClosed`
1970-01-01, a placeholder.

**One doubtful live value.** BURE_ACLE_E_202601 read 21.0 °C at 12:25 UTC on 26 Oct. The 98 live
sensors had a median of 11.0 °C. The next warmest were Counter Drain at Flag Fen (18.0 °C) and the
Lee in east London (16.3 °C and 15.6 °C). I did not check whether any of these is a fault. The
site's plausibility range is -1 to 35 °C, so all of them pass. No spot is near any of them, so the
site shows none of them.

## What the site shows, and what it never claims

Already built (3 Oct). Nothing here changes it.

- A river spot with a matching sensor gets a Water temperature tile: the figure, then "Measured at
  Bures Mill on the Stour, 10.9 km downstream, 1 h ago". The age is counted when the page is read.
  The tile's detail says the water where you swim can be warmer or colder, says when the EA has not
  checked the reading, says it is not part of the pollution level, and links the EA's page for the
  sensor.
- It is an observation. It is never a forecast, never an estimate for the spot, and never an input
  to the level.
- No tile when there is no sensor on the same water, or the sensor is on the other side of the tidal
  limit, or the network does not join the two, or the latest reading is over 24 h old at build
  time. Lakes get none.
- Cost per build: two Hydrology requests (readings since the start of yesterday, about 1 MB, and the
  active temperature stations, about 0.5 MB; the module's 3 Oct measurements). Each is tried once
  more after a 403, 429 or 5xx, so at most 4. No Open-Meteo.
- Failure: any error leaves every spot without a tile and the build carries on.
  `tests/test_water_temperature.py::test_a_failed_request_leaves_every_spot_without_and_the_build_counts_them`
  checks this. `tests/site_water_temp.test.cjs` checks the rendering.

## Running the script

```
uv run python scripts/water_temperature_coverage.py --network data/processed/river_network.pkl --out /tmp/wt.json
```

It makes 5 requests on a cold cache (`data/cache/water_temperature_coverage/`) and none on a warm
one. `--now` fixes the clock. Without `--network` it skips the up/downstream and tidal checks and
over-counts. Today that gives 4 instead of 3.

## Open questions for Ethan

1. **Keep the tile on?** 3 of 105 spots get it, and 1 of 38 bathing waters. It costs 2 requests a
   build and is correct where shown. My recommendation is to keep it as it is and spend no more on
   it until the EA deploys sondes for the 2027 season. Then re-run the script in May or June.
2. **Hide stale readings when the page is read?** The build drops readings over 24 h old. The page
   then shows the age as it grows ("26 h ago" is tested on purpose). If builds stop for days, as on
   25 Oct, a spot shows a days-old reading with its true age. The alternative is hiding it after,
   say, 48 h at read time.
3. **Add the flood-monitoring water sensor near Winchester?** Station 152206005 is 4.3 km from
   Compton Lock, and its measure's period is 15 minutes. Its label is "Rainfall station" and it has no river
   name, so I cannot confirm it is in the Itchen. Adding it would cost one more request a build.
4. **Tighten the plausibility check?** A 21 °C reading in late October passes -1 to 35 °C. A check
   against the other live sensors would catch it. Any fixed margin would also need to pass urban or
   effluent-fed water, such as the Lee at 16 °C. It does not matter yet, since no spot is near any
   of these sensors.
5. **Ask the EA where sondes will go in 2027?** Deployments follow EA projects, not swim spots. Past
   ones sat at Knaresborough Lido and Ilkley, both bathing waters, so a request could be welcome.
