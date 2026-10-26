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
   reading, and its readings from 1 October 2025 to 24 October 2026 as CSV (`max-date` 25 October, exclusive). Readings marked Suspect, Rejected or
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

## What the prototype found (run 26 October 2026, 18:45 to 19:03 UTC)

Run from commit `1326c30`, the commit that set the caps. The tables are in a scratch folder, not in git. Every figure
below was measured on that run unless marked inferred.

### Requests

219 requests, all HTTP 200. No stop, no retry. 283 MB downloaded, 272 MB of it the 42 readings files.

| What | Requests | Size |
|---|---|---|
| Stations near each spot (`station_pick`) | 72 | 1.5 MB |
| Stage scales (`station_pick`, linked scales) | 60 | 0.1 MB |
| National level-station list | 1 | 2.5 MB |
| Latest reading of every level measure | 1 | 1.3 MB |
| Hydrology station list | 1 | 5.6 MB |
| Earliest reading, per sampled series | 42 | under 0.1 MB |
| 15-minute readings, 1 Oct 2025 to 24 Oct 2026, per sampled series | 42 | 271.8 MB |

No Open-Meteo request was made. No rain was fetched.

### Coverage

- **Spots.** 72 river spots, and every one got some gauge within 15 km. 66 have a usable gauge by the site's own test
  (on the spot's river, with a usual range), on 55 distinct gauges. The other 6 got a gauge on another river: Sandy
  Lane (Chester), Janet's Foss, Rivelin, Padley Gorge, Lathkill and Bradford Dale.
- **Upstream gauges.** 48 of the 66 usable spots (39 of 55 gauges) have at least one EA level station upstream of
  their gauge within 50 km along the network. 46 spots (37 gauges) have one on the same river name. Among the 39
  gauges, the number upstream is 1 to 47, median 6.
- **No upstream gauge: 18 spots.** Some are headwaters with nothing above them (Bellever on the East Dart, Carnwood on
  the Plym, Chagford on the Teign, Ulpha on the Duddon, Hug Bridge on the Dane). Some are not: Hambleden Lock and
  Temple Lock on the Thames, Houghton on the Great Ouse and Barcombe on the Sussex Ouse all have gauges upstream on the
  map. **Inferred, not checked:** those gauges snapped to a lock cut or side channel whose upstream trace is short. So
  48 is a lower bound.
- **History.** 45 of the 55 spot gauges matched a Hydrology 15-minute level series. The other 10 did not match by
  `stationReference`, `wiskiID` or `RLOIid`. Whether they have one under another id was not checked. All 45 opened
  before 2015: opening year 10th percentile about 1961, median 1982, 90th percentile 2003. Of the 42 sampled series,
  the year of the earliest reading has median 1988 (10th percentile 1969, 90th 2004).
- **Gaps (42 sampled series, 1 Oct 2025 to 24 Oct 2026).** The share of 15-minute slots with a usable reading has
  median 1.00 (10th percentile 0.96). Gaps of an hour or more: median 0 per series, 90th percentile 2. The longest
  gap has median 0.5 h and a long tail: 75th percentile 46 h, 90th 228 h. Four series have under 95% of slots. The
  worst (33.6%) stopped on 8 February 2026, and 15,630 of its readings were marked Suspect. Two others lose 26% and
  30% of their readings to Suspect flags.
- **How recent the Hydrology series are.** 39 of the 42 end at 24 October 2026 23:45 UTC, the last slot asked for.
  Two end on 15 October, one on 8 February. So the Hydrology API carries 15-minute levels to within a day. Much of
  the recent part is marked "Unchecked", not "Good".
- **Radar.** 57 of the 66 usable spots have saved radar months for their rain cell. The 9 without have no saved file
  for their cell (for example Low Force on the Tees, Chilbolton on the Test, Dartington on the Dart).

### Publication delay (one snapshot)

The latest-readings call at 18:59:43 UTC on 26 October 2026 held a reading for 298 of the spot and upstream gauges.
The reading's age at that moment: median 0.5 h, 75th percentile 0.75 h. 21 of 298 were over 1 hour old, 3 over 6
hours. One of the three is a spot gauge: Izaak Walton on the Dove (Dovedale stepping stones), last reading 15
October, 270 h old. The site already treats a reading over 24 h old as stale.

This is one evening. The EA page says transfer is "typically once or twice per day" and increases at times of flood
risk. On this evening most gauges were within 45 minutes. **Not measured:** how the delay varies by day, by gauge, or
during a rise. That needs repeated snapshots, which the site's builds already make (one latest call per build).

### Arrival lags (25 sampled pairs, 1 Oct 2025 to 24 Oct 2026)

The pairs: one per spot gauge, the nearest upstream gauge on the same river with at least a quarter of the
catchment, at least 3 km up. 25 pairs, 3 to 45 km apart (median 18 km).

- **Events.** The spot gauges met the "rising fast" rule 358 times (at most once per 48 hours), at 24 of the 25
  pairs. Hannington Bridge on the Thames met it never. Events per pair: median 11.5, 10th percentile 2, 90th 31.
- **Of the 358,** a lag was measured for 308, at 23 pairs. At 42 the upstream gauge did not rise by a fifth of its
  usual range. At 8 its readings were missing. Langham on the Stour had 2 onsets and no measured lag.
- **Peak-to-peak lag, 308 events:** 10th percentile −0.5 h, 25th 0.25 h, **median 1.5 h**, 75th 3.3 h, 90th 6.5 h.
  58 lags are negative: the "upstream" gauge peaked after the spot gauge.
- **Per pair,** the median lag runs from −6 h to 28 h. The median across pairs is 1.1 h. 7 of 23 pairs have a
  median of 3 h or more. 5 of those have at least 5 events: Rothbury on the Coquet (6.1 h, 12 events), Low Moor on
  the Ribble (6.8 h, 13), Old Wye Bridge at Hereford (5.3 h, 16), Great Corby on the Eden (4.4 h, 12) and Addingham on
  the Wharfe (3.0 h, 31). The long Thames lags (Sutton Courtenay 28 h, Farmoor 16.6 h) rest on 1 and 2 events.
- **One pair is not a river wave.** Trowlock Island and Thames Ditton Island (the Thames above Teddington) gave 59
  onsets, 25 of its 39 lags negative, and a best-matching change lag of 24 h. Inferred: lock and weir operation, not
  a rise travelling downstream. Without this pair the median lag is 1.75 h (269 events, 33 negative).
- **The best-matching 15-minute change lag** (secondary): median 2.0 h, 75th percentile 4.25 h.
- **Implied wave speed** (distance over a positive lag): median 1.9 m/s, 10th to 90th percentile 1.0 to 4.0 m/s.
- **How early the upstream gauge met the same rule** before the spot gauge did: median 5 h, 75th percentile 19 h.
  Inferred: the 36-hour search window often catches an earlier, separate rise. This is not a usable lead time.
- **The EA usual range is wider than a year's spread.** At the 25 spot gauges, the 5th-to-95th-percentile spread of
  the year's readings was median 0.6 of the EA usual range (0.33 to 1.4). The upstream gauges here were judged on
  that spread, because their EA range was not asked for. So their rule was looser than the site's rule would be.

### What this says (inferred from the figures above)

- **Data is not the obstacle.** Most usable spots have an upstream gauge. The 15-minute records go back decades. The
  recent year is about 99% complete at the median. The Hydrology API is current to within a day. On the one evening
  measured, the real-time feed was about 30 minutes behind.
- **Lead time is.** At the median pair a rise reaches the spot gauge about 1.5 hours after the upstream gauge. The
  real-time reading is about 0.5 hours old when the site sees it, and the site builds every 30 minutes. So at most
  spots an upstream gauge gives about an hour of notice, often less. Only a few longer rivers (Coquet, Ribble, Wye at
  Hereford, Eden, Wharfe at Addingham) show 3 to 7 hours.
- **A horizon of several hours needs rain.** The rain that drives a rise falls before any gauge moves, so only rain
  (radar now, forecast later) could add hours. Radar is saved locally for 57 of the 66 usable spots.

## Evaluation plan (stated 26 October 2026, before any model is fitted)

Nothing below has been run. The coverage and lag figures above have been seen. No label rate, no model and no
reference has been computed. Results will go in a later section. Nothing in this plan changes after a score is seen,
except by a dated amendment written before the run.

### The question

At an issue time when the site shows no word for the spot (the gauge neither "high" nor "rising fast"), will the
spot gauge rise by more than a fifth of its usual range in the next three hours? And do upstream gauges and radar
rain, as published by then, say so better than the spot gauge's own recent trend?

### Target

- **Issue times:** every hour on the hour, UTC.
- **Label:** 1 when the spot gauge's highest reading in (t, t + 3 h] is more than 0.2 of its EA usual range above its
  last reading at or before t; 0 otherwise; missing when either side has no reading. 0.2 is the site's
  `RISING_SHARE`, unchanged. The range is the EA's `typicalRangeHigh` minus `typicalRangeLow`, as the site uses.
- **Primary horizon 3 h,** because the median measured lag is 1.5 h and only rain could see further. **Secondary
  6 h,** for the radar candidate only.
- **Primary population (P):** issue times where the spot gauge had a published reading at most 24 h old by t, its
  index was at most 1 (not "high"), and it had not risen more than 0.2 of its range over the last 6 h (not "rising
  fast"). These are the hours where a new word would add something. **Secondary population (A):** every issue time
  with a published reading.

### Inputs (fixed now)

- **The spot gauge's own trend (R3's inputs):** its level index, and its rise over the last 1 h and 3 h, as shares
  of its usual range.
- **Upstream gauges (C1 adds):** for each spot gauge, the nearest upstream gauge on the same river with at least a
  quarter of its catchment (the pairing rule above), and the upstream gauge on another river name with the largest
  catchment (a tributary), where they exist. Each: rise over the last 1, 3 and 6 h as a share of its own EA usual
  range, and its index. Their EA ranges are fetched for this (one stage-scale request each). A missing upstream gauge
  is filled with 0 rise and a flag.
- **Radar rain (C2 adds to C1):** the saved hourly radar, mean of the rain cells that hold the spot gauge and each of
  its upstream gauges within 50 km; sums over the last 3, 6 and 12 h. Only hours ending at or before t − 1 h.
- **No forecast rain** in this test. It would mean Open-Meteo calls, whose daily ledger the live site uses.

### Strict time order

- `issue_rows` in the script is the window builder. A reading at time r counts at issue time t only if r ≤ t − d,
  where d is the gauge's publication delay. **d = 1 h for every gauge** (above the 0.75 h 75th percentile measured).
  Sensitivity: d = 3 h, reported in full. Only the label reads past t. The test file checks this.
- **Readings come from the Hydrology series,** the archived values. They may be corrected after the fact, and the
  real-time feed may have had gaps the archive does not. Inferred: this makes the hindcast optimistic. The
  prospective shadow (below) is the only clean check.
- Radar hours are labelled by their end time. An hour ending at t − 1 h or earlier is used. The radar is out "within
  20 minutes" (`docs/MET-OFFICE-DATA-2026-10.md`; read there, not re-checked here).

### Separation

- **By time:** train on 21 November 2024 (the radar's first full day) to 30 September 2025. Test on 1 October 2025
  to 24 October 2026. Nothing from the test period enters training, fitting or the choice of anything.
- **By catchment:** the spot gauges are grouped into river systems (the network outlet each drains to). The systems
  are split into 5 folds with numpy `default_rng(20261026)`. A test-period prediction for a gauge comes from a model
  trained only on the other folds' gauges, in the training period. Both separations hold at once.

### Models and references

- **Model:** logistic regression on standardised inputs, C = 1, pooled across gauges (as `ecoli.fit`). One for C1,
  one for C2. Not tuned.
- **R1, base rate:** the training share of label 1 by spot gauge and calendar month, in the same population.
- **R2, the site's current words** (population A only): the training share of label 1 given the site's word at t
  ("high", "rising fast", none).
- **R3, persistence:** the same logistic regression on the spot gauge's own trend alone. This is the primary
  reference: an upstream input has to beat what the spot gauge itself already shows.

### Metrics

Brier score, and Brier skill against R3 and R1. AUC. Reliability in ten bins. At a warning line of 0.5: hit rate and
false-alarm ratio. **Lead gained:** for each test onset of the site's own "rising fast" at the spot gauge, the hours
between the onset and the first issue time, within the 6 hours before it, from which C1 stayed at or above 0.5. All
pooled, by river system and by spot gauge.

### Gate (checked before any score)

- at least 25 spot gauges with a pair, and at least 80% of hourly issue times with a label in both periods;
- at least 150 label-1 episodes (runs of consecutive 1s) in population P in the test period, at 15 or more gauges in
  6 or more river systems.

Below the gate, scores are reported as description, and nothing can pass.

### Pass conditions (C1 against R3, population P, 3 h)

All must hold:
1. Brier skill against R3 at least 0.05, with the 95% interval from a river-system cluster bootstrap (2,000
   resamples) above 0.
2. Skill above 0 in at least two thirds of the river systems with 5 or more test episodes.
3. At the 0.5 line, hit rate at least 0.5 and false-alarm ratio at most 0.5.
4. Median lead gained at least 1 h over the site's own word, on the onsets C1 caught.
5. With d = 3 h, skill against R3 still above 0.
6. **Placebo:** each upstream series shifted by a whole number of weeks (1 to 4, random sign) within its gauge, 200
   times, `default_rng(20261026)`. The real Brier gain over R3 is above the 95th percentile of the 200.

C2 is judged against C1 by the same six (horizon 3 h; 6 h reported). The near-miss labels of the 26 October addendum
in `docs/LAKE-ECOLI-LINE-TEST-2026-10.md` apply. B and H are written in the run statement, from predictions alone,
before any outcome is read.

### Expected, stated now

Inferred from the lags: C1 will most likely fail condition 1 or 4 at most gauges, because the spot gauge's own first
hour of rise already carries most of what an upstream gauge one or two hours away knows. If anything passes, it is
most likely C2 (radar), or C1 at the five longer pairs. Overall expectation: C1 does not pass pooled.

### Running

- Fetching: about 2 years of 15-minute readings for the 39 spot gauges with upstream gauges and their chosen upstream
  gauges (up to about 120 series), and up to about 80 stage scales. Under the same caps (300 a run), so two or three
  runs, or the Hydrology batch API the EA recommends for bulk. Estimate: about 13 MB a series for two years
  (6.5 MB a year was measured), about 1.5 GB in all, to scratch. Not in git.
- One run, alone on the machine (the heavy-run lock absent), offline from the cache, after Ethan has read this plan.
  No Open-Meteo request.
- Not before 2 November 2026, so that Ethan has a week to change the plan by a dated amendment. If possible before
  21 November 2026, while the radar's oldest months are still on AWS in case any need fetching again.

### What follows

- **Whatever the result, nothing on the site changes because of this test.** The EA says its APIs "should not be
  relied upon for safety critical applications".
- **C1 or C2 passes:** Ethan decides whether to run a shadow log. It would cost no extra EA requests for levels: the
  build's one latest-readings call already holds every gauge, and builds every 30 minutes would keep a rolling
  series. It would log each spot's chance without showing it, for a window stated in advance (proposed: 1 December
  2026 to 28 February 2027, read on 1 March 2027), scored against the real-time feed as it was published. Only after
  that would wording be proposed. It would describe an observation ("the river upstream rose 0.4 m in the last three
  hours"), not promise a forecast.
- **Neither passes:** the spot gauge's own "rising fast" stays the only word. A plain observation of the upstream
  gauge, with no forecast, is still possible and needs no model. That is a product decision for Ethan.

## Seen before writing the plan

- The coverage, delay and lag figures above, from the 26 October run.
- The two EA reference pages; `src/dipcast/ingest/flows.py`; `docs/GLOFAS-CHECK-2026-11.md`;
  `docs/RADAR-RAIN-CHECK-2026-10.md`; `docs/MET-OFFICE-DATA-2026-10.md`; `docs/LAKE-ECOLI-LINE-TEST-2026-10.md`.
- The list of saved radar months (file names only; no radar value was read).
- No label rate, no model fit and no score of any kind.
