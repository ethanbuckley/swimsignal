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

### Row builder ready, 16 November 2026 (no held-out result read)

`scripts/river_unseen/build_rows.py` builds the inputs of amendment 1, section 7. It calls
`lake_range_hindcast.build_rows` unchanged and changes only where a site's pin comes from. That function and its
rain loader are on main, so stage 2 does not wait on #700.

Tested end to end on samples already seen, with nothing from the sealed table: the bench's 280 seen river samples of
2025 at 14 bathing waters, rebuilt on ERA5-Land rain for 2025 (2,069 cells converted in 7 seconds). All 280 rows
came out, none dropped, every site with the same number of overflows upstream as the bench's row, in 21 seconds.

Seen in passing, and not the match check: at those 280 sample times ERA5-Land's 48-hour rain correlates 0.81 with
the bench's Open-Meteo rain and averages 12% lower (3.41 mm against 3.87 mm); exposure correlates 0.88. That is in
line with the expectation in section 1 that the check fails and `river-range-v0e` is the candidate. The check
itself still runs once, on every paired cell and year, when the downloads finish.

`build_rows.py points` joins results to inputs, so it is part of the read. It has not been run.

### Match check and the candidate, 16 November 2026 (no held-out result read)

**The rain match check failed, so the candidate is `river-range-v0e`.** This is section 1's second branch, and the
outcome it expected.

The check: #702's `match_check.py --kind best_match`, run once, on every cell and year where both a cached Open-Meteo
file and converted ERA5-Land exist (2019 to 2026, after the 2023-26 download finished and 2019 to 2022 were on disk).
2,070 cells, 2,569,384 paired cell-days. The reference files' SHA-256 was the same before and after.

| Test | Result | Needed | |
|---|---|---|---|
| B1 pooled daily correlation | 0.879 | 0.90 or more | fail |
| B2 mean daily difference as a share of the reference | 12.1% lower | within 10% | fail |
| B3 share of cell-days within 0.5 mm | 58.0% | 85% or more | fail |
| B4 share of cells with daily correlation of 0.80 or more | 99.7% | 90% or more | pass |

Hourly correlation is 0.627 with no shift (0.594 one hour early, 0.564 one hour late), so the times line up and the
two products differ in the rain itself. ERA5-Land is not a stand-in for the cached rain. A model fitted on one must
not be tested on the other, which is what section 1 provided for.

**The candidate, frozen before any archive result is joined:** `docs/river-unseen/river_range_v0e.json`, SHA-256
`3c8bfe59…`. Same script, same features, fitted on the bench's seen river samples with rain and exposure rebuilt
from ERA5-Land by `build_rows.py bathing` (rows in `swimsignal-private/river-unseen/seen_river_rows_era5land.parquet`,
SHA-256 `7fac233d…`).

One departure from section 1, and why. It said "the same 943 seen river samples". 923 could be rebuilt. The other
20 are all from September 2026, and the ERA5-Land download ends at August 2026 because later months are still
preliminary at the source. They were dropped by the 90% rain-coverage rule, not by choice, before any fit.

| | Fitted on | 48-h rain | 24-h rain | Exposure | Spread (log10) |
|---|---|---|---|---|---|
| `river-range-v0` (Open-Meteo rain; not used) | 943 | 0.110 | −0.033 | 0.118 | 0.456 |
| `river-range-v0e` (ERA5-Land rain; the candidate) | 923 | 0.127 | −0.039 | 0.118 | 0.457 |

The two fits are close. Exposure on the seen rows runs lower on ERA5-Land (median 0.033 against 0.042, 90th
percentile 0.365 against 0.432), as the lower rain would give.

**The main reference**, as section 1 set: production's form refitted on those 923 rows. Production as deployed is
reported and decides nothing.

**What is left:** 80 months of 2012-18 rain still downloading; then convert the 85 river cells for 2012-22, build
the held-out rows and read once.

### Read script ready, 16 November 2026 (no held-out result read)

`scripts/river_unseen/read.py` computes what the statement and amendment 1 fix: the primary correlation with its
river-system-season interval, the range check with the lab-limit rule, and the reported figures. Without `--dev` it
refuses to run unless the candidate, the statement and the scripts are committed and the candidate's hash is named
here; it writes `docs/river-unseen/result.json` and appends to `docs/river-unseen/reads.jsonl` whatever it shows.

Tested with `--dev` on the 923 seen river rows the candidate was fitted on, which logs nothing. In-sample, so it says
nothing about the read: correlation 0.426 (0.349 to 0.504), 80.6% inside the range. It ran in 98 seconds.

`build_rows.py points` now also builds the two reported side sets: the 8 points rule 3 alone dropped that have an
overflow upstream, and the 23 points with no overflow upstream (exposure 0, as production gives). Neither decides
anything.

The commands for the read, in order, once 2012-18 rain is on disk:

1. `to_cells.py --points <85 cells> --years 2012-2022`
2. `build_rows.py points <sealed samples> points.csv systems.csv <held-out rows> held_out kept`
3. `read.py <held-out rows> <seen rows on ERA5-Land> river_range_v0e.json <production model> docs/river-unseen`

## The read, 16 November 2026: order passes, range fails

Run once, at 18:19 UTC on 16 November 2026, at commit `971ec69d`, with the candidate `river-range-v0e`
(`3c8bfe59…`). Logged in `docs/river-unseen/reads.jsonl`; every figure is in `docs/river-unseen/result.json`. The
2012-18 rain finished downloading at 17:52 UTC. The row builder took 6,322 samples in and gave 6,322 rows out at 59
points in 33 river systems, with no row dropped. There are no 2020 rows, as at staging.

| Check | Result | Pass rule | Verdict |
|---|---|---|---|
| Order: mean within-point correlation | 0.360 (0.314 to 0.394) | interval wholly above 0.15 | pass |
| Range: share inside the 8-in-10 range | 53.1% | 72% to 88% | fail |

0.7% of results sat at a lab limit, so the range check is not weak by amendment 1's rule.

**What is supported.** At river points and years no model here had seen, the candidate puts a point's days in the
right order: 0.360, against 0.426 in-sample on the seen rows. This is confirmation evidence for the order, at these
points. They are not swimming spots, 48 of 59 are in the South West, and the hindcast is at lead 0.

**What is not supported.** A stated reading or range at river points. The range was fitted on bathing waters and
sits too low here.

### Reported, deciding nothing

| Figure | Within-point correlation |
|---|---|
| Candidate | 0.360 |
| Production, refitted on the same seen rows | 0.347 |
| Production as deployed | 0.376 |
| Rain in the last 48 hours alone | 0.355 |

The candidate less refitted production is +0.013 (0.011 to 0.028). Rain alone comes within 0.005 of the candidate,
so the overflow exposure adds little to the order at these points.

Brier score for a result over 900 (lower is better; 48.3% of results were over 900): rain rule 0.286, production as
deployed 0.300, production refitted 0.305, candidate 0.306, month rate 0.319.

| Rows | Samples | Points | Correlation | Inside the range |
|---|---|---|---|---|
| Seasons to 2016 | 3,895 | 57 | 0.382 | 57.2% |
| Seasons from 2017 | 2,427 | 39 | 0.329 | 46.6% |
| Large catchment (100 km of channel or more) | 1,154 | 10 | 0.447 | 66.8% |
| Medium (10 to 100 km) | 3,614 | 29 | 0.367 | 52.1% |
| Small (under 10 km) | 1,554 | 20 | 0.307 | 45.3% |
| Purpose MU | 3,063 | 30 | 0.404 | 60.7% |
| Purpose PI | 2,290 | 29 | 0.325 | 40.2% |
| Purpose PN | 655 | 20 | 0.315 | 57.6% |
| Purpose MS | 313 | 29 | 0.274 | 64.2% |

The two side sets, scored with `read.py --dev` so that nothing is logged as a read:

| Side set | Samples scored | Points | Correlation | Inside the range |
|---|---|---|---|---|
| Rule 3 sensitivity (overflow upstream, name rule failed) | 518 of 870 | 7 of 8 | 0.341 (0.293 to 0.460) | 42.7% |
| No overflow upstream | 2,071 of 2,189 | 23 | 0.309 (0.263 to 0.375) | 29.5% |

The sensitivity set lost 352 rows in the builder (219 with no full rain window, 133 with no exposure, as first
built) and the no-overflow set lost 118 with no full rain window. The cause was not traced; a rain cell with no land
value in ERA5-Land is the likely one. At the no-overflow points the rain rule has the best Brier score (0.292
against 0.484 for the candidate), and rain alone orders days slightly better than the candidate (0.321 against
0.309).

### The spread, by stream size (exploratory, after the read)

The statement asks for the spread to be diagnosed by stream size when the range fails. These figures were computed
after the read on rows now seen. They are development evidence.

- The misses are one-sided: 44.3% of results were above the range and 2.6% below. The mean result was 0.54 log10
  above the likely reading, a factor of 3.4. The median result was 818 per 100 ml, against 320 on the seen rows.
- By band, the share above the range was 25.6% (large), 46.5% (medium) and 53.2% (small). The mean gap was 0.21,
  0.58 and 0.68 log10.
- By purpose, the mean gap was 0.36 (MS), 0.43 (MU), 0.48 (PN) and 0.72 (PI) log10. Planned investigations sit
  furthest out, as the limits section expected.
- A point's own level explains most of it. The standard deviation of the points' mean gaps is 0.41 log10. Within a
  point the spread is 0.51 log10, against the candidate's 0.46. With each point's own mean gap removed, which uses
  the results themselves, 78.4% of results fall inside a range of the candidate's width (75.1% large, 81.2% medium,
  74.3% small). That is a hindsight figure. It says a range needs a level for the place, and it does not show that
  such a range would pass.

### What this leads to

By the statement: an order-only line is proposed for river spots ("higher or lower than usual here"), with no
reading and no range. Ethan decides; nothing shows until he does. The river estimate, every forecast, every frozen
file and every active window are unchanged.

The next deliverable the evidence supports is a candidate for the level of a place, frozen before it is scored:
stream size and what lies upstream as inputs, fitted on seasons to 2016 and scored on seasons from 2017, by river
system. These rows have now been read, so that would be a development result, and a pass would need new unseen
points or the 2027 season to confirm it. Those 2023-26 archive rows at these points (development by the statement)
have not been scored.
