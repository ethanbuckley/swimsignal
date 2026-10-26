# Satellite algae readings at lake bathing waters: the test, stated before any run

Written 26 October 2026 and revised the same day, before any run. Nothing has been scored. No EA algae check has been
fetched for this test, and none has been paired with a satellite reading. No B4 or B5 pixel and no CLMS pixel has
been read. The only pixels read are scene classification (SCL) windows at three sites in 2025, for the coverage count
below. Results go below the line at the end. Nothing above it changes after a result is seen.

## Revisions before any run

All on 26 October 2026, at Ethan's request, after the first version (b558da0) and before any reading or check was
seen. What was seen while making them is listed in "Seen before writing".
1. **Download caps.** Written into this file and into `scripts/lake_algae_sat_eval/net.py` (ef64038, 18:40 UTC)
   before the first request through the harness (18:41 UTC). Stage 1's own caps were added after the coverage
   prototype and before any stage 1 request.
2. **The Copernicus Land Monitoring Service (CLMS) Lake Water Quality product is now the first candidate**,
   benchmarked before any custom NDCI processing, with an order and a decision rule ("The readings, in order"). Why: a
   finished product, with its own cloud masking and a water-specific atmospheric correction, should be tried before
   building one. What was found makes it unlikely to apply: its record starts in September 2024, the manual's map shows
   no processed granule in England, and reading a pixel needs a CDSE account. Those are reasons to state the rule, not
   to skip it.
3. **2022 has no reading.** Earth Search's `sentinel-2-c1-l2a` holds no item at any of the 18 sites from May to
   September 2022 (coverage count, 26 October). The test does not fill the gap from the older `sentinel-2-l2a`
   collection: it uses a different processing baseline, and mixing them would change the reading partway through the
   record. 2022 checks are counted, with no reading.
4. **The coverage count.** Metadata for all sites and seasons, and SCL at three sites in 2025. Valid-or-not only; no
   band value, no check, no score. Its counts are below.
5. **Data terms** rewritten from the texts themselves, with the attribution wording quoted.
6. **Harness choices** made explicit (a separate section): the water mask's denominator also leaves out SCL 0 and 1,
   the connected piece is found within 1 km of the point, pixels with no valid NDCI are left out, and a label case the
   framework does not cover ("Unlabelled", which cannot pass).
7. **Stage 1 is split** into 1a (SCL masks only) and 1b (B4, B5 and NDCI), so the CLMS benchmark can sit between them.
8. **Between-image bloom forecasting** is named as a later, separately stated test.

## Why

Lakes are where the site says least. They get no E. coli estimate: both lower lines failed on 26 October
(`docs/LAKE-ECOLI-LINE-TEST-2026-10.md`). What a lake spot does show about algae is the EA sampler's visual check
(`src/dipcast/algae.py`): the latest one, dated, and this season's tally. Samplers visit about once a week in season,
so the check can be days old, and nothing is known between visits.

Sentinel-2 passes over England every few days. Its red and red-edge bands respond to chlorophyll in the water. Ethan
asked whether a satellite reading could fill the gap between checks.

The question: **does a satellite chlorophyll reading at a lake bathing water, from the latest one available on the
day, rank the EA's algae checks well enough, and add enough to the month and the last check, to be worth showing
beside the check?**

What it cannot answer, whatever the result:
- **Toxic or not.** Sentinel-2 has no band at the phycocyanin peak (about 620 nm), the pigment that marks blue-green
  algae (cyanobacteria). Chlorophyll is in all algae. The EA check does not tell blue-green from harmless kinds either
  (`algae.py`). So this test can only ever support "more algae than usual", never "toxic algae".
- **The CLMS floating cyanobacteria layer is not a toxin measurement either.** Its manual describes it as a
  "Probability of floating cyanobacteria" from 0 to 1, from a floating algae index and a water index test that tells
  floating cyanobacteria from floating plants (PUM, sections 3.2.1 and 4.4.1). It flags a surface scum that looks like
  cyanobacteria. It does not measure toxins, and not every cyanobacteria bloom is toxic. It is reported here as
  description only.
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

## What each source can give, counted before the test

### CLMS Lake Water Quality, 100 m, version 2

Read on 26 October 2026 from the product page (https://land.copernicus.eu/en/products/water-bodies/lake-water-quality-v2-0-100m
and its JSON at `land.copernicus.eu/api/en/products/water-bodies/lake-water-quality-v2-0-100m`, whose own address is
now `.../lake-water-quality-v2-2-100m`), the CDSE news item of 18 February 2026
(https://dataspace.copernicus.eu/news/2026-2-18-guide-newly-launched-clms-datasets), the Product User Manual
(`CGLOPS2_PUM_LWQ100_S2_v2.0.0_I1.02`, 24 July 2024, marked "draft – pending review",
https://land.copernicus.eu/en/technical-library/product-user-manual-lake-water-quality-100m-version-2.0/@@download/file),
the EEA metadata record (https://sdi.eea.europa.eu/catalogue/srv/api/records/deae3db1-a214-4375-8d1a-63c42498050e)
and the CDSE documentation for CLMS, OData and S3. The ATBD and QAR the manual cites were not found as links and were
not read.

- **Variables** (PUM 4.4.1): mean turbidity, mean total suspended matter, mean chlorophyll-a (`chla_mean`), a trophic
  state index, a "representative" water-leaving reflectance spectrum, `floating_cyanobacteria` (probability, 0 to 1),
  observation counts and dates per pixel, and `quality_flags` naming L1_invalid, bright_pixels, cloud, snow_ice, land,
  turbidity_invalid, chla_invalid, tsm_invalid, atmospheric_correction_failure, floating_cyanobacteria and
  floating_macrophytes_or_mixed_pixel. The manual names the flags but not their bits.
- **Sensor and resolution:** Sentinel-2 MSI, bands resampled to 100 m; Polymer atmospheric correction, which works
  over water; the product page says "Sentinel-2 MSI", 100 m. The EEA record's lineage says "SENTINEL-3 data"; that
  looks like an error carried from the 300 m product (inferred, not confirmed).
- **Time:** 10-day composites (dekads: days 1–10, 11–20, 21 to month end), not single passes (PUM 4.5.3). Per pixel,
  the chlorophyll is the mean over the dekad's valid observations.
- **Period:** the page says "2024-present"; its description says "from September 2024 to present". The CDSE catalogue
  agrees: 155 products, first dekad 1 September 2024, last 11 October 2026. In the May–September seasons that is 3
  dekads in 2024 (September), 15 in 2025 and 15 in 2026. Version 1 (100 m, 2019–2024) has no chlorophyll or
  cyanobacteria layer (CDSE news).
- **Lag:** the page states "Within 4 days after the end of the synthesis period". In the CDSE catalogue the shortest
  gap from a dekad's end to its publication was 2.3 days (which dekad was not recorded). Most dekads were loaded in
  bulk in October 2026 (median 373 days after their end), so catalogue dates do not measure the production lag for
  them.
- **Clouds and shores:** pixels are classed by IdePix as water, land, mixed, cloud, cloud shadow, haze or snow and ice,
  and only water pixels go to the atmospheric correction (PUM 3.2.1). On shores the manual says: "The 100m products
  include near-shore areas that may be shallow. Such areas are not yet flagged." (PUM 3.3).
- **Which lakes:** the manual says the 100 m products "cover 225 Sentinel-2 granules" in Europe and Africa, and "All
  water pixels within those granules are processed" (PUM 4.5.2). There is no minimum lake size and no lake list; the
  granule list is only a map (Figure 2). At the map's resolution it shows one granule over Great Britain, in
  Scotland, and none over England. **Inferred, not confirmed: none of our 12 water bodies is in the product.** The map
  dates from July 2024 and the granule set may have changed. Every product is one global file (catalogue footprint:
  the whole globe), so the catalogue cannot say which lakes hold data. Settling it needs one pixel read at each site,
  which needs an account (next point).
- **Access, and the blocker.** Each dekad is one global file: netCDF 0.38–1.87 GB, COG 7.4–9.0 GB (catalogue).
  - CDSE OData catalogue search: works without an account (used here; two requests were refused, HTTP 403, until the
    client's user-agent string was made plain).
  - CDSE OData download: "only authorized users are allowed to download data products" (CDSE OData documentation); a
    token comes from an account login.
  - CDSE S3 (`/eodata/CLMS/bio-geophysical/lake_water_quality/lwq-nrt_global_100m_10daily_v2`): "you must have a
    registered account" to make the keys (CDSE S3 documentation).
  - Sentinel Hub and the Copernicus Browser: CDSE login. Not tried.
  - The land.copernicus.eu "Download" section points to CDSE. Its older VITO manifest
    (`globalland.vito.be/download/manifest/lwq_100m_v2_10daily-nrt_netcdf/`) did not answer on 26 October (HTTP/2
    stream error).
  - A WMTS for the dataset (`land.copernicus.eu/cdse/lwq_nrt_global_100m_10daily_v2`) lists rendered layers
    (CHLAMEAN, FCBPROB, TSI and others). Only its capabilities were read. No tile was requested: a tile is a picture
    of values, which the blinding forbids, and not data.
  - WEkEO: not checked.

  **No route to CLMS pixels works without an account. No account was created.** Whether to make one (a free CDSE
  registration) is Ethan's decision. Until then CLMS coverage stays at the metadata above.

### Sentinel-2 Level-2A on Earth Search (the custom reading's source)

Metadata for all 18 sites, May to September 2020–2026, and SCL windows at three sites in 2025
(`docs/LAKE-ALGAE-SATELLITE-TEST-2026-10-coverage.json`). Counts only.
- **Items and dates per site and season.** 2020, 2021, 2023, 2024: 60–62 dates at every site but Frensham (30–31).
  2025 and 2026, with Sentinel-2C: 75–77 dates (Frensham 45). Windermere's sites lie on two tiles, so they have about
  twice as many items as dates. Median gap between dates 2 to 3 days (Frensham 3 to 5); longest gap 3 to 5 days (Frensham 7 in
  2025).
- **2022: no item.** At all 18 sites, May–September 2022 returns nothing from `sentinel-2-c1-l2a`. Over the whole of
  2022, Millerground Landing has 22 C1 items, all in March and December. The older `sentinel-2-l2a` collection has 124
  items on 61 dates there, May–September 2022 (processing baseline 04.00). See revision 3.
- **Tile cloud flag.** Dates with at least one item under 50% tile cloud: 8 to 31 per site and season. This is a tile
  figure, not the site's.
- **Scale and offset.** All 7,317 items fetched with their band metadata (97 of the 126 site-seasons) carry
  `raster:bands` scale and offset on B4 and B5. The other 29 site-seasons were counted without it (the request that
  includes it costs about 14 KB an item). The stop rule still checks every item in stage 1.
- **Publication lag.** Item creation minus sensing time, median per site and season: about 5 hours in 2024–2026. Earlier
  items were reprocessed later (about 6 months after sensing for 2023, 2.5 years for 2021, 3.5 years for 2020), so
  their lag says nothing about a live service.
- **SCL at three sites, 2025** (45 scenes each, evenly spaced through the season, on the tile with most items; the
  mask here is from these 45 scenes, not all seasons as stated, so the counts are a preview):

| Site | Tile | Water pixels in 2 km window | Site pixels (300 m) | Core pixels | Size rule | Usable scenes (dates) | Gap between usable dates, median / longest |
|---|---|---|---|---|---|---|---|
| Windermere, Millerground Landing | 30UVF | 4,203 | 362 | 323 | passes | 8 of 45 (8) | 25 / 31 days |
| Rutland Water Whitwell Creek | 30UXD | 4,233 | 120 | 74 | passes | 8 of 45 (8) | 10 / 62 days |
| Hampstead Heath (Ladies Pond) | 30UXC | 21 | 7 | 0 | fails | 0 | – |

  With half the scenes read, the gaps are longer than they would be with all of them. About 1 scene in 6 was usable
  at the two lakes.

## The readings, in order

**Order.** Stage 1a (SCL masks); then stage 0 (the CLMS benchmark); then stage 1b (custom NDCI) only where CLMS
cannot serve; then stage 2. Every step before stage 2 is outcome-blind.

### Stage 0: CLMS first

It runs only if Ethan approves a CDSE account. Its fetch is not written yet; it will be, with its own caps, before any
CLMS pixel is read. Its rules are fixed now (`protocol.py`, `clms_*`):
- **Pixels at a site.** CLMS pixels whose centre lies on one of the site's core pixels from stage 1a, within 300 m of
  the point. This uses the 20 m shore margin, because CLMS does not flag near-shore pixels. A site needs at least 3 such
  pixels.
- **Valid pixel in a dekad.** `chla_mean` finite and above zero, and none of these flags set: L1_invalid,
  bright_pixels, cloud, snow_ice, land, chla_invalid, atmospheric_correction_failure,
  floating_macrophytes_or_mixed_pixel. The flag bits are read from the file's own flag attributes; a file without any
  of these flags stops the run. `floating_cyanobacteria` does not make a pixel invalid: it is the bloom.
- **Reading.** log10 of the median `chla_mean` over valid pixels, when at least 3 are valid. Otherwise the dekad has no
  reading at that site.
- **Pairing.** A check on local date d takes the latest dekad at its site whose end plus 4 days is on or before d: the
  stated timeliness, so what a page could have shown that day.
- **Covered.** A water body is covered when one of its sites has a reading in at least 8 of the 15 dekads of May to
  September 2025. Valid-or-not only: no value is looked at to decide this.
- **The decision rule.** If at least 4 water bodies are covered, **CLMS is the primary reading** at those water
  bodies, and stage 1b reads NDCI only at the water bodies CLMS does not cover. If fewer than 4 are covered, or no
  account is approved, CLMS is reported as coverage only and NDCI is the primary reading everywhere, as first stated.
- **If CLMS is judged.** The same references, candidates (M1c: the CLMS reading; M2c: R2 plus it), hold-outs, labels,
  margins and conditions as below, on checks at covered water bodies, September 2024 to September 2026. Its gate needs
  30 events at 4 or more water bodies and at least 5 in each of 2025 and 2026: its record starts in September 2024,
  so three seasons with 5 cannot be asked. NDCI is then judged on its own rows. Four comparisons are judged (two
  readings, two outcomes), so every interval in both is 98.75% (0.625th to 99.375th percentile). The
  `floating_cyanobacteria` median is reported as description only, never judged.

What is expected of stage 0: no water body covered, so NDCI stays the primary reading (from the granule map; inferred).

### Stage 1: the custom reading, NDCI from Level-2A

**Source.** Sentinel-2 Collection 1 Level-2A (`sentinel-2-c1-l2a`) from Element 84's Earth Search STAC API
(`https://earth-search.aws.element84.com/v1`), which serves the AWS open-data copy. No account. Assets used: `red`
(B4, 665 nm, 10 m), `rededge1` (B5, 705 nm, 20 m) and `scl` (the scene classification, 20 m). Each item's
`raster:bands` scale and offset are applied as given. The harness stops if an item lacks them, because the
reflectance offset changed with processing baseline 04.00 in January 2022 and a missing offset would shift every later
reading. 2022 has no item (revision 3).

**The index.** NDCI, the normalised difference chlorophyll index (Mishra and Mishra 2012, Remote Sensing of
Environment 117:394–406, doi 10.1016/j.rse.2011.10.016):

NDCI = (B5 − B4) ÷ (B5 + B4)

B4 is averaged from 10 m to the 20 m grid (2 × 2 mean). NDCI was built for turbid, productive water. It is used here
because it needs no fitting: with this few events, a fitted retrieval would be tuned on the outcomes it is judged on.

**Where, per bathing water (stage 1a).** Fixed once, from SCL pixels alone, before any check is fetched:
1. Every `sentinel-2-c1-l2a` item over the point, 1 May to 30 September 2020–2026, on the 20 m grid of the item's
   tile.
2. **The water mask.** A pixel is water if SCL says water (class 6) in at least half of the items that saw it: not
   no data, defective, cloud, cloud shadow, cirrus or snow (classes 0, 1, 3, 8, 9, 10, 11). One mask per site and
   tile, from all seasons together. A per-scene mask is not used: a dense surface scum can look like land to the
   classifier, so it would drop exactly the scenes that matter.
3. **The site's water.** The connected piece of the mask (8-neighbour), found within 1 km of the point, that holds the
   water pixel nearest the point, cut to 300 m from the point. This keeps the three Hampstead ponds apart.
4. **Core pixels.** Pixels of the site's water whose 8 neighbours are all in the connected piece. This keeps one pixel
   off the shore, where land light leaks into the reading. The 300 m cut is not a shore.
5. **The size rule.** A site with fewer than 9 core pixels on its tile gets no reading from that tile. A site with no
   tile past the rule is out of the test. It is listed, with its pixel count.

**Per scene (stage 1b).** A scene is usable at a site when at least 80% of the site's core pixels are clear (SCL class
6, 4, 5, 7 or 2). The site's reading is the median NDCI over its clear core pixels with a valid NDCI (B4 and B5 both
above zero). Where two items fall on the same date (tile overlap), the one with more clear core pixels is used; on a
tie, the first by item id.

**Pairing.** A check on local date d takes the latest usable scene dated d − 3 to d (the scene's UTC date; passes are
near 11:00 UTC). This is what a page could have shown that day. A check with no such scene has no reading. The share
of checks with a reading is reported per site and year.

**Blinding.** Stage 1 reads every usable scene at every site, not only scenes near check dates. It writes
`features.parquet` (site, tile, scene date, item id, clear core pixels, core pixels, usable, median NDCI) and its
SHA-256. That hash is committed before stage 2 fetches a single check. Stage 2 refuses a features file whose hash
differs. The same holds for a CLMS features file, if stage 0 runs.

## The candidates and the references

Fitted per hold-out fold, from that fold's training rows only, as logistic regressions on standardised inputs
(`ecoli.fit`: scikit-learn `LogisticRegression`, C = 1).

**The references:**
- **R1, the base rate.** The training share of checks with the outcome.
- **R2, month and last check.** Inputs: the month (May to September, one-hot) and the previous check's level at the
  same bathing water in the same season (one-hot 0 to 3, plus "none" for a season's first check). This is roughly
  what the site already shows: the latest check, and the time of year.

**The candidates** (M1c and M2c, the same with the CLMS reading, if stage 0 makes CLMS primary):
- **M1, NDCI alone.** Input: the paired reading.
- **M2, R2 plus NDCI.** R2's inputs and the paired reading.

Every model and reference is scored on the same rows: checks with a reading, at sites past the size rule.

## The hold-outs

- **Leave one water body out (LOWO), the main one.** Each water body is predicted by models that never saw it. This
  matches the use: a reading at a lake the model was not fitted on.
- **Leave one season out (LOSO).** Each season with rows (2020, 2021, 2023 to 2026; 2022 has none) held out in turn.

**Intervals.** Cluster bootstrap with water bodies as clusters, 2,000 resamples, numpy `default_rng(20261026)`. Two
outcomes are judged, so each interval is 97.5% (1.25th to 98.75th percentile); 98.75% if CLMS is judged too.

## The test, for each outcome

### The gate, checked first

The outcome is judged only if the paired rows hold:
- at least 30 checks with the outcome;
- at 4 or more water bodies;
- at least 5 in each of 3 or more seasons (for CLMS: in each of 2025 and 2026).

Below that it is "too few to judge". Its scores are reported as description. It cannot pass.

### The primary comparison, with the near-miss labels

The primary comparison is **M2 against R2, LOWO, the Brier gain** (R2's Brier minus M2's). It asks whether the
satellite adds anything to the month and the last check. The label comes from the framework in the addendum to
`docs/LAKE-ECOLI-LINE-TEST-2026-10.md`: Better, Promising not shown, No useful difference, Possible harm, Harm, Too
uncertain, the first that fits, from the point gain d and the interval (L, U). If none fits (for example d just under
B with L above zero and U at or above B), the result is "Unlabelled". It cannot pass and does not go to the forward
step.

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

These figures stay fixed whatever the rate turns out to be in the 2020–2026 rows. They apply to CLMS too.

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

## Later, and separately: forecasting blooms between images

This test asks only whether a reading **detects** what the sampler sees on the day. Forecasting a bloom for the days
between images (from the last reading, water temperature, sunshine, wind and rain) is a different question with
different failure modes. It is a separate, later test, stated in its own file, and only if detection here is labelled
Better or Promising not shown. Nothing in this file tests or permits a forecast.

## What follows

**Whatever the verdict, nothing on the live site changes in this PR or because of it.**

**An outcome passes.** Ethan decides whether lake spots show a satellite reading. If yes, it comes in separate PRs:
- the reading as an observation beside the EA check, dated by the scene (or the dekad, for CLMS), never changing a
  level, never saying toxic, blue-green or safe. Wording decided then. For example: "Satellite, 14 Aug: greener than
  usual for this lake."
- the attribution the data terms require (below);
- the live fetch: one STAC query and a few small reads per lake per day (NDCI), or one dekad file read per 10 days
  (CLMS, with an account). No Open-Meteo calls. Its failure must not stop a build, as with `refresh_algae`.

**Too few to judge, or fails.** Lakes keep the EA check only. This PR stays as the record.

## The forward part: 2027

2020 to 2026 will have been seen. A clean test is 2027. It runs if the retrospective result for an outcome is Better
or Promising not shown, and Ethan approves a shadow log.
- **Frozen.** M2 (or M2c) for that outcome, fitted on all paired rows, saved with its SHA-256 in a dated amendment to
  section 17 of `docs/PREREGISTRATION-2027.md` before 1 May 2027. The water masks are frozen with it. No refit after
  that.
- **Logged.** A daily job, not part of the site build, logs each lake site's latest usable reading and the model's
  figure. Nothing is shown.
- **Scored.** EA algae checks from 1 May to 30 September 2027, paired as above, primary comparison with the same B and
  H. It must be labelled Better. A second Promising is not stacked on the first.
- **Size.** About 300 lake checks a season, going by the 1,304 over four seasons from 2023. Most will be lost to cloud.
  Outcome B is very likely too few to judge in a single season. The power calculation the framework asks for is
  made before 1 May 2027, from the spread of the per-water-body gain in this retrospective run (other data, so
  allowed). If one season cannot reach 80% power for a gain of B, that is stated then and 2027 is description only.

## What is expected, stated now

These are guesses.
- **CLMS covers none of our water bodies,** from the manual's granule map (inferred). Without an account it is not
  checked at all.
- **Clouds take most checks.** I expect a third or fewer of checks to have a usable scene within 3 days. The SCL
  preview (about 1 usable scene in 6 at two lakes in 2025) fits that, but it did not look at check dates.
- **Small ponds drop out.** The Hampstead ponds and Henleaze are likely to fail the size rule at 20 m with a
  one-pixel shore margin. The Serpentine and Frensham may too. Ladies Pond had 0 core pixels in the one-season
  preview.
- **2022 is lost** (no C1 items), which leaves six seasons.
- **Outcome B is likely too few to judge.** 63 objectionable checks from 2023, before cloud, at a few lakes.
- **Outcome A, if judged, most likely passes condition 1 and fails condition 4 and the primary comparison.** NDCI will
  separate green lakes from clear ones. Whether it tracks the day is the open question. The EA check is one person
  looking at the shore. Wind piles scum against one shore and leaves open water clear. A 20 m pixel 20 m offshore
  may not see what the sampler sees.
- My overall expectation: neither outcome passes. "Promising, not shown" for A is the likeliest good result.

## Not chosen, and why

- **CLMS Lake Water Quality at 300 m (Sentinel-3), and version 1 at 100 m.** 300 m pixels cannot hold the ponds or
  keep off most shores. Version 1 (2019–2024) has no chlorophyll or cyanobacteria layer.
- **CyFi** (DrivenData, MIT licence, `github.com/drivendataorg/cyfi`). It estimates cyanobacteria cells per ml from
  Sentinel-2 with a trained model. Its labels are in-situ samples from across the US. It outputs a quantity the EA check
  does not measure. It brings a full machine-learning stack. If a reading shows day-level signal here, CyFi is a
  candidate for a later, separately stated test.
- **The UK Lakes Observatory** (University of Stirling with UKCEH; Hunter and others). From slides and a conference
  paper, not an official product page: weekly Sentinel-2 chlorophyll-a at 20 m for over 900 UK water bodies, with
  algorithms picked per pixel by optical water type and calibrated on UK regulatory data. It would likely beat raw
  NDCI. Its current status and licence are not confirmed. A licence question comes first, as with UKCEH's Bloomin'
  Algae reports (`docs/ROADMAP-2026-10.md`, task 9).
- **Sentinel-3 OLCI.** It has bands near 620 nm, but 300 m pixels. Only the largest lakes here (Windermere, Rutland,
  Derwent Water, Coniston) could hold even a few pixels clear of the shore, and none of the ponds. Not counted.
- **A different atmospheric correction** (for example ACOLITE, built for water). Level-2A uses Sen2Cor, which is made
  for land. ACOLITE would add a processing step per scene and choices to tune. It is left for a later test if NDCI on
  Level-2A shows signal. CLMS (Polymer) is the water-specific correction tried first.
- **Filling 2022 from `sentinel-2-l2a`.** Different processing from C1; see revision 3.
- **A wider pairing window.** Algae can change within days. 3 days is fixed now and not tuned. 0 and 7 days are
  reported as description only.

## Data terms

Read on 26 October 2026 from the texts themselves.
- **Sentinel data (the NDCI reading).** The European Commission's "Legal notice on the use of Copernicus Sentinel Data
  and Service Information" (https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice, 2
  pages; the `sentinel.esa.int` address did not resolve). It grants free use for reproduction, distribution,
  communication to the public, and adaptation and combination with other data. Users communicating or distributing
  the data must name the source with "Copernicus Sentinel data [Year]". Where the data have been "adapted or
  modified", the notice to use is "Contains modified Copernicus Sentinel data [Year]". An NDCI reading is modified
  data, so a page would carry the second. The notice cites Regulation (EU) No 377/2014 and Commission Delegated
  Regulation (EU) No 1159/2013. Article 8 of 1159/2013 (read on legislation.gov.uk, which holds the EU text as at 31
  December 2020; EUR-Lex refused automated reads) adds that users "shall make sure not to convey the impression to the
  public that the user's activities are officially endorsed by the Union".
- **The AWS copy.** The AWS open-data registry page (https://registry.opendata.aws/sentinel-2-l2a-cogs/) says access is
  "free, full and open" and links its terms to the same legal notice. Its buckets are marked "No AWS account required".
  It asks for a citation of the form "Sentinel-2 Cloud-Optimized GeoTIFFs was accessed on DATE from
  https://registry.opendata.aws/sentinel-2-l2a-cogs".
- **CLMS Lake Water Quality (if used).** Three texts, all read:
  - the CLMS data policy (https://land.copernicus.eu/en/data-policy): free, full and open access on three conditions:
    inform the public of the source, "clearly state" any adaptation or modification, and do not suggest EU
    endorsement. Its suggested credit for derived products: "Generated using European Union's Copernicus Land
    Monitoring Service information;" followed by the dataset DOI (here 10.2909/deae3db1-a214-4375-8d1a-63c42498050e);
  - the product manual (PUM 4.5.4): any publication or communication using the products must include a longer
    citation that names the Copernicus land service and the Calimnos chain's developers (PML, University of Stirling,
    Brockmann Consult, HYGEOS), plus "Contains modified Copernicus Service information [Year]" for modified data;
  - the EEA metadata record repeats the three conditions.
  The manual also says v2.0 products are "currently delivered as demonstration products" and the news item says the
  chlorophyll datasets "need further calibration". Neither is a licence term; both bear on wording.
- **EA algae checks.** Water Quality Archive data, already used on the site (`algae.py`).
- The test itself publishes only aggregate scores and counts.

## Harness choices

Fixed in `scripts/lake_algae_sat_eval/protocol.py` before any reading or check was seen:
- The water mask's denominator also leaves out SCL 0 (no data) and 1 (saturated or defective): a pixel a scene did not
  see is not evidence of land.
- The connected piece is found inside a square of 1 km around the point, not the whole tile.
- A pixel whose B4 or B5 reflectance, after scale and offset, is zero or less, or no data, has no NDCI and is left out
  of the median. A usable scene where no clear core pixel has a valid NDCI gives no reading.
- A training fold whose outcomes are all 0 or all 1 predicts that rate (R1) for every model. A fold with no training
  rows gives no prediction, and those rows are counted and left out of Brier and AUC.
- Brier is the mean of (p − y)². AUC is scikit-learn's `roc_auc_score`. A bootstrap draw with no event or no non-event
  gives no AUC and is counted.
- Percentiles are numpy's default (linear). The placebo needs the real AUC above both the 95th percentile and the
  190th smallest of the 200.
- The level map is the harness's own copy, checked equal to `algae.LEVELS` before any score.
- No raster library: SCL, B4 and B5 windows are read by a small COG reader (`cog.py`, numpy and zlib) over range
  requests through the capped client, so every byte is counted.

## Running

- The harness is `scripts/lake_algae_sat_eval/`, in this PR with the revised statement. Its pixel and scoring rules
  are tested on synthetic data in `tests/test_lake_algae_sat_eval.py`. Stage 0's fetch is not written (account).
- **Stage 1a, online, outcome-blind:** `run.sh stage1 <out> masks`. STAC search and SCL windows at each site, the
  masks and `sizes.json`.
- **Stage 0, if an account is approved:** the CLMS benchmark, written then; its covered water bodies go in a
  `skip.txt`.
- **Stage 1b, online, outcome-blind:** `run.sh stage1 <out> readings [skip.txt]`. B4 and B5 for usable scenes, the
  readings, `features.parquet` and its hash. The hash is committed.
- **Estimate for stage 1, from the coverage counts:** 9,238 items over the 126 site-seasons; about 2 requests per SCL
  window (header and one tile, about 27 KB), and about 5 more per usable scene for B4 and B5. About 27,000 requests and
  2 GB in all; at 1 second a request, about 8 hours over 7 runs (estimate, not checked).
- **Stage 2:** `run.sh fetch <out> <features hash>` fetches the algae checks once and saves them with their hash.
  Then `run.sh score <out> <features hash> <checks hash>` from a `git archive` of the harness commit, in a scratch
  folder, with every outgoing connection refused and counted (`scripts/lake_distance_eval/run_offline.py`).
- The order in stage 2: stop rules; the gate counts for both outcomes; then the scores.
- One run, alone. No other evaluation, training, build or test on this machine at the same time.
- It runs after Ethan has read this statement.

## Download caps

Written here and in `scripts/lake_algae_sat_eval/net.py` (26 October 2026, ef64038) before any request went through
the harness. Every public request the harness makes, in the coverage prototype and in stage 1, goes through that one
client. (Stage 2's one fetch of EA checks uses `ingest.wqa`, as the site does.)
- One request at a time. At least 1 second between requests. A 60-second timeout on each.
- At most 300 requests and 100 MB per run.
- The coverage prototype, all its runs together: at most 900 requests and 300 MB, counted in a ledger file (one line
  per request: time, URL, status, bytes).
- At most 32 MB in any one response.
- Stop at once on HTTP 429 or any 5xx, and on any status other than 200 or 206. Nothing is retried.
- Only these hosts: Earth Search's STAC API, the two public AWS buckets that hold its Sentinel-2 files, and the CDSE
  catalogue and STAC search endpoints (search only). No account, token, key or cookie is ever sent; the client refuses
  a request that carries one.

**Stage 1's caps,** added after the coverage prototype and before any stage 1 request, from its counts: at most 4,000
requests and 500 MB per run, and 40,000 requests and 4 GB over all stage 1 runs (its own ledger). The pause, timeout,
hosts and stop rules are the same. It resumes from what earlier runs wrote.

**What the coverage prototype used:** 522 requests and 113.7 MB through the client, in 12 runs on 26 October
(18:41 to 19:02 UTC): 246 to Earth Search's API, 272 range reads from the AWS bucket, 4 to the CDSE catalogue (2 of
them refused with HTTP 403). The first metadata run stopped at the 100 MB per-run cap after 181 requests: asking for
the bands' `raster:bands` returns whole items. A second run with lighter fields finished the 29 site-seasons left.
Outside the client: 2 diagnostic requests to the CDSE catalogue (to read the 403), and single requests for the VITO
manifest, the CDSE CSV listing page and the WMTS capabilities. Downloads are in a scratch folder, not in the repo.

## What will be reported

Whatever the verdict:
- the CLMS stage 0 result: run or not (account), water bodies covered, usable dekads per site, the decision;
- the size rule: core pixels per site and tile, sites in and out;
- pairing: checks, checks with a reading, days from scene to check, per site and year, and the 2022 checks without one;
- the gate counts for each outcome, by water body and season;
- the primary label with d, L, U, B and H;
- each condition with its figure and interval;
- LOWO and LOSO tables: R1, R2, M1, M2, Brier and AUC, per outcome;
- AUC per water body, as description;
- the 200 placebo AUCs (lowest, median, 95th percentile, highest);
- the 0- and 7-day pairing windows and the statutory-only checks, as description;
- the features and checks hashes, the harness commit, the network-attempt counts and the request ledgers.

## Seen before writing

First version (b558da0):
- `algae.py`'s docstring tallies (28 September 2026): 2,925 checks at the 38 bathing waters since 2020; from 2023,
  algae seen in 310 of 1,304 lake checks (63 objectionable) and 64 of 1,012 river checks (11). No other count of
  checks was made, by site, season or level.
- The 18 lake bathing waters and their points, from `data/raw/bathing_waters_inland.json`.
- Earth Search metadata only: the `sentinel-2-c1-l2a` collection (its asset names and licence link), and one search
  over Millerground Landing for 1 May to 30 September 2025 that returned 186 items (Sentinel-2A 60, 2B 62, 2C 64),
  and one for early May 2020 that returned items with `rededge1` and `scl`. No asset was read.
- CyFi's repository and documentation pages; search results about the UK Lakes Observatory; the NDCI citation.

Added for this revision (26 October 2026):
- The CLMS pages, manual, metadata record, CDSE documentation and data terms named above, with the manual's Figure 2
  enlarged over the British Isles. One web search for a granule list (none found).
- The CDSE catalogue's list of the 155 LWQ 100 m v2 products: names, dates, sizes, publication dates, footprints.
  No product was downloaded or opened.
- The WMTS capabilities' layer names. No tile.
- Earth Search metadata for all 18 sites and seven seasons: item ids, dates, tiles, tile cloud percentage, creation
  times, processing baselines, and (for 97 site-seasons) the bands' scale and offset. Counts are in "What each source
  can give" and in `docs/LAKE-ALGAE-SATELLITE-TEST-2026-10-coverage.json`.
- One full Earth Search item (Millerground Landing, 10 July 2025) to see its structure, and its SCL window (classes 8
  and 9 present: cloud).
- SCL windows (101 × 101 pixels) at Millerground Landing, Whitwell Creek and Ladies Pond, 45 scenes each in 2025: the
  counts in the table above, and which 2025 dates were usable at each (in the coverage file). No B4 or B5 asset was
  read at any time, so no NDCI exists. No CLMS pixel was read.
- No EA algae check was fetched or opened for this revision. No satellite value was paired with any check. No score of
  any kind has been computed.

## Approval

Ethan approved this statement on 26 October 2026 at about 19:25 UTC, in the session that wrote it, in reply to "Approve
the revised #377 statement so stage 1 can run?": "approved". He had the revision at e6382b7. Nothing above this
section changed after that, and nothing had been run.

**Stage 0 is not run.** The approval did not cover a Copernicus Data Space account, and Claude does not create
accounts. So, by the decision rule in "Stage 0: CLMS first", CLMS is reported as coverage only (the metadata above) and
NDCI is the primary reading at every water body.

## Run log, after approval

A record of what was done and seen while the test ran. It changes nothing above "Approval".
- **26 October, 19:29 UTC: stage 1a started** from a `git archive` of cb06272 in a private folder, under the group's
  heavy-run lock, with the stage 1 caps.
- **26 October, from 19:50 UTC: the CLMS coverage check Ethan asked for** ("lets defo take a look and check about
  english lakes"). The dataset's public WMTS needs no account. Tiles of the TMEAN (turbidity) layer, zoom 14, one per
  site per dekad of May to September 2025, plus five control lakes; only the alpha channel was kept (data or no data
  within 300 m and in the whole tile), never a colour or value. Its own caps: 320 requests and 40 MB in all, one at a
  time, stop on HTTP 429. It stopped twice on HTTP 429 and resumed later at a slower pace. Results are added below when
  it ends.
- **26 October, 20:40 UTC: a walkthrough figure for Ethan** at Rutland Water, Whitwell Creek: true colour, SCL, NDCI
  and the median NDCI (+0.002) of one scene on **30 April 2026**, outside the May to September window. The water
  mask and core pixels (75) came from the 424 in-window SCL windows stage 1 had saved; SCL holds no chlorophyll. Usable
  in-window scenes there by season, from SCL only: 2020 15 of 60, 2021 12 of 61, 2023 12 of 61, 2024 9 of 61, 2025 16
  of 91, 2026 27 of 90. No in-window B4 or B5 pixel was read and no EA check was touched. 39 requests, 12.2 MB, own
  ledger.

---

## Results

None yet.
