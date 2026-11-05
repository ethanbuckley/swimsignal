# Satellite lake readings: how much does the shore margin matter? (exploratory, offline)

Written 5 November 2026, before any figure below was computed. A bounded offline check in the satellite work
([recovery register](RESEARCH-RECOVERY-2026-10.md), SAT-OBS; [satellite test](LAKE-ALGAE-SATELLITE-TEST-2026-10.md),
stage 1a). **Exploratory, on cached data already read.** It changes no reading, no published file and no protocol; it
reads no algae check or lab result; it touches no active window. A satellite index is not a toxin measurement, and
nothing here is a safety or algae claim: this is about which pixels a reading is taken from.

## The question

A site's reading is the median NDCI over its *core* pixels: open water whose 8 neighbours are all in the site's
connected water, so one 20 m pixel is kept off the shore, "where land light leaks into the reading" (stage 1a, step 4).
How sensitive is that choice? A wider margin removes more mixed shore pixels but leaves fewer pixels, fewer sites past
the 9-pixel size rule, and possibly fewer usable scenes.

## What the cache allows (checked before writing this)

- Cached: every scene's scene-classification (SCL) window at every site (9,238 at the 18 bathing-water lakes,
  25,148 at the chlorophyll points), the saved core masks, and each scene's median NDCI.
- **Not cached: B4 and B5 pixels**, anywhere. So NDCI cannot be recomputed at another margin offline. This check
  measures what the margin does to the pixels and scenes, and how the shore pixels are *classified*; how much it moves
  the index itself needs a bounded band fetch (done afterwards; see the end).

## Protocol (fixed before running)

- **Data.** For each set (bathing-water lakes; chlorophyll points), each site and tile: every cached SCL window, with
  the items' tiles from the cached item lists. Inputs fingerprinted (SHA-256 of every file in `cores/` and `scl/`, and
  `features.parquet`) before and after; the run writes nothing beside them.
- **Rebuild check.** Each tile's water mask, connected piece and site water are rebuilt with stage 1's own functions
  (`protocol.water_mask`, `site_water`, `core_pixels`). The one-pixel cores must equal the saved ones exactly on every
  site and tile, or the run stops and reports that first.
- **Margins.** k = 0 (all the site's water), 1 (production), 2 and 3 pixels: a site pixel is kept when every pixel
  within k in each direction (a (2k+1)-square) is in the connected piece.
- **Measures, per margin.** Pixels; site-tiles and sites past the size rule (9 pixels); scenes usable by the 80%-clear
  rule, among all cached scenes on tiles past the rule at that margin.
- **Shore rings.** In scenes usable at k = 1, among pixels clear by the scene rule, the share *not classed as water*
  (SCL other than 6) in ring 1 (k0 minus k1), ring 2 (k1 minus k2), ring 3 (k2 minus k3) and the inner pixels (k3).
  Pooled over scenes and sites, and per site. A pixel classed as land in a clear scene is a sign it mixes land and
  water; the converse does not hold (a mixed pixel can still be classed water).
- **What would follow** (a recommendation only, not a rule for production):
  - if ring 2's not-water share is more than twice the inner share *and* at least 2 percentage points above it,
    pooled, mixed pixels reach past the one-pixel margin: recommend a band-sample test of k = 2;
  - otherwise the one-pixel margin removes most of what the classification can see: no change recommended;
  - in either case, report how many sites a wider margin would drop.

## Results (5 November 2026; `python scripts/satellite_shore_margin.py`, about 14 s)

**Rebuild check: passed.** The rebuilt one-pixel cores equal the saved ones on every site and tile in both sets, and
the bathing lakes' usable scenes at k = 1 come to 1,749, the satellite test's own count. **Inputs unchanged:** the
SHA-256 of every cached file, `cores/`, `scl/` and `features.parquet`, was the same before and after the run (bathing
`features.parquet` 41f234d3…, equal to its committed `features.sha256`).

**What the margin does to pixels, sites and scenes**

| Set | Margin | Pixels | Site-tiles past the size rule | Sites past it | Usable scenes |
|---|---|---|---|---|---|
| Bathing lakes (18 sites) | 0 | 3,896 | 18 | 14 | 1,517 of 7,523 |
| | **1 (production)** | 3,158 | 18 | 14 | **1,749** of 7,523 |
| | 2 | 2,489 | 18 | 14 | 1,921 of 7,523 |
| | 3 | 1,917 | 14 | 11 | 1,512 of 5,808 |
| Chlorophyll points (40) | 0 | 16,991 | 63 | 40 | 5,623 of 25,148 |
| | **1 (production)** | 13,847 | 59 | 38 | **5,850** of 23,424 |
| | 2 | 10,945 | 59 | 38 | 6,554 of 23,424 |
| | 3 | 8,431 | 47 | 31 | 5,406 of 18,701 |

A margin of 3 drops 3 bathing lakes (ukd1203-45700, ukf1400-09750, uki1106-11940) and 7 chlorophyll points.
A margin of 2 drops none.

**How often each shore ring is classed as not water, in clear pixels of scenes usable at k = 1** (pooled)

| Set | Ring 1 (outermost) | Ring 2 | Ring 3 | Inner (k = 3) |
|---|---|---|---|---|
| Bathing lakes | 7.26% (4,328 of 59,645) | 1.73% | 1.52% | 1.20% |
| Chlorophyll points | 8.29% (23,702 of 285,815) | 1.46% | 1.25% | 1.06% |

**Under the rule fixed above: no change recommended.** Ring 2 is 1.4 times the inner share in both sets (1.73% against
1.20%; 1.46% against 1.06%), and 0.4 to 0.5 points above it: under both "twice" and "2 points". The one-pixel margin
takes off the ring that the classification shows most often as land (about 7 to 8%, against about 1% inside).

**Exploratory, not pre-specified.**
- *Usable scenes.* A margin of 2 keeps every site in both sets and makes 10% (bathing) to 12% (chlorophyll) more scenes
  usable. *Inferred, not measured:* shore pixels are more often unclear in a scene, which counts against the 80% rule.
  Whether readings from those extra scenes, or from fewer pixels, are as good is not known without bands. Worth raising
  in the 2027 shallow-lake protocol review (before 1 May 2027); production keeps margin 1.
- *Per site.* No bathing lake meets the rule on its own. Two chlorophyll points do: MD-28548100 (rings 19%, 11%, 9%,
  inner 3.8%: the whole site reads mixed, not just its shore) and NE-44100119 (ring 2 5.4% against 1.1% inside).
  Whether two of 38 is more than ordinary variation between sites was not tested; noted, not acted on.

**Band samples (done 5 November 2026).** Two 50-scene band samples measured the NDCI shift: see the
[band comparison](SATELLITE-SHORE-BANDS-2026-11.md) ([#621](https://github.com/ethanbuckley/swimsignal/pull/621)) and its
second sample. Neither says which margin is closer to lab chlorophyll; that needs the 2027 confirmation data.

## Not claimed

- Anything about algae, toxins, or whether water is safe.
- That a pixel classed as water is free of land light (classification sees only gross mixing).
- That a different margin would make the readings better or worse against lab chlorophyll: that needs bands and the
  confirmation data, under the 2027 protocol's own rules.
