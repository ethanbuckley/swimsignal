# River water temperature: replay against EA sensors (exploratory; stated before its requests, 27 October 2026)

This is an exploratory check of the river estimate in #418 against continuous Environment Agency (EA) water-temperature sensors. It decides nothing.
- The model, the bridge and every frozen rule in `docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md` stay as they are.
- Nothing is refitted to these data.
- The river verdict stays the one scored on 27 October.
- This file is written and committed before any sensor reading is requested. Nothing in it is changed after a result is seen; a result is added below the line.

## Why

The model was trained and tested on EA spot samples (the Water Quality Archive, determinand 0076), mostly taken in the working day. Continuous sondes are a different measurement of the same water. Six such sensors ran through May–September 2025 inside three of the 62 river-spot cells whose archived forecast air amendment 3 already holds. So the deployed model can be replayed on 2025 with **no new Open-Meteo request**.

## The sensors

EA Hydrology API stations with a water-temperature measure, open for the whole of 1 May–30 September 2025, inside one of the 62 cells:

| Station | Notation | Measure | River | Cell |
|---|---|---|---|---|
| Lugg Meadows | `E02703A` | `E02703A-temp-i-subdaily-C` (15 min, unchecked) | River Lugg | 52.100, −2.700 |
| Lugwardine | `fe43947f-a0e9-49fe-9a11-5ef97f102fbd` | `…-temp-m-86400-C-qualified` (daily mean, qualified) | River Lugg | 52.100, −2.700 |
| Three Elms | `553c2147-bb82-4d86-8f0a-00b892d3c314` | `…-temp-m-86400-C-qualified` (daily mean, qualified) | Yazor Brook | 52.100, −2.700 |
| Teme at Ludlow | `E06567A` | `E06567A-temp-i-subdaily-C` (15 min, unchecked) | River Teme | 52.400, −2.700 |
| Nidd at Knaresborough Lido | `E03700A` | `E03700A-temp-i-subdaily-C` (15 min, unchecked) | River Nidd | 54.000, −1.500 |
| Nidd upstream of Harrogate WwTW | `E08559A` | `E08559A-temp-i-subdaily-C` (15 min, unchecked) | River Nidd | 54.000, −1.500 |

## Requests, capped

- One CSV request per measure to `environment.data.gov.uk/hydrology/id/measures/<measure>/readings.csv`:
  - Part A: dates 1 May to 1 October 2025;
  - Part B: 1 May 2023 to 1 October 2025, for the two qualified daily series.
- **At most 12 EA requests in all**, through a small cached client (`wt_sensor_replay.py`): network errors retried after 30 s, 2 min and 5 min, any answer other than 200 a stop.
- **No Open-Meteo request.** Part A reads amendment 3's cached archived forecast. Part B uses HadUK-Grid, already on disk.
- OGL v3. "Unchecked" readings, which the EA defines as "raw input data that has not been inspected manually", are kept and labelled. "Suspect", "Missing" and "Rejected" are dropped.

## What is compared

**Days.** London calendar days, 1 May–30 September 2025 (Part B also 2023–24).
- 15-minute series: a day counts with at least 87 of its 96 readings, as the daily mean of those readings. Also reported, deciding nothing: the mean over 10:00–16:00 London time, closer to when spot samples are taken.
- Daily series: the EA's own daily mean, qualified.

**Part A: replay of the deployed estimate.**
- `water_temp.estimate` as #418 ships it: `data/processed/water_temp_model.json`, the bridge and the 30-day rule.
- **Air input:** the hourly archived forecast for the station's cell, from amendment 3's cache (`histforecast_hist2025_*.json`, Historical Forecast API, 24 April–30 September 2025).
- **Catchment:** `upstream_km` at the station, by the test's rule.
- **Elevation:** that cache's elevation for the cell.
- **Scored:** the unrounded estimate against the observed daily mean. Also reported: the rounded figure the page shows, and the share of days within 2 °C.
- **Held out by time only.** The deployed model was trained on 2000–2022 spot samples, which may include these rivers. 2025 is outside its training years.

**Part B: held out by river, HadUK air.**
- #414's fold model whose test fold holds the station's river group: the named river, found by #414's own rule (`wt_score.cmd_groups`: the link within 250 m, its name, else the first named link downstream).
- Refitted from the committed harness on that fold's training rows (training years 2000–2022), so the river is out of fitting.
- Fed HadUK-Grid air for the station's 5 km cell, by #414's nearest-valid-cell rule, as the test was.
- Scored on 2023–2025 (Lugwardine, Three Elms) and 2025 (the sondes).
- The 7-day air and day-of-year baselines are fitted on the same training rows, as in #414.

## Reported, deciding nothing

Per station and pooled:
- RMSE, bias, 90th-percentile absolute error, days;
- the share within 2 °C;
- by month;
- Part B's baselines.

There are no pass or fail rules. Daily readings are correlated, and six sensors on three rivers say nothing firm about rivers in general.

## What this cannot show

- **Not the live input.** The replay's "today" is archived analysis air, not a live forecast for today. The live site feeds today's forecast, which neither check validates. A model change at Open-Meteo since 2025 would not show here.
- **Not a spot reading.** A sonde's daily mean is not a swimmer's afternoon reading at the spot. A sensor 0–10 km from a spot is not the spot.
- **Not independent of the training rivers** in Part A.
- **Unchecked data.** Four of the six series are unchecked (raw) readings.

---

## Run log and results

### Fetch, 27 October 2026, 22:35 UTC, and an amendment before any score

**Requests.** 8 EA requests, all HTTP 200: the 6 stated readings requests, and 2 `readings.csv?latest` requests made after the first 6 to see where the qualified series end. No Open-Meteo request.

**What came back:**
- **The four sondes:**
  - Lugg Meadows: 3,579 readings, hourly;
  - Teme at Ludlow: 3,681, hourly;
  - Nidd at Knaresborough Lido: 7,382, every 30 minutes;
  - Nidd upstream of Harrogate WwTW: 6,967, every 30 minutes.
  - Every reading is "Unchecked".
- **The two qualified daily series** (Lugwardine on the River Lugg, Three Elms on Yazor Brook) returned **no readings** for 1 May 2023–1 October 2025, and none at all from `?latest`. Their daily-mean temperature measures exist in the station list but have no published readings. So **Part B's 2023–2025 long-record arm cannot run**. Part B runs on the four sondes for 2025 only.

**Amendment 1, before any score.** The statement's day rule ("at least 87 of its 96 readings") assumed 15-minute series. None of the four is 15-minute. The rule becomes: a day counts with at least 90% of its expected readings at the series' own interval (the most common step), rounded up. That is 87 of 96 at 15 minutes (as stated), 44 of 48 at 30 minutes, and 22 of 24 hourly. Nothing else changes.

### Results

(Added after the one scoring run.)
