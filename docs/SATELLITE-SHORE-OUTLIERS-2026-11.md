# Shore-margin outliers: what is in the images, and a flag for readings that depend on the mask (exploratory)

Written 5 November 2026, protocol first, before any new pixel was fetched. Follow-up to the
[shore-margin check](SATELLITE-SHORE-MARGIN-2026-11.md) ([#620](https://github.com/ethanbuckley/swimsignal/pull/620)) and
the two [band samples](SATELLITE-SHORE-BANDS-2026-11.md) ([#621](https://github.com/ethanbuckley/swimsignal/pull/621),
[#622](https://github.com/ethanbuckley/swimsignal/pull/622)). Bounded exploration under the
[research workflow](RESEARCH-WORKFLOW.md), SAT-OBS. **Exploratory, on seen imagery.** It changes no reading, no published
file, no forecast and no protocol; the 2027 evaluation stays frozen. A satellite index is not a toxin measurement, an
algae forecast or swimming clearance, and nothing here says a flagged or unflagged reading is accurate.

## 1. The question

Two 50-scene samples found that moving the shore margin from one to two pixels usually shifts a reading by about 0.004
NDCI, but 13 of 98 distinct scenes shifted by 0.02 or more and one (the Serpentine, 24 June 2026) by 0.23. Why, and
can a reading carry its own warning when it is sensitive to which pixels it was taken from?

## 2. What the caches already say (offline, no fetch; read before fixing the protocol)

Everything in this section used only the cached scene classification, masks and one-pixel readings, plus the second
sample's 50 band windows, which were still in that session's scratch directory. These findings shaped the protocol
below, so they are development observations, not tests.

**The readings around the outliers.** The Serpentine's one-pixel reading of 0.24 on 24 June 2026 sits among readings of
0.15 to 0.41 at that site through June and July 2026; it is the two-pixel value (0.007) that is out of line with the
series. In the second sample, two other summer Serpentine scenes (25 Aug 2025, 16 Jul 2026) read 0.24 and 0.27 at both
margins, with the inner pixels no lower than the ring. The two Lake District outliers are different: Windermere
(`ukd1203-45625`) read −0.41 on 12 July 2025 on tile 30UVF while the same acquisition on tile 30UWF read −0.14, and
Coniston (`ukd1230-45775`) read −0.47 from Sentinel-2B at 11:21 on 18 May 2025 while Sentinel-2A read −0.04 at 11:33.

**Same-day disagreement is common.** 393 of 1,305 usable site-dates have more than one usable reading (two tiles of the
same pass, or two satellites 12 minutes apart). Their range has median 0.03 and 90th percentile 0.17; 17.6% differ by
0.10 or more. Pairs from two satellites differ more (median 0.07) than two tiles of one pass (0.03). Every one of the 13
two-satellite pairs that differ by 0.20 or more has one reading at or below −0.21 (one exception: the Serpentine, 0.18
against 0.41). 50 of the 1,744 usable readings are at or below −0.3; 43 of them are at the Windermere, Coniston and
Derwent Water sites.

**Pixels in the second sample.** Across its 50 scenes, the six that shifted by 0.02 or more fall into two groups:
- three with a median B4 + B5 reflectance over the core of 0.007 to 0.012 and an interquartile range of pixel NDCI of
  0.28 to 0.43 (the other 44 scenes: median brightness 0.033, IQR 0.055). At such low reflectance the index is a ratio
  of two numbers a few digitisation steps above the processing offset, so pixel values scatter widely and the median
  depends on which pixels are kept;
- three at sites where the two-pixel margin removes 39 to 68% of the core (the Serpentine, Windermere Fellfoot,
  Colwick), leaving 22 to 24 inner pixels; their brightness and IQR were ordinary.

**Geometry alone is weak.** The share of the core removed by the two-pixel margin is known for every scene from the
masks. A flag at 0.40 or more marks 35 of the 98 sampled scenes and catches 7 of the 13 that moved (median absolute
shift 0.0085 among flagged against 0.0034 unflagged). The Lake District movers are on wide water (share 0.22 to 0.29).

## 3. Protocol (fixed before the fetch)

**Scenes.** Three sets, selected offline from cached values; no pixel of these scenes had been seen.
- A. The first sample's seven scenes that shifted by 0.02 or more (the second sample's six already have pixels).
- B. Three partners: the 12 July 2025 Windermere scene on the other tile (30UWF), the 18 May 2025 Coniston Sentinel-2A
  scene, and the Serpentine scene of 26 June 2026 (two days after the outlier; one-pixel reading −0.10).
- C. A same-day pair test: among site-date-tile pairs read by two satellites, four with a range of 0.20 or more and four
  with a range of 0.02 or less, at most one pair a site, chosen by a seeded permutation (seed 20261105) after
  excluding scenes already in A or B. The 18 May 2025 Coniston pair, already in A and B, counts as a fifth big pair.
- True-colour (TCI) windows for four scenes only: the Serpentine on 24 and 26 June 2026, Windermere 12 July 2025
  (30UVF), Coniston 18 May 2025 (Sentinel-2B).

**Reads.** `python scripts/satellite_shore_outliers.py prepare|read|report`. B4 and B5 windows through the existing
reader, same scale, offset and mask rules; TCI on the 10 m window. One run, at most **200 requests and 120 MiB**, no
account, stop on the first HTTP error, cap or mismatch, no retry; a partial run stays partial. Every one-pixel reading
must equal the cached one within 1e-6. SHA-256 over every cached input file before selection, before the fetch and after
it. Pixels stay in scratch; the record publishes values only, plus pictures of the inspected scenes.

**Per scene:** readings at margins 0, 1 and 2; clear core pixels; inner pixels; the share the two-pixel margin removes;
median B4 + B5 reflectance over the clear core ("brightness"); IQR of pixel NDCI over the clear core; ring-minus-inner
median NDCI ("contrast"); pixels in the core classed as not water.

**Flags proposed** (thresholds fixed from the second sample, section 2, so exploratory; none uses the two-pixel reading):
- *dark*: brightness below 0.015;
- *spread*: IQR at or above 0.10;
- *narrow*: the two-pixel margin removes 40% or more of the core.

**What is reported** (descriptive counts, no significance claims, nothing adopted):
- H1, the pair test: in each big pair, whether the scene with the larger |reading| is dark or spread; in each small
  pair, whether either scene is. The expectation written down beforehand: big pairs mostly yes, small pairs mostly no.
- H2, the Serpentine outlier: ring-minus-inner contrast on 24 June 2026 against 26 June 2026 and the two cached summer
  scenes, and what the true-colour picture shows over the inner pixels and the shore.
- Each flag against a shift of 0.02 or more on the fetched scenes and on the second sample (the latter is the data the
  thresholds came from, and says so).
- Pictures: true colour, scene classes and NDCI over the site's water, with the one-pixel mask outlined in white and the
  two-pixel mask in yellow, for the four TCI scenes and the first sample's movers.

**Not claimed:** that any flag detects algae, that a flagged reading is wrong or an unflagged one right, or which margin
is closer to lab chlorophyll. Those need the 2027 confirmation data under its own protocol.

## 4. Results

(To be filled in after the run.)
