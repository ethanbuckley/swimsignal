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

---

## The read, 25 November 2026: both conditions pass

Run once, at 14:38 UTC on 25 November 2026, at commit `f44527ec` (the statement as pushed). Logged in
`docs/rain-word/reads.jsonl`; every figure is in `docs/rain-word/result.json`. The builder took 1,028 reserve samples
in and gave 1,020 rows out at 12 points in 8 river systems; 8 rows had no full rain window
(`docs/rain-word/reserve_rows.audit.json`). 8 points have 15 or more rows, in 5 river systems: the River Brock (3
points), the Yealm and the Piall (one system), the Alde, the Deben and the Ebble. Each has more than one word and
more than one count, so all 8 are scored. The two Hastings points fell to 14 rows each (their cell has rain from
2019 only), under the 15 that the count before the build gave them. The not-run rule (8 points, 700 rows) is met
exactly on points. 42.0% of results were over 900; 4.3% sat at a lab limit.

| Condition | Result | Pass rule | Verdict |
|---|---|---|---|
| 1. Raw order: mean within-point correlation of the word with the log count | 0.504 (0.353 to 0.531) | interval wholly above 0.15 | pass |
| 2. Order beyond the calendar (month means removed) | 0.415 (0.287 to 0.495) | interval wholly above 0.15 | pass |

**What is supported.** At river monitoring points with no monitored overflow upstream, in six winters that no figure
here had been scored on, a three-way word made only from the rain in the last 48 hours against the point's own
usual put a point's winter days in the right order, and not only by the calendar. Samples on "more rain than usual"
days tended to read higher than on "less" days at the same point. This is confirmation evidence for the order, at
these points, at lead 0 with reanalysis rain: the word, its cut-points and the conditions were pushed first, and the
reserve's results had not been joined to anything.

**What is not supported.**

- A count, a chance or a level from the word. The shares over 900 below differ a lot by word, but they are these
  points' shares, and the points read high.
- Anything at an upland beck. The scored points are lowland and coastal rivers in Lancashire, Suffolk, Wiltshire
  and Devon, 5 river systems in all. The 15 spots are not like them.
- Anything days ahead, or from forecast rain.

### Reported, deciding nothing

| Figure (same rows) | Raw | Month means removed |
|---|---|---|
| The word | 0.504 | 0.415 (0.287 to 0.495) |
| Rain in 48 hours as a number | 0.519 | 0.432 (0.316 to 0.534) |
| Production's chance with exposure 0 (`7daf7c8e…`) | 0.602 | 0.414 (0.305 to 0.518) |

- The word less rain as a number, month means removed: −0.017 (−0.061 to −0.014). Cutting rain into three loses a
  little order, as expected, and the loss is small.
- Production's raw figure is higher because its day-of-year terms follow the calendar; with month means removed it
  is level with the word.
- Level by word: on "less" days 8.3% of results were over 900 (median 210 per 100 ml, 291 rows); "about" 38.8%
  (545, 312 rows); "more" 67.9% (2,000, 417 rows). Production's mean chance was 8.2% where 42.0% were over 900.
  The word shares on sample days were 29% less, 31% about, 41% more: samples fell on wetter days more often than a
  third of the time.
- By month group (raw, month-removed): October and November 0.532, 0.502; December to February 0.454, 0.422; March
  and April 0.339, 0.351. Winters to 2017: 0.493, 0.405; from 2019: 0.398, 0.353 (3 points scored).
- Each system left out in turn: condition 1 stays between 0.489 and 0.534 and condition 2 between 0.407 and 0.468,
  except without the River Brock (3 points), where they are 0.418 and 0.284. The Brock is the strongest part.
- Each point's own correlation: Alde 0.60, Deben 0.29, Brock 0.53, 0.71 and 0.70, Ebble 0.30, Yealm 0.30, Piall 0.59.

**Development, on rows already read** (`docs/rain-word/development.json`, scored after the statement was pushed):

| Rows | Points scored | Raw | Month means removed |
|---|---|---|---|
| RIVER-WINTER's read half, winter (1,122) | 8 | 0.426 (0.314 to 0.501) | 0.448 (0.331 to 0.508) |
| RIVER-UNSEEN's summer side set, summer cut-points (2,071) | 23 | 0.297 (0.241 to 0.367) | 0.338 (0.268 to 0.395) |

In summer the word is weaker than in winter, and weaker than rain as a number (0.321 raw, 0.375 month-removed): the
word less rain was −0.038 (−0.059 to −0.010). Over 900 by word in summer: less 35.7%, about 43.9%, more 74.6%.

Shared inputs had the same fingerprints before and after (`docs/rain-word/shared_inputs_fingerprint.txt`): the
sealed table, the private RIVER-UNSEEN folder, the ERA5-Land cache listing, the river-usual cache listing and the
summer side-set rows. Built rows: `reserve_rows_no_overflow.parquet`, SHA-256 `e51a5dab…`, in the session's scratch
folder.

### What this leads to

By the statement: **the word goes on the site**, as fixed above, in its own pull request, not merged by this project.

- **Summer too.** The statement's rule for summer was the development figure's raw interval wholly above 0.15. It is
  (0.241 to 0.367), so the word also shows from May to September, with summer cut-points. The page says the summer
  evidence is weaker. It is development evidence on samples that no model had seen when RIVER-UNSEEN scored them, not
  a pass test.
- **The wording, against the kill rule.** "More rain than usual here in the last two days" is a statement about rain.
  The sentence under it says what the word rests on and "This is not a level". So the shortlist's second kill
  condition (no wording avoids implying a level) is not met, on this project's judgement; Ethan can overrule it.
- **The reserve.** This read used the reserve's no-overflow rows. The reserve's rows at points with an overflow
  upstream are still sealed for RIVER-WINTER's own use.
- **Next check** (owner: this project's family): when winter samples at a listed upland beck exist (none known now),
  score the word there. Until then the evidence is monitoring points only, and the page says so.
