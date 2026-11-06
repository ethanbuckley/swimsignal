# Shore margin: a bounded band comparison (exploratory protocol)

5 November 2026. Follow-up to `SATELLITE-SHORE-MARGIN-2026-11.md`, written before reading any band values.
The SCL classification comparison cannot determine how the median NDCI changes with the margin.

Use the existing bathing-lake scene and classification caches only. Rebuild the masks exactly as in the preceding
check, stopping if the one-pixel mask differs from the saved core. Eligible scenes pass the existing size and 80% clear
rules at both one and two pixels. Select at most 50 scenes, without looking at band values: take scenes in round-robin
order over sorted site IDs, with scenes at each site sorted by date and item ID and selected at evenly spaced quantiles.
No sample or algae outcomes are read. Identify the selected item IDs and dates and freeze the selection before fetching.

For each selected scene, retrieve only the public B4 and B5 pixel windows using the existing range reader, convert to
reflectance and compute median NDCI with the existing rules at both margins. Report per-scene differences and site
summaries, the median and range of paired differences, missing values and the fraction moving by at least 0.02 index
units. The 0.02 figure is descriptive, not a significance, accuracy or adoption threshold. Check the one-pixel value
against the original cached feature where available; mismatches are investigated, not averaged away. Keep image pixels
out of the repository; results are exploratory on previously used imagery and do not establish which margin is more
accurate. No change to a forecast or active evaluation follows.

Network budget: a single run, at most 300 requests and 150 MiB total, no account or credentials. Stop on the first
HTTP error, rate limit, cap, grid mismatch, mask mismatch or missing scale/offset; do not retry. A partial run remains
partial, not a reason to change the selection. Record request and byte use and input fingerprints before and after.

## Result, 5 November 2026

All 50 selected site-scenes were read across 14 bathing-water sites. Selection and the protocol above were written
before the band fetch, but were not independently timestamped outside this work session. The sample is deliberately
small and stratified by site, not a random sample of all usable images or lakes. It includes several sites on the
same water body. The selected scene IDs, dates and paired values are in
[`data/research/satellite_shore_bands_2026_11.json`](../data/research/satellite_shore_bands_2026_11.json).

- All 50 one-pixel readings exactly reproduced the existing cached values. All 50 pairs had finite readings.
- Two-pixel minus one-pixel NDCI had median **−0.0033**, median absolute change **0.0041**, and range **−0.2347 to
  +0.0099**. Seven of 50 pairs changed by at least 0.02 in absolute value. These are descriptive counts, not a rate
  for all lake images or an error estimate.
- The largest change was at `uki1106-11940` on 24 June 2026: 0.2415 to 0.0068. The mask shrank from 69 to 22 clear
  pixels. This flags sensitivity to the choice of pixels; it does not identify which result is closer to chlorophyll.
- The next two largest changes were −0.0760 (`ukd1203-45625`, 12 July 2025; 184 to 143 clear pixels) and −0.0500
  (`ukd1230-45775`, 18 May 2025; 129 to 92). Different sites and scenes need not be independent.

The existing data were read without changing the shared caches: a SHA-256 over 9,275 input files was identical
before selection, after selection, before the fetch and after it (`53233d33134b55ae47680809d32e51dae4c40ad1c6ba776363a3ef885a09efde`).
The one run used **222 requests and 125,478,853 bytes** (119.7 MiB), below its limits; there were no retries. The
data are Sentinel-2 L2A, accessed as public Earth Search windows with the existing scale, offset and mask rules.
Contains modified Copernicus Sentinel data 2020–2026.

**Decision:** keep the production margin and the 2027 evaluation frozen. Carry this sensitivity into the planned
2027 protocol review, including the large outlier and the lost pixel counts. This check cannot show whether changing
the margin improves the index, predicts chlorophyll, detects toxins or makes water safe. A follow-up should inspect
outlying images and decide the independent validation design before examining additional outcome labels.

## Second sample, 5 November 2026 (a parallel session, run before #621 was seen)

A parallel session ran the same comparison on a different selection, and ran it before #621 was seen there. It is
recorded here as a second sample, not a new study. Same caches, same rules, same reader.

**Protocol** (committed locally before the fetch; like the first, not independently timestamped). Eligible: bathing-lake
scenes with a cached reading, usable at margins 1 and 2. Selection: seed 20261105, sites in a seeded order, each site's
scenes in a seeded order, one per site in turn until 50 (`python scripts/satellite_shore_margin.py bands`). The k = 1
reading must equal the cached one within 1e-6 or scoring stops. Measures: medians at margins 0, 1 and 2; the shifts'
median, spread and direction; their size against the spread the readings already have (median over sites of the SD of
margin-1 readings, sites with 10 or more scenes: 0.105 NDCI). Words fixed in advance: *barely moves* if the median
absolute shift is at most 0.1 of that spread and its 90th percentile at most 0.25; *moves materially* if the median is
at least 0.25; *moves somewhat* between.

**Result.** 222 requests and 131,527,723 bytes, every response a 206; caches' SHA-256 unchanged before and after. All 50
margin-1 readings equal the cached ones exactly. Only 2 of the 50 scenes are also in the first sample; on those 2 the two
runs give the same values (to 6 decimal places). Paired values: [`data/research/satellite_shore_bands_2026_11_second.json`](../data/research/satellite_shore_bands_2026_11_second.json).

| Change | Scenes | Median | Interquartile range | Median absolute | 90th percentile absolute | Largest absolute | Below zero |
|---|---|---|---|---|---|---|---|
| margin 2 minus margin 1 | 50 | -0.0034 | -0.0093 to -0.0006 | 0.0041 | 0.0205 | 0.0614 | 44 of 50 |
| margin 0 minus margin 1 | 41 | +0.0072 | +0.0035 to +0.0157 | 0.0076 | 0.0378 | 0.1379 | 4 of 41 |

Margin 0 has 41 scenes because 9 fail the 80%-clear rule once the shore pixels are counted. By the words fixed in
advance: margin 2 *barely moves* the readings (median absolute shift 0.04 of the spread, 90th percentile 0.20);
margin 0 *moves them somewhat* (90th percentile 0.36).

**Read with the first sample (exploratory).**
- Two nearly separate samples give the same typical shift to margin 2: median -0.0033 and -0.0034, median absolute
  0.0041 in both. The first sample's -0.2347 outlier at the Serpentine shows the tail can be large; this sample's largest
  was -0.0614 (Derwent Water at Crow Park).
- Both lean one way: margin 2 is lower in 38 of 50 and 44 of 50 scenes, and margin 0 is higher in 37 of 41. Pixels
  nearer the shore read a higher NDCI than the water inside. *Inferred, not measured:* land or plants in mixed pixels add
  more red-edge light (B5) than red (B4). Shore water that really differs (shallower, weed, sediment, algae) would show
  the same; these bands cannot tell the two apart.
- Neither sample is random over all images, and scenes at one site are not independent: these describe the samples.
  Production keeps margin 1; the 2027 protocol review takes both samples and the outliers.
