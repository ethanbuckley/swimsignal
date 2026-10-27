# Satellite NDCI against laboratory chlorophyll-a in English lakes: the test, stated before any run

Written 26 October 2026, before any run. Nothing has been scored. No chlorophyll-a value has been read: every
Water Quality Archive (WQA) response touched so far went through a parser that drops the result first. No B4, B5 or SCL
pixel has been read for this test. Ethan approves this statement before any outcome is fetched. Results go below the
line at the end. Nothing above it changes after a result is seen.

## Why

The lake algae satellite test (`docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md`, PR #377) compared a Sentinel-2 NDCI reading
with the EA sampler's visual algae check. It failed: AUC 0.60, primary label "Possible harm". The visual check is a
coarse outcome: one person's look from the shore, in four levels. NDCI was built to track chlorophyll-a in the water.

So the question here is narrower and comes first: **does a Sentinel-2 NDCI reading, made exactly as in #377, track EA
laboratory chlorophyll-a at English lake sampling points?** If it cannot track the quantity it was built for, there is
no reason to expect more from it against the visual check.

What it cannot answer, whatever the result:
- **Toxic or not.** Chlorophyll-a is in all algae. Neither the reading nor the outcome tells blue-green algae from
  other kinds (#377, "Why").
- **Safety.** Nothing here is a health figure, and nothing reaches the site.

## The outcome: EA laboratory chlorophyll-a

**Determinand 7887, "Chlorophyll : Acetone Extract", unit "MICROGRAM PER LITRE" (µg/l).** Read from the WQA codelist
(`/codelist/determinand`, search "chloroph", 26 October 2026) and from the listing below.
- The codelist holds other chlorophyll codes: 0728 (wet weight), 0729 ("Chlorophyll a"), 0947 (a + b), 3179
  (chlorophyllide a), 3904 (chlorophyll b), 7727 (filtered 35 µm), 7888 (methanol extract), 7907 (fluorimeter), 8306
  (HPLC) and 9900 (a ratio).
- A listing of 0729, 0947, 7727, 7887, 7888, 7907 and 8306, May to September 2020–2026, at every point type in England,
  returned rows for 7887 and 7888 only. The 18 rows of 7888 are all at water-treatment process-effluent points. So 7887
  is the only code measured at lakes. Every 7887 row had the unit "MICROGRAM PER LITRE".
- **Inferred, not confirmed:** the label says "Chlorophyll", not "chlorophyll a". The EA method behind 7887 was not
  found and not read. Acetone extraction with a spectrophotometer is a standard method for chlorophyll-a, so 7887 is
  taken to be chlorophyll-a. If it includes other pigments, the test still asks whether NDCI tracks the EA's measured
  chlorophyll.

**Values.** The result is a text field (`result` in the CSV). The rules, fixed now (`chl_protocol.chl_value`):
- "<x" (below the reporting limit) is set to x ÷ 2 and counted as censored.
- ">x" is set to x and counted.
- Text that is not a number, or a value of 0 or less, is dropped and counted.
- The outcome is log10 of the value. One sample per point and local date: the first by time.
- How many values are censored is not known. The listing dropped every result, "<" included.
- Description only: the correlation with censored samples left out.

**Season and years.** 1 May to 30 September, 2020 to 2026, by the sample's local date (`phenomenonTime`, published as
local time).
- **2020 has no in-season sample.** The listing found 3 rows of 7887 in England from May to September 2020, none at a
  lake. A first page of 2,500 rows for the whole of 2020 held none from April to August. Inferred: routine sampling
  stopped in spring 2020. None of the chosen points has a 2020 sample.
- **2022 has samples but no imagery.** `sentinel-2-c1-l2a` holds no May–September 2022 item (#377, revision 3). The
  2022 samples are counted and reported, with no reading, as in #377.
- So readings come from five seasons: 2021, 2023, 2024, 2025 and 2026.

**Licence.** The WQA pages (landing page, downloads, API documentation, read 26 October 2026) say in their footer that
all content is under the Open Government Licence v3.0, except where otherwise stated. Nothing on those pages states
otherwise for the data. The licence (nationalarchives.gov.uk, version 3, read the same day) asks for the provider's own
attribution statement or, where there is none, this one: "Contains public sector information licensed under the Open
Government Licence v3.0." No WQA page gives its own statement. The four support FAQ pages linked from the footer are
drawn by JavaScript and returned no text, so they were not read.

## Which lakes

### The rule, from metadata and sample dates only

No chlorophyll value is an input. The rule is `chl_protocol.select`, applied by `select_lakes.py choose`:
1. **Points with chlorophyll-a.** Every WQA point with a 7887 sample dated May to September 2020–2026 (the listing).
2. **Lake points.** WQA point type "FRESHWATER - LAKES/PONDS/RESERVOIRS" (FA) or "FRESHWATER - BATHING WATER" (FL).
   This leaves out river, inlet and raw-water points that sit on or near a lake.
3. **On a lake.** Inside a WFD Cycle 3 lake outline, or within 50 m of one (a shore or jetty sample). These are the
   outlines the repo already uses (`src/dipcast/ingest/lakes.py`, `scripts/build_any_point.py`); the file used is
   `data/raw/wfd_lakes_cycle3.geojson`, SHA-256 `c355d810…f9f1bb287`. A point near two lakes takes the nearer.
4. **Enough open water.** The lake outline moved 30 m inward, cut to 300 m from the point (#377's site radius), holds
   at least 10,000 m². That is 25 pixels of 20 m, about three times #377's size rule of 9 core pixels, because a 20 m
   grid loses pixels along any shore. This rule only saves downloads. The size rule that decides is #377's, on pixels,
   in stage 1a.
5. **Enough dates.** At least 5 distinct sample dates in the seasons with imagery (2020, 2021, 2023–2026).
6. **One point per lake.** The point with the most such dates; on a tie, the first point notation.
7. **At most 40 lakes.** The most dates first; on a tie, the larger lake, then the WFD id.

**Lake type, for condition 4.** "Shallow" when the lake's HydroLAKES mean depth (`hl_depth_avg_m` in
`data/raw/lake_residence.csv`, already in the repo) is under 3 m; "deeper" otherwise. Most of these depths are
estimated by HydroLAKES from the land around the lake (`hl_vol_src` 3, as `scripts/make_lake_residence.py` notes),
not measured. A lake with no HydroLAKES depth is in neither group. It
stays in every pooled figure. Why depth: in shallow water the lake bed and stirred-up sediment add to the red and
red-edge light, and deep, clear lakes have little chlorophyll, where NDCI is weakest. Both could make NDCI fail in one
type and not the other.

**Lakes are the clusters.** Every interval and every hold-out uses the WFD water body. Windermere's North and South
Basins are separate WFD water bodies, so they count as two lakes. Their readings may move together (inferred).

### What the rule gave

From the listing (`docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-dates.parquet`, SHA-256 `5f4097d7…bfca993f3`, no result
column) and the outlines:

| Step | Count |
|---|---|
| WQA points with a 7887 sample, May–September 2020–2026 | 1,628 (20,727 point-dates) |
| typed lake or bathing water | 503 |
| on or within 50 m of a WFD lake | 216 points on 165 lakes |
| past the open-water rule | 203 |
| with 5 or more dates in seasons with imagery | 132 points on 111 lakes |
| chosen (one per lake, cap 40) | 40 lakes; 71 left out by the cap |

The cap fell inside a tie: 9 lakes had 13 dates, and Bomere Pool (0.09 km²), the smallest, was left out by area.

The 40 points have 854 sample dates in May to September: 0 in 2020, 131 in 2021, 129 in 2022 (no imagery), 149 in
2023, 141 in 2024, 156 in 2025 and 148 in 2026. 725 are in seasons with imagery. Lake types: 14 shallow, 19 deeper, 7
with no depth. Every point, its lake, position and dates: `docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json`.

| # | Lake (WFD) | WQA point | Type (mean depth) | Area km² | Point | Dates with imagery | Items within 1 day |
|---|---|---|---|---|---|---|---|
| 1 | Windermere (N Basin) | NW-88023689 | deeper (15.5 m) | 8.67 | inside | 53 | 140 |
| 2 | Windermere (S Basin) | NW-88004556 | deeper (15.5 m) | 6.08 | 4 m outside | 50 | 134 |
| 3 | Hickling Broad | AN-THR030A | shallow (0.7 m) | 1.60 | inside | 24 | 90 |
| 4 | Barton Broad | AN-ANT160 | shallow (2.2 m) | 0.71 | inside | 22 | 66 |
| 5 | Horsey Mere | AN-THR020 | shallow (1.5 m) | 0.33 | inside | 22 | 56 |
| 6 | Martham Broad | AN-THR061 | no depth | 0.18 | inside | 22 | 54 |
| 7 | Ranworth Broad | AN-BUR170A | no depth | 0.42 | inside | 20 | 60 |
| 8 | Wroxham Broad | AN-BUR300 | shallow (2.1 m) | 0.35 | 13 m outside | 20 | 64 |
| 9 | Rollesby Broad | AN-ROL010 | shallow (2.0 m) | 0.34 | inside | 20 | 60 |
| 10 | Blelham Tarn | NW-88016157 | no depth | 0.10 | inside | 20 | 62 |
| 11 | Wast Water | NW-88021658 | deeper (15.9 m) | 2.84 | on the line | 19 | 24 |
| 12 | Ormesby Broad | AN-ORM010 | shallow (2.0 m) | 0.55 | inside | 19 | 58 |
| 13 | Ormesby Little Broad | AN-ROL020 | shallow (1.9 m) | 0.40 | inside | 19 | 58 |
| 14 | Filby Broad | AN-FIL010 | shallow (1.6 m) | 0.42 | inside | 18 | 56 |
| 15 | Little Sea | SW-50900003 | shallow (2.2 m) | 0.33 | 2 m outside | 18 | 23 |
| 16 | Upton Broad | AN-UPT010 | no depth | 0.07 | inside | 18 | 84 |
| 17 | Fritton Decoy | AN-FRT020E | shallow (2.9 m) | 0.62 | inside | 17 | 54 |
| 18 | Crose Mere | MD-27942900 | shallow (2.2 m) | 0.15 | inside | 17 | 11 |
| 19 | Malham Tarn | NE-40000385 | deeper (5.3 m) | 0.61 | inside | 16 | 24 |
| 20 | Ullswater | NW-88010023 | deeper (18.2 m) | 8.82 | inside | 15 | 40 |
| 21 | Aqualate Mere | MD-28548100 | deeper (3.5 m) | 0.76 | 1 m outside | 15 | 19 |
| 22 | Loweswater | NW-88010126 | deeper (7.0 m) | 0.61 | inside | 15 | 23 |
| 23 | Rostherne Mere | NW-88022930 | deeper (4.4 m) | 0.50 | 1 m outside | 15 | 12 |
| 24 | Tunstall Reservoir | NE-44100119 | deeper (5.1 m) | 0.24 | inside | 15 | 24 |
| 25 | Coniston Water | NW-88010011 | deeper (12.4 m) | 4.75 | inside | 14 | 22 |
| 26 | Ennerdale Water | NW-88005133 | deeper (17.2 m) | 3.02 | inside | 14 | 24 |
| 27 | Grasmere | NW-88016103 | deeper (6.9 m) | 0.60 | inside | 14 | 21 |
| 28 | Semer Water | NE-40000443 | deeper (4.9 m) | 0.29 | inside | 14 | 8 |
| 29 | Ogden Reservoir Lancashire | NW-LSN0028 | deeper (5.3 m) | 0.22 | inside | 14 | 9 |
| 30 | Brothers Water | NW-88010024 | deeper (7.9 m) | 0.20 | inside | 14 | 42 |
| 31 | The Mere (Ellesmere) | NW-88010089 | shallow (2.7 m) | 0.16 | inside | 14 | 12 |
| 32 | Elter Water | NW-88010013 | no depth | 0.15 | inside | 14 | 25 |
| 33 | Bassenthwaite Lake | NW-88010015 | deeper (12.6 m) | 5.09 | inside | 13 | 23 |
| 34 | Balderhead Reservoir | NE-45100109 | deeper (18.9 m) | 1.14 | inside | 13 | 23 |
| 35 | Thrapston Lake | AN-TMNRSFFD | shallow (2.7 m) | 0.60 | 4 m outside | 13 | 9 |
| 36 | Nook Beach | SO-E0004611 | shallow (1.3 m) | 0.49 | inside | 13 | 38 |
| 37 | Ravensthorpe Reservoir | AN-RAVENWFD | deeper (3.8 m) | 0.45 | inside | 13 | 48 |
| 38 | Frensham Great Pond | TH-PGWL0034 | deeper (3.5 m) | 0.29 | inside | 13 | 8 |
| 39 | Swanholme Lakes | AN-SWANHWFD | no depth | 0.16 | inside | 13 | 46 |
| 40 | Groby Pool | MD-47301190 | no depth | 0.12 | inside | 13 | 16 |

"Items within 1 day" is the count of `sentinel-2-c1-l2a` items over the point dated within a day of one of its sample
dates (metadata only, `docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-count.json`). Some of these lakes may fail #377's size
rule in stage 1a (Elter Water and Upton Broad have least open water near the point: 14,344 and 18,475 m² by rule 4).
Which ones is decided by pixels alone.

### How the values were kept out

Every WQA response that can carry a result goes through `wqa_meta.keep_only` (CSV) or `wqa_meta.keep_only_jsonld`
(JSON-LD) before anything else touches it. They keep the point notation, its label, easting, northing and type, the
sample time, determinand, unit, sampling purpose and sample material, and nothing else. Each row is cut to those
columns as it is read; the result and its "<" never reach a frame, a file, a log or the screen. `assert_no_values`
checks every parsed frame before it is saved. Tests (`tests/test_lake_chlorophyll_eval.py`): a sentinel result value
and its "<" are absent from the parsed frame, from every file the listing step writes (the ledger included) and from
what it prints; an unexpected header raises with column names only; the JSON-LD parser never reads `hasResult` or
`hasSimpleResult`.

The brief named point notation, position and sample date. The parser also keeps the label, type, determinand, unit,
purpose and material. None of them is a measurement. The unit and determinand are needed to state the outcome, and the
type for rule 2.

## The reading: NDCI exactly as #377

Every pixel rule is #377's, imported and unchanged (`scripts/lake_algae_sat_eval/protocol.py` and `stage1.py`):
- `sentinel-2-c1-l2a` items from Earth Search over the point, 1 May to 30 September 2020–2026, with the stop rule on
  `raster:bands` scale and offset;
- **the water mask** per point and tile from the SCL of every item: water where SCL is 6 in at least half the scenes
  that saw the pixel;
- **the connected piece** (8-neighbour) within 1 km holding the water pixel nearest the point, cut to 300 m;
- **core pixels**, whose 8 neighbours are all in the piece;
- **the size rule**: 9 core pixels on a tile, else no reading from that tile;
- **a usable scene**: at least 80% of core pixels clear;
- **the reading**: the median NDCI = (B5 − B4) ÷ (B5 + B4) over clear core pixels, B4 averaged 2 × 2 to 20 m;
- one scene per UTC date: the most clear core pixels, then the first item id.

The "site" is the WQA point's position (from its easting and northing), not a bathing water.

**The one change: which scenes get B4 and B5.** #377 read every usable scene. Here only usable scenes dated within
1 day of one of the point's sample dates are read. Sample dates are not outcomes. The SCL of every item is still read,
because the water mask needs all of them.

**Pairing.** A sample on local date d takes the usable scene at its point dated d − 1 to d + 1 (the scene's UTC date;
passes are near 11:00 UTC), the nearest first; on a tie between d − 1 and d + 1, the earlier. A sample with no such
scene has no reading.
- Why 1 day either side. Chlorophyll-a in a lake can change within days, with growth, die-off and wind mixing. Same-day
  or ±1-day windows are the usual choice in published satellite match-up studies for chlorophyll. That is from general
  knowledge; no paper was opened for this statement. ±1 day triples the chance of a clear scene over same-day only.
  Wider windows cost bytes: 3,770 items lie within 3 days of a sample date, against 1,670 within 1 day.
- Why both sides, when #377 used only d − 3 to d. #377 asked what a page could have shown on the day. This test asks
  whether the reading agrees with the water, so a scene the day after counts as well as the day before.
- Description only: the same-day pairs (a subset of these). A 3-day window is not read.

## The comparison and the conditions

**Rows:** samples with a reading, at points past the size rule. **Clusters:** lakes. **Intervals:** cluster bootstrap
by lake, 2,000 draws, numpy `default_rng(20261026)` (#377's draws), 95% (2.5th to 97.5th percentile).

### The gate, checked first

The test is judged only if the rows hold all of:
- at least 60 pairs;
- at least 10 lakes with 3 or more pairs each;
- at least 3 seasons with 10 or more pairs each.

Below that it is "too few to judge". Figures are reported as description. It cannot pass.

### The test passes if all four conditions hold

1. **Rank agreement (primary).** Pooled Spearman correlation of the reading with log10 chlorophyll-a is at least 0.5,
   and its interval's lower end is above 0.3.
2. **Placebo: signal within the lake.** The readings are shuffled within each lake and season, 200 times, numpy
   `default_rng(20261026)`, and the pooled Spearman recomputed. The real figure must be above the 95th percentile and
   above the 190th of the 200 ranked. Shuffling within lake and season keeps each lake's level that year and breaks the
   link to the day. Broads with high chlorophyll and clear Cumbrian lakes would give condition 1 on their own. This
   condition asks for signal on the day.
3. **Calibration at an unseen lake.** Leave one lake out. For each held-out lake, from the other lakes' pairs only:
   - **the fit:** ordinary least squares of log10 chlorophyll-a on the reading;
   - **the reference:** the lake-mean reference, the mean over the other lakes of each lake's mean log10 chlorophyll-a
     (every lake counts once). It is the best guess for an unseen lake without a satellite.
   The score is the skill d = 1 − MSE(fit) ÷ MSE(reference), pooled over every held-out prediction. Its interval is the
   cluster bootstrap of d with the predictions fixed. The label comes from the near-miss framework (addendum to
   `docs/LAKE-ECOLI-LINE-TEST-2026-10.md`), the first that fits: Better, Promising not shown, No useful difference,
   Possible harm, Harm, Too uncertain; "Unlabelled" when none fits. **It must be Better.**
4. **No lake type labelled harm.** Condition 3's label, computed on the shallow lakes' rows and on the deeper lakes'
   rows separately (same predictions, each its own bootstrap), with the same B and H. By the framework's note of 26
   October 2026 (Ethan's decision), "labelled harm" means "Possible harm" or "Harm". A type with fewer than 4 lakes or
   20 pairs is "too few to judge", reported, and does not block.

**The margins B and H, and the working.** The framework sets B as the smallest gain that changes what a swimmer sees.
Nothing here is shown on the site, so there is no band to cross. B is set instead from the reference's own error, as a
share of it: **B = 0.10 in skill, a fit that removes a tenth of the reference's squared error.** Why a tenth: a linear
fit's skill over a constant, in the fitting data, is about r² (r the Pearson correlation). Condition 1's lower bar is
0.3, and 0.3² = 0.09, rounded up to 0.10. So B asks the fit to do at an unseen lake about what a correlation of 0.3
does in-sample. **H = 0.05**, half of B, as in #377. Both are in skill units, so they hold whatever the reference's
MSE turns out to be. No outcome was seen in setting them.

**Verdicts.** "Passes": gate met and conditions 1–4 hold. "Fails: near miss": conditions 1, 2 and 4 hold and condition
3 is "Promising, not shown". "Fails": anything else with the gate met. "Too few to judge": gate not met.

**Why 95% with four conditions.** All four must hold, so the chance of a pass by luck is no larger than for any one of
them. No correction is applied.

**Power, inferred and not simulated.** The usual standard error of a correlation is about (1 − ρ²) ÷ √n. With n
between the number of lakes (about 35 after the size rule) and the number of pairs, a true ρ of 0.5 gives a lower end
somewhere near 0.25 to 0.4. So condition 1 needs a true correlation nearer 0.6 to pass reliably. This is a property
of the bar, stated now.

### Stop rules, checked before any score

- The features file hashes to the committed SHA-256. The values file hashes to the hash printed by the one fetch.
- Every item had `raster:bands` scale and offset on B4 and B5 (#377's check, in stage 1).
- Every fetched value has unit "MICROGRAM PER LITRE" and determinand 7887.
- The score step makes 0 network attempts (`scripts/lake_distance_eval/run_offline.py`).

If any fails, the run stops and that is reported before any score.

## What is expected, stated now

These are guesses.
- **Pairs.** In #377, 30% of checks had a usable scene in a 4-day window and 10% on the same day. A 3-day window should
  give about a quarter: about 150 to 180 pairs from the 725 sample dates, before the size rule. The gate should be met.
- **Size rule.** The points with least open water near them (Elter Water, Upton Broad, Swanholme Lakes) are the
  likeliest to fail it.
- **Condition 1 likely holds.** Chlorophyll-a across these lakes runs from clear Cumbrian lakes to the Broads,
  which are known for high algae. NDCI should rank that range.
- **Condition 2 is the open question.** Within a lake and season the range is small and each lake-season has few
  pairs. I give it about even odds.
- **Condition 3 likely Better** if condition 1 holds, because between-lake differences carry most of the variance.
- **Condition 4 may fail for the deeper lakes.** They have little chlorophyll, where NDCI is weakest and Sen2Cor's
  land-made atmospheric correction adds most noise.
- Overall: a pass is possible, not likely. My guess is about one in three.

## What follows

**Whatever the verdict, nothing on the site changes in this PR or because of it.**
- **Passes.** A later test of NDCI against the EA visual check, or of bloom detection, becomes worth stating, in its
  own file. Nothing is adopted from this test.
- **Fails, including a near miss.** Satellite work on Sentinel-2 Level-2A NDCI ends for now. A water-specific
  correction (ACOLITE, or CLMS if it ever covers England) would be a new test, not a retry of this one.
- **Too few to judge.** Reported as such. Nothing follows.

## Caps, sized first

**What the run needs, estimated** from the count step (25,148 items over the 40 points; 1,670 within 1 day of a sample
date) and #377's measured costs (28,317 requests and 5.18 GB for 18 sites; a clear scene's B4 and B5 about 2.6 MB,
because B4 pulls whole 10 m tiles):

| Part | Requests | Bytes | Pace |
|---|---|---|---|
| STAC searches, with `raster:bands` (about 14 KB an item) | 284 | about 0.35 GB | 1 a second |
| SCL windows, about 2.1 requests and up to 70 KB each | 52,800 | 1.76 GB | 16 at a time |
| B4 and B5, about 420 usable scenes (a quarter of 1,670), about 5 requests and 2.6 MB each | 2,100 | 1.09 GB | 16 at a time |
| **Stage 1 in all** | **about 55,200** | **about 3.2 GB** | |
| Stage 2 fetch, one request per point | 40 | about 1 MB | 1 a second |

At #377's measured rate under Amendment A1 (about 2,100 bucket reads a minute) and 1 second a search, stage 1 takes
about 35 minutes over 3 or 4 runs. The SCL cost per window is the least certain figure: 54 KB from #377's partial
stage 1a, 68 KB from its totals.

**The caps** (`chl_stage1.py`, `chl_stage2.py`, `wqa_meta.py`; checked by `test_caps_are_the_stated_ones`):
- **Stage 1:** at most 70,000 requests and 4.5 GiB over all runs (ledger `ledger-stage1.jsonl`); at most 20,000
  requests and 1.5 GiB per run. The two AWS COG buckets 16 at a time with no pause (#377's A1); the STAC API one at a
  time, 1 second apart. Byte caps checked before each request starts (#377's A2). Stop on HTTP 429, any 5xx or any
  status other than 200 or 206; nothing retried; only #377's hosts; no credentials.
- **Stage 2 fetch:** at most 80 requests and 20 MB, one at a time, 1 second apart, the EA host only, same stop rules.
- **The selection step** (already run): at most 200 requests and 100 MB to the EA host.
- **The count step** (already run): at most 400 requests and 50 MB.

If a cap stops stage 1 short, the fix is an amendment recorded in the run log before the next run, as in #377. No
reading changes because of a cap.

## Running, after approval only

Stages as in #377, in a scratch folder, from a `git archive` of the commit Ethan approves. Each step under the group's
heavy-run lock (`$HOME/Library/Application Support/Claude/side-session-notes/local_dc9219fa-fafc-4f09-a84d-03316133ab4a/heavy-run.lock`):
check it is absent, write it with the session name, start time and expected length, run, delete it.
1. **Stage 1a, online, outcome-blind:** `run.sh stage1 <out> masks`, again until it prints "complete". SCL windows,
   masks, `sizes.json`.
2. **Stage 1b, online, outcome-blind:** `run.sh stage1 <out> readings`, again until "complete". B4 and B5 for usable
   scenes within 1 day of a sample date, `features.parquet` and its SHA-256.
3. **The features hash is committed** to this file's run log and pushed before step 4.
4. **The one fetch:** `run.sh fetch <out> <features SHA-256>`. One request per point, determinand 7887, 1 May 2020 to
   30 September 2026. It refuses a second fetch. It prints counts and the values' SHA-256, never a value.
5. **Scoring, offline:** `run.sh score <out> <features SHA-256> <values SHA-256>`, every outgoing connection refused
   and counted; it must print "network attempts: 0". Order inside: stop rules, gate, then the scores.

The values stay in the run folder and are not committed. Only aggregate figures and counts are published.

## What will be reported

- The size rule: core pixels per point and tile, points in and out.
- Pairing: samples, samples with a reading, days from scene to sample, per point and season; the 2022 samples.
- Values: measured, censored, above and dropped counts.
- The gate counts, by lake and season.
- Each condition with its figure and interval; condition 3's d, L, U, B, H, both MSEs and the label; condition 4 per
  lake type.
- The 200 placebo figures (lowest, median, 95th percentile, highest).
- Description: same-day pairs, censored left out, Spearman by lake and by season, the line fitted on all pairs.
- The hashes, the harness commit, the network-attempt count and the request ledgers' totals.

## Harness choices

Fixed in `scripts/lake_chlorophyll_eval/` before any value or reading was seen:
- The reference in condition 3 weights lakes equally, not pairs. Windermere's two basins have far more dates than other
  lakes and would otherwise set it.
- A training fold with fewer than 2 distinct readings predicts the reference.
- Spearman is scipy's `spearmanr`; a draw with fewer than 3 pairs or no spread gives no value and is counted.
- Percentiles are numpy's default (linear).
- The pixel half is #377's code, not a copy, so it cannot drift. `git diff` of `scripts/lake_algae_sat_eval/` and
  `tests/test_lake_algae_sat_eval.py` against PR #377's branch is empty.

## Not chosen, and why

- **Other chlorophyll codes.** None has a lake row in the seasons (above).
- **Several points per lake.** Points on one lake on one day are near-duplicates. One point per lake keeps lakes as the
  unit.
- **WFD "heavily modified" as the lake type.** Windermere and most Broads are designated heavily modified, so it does
  not separate lakes by how light leaves the water. Depth does.
- **A 3-day window as primary.** More pairs, more mismatch in time, and about 2.3 times the bytes.
- **Filling 2022 from the older `sentinel-2-l2a` collection.** Different processing (#377, revision 3).

## Seen before writing

All on 26 October 2026, between 22:06 and 22:31 UTC (EA host), plus the STAC count after that.
- **From #377 and the repo:** #377's statement, harness, tests and results; the near-miss addendum and its 26 October
  note (commit 6d26f62, on the `docs/ai-programme-status` branch, not yet on this branch); `src/dipcast/ingest/wqa.py`;
  the WFD outlines and `data/raw/lake_residence.csv`.
- **WQA reference pages:** the landing, downloads and API documentation pages (footer licence text); the OpenAPI
  description (`/water-quality/api/swagger`); the determinand codelist search "chloroph" (the 11 chlorophyll codes
  named above, among chlorophenol codes); the sampling-point type codelist (113 types). Four support FAQ pages returned no text.
- **The licence:** OGL v3.0 on nationalarchives.gov.uk.
- **The listing, values dropped** (every response through `keep_only`):
  - two requests of one row each, to read the CSV header names and one row's kept fields (Barton Broad, AN-ANT160,
    27 May 2025, 7887, µg/l, a planned investigation sample);
  - May–September per season, the seven codes above, every point type: rows per season 2020 5, 2021 3,373, 2022 3,324,
    2023 4,236, 2024 3,565, 2025 2,865, 2026 3,436; of them 7888 2 or 3 a season (18 in all, all at process-effluent
    points), the rest 7887; counts by point type per season (lakes, ponds and reservoirs 320 to 1,007 a season);
  - one page of 7887 for the whole of 2020: 2,500 rows by month (January 805, February 659, March 591, September 7,
    October 84, November 139, December 215; none April to August);
  - the committed listing step (`select_lakes.py list`, 13 requests): 20,786 rows of 7887, all in µg/l.
- **The selection** (`select_lakes.py choose`): every count and the table above. An earlier run of the rule, before
  rule 2 (point type) and the depth-based lake type were added, chose a beck (Cunsey Beck at Ees Bridge), a raw-water
  intake (Weir Wood) and two river-typed points. That is why rule 2 exists. No value was involved.
- **The STAC count** (`chl_stage1.py count`, metadata only, 284 requests, 5.1 MB): items per point and items within
  0, 1 and 3 days of a sample date (550, 1,670, 3,770). No asset was read.
- **Requests:** 40 to the EA host (16 exploratory listing requests, 13 listing requests by the committed step, 11
  reference and codelist pages), 1 to nationalarchives.gov.uk, 284 to Earth Search. All counted in ledgers kept in the
  session's scratch folder.
- **Not seen:** no chlorophyll value, no "<", no count of censored values; no B4, B5 or SCL pixel; no score.

## Approval

Ethan approved this statement on 27 October 2026 at 00:35 UTC, in the coordinating session, in his words: "I approve the #386 and #385 statements as written. Run #386 then #385 under their stated protocols and caps, record the approval and results in each PR, and draft the 2027 forward statement for the third question without running anything." He had the statement at 61ff324 (statement f20bf05 plus the dated determinand check). Nothing above this section changes after approval, and nothing had been run: no B4/B5/SCL pixel read, no chlorophyll value read.

Context: on 26 October Codex had kept this test unrun during the product window and asked that 7887's definition be checked first; that check is the section below (partly verified). The results must name the outcome as "EA acetone-extract chlorophyll (determinand 7887), phaeopigment correction not stated".

---

## Determinand check, 26 October 2026 (after the statement, before review)

Written after the statement above, before Ethan's review and before any run. It changes nothing in the protocol: the
outcome is still determinand 7887, read and scored as above. No chlorophyll value was read for this check.

**Verdict: partly verified.** The method behind the EA's acetone-extract chlorophyll is now found and read. It
measures chlorophyll a by acetone extraction and spectrophotometry. Two things stay open: no EA page ties code 7887 to
that test by name, and no source says whether 7887 is corrected for phaeopigments.

What the sources say (all read 26 October 2026):
- **The WQA codelist record for 7887** (`https://environment.data.gov.uk/water-quality/codelist/determinand?notation=7887`):
  notation "7887", prefLabel "Chlorophyll : Acetone Extract", altLabel "CHLOROPHYLL". Nothing else: no definition, no
  method, no unit. The API description (`/water-quality/api/swagger`, version 1.3.1) has no other determinand
  endpoint. The old definitions URL (`/water-quality/def/determinands/7887.json`) now returns 404. The downloads and
  API-docs pages render in the browser and their HTML holds no determinand reference list.
- **The neighbouring codes** (codelist, prefLabel contains "chlorophyll", 11 codes; contains "phaeo", 11 codes). The
  EA keeps "Chlorophyll a" (0729), "Chlorophyll a + b" (0947), "Chlorophyll b" (3904) and "Chlorophyll a : HPLC"
  (8306) as separate codes from 7887. It also has "Phaeophytin, Acetone Extract" (5122), "Phaeophytin A" (3905, 8172)
  and "Chlorophyll a : Phaeophytin ratio" (9900). 7887 is not labelled as either a + b or total pigment.
- **The EA's own laboratory accreditation.** UKAS schedule 0754, Environment Agency - National Laboratory Service,
  issue 116, 9 September 2026 (`https://www.ukas.com/download-schedule/0754/Testing`), Starcross Laboratory, page 5:
  test "Chlorophyll", "Acetone Extraction and Spectrophotometric Analysis", documented in-house method "SX I
  Chlorophyll UVV", reference "(ISBN 011 7516740 1980)", Test 19; accredited for surface water, not ground or saline
  water. It is the only chlorophyll test on the schedule.
- **The method that ISBN names.** Standing Committee of Analysts, *The Determination of Chlorophyll a in Aquatic
  Environments 1980*, Methods for the Examination of Waters and Associated Materials, HMSO, ISBN 0 11 751674 0
  (`https://standingcommitteeofanalysts.co.uk/wp-content/uploads/Blue_Book_Library/65.pdf`, a scanned copy, read page
  by page). In summary:
  - A1.1 gives the substance determined as chlorophyll a.
  - Section A: filter about 1 litre through a glass-fibre filter, extract in 90% v/v acetone, read absorbance at 665 nm
    and subtract 750 nm for turbidity, then chlorophyll a = 11.9 × A × v ÷ (d × V) µg/l (step A8.24).
  - Note (t) to that step says the calculation "makes no correction for the presence of degraded matter or of other
    pigments". Note (r) says the 11.9 factor makes an arbitrary allowance for absorbance by other pigments.
  - A3.1 and A3.2: chlorophylls b and c, carotenoids and degradation products (phaeophytin, phaeophorbide) add to the
    absorbance at 665 nm, and A3.2 calls degradation products the more serious effect.
  - Section D1 is an optional extra step: acidify the acetone extract and read again, giving the undegraded
    chlorophyll a as 11.9 × 2.43 × (A₆₆₅ before − A₆₆₅ after) × v ÷ (d × V).
- **EA-commissioned guidance, for context only.** SNIFFER WFD38, *Chlorophyll and Phosphorus Classifications for UK
  Lakes* (Carvalho et al., October 2006; project manager at the Environment Agency;
  `https://nora.nerc.ac.uk/id/eprint/3305/1/WFD38_WP2_Final_report_e_version.pdf`), Appendix 2, page 81, recommends
  cold 90% acetone with an acidification step. That is a recommendation, not a statement of what the laboratory does.
- **A metadata check, values dropped.** One listing request for determinand 5122 (phaeophytin, acetone extract),
  May to September 2025, every point type in England, through `wqa_meta.keep_only`. The service answered HTTP 204 No
  Content: no rows. So in that season the EA published no phaeophytin result from the acetone extract.

What is established and what is inferred:
- **Established:** the EA's laboratory runs one accredited chlorophyll test. It is acetone extraction with
  spectrophotometry, following the SCA 1980 chlorophyll a method. That method measures chlorophyll a at 665 nm in 90%
  acetone. Its standard result is not corrected for degradation products or other pigments.
- **Inferred, not confirmed:** that 7887 holds the result of that test. The label "Chlorophyll : Acetone Extract"
  matches the test name, and it is the only chlorophyll code at lakes. But no EA source names code 7887 next to the
  test.
- **Unresolved:** whether 7887 is the uncorrected value (step A8.24) or the acid-corrected value (section D1). No
  phaeophytin row in summer 2025 points weakly to the uncorrected value. The in-house method "SX I Chlorophyll UVV" is
  not published, and it would settle this. So would an answer from NLS Customer Services (nls@environment-agency.co.uk).

What this means for the test: 7887 is best read as **spectrophotometric chlorophyll a, probably not corrected for
phaeopigments**. It is not total chlorophyll and not a + b by label. Phaeopigments and chlorophylls b and c may raise
it. NDCI responds to red-edge absorption by the same pigment group, so this does not change the question. The results
must still not claim agreement with "laboratory chlorophyll-a" in a stricter sense than this. They should say
"EA acetone-extract chlorophyll (determinand 7887), spectrophotometric, phaeopigment correction not stated".

Requests for this check: 8 to the EA host (API description, codelist 7887, old definitions URL, downloads page,
API-docs page, two codelist searches, one 5122 listing), 1 to ukas.com, 1 to standingcommitteeofanalysts.co.uk,
1 to nora.nerc.ac.uk, 1 to wfduk.org (404), and 5 web searches.

## Results

None yet.
