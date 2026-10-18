# GloFAS flow against the EA gauges (review task D5)

Research only. Nothing here changes the site or the model. Task D5 of `docs/REVIEW-2026-10-16.md`,
data source item 4 there (Open-Meteo Flood API, GloFAS v4, 5 km).

## Question

The spill model sees rain, season and three fixed site figures, and nothing about how wet the
catchment is. The transport step holds today's river state flat over the five forecast days (the
reach speed comes from today's EA level index, `transport.river_velocity`). A forecast river flow
could feed both a dilution that changes day by day and a catchment-wetness input. That is only
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
