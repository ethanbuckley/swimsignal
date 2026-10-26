# Will the river at a spot rise in the next few hours? Scope, coverage and an evaluation plan

Written 26 October 2026. Research only. Nothing here changes the live site, a level, the words "high" or "rising
fast", or any shadow or test window. **This is not a swimming-safety forecast.** No model has been fitted or scored.

## Why

Spot pages already say "high" or "rising fast" from the nearest Environment Agency level gauge on the spot's own river
(`src/dipcast/ingest/flows.py`). "Rising fast" means the gauge rose more than a fifth of its usual range
(`RISING_SHARE` 0.2) over the last six hours (`RISE_WINDOW_H`). It says what has happened at the gauge. It says nothing
about the next few hours.

A rise usually starts upstream. If a gauge upstream has risen, or rain has fallen on the catchment above the spot, the
spot's river may rise a few hours later. This file asks whether such a short-horizon extension is feasible with data the
project can get: are there upstream gauges, how long are their records, how complete are they, how long do rises take to
arrive, and how late is the data published. It ends with a dated plan for testing it. It does not test it.

## Licences and request guidance (read 26 October 2026)

Both pages were downloaded on 26 October 2026 at about 18:37 UTC and read in full for the passages below.

**EA real-time flood-monitoring API.** Page: https://environment.data.gov.uk/flood-monitoring/doc/reference.
- Licence: "These APIs are provided as open data under the Open Government Licence with no requirement for
  registration." Every response's metadata names OGL v3
  (`http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/`).
- Attribution: "If you make use of this data please acknowledge this with the following attribution statement: this
  uses Environment Agency flood and river level data from the real-time data API (Beta)".
- Publication: "Water levels and flows are regularly monitored, usually every 15 minutes. However, data is transferred
  back to the Environment Agency at various frequencies, usually depending on the site and level of flood risk.
  Transfer of data is typically once or twice per day, but usually increases during times of heightened flood risk."
- Request guidance: for the latest values, "issue a single call every 15 mins" to `/data/readings?latest`, which "is
  much preferable to crawling all the stations every 15 mins". The readings endpoints hold "the recent period (up to
  the last four weeks)"; older readings are in daily CSV dumps under `/flood-monitoring/archive`.
- Safety: the APIs "do not offer a guarantee of service level and should not be relied upon for safety critical
  applications. They do not replace the existing channels by which the Agency notifies members of the public and
  partner organizations of floods and flood risk."
- Size: readings default to 500 items, "up to a hard limit of 10000 items".

**EA Hydrology API.** Page: https://environment.data.gov.uk/hydrology/doc/reference.
- Licence: response metadata `"license": "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"`,
  `"licenseName": "OGL 3"`. The page footer: "All content is available under the Open Government Licence v3.0, except
  where otherwise stated".
- Request guidance: "We ask that users who are automatically downloading bulk data to limit the number of non-batch
  API requests they make at any one time. Ideally limit to one request in flight at a time, waiting for each request to
  finish before issuing the next." The EA "may find it necessary to block users who place excessive demands".
- Size: readings calls have "a soft limit of 100,000 rows per-call" and "a hard limit of 2,000,000 rows". `?earliest`
  returns a measure's first reading.
- Latency: a measure's `hasTelemetry` "indicates that high resolution data from this station may updated directly from
  a telemetry feed and so has less latency that data only received via wiski services".

What this means (inferred, not legal advice): using both for research is allowed. Anything shown on the site would
carry the flood-monitoring attribution, as the site's gauge words already do. The EA's own words rule out presenting
any of this as a safety-critical warning.

## Network caps, fixed before any request

Written into `scripts/river_rises_coverage.py` as constants before it made any request:
- at most **300 requests per run** (`MAX_REQUESTS`), all hosts together; cached answers do not count;
- **one request at a time, 1.5 s apart** (`PAUSE_S`);
- **EA hosts only** (`environment.data.gov.uk`, https). **No Open-Meteo request at all**: its daily ledger is shared
  with the live site;
- **stop the run at the first 403, 429 or 5xx**, or a connection error; redirects are not followed and also stop it;
- **every answer cached** in a scratch folder outside git; a rerun without `--fetch` reads only the cache and stops at
  the first missing answer;
- every request logged (time, status, size, URL) in the cache's `requests.log`.

Rain: no rain is fetched. The Met Office radar months already saved in `data/raw/met_office_radar/` (hourly, per
0.1° rain cell, from 21 November 2024) are only checked for presence.

## What the prototype does

`scripts/river_rises_coverage.py` (constants named in capitals below are in that file):
1. **Spots.** The river spots in `spots.csv` and `spots-osm.csv`, placed on the network with `locate_pin` and the
   build's hints, as `scripts/glofas_check.py` does. Lakes are left out: the site's gauge words need a gauge on the
   spot's own river.
2. **Spot gauge.** `flows.station_pick` exactly as the site calls it (15 km, the spot's river name), with its requests
   routed through the capped client. "Usable" is the site's own test: the gauge's river shares a word with the spot's
   (`names.same_river`) and the gauge has a usual range.
3. **Upstream gauges.** One request for every EA level station (`/id/stations?parameter=level&type=SingleLevel`).
   Each within 50 km of a usable spot gauge is snapped to a river link (within 250 m). A station counts as upstream if
   it is upstream of the spot gauge along the network within 50 km (`UP_MAX_KM`) and at least 0.5 km away. Its
   catchment share is the network's upstream length at each, as in the GloFAS check.
4. **Publication delay.** One request for the latest reading of every level measure, the call the site makes. For each
   spot gauge and upstream gauge: the reading's age at the moment of the request. One snapshot, not a distribution
   over time.
5. **History.** The EA Hydrology station list (one request), matched on `stationReference`, then `wiskiID`, then
   `RLOIid`, for each gauge's 15-minute level series. For a bounded sample of pairs: one pair per spot gauge, the
   nearest upstream gauge on the same river name, at least 3 km up, with at least a quarter of the spot gauge's
   catchment; at most 25 pairs (seeded sample if more). For each gauge in the sample, two requests: its earliest
   reading, and its readings from 1 October 2025 to 25 October 2026 as CSV. Readings marked Suspect, Rejected or
   Missing are dropped.
6. **Coverage.** Per sampled series: the share of 15-minute slots with a reading, gaps of an hour or more, the longest
   gap, the first and last reading. The opening date of every spot gauge with a Hydrology series, from the station list.
7. **Lags.** On each sampled pair, the spot gauge's own "rising fast" onsets (a rise of more than 0.2 of its EA usual
   range over 6 hours, at most one per 48 hours). For each: the spot gauge's peak in the 24 hours after the onset, the
   upstream gauge's peak from 36 hours before that to 6 hours after, and the lag between the two peaks. The upstream
   gauge must itself have risen more than 0.2 of its usual range in the 24 hours before its peak, or no lag is
   counted. Its usual range is the 5th to 95th percentile of its own readings in the window (the EA range was not
   asked for, to save requests). Also reported: the lag that best matches the two gauges' 15-minute changes (0 to 36 h),
   and how long before the spot gauge's onset the upstream gauge met the same rule.

The tests (`tests/test_river_rises_coverage.py`) check the lag on synthetic hydrographs, the gap counts, the cap, the
stop on 403, 429, 5xx and redirects, that nothing is fetched without `--fetch`, and that the evaluation's window builder
(`issue_rows`) reads nothing after its cut.
