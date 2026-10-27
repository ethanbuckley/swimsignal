# A lake water-temperature model: the second test, stated before any lake model is fitted or scored

Written 27 October 2026. **Approved by Ethan on 27 October 2026**, in these words: "okay rivers go ahead now and the
lets do more tests for lakes". This document fixes the test before any lake model is fitted or scored. It was
committed before the harness that fits and scores. Results go below the line at the end. Nothing above the line
changes after a result is seen. If something has to change after a result, both results are kept and the change is
stated in the run log.

The first test is `docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md` (draft PR #414). This test reuses its rows, water
bodies, folds, HadUK-Grid air and Open-Meteo bridge. Where this document says nothing, the first test's rule holds.

## Why a second test

The first test was scored once, on 27 October at 18:28 UTC. Lakes failed:

- RMSE 1.82 °C against a limit of 1.5 °C.
- The gain over the 7-day air baseline was 0.10 °C, 95% interval [−0.02, 0.23]. So it did not reliably beat "a
  straight line on the last 7 days of air" (1.92 °C).
- Lakes read about 1 °C too cold in May (bias −1.04 °C). The 11 large WFD lakes (1 km² and over) were worse than
  both baselines.
- The first statement had guessed this. A lake's surface lags the air by weeks, and that model knew no depth and no
  air older than 30 days.

So this test asks one thing: with a longer air memory and a depth figure, can a lake model be good enough to show a
swimmer, on a season nobody has scored?

## What is already seen, and how this test avoids tuning to it

**Seen.** The 2023–25 lake test rows of the first test were scored. Their aggregate errors are in that document:
by year, month, fold and lake-size group. Every choice below was made by someone who has read those results. The
choice to add longer air windows and depth comes straight from them. That cannot be undone. It is a reason to judge
on new data, not a licence to tune on the old.

**Not seen.** May to September **2026**. No 2026 lake temperature has been fitted, scored, summarised or plotted by
anyone in this project.

**Rule.** The verdict is decided on May–September 2026 only. The 2023–25 lake rows are scored again, but only as a
secondary report that decides nothing. Every window and setting below is either fixed here or chosen inside the
training rows of each fold by the rule written here. None is chosen by looking at a 2026 or a 2023–25 score.

**2026 rows checked before writing this** (27 October, 18:40 UTC, 13 requests, `scripts/lake_temperature_eval/
lt_fetch.py ea2026`, into `~/Documents/GitHub/swimsignal-private/water-temperature/ea-2026/`). Fresh water
(`2AZZ,2GZZ`), determinand 0076, May to September 2026, POST, `dateTo` the first of the next month (exclusive), a 204
as an empty page. All 13 answered 200, 9.8 MB, 25,233 rows. Counted by material and month, with no value read:

| month (2026) | lake material rows | river material rows |
|---|---|---|
| May | 266 | 5,849 |
| June | 322 | 4,844 |
| July | 342 | 4,855 |
| August | 294 | 4,146 |
| September | 272 | 4,043 |

Lake material: **1,473 point-days at 297 points.** That is before the point-type rule, the water bodies and the air
rule. The gate below needs 30 water bodies and 300 rows. *Inferred:* 2026 will clear it with room. The exact counts go
in the run log before any score. September 2026 may still be filling in: the archive adds samples late. Whatever the
archive held on 27 October is the test set. It is not fetched again.

**If 2026 fails the gate** (fewer than 30 held-out lake water bodies or 300 rows after every rule): the verdict is
"too few to judge" and lakes cannot pass. There is **no fallback to 2023–25** for the verdict, because those rows are
seen. The next chance would be May–September 2027. The secondary 2023–25 report is still written.

## Data

Everything is reused from the first test unless listed here. All of it is free and open.

- **Water temperature.** EA Water Quality Archive, determinand 0076 (Open Government Licence v3.0). The first test's
  cache for 2000–2025 (`water-temperature/ea/`, not fetched again) plus the 13 pages for 2026 above (`ea-2026/`).
- **Training air.** Met Office HadUK-Grid 5 km daily mean `tas` (OGL v3), the 156 files Ethan downloaded, April to
  September, 2000–2025. Read through the first test's `work/haduk_series.npz` and `work/haduk_points.parquet`.
- **2023–25 test air** (secondary). ERA5-Land through Open-Meteo, the first test's cache (`open-meteo/`). No new call.
- **2026 test air** (primary). ERA5-Land daily mean (`temperature_2m_mean`, `models=era5_land`,
  `timezone=Europe/London`) through Open-Meteo's archive API, 1 April to 30 September 2026, for the 0.1° cells of the
  lake points with a 2026 row. New requests, capped below. Cached in `water-temperature/open-meteo-2026/`.
- **The bridge**, unchanged from the first test: `HadUK = 0.5013 + 0.9792 × OpenMeteo` (2018 daily air only, no water
  temperature; c = 0.5012729716522162, d = 0.9791684691913549 in its `features_info.json`). The 2023–25 and 2026
  Open-Meteo daily values pass through it before any window is taken.
- **Lake area.** EA WFD lake water bodies, cycle 3 (`data/processed/lakes.parquet`), as before.
- **Lake depth.** HydroLAKES v1.0 mean depth (`Depth_avg`, metres), as already copied for the WFD lakes in
  `data/raw/lake_residence.csv` (`hl_depth_avg_m`; 282 of the 564 WFD lakes; checked field by field against the
  official `HydroLAKES_points_v10_shp.zip` on 13 October, `docs/LAKE-RESIDENCE-TEST-2026-10.md`). No new download.
  - Licence, read on HydroSHEDS' HydroLAKES page (hydrosheds.org/products/hydrolakes) on 27 October 2026: "The
    HydroLAKES database is licensed under a Creative Commons Attribution (CC-BY) 4.0 International License." The site
    already credits it on its terms page.
  - **It is modelled, not measured,** for most British lakes (volume from the lake's area and the slope of the land
    around it, Messager et al. 2016). It is a proxy. It covers lakes of 10 ha and more.
  - Measured depths were looked for in the lake residence work (13 October). The UK Lakes Portal's depth pages state
    no licence, so they are not used. Wikidata (CC0) holds depth for two of these lakes. The EA's WFD typology gives
    only a depth class and was not reachable then. Nothing more open was found.
- **Elevation.** Open-Meteo's cell elevation, as before. New 2026 cells take it from their 2026 answer.

## Rows and water bodies

- Rows: the first test's rules (`wt_protocol.clean_rows`) on all pages, 2000–2026 together. One row per point and
  local date, May to September. A point's type is the type most of its rows have, now counting 2026 rows too. Only
  points of type **lake** enter this test. A few points may change type against the first test; the run log counts
  them.
- Water bodies: the first test's lake rules (`wt_score.py groups`). In or within 100 m of a WFD polygon: that lake.
  Else within 250 m of an OS Open Rivers lake link: that link's connected lake, with no area. Else a water of its own.
- Folds: `int(sha256(water id), 16) % 5`, as before. A water keeps the fold it had in the first test.
- **Hold-out.** Fold k's model is trained on lake rows of the waters in the other four folds and predicts the test
  rows of the waters in fold k. No water's rows are in both the training and the test set of one model, in any year.

## The two arms

| arm | training rows (HadUK air) | test rows | decides |
|---|---|---|---|
| **primary** | lake rows, May–Sep **2000–2025** | lake rows, May–Sep **2026**, bridged Open-Meteo air | **yes** |
| secondary | lake rows, May–Sep 2000–2022 | lake rows, May–Sep 2023–25, bridged Open-Meteo air | no (seen) |

Why the primary trains on 2023–25 too: training on rows is not tuning to them, and those seasons are the closest to
2026. The 2026 rows are never in any training set.

## Inputs

For a lake row at point p on local date d in year y. The air series is the daily mean at p's air cell (HadUK 5 km
cell in training; the bridged Open-Meteo 0.1° cell in testing), from 1 April of y.

| input | definition | why it is there |
|---|---|---|
| `a1`, `a7`, `a14`, `a30` | mean of the daily means on d and the 0, 6, 13, 29 days before | short memory, as in the first test, plus a two-week step |
| `a_apr` | mean of the daily means from 1 April to d | the longest memory the files allow: the season's warmth so far |
| `e_tau` | exponentially weighted mean from 1 April to d: weights (1 − α)^i for the day i days before d, α = 1 − exp(−1/τ), divided by the sum of the weights used | a lag that fades smoothly; τ (days) is chosen inside training data (below) |
| day of year | sine and cosine of 2π × day / 365.25 | sun and season beyond what the air says |
| lake area | log10 of the WFD polygon's km²; missing if unmatched | bigger lakes hold more heat and mix differently |
| lake depth | log10 of HydroLAKES mean depth in metres; missing if none | depth sets how much heat the lake stores, so how far its surface lags the air |
| elevation | Open-Meteo cell elevation, metres | upland lakes run colder than lowland ones at the same cell air |

A row needs its cell's air on every day from 1 April to d. Rows without it are dropped and counted.

**Why no 60-day mean.** The HadUK files on disk run from April to September. A 60-day mean on 1 May needs early
March. Getting March means Ethan downloading more HadUK files with his own CEDA account. So the long memories here
are `a_apr` and `e_tau`, both starting on 1 April. In May they are cut short. That is a known weakness, and it falls
exactly where the first test was worst (May). It is stated now so that a May failure is not a surprise.

**τ grid:** 5, 10, 15, 20, 30, 45, 60 and 90 days.

## Choosing windows inside training data only

In each outer fold k, using only fold k's training rows (the other four folds' waters, the arm's training years):

- **Inner splits:** each of the four training folds in turn is held out; a straight line is fitted on the other three
  and predicts it. The pooled RMSE over the four held-out folds is the window's inner score.
- **The third baseline's window** is the one with the lowest inner score among `a14`, `a30`, `a_apr` and `e_tau` for
  every τ in the grid. A tie goes to the earlier one in that list.
- **The candidate's τ** is the one with the lowest inner score among the `e_tau` windows alone. The candidate gets
  that one `e_tau` as an input.
- The chosen windows and their inner scores are written to the score file for each fold and arm.

No 2026 or 2023–25 test row enters any of this.

## The candidate

Fitted per outer fold on that fold's lake training rows only. **[choice]** Lake rows only: in the first test one model
served all types, and river rows outnumbered lake rows about 50 to 1.

1. **Stage 1: the third baseline itself.** `T = a + b × w`, w the window chosen above, ordinary least squares.
2. **Stage 2: a boosted correction** of the stage 1 residual. scikit-learn `HistGradientBoostingRegressor` on `a1`,
   `a7`, `a14`, `a30`, `a_apr`, the chosen `e_tau`, day-of-year sine and cosine, lake area, lake depth and elevation.
   Missing values handled natively. An input with no value at all in a fold's training rows is left out of that fold's
   fit. Settings as the first test, fixed now and never tuned: squared error, learning rate 0.05, 400 iterations, at
   most 31 leaves, at least 100 rows a leaf, L2 1.0, no early stopping, `random_state` 0.

The estimate is stage 1 plus stage 2. No Mohseni curve: in the first test it hit its bound in every fold and added
nothing over a straight line.

## The baselines

All fitted on the same lake training rows as the candidate, per fold.

1. **Day of year.** The first test's rule: mean training water temperature per day of year, over a centred 31-day
   window.
2. **7-day air.** `T = a + b × a7`, least squares.
3. **The best simple longer window.** `T = a + b × w`, least squares, w chosen inside training data as above.

## Scores and the verdict

On the 2026 test rows of all five folds together:

- RMSE of the candidate and each baseline, in °C. Each row counts once.
- Gain over a baseline = RMSE(baseline) − RMSE(candidate).
- 95% interval of each gain: 2,000 resamples of the held-out water bodies with replacement, each bringing all its
  rows; 2.5th and 97.5th percentiles. numpy `default_rng(20261027)`.
- P90: the 90th percentile of the candidate's absolute error.

**Lakes pass only if all six hold:**

1. the gate: at least **30** held-out lake water bodies and **300** test rows in 2026;
2. the lower end of the gain over day of year is above 0;
3. the lower end of the gain over 7-day air is above 0;
4. the lower end of the gain over the best longer window is above 0;
5. RMSE at most **1.5 °C**;
6. P90 at most **2.5 °C**.

If the gate fails, the label is "too few to judge". Otherwise "pass" or "fail".

## Why 1.5 °C, and why 2.5 °C for 9 errors in 10

The first statement gave 1.5 °C for lakes with no reason. Ethan asked for one. Here it is, argued from what a swimmer
would read. The number is not taken from the first test's 1.82 °C. It happens to be the same number as before, and
that is stated plainly so nobody has to wonder.

**What the page would promise.** The first test's display rule is "About N °C (estimated, typically within X °C)",
with X the held-out RMSE rounded up to the next 0.5 °C. So the swimmer is handed a range N ± X, 2X wide.

**What a swimmer does with a water temperature.** They decide how cold it will feel, whether to wear a wetsuit, and
how long to stay in. The Outdoor Swimming Society's cold-water guide gives the bands swimmers use (read on
27 October 2026 at outdoorswimmingsociety.com/cold-water-feels-temperature-guide): 0–6 "Baltic", 6–11 "Freezing",
12–16 "Fresh", 17–20 "Summer swimming", 21 and over "Warm". The page itself says the bands are anecdotal, not
scientific. The site shows a whole number of degrees, so 12–16 covers readings from 11.5 to 16.5 (5 °C wide) and
17–20 covers 16.5 to 20.5 (**4 °C wide**). Those two are the bands a lake spends May to September in.

**The argument for the RMSE limit.** An estimate is worth showing if its stated range is narrower than the narrowest
band a lake swimmer meets in the season. Then the estimate points at one band, or at most two neighbours, never three.
That needs 2X < 4 °C, so X < 2 °C. X moves in steps of 0.5 °C, so X ≤ 1.5 °C, which is **RMSE ≤ 1.5 °C**. At 2.0 °C
the range would be as wide as the whole "Summer swimming" band and would not tell the swimmer which side of it they
are on.

**The argument for the 90% limit.** "Typically" covers most readings, not all. If errors were normally spread, an
RMSE of 1.5 °C would put 9 in 10 within 1.645 × 1.5 = 2.47 °C. So **P90 ≤ 2.5 °C** says the tail is no heavier than
the "typically within 1.5 °C" promise implies. In band terms: from the middle of the 4 °C "Summer swimming" band, an
error under 2.5 °C stays in that band or the next one. A heavier tail (as in the first test's lakes) would mean the
1-in-10 miss sends a swimmer two bands off.

**Stated now:** by this same argument the river limit of 2.0 °C (first test) is loose: "typically within 2 °C" is a
4 °C range. That is a matter for the river display, not for this test, and it is not changed here.

## Reported, deciding nothing

For the candidate and all three baselines: rows, waters, RMSE, bias, mean absolute error, P90. Gains with intervals
where there are at least 30 waters.

- **Large lakes:** WFD area 1 km² and over.
- **Reservoirs:** the WFD lake name or the sampling point's label contains "reservoir" (case ignored).
- **Small ponds:** WFD area under 0.1 km² (10 ha), and separately points matched to no WFD polygon.
- Lakes with a HydroLAKES depth, and without.
- **May against June to September**, and every month.
- By fold, and the windows chosen in each fold.
- The secondary arm (2023–25, seen), the same tables.
- The primary arm with un-bridged Open-Meteo air.
- Rows dropped at each rule.

## Caps, sized before any request

**EA archive:** done (13 requests, above). Cap was 40 requests, 12 pages a month, 200 MB. No more EA requests.

**Open-Meteo, 2026 only.** Cells: the 0.1° cells of lake points with a kept 2026 row. *Inferred* from 297 lake points:
about 150 to 250 cells. One request per 25 cells, 1 April to 30 September 2026 (183 days): weight 1.307 a cell
(`om_weight(n, 183, 1)`), so about 200 to 330 weighted calls.
- **Caps:** at most **600** weighted calls for this test; requests 25 s apart, one in flight; at most 9,500 in a UTC
  day and 4,700 in a rolling hour **counted over this fetch's log and the first test's log together** (one Mac, one
  free quota); `archive-api.open-meteo.com` only.
- Stop rules as the first test: a network error is tried again after 30 s, 2 min and 5 min, then the fetch stops; an
  answer that is not 200, or a body that is not JSON, stops it at once.
- Wall time: about 10 requests × 25 s, under 5 minutes.
- If a day of 2026 comes back empty (ERA5-Land lags by days), rows that need it are dropped and counted. No request is
  repeated for it.
- No other host. No other new request.

**Compute.** Rows, water bodies, features and the score run under the group's `heavy-run.lock`
(`scripts/lake_temperature_eval/run_locked.sh`). If another session holds it, the stage waits. It is never broken.

## What follows

- **Nothing on the live site changes in this PR.**
- **If lakes pass:** still nothing is shown. A lake display is a separate draft PR and Ethan's decision. It would need
  the same check as rivers first: forecast-API air against ERA5-Land at the spot cells. It would say "typically within
  X °C" with X the 2026 RMSE rounded up to the next 0.5 °C.
- **If lakes fail:** lake spots get no estimate. This PR records which conditions failed. What a third test would need
  is written down, not run: HadUK March files (a real 60-day memory), and measured depths.
- **Too few to judge:** as a fail, and the next chance is May–September 2027.

## What is expected, stated now

Guesses, not results.

- Candidate RMSE on 2026: about 1.5 to 1.9 °C. More likely than not to miss 1.5 °C.
- The longer window will beat 7-day air for lakes. *Inferred:* `e_tau` with τ around 15 to 30 days, or `a_apr`, will be
  chosen.
- The candidate's gain over that third baseline will be small, about 0.05 to 0.2 °C, and its interval may well reach
  below 0. That alone could fail the test.
- May will stay the worst month, because the long windows are cut at 1 April.
- Large lakes will improve most from depth, but they are few (about 10 to 15 waters), so their figures will be noisy.

## Order of work

1. This statement, committed before any lake fit or score. (Done before it: the 2026 count above.)
2. The harness and its synthetic tests, committed.
3. Rows and water bodies over 2000–2026; the Open-Meteo plan; the 2026 Open-Meteo fetch. Counts only.
4. The features file. Its SHA-256 committed here **before any model is fitted or scored**. The scoring code refuses any
   other file.
5. One scoring run, offline, from the committed code. Results below the line.

Harness: `scripts/lake_temperature_eval/` (`lt_fetch.py`, `lt_protocol.py`, `lt_score.py`, `run_locked.sh`). Tests:
`tests/test_lake_temperature_eval.py`, synthetic data only.

## Run log (written before any score)

*(empty)*

---

## Results

*(none yet)*
