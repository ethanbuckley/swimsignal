# A national air-to-water temperature model: the test, stated before any data is fetched

Written 27 October 2026. **Approved by Ethan on 27 October 2026.** His words: "I approve ... you can work on all of
this autonomously". He ticked "Approve the water-temperature test as stated above, then the training fetch". What he
approved is the model section of the plan, quoted under "The approved test". This document fixes the details of that
test. It was committed before any training data was fetched. No water-temperature value from the training or test
rows has been read for it. No air temperature has been fetched. No model has been fitted.

Results go below the line at the end. Nothing above the line changes after a result is seen. If anything is changed
after a result is seen, both results are kept and the change is stated.

**Two amendments, both on 27 October 2026 and both before any score:** the Open-Meteo pace (in "Caps"), and
training on 2000–2022 with HadUK-Grid air temperature ("Amendment 2", below "Caps"). Where Amendment 2 differs from
the text above it, Amendment 2 holds.

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

**Amendment, 27 October 2026, before any score.** Ethan asked for the air fetch to go faster. His reason is
speed only. No outcome has been seen: no model has been fitted, and no water temperature has been summarised. This
Mac's free Open-Meteo quota (10,000 a day, 5,000 an hour, 600 a minute, per IP) is separate from the site's GitHub
builds, so the caps above were more cautious than needed. From the restart on 27 October:
- at most **9,500** weighted calls in one UTC day, counted from this fetch's own log, including what it had already
  used that day (was 6,000);
- at most **4,700** weighted calls in any rolling hour; at 32.7 a request that is one request every 25 s or more, so
  the pause is now **25 s** (was 60 s);
- the total cap stays **20,000**;
- the stop rules are unchanged: stop at the first 4xx, 5xx, redirect, connection error or body that is not JSON, with
  no retry. After a 429 the fetch resumes no earlier than the next UTC day.
- The other-job check now looks only for Python processes that fetch from Open-Meteo (a second `wt_fetch.py
  open_meteo`, or a Python command line naming Open-Meteo), leaving out this process and its parent. The first
  version also matched this test's own log-watching shells, whose command lines name `open_meteo.log`, and paused the
  fetch at 14:27 UTC. The check never stops another process.
- Wall time becomes: about 9,500 by the evening of 27 October, the rest from 00:10 UTC on 28 October, done about
  01:00 UTC.

**Other hosts:** none. No request to any other host.

**Cache.** Every answer is kept outside git, in `~/Documents/GitHub/swimsignal-private/water-temperature/`, one folder
per host (`ea/`, `open-meteo/`), with a `requests.log` (UTC time, status, bytes, weight, URL) in each. A cached
answer is never asked for again. A run stopped at a cap resumes from the cache.

**Compute.** The network snap, the fit and the bootstrap run under the group's `heavy-run.lock`, and so does the EA
fetch. The Open-Meteo fetch is a slow trickle over days and light on the machine; it runs without the lock.

## Amendment 2, 27 October 2026: training on 2000–2022 with HadUK-Grid (before any score; no outcome seen)

**Ethan's decision, his words:** "Hold the scoring. I'll register at CEDA and make a token; then give me the download
command, and amend the test to train on 2000–2022 before any score."

When this was written: the EA fetch for 2018–2025 was done, and 26 Open-Meteo answers for 2018 were cached. No
features file had been built. No model had been fitted. No water temperature had been summarised, plotted or
compared with any air temperature.

What changes:

- **Training seasons:** 1 May to 30 September of every year from **2000 to 2022**. Test seasons unchanged: May to
  September 2023–25.
- **Training air input: Met Office HadUK-Grid v1.3.2, 5 km, daily mean `tas`** (OGL v3, per CEDA's catalogue). Files
  `tas_hadukgrid_uk_5km_day_YYYYMM01-YYYYMMDD.nc`, April to September, 2000 to 2025: 156 files. **Ethan downloads them
  himself** with his own CEDA token, into `~/Documents/GitHub/swimsignal-private/water-temperature/haduk/`, with the
  script `get_haduk.sh` in that folder. I do not run it and never handle his token. The run waits until the folder
  holds all 156 files and each one opens (its `tas` has one step per day of its month).
  - Each point takes the 5 km grid cell it falls in (British National Grid). If that cell has no value (sea or a
    coastal edge), the nearest cell with values within 10 km. Otherwise the point has no HadUK air and its training
    rows are dropped and counted.
  - `a1`, `a7` and `a30` are computed from the HadUK series exactly as stated under "Inputs".
  - *Stated now, not checked:* HadUK's daily mean is built from daily maximum and minimum, whose day runs from 09:00
    to 09:00 UTC. Open-Meteo's daily mean is the London calendar day. The two days are offset by up to 9 hours.
- **Test-season air input, and which decides the verdict.** **[choice]**
  - **Primary, decides the verdict:** Open-Meteo's ERA5-Land daily mean for 2023–25, as already stated, because it
    is closest to what the live site would feed the model (the site's weather comes from Open-Meteo at the same
    cells). The model is trained on HadUK, so the Open-Meteo values pass through a **bridge** first: one national
    straight line, `HadUK = c + d × OpenMeteo`, fitted by least squares on daily values from 1 April to 30 September
    2018. One pair per day for each distinct (HadUK cell, Open-Meteo cell) of the points with a row in May to
    September 2018. No water temperature enters the bridge. The bridged daily values then give `a1`, `a7`, `a30`.
    Both the candidate and the 7-day air baseline are fed the bridged values.
  - Why 2018 only: one hot season spans the range of 2023–25, and it is already half fetched. Why a straight line and
    not a per-cell offset: 2018 lacks a fifth of the test cells.
  - **Secondary, reported, decides nothing:** the same test with HadUK air for 2023–25 (no bridge), on the test rows
    that have HadUK air. Also reported: Open-Meteo with no bridge. And the bridge itself: c, d, the number of pairs,
    and the root-mean-square difference before and after.
- **Elevation** stays Open-Meteo's cell elevation. Cells whose points have rows only before 2018 have no Open-Meteo
  answer. For them: one request per batch of at most 25 cells for a single day (1 June 2018, the same variable and
  model). Its weight is 1 a cell (`om_weight(n, 1)` = n). Only the elevation is used. Cap: at most **1,500** weighted
  calls for these.
- **Open-Meteo, narrowed:** the 2018 season (for the bridge; 54 requests, 26 already done), the test seasons 2023,
  2024 and 2025, and the elevation-only requests. **2019 to 2022 are not fetched.** Expected: 1,327 × 1.307 + 4,850 ×
  1.307 + up to 1,500 = about **9,600** weighted calls in all, of which 850 were spent before this amendment. The
  total cap stays 20,000, the day cap 9,500, the rolling-hour cap 4,700, the pause 25 s, the stop rules unchanged.
- **EA archive, extended** to May–September 2000–2017: 90 more months, same queries, same client (POST, `dateTo`
  exclusive, a 204 as an empty page), one request in flight, at least 1.5 s apart, same stop rules.
  - Expected: 3 to 5 pages a month (June 2005's first page of fresh water was full) and 1 for sea, so about 300 to
    550 requests.
  - **Caps for the extension, sized now:** at most **700 more requests** (so at most **850** in this test's EA log
    all told, which holds 121 already); at most **12 pages** for one month and set (was 8); stop past **1.5 GB** in
    all (was 600 MB). Wall time: about 550 × 3 s, about 30 minutes, under the heavy-run lock.
- **Unchanged:** hold-out by water body and the 5 folds, both baselines, the thresholds (2.0 °C rivers, 1.5 °C lakes),
  the gate, the groups, the inputs other than the air source, the model and its settings, the reported groups.

Order from here: push this amendment; the EA extension; rows and water bodies again over all years (a water's fold
depends only on its id, so existing waters keep their folds); the narrowed Open-Meteo fetch; wait for the 156 HadUK
files; the bridge; the features file and its SHA-256, committed; then one score.

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

**Open-Meteo, first run** (14:26 to 14:46 UTC): 26 requests for the 2018 season, all HTTP 200, 849.6 weighted calls.
It paused once at 14:27 on its own log watchers (the other-job check, fixed under the pace amendment) and was stopped
twice by me between requests: once for the pace amendment, once for amendment 2. All 26 answers are cached and used.

**After amendment 2.**

*EA extension, 14:51 to 15:07 UTC, under the heavy-run lock:* 356 requests, all HTTP 200, 252.7 MB (caps: 700 more
requests, 1.5 GB in all). The log now holds 477 requests, 320 MB. No month needed more than 12 pages.

*Rows, all years* (2000–2025): 813,733 raw rows; dropped 4 duplicate ids, 6 not a number, 17 out of range; 790,196
point-days kept, 10,175 with more than one reading.

| type | training (2000–22) | test (2023–25) | points |
|---|---|---|---|
| river | 587,295 | 67,003 | 18,096 |
| lake | 12,736 | 2,982 | 826 |
| sea | 97,345 | 22,835 | 1,508 |

The test rows differ slightly from the first count (river 67,003 not 67,010; lake 2,982 not 2,974; sea 22,835 not
22,836). A point's type is the type most of its rows have, and older rows changed the majority at a few points.

*Water bodies, all years:* river points 12,900 on a named link, 2,177 named downstream, 3,019 their own water; lake
points 340 WFD polygon, 87 OS lake link, 399 their own; 1,508 sea points. Waters: 8,093 river, 671 lake, 334 sea;
1,723 to 1,871 a fold. 1,957 cells of 0.1°.

*Open-Meteo plan, narrowed* (before its first request): 2018 1,327 cells, 2023 1,561, 2024 1,686, 2025 1,603, and
118 elevation-only cells. 255 requests, **8,192.2 weighted calls** in all (849.6 already spent), elevation 118 (cap
1,500).

*HadUK-Grid files:* Ethan downloaded all 156 at about 15:30 UTC with his own CEDA token (546 MB; each begins with the
HDF5 signature, so NetCDF-4). I never saw the token. SHA-256 of the sorted list of the 156 files' SHA-256s
(`shasum -a 256 tas_*.nc`, saved as `work/haduk_files.sha256`):
`7eadc03d0a23c1ff50f1239899f4c19d3611fc81399447649d15cdb602b30d2e`.
`wt_score.py haduk` (15:40 UTC, h5py in a throwaway environment, no water temperature read) opened every file: each
`tas` has one step per day of its month (4,758 days in all), and all share one 180 × 290 grid of 5 km cells. Of those
cells, 10,432 have values. Points: 413 have no valued cell within 10 km and get no HadUK air; 738 took a neighbouring
cell; the 4,586 cells used have no missing day. `tas` is labelled "Mean air temperature" at 1.5 m, with
`cell_methods: time: mid_range` (the mean of the day's maximum and minimum). Its time bounds are calendar days. Whether
the maximum and minimum behind it run 09:00 to 09:00 was not checked.

*Open-Meteo, narrowed fetch* (15:07 to 17:04 UTC): 215 requests answered HTTP 200; then one **connection error** at
17:04, and the fetch stopped, as its rule says. 2018, 2023 and 2024 are complete; 2025 has 56 of 65 batches; the 5
elevation batches are not done. The log holds 241 answers, 7,808.9 weighted calls, and at most 4,248 in any clock
hour. Under the stop rule the fetch resumes no earlier than the next UTC day: from 00:05 UTC on 28 October, from its
cache (the first of at most two resumes). The rest is about 412 weighted calls.

**Not as written:** the fetch did not wait for the next UTC day. The coordinating session found the archive answering
again at 17:25 UTC and restarted it at 17:26. I cancelled my own midnight resume so that only one fetch ran. The
restart paused on its other-job check while my features dry run ran (that run's command line names `open-meteo`).
It stopped again on a connection error at 17:50 (251 answers, 8,099 weighted). The coordinating session restarted it
at 18:09 through a wrapper that reruns it after 120 s, up to 12 times. It finished at 18:10:50 UTC after one run. The
Mac's connection was dropping in short bursts. *Inferred:* a network fault cannot bias the air values; an answer is
either cached whole or not at all.

**Open-Meteo totals:** 255 answers, all HTTP 200, 2 connection errors, **8,192.2 weighted calls** (the plan's figure;
cap 20,000). By clock hour: 14:00 850; 15:00 2,748; 16:00 4,212; 17:00 290; 18:00 93. All on 27 October, under the
day's 9,500. Answers by season: 2018 54, 2023 63, 2024 68, 2025 65, elevation 5.

**Fetch tool change, after the fetch (commit 4948dbd), approved by Ethan:** a network error (no answer: connection,
DNS, TLS, timeout) is now tried again after 30 s, 2 min and 5 min, each retry logged, then the run stops. An answer of
any status is still never retried. It changes no feature and no score, and was not used for any request here.

**Features file** (`wt_score.py features`, 18:12 to 18:26 UTC, commit 4948dbd, under the heavy-run lock, 15 min):

- **SHA-256: `4e9ca630a8658aaea7eb69890571def6ab55f5e5e7d95c985d261ff7a77f936d`**, 784,409 rows. Committed here
  before any model is fitted or scored. `wt_score.py score` refuses any other file.
- **The bridge** (2018, no water temperature): `HadUK = 0.5013 + 0.9792 × OpenMeteo`, from 446,337 daily pairs at
  2,449 (HadUK cell, Open-Meteo cell) pairs. Root-mean-square difference 0.939 °C before, 0.914 °C after.
- Rows kept:

  | type | training (2000–22, HadUK air) | test (2023–25, bridged Open-Meteo air) |
  |---|---|---|
  | river | 583,916 | 66,577 |
  | lake | 12,371 | 2,967 |
  | sea | 96,275 | 22,303 |

- Dropped for want of air: training river 3,379, lake 365, sea 1,070 (no HadUK cell within 10 km); test river 426,
  lake 15, sea 532 (no Open-Meteo value).
- 91,825 test rows also have HadUK air (the secondary arm). Every row has an elevation (1,957 cells).
- Checks on inputs only: no infinite value; no missing `a1`, `a7`, `a30`, day of year or elevation; lake area on
  10,874 lake rows; every water in exactly one fold. Waters with rows: 7,799 river, 616 lake, 314 sea.
- A dry run of the same stage (17:24 to about 17:40 UTC), on a copy before the fetch had finished, was used only to find faults in
  the code. It fitted nothing and scored nothing. Its file (hash 763d0c25…) is not used.

---

## Results

Added 27 October 2026 after the one scoring run: 18:28 UTC, 31 s, commit 4b3c3dc, under the heavy-run lock, offline.
The features file's SHA-256 matched the one committed in d15670a before the run. Aggregates only:
`docs/WATER-TEMPERATURE-MODEL-TEST-2026-10-score.json`. The per-row predictions stay in the private folder.

**Verdict, primary input (bridged Open-Meteo air for 2023–25): rivers pass; lakes fail.**

| | rivers | lakes |
|---|---|---|
| held-out waters / test rows | 3,798 / 66,577 | 307 / 2,967 |
| candidate RMSE | **1.56 °C** | **1.82 °C** |
| day-of-year baseline RMSE | 2.19 °C | 2.46 °C |
| 7-day air baseline RMSE | 1.85 °C | 1.92 °C |
| gain over day of year [95% interval] | 0.63 [0.59, 0.67] | 0.64 [0.34, 0.92] |
| gain over 7-day air [95% interval] | 0.29 [0.27, 0.31] | 0.10 [**−0.02**, 0.23] |
| 1. beats day of year | yes | yes |
| 2. beats 7-day air | yes | **no** (interval reaches below 0) |
| 3. RMSE limit (2.0 rivers, 1.5 lakes) | yes | **no** (1.82 > 1.5) |
| 4. gate (30 waters, 300 rows) | yes | yes |
| **label** | **pass** | **fail** |

Other figures for the candidate: rivers bias +0.27 °C, mean absolute error 1.19 °C, 90% of errors within 2.51 °C;
lakes bias −0.40 °C (too cold), mean absolute error 1.36 °C, 90% within 3.01 °C.

**Sea** (reported, decides nothing): 227 waters, 22,303 rows; candidate 1.55 °C, day of year 2.13, 7-day air 1.63.

**Secondary inputs (decide nothing):**

| input for 2023–25 | rivers: candidate / 7-day air | lakes: candidate / 7-day air |
|---|---|---|
| bridged Open-Meteo (primary) | 1.56 / 1.85 | 1.82 / 1.92 |
| HadUK (91,825 rows) | 1.52 / 1.82 | 1.69 / 1.85 |
| Open-Meteo, no bridge | 1.55 / 1.83 | 1.87 / 1.96 |

With HadUK air the lake gain over 7-day air is 0.15 [0.06, 0.24], so condition 2 would hold, but the RMSE (1.69)
still misses 1.5. *Inferred:* the input source moves lakes by about 0.1 to 0.2 °C; it does not decide the lake
verdict. The bridge made rivers a little worse than no bridge (1.56 against 1.55) and lakes a little better.

**Groups (primary input; candidate / day of year / 7-day air, RMSE in °C):**

| group | waters | rows | candidate | day of year | 7-day air |
|---|---|---|---|---|---|
| small upland streams (< 20 km upstream, cell ≥ 200 m) | 410 | 5,684 | 1.57 | 2.41 | 1.88 |
| rivers, under 20 km upstream | 2,495 | 36,499 | 1.61 | 2.10 | 1.88 |
| rivers, 20 to 200 km | 912 | 19,153 | 1.41 | 2.08 | 1.64 |
| rivers, 200 km and over | 203 | 6,898 | 1.36 | 2.72 | 2.01 |
| rivers, not on the network (catchment unknown) | 724 | 4,027 | 2.02 | 2.41 | 2.20 |
| lakes, WFD, under 1 km² | 73 | 619 | 1.70 | 2.68 | 2.05 |
| lakes, WFD, 1 km² and over | 11 | 691 | **2.18** | 1.86 | 1.96 |
| lakes, not matched to a WFD polygon | 223 | 1,657 | 1.70 | 2.59 | 1.86 |

Small upland streams gain 0.83 [0.72, 0.95] over day of year and 0.30 [0.24, 0.37] over 7-day air. They are not
worse than other rivers, against the plan's expectation. The worst river group is points that did not snap to the
network (2.02).

The 11 large lakes are the one group where the candidate is worse than both baselines (2.18 against 1.86 and 1.96).
*Inferred:* a deep lake's surface lags the air by more than 30 days, and the model has no depth.

**By year and month (candidate RMSE):** rivers 2023 1.55, 2024 1.48, 2025 1.66; May 1.57, June 1.68, July 1.61,
August 1.57, September 1.37. Lakes 2023 1.91, 2024 1.76, 2025 1.83; May 2.03, June 2.09, July 1.82, August 1.66,
September 1.44. Lakes are too cold early in the season (bias −1.04 °C in May) and slightly too warm in September
(+0.37 °C). The 30-day air average does not carry enough of a lake's memory. Rivers by fold: 1.51 to 1.63; lakes by
fold: 1.54 to 2.00.

**The stage 1 curve:** in every fold the river and lake curves hit the upper bound for alpha (35 °C), with gamma
about 0.08 to 0.11. In the May–September range the logistic is close to a straight line. So stage 1 alone equals
the 7-day air baseline to 0.01 °C. All the gain over that baseline comes from the boosted correction (the 1- and
30-day averages, day of year, type, size and elevation). The sea curve fitted inside its bounds. All 15 fits
converged.

**What this does not show.** Every test row is an EA spot sample, mostly taken in the working day. These are not
swim-spot readings, and the estimate is of a daytime spot reading. The bridge was fitted on archive air. The live site
would feed forecast-API air (model analyses for past days, a forecast for today). That gap is not measured here. It
is the check stated under "What follows", before any display.

### What follows from this result

- **Rivers passed.** As stated, a separate draft PR may add the estimate for river spots only, "about N °C
  (estimated, typically within 2 °C)": 1.56 °C rounded up to the next 0.5 °C. It comes after the live sensor where a
  sensor exists. First comes the check of forecast-API air against ERA5-Land at spot cells. Ethan decides whether it
  ships.
- **Lakes failed.** Lake spots get no estimate. The large-lake result says what a lake model would need first: a
  longer air memory or depth.

Ethan, 27 October, after the result: "okay rivers go ahead now and the lets do more tests for lakes". Lakes go to a
separate piece of work. This document covers rivers only from here.

### Forecast-air check, stated before its requests (27 October 2026)

**Why.** The model was tested on archive air (ERA5-Land) passed through the bridge. The site would feed it the
forecast API's air: its past days are model analyses, and today is a forecast. If those differ from ERA5-Land by more
than the bridge allows for, the tested error does not carry over to the site.

**Cells:** the 0.1° rain cells (`rainfall.grid_cell`) of the 72 river spots in `spots.csv` and `spots-osm.csv`:
62 cells.

**Requests** (`wt_air_check.py`, through the test's capped Open-Meteo client: its log, its day and rolling-hour caps,
25 s apart, network errors retried after 30 s, 2 min and 5 min, any answer other than 200 a stop):
1. **Forecast, as the site would ask:** `api.open-meteo.com/v1/forecast`, `hourly=precipitation,temperature_2m`,
   `past_days=31`, `forecast_days=6`, `timezone=UTC`. Weight `call_weight(n, 38, 2)` = 1 a cell.
2. **Forecast, rain only,** the same request with `hourly=precipitation`, to check that adding temperature leaves the
   rain values unchanged. Weight 1 a cell.
3. **Archive:** ERA5-Land daily mean, `timezone=Europe/London`, for the same 31 past days. Weight 1 a cell.

In batches of at most 25 cells: 9 requests, **186 weighted calls**. Cap for this check: **250**. Hosts:
`api.open-meteo.com` and `archive-api.open-meteo.com` only.

**Measures.** Forecast daily means are London calendar days built from the hourly values. A day counts only if all
24 hours are present (25 or 23 on the clock-change day, 25 October). Archive days are those ERA5-Land has; it runs
about five days behind. For each cell and day with both: d = forecast − archive. Then `a7` from each source on days
whose 7 days are all present in both, and the difference.

**Pass rule, fixed now:** the mean `a7` difference over all cells and days is within ±0.5 °C, **and** the
root-mean-square `a7` difference is at most 1.0 °C. Why these limits: the model's response to `a7` is below 1 °C per
°C (the 7-day air baseline's slope), so a 0.5 °C input bias moves an estimate by under 0.5 °C. Added to the test's
1.56 °C error in quadrature, that gives about 1.64 °C, still inside the 2 °C that would be shown. *Inferred, not
tested.* Also reported, deciding nothing: the daily differences, their spread by cell, and whether any rain value
differs between requests 1 and 2.

**If it fails:** nothing is built. Nothing is refitted: no bridge, no model. It is reported to Ethan.

**Limits, stated now:** one window (late September to late October), outside the May–September season the model was
tested on. 62 cells. The forecast for today itself is not checked, since ERA5-Land has no today.
