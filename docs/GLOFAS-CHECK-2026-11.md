# GloFAS flow against the EA gauges (review task D5)

Research only. Nothing here changes the site or the model. Task D5 of `docs/REVIEW-2026-10-16.md`,
data source item 4 there (Open-Meteo Flood API, GloFAS v4, 5 km).

**Verdict.** GloFAS is good enough to take to the two model tests at the end, and not good enough
to use as a flow in cubic metres a second. By the rule stated before the data was fetched it
tracks the gauges: all four conditions pass at 42 river spots. The pass is narrow. A series with
no events at all (GloFAS smoothed over 31 days) would pass two of the four conditions, and the one
condition that tests events passed by 0.005. Any use needs three things: never the nearest GloFAS
cell (at 20 of 42 spots it is off the river), GloFAS relative to its own typical flow (it reads
about a third low), and GloFAS moved one day earlier (it matches best a day late at 37 of 42).

## Question

The spill model sees rain, season and three fixed site figures, and nothing about how wet the
catchment is. The transport step holds today's river state flat over the five forecast days (the
reach speed comes from today's EA level index, `transport.river_velocity`). A forecast river flow
could feed both a dilution that changes day by day and a catchment-wetness input. (Corrected after
the run: the level index sets reach speed only in the API, which is not deployed. The site calls
`forecast_point(..., gauge=False)` (`scripts/build_site.py`), so its reach speed is a fixed
0.2 m/s and its dilution a fixed length ratio: nothing in its transport step follows the flow,
today or ahead. The method is unchanged by this.) That is only
worth testing if the flow tracks real gauges. Does GloFAS daily discharge, as the Open-Meteo Flood
API serves it, track the EA's measured daily mean flow at the listed river spots?

## Pre-stated part (written and committed before any flow was fetched)

### What was seen before writing this

- One Flood API probe at one spot (Wharfe at Cromwheel, Ilkley; 1 Oct 2025 to 15 Nov 2026,
  models `seamless_v4`, `forecast_v4`, `consolidated_v4`). It showed which models carry data:
  `consolidated_v4` was empty for every day, and `seamless_v4` equalled `forecast_v4` on all 411
  days. No gauge flow was fetched, so nothing was compared.
- The EA Hydrology station list, and the spot-to-station matching below. No readings.

### Spots and gauges (fixed here)

`scripts/glofas_check.py --step match`, run 18 Oct 2026 on the network in the main checkout's
`data/processed/river_network.pkl`.

- **Spots:** the 72 river spots in `spots.csv` and `spots-osm.csv`, placed with `locate_pin` and
  the build's hints (`transport.spot_hints`). The 33 lake spots are left out: GloFAS's 5 km
  network routes lakes coarsely, and the site's lake path uses residence time, not river flow.
- **Gauges:** the 1,102 EA Hydrology flow stations with a daily mean flow measure
  (`-flow-m-86400-m3s-qualified`, OGL v3.0); 1,079 snap within 250 m of a river link.
- **Rule:** a station counts for a spot if it is on the spot's river path (upstream or downstream
  along the network) within 25 km, and its catchment is within a factor of 2 of the spot's. Both
  catchments come from the network's upstream length (`transport.catchment_km2`), so the ratio is
  like for like. A station that gauges one channel of several is skipped, by words in its EA label
  (side, main, flume, fishladder, bypass, intake) or river name (relief, navigation, carrier,
  leat); where a "Total" or "Combined" station sits within 0.5 km it goes first. The words were
  read off the stations near the spots, before any flow was fetched. Of what is left, the nearest
  along the network is used.
- **Result:** 48 of the 72 river spots qualify, on 37 distinct stations. 21 have gauges on the
  path but with a catchment more than twice or under half the spot's (mostly headwater spots:
  Dart, Teign, Plym, Peak District brooks, the upper Wharfe and Ribble). 2 have no gauge on the
  path within 25 km (Falcon Meadow on the Waveney, Drogo Weir on the Teign). 1 has only a
  part-channel gauge on the path (Chilbolton Cow Common on the Test). The per-spot table, with
  distances, is in the results.

### Data (fixed here)

- **Days:** 1 Oct 2025 to 30 Sep 2026 (365 days). A pair needs at least 300 days with both values.
- **GloFAS:** Flood API `daily=river_discharge`, `models=seamless_v4`, `cell_selection=nearest`.
  Per spot, the 3 x 3 block of GloFAS cells (0.05 degrees) centred on the spot's own cell; per
  station, the station's own cell. Requests batch up to 100 locations; every response is cached.
- **EA:** each station's daily mean flow for the same days, one request per station, 2 s apart.
- **Scaling:** at a spot, the gauge's flow is scaled by the catchment ratio (spot over gauge),
  the usual drainage-area transfer. At the station's own cell, it is not scaled.

### Cells compared (fixed here)

- **(a) Nearest:** the GloFAS cell nearest the spot. What a plain Flood API call returns.
- **(b) Area rule (primary):** of the 9 cells around the spot, the one whose mean discharge over
  the 365 days is nearest, in log terms, to the network's estimate of the spot's mean flow
  (`transport.QMEAN_PER_KM2` x the spot's catchment). It uses no gauge data, so production could
  use it. It is primary because the Flood API itself warns that the nearest cell may be the wrong
  river.
- **(c) Gauge cell:** GloFAS at the station's own coordinates against the station, unscaled.
  This separates GloFAS's own error from the error of moving to the spot.

### Measures (per pair, over shared days)

1. **Bias factor:** GloFAS mean over gauge mean (scaled at a spot).
2. **Rank correlation:** Spearman's rho of the daily values.
3. **Event rank correlation:** Spearman's rho of log flow minus its centred 31-day rolling mean
   (at least 15 days). This takes out the seasonal cycle, which alone gives a high rho to any
   series that is wet in winter and dry in summer.
4. **High-flow hit rate:** of the gauge's days at or above its own 90th percentile, the share on
   which GloFAS is at or above its own 90th percentile on the same day or one day either side.
5. **Timing:** the lag from -3 to +3 days that maximises measure 3 (positive: GloFAS late).
6. **KGE** (Kling-Gupta efficiency, 2009 form) of the scaled series, for comparison with
   published GloFAS skill.
7. **Wrong river:** bias factor outside [1/3, 3], or rho under 0.5.

### Verdict rule (fixed here)

GloFAS "tracks the gauges well enough to take to the two model tests" only if all four hold for
cell rule (b) over the 48 spots:

1. Median rank correlation at least 0.80.
2. Median event rank correlation at least 0.50.
3. Median high-flow hit rate at least 0.50.
4. Wrong river at no more than 4 of the 48 spots (under 10%).

The bias factor is reported but is not a condition: both later tests can use GloFAS relative to its
own climatology (a percentile or a ratio to its own median), which removes a constant bias. If the
median bias factor is within [2/3, 1.5], absolute flows could be used as well.

### What this cannot show (stated before)

- **Forecast lead.** The probe shows `seamless_v4` serves `forecast_v4` for past days. That is
  inferred to be each day's shortest-lead GloFAS value; the Flood API page does not say. Skill at
  leads 2 to 5, which the dilution test needs, is not measured here.
- **Calibration stations.** GloFAS v4 was calibrated on river gauges, which may include some of
  these EA stations. At those, the check is optimistic (inferred; not checked against the
  GloFAS station list).
- **Independence.** Several spots share a station (five Wharfe spots use Addingham), so the 48 are
  not 48 independent checks. Measure (c) is reported per station as well.
- **One year.** Oct 2025 to Sep 2026 is one hydrological year.

## Terms (read 18 Oct 2026)

The review had not fetched these. All quotes below were read on the pages themselves on 18 Oct 2026.

### GloFAS (Copernicus Emergency Management Service)

Source: global-flood.emergency.copernicus.eu/terms-of-service/, "Terms and Conditions", "Last
updated: 29 Jul 2026", linked from the GloFAS home page as "Terms and Conditions of Access".

- Use: users "are granted free access to the data of the CEMS early warning and monitoring
  systems for the following purposes": "(a) reproduction; (b) distribution; (c) communication to
  the public; (d) adaptation, modification and combination with other data and information;
  (e) any combination of points (a) to (d)."
- Attribution when publishing: "'Generated using Copernicus Emergency Management Service
  information [Year]'", and where the data "has been adapted or modified": "'Contains modified
  Copernicus Emergency Management Service information [Year]'".
- Not a warning: the data "does not constitute in any way an early warning for which only
  national/regional institutions are authorized within their region of responsibility."
- No warranty: provided "as is" without warranty "including ... fitness for a particular
  purpose"; "changes to the data might occur frequently and without prior notice."
- Restricted data: "Some data as produced by the CEMS early warning and monitoring systems are
  restricted ... Access to this restricted data will be granted only to specific users and upon
  registration."

The dataset Open-Meteo draws on, "River discharge and related forecasted data by the Global Flood
Awareness System" on the CEMS Early Warning Data Store (ewds.climate.copernicus.eu,
`cems-glofas-forecast`), states "Licence: CEMS-FLOODS datasets licence", "Horizontal resolution
0.05° x 0.05° for version 4.0", "Updated daily". That licence (PDF, SHA-256 `428a6e1019ec50b3dad9c37a90d630fab139059933a939dd5df620bfcb420cc3`, the
older wording citing Regulation (EU) No 377/2014) grants the same five uses and the same two
notices. Open-Meteo's licence page links it at a `/licenses/` path that answered `NoSuchKey`; the
same file is at the `/licences/` path.

What this means (inferred): showing a forecast flow, or a dilution or wetness figure built from it,
is allowed, with "Contains modified Copernicus Emergency Management Service information 2026" next
to it. The site must not word it as a flood warning. Whether the forecast Open-Meteo serves counts
as "restricted" was not settled: the open EWDS dataset carries the forecast, so it is inferred not to.

### Open-Meteo

Flood API page (open-meteo.com/en/docs/flood-api):

- "This API uses reanalysis and forecast data from the Global Flood Awareness System (GloFAS)."
- "Please note: Due to the 5 km resolution the closest river might not be selected correctly.
  Varying coordiantes by 0.1° can help to get a more representable discharge rate." (sic)
- "Note: Seamless combines forecast and consolidated historical data." Its data-source table gives
  "GloFAS v4 Reanalysis ... 1984 - July 2022" and "GloFAS v4 Forecast ... 30 days forecast".
  The table is out of date: a later probe at one cell found `consolidated_v4` values to 31 May
  2025 (see "What is measured"). Both probes agree that 2025-26 comes from `forecast_v4`.

Terms (open-meteo.com/en/terms):

- "Less than 10'000 API calls per day, 5'000 per hour and 600 per minute. You may only use the free
  API services for non-commercial purposes. You accept to the CC-BY 4.0 licence".
- Non-commercial includes "Private or non-profit websites or apps that do not have subscriptions or
  advertising" and "Voluntary donations, including contributions through a tip jar, are permitted."
  Commercial includes "Websites or apps that have subscriptions or display advertisements."

Licence (open-meteo.com/en/licence): "API data are offered under Attribution 4.0 International
(CC BY 4.0)"; "You must include a link next to any location Open-Meteo data are displayed"; GloFAS
is listed as "Flood forecasts from Global Flood Awareness System GloFAS" with the CEMS-FLOODS PDF.

What this means (inferred): the Flood API sits under the same Open-Meteo terms as the rain the
site already uses, so the Ko-fi tips stay within them and a paid pilot would not. Each location over
365 days weighs about 2.6 calls by Open-Meteo's own weighting (see PR #243); a build
asking each of the 72 river spots for 14 days would weigh 72 calls.

## Results (18 Oct 2026)

### The run

`scripts/glofas_check.py --step compare --fetch`, after the statement commit 4c1d801. Four Flood
API requests for 386 distinct cells, 40 s apart, about 1,006 calls by Open-Meteo's weighting; 37
EA requests, 2 s apart. Two one-location probes besides (about 3 and 40 calls). No Open-Meteo
ledger had been written locally that day; whether other sessions called Open-Meteo then is not
known. The responses are cached in the session's scratch folder, not committed. The tables below
are in
`docs/GLOFAS-CHECK-2026-11-spots.csv` (spots, cells a and b), `-gauges.csv` (cell c) and
`-cells.csv` (all nine cells per spot).

**Days.** 42 of the 48 spots have at least 300 days. Six do not, because their station published
too little for the year: Offord Ultrasonic (two Great Ouse spots) and Easton returned no daily
means, Barcombe 3 (354 marked Missing), Hunsingore 18, Maidenhead 186 (179 more marked Suspect,
dropped as stated). So 32 of the 37 stations count.

### Overall (medians; measured)

| Cells | Pairs | Bias | Rank r | Event r | High-flow hit | KGE | Wrong river |
|---|---|---|---|---|---|---|---|
| (a) nearest | 42 | 0.47 | 0.85 | 0.50 | 0.79 | 0.01 | 20 |
| (b) area rule | 42 | 0.66 | 0.88 | 0.51 | 0.78 | 0.37 | 2 |
| (c) gauge's own cell | 32 | 0.62 | 0.86 | 0.51 | 0.75 | 0.30 | 9 |

**Pre-stated verdict, rule (b): tracks.** Condition 1, rank r 0.88 (at least 0.80): pass.
Condition 2, event r 0.505 (at least 0.50): pass. Condition 3, hit rate 0.78 (at least 0.50):
pass. Condition 4, wrong river at 2 spots (at most 4): pass.

### What the rule missed (added after the results; not part of the verdict)

These measures were added after the first results were seen. They change the reading of the
verdict, not the verdict.

| Cells | Rank r | Event r, GloFAS 1 day earlier | Same-day hit | Same-day hit, 1 day earlier | Best lag +1 day |
|---|---|---|---|---|---|
| (a) nearest | 0.85 | 0.62 | 0.57 | 0.70 | 30 of 42 |
| (b) area rule | 0.88 | 0.66 | 0.56 | 0.70 | 37 of 42 |
| (c) gauge's own cell | 0.86 | 0.65 | 0.56 | 0.66 | 25 of 32 |
| Seasonal only: (b) smoothed, centred 31-day mean | 0.87 | — | — | — | — |

- **Conditions 1 and 3 do not test events.** The seasonal-only series has no events and still
  scores rank r 0.87 and a high-flow hit rate of 0.53 (one day either side). It would pass both.
  GloFAS's hit rate of 0.78 is 0.25 above it, so GloFAS does carry events, but the conditions as
  written did not show that.
- **Condition 4 is partly built in for rule (b).** Rule (b) picks the cell whose mean is nearest
  the network's estimate, and the bias half of the flag compares means with the gauge. A cell on
  a neighbouring river of similar size, in the same weather, would pass both halves.
- **The one event test passed by 0.005.** The event rank correlation is 0.505 against 0.50.
- **GloFAS matches best one day late.** The lag that maximises the event correlation is +1 day at
  37 of 42 spots under rule (b), and at 25 of 32 stations' own cells. Moved one day earlier, the
  median event correlation is 0.66 and the same-day high-flow hit rate 0.70, against 0.51 and 0.56.
  The cause is not settled. Open-Meteo stamps each value with the GRIB message's time for "river
  discharge in the last 24 hours" (`GloFasDownloader.swift`); the code does not say whether that is
  the start or the end of the 24 hours. The EA's daily means carry 09:00 times. If the day is a
  label convention, the GloFAS forecast is a day shorter than it looks; if it is GloFAS's routing,
  GloFAS rises late. Either way a later test should move GloFAS one day earlier, stated first. At
  one cell (Ilkley), GloFAS's forecast and consolidated series over their 730 shared days also
  match best one day apart (rank r 0.959 against 0.954 unshifted), a hint only.
- **The weakest event tracking** under rule (b) is on the Suffolk Stour (Friars Meadow 0.09,
  Dedham 0.27) and the Tees at Low Force (0.31, best lag 2 days) and Coquet (0.35, best lag 2).

### Snapping at 5 km (measured, except where marked)

- **The nearest cell is often off the river.** It is within 3.0 km of every spot. At 20 of 42
  spots it carries under a third of the river's flow, and at 13 under a tenth. None carries too
  much. Examples (cell mean against the gauge's scaled mean, m³/s): Thames at Wallingford 0.08
  against 45.2, Thames at Long Bridges, Oxford 0.13 against 36.6, Avon at Fordingbridge 0.14
  against 19.0, Eden at Armathwaite 0.30 against 37.9, Thames at Kingston 0.76 against 64.3.
- **The gauges' own cells** are off the river at 9 of 32 stations (Amesbury 0.04, Bathford 0.03).
- **Rule (b) moved off the nearest cell at all 48 spots**, a median 4.5 km and at most 8.8 km
  from the spot. With it, 2 of 42 spots are flagged. Judged against the gauge (which production
  cannot do), rule (b) picked the block's best cell by KGE at 20 of 42 spots.
- **Why it always moves.** Measured: at 24 of the 48 spots, rule (b)'s cell carries within 25% of
  the nearest cell's flow, and the nearest cell was second or third closest to the network's
  estimate, by a small margin. At 20 the rule's cell carries over three times the nearest's (the
  nearest was off the river), and at 4 the ratio is outside both bands. Inferred: in the first
  group the rule stepped one cell up or down the same river. Adjacent cells on one river differ by
  a few per cent, while the estimate differs from GloFAS by more, so the rule always steps toward
  the estimate. The direction fits: at Ilkley the estimate (7.3 m³/s) is below the nearest cell
  (10.1) and the rule took a smaller cell (9.9); at Ironbridge it is above (56.4 against 42.2) and
  the rule took a larger one (43.6). A rule that kept the nearest cell when it is within a factor of
  2 of the estimate would avoid the step (not tested). That the moved cells are on the same river
  is not proven: see condition 4 above. GloFAS's upstream-area map (`glofas_upArea.nc`, on the
  EWDS behind a free account) would show which river each cell is on. It was not fetched.
- **Chee Dale, Derbyshire Wye (flagged).** The network's estimate (0.6 m³/s) is a quarter of the
  Ashford gauge's 2.5. Rule (b) matched it and took a 0.6 m³/s cell; a 2.8 m³/s cell in the same
  block fits the gauge (bias 0.91, KGE 0.70). Inferred cause: the estimate has no geology term,
  and the Wye there is a limestone river.
- **Dartington, Dart (flagged).** No cell in the block comes near the gauge (largest 5.7 m³/s
  against 17.2 at Austins Bridge). Either GloFAS under-simulates the Dart or its Dart cell lies
  outside the block (inferred; not checked). The network's estimate is low there too (4.7), the
  wet-upland case `transport.py` names.

### Per spot

Rule (b) unless marked. "Event r (+1 day)" is the event correlation, then the same with GloFAS one
day earlier. "Along / straight km" is spot to gauge, along the network and in a straight line;
"Gauge/spot area" is the catchment ratio used to scale the gauge.

| Spot | Gauge (EA river) | Gauge is | Along / straight km | Gauge/spot area | Nearest cell: km, bias | Rule (b) cell: km | Bias | Rank r | Event r (+1 day) | Hit | KGE | Flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Wharfe at Cromwheel, Ilkley | Addingham (River Wharfe) | upstream | 4.4 / 3.1 | 0.94 | 1.0, 0.68 | 3.9 | 0.66 | 0.81 | 0.49 (0.72) | 0.73 | 0.27 |  |
| Nidd at the Lido, Knaresborough | Hunsingore (River Nidd) | downstream | 14.9 / 7.3 | 1.37 | 3.0, — | 3.1 | — | — | — | — | — | 18 days |
| Wharfe at Wilderness Carpark | Tadcaster (River Wharfe) | downstream | 13.1 / 8.2 | 1.06 | 0.7, 0.81 | 2.6 | 0.80 | 0.87 | 0.59 (0.71) | 0.81 | 0.53 |  |
| Swale above Richmond Falls | Catterick Bridge (River Swale) | downstream | 8.5 / 5.4 | 1.30 | 2.8, 0.06 (wrong) | 3.9 | 0.73 | 0.88 | 0.43 (0.68) | 0.65 | 0.34 |  |
| Friars Meadow, River Stour | Lamarsh (River Stour) | downstream | 7.2 / 5.4 | 1.07 | 1.2, 0.03 (wrong) | 7.1 | 0.63 | 0.60 | 0.09 (0.08) | 0.53 | 0.37 |  |
| Pangbourne Meadow, River Thames | Reading (River Thames) | downstream | 10.4 / 8.5 | 1.01 | 1.4, 0.61 | 4.3 | 0.61 | 0.91 | 0.61 (0.63) | 0.89 | 0.51 |  |
| Ham and Kingston, River Thames | Kingston (River Thames) | upstream | 1.4 / 1.3 | 1.00 | 1.0, 0.01 (wrong) | 5.9 | 0.94 | 0.79 | 0.49 (0.58) | 0.97 | 0.89 |  |
| Wolvercote Mill Stream | Farmoor (River Thames) | upstream | 9.0 / 5.5 | 0.75 | 1.6, 0.16 (wrong) | 6.4 | 0.71 | 0.88 | 0.49 (0.51) | 0.92 | 0.65 |  |
| Wallingford Beach, River Thames | Sutton Courtenay (River Thames) | upstream | 17.9 / 10.7 | 0.81 | 2.8, 0.00 (wrong) | 4.7 | 0.51 | 0.92 | 0.63 (0.66) | 0.92 | 0.36 |  |
| River Avon at Fordingbridge | East Mills Combined (River Avon) | upstream | 1.6 / 0.9 | 0.99 | 1.0, 0.01 (wrong) | 2.6 | 0.61 | 0.91 | 0.51 (0.59) | 0.81 | 0.57 |  |
| River Avon at Queen Elizabeth Gardens | Amesbury (Hampshire Avon / River Avon) | upstream | 18.2 / 11.6 | 0.73 | 1.8, 1.87 | 8.2 | 0.53 | 0.90 | 0.55 (0.61) | 0.84 | 0.48 |  |
| River Tone at French Weir Park | Taunton Market (River Tone) | downstream | 1.3 / 0.9 | 1.09 | 1.1, 0.67 | 2.8 | 0.74 | 0.94 | 0.49 (0.68) | 0.77 | 0.55 |  |
| River Frome at Farleigh Hungerford | Tellisford (Somerset Frome) | upstream | 2.7 / 1.3 | 0.97 | 0.9, 1.58 | 7.4 | 1.36 | 0.93 | 0.42 (0.63) | 0.78 | 0.42 |  |
| River Teme in Ludlow | Tenbury (River Teme) | downstream | 17.9 / 10.8 | 1.20 | 0.9, 0.04 (wrong) | 5.7 | 0.73 | 0.94 | 0.59 (0.68) | 0.51 | 0.59 |  |
| River Severn at Ironbridge | Buildwas (River Severn) | upstream | 2.6 / 2.4 | 0.99 | 1.2, 0.58 | 6.2 | 0.60 | 0.91 | 0.68 (0.63) | 0.70 | 0.46 |  |
| River Severn in Shrewsbury | Montford (River Severn) | upstream | 22.4 / 7.9 | 0.92 | 2.0, 0.62 | 4.5 | 0.75 | 0.89 | 0.64 (0.61) | 0.62 | 0.64 |  |
| River Ribble at Edisford Bridge | Henthorn (River Ribble) | downstream | 3.1 / 2.3 | 1.07 | 0.9, 0.82 | 4.9 | 0.62 | 0.83 | 0.58 (0.74) | 0.68 | 0.14 |  |
| River Lune, Devil's Bridge, Kirkby Lonsdale | Caton (River Lune) | downstream | 20.6 / 15.6 | 1.78 | 2.8, 0.06 (wrong) | 8.5 | 0.42 | 0.83 | 0.55 (0.77) | 0.84 | -0.05 |  |
| River Lune, Crook o' Lune, Caton | Caton (River Lune) | upstream | 1.1 / 1.0 | 0.99 | 0.4, 0.82 | 6.7 | 0.75 | 0.82 | 0.56 (0.79) | 0.86 | 0.26 |  |
| River Wharfe, Bolton Abbey (Cavendish Pavilion) | Addingham (River Wharfe) | downstream | 6.6 / 5.5 | 1.16 | 1.6, 0.02 (wrong) | 2.7 | 0.77 | 0.81 | 0.49 (0.72) | 0.76 | 0.37 |  |
| River Wharfe, Burnsall | Addingham (River Wharfe) | downstream | 17.5 / 13.3 | 1.78 | 2.8, 1.09 | 5.6 | 0.87 | 0.82 | 0.50 (0.73) | 0.81 | 0.46 |  |
| River Wharfe, Appletreewick | Addingham (River Wharfe) | downstream | 14.3 / 11.1 | 1.49 | 0.9, 0.03 (wrong) | 3.7 | 0.91 | 0.81 | 0.50 (0.73) | 0.73 | 0.49 |  |
| River Ure, Aysgarth Falls | Kilgram Bridge (River Ure) | downstream | 25.0 / 18.1 | 1.91 | 2.1, 0.03 (wrong) | 3.2 | 0.77 | 0.84 | 0.50 (0.73) | 0.81 | 0.37 |  |
| River Eden, Armathwaite | Great Corby (River Eden) | downstream | 13.5 / 10.1 | 1.02 | 2.1, 0.01 (wrong) | 4.5 | 0.80 | 0.91 | 0.68 (0.83) | 0.81 | 0.46 |  |
| River Eden, Lazonby | Temple Sowerby (River Eden) | upstream | 18.1 / 13.1 | 0.52 | 2.7, 0.92 | 3.6 | 0.89 | 0.87 | 0.57 (0.79) | 0.71 | 0.30 |  |
| River Tees, Low Force | Middleton (River Tees) | downstream | 6.5 / 5.4 | 1.33 | 2.8, 0.67 | 5.7 | 0.59 | 0.68 | 0.31 (0.60) | 0.78 | 0.14 |  |
| River Coquet, Rothbury | Rothbury (River Coquet) | downstream | 1.1 / 1.0 | 1.00 | 2.0, 0.45 | 4.4 | 0.50 | 0.81 | 0.35 (0.59) | 0.70 | 0.08 |  |
| River Dove, Dovedale stepping stones | Izaak Walton (River Dove) | upstream | 0.5 / 0.4 | 0.99 | 2.5, 0.14 (wrong) | 3.3 | 0.35 | 0.91 | 0.53 (0.62) | 0.78 | 0.17 |  |
| River Wye, Bishop's Meadow, Hereford | Belmont (River Wye) | upstream | 2.5 / 2.5 | 0.98 | 2.7, 0.15 (wrong) | 4.9 | 0.69 | 0.94 | 0.71 (0.78) | 0.62 | 0.50 |  |
| River Avon, Warleigh Weir, Bath | Bathford (River Avon) | downstream | 3.4 / 2.9 | 1.08 | 1.7, 0.01 (wrong) | 7.5 | 0.57 | 0.93 | 0.53 (0.69) | 0.73 | 0.39 |  |
| River Frome, Tellisford Weir | Tellisford (Somerset Frome) | downstream | 1.2 / 1.0 | 1.01 | 2.6, 0.13 (wrong) | 3.0 | 1.64 | 0.93 | 0.45 (0.65) | 0.84 | 0.05 |  |
| River Barle, Tarr Steps | Brushford (River Barle) | downstream | 13.0 / 8.6 | 1.54 | 0.5, 0.70 | 3.0 | 0.41 | 0.88 | 0.50 (0.63) | 0.84 | 0.16 |  |
| River Great Ouse, Houghton Mill | Offord Ultrasonic (River Great Ouse) | upstream | 13.8 / 9.4 | 0.88 | 0.8, — | 2.7 | — | — | — | — | — | 0 days |
| River Waveney, Outney Common, Bungay | Needham Weir Total (River Waveney) | upstream | 19.8 / 13.7 | 0.61 | 1.8, 0.64 | 3.5 | 0.65 | 0.72 | 0.47 (0.59) | 0.73 | 0.32 |  |
| River Stour, Dedham | Langham (River Stour) | upstream | 6.2 / 4.0 | 0.69 | 2.2, 0.57 | 4.4 | 0.61 | 0.80 | 0.27 (0.32) | 0.78 | 0.37 |  |
| River Thames, Clifton Hampden | Sutton Courtenay (River Thames) | upstream | 5.2 / 3.1 | 0.99 | 2.5, 0.53 | 4.0 | 0.61 | 0.92 | 0.63 (0.66) | 0.92 | 0.51 |  |
| River Thames, Henley-on-Thames | Reading (River Thames) | upstream | 15.1 / 9.8 | 0.75 | 2.2, 0.67 | 4.4 | 0.67 | 0.89 | 0.62 (0.62) | 0.89 | 0.60 |  |
| River Thames, Hurley | Maidenhead (River Thames) | downstream | 15.3 / 8.1 | 1.01 | 2.8, — | 3.9 | — | — | — | — | — | 186 days |
| River Thames, Port Meadow, Oxford | Farmoor (River Thames) | upstream | 10.2 / 5.4 | 0.75 | 1.1, 0.16 (wrong) | 5.3 | 0.71 | 0.88 | 0.49 (0.51) | 0.92 | 0.64 |  |
| River Ouse (Sussex), Barcombe Mills | Barcombe (River Ouse) | upstream | 1.6 / 1.2 | 0.99 | 1.9, — | 5.4 | — | — | — | — | — | 3 days |
| River Medway, Tonbridge | Lucifer Bridge (River Medway) | upstream | 1.9 / 1.5 | 0.91 | 2.3, 0.48 | 4.8 | 0.55 | 0.79 | 0.52 (0.67) | 0.74 | 0.33 |  |
| River Wharfe, Greenholme, Burley-in-Wharfedale | Addingham (River Wharfe) | upstream | 10.0 / 7.7 | 0.84 | 1.6, 0.69 | 1.7 | 0.62 | 0.80 | 0.49 (0.72) | 0.76 | 0.22 |  |
| River Wye, Chee Dale, Derbyshire | Ashford (River Wye) | downstream | 12.6 / 6.7 | 1.49 | 2.4, 0.91 | 8.8 | 0.22 | 0.94 | 0.58 (0.67) | 0.92 | -0.04 | wrong river |
| River Great Ouse, Overcote | Offord Ultrasonic (River Great Ouse) | upstream | 25.0 / 15.8 | 0.82 | 1.4, — | 6.0 | — | — | — | — | — | 0 days |
| River Thames, Long Bridges, Oxford | Farmoor (River Thames) | upstream | 15.8 / 8.6 | 0.51 | 2.0, 0.00 (wrong) | 7.1 | 0.53 | 0.88 | 0.47 (0.53) | 0.92 | 0.39 |  |
| River Wey, Waverley, near Farnham | Farnham (River Wey) | upstream | 4.3 / 2.8 | 0.73 | 2.1, 0.11 (wrong) | 4.7 | 1.14 | 0.67 | 0.48 (0.61) | 0.95 | 0.21 |  |
| River Itchen, Compton Lock | Easton (River Itchen) | upstream | 9.6 / 7.8 | 0.55 | 0.3, — | 5.3 | — | — | — | — | — | 0 days |
| River Dart, Dartington Pontoon | Austins Bridge (River Dart) | upstream | 10.2 / 6.6 | 0.88 | 2.0, 0.29 (wrong) | 2.9 | 0.28 | 0.90 | 0.55 (0.77) | 0.73 | -0.02 | wrong river |

### Per station, GloFAS at the station's own cell (c), unscaled

| Station | River | Spots | Cell km | Days | Bias | Rank r | Event r (+1 day) | Hit | KGE | Flag |
|---|---|---|---|---|---|---|---|---|---|---|
| Addingham | River Wharfe | 5 | 1.8 | 365 | 0.71 | 0.81 | 0.49 (0.72) | 0.73 | 0.31 |  |
| Amesbury | Hampshire Avon / River Avon | 1 | 0.8 | 365 | 0.04 | 0.83 | 0.51 (0.52) | 0.84 | -0.35 | wrong river |
| Ashford | River Wye | 1 | 0.2 | 365 | 0.81 | 0.95 | 0.59 (0.68) | 0.95 | 0.74 |  |
| Austins Bridge | River Dart | 1 | 1.1 | 365 | 0.27 | 0.90 | 0.53 (0.76) | 0.81 | -0.03 | wrong river |
| Barcombe | River Ouse | 1 | 1.7 | 3 | — | — | — | — | — | quality: {Missing: 354, Unchecked: 3} |
| Bathford | River Avon | 1 | 2.8 | 365 | 0.03 | 0.94 | 0.49 (0.64) | 0.78 | -0.38 | wrong river |
| Belmont | River Wye | 1 | 2.7 | 335 | 0.70 | 0.94 | 0.71 (0.78) | 0.62 | 0.52 |  |
| Brushford | River Barle | 1 | 0.6 | 365 | 0.10 | 0.77 | 0.39 (0.50) | 0.54 | -0.30 | wrong river |
| Buildwas | River Severn | 1 | 1.2 | 365 | 0.58 | 0.91 | 0.68 (0.63) | 0.70 | 0.43 |  |
| Caton | River Lune | 2 | 0.7 | 365 | 0.82 | 0.82 | 0.55 (0.79) | 0.84 | 0.31 |  |
| Catterick Bridge | River Swale | 1 | 2.1 | 365 | 0.63 | 0.88 | 0.45 (0.69) | 0.70 | 0.24 |  |
| East Mills Combined | River Avon | 1 | 0.3 | 365 | 0.01 | 0.92 | 0.36 (0.45) | 0.84 | -0.40 | wrong river |
| Easton | River Itchen | 1 | 1.6 | 0 | — | — | — | — | — | no readings |
| Farmoor | River Thames | 3 | 2.0 | 365 | 0.69 | 0.90 | 0.48 (0.51) | 0.92 | 0.64 |  |
| Farnham | River Wey | 1 | 2.3 | 365 | 1.56 | 0.67 | 0.48 (0.61) | 0.95 | -0.52 |  |
| Great Corby | River Eden | 1 | 1.7 | 362 | 0.01 | 0.81 | 0.53 (0.71) | 0.65 | -0.48 | wrong river |
| Henthorn | River Ribble | 1 | 2.6 | 365 | 0.57 | 0.83 | 0.58 (0.74) | 0.68 | 0.10 |  |
| Hunsingore | River Nidd | 1 | 1.6 | 18 | — | — | — | — | — | quality: {Unchecked: 18} |
| Izaak Walton | River Dove | 1 | 2.1 | 365 | 0.14 | 0.90 | 0.36 (0.50) | 0.81 | -0.17 | wrong river |
| Kilgram Bridge | River Ure | 1 | 1.2 | 365 | 0.62 | 0.82 | 0.48 (0.71) | 0.70 | 0.22 |  |
| Kingston | River Thames | 1 | 1.6 | 365 | 0.01 | 0.43 | 0.51 (0.41) | 0.76 | -0.48 | wrong river |
| Lamarsh | River Stour | 1 | 1.7 | 314 | 0.59 | 0.60 | 0.09 (0.08) | 0.53 | 0.36 |  |
| Langham | River Stour | 1 | 1.1 | 365 | 0.81 | 0.79 | 0.28 (0.31) | 0.81 | 0.64 |  |
| Lucifer Bridge | River Medway | 1 | 2.7 | 336 | 0.53 | 0.79 | 0.53 (0.68) | 0.74 | 0.30 |  |
| Maidenhead | River Thames | 1 | 1.6 | 186 | — | — | — | — | — | quality: {Unchecked: 186, Suspect: 179} |
| Middleton | River Tees | 1 | 0.6 | 365 | 0.91 | 0.67 | 0.28 (0.57) | 0.73 | 0.39 |  |
| Montford | River Severn | 1 | 0.2 | 365 | 0.63 | 0.91 | 0.68 (0.65) | 0.73 | 0.49 |  |
| Needham Weir Total | River Waveney | 1 | 0.8 | 365 | 0.65 | 0.72 | 0.47 (0.59) | 0.73 | 0.33 |  |
| Offord Ultrasonic | River Great Ouse | 2 | 0.2 | 0 | — | — | — | — | — | no readings |
| Reading | River Thames | 2 | 1.6 | 363 | 0.76 | 0.91 | 0.61 (0.62) | 0.89 | 0.74 |  |
| Rothbury | River Coquet | 1 | 2.3 | 365 | 0.03 | 0.61 | 0.31 (0.50) | 0.54 | -0.46 | wrong river |
| Sutton Courtenay | River Thames | 2 | 2.9 | 365 | 0.53 | 0.93 | 0.64 (0.66) | 0.92 | 0.38 |  |
| Tadcaster | River Wharfe | 1 | 1.8 | 365 | 0.81 | 0.86 | 0.58 (0.71) | 0.78 | 0.53 |  |
| Taunton Market | River Tone | 1 | 1.8 | 349 | 0.62 | 0.94 | 0.51 (0.69) | 0.77 | 0.39 |  |
| Tellisford | Somerset Frome | 2 | 2.1 | 365 | 1.62 | 0.93 | 0.45 (0.65) | 0.84 | 0.07 |  |
| Temple Sowerby | River Eden | 1 | 2.7 | 336 | 0.67 | 0.86 | 0.53 (0.78) | 0.71 | 0.14 |  |
| Tenbury | River Teme | 1 | 1.7 | 365 | 0.70 | 0.93 | 0.59 (0.68) | 0.54 | 0.55 |  |

### River spots with no qualifying gauge

| Spot | River | Why left out |
|---|---|---|
| Sheep's Green, River Cam | River Cam | gauges on the path, catchment too different |
| Falcon Meadow, River Waveney | River Waveney | no gauge on the river path |
| Sandy Lane, Chester | River Dee | gauges on the path, catchment too different |
| River Wharfe, Linton Falls, Grassington | River Wharfe | gauges on the path, catchment too different |
| River Ribble, Stainforth Force | River Ribble | gauges on the path, catchment too different |
| Janet's Foss, Gordale Beck, Malham | Gordale Beck | gauges on the path, catchment too different |
| River Duddon, Birks Bridge | River Duddon | gauges on the path, catchment too different |
| River Allen, Plankey Mill | River Allen | gauges on the path, catchment too different |
| River Derwent, Slippery Stones (Howden) | River Derwent | gauges on the path, catchment too different |
| River Wye, Symonds Yat | River Wye | gauges on the path, catchment too different |
| River Dart, Spitchwick (Deeper Marsh) | River Dart | gauges on the path, catchment too different |
| River Dart, Sharrah Pool | River Dart | gauges on the path, catchment too different |
| River Plym, Cadover Bridge | River Plym | gauges on the path, catchment too different |
| River Teign, Fingle Bridge | River Teign | gauges on the path, catchment too different |
| River Cam, Grantchester Meadows | River Cam | gauges on the path, catchment too different |
| River Thames, Lechlade | River Thames | gauges on the path, catchment too different |
| River Thames, Buscot Weir | River Thames | gauges on the path, catchment too different |
| River Rivelin, plunge pool, Rivelin Valley | River Rivelin | gauges on the path, catchment too different |
| Burbage Brook, Padley Gorge | Burbage Brook | gauges on the path, catchment too different |
| River Dane, Panniers Pool, Three Shires Head | River Dane | gauges on the path, catchment too different |
| River Lathkill, Lathkill Dale, Over Haddon | River Lathkill | gauges on the path, catchment too different |
| River Bradford, Bradford Dale, Youlgrave | River Bradford | gauges on the path, catchment too different |
| River Test, Chilbolton Cow Common | River Test | only part-channel gauges |
| River Teign, Drogo Weir | River Teign | no gauge on the river path |

Chilbolton Total, the whole-river station at Chilbolton, has a daily mean but was not on the spot's
path by the network rule. Inferred: it snapped to a parallel channel of the Test (not inspected).

## What is measured and what is inferred

Measured: every number in the tables; the Flood API's model coverage at one cell (forecast series
from 1 Jun 2023 with one gap on 4 Aug 2023, consolidated to 31 May 2025, the seamless default
switching to the forecast series in Aug 2023, apart from three single days); the terms quoted above.

Inferred, not checked: that the past-year series is each day's shortest-lead forecast; why GloFAS
matches best a day late; which river each rule-(b) cell is on; why Chee Dale and Dartington fail;
that some of these stations calibrated GloFAS v4 (which would flatter cell c); that one
hydrological year (Oct 2025 to Sep 2026) is typical. The KGE was meant for comparison with
published GloFAS skill, but no published figure was looked up, so no comparison is made.

Not measured at all: GloFAS skill at forecast leads 2 to 5. Open-Meteo serves no archive of past
forecasts at those leads, so neither test below can measure it either; both measure an upper
bound, the value of knowing the day's flow.

## Two candidate tests for later sessions (not run here)

Both should be stated and committed before any result, like this note, and both should take from
here: rule (b) cells (listed in `docs/GLOFAS-CHECK-2026-11-spots.csv`, so the 3 x 3 search need not
be repeated), GloFAS as a ratio to its own median at that cell, and GloFAS moved one day earlier.

### 1. Forecast-flow dilution against today's held flow, on the E. coli set

This answers part of the Sheffield method review: dilution that follows the river's flow on the
day, not a fixed length ratio.

- **Question:** at each E. coli sample, does a dilution that uses the river's flow on the sample
  day beat one that holds the issue day's flow?
- **Candidates:** the reference as the transport-fit tests ran it (`docs/TRANSPORT-FIT-2-TEST-2026-10.md`:
  dilution `length` at PR #248's settings); dilution `flow` with Q50 replaced by Q50 x R, where R
  is GloFAS on the day over its own median at the spot's cell; and the same with R held at its
  value on the issue day, for each lead 1 to 4 (`scripts/replay_ecoli_leads.py` has the leads).
  The day's R is the upper bound; the held R is today's practice.
- **Data:** the 1,685 samples at 85 bathing waters (2023 to 2026). Use the forecast series
  throughout (from 1 Jun 2023), so every year has the same kind of GloFAS; samples before June 2023
  drop out. Fewer than 85 cells (river bathing waters only) over 3.3 years weigh about 9 calls
  each by Open-Meteo's rule: under 800 calls, in batches kept under 600 a minute.
- **Measures:** as the transport-fit tests: within-site Spearman, AUC, and `train_ecoli`'s
  leave-one-year-out Brier (PR #248's 0.0919), with lake AUC as a condition, as
  `TRANSPORT-FIT-2` asks.
- **What a pass would mean:** only that knowing the day's flow helps. A deployment would then need
  live GloFAS forecasts at leads 1 to 4 archived for a season (72 river spots, 72 calls a day) and
  scored the same way. If the day's R does not beat the held R, stop there.

### 2. Flow as a catchment-wetness input to the spill model

- **Question:** does how wet the catchment is, read from river flow the day before, improve the
  nine-company spill model's 2025 Brier against D2's 0.0362 (ERA5 rain;
  `docs/NINE-COMPANY-MODEL-TEST-2026-10.md`)?
- **Feature:** GloFAS the day before (after the one-day move) as a percentile of that cell's own
  record, at the overflow's receiving river. Comparator: ERA5-Land soil moisture from Open-Meteo's
  archive, which needs no snapping (inferred available; check first). Use the same conditions and
  harness as the live-status test (PR #254).
- **Snapping is the hard part.** Most overflows discharge to small streams, where this check
  found the nearest cell least reliable. A rule-(b) cell per overflow, or one cell per operational
  catchment, keeps requests down: about 500 cells over 2023 to 2025 weigh about 3,900 calls, in
  batches kept under 600 a minute and checked against anything else on the same IP that day.
- **What a pass would mean:** a wetness term helps the spill model in hindsight. Forecast days
  would still need the flow forecast, which is where the lead 2 to 5 question returns.

## Data credits

Contains modified Copernicus Emergency Management Service information 2026 (GloFAS v4, via the
Open-Meteo Flood API, CC BY 4.0, open-meteo.com). Environment Agency Hydrology API daily mean flow,
Open Government Licence v3.0.
