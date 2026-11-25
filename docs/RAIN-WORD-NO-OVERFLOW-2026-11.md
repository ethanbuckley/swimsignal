# A rain word where no overflow is upstream: one frozen read of the winter reserve

Statement written 25 November 2026 against main `7b704b8e`, and pushed **before any result in the reserve half of
the winter samples was read or joined to rain**. Project ID: RAIN-WORD. Owner: the Claude session that took rank 2
of the [next research shortlist](NEXT-RESEARCH-SHORTLIST-2026-11.md). It uses the reserve that
[RIVER-WINTER](RIVER-WINTER-READ-2026-11.md) sealed and changes none of its rules, results or files, nor any of
[RIVER-UNSEEN](RIVER-UNSEEN-PROTOCOL-2026-11.md)'s.

Nothing on the site, in a frozen file, in an active window or in the 2027 primary evaluation changes because of
this statement. What a pass leads to is fixed below.

## Why this, why now

- 15 listed river spots have no monitored overflow found upstream: upland becks and gorges such as Janet's Foss,
  Tarr Steps and Padley Gorge (live `spots-lite.json`, 25 November 2026 13:34 UTC). Their level reads "No monitored
  overflow found upstream" every day in every weather. The page gives the rain in the 48 hours to midday as a
  figure (DESIGN, 3 and 11 October 2026). It does not say whether that is a lot for the place.
- Rain alone already ordered days at points like these, twice, on samples no model here had seen when they were
  scored: in summer at 23 monitoring points (RIVER-UNSEEN's side set) and in winter at 12 (RIVER-WINTER's read half).
  Neither was a pass test of a rain figure. The reserve half of the winters holds the same kind of rows, unopened.
- The shortlist fixed the test and the kill rule on 24 November: freeze a rain-only word and score it once on the
  reserve's no-overflow rows; drop it if the reserve interval is not wholly above 0.15, or if no wording avoids
  implying a level.

## What was known when this was written

- RIVER-WINTER's read half at the no-overflow points (1,122 rows, 12 points, 8 with 15 or more): rain in 48 hours
  alone 0.458 (0.326 to 0.521) with month means removed, 0.439 raw. Production with exposure 0: 0.424 (0.289 to
  0.499). 45.5% of results over 900, median 740 per 100 ml, production's mean chance 8.7%.
- RIVER-UNSEEN's summer side set (2,071 rows, 23 points): the candidate (rain and season) 0.309 (0.263 to 0.375);
  rain alone 0.321, reported without an interval.
- Counts of the reserve's rows at these points, from every column of the sealed table except the result
  (`winter_read.py counts`): 1,028 rows, 13 points, 10 with 15 or more (1,024 rows at them). By winter: 2013 325,
  2015 435, 2017 86, 2019 81, 2021 63, 2023 38. None falls before 1 February 2012.
- The 48-hour rain at the 23 points' cells (ERA5-Land) and at the 15 spots' cells (Open-Meteo's archive), rain
  only, to see whether thirds could tie at zero. They do not: 12% to 21% of days are dry, and the lower cut-point is
  0.4 mm or more everywhere.
- `rain_word_read.py selftest` rebuilds two sets of rows already read with this read's builder and matches them on
  every input: RIVER-WINTER's 1,122 read-half rows and RIVER-UNSEEN's 2,071 summer side-set rows (largest
  difference 0 in rain, exposure and count).
- The points: 18 of 23 in the South West, mostly short coastal streams in Cornwall and Devon, plus the River Brock
  (Lancashire), the Alde and Deben (Suffolk), the Ebble (Wiltshire), and two Hastings park streams and Prittle Brook
  (Thames). Each point's system is RIVER-UNSEEN's (`docs/river-unseen/systems.csv`). They are not upland becks.
- No reserve result, by me or by any script here. RIVER-WINTER's `load_half` refuses the reserve.

## The figure: the word

For a place and a day, the rain in the 48 hours before is compared with that place's own usual:

- **Less rain than usual** when the rain, to 0.1 mm, is under the place's lower cut-point.
- **More rain than usual** when it is over the upper cut-point.
- **About usual** otherwise.

The cut-points are one third and two thirds of the place's own 48-hour rain (to 12:00 local, as the page's rain) on
October to April days, as #709 made thirds of a spot's own figure. A place with fewer than 300 such days, or
cut-points closer than 1.0 mm, gets no word.

**For this read**, each monitoring point's cut-points come from its ERA5-Land cell on the October to April days of
the even winters (1 February 2012 to 30 April 2022): rain only, from days outside the reserve's winters, as the live
cut-points come from days before the ones they judge. They are frozen in `docs/rain-word/test_cutpoints.json`,
SHA-256 `48628695…` (all 23 points have them; three cells have rain from 2019 only, so 425 days). The sample's rain
is the row's own: ERA5-Land, the 48 hours before the sample time, as both earlier reads used. Coded −1, 0 and 1.

The word sets no level, no colour and no chance. It says something about the rain.

## Rows

The reserve half's rows (odd winters 2013 to 2023) at RIVER-UNSEEN's 23 points with no monitored overflow upstream
(`build_rows.which_points(..., "no_overflow")`), under RIVER-WINTER's row rules unchanged: river water, purposes
MS, MP, MU, MN, PI or PN, October to April, held-out span 2012 to 2022. `rain_word_read.py build` reads results for
those rows' ids only. No result of a reserve row at a point with an overflow upstream is read, now or later by this
project; those rows stay sealed for RIVER-WINTER's own later use.

Rows are built by `build_rows.rows_without_overflows`, unchanged (the selftest above). A row with no full rain
window is dropped and counted.

## Conditions, both needed for a pass

Fixed before the read. Seed 20261125.

1. **Raw order.** The mean, over points with 15 or more rows, of the within-point Spearman correlation between the
   word and the measured log10 count. Pass: the 95% interval lies wholly above **0.15**. This is the shortlist's
   rule.
2. **Order beyond the calendar.** The same, after taking off, from both the word and the log10 count, the point's
   own mean for that calendar month (point-months with fewer than 3 rows left out). Pass: the 95% interval lies
   wholly above **0.15**.

Condition 2 is RIVER-WINTER's guard: a word that only knew wet December from dry April would pass condition 1 and
tell a swimmer nothing about which day to pick. Adding it can only make a pass harder.

A point is scored when it has 15 or more rows and its word and count each take more than one value (RIVER-UNSEEN's
`rho_points`). The interval: 2,000 resamples of river-system winters drawn with replacement, as RIVER-WINTER drew
them; a drawn system-winter brings all its rows. Month means are recomputed inside each resample.

**Not run** if, after the builder's drops, fewer than 8 points have 15 or more rows or fewer than 700 rows remain.
The reserve is then not opened again to make up numbers.

## Reported, deciding nothing

- Rain in 48 hours as a number (the continuous figure the word is cut from), and production's river chance as
  deployed (`ecoli_model.json`, `7daf7c8e…`) with exposure 0: raw and month-removed, with intervals for the
  month-removed figures. The word less rain alone, as a paired difference. A three-way word loses some order; this
  says how much.
- Level, by word: the share of results over 900 and the median count on "less", "about" and "more" days, beside
  production's mean chance. These show whether a word could be misread as a level. They do not decide anything.
- By month group, by era (winters to 2017, from 2019), by catchment band, each system left out in turn, and each
  point's own correlation.
- **Development, on rows already read:** the same two conditions for the word on RIVER-WINTER's read half
  (winter cut-points as above), and on RIVER-UNSEEN's summer side set with summer cut-points (May to September days
  of 2012 to 2022 at the same cells, in the same file). Both sets of results were read on 16 and 24 November, so
  these are development figures, said as such.

## What each outcome leads to

Ethan has said, in this project's brief, that the wording and the build are for this project to decide ("Everything else is
yours to decide"), apart from fixed rules.

- **Both pass.** The word goes on the site, small, at the 15 river spots where no monitored overflow is found
  upstream, as below. Its wording is marked against `docs/DESIGN.md`. One pull request, not merged by this project.
- **Condition 1 passes, condition 2 fails.** The order is mostly the calendar. No word is shown. The record says
  so; a month-relative word would need new unseen winter samples, since this reserve is then spent for this purpose.
- **Condition 1 fails.** No word is shown. The record says what the rain evidence does support (the two earlier
  continuous figures, as figures on monitoring points) and archives "a rain word at no-overflow spots" until winter
  samples at a listed upland beck exist.
- **Too few rows.** Recorded as not run.

### The site word, fixed now in case of a pass

- **Where:** a listed river spot with no monitored overflow found upstream (the forecast's own count of overflows
  is 0) and its own cut-points. Not at a lake, a clicked point, or a spot with any overflow upstream.
- **When:** today's day only, as the winter river line, because the read is at lead 0.
- **Rain:** the build's own `rain_48h_mm` for today, to midday, the figure the page already shows. The build already
  fetches rain for each listed spot's own cell; no new request.
- **Cut-points:** per spot, from Open-Meteo's archive rain at the spot's cell (the read-only cache made for #709 and
  #736: `dipcast-scratch/river-usual/cache`, 2023 to 2026), 48 hours to 12:00 local. Winter: October to April days,
  1 February 2023 to 11 November 2026. Summer: May to September days of 2023 to 2026. Frozen in
  `data/processed/rain_usual.v1.json` with its SHA-256 in code, as `river_usual.py` does.
- **Summer:** the word shows May to September only if the development figure for the word on the summer side set
  has a raw interval wholly above 0.15. Those samples had not been seen by any model when RIVER-UNSEEN scored them,
  but this word's figure on them is computed after; the page says the summer evidence is weaker.
- **Words** (in view, under the no-overflow line, before "Other risks apply"):
  - "More rain than usual here in the last two days." / "About the usual rain here in the last two days." /
    "Less rain than usual here in the last two days."
  - Then, smaller, what it rests on: "At river sampling points with no overflow upstream, E. coli tended to be
    higher after more rain. That held on past winter samples kept back for this test[, and on summer samples]. Those
    points were Environment Agency monitoring points, not swim spots. This is not a level."
- **Not:** a level, a colour, a percentage, "safe", "clean", an alert, the shared picture, the list rows or the
  planner. "No monitored overflow found upstream" and "Other risks apply" stay as they are.

## Limits, stated before the read

- Monitoring points, not swim spots, and not the kind of place the 15 spots are: mostly small coastal streams in
  the South West, where the spots are upland becks in the Pennines, the Lakes, Dartmoor and Exmoor.
- Reanalysis rain to the sample time, at lead 0. The page's rain for today is partly a forecast for the morning.
- The cut-points for the test and for the site come from different rain sources (ERA5-Land and Open-Meteo's
  archive). Each place is compared only with its own source.
- Thirds of rain treat a place's days as equal in kind. A dry spell after a very wet month reads "less rain" all
  the same.
- Few independent rivers: the interval is over river-system winters, and most systems hold one or two points.
- A pass supports an order within a place: on wetter days, counts tended to be higher. It does not support a count,
  a chance or "safe".

## How to rerun

```
export DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<scratch cache: ERA5-Land cells of the 23 points, 2012-22>
export PYTHONPATH=src
python scripts/rain_word/rain_word_read.py cuts docs/rain-word/test_cutpoints.json
python scripts/rain_word/rain_word_read.py selftest <sealed samples.parquet> <RIVER-WINTER read-half no-overflow rows> <RIVER-UNSEEN summer side-set rows>
python scripts/rain_word/rain_word_read.py build <sealed samples.parquet> <private out dir>
python scripts/rain_word/rain_word_read.py read <private out dir>
```

`build` and `read` refuse unless this file, the scripts and the cut-points file are committed and the hashes named
here match. `read` writes `docs/rain-word/result.json` and appends to `docs/rain-word/reads.jsonl` whatever it shows.
Built rows hold results and stay out of git, in a scratch folder; `result.json` records their SHA-256. Sealed table:
`95ca8c9f…`.
