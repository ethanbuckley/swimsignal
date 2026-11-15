# RIVER-UNSEEN: statement, written before any archive sample is fetched

Written 15 November 2026 against main `6743baf2`. Project 1 of the
[ambition portfolio](https://github.com/ethanbuckley/swimsignal/pull/704) (`docs/AMBITION-PORTFOLIO-2026-11.md` on
that PR). This file fixes the rows, the candidate, the references, the metrics and what each outcome leads to.
**Nothing below the line "Staging result" existed when this was pushed, and no archive sample had been fetched.**
A change after that is an amendment: dated, with both versions kept.

Nothing on the site changes. No forecast, frozen file, active window or the 2027 primary evaluation is touched.

## The question

The river E. coli model was fitted on 2023-26 samples at 20 river bathing waters. The backtest bench (#700) has 60
held-out river rows at 2 sites, so "River candidates cannot be confirmed here". The Environment Agency's Water Quality
Archive holds river E. coli results at points that are not bathing waters, back to 2000. No model here has used them.

**Does a river model fitted only on bathing-water samples from 2023-26 order the samples at river points it never
saw, in 2012-22, and does its 8-in-10 range hold there?**

## What was known when this was written

- On 15 November two requests returned the archive's page cap of 2,500 rows, for 2019 and for 2024 (determinand 2348,
  sampling point type F6). From those two pages I printed counts by sampling point, region, area, purpose, material
  and month. I did not read the result column, and I deleted both files (`docs/ambition-portfolio/request_log.tsv`
  on #704).
- So: at least 2,500 rows a year; about 155 points a page, about 100 of them with 10 or more rows; 72% May to
  September; most rows planned monitoring or planned investigation; the pages lean to Devon, Cornwall, Morecambe Bay
  and East Anglia.
- No result value at any of these points has been read by this work, and none has been joined to rain, exposure or
  any model figure.
- On the bench's seen rows (development evidence): a log10 river model's 8-in-10 range held 79.3% of
  held-out-season samples with no site level, and its within-site Spearman correlation was 0.36 to 0.43
  (`docs/ambition-portfolio/river_bands_range.txt` on #704).

## Stage 1: fetch, count and place (this PR)

Stage 1 reads no result value. It settles whether the set can test the river model at all.

### The fetch

`scripts/river_unseen/fetch.py`. Environment Agency Water Quality Archive, Open Government Licence v3.0.

| What | Request | Sized before the run | Cap | Pace |
|---|---|---|---|---|
| E. coli, determinand 2348, sampling point type F6, calendar years 2012 to 2026 | `POST /data/observation`, CSV, 2,500 rows a page, one year a query | 30 to 135 requests, about 1 MB each (2,500 to 20,000 rows a year; the true count is not known) | 150 requests, 200 MB | 4 s |

- Wall time: at most 35 minutes at about 10 s an answer.
- A refusal (HTTP 401, 403 or 429) stops the run and is not retried. A 502, 503 or 504 is retried after 30 s and
  90 s, and each try counts against the cap.
- Order: 2022 back to 2012, then 2023 to 2026, so a stop costs the least useful years.
- Every request is in `docs/river-unseen/ledger.jsonl`. Raw pages go to `swimsignal-private/river-unseen/raw/`, not
  to git.
- Open-Meteo calls: none.

### Rows kept

- Material "RIVER / RUNNING SURFACE WATER".
- Sample taken in May to September.
- Sampling purpose one of: MS (statutory environmental monitoring), MP (environmental monitoring, GQA and RE), MU
  (monitoring, UK government policy), MN (monitoring, national agency policy), PI (planned investigation, local),
  PN (planned investigation, national).
- Dropped purposes: UI and UF (reactive, pollution incidents), SI and MI (follow-ups to a statutory failure), MA to
  MD (bathing-water abnormal situations and short-term pollution), and any other. Those samples are taken because
  of a bad result or an incident, which selects on the outcome.
- **Held-out rows:** 2012 to 2022. **Development rows:** 2023 to 2026 at the same points. Development rows are not
  part of any read.

### Points kept

A sampling point is kept when all of these hold. Each is decided from positions, names and counts, never a result.

1. **Count.** 30 or more kept held-out rows, in three or more seasons.
2. **On a river.** `transport.locate_pin` with `kind_hint="river"` and no river hint places it in river mode within
   50 m of a link of the river network (`pin.snap.dist_m`), with the site's settings.
3. **The right river.** Where the link it lands on has a name, that name's core (the name without "River", "Afon"
   or "The") appears in the sampling point's label, ignoring case. A point on an unnamed link is kept. This guards
   against a point by a confluence landing on the other river. The points it drops are listed, and a read reports
   them as a sensitivity set.
4. **Overflows upstream.** `transport.upstream_overflows`, with the site's settings, finds one or more monitored
   storm overflows.
5. **Not a bench site.** More than 500 m from every inland bathing water in `data/raw/bathing_waters_inland.json`.

Rule 4 is counted two ways, because the kill rule needs both: points that pass rules 1, 2, 3 and 5 with an overflow
upstream, and those without.

### Kill rule, stated before the fetch

Stop RIVER-UNSEEN as a test of the river model if either holds:

- fewer than 30 points pass all five rules; or
- of the kept held-out rows at points passing rules 1, 2, 3 and 5, more than half are at points with no monitored
  overflow upstream.

Then the rows are kept for the portfolio's rain-only question (ANYWATER) and this record says why.

### What stage 1 commits

- `docs/river-unseen/points.csv`: every sampling point with its label, position, counts of kept rows by span, and
  each rule's outcome. No result.
- `docs/river-unseen/manifest.json`: row counts by year, purpose and material, duplicate checks, the SHA-256 of the
  sealed sample table, and the fingerprints of the shared inputs before and after.
- The sealed sample table (`swimsignal-private/river-unseen/samples.parquet`) holds the results. Stage 1 writes it
  without printing, summarising or joining any result.

## Stage 2: the read (a later PR)

Stage 2 needs rain and exposure for every kept row. That is about 2,900 weighted Open-Meteo calls for the points
alone, more for the overflows' cells, or none with the ERA5-Land bulk download (#702), which waits on a Copernicus
account. Stage 2 does not start until one of those is settled, and any choice it must make that is not fixed here is
an amendment pushed before the join.

- **Candidate.** `river-range-v0`, frozen in `docs/river-unseen/river_range_v0.json` (SHA-256 `bb4d8c10…`), fitted
  by `scripts/river_unseen/freeze_candidate.py` on the bench's 943 seen river rows (`seen.parquet`, SHA-256
  `417648aa…`). A log10 model: rain in 48 and 24 hours, upstream exposure, season. No site level. Spread 0.456 log10.
  The likely reading is its median; the 8-in-10 range is the median times and divided by 3.8.
- **References.** Production's river chance as deployed (without soil moisture in years where none exists; said in
  the record); the month-of-year rate; "more than 10 mm in 48 hours".
- **Rain.** The same source for the candidate and every reference. If ERA5-Land is used where production was fitted
  on Open-Meteo's archive, the record says so and reports the #702 match check beside the result.
- **Primary metric.** Mean over points (15 rows or more) of the within-point Spearman correlation between the likely
  reading and the measured log10 count. **Pass:** the 95% interval, from 2,000 resamples of river-system seasons,
  lies wholly above 0.15.
- **Range check.** The share of held-out samples inside the 8-in-10 range. **Pass:** between 72% and 88%.
- **Reported, deciding nothing.** Brier over 900 against each reference. Seasons to 2016 and from 2017 apart (the
  archive rain most likely changes source at 2017). By purpose. By upstream catchment size. The rule 3 sensitivity
  set. Points with no overflow upstream.

### What each outcome leads to

- **Both pass.** A wording proposal for Ethan: a likely reading and range at river spots in season, on the lake
  range's pattern (#585), and a shadow log beside production for 2027. Nothing shows until he decides.
- **Order passes, range fails.** An order-only line is proposed ("higher or lower than usual here"). The spread is
  diagnosed by stream size.
- **Order fails.** The river estimate stays as it is. The record says the model did not carry to these points and
  shows which kinds of point it failed at. The rows stay as development data.

### Limits known now

- These are not swimming spots. Many are small streams above beaches, sampled to find sources of pollution. A pass
  supports the model at river points with overflows upstream. It does not show the same at a large lowland river
  unless such points are in the set; the read reports catchment size for that reason.
- Investigation points are placed where pollution is suspected. Levels may run higher than at a bathing water. The
  primary metric is order within a point, which a point's level does not move. The range check is exposed to it.
- Hindcasts on archive rain at lead 0, as every bench read. Skill at leads 1 to 4 is not measured.
- The spill model's labels start in 2024. Exposure for 2012-22 comes from that model run on older rain, as the
  bench's lake rows do.

---

## Staging result

Added 15 November 2026, after the statement above was pushed at `0db5828f` (22:44:16 UTC). The first request went
at 22:44:23 UTC. Nothing above this heading changed.

**The kill rule is not met. The set can test the river model.** 59 sampling points pass all five rules, with 6,322
held-out samples from 2012-22. The bench has 60 held-out river rows at 2 sites. No result was read to get here.

### The fetch

34 requests, all answered 200, 26.1 MiB, 22:44:23 to 22:48:55 UTC (`docs/river-unseen/ledger.jsonl`). Under the cap
of 150 requests. 64,279 rows, 2012 to 2026, at 1,223 sampling points. No observation id came twice across pages. 4
rows share a point and a time with another row; they are kept as they are for stage 2 to rule on.

| Year | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rows fetched | 9,683 | 7,286 | 5,775 | 5,017 | 3,310 | 2,814 | 2,838 | 3,349 | 317 | 2,808 | 3,719 | 4,295 | 3,810 | 4,853 | 4,405 |
| Kept, held out | 3,320 | 2,190 | 1,301 | 1,553 | 1,219 | 1,188 | 1,347 | 1,874 | 0 | 1,272 | 1,892 | | | | |

2020 has no kept row: 317 rows were taken that year, none in May to September with a kept purpose.

### Rows

- 61,741 of 64,279 rows are river water. The rest are estuary, sea, drainage and other materials filed under a river
  sampling point, and are dropped.
- 29% of rows (18,545) have a dropped purpose. 17,061 of those are follow-ups to a statutory failure at a point that
  is not designated. That share is larger than the two pages seen before the statement suggested.
- Kept rows: 17,156 held out and 12,718 development.

### Points

| Rule | Points left |
|---|---|
| All sampling points with a row | 1,223 |
| 1. 30 or more kept held-out rows in three or more seasons | 115 |
| 2. In river mode within 50 m of a link | 95 |
| 3. The link's name appears in the point's label, or the link has no name | 82 |
| 5. More than 500 m from every inland bathing water | 82 |
| 4. One or more monitored overflows upstream | **59** |

Kill rule, first part: 59 points, against a floor of 30. Second part: the 82 points passing rules 1, 2, 3 and 5 hold
8,511 kept held-out rows, 2,189 of them (25.7%) at the 23 points with no overflow upstream, against a ceiling of half.

At the 59 kept points: 6,322 held-out rows and 1,495 development rows. Every point has 38 or more held-out rows; the
middle point has 81; the largest has 402. 29 points have five or more seasons.

### What kind of points these are

Read from labels, positions and counts (`docs/river-unseen/points.csv`):

- **48 of the 59 are in the South West**, with 4,606 of the 6,322 rows. 5 are in East Anglia (the Deben, Ore and
  Tud), 4 in the North West (the Wyre and its brooks), 1 on the Thames above Runnymede and 1 at Havant.
- **Most are small.** 22 points have one overflow upstream, 19 have two to five, 18 have six or more. 18 sit on a
  link with no name, most of them a stream crossing a beach ("Polzeath Beach - Stream A").
- **The larger rivers are few:** the Hampshire Avon and its tributaries the Nadder, Wylye and Bourne (10 points, 4
  seasons each), the Dorset Stour (47 overflows upstream), the Wyre, the Yealm, the Thames.
- One kept point, the Hampshire Avon at Fordingbridge, is 825 m from the bench's Fordingbridge bathing water. It
  passes rule 5 as written. Its held-out rows are from years before that bathing water was sampled.

So the limit stated before the fetch holds, and is stronger than stated: a pass would support the model at small
coastal streams and chalk rivers of southern England. It would say little about large lowland rivers. Stage 2 must
report the Avon system, the Stour, the Wyre and the Thames apart.

### What rule 3 cost

Rule 3 dropped 13 points that rule 2 had placed. Read by eye, with no result in view:

- 4 are right to drop: the point sits on a tributary and landed on the main river (Newton Stream and two Cofflete
  Stream points on the "River Yealm" link; Barton Brook on "New Mill Brook").
- 5 look like the right water under another spelling or name: "Sparting Brook" against "Sparling Brook", "Lariggan"
  against "Larriggan", "Old River Brock" (the rule removes "River" from the middle of a name), the Strat at Bude on
  the link named "River Neet", and the Mawgan Porth stream on the "River Menalhyl".
- 4 could not be told from the label.

The rule stays as written. Loosening it after seeing which points it drops would be choosing the set after the
fact. The 13 are the sensitivity set the statement names; 8 of them have an overflow upstream.

Rule 2 dropped 20 points: 5 where the network has no river within reach, 2 that land on a lake, and 13 that land
more than 50 m from a link (168 m to 1.5 km), mostly streams too small for the network.

### Shared inputs

Placement ran in a scratch root: copy-on-write clones of the main checkout's `data/processed` and `data/raw`, with
this commit's tracked data laid over them, and scratch `DIPCAST_STATE` and `DIPCAST_CACHE`. Nothing was written to
either scratch folder. The main checkout's `river_network.pkl`, `overflows.parquet` and `lakes.parquet` (size and
SHA-256) and the listings of `data/raw` and `data/processed` (name, size and modified time of every file) were the
same before and after (`docs/river-unseen/shared_inputs_fingerprint.txt`). As a check on the trace, the bathing water
at Ilkley placed 3 m from the River Wharfe with 16 overflows upstream, the bench's own count.

### Where things are

- In git: `docs/river-unseen/points.csv` (1,223 points; no result), `manifest.json`, `ledger.jsonl`,
  `river_range_v0.json`. Contains Environment Agency information © Environment Agency and database right, Open
  Government Licence v3.0.
- Not in git: the 34 raw pages (26 MB) and the sealed sample table, in `swimsignal-private/river-unseen/`. The table
  is `samples.parquet`, 64,279 rows, SHA-256 `95ca8c9f…` (in the manifest). It holds the results as text.

### What follows

Stage 2 is the read. It is blocked on rain, not on anything in this PR:

1. **Rain for 59 point cells and their overflows' cells, 2012-22.** Either the Copernicus account that #702 waits on
   (Ethan's step, then no Open-Meteo call), or about 1,700 weighted Open-Meteo calls for the point cells (59 cells,
   11 years, 2.6 a cell-year) and more for the overflows' cells, spread under the daily ration.
2. **An amendment before any join**, to fix what this statement left open: which points form one river system for
   the interval; how two results at one point and time are handled; the catchment-size bands; and which rain source
   decides.
3. **Then the read**, once, with its result under this file.

Nothing on the site changes at any stage until Ethan decides on a wording proposal.

---

## Amendment 1, 15 November 2026: what the read still needed fixed

Written after the staging result and **before any sample result is read or joined to rain, exposure or a model
figure**. It fixes the four things "What follows" listed, and three more that building the rows will need. It changes
no row rule, no point rule, the kill rule, the primary metric, either pass threshold or what an outcome leads to.

What was known when this was written: everything under "What was known" and "Staging result" above; the unit and
time columns of the sealed table (read for sections 5 and 6 below; neither is a result); and that the first month of
ERA5-Land rain had arrived from the Copernicus Climate Data Store (10.1 MB in 2.0 minutes). No rain value has been
opened.

### 1. Which rain decides

The statement said the candidate and every reference use the same rain source. It did not say what happens when
that source is not the one the candidate was fitted on. `river-range-v0` was fitted on the bench's seen rows, whose
rain is Open-Meteo's archive, most likely the IFS analysis (#702). The read's rain is ERA5-Land from the Copernicus
store, converted by #702's `to_cells.py`. #702's record sets the rule: "Never fit on one source and test on the
other", unless its `best_match` check passes.

So the candidate depends on that check, and the choice is fixed now:

- **Run #702's `best_match` check first** (`match_check.py`, tests B1 to B4, thresholds as #702 wrote them), on every
  cell and year where both a cached Open-Meteo file and ERA5-Land exist. It reads rain only, no sample.
- **If it passes:** the candidate is `river-range-v0` as frozen (`bb4d8c10…`). The main reference is production's
  river chance as deployed.
- **If it fails, or gives no verdict:** the candidate is `river-range-v0e`. It is the same script
  (`freeze_candidate.py`), the same features and the same 943 seen river samples, with their rain and exposure
  rebuilt from ERA5-Land for 2023-26. It is fitted and its hash committed before any archive result is joined. The
  main reference is production's form refitted on those same rows. Production as deployed is reported beside it
  and decides nothing.
- Either way the read uses ERA5-Land for every row and every figure, and the pass thresholds are unchanged.

Expectation, written before the check: it is more likely to fail than pass, as #702 expects, so `river-range-v0e`
is the more likely candidate.

One limit this does not remove. The spill model inside the exposure was trained on Open-Meteo rain for 2024-25 and
is not refitted. In the `v0e` branch it is fed ERA5-Land in the fit and in the test alike, so the E. coli model
learns its exposure term on the same kind of exposure it is tested on. The spill chances themselves may be off in
level. The read reports exposure's distribution in 2023-26 and 2012-22 side by side so a shift is visible.

This needs ERA5-Land for January 2023 to August 2026 as well as 2012-22: 44 more monthly requests, queued after the
132 now running.

### 2. River systems, for the interval

`scripts/river_unseen/systems.py` writes `docs/river-unseen/systems.csv` from positions and the river network only.
A point's river system is the outlet it drains to: the terminal node of the network reached by going downstream
from where its trace starts (the smallest node id where a braid reaches more than one). Points with the same outlet
are one system.

- The 59 kept points fall in **33 systems**. 23 systems hold one point.
- The largest, S07, holds 11 points and 876 rows: the Hampshire Avon, Nadder, Wylye and Bourne, and the Dorset Stour,
  which share an outlet at Christchurch Harbour. S30 (the Yealm and Piall) holds 6; S25 (the Wyre and its brooks)
  holds 4.

The deciding interval: 2,000 resamples, seed 20261115, of system-seasons drawn with replacement. A drawn
system-season brings every held-out row at every point of that system in that season, and one drawn twice counts
twice. In each resample a point's correlation is recomputed from its drawn rows, a point with fewer than 15 rows is
left out of that resample's mean, and the mean is over points. The 2.5th and 97.5th percentiles are the interval.
This is the bench's water-body-season interval (#700) with "river system" in place of "water body".

### 3. Catchment size bands

By the length of channel upstream of the point on the network (`upstream_km` in `systems.csv`). The band edges were
written into `systems.py` before any length was computed.

| Band | Channel upstream | Kept points | Held-out rows |
|---|---|---|---|
| Small | under 10 km | 20 | 1,554 |
| Medium | 10 km to under 100 km | 29 | 3,614 |
| Large | 100 km or more | 10 | 1,154 |

The read reports the primary metric and the range check for each band, deciding nothing. The 10 large points are
six in the Hampshire Avon and Stour system, the Devon Avon, two on the Wyre and the Thames. A reader who wants to
know about large rivers should look at that row and its interval, not the pooled figure.

### 4. Two results at one point and time

If two kept rows share a sampling point and a time: where the results are equal, one is kept; where they differ, the
higher is kept (the coastal baselines' rule). Counted in the read's manifest. The 4 such rows in the fetch are not
among the kept held-out rows at kept points, so today this rule touches no row of the read.

### 5. Results at the lab's limits

Every kept row's unit is "number per hundred millilitres" (the unit column, checked). A result reported as below a
limit is kept at the limit with its "<", one reported as above a limit at that value with its ">", as #584 and #466
did.

- The primary metric uses those values as they are; ties are allowed.
- Range check: a "<" result counts as inside when the range's lower end is at or below the limit. A ">" result counts
  as inside when the range's upper end is at or above the limit. Any other result counts as inside when it lies
  between the two ends, ends included.
- The share of "<" and ">" results is reported beside the range check. If more than a quarter of held-out results
  are at a limit, the record says the range check is weak evidence, whatever it reads.

### 6. Sample times

The archive gives each time with no offset. It is read as UK local time, as the coastal baselines read it. The 48-
and 24-hour rain windows end at that time, as the bench's rows do, and a row whose 48-hour window is less than 90%
covered is dropped (`ecoli.MIN_COVERAGE`). No kept row has a time of exactly midnight; 77 of the 6,322 fall between
00:00 and 05:59 and are kept as given.

### 7. Building the rows, and the references

- **Rows.** The bench's row builder (#700: `stage.py` through `lake_range_hindcast.build_rows`), unchanged, with
  each kept point as a river pin at its `points.csv` position. If #700 is not merged when stage 2 starts, stage 2
  waits for it or carries its files unchanged and names the commit. The spill model file, the lead-0 calibration map
  and the overflow table go in the read's manifest by SHA-256.
- **Rain cells.** `docs/river-unseen/rain_cells.csv`: 85 cells of 0.1 degree, 41 holding a kept point and the rest
  holding only overflows upstream of one.
- **Month-of-year rate:** the share of the 943 seen river samples over 900 in each calendar month.
- **Rain rule:** over 900 forecast when more than 10 mm fell in the 48 hours before the sample, with the two chances
  set to the seen river rows' shares over 900 above and below that line.
- **One read.** The result goes under this file with the command, the commit and the time, and a line is appended to
  `docs/river-unseen/reads.jsonl` for every run of the read script against held-out rows, whatever it shows.

### What follows now

1. The download finishes: 2012-22, then 2023 to August 2026.
2. `to_cells.py` for the 85 cells and for every cached cell the match check pairs.
3. The `best_match` check. Its verdict picks the candidate (section 1).
4. If `river-range-v0e`: rebuild the 943 seen river rows on ERA5-Land, fit, commit the hash.
5. Build the held-out rows and read once.
