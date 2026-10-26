# Satellite algae readings at lake bathing waters: the test, stated before any run

Written 26 October 2026. Nothing has been run. No satellite pixel has been read at any bathing water, and no EA algae
check has been paired with a satellite reading. Results go below the line at the end. Nothing above it changes after a
result is seen.

## Why

Lakes are where the site says least. They get no E. coli estimate: both lower lines failed on 26 October
(`docs/LAKE-ECOLI-LINE-TEST-2026-10.md`). What a lake spot does show about algae is the EA sampler's visual check
(`src/dipcast/algae.py`): the latest one, dated, and this season's tally. Samplers visit about once a week in season,
so the check can be days old, and nothing is known between visits.

Sentinel-2 passes over England every few days. Its red and red-edge bands respond to chlorophyll in the water. Ethan
asked whether a satellite reading could fill the gap between checks.

The question: **does a Sentinel-2 chlorophyll index, read at a lake bathing water from the latest clear pass, rank
the EA's algae checks well enough, and add enough to the month and the last check, to be worth showing beside the
check?**

What it cannot answer, whatever the result:
- **Toxic or not.** Sentinel-2 has no band at the phycocyanin peak (about 620 nm), the pigment that marks blue-green
  algae (cyanobacteria). The index responds to chlorophyll in any algae. The EA check does not tell blue-green from
  harmless kinds either (`algae.py`). So this test can only ever support "more algae than usual", never "toxic algae".
- **Safety.** Nothing here is a health figure.

## The outcome: the EA algae check

At each sampling visit the sampler records one of four levels, determinand 4824 in the Water Quality Archive, as
`algae.LEVELS` maps them:

| EA wording | Level |
|---|---|
| No material present | 0 |
| Trace present - 1 or 2 items | 1 |
| Some at intervals - 3 to 6 items | 2 |
| Sufficient to be objectionable >6 items | 3 |

Two outcomes, each judged on its own:
- **A, algae seen:** level 1 or more.
- **B, objectionable:** level 3.

A check whose wording is not in `algae.LEVELS` is dropped and counted, as `algae.by_site` does. Every sampling purpose
is kept, as `ingest.wqa.fetch_algae` keeps it: a follow-up visit is still a look at the water that day. A sensitivity
table with statutory visits only (purpose MS) is reported as description.

**Which checks.** The 18 lake bathing waters in `data/raw/bathing_waters_inland.json` (`kind` = lake), checks dated
1 May to 30 September, 2020 to 2026. The harness fetches them with `fetch_algae` from each site's `wqa_point`, once,
in stage 2 below.

They sit on 12 water bodies, which are the clusters for every interval and every hold-out:

| Water body | Bathing waters |
|---|---|
| Windermere | Lakeside YMCA, Millerground Landing, Rayrigg Meadow, Fellfoot |
| Coniston Water | Brown Howe, Boating Centre, Monk Coniston |
| Rutland Water | Whitwell Creek, Sykes Lane |
| Derwent Water | Crow Park |
| Colwick Country Park, West Lake | Colwick |
| Cotswold Country Park lake | Cotswold Country Park and Beach |
| Hampstead Heath Ladies Pond | Ladies Pond |
| Hampstead Heath Men's Pond | Mens Pond |
| Hampstead Heath Mixed Pond | Mixed Pond |
| The Serpentine | Hyde Park |
| Frensham Great Pond | Frensham |
| Henleaze Lake | Henleaze |

Some will drop out at the size rule below. Which ones is decided by pixels alone, before any check is joined.

## The satellite reading

**Source.** Sentinel-2 Collection 1 Level-2A (`sentinel-2-c1-l2a`) from Element 84's Earth Search STAC API
(`https://earth-search.aws.element84.com/v1`), which serves the AWS open-data copy. No account. Assets used: `red`
(B4, 665 nm, 10 m), `rededge1` (B5, 705 nm, 20 m) and `scl` (the scene classification, 20 m). Each item's
`raster:bands` scale and offset are applied as given. The harness stops if an item lacks them, because the
reflectance offset changed with processing baseline 04.00 in January 2022 and a missing offset would shift every later
reading.

**The index.** NDCI, the normalised difference chlorophyll index (Mishra and Mishra 2012, Remote Sensing of
Environment 117:394–406, doi 10.1016/j.rse.2011.10.016):

NDCI = (B5 − B4) ÷ (B5 + B4)

B4 is averaged from 10 m to the 20 m grid (2 × 2 mean). NDCI was built for turbid, productive water. It is used here
because it needs no fitting: with this few events, a fitted retrieval would be tuned on the outcomes it is judged on.

**Where, per bathing water.** Fixed once, from pixels alone, before any check is fetched:
1. Every `sentinel-2-c1-l2a` item over the point, 1 May to 30 September 2020–2026, on the 20 m grid of the item's
   tile.
2. **The water mask.** A pixel is water if SCL says water (class 6) in at least half of the items where it is not
   cloud, cloud shadow, cirrus or snow (classes 3, 8, 9, 10, 11). One mask per site and tile, from all seasons
   together. A per-scene mask is not used: a dense surface scum can look like land to the classifier, so it would
   drop exactly the scenes that matter.
3. **The site's water.** The connected piece of the mask (8-neighbour) that holds the water pixel nearest the point,
   cut to 300 m from the point. This keeps the three Hampstead ponds apart.
4. **Core pixels.** Water pixels whose 8 neighbours are all water. This keeps one pixel off the shore, where land
   light leaks into the reading.
5. **The size rule.** A site with fewer than 9 core pixels on its tile gets no reading and is out of the test. It is
   listed, with its pixel count.

**Per scene.** A scene is usable at a site when at least 80% of the site's core pixels are clear (SCL class 6, 4, 5,
7 or 2: not cloud, shadow, cirrus, snow or no data). The site's reading is the median NDCI over its clear core pixels.
Where two items fall on the same date (tile overlap), the one with more clear core pixels is used; on a tie, the first
by item id.

**Pairing.** A check on local date d takes the latest usable scene dated d − 3 to d (the scene's UTC date; passes are
near 11:00 UTC). This is what a page could have shown that day. A check with no such scene has no reading. The share
of checks with a reading is reported per site and year.

**Blinding.** Stage 1 reads every usable scene at every site, not only scenes near check dates. It writes
`features.parquet` (site, scene date, item id, clear core pixels, median NDCI) and its SHA-256. That hash is
committed before stage 2 fetches a single check. Stage 2 refuses a features file whose hash differs.

## The candidates and the references

Fitted per hold-out fold, from that fold's training rows only, as logistic regressions on standardised inputs
(scikit-learn `LogisticRegression`, C = 1, as `ecoli.fit`).

**The references:**
- **R1, the base rate.** The training share of checks with the outcome.
- **R2, month and last check.** Inputs: the month (May to September, one-hot) and the previous check's level at the
  same bathing water in the same season (one-hot 0 to 3, plus "none" for a season's first check). This is roughly
  what the site already shows: the latest check, and the time of year.

**The candidates:**
- **M1, NDCI alone.** Input: the paired reading.
- **M2, R2 plus NDCI.** R2's inputs and the paired reading.

Every model and reference is scored on the same rows: checks with a reading, at sites past the size rule.

## The hold-outs

- **Leave one water body out (LOWO), the main one.** Each water body is predicted by models that never saw it. This
  matches the use: a reading at a lake the model was not fitted on.
- **Leave one season out (LOSO).** Each of 2020 to 2026 held out in turn.

**Intervals.** Cluster bootstrap with water bodies as clusters, 2,000 resamples, numpy `default_rng(20261026)`. Two
outcomes are judged, so each interval is 97.5% (1.25th to 98.75th percentile).

## The test, for each outcome

### The gate, checked first

The outcome is judged only if the paired rows hold:
- at least 30 checks with the outcome;
- at 4 or more water bodies;
- at least 5 in each of 3 or more seasons.

Below that it is "too few to judge". Its scores are reported as description. It cannot pass.

### The primary comparison, with the near-miss labels

The primary comparison is **M2 against R2, LOWO, the Brier gain** (R2's Brier minus M2's). It asks whether the
satellite adds anything to the month and the last check. The label comes from the framework in the addendum to
`docs/LAKE-ECOLI-LINE-TEST-2026-10.md`: Better, Promising not shown, No useful difference, Possible harm, Harm, Too
uncertain, the first that fits, from the point gain d and the 97.5% interval (L, U).

**The margins B and H, and how they were set.** The framework sets B from predictions crossing a band cut. Algae has no
band on the site, so that method has nothing to work from. B is set instead as 2% of the Brier score of a constant
forecast at the published lake rate, the same 0.02 skill used as the bar in the E. coli line test. The rate is the
one already in `algae.py`'s docstring (28 September 2026), seen before this test was thought of: 310 of 1,304 lake
checks with algae seen since 2023, 63 objectionable. It is an outcome rate, not the result of any test of this index.
H is half of B.

| Outcome | Rate used | Constant-forecast Brier p(1 − p) | B | H |
|---|---|---|---|---|
| A, seen | 310 ÷ 1,304 = 0.2377 | 0.1812 | 0.0036 | 0.0018 |
| B, objectionable | 63 ÷ 1,304 = 0.0483 | 0.0460 | 0.0009 | 0.00046 |

These figures stay fixed whatever the rate turns out to be in the 2020–2026 rows.

### An outcome passes if the primary label is Better and all of these hold

1. **Ranking, unfitted.** The AUC of the raw reading against the outcome, pooled over all paired rows, is at least
   0.65, and its interval's lower end is above 0.50. No model is fitted, so no hold-out is needed.
2. **LOWO, M1 against R1.** Brier gain at least B, interval lower end above zero.
3. **LOSO, M2 against R2.** The pooled gain is above zero, and it is above zero in at least two-thirds of the seasons
   with 5 or more events (rounded up).
4. **Placebo.** The readings are shuffled within each water body and season, 200 times, numpy
   `default_rng(20261026)`. The pooled AUC (condition 1) is recomputed on each. The real AUC must be above the 95th
   percentile of the 200 (above the 190th when ranked). Shuffling within a water body and season keeps how green each
   lake is that year and breaks the link to the day. Eutrophic lakes such as Rutland and Colwick may have both more
   algae checks and higher NDCI all season. Condition 1 alone would reward that. This condition asks for signal in the
   day.
5. **No group labelled Harm.** The primary comparison is labelled separately for the Lake District lakes (Windermere,
   Coniston, Derwent Water) and the lowland waters (the rest), with the same B and H. Neither may be Harm.
6. **Calibration.** In LOWO, M2's mean forecast is within 0.03 (A) or 0.01 (B) of the observed rate.
7. **Stop rules.** Stage 2 makes 0 network attempts after the checks are fetched. The features hash matches the
   committed one. Every item had its scale and offset. The level map reproduces `algae.LEVELS` exactly. If any fails,
   the run stops and that is reported before any score.

**Promising, not shown** on the primary comparison, with conditions 1 and 4 to 7 holding, goes to the 2027 forward
step below. It is not adopted.

Why these margins. An AUC of 0.65 is the bar the lake E. coli line test used. The placebo is the condition that
matters most: a reading that only tells Rutland from Coniston adds nothing a swimmer does not already know from the
season tally.

## What follows

**Whatever the verdict, nothing on the live site changes in this PR or because of it.**

**An outcome passes.** Ethan decides whether lake spots show a satellite reading. If yes, it comes in separate PRs:
- the reading as an observation beside the EA check, dated by the scene, never changing a level, never saying toxic,
  blue-green or safe. Wording decided then. For example: "Satellite, 14 Aug: greener than usual for this lake."
- the Copernicus attribution the Sentinel data terms require (below);
- the live fetch: one STAC query and a few small reads per lake per day. No Open-Meteo calls. Its failure must not
  stop a build, as with `refresh_algae`.

**Too few to judge, or fails.** Lakes keep the EA check only. This PR stays as the record.

## The forward part: 2027

2020 to 2026 will have been seen. A clean test is 2027. It runs if the retrospective result for an outcome is Better
or Promising not shown, and Ethan approves a shadow log.
- **Frozen.** M2 for that outcome, fitted on all paired rows, saved with its SHA-256 in a dated amendment to section 17
  of `docs/PREREGISTRATION-2027.md` before 1 May 2027. The water masks are frozen with it. No refit after that.
- **Logged.** A daily job, not part of the site build, logs each lake site's latest usable reading and M2's figure.
  Nothing is shown.
- **Scored.** EA algae checks from 1 May to 30 September 2027, paired as above, primary comparison with the same B and
  H. It must be labelled Better. A second Promising is not stacked on the first.
- **Size.** About 300 lake checks a season, going by the 1,304 over four seasons from 2023. Most will be lost to cloud.
  Outcome B is very likely too few to judge in a single season. The power calculation the framework asks for is
  made before 1 May 2027, from the spread of the per-water-body gain in this retrospective run (other data, so
  allowed). If one season cannot reach 80% power for a gain of B, that is stated then and 2027 is description only.

## What is expected, stated now

These are guesses.
- **Clouds take most checks.** I expect a third or fewer of checks to have a usable scene within 3 days.
- **Small ponds drop out.** The Hampstead ponds and Henleaze are likely to fail the size rule at 20 m with a
  one-pixel shore margin. The Serpentine and Frensham may too.
- **Outcome B is likely too few to judge.** 63 objectionable checks from 2023, before cloud, at a few lakes.
- **Outcome A, if judged, most likely passes condition 1 and fails condition 4 and the primary comparison.** NDCI will
  separate green lakes from clear ones. Whether it tracks the day is the open question. The EA check is one person
  looking at the shore. Wind piles scum against one shore and leaves open water clear. A 20 m pixel 20 m offshore
  may not see what the sampler sees.
- My overall expectation: neither outcome passes. "Promising, not shown" for A is the likeliest good result.

## Not chosen, and why

- **CyFi** (DrivenData, MIT licence, `github.com/drivendataorg/cyfi`). It estimates cyanobacteria cells per ml from
  Sentinel-2 with a trained model. Its labels are in-situ samples from across the US. It outputs a quantity the EA check
  does not measure. It brings a full machine-learning stack. If NDCI shows day-level signal here, CyFi is a candidate
  for a later, separately stated test.
- **The UK Lakes Observatory** (University of Stirling with UKCEH; Hunter and others). From slides and a conference
  paper, not an official product page: weekly Sentinel-2 chlorophyll-a at 20 m for over 900 UK water bodies, with
  algorithms picked per pixel by optical water type and calibrated on UK regulatory data. It would likely beat raw
  NDCI. Its current status and licence are not confirmed. A licence question comes first, as with UKCEH's Bloomin'
  Algae reports (`docs/ROADMAP-2026-10.md`, task 9).
- **Sentinel-3 OLCI.** It has bands near 620 nm, but 300 m pixels. Only the largest lakes here (Windermere, Rutland,
  Derwent Water, Coniston) could hold even a few pixels clear of the shore, and none of the ponds. Not counted.
- **A different atmospheric correction** (for example ACOLITE, built for water). Level-2A uses Sen2Cor, which is made
  for land. ACOLITE would add a processing step per scene and choices to tune. It is left for a later test if NDCI on
  Level-2A shows signal.
- **A wider pairing window.** Algae can change within days. 3 days is fixed now and not tuned. 0 and 7 days are
  reported as description only.

## Data terms

- **Sentinel data.** Copernicus Sentinel data is free to use, with attribution when modified. The usual wording is
  "Contains modified Copernicus Sentinel data [year]". The ESA legal notice the STAC collection links to
  (`sentinel.esa.int/documents/247904/690755/Sentinel_Data_Legal_Notice`) did not resolve on 26 October 2026, so that
  wording is from memory, not read. It must be read before any reading goes on a page. The test itself publishes only
  aggregate scores.
- **EA algae checks.** Water Quality Archive data, already used on the site (`algae.py`).

## Running

- The harness is `scripts/lake_algae_sat_eval/`. It is committed after this file is pushed and before any score.
  The statement above the line does not change when it is added. Reading the images needs a raster library
  (`rasterio`); it goes in a new optional dependency group, as `nn` and `radar` do, and the build never installs it.
- **Stage 1, online, outcome-blind.** STAC search and windowed reads of the three assets at each site. One process,
  one request at a time. Its log counts items found, read and failed. Estimate, not checked: about 1,000 items per
  site area over seven seasons, three small reads each. It writes the masks, `features.parquet` and the hash. The hash
  is committed.
- **Stage 2, offline after one fetch.** From a `git archive` of the harness commit, in a scratch folder. It fetches the
  algae checks once, saves them with their hash, then scores with every outgoing connection refused and counted
  (`scripts/lake_distance_eval/run_offline.py`).
- The order in stage 2: stop rules; the gate counts for both outcomes; then the scores.
- One run, alone. No other evaluation, training, build or test on this machine at the same time.
- It runs after Ethan has read this statement.

## Download caps

Written here and in `scripts/lake_algae_sat_eval/net.py` (26 October 2026) before any request went through the
harness. Every public request the harness makes, in the coverage prototype, stage 1 and stage 2's metadata, goes
through that one client.
- One request at a time. At least 1 second between requests. A 60-second timeout on each.
- At most 300 requests and 100 MB per run.
- The coverage prototype, all its runs together: at most 900 requests and 300 MB, counted in a ledger file (one line
  per request: time, URL, status, bytes).
- At most 32 MB in any one response.
- Stop at once on HTTP 429 or any 5xx, and on any status other than 200 or 206. Nothing is retried.
- Only these hosts: Earth Search's STAC API, the two public AWS buckets that hold its Sentinel-2 files, and the CDSE
  catalogue and STAC search endpoints (search only). No account, token, key or cookie is ever sent; the client refuses
  a request that carries one.

Stage 1 over all 18 sites and seven seasons would pass the per-run cap. It runs in as many runs as it needs, each
under the per-run caps, and resumes from what earlier runs wrote.

## What will be reported

Whatever the verdict:
- the size rule: core pixels per site and tile, sites in and out;
- pairing: checks, checks with a reading, days from scene to check, per site and year;
- the gate counts for each outcome, by water body and season;
- the primary label with d, L, U, B and H;
- each condition with its figure and interval;
- LOWO and LOSO tables: R1, R2, M1, M2, Brier and AUC, per outcome;
- AUC per water body, as description;
- the 200 placebo AUCs (lowest, median, 95th percentile, highest);
- the 0- and 7-day pairing windows and the statutory-only checks, as description;
- the features and checks hashes, the harness commit, and the network-attempt counts.

## Seen before writing

- `algae.py`'s docstring tallies (28 September 2026): 2,925 checks at the 38 bathing waters since 2020; from 2023,
  algae seen in 310 of 1,304 lake checks (63 objectionable) and 64 of 1,012 river checks (11). No other count of
  checks was made, by site, season or level.
- The 18 lake bathing waters and their points, from `data/raw/bathing_waters_inland.json`.
- Earth Search metadata only: the `sentinel-2-c1-l2a` collection (its asset names and licence link), and one search
  over Millerground Landing for 1 May to 30 September 2025 that returned 186 items (Sentinel-2A 60, 2B 62, 2C 64),
  and one for early May 2020 that returned items with `rededge1` and `scl`. No asset was read.
- CyFi's repository and documentation pages; search results about the UK Lakes Observatory; the NDCI citation.
- No satellite pixel has been read. No check has been paired with a scene. No score of any kind has been computed.

---

## Results

None yet.
