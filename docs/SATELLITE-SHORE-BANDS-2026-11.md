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

**Decision:** keep the production margin and the 2027 evaluation frozen. Carry this sensitivity into the planned
2027 protocol review, including the large outlier and the lost pixel counts. This check cannot show whether changing
the margin improves the index, predicts chlorophyll, detects toxins or makes water safe. A follow-up should inspect
outlying images and decide the independent validation design before examining additional outcome labels.
