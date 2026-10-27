# A national air-to-water temperature model: the test, stated before any data is fetched

Written 27 October 2026. **Approved by Ethan on 27 October 2026.** His words: "I approve ... you can work on all of
this autonomously". He ticked "Approve the water-temperature test as stated above, then the training fetch". What he
approved is the model section of the plan, quoted under "The approved test". This document fixes the details of that
test. It was committed before any training data was fetched. No water-temperature value from the training or test
rows has been read for it. No air temperature has been fetched. No model has been fitted.

Results go below the line at the end. Nothing above the line changes after a result is seen. If anything is changed
after a result is seen, both results are kept and the change is stated.

## The approved test (Ethan, 27 October 2026)

Copied from the plan he approved:

- One national air-to-water model trained on every EA Water Quality Archive point in England with determinand 0076
  "Temperature of Water" (OGL v3; environment.data.gov.uk/water-quality; data from 2000). Mohseni-style logistic
  curve on smoothed air temperature, plus inputs: air temperature averaged over 1, 7, 30 days; day of year; water type
  (river/lake/sea); lake area/depth where known; catchment size or elevation; flow where a gauge has it (optional).
- The test: (1) hold out whole rivers and lakes (group by water body), so no water appears in both training and test;
  (2) train on years to 2022, test on May–September 2023–25; (3) beat two baselines on held-out waters: day-of-year
  average, and 7-day air temperature alone; (4) pass only if the gain's 95% interval, resampled by water body, stays
  above zero, and typical error (RMSE) is at most 2 °C for rivers and 1.5 °C for lakes; (5) report small upland
  streams and lakes separately.
- Expected accuracy (inferred): 1.5–2.5 °C on lakes and large rivers, worse on small upland streams. Spot readings are
  taken at a time of day, not daily means.

Everything below is how this test is run. Where the plan left a choice open, the choice is made here, before any data,
and the reason is given. Those choices are mine, not Ethan's. They are marked **[choice]**.

## The question

Can one national model, fed only air temperature, the date and fixed facts about a water, estimate a spot-sample water
temperature at a river or lake it has never seen, within 2 °C for rivers and 1.5 °C for lakes, and better than the two
simple baselines?

Why it matters: 3 of 105 spots have a live sensor (`docs/WATER-TEMPERATURE-2026-10.md`). An estimate could cover the
rest. It would be labelled an estimate, and shown only if this test passes.

## Data sources and licences

**Water temperature: EA Water Quality Archive (WQA).**
- `https://environment.data.gov.uk/water-quality/data/observation`, determinand `0076` "Temperature of Water", unit
  CELSIUS. CSV, at most 2,500 rows a page (the API's own limit for CSV, read in its OpenAPI document on 27 October).
- Licence: Open Government Licence v3.0. The WQA pages say so in their footer, as recorded in
  `docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md`. No WQA page gives its own attribution statement, so the OGL default
  applies: "Contains public sector information licensed under the Open Government Licence v3.0."
- Known before writing (research session, 27 October, 20 requests, `ea_log.json` in that session's scratchpad): a
  query across many points may span at most one year; a single point may span its whole history; June 2025 had
  4,413 river and lake rows at 3,532 points in England, in 1,361 cells of 0.1°. The temperatures in those research
  files were not looked at for this test, and those files are not used in it.
- `phenomenonTime` has no time zone. It is taken as UK local clock time, as the chlorophyll test did. *Inferred, not
  confirmed.*

**Air temperature: ERA5-Land through Open-Meteo's historical archive (free tier).**
- `https://archive-api.open-meteo.com/v1/archive`, `daily=temperature_2m_mean`, `models=era5_land`,
  `timezone=Europe/London`. ERA5-Land is a Copernicus reanalysis at about 0.1° (9 km). The site's rain archive uses
  the same host. Open-Meteo's free API is for non-commercial use; this is a one-off offline training fetch from this
  Mac.
- If the first answer shows that `models=era5_land` does not serve this daily variable, the fetch stops. It is then
  rerun once without `models` (Open-Meteo's default), and that is recorded in the run log. **[choice]**
- Each answer also carries Open-Meteo's `elevation` for the coordinate asked for. That is the cell's elevation used
  below.

**Sources checked and ruled out (27 October 2026, before writing):**
- **Met Office HadUK-Grid** (1 km and 5 km daily max and min, OGL). The CEDA directory listings open without a login.
  A file does not: `tasmax_hadukgrid_uk_5km_day_20250601-20250630.nc` answered HTTP 302 to `/login/`, and the folder's
  licence readme answered "Unauthenticated". It needs a CEDA account. The brief says not to create one. 11 requests to
  `dap.ceda.ac.uk`: directory listings, the readme, and two tries at that one file.
- **E-OBS** (KNMI, 0.1° daily mean temperature, a direct download with no account). Its access page says "These
  observational data are strictly for use in non-commercial research and non-commercial education projects only".
  SwimSignal is considering paid pilots. One request to `surfobs.climate.copernicus.eu`.
- An elevation model download (OS Terrain 50, OGL, 162 MB) was found but not taken. Downloading files beyond the
  approved fetch needs Ethan's say-so. Elevation here is the coarse Open-Meteo cell elevation instead.

**Fixed facts about each water (local files, no request):**
- Rivers: the site's OS Open Rivers network (`data/processed/river_network.pkl` of 11 September 2026, loaded with
  `RiverNetwork.load`, which mends it as the site does).
- Lakes: the EA's WFD lake water bodies, cycle 3 (`data/processed/lakes.parquet`: 564 polygons with `wb_id` and
  `area_km2`). Open Government Licence v3.0, as the site already credits.
- Lake depth: no source is held locally. It is left out. **[choice]**
- Flow: optional in the plan. Left out. **[choice]** Few gauges sit near sampling points, and the flow test the same
  day found the Hydrology archive up to 13 days behind (`docs/FLOW-DILUTION-TEST-2026-10.md`).

## Rows

**Seasons.** **[choice]** Training: 1 May to 30 September of 2018, 2019, 2020, 2021 and 2022. Test: 1 May to 30
September of 2023, 2024 and 2025. By the sample's local date.
- Why from 2018 and not 2000: the Open-Meteo cost is per cell and per day (see "Caps"). Five seasons from about 1,400
  cells already cost two to three days of the free ration. 2018 is included for its hot summer, so the training data
  reach the temperatures of 2025. *Inferred:* about 40,000 training rows a season is enough for a model with this few
  inputs.
- Why May to September only, in training too: the test is May to September. Training on the same months halves the
  air cost against whole years, and the day-of-year baseline is the same months.

**Water type, from the archive's sample material** (`sampleMaterialType`):
- river: `2AZZ` RIVER / RUNNING SURFACE WATER;
- lake: `2GZZ` POND / LAKE / RESERVOIR WATER;
- sea: `2IZZ`, `2IAZ`, `2IBZ`, `2ICZ` (sea water, any tide);
- left out and counted: canal (`2FZZ`, `2FAZ`), estuarine (`2H…`), groundwater, effluents and the rest. **[choice]**
  Canals and estuaries are neither type the site shows.
- A point takes the type most of its rows have (a tie goes to river). All its rows then carry that type.

**Values.**
- The `result` must parse as a number, with unit CELSIUS. Text such as "<0.5" is dropped and counted.
- Kept only from -1 to 35 °C, the live tile's plausibility range. Others are dropped and counted.
- Duplicate observation ids (from paging) are dropped and counted.
- One row per point and local date: the mean of that day's readings at that point. The number of days with more than
  one reading is reported.
- A row needs its cell's air temperature on every one of its 30 days (below). Rows without it are dropped and
  counted by type.

## Water bodies (the groups)

The archive carries no WFD water body id (checked in its OpenAPI document: a sampling point has notation, labels,
coordinates, status, type and EA region, area and sub-area only). So points are put into water bodies by these
rules, fixed now:

**Rivers.** The point is snapped to the nearest OS Open Rivers link of form `inlandRiver` or `tidalRiver` within
250 m.
- A **river** is a connected set of links that carry the same `watercourse_name` (trimmed, case ignored) and touch at a
  node. Its id is the name plus the smallest link id in the set. So two different River Avons are two rivers.
- A point on an **unnamed** link joins the first named river found downstream along the network, within 50 km. So a
  small unnamed tributary is held out with the river it feeds. *Inferred:* that makes the hold-out stricter, not
  looser.
- A point that does not snap, or finds no named river downstream, is a water of its own (`pt:<notation>`).
- **Limitation, stated now:** a named tributary or side channel (for example a "Mill Stream" beside its river) is a
  separate water from the river it joins. Its temperature is close to the river's. This can leak a little between
  training and test. It is not corrected.

**Lakes.** A point inside a WFD lake polygon, or within 100 m of one, belongs to that lake (`lake:<wb_id>`) and takes
its area. Otherwise, a point within 250 m of an OS Open Rivers `lake` link belongs to that link's connected lake
(`RiverNetwork.lake_component`), with no area. Otherwise it is a water of its own.

**Sea.** Sea points are grouped by the 10 km Ordnance Survey grid square they fall in. **[choice]** Neighbouring
beaches share their sea.

**Folds.** Every water body goes to one of 5 folds by `int(sha256(id), 16) % 5`. Fold k's model is trained on the
training seasons' rows of the waters in the other four folds, and predicts the test seasons' rows of the waters in
fold k. So every water is predicted once, by a model that never saw it in any year. No water's rows are ever in both
the training and the test set of one model.

## Inputs

For a row at point p on local date d, with c the 0.1° cell of p (the site's rain-cell rule, `rainfall.grid_cell`):

| input | definition |
|---|---|
| `a1` | air temperature, the daily mean on d at c |
| `a7` | mean of the daily means on d and the 6 days before |
| `a30` | mean of the daily means on d and the 29 days before |
| day of year | as sine and cosine of 2π × day / 365.25 |
| water type | river, lake or sea |
| lake area | log10 of the WFD polygon's km²; missing for other waters and unmatched lakes |
| catchment size | log10 of the network length upstream of the snapped point, in km (the link's upstream length plus the part of the link above the point). Missing for lakes, sea and unsnapped points |
| elevation | Open-Meteo's elevation for the cell centre, in metres |

*Stated now:* the air series is at the cell centre, not the point. The live site asks for its weather at the same cell
centres. Day d itself is in every average. On the site that day comes from the forecast.

The time of day of the sample is not an input. The plan did not list it. A spot reading is taken at one time; that adds
to every model's error alike.

## The candidate model

Two stages, fitted on the training rows of each fold.

1. **Mohseni curve, one per water type**, on `a7`:
   `T = mu + (alpha - mu) / (1 + exp(gamma × (beta - a7)))`. Least squares (`scipy.optimize.curve_fit`), starting at
   mu 0, alpha 25, beta 13, gamma 0.2, within bounds mu -5 to 10, alpha 15 to 35, beta 0 to 30, gamma 0.01 to 2. If the
   fit fails, or the type has fewer than 20 training rows, the starting values are used and the failure is reported.
2. **A gradient-boosted correction** of the stage 1 residual, one model across all types: scikit-learn
   `HistGradientBoostingRegressor` on every input in the table above (water type as a categorical; missing values
   handled natively; an input with no value at all in a fold's training rows is left out of that fold's fit). Settings fixed now, never tuned on any result: squared error, learning rate 0.05, 400
   iterations, 31 leaves at most, at least 100 rows a leaf, L2 1.0, no early stopping, `random_state` 0. **[choice]**

The estimate is stage 1 plus stage 2.

## The baselines

Both fitted on the same training rows as the candidate, per fold, by water type.

- **Day-of-year average.** The mean training water temperature for each day of the year, smoothed over a 31-day
  window centred on the day (sum of temperatures in the window ÷ number of rows in it). A day with no rows within its
  window takes the type's mean.
- **7-day air temperature alone.** Ordinary least squares, `T = a + b × a7`. **[choice]** A straight line is the
  plain reading of "7-day air temperature alone".

## Scores and the verdict

On the test rows of all five folds together, separately for rivers and for lakes:

- **RMSE** of the candidate and of each baseline, in °C. Each row counts once.
- **Gain** over a baseline = RMSE(baseline) − RMSE(candidate). Positive is better.
- **95% interval of each gain, resampled by water body:** 2,000 resamples of that type's water bodies with
  replacement; each drawn water brings all its test rows; the gain is recomputed; the 2.5th and 97.5th percentiles are
  the interval. numpy `default_rng(20261027)`.

**A water type passes if all four hold:**
1. the lower end of the gain over the day-of-year baseline is above 0;
2. the lower end of the gain over the 7-day air baseline is above 0;
3. the candidate's RMSE is at most 2.0 °C for rivers, or at most 1.5 °C for lakes;
4. the gate: at least 30 held-out water bodies and 300 test rows of that type.

If the gate fails, the type is "too few to judge" and cannot pass. Rivers and lakes get a verdict each. Sea has no
threshold in the plan: it is reported and decides nothing.

**Reported, deciding nothing** (plan item 5 and the rest):
- **Small upland streams:** river points with catchment size under 20 km of upstream network and cell elevation of at
  least 200 m. Defined now, before any outcome. *Stated now:* the cell elevation is coarse; a stream in a valley can
  sit well below its cell's figure.
- Rivers by catchment size: under 20 km, 20 to 200 km, 200 km and over, unknown.
- Lakes: WFD-matched with area under 1 km², 1 km² and over, and unmatched.
- Sea.
- For each: rows, waters, RMSE, mean error (bias), mean absolute error, and the 90th percentile of the absolute error,
  for the candidate and both baselines.
- By test year, by month, by fold; and the stage 1 curve alone.
- Rows dropped at each rule, by type.

## What follows

- **Nothing on the live site changes in this PR.**
- **If rivers or lakes pass:** a separate draft PR, for the types that pass only. It adds `temperature_2m` to the
  site's existing forecast request (its weight stays 1 a cell: `call_weight(n, 38, 2)` is `n × max(1, 0.2, 0.54)`), and
  shows "About N °C (estimated, typically within X °C)" on spot pages, after the live sensor tile where one exists. X is
  the type's held-out RMSE, rounded up to the next 0.5 °C. Before that PR is opened, a reported check compares
  Open-Meteo's forecast-API past days with ERA5-Land at a sample of spot cells, because the model is trained on one and
  fed the other. Ethan decides whether it ships.
- **If neither passes:** no display is built. This PR records what failed.

## What is expected, stated now

Guesses, not results.
- Rivers: candidate RMSE about 1.7 to 2.3 °C. Close to the 2.0 °C line either way.
- Lakes: about 1.6 to 2.2 °C. More likely than not to miss 1.5 °C. Sampled lakes include reservoirs and deep lakes,
  whose surface lags the air by weeks, and the model knows no depth.
- Gains: likely positive against both baselines. Day of year knows no weather. A straight line in `a7` knows no lag.
- Small upland streams: worse than other rivers, as the plan expects. Their elevation and shade are not in the inputs.
- Sea: worst of all. Sea temperature follows months of weather, not a 30-day window.

## Caps, sized before any request

**EA Water Quality Archive** (`wt_fetch.py ea`):
- Queries: one per calendar month, May to September, 2018 to 2025 (40 months), for each of two material sets:
  fresh (`2AZZ,2GZZ`) and sea (`2IZZ,2IAZ,2IBZ,2ICZ`). Pages of 2,500 rows (`skip` in steps of 2,500) until a page has
  fewer than 2,500.
- Expected: about 2 to 3 pages a fresh month (June 2025 had 4,413 rows) and 1 to 2 a sea month. About 160 requests.
- **Caps:** at most **300 requests** in all; at most **8 pages** for one month and set (more means paging is not
  working, and the run stops); one request in flight; at least **1.5 s** from the end of one request to the start of the
  next; https to `environment.data.gov.uk` only; **stop** at the first 403, 429, 5xx, redirect or connection error, with
  no retry; stop if the answers pass **600 MB** in all (expected about 160 MB).
- Wall time: about 160 × (1.5 s + about 6 s an answer) = about 20 minutes.

**Open-Meteo archive** (`wt_fetch.py open_meteo`):
- One request per season per batch of at most 25 cells. A cell is asked for in a season only if it has at least one
  kept row in that season. Each season runs from 1 April (for the 30-day averages of early May) to 30 September: 183
  days. Open-Meteo's weight is `call_weight(n, 183, 1)` = 1.307 per cell (`rainfall.call_weight`, its own rule).
- Expected: about 1,400 cells a season × 8 seasons × 1.307 = about **14,600** weighted calls.
- **Caps:** at most **20,000** weighted calls in all; at most **6,000** in one UTC day, counted from this fetch's own
  log; one request in flight, at least **60 s** apart (at most about 2,600 an hour, under Open-Meteo's 5,000 an hour);
  https to `archive-api.open-meteo.com` only; **stop** at the first 4xx, 5xx, redirect, connection error or body that
  is not JSON, with no retry. A stop is resumed no earlier than the next UTC day, at most twice; a third stop ends the
  fetch and is reported.
- **If the planned total is over 20,000** once the cells are known (after the EA fetch, before any Open-Meteo
  request), training seasons are dropped, oldest first, until it fits. At least three training seasons stay. If it
  still does not fit, sea cells are dropped (sea decides nothing). Whatever is dropped is recorded in the run log
  before the first Open-Meteo request.
- Run only from this Mac. Before each day's run, `pgrep -fl` must show no other local Open-Meteo job; if one is
  running, the fetch waits. The process name carries `open_meteo`, so other sessions' checks see it.
- Wall time: about 14,600 ÷ 6,000 = **3 UTC days**.

**Other hosts:** none. No request to any other host.

**Cache.** Every answer is kept outside git, in `~/Documents/GitHub/swimsignal-private/water-temperature/`, one folder
per host (`ea/`, `open-meteo/`), with a `requests.log` (UTC time, status, bytes, weight, URL) in each. A cached
answer is never asked for again. A run stopped at a cap resumes from the cache.

**Compute.** The network snap, the fit and the bootstrap run under the group's `heavy-run.lock`, and so does the EA
fetch. The Open-Meteo fetch is a slow trickle over days and light on the machine; it runs without the lock.

## Order of work

1. This statement, committed and in a draft PR. Then the harness and its synthetic tests, committed, before any
   request.
2. EA fetch. Then the rows, types and water bodies (offline). No temperature is summarised or plotted.
3. The Open-Meteo plan (cells per season, total weight, anything dropped), recorded in the run log. Then the fetch.
4. The features file assembled. Its SHA-256 committed to this PR **before any model is fitted or scored**.
5. One scoring run, offline, from the committed code. Then the results below the line.

The harness is `scripts/water_temperature_model_eval/`: `wt_protocol.py` (the rules above), `wt_fetch.py` (the capped
clients) and `wt_score.py` (rows, groups, features, fit and score). Its tests are
`tests/test_water_temperature_model_eval.py`, on synthetic data only.

## Seen before writing

- Read on 27 October 2026: `docs/WATER-TEMPERATURE-2026-10.md`, `docs/FLOW-DILUTION-TEST-2026-10.md`,
  `docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md` (opening sections), `src/dipcast/ingest/rainfall.py` (`call_weight`,
  `grid_cell`, `fetch_forecast`), `src/dipcast/ingest/lakes.py`, `src/dipcast/network/rivers.py`, the WQA OpenAPI
  document and sample-material codelist from the research session.
- From the research session's June 2025 file: counts of rows, points, cells, materials and point types only.
- Requests made in writing this: 11 to `dap.ceda.ac.uk` (listings, a readme, one file refused), 1 page from
  `surfobs.climate.copernicus.eu`, 1 product listing from `api.os.uk`. None returned a temperature.
- No WQA request, no Open-Meteo request.

## Run log (written before any score)

Code: this branch. Data and caches: `~/Documents/GitHub/swimsignal-private/water-temperature/`, outside the repo.

**EA fetch, 27 October 2026, 14:18 to 14:25 UTC, under the heavy-run lock.** 121 requests in all (cap 300), 67.3 MB
(cap 600 MB), `environment.data.gov.uk` only:
- 1 answered **405**. The multi-point endpoint is POST only (its OpenAPI document lists `post /data/observation`).
  The client stopped, as it should. It now sends POST with an empty body (commit d93e921).
- 2 answered 200 but were superseded: **`dateTo` is exclusive.** `dateTo=2018-05-31` returned nothing after 30 May
  18:35. Each month's `dateTo` is now the first day of the next month (d93e921). The two files are kept aside, unused.
- 5 answered **204** (no rows). The first, sea water in May 2020, stopped the run. A 204 is now an empty page
  (9174426), and the run resumed from the cache.
- 113 answered 200 and are used: 117 pages counting the 204s, 170,183 rows.

**Rows** (`wt_score.py rows`): 165,181 point-days kept. Dropped: 0 duplicate ids, 0 other materials, 0 not Celsius,
0 not a number, 4 out of range. 2,965 point-days had more than one reading. Rows by type and season:

| type | training (2018–22) | test (2023–25) | points |
|---|---|---|---|
| river | 67,330 | 67,010 | 10,342 |
| lake | 2,221 | 2,974 | 495 |
| sea | 2,810 | 22,836 | 782 |

**2020 is nearly empty.** 64 cells have a row in May to September 2020, against 1,253 to 1,686 in the other
seasons. *Inferred:* sampling stopped in spring 2020, as the chlorophyll test found.

**Water bodies** (`wt_score.py groups`, 12 s, 0.8 GB peak). River points: 7,849 on a named link, 1,234 joined to
the first named river downstream, 1,259 a water of their own (no river link within 250 m, or no named river
downstream). Lake points: 207 in or within 100 m of a WFD polygon, 70 on an OS lake link, 218 their own water. Sea:
782 points in 253 squares. Waters: 5,134 river, 421 lake, 253 sea; 1,093 to 1,202 per fold. 1,872 cells of 0.1°.

**Open-Meteo plan** (`wt_score.py plan`, before any Open-Meteo request): 424 requests, **13,680.6 weighted calls**
(cap 20,000), so **nothing is dropped**. Cells by season: 2018 1,327; 2019 1,541; 2020 64; 2021 1,431; 2022 1,253;
2023 1,561; 2024 1,686; 2025 1,603. 91 cells hold only sea points. At 6,000 a UTC day this takes three UTC days.

---

## Results

Not run yet.
