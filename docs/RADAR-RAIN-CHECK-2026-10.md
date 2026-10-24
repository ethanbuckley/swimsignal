# Met Office radar rain against gauges, and what wrong rain forecasts cost: the test, stated before any run

Written 24 October 2026. Nothing has been run. No radar, gauge or forecast rain value has been read for this test,
and no score of any kind has been computed. Results go below the line at the end. Nothing above it changes after a
result is seen.

## Why

`docs/MET-OFFICE-DATA-2026-10.md` found a free source the project did not use: the Met Office's UK radar rain rate on
AWS, a 1 km composite every 15 minutes, kept for about two years. `scripts/fetch_met_office_radar.py` keeps it as
hourly rain per SwimSignal rain cell (0.1°), in `data/raw/met_office_radar/`. The backfill from 21 November 2024
started on 24 October 2026.

Two things are not known, and the second depends on the first.
- **Is the radar a fair record of the rain that fell?** It is a raw radar estimate. Whether the Met Office corrects it
  with gauges is not stated. On the one day checked (6 February 2026), the Lake District cell (54.4, −2.9) read 2.77
  times the forecast. Before radar is used as truth for anything, it is checked against rain gauges.
- **How much do wrong rain forecasts cost the spill forecast?** The spill model is fitted on ERA5-Land rain and fed
  Open-Meteo's forecast rain. When it misses a spill, the rain forecast may have been wrong, or the model may have
  been wrong with the right rain. If rain error is the main limit, better rain (radar for "right now", the ensemble
  band) is where the work goes. If the model is the main limit, the work goes into the model.

There are three questions. Question 1 decides whether radar can serve as truth in Questions 2 and 3. Nothing here
changes the site or the model.

## The data

**Radar.** `data/raw/met_office_radar/radar_<cell>_<YYYY-MM>.parquet`: hourly rain per cell (hour-ending, UTC), the
mean over the radar pixels whose centre lies in the cell, and `coverage`, the share of that hour's pixel samples with
data. An hour counts only when `coverage` is at least 0.9. It is written by the fetcher at commit 8073988, from the
AWS Open Data bucket "Met Office UK Radar Observations" (CC BY-SA 4.0). The radar results stay in this repo's docs as
summary figures only. No radar-derived series is published.

**Gauges.** The Environment Agency's Hydrology API (`environment.data.gov.uk/hydrology`, Open Government Licence),
the 15-minute rainfall totals ("15min total Rainfall (mm)", `-rainfall-t-900-mm-qualified`) of every rain gauge
whose position falls in a radar cell. On 24 October 2026 the station list gave 995 rainfall stations, 302 of them in
244 of the 499 radar cells. Only the station list was read. Readings flagged Suspect or Missing are dropped. The
15-minute totals are summed to hours ending on the hour, UTC, as the radar and forecast are stamped. An hour counts
only with all four quarter-hours present.

**Forecast rain.** Open-Meteo's Previous Runs API, as cached for the evaluations
(`cache/rain/leads_<cell>_<year>.parquet`, leads 0 to 4). It runs to 13 September 2026. 394 cells have 2025; 206
cells have 2024 and 2026.

**Reanalysis.** ERA5-Land, as cached for training (`cache/rain/archive_*` and `cache/rain_nine/archive_*`), where a
cell has it.

**Days.** UTC days, built with `features.daily_rain_features`: a day with fewer than 20 valid hours
(`MIN_HOURS_PER_DAY`) has no total.

**Window.** Questions 1 and 2: 1 December 2024 to 13 September 2026 (the lead cache's last day), so all three
sources cover the same days. Question 1 also reports, separately, 14 September to 23 October 2026, radar against
gauges only. Question 3: calendar 2025.

## Question 1: radar against gauges

Each gauge is set against its cell's radar on each day both have. This compares a point to a 10 km cell average, so
agreement is understated. The same holds for ERA5-Land and the forecast in Question 2, so the comparison between
sources is fair even where the absolute figures are low.

**Radar is fit to serve as truth if all three hold:**
1. **Totals.** Over all gauge-days pooled, total radar rain divided by total gauge rain is between 0.80 and 1.25.
2. **Day-to-day agreement.** Across gauges with at least 200 valid days, the median Spearman correlation of daily
   totals is at least 0.75.
3. **Wet and dry days.** On gauge days of 1 mm or more, the radar reads 1 mm or more on at least 80% of them. On gauge
   days under 0.2 mm, the radar reads under 1 mm on at least 90% of them.

**Reported whatever the verdict:** the three figures by season (December to February, and so on), for gauges in the
North West region (cells north of 53.3° and west of −2.0°) against the rest, and per gauge. Also, as Question 1b,
the same three figures for ERA5-Land against the same gauges on the same days, and the mean absolute daily error of
radar and of ERA5-Land against gauges. Question 1b decides nothing. It says whether radar is closer to the gauges than
the rain the models are trained on.

**If Question 1 fails**, Questions 2 and 3 still run with radar, and every radar figure is labelled with the condition
that failed. Question 2 is then also scored against the gauges in the gauge cells, and that version is the one
reported first. Question 3's verdict is "not decided".

## Question 2: how wrong the forecast rain is, by lead

Daily totals per cell, forecast at leads 0 to 4 against radar, on cell-days where every lead and the radar have a
total. This is a description. Reported: mean absolute error, mean bias, ratio of totals, Pearson correlation, and the
share of radar days of 10 mm or more that the forecast also put at 10 mm or more, with the share of radar days under
10 mm that the forecast put at 10 mm or more. Each by lead, by season, and North West against the rest.

**Stated now, to be checked:** the error grows with lead; at lead 0 the correlation with radar is at least 0.7;
the forecast's totals are within 20% of radar's at every lead.

## Question 3: what wrong rain forecasts cost the spill forecast

`scripts/verify_leads.py`'s rows and method for 2025, with one more rain source. The production spill model
(`spill_model.pkl`, trained on United Utilities 2023 to 2025) is fed each source in turn:
- **ERA5-Land**, the rain it was trained on, as `verify_leads.py` feeds it;
- **forecast, lead k** (k = 0 to 4), as `verify_leads.py` builds it: the day and the two days before from the lead
  forecasts, the 7-day, 30-day and antecedent-index features from ERA5-Land;
- **radar**, built the same way as lead 0 with radar in place of the lead forecasts: the day and the two days before
  from radar, the longer features from ERA5-Land. This is the spill forecast with the rain known.

Rows: site-days in 2025 of the nine English companies' overflows in cells with lead forecasts and radar, covered by
the EA start/stop files (`training.site_years`), **less United Utilities**, whose 2025 the model was trained on. A
row is scored only where every source has a day total. Labels: spill days from the EA start/stop files.

Each source is scored on raw probabilities, with no lead map, since radar has none: Brier score, AUC, and the share of
spill days with a probability of 0.4 or more (the High line's threshold), with the share of dry days at 0.4 or more.
The interval for the Brier difference is a bootstrap over ISO weeks (weather is shared within a week), 2,000 draws,
seed 20261024.

**The verdict, one of three:**
- **A. Wrong rain is the main limit** if radar's Brier is below lead 1's with the 95% interval of the difference
  wholly below zero, and radar's AUC is at least 0.03 above lead 1's.
- **B. The model is the main limit** if radar's Brier is not below lead 0's: the interval of radar minus lead 0
  includes zero or lies above it.
- **C. Both matter** otherwise.

**A check on the radar arm.** The model learned rain's scale from ERA5-Land. If radar's Brier is worse than
ERA5-Land's by more than lead 0's is, the difference may be scale, not information. That is reported beside the
verdict. It does not change the verdict.

## What is expected, stated now

- **Question 1:** totals within the band, but closer to 0.8 than to 1, with radar under-reading in the hills.
  Condition 2 is the likely failure, because a point gauge and a 10 km mean differ on showery days.
- **Question 1b:** radar closer to the gauges than ERA5-Land, by mean absolute daily error.
- **Question 2:** the stated pattern holds, with the largest errors in the North West.
- **Question 3:** C. Rain error matters most at leads 3 and 4, but at lead 0 and 1 the model is the larger limit,
  because outside United Utilities the model carries offsets it never learned.

## Running

- The harness is `scripts/radar_rain_eval/`. It is committed after this file and before the run. The statement above
  the line does not change when it is added.
- The gauge fetch first, after the harness commit, into the run's scratch folder, with every request and its result
  counted. Then everything else offline from a `git archive` of the harness commit, on a frozen copy of the data
  folder whose file hashes go in the results.
- The run starts after the radar backfill has finished (to 23 October 2026), with no other evaluation, training or
  build running on this machine.

## What follows

Nothing is adopted from this test, whatever the result. It decides what is tested next:
- **Question 1 passes:** radar can be the truth in the next stated tests: observed rain for "right now" (review task
  D6) and a check of the ensemble band against rain that fell. Each gets its own statement.
- **Question 1 fails:** those tests use gauges, where there are gauges, and radar is not used as truth.
- **Verdict A:** the next work is rain: D6 first, then the ensemble band.
- **Verdict B:** the next work is the model outside United Utilities, for example option B of
  `docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md` or a nine-company refit.
- **Verdict C:** both, rain at the long leads first.

Any live use of radar changes the 2027 forecast stamp (`rain=open-meteo-forecast`, `docs/PREREGISTRATION-2027.md`
section 2) and would need a dated amendment before 1 May 2027.

## What will be reported

Whatever the verdict: every figure named above with its rows and dropped rows; the gauges used and those dropped
(too few valid days, outside a cell); requests made to the Hydrology API and their failures; run time; and the data
folder's hashes.

## Seen before writing

- The radar fetcher's one-day check in `docs/MET-OFFICE-DATA-2026-10.md` (6 February 2026, eight cells), including
  the Lake District ratio quoted above.
- The backfill log's first lines (21 November 2024 to 23 February 2025): counts of radar files read and missing, and
  one cell's total for 21 November 2024 (1.63 mm), seen while checking the files landed. Nothing was compared with it.
- The lead cache's file list and one 2026 file's span by lead (1 January to 13 September 2026).
- The Hydrology API's station list: positions, measure names, counts (995 stations; 302 in 244 radar cells). No
  readings.
- `scripts/verify_leads.py`, `features.daily_rain_features`, `training.load_rain` and `training.site_years`, read for
  method.
- The live verification page's warning table (24 October 2026), read for a separate correction.
- No score of any kind has been computed for this test.

---

## Results

Not yet run.
