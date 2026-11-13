# Wessex Water river samples: the observation contract, version 1

Written 13 November 2026. Source inventory rank 3 (`wessex-river-samples`, `docs/SOURCE-INVENTORY-2026-11.md`),
register row **WESSEX-RIVER** (`docs/RESEARCH-RECOVERY-2026-10.md`), route "public research observations"
(`docs/RESEARCH-WORKFLOW.md`). Produced and checked by `scripts/export_wessex_river_samples.py`; file
`data/research/wessex_river_samples.v1.json` (70 KB). Shown on `/wessex-river-samples.html`
(`build_site.write_wessex_samples`) and linked from each of the three spots' pages.

## The source

- **Layer:** "Wessex Water Environmental Water Quality 2019-2025", ArcGIS item `4659ab28caa640c58e725b41ecbba79f`,
  owner `WessexWaterData`, layer `Wessex_Water_Environmental_Water_Quality_view/FeatureServer/0`.
- **Licence, read on the day** (13 Nov 2026, 15:18 UTC, the item's `licenseInfo`): "Wessex Water Environmental Water
  Quality © 2026 by Wessex Water is licensed under CC BY 4.0". Item last modified 5 June 2026; the layer's data last
  edited 5 June 2026.
- **Cache:** the main checkout's `data/cache/wessex_wq/ecoli.parquet` (SHA-256 `e02f8817…cbc64e`), all 4,123 rows
  with `Determinand = 'E. coli'`, fetched once on 25 Oct 2026 by `scripts/soil_moisture_eval/rivers.py`. On 13 Nov a
  count-only query returned 4,123, so the cache is complete. Three requests in all (item, layer, count). No new
  download.
- **What the company says the samples are** (the item's description): river samples "analysed at an accredited
  laboratory", used "to help us understand the impacts our operations have on the environment". They are the
  company's own samples. They are **not** the Environment Agency's statutory bathing water samples and follow no
  bathing water rules: they run through the year, in any weather. At the three points, 593 of 594 were taken on a
  weekday and 545 before 1 pm (the page says "mostly on weekday mornings").

## Which points, and the placement check

The layer has no site name. Its rows give a position. Positions under 10 m apart are joined into one point (the
layer moves a point's sixth decimal between years). For each spot the export takes the nearest point and places both
on the river network with the site's own code (`transport.locate_pin` with the spot's river, `upstream_overflows`
over the overflow table). The point is linked only if all five checks hold, and each check is kept in the file:

1. both are placed on the spot's named river;
2. the point is within 2.5 km in a straight line;
3. its distance along the river is known: the shared upstream overflows give one value (spread under 1 m);
4. that distance is within 3 km;
5. no monitored storm overflow lies between them (the two upstream sets are equal).

| Spot | Point | Straight | Along the river | Upstream overflows | Samples |
|---|---|---:|---|---:|---:|
| Warleigh Weir (`avon-warleigh-weir`), River Avon | 51.37705, −2.30064; snapped 9 m | 50 m | 51 m downstream | 185 of 185, none between | 322, 19 Mar 2021 to 8 Dec 2025 |
| Farleigh Hungerford (`bw-ukk2301-36051`), River Frome | 51.30928, −2.28610; 27 m from an unnamed side channel, 78 m from the Frome's mapped line | 1,025 m | 2,269 m upstream | 38 of 38, none between | 174, 27 Apr 2021 to 28 Jul 2025 |
| Tellisford Weir (`frome-tellisford-weir`), River Frome | 51.29962, −2.27946; snapped 26 m | 213 m | 212 m downstream | 38 of 38, none between | 98, 14 Apr 2021 to 12 Dec 2025 |

**Established:** the same named river, the distances, the equal overflow sets. **Not established:** the overflow
table holds monitored storm overflows only. A treatment works' continuous final effluent, a private discharge, a
farm or a tributary joining between point and spot would not show here. At Farleigh 2.3 km of river lies between
them. The page says how far each point is and never calls it the spot's own water.

**A correction to the brief and the inventory.** Both said all three spots have no other samples. Farleigh
Hungerford is a designated bathing water (2024): the Environment Agency has 60 samples there, 4 May 2024 to
21 Sep 2026, on `/samples.html` (`ecoli_evidence.v1.json`). Wessex's point adds 2021-25 at a point 2.3 km upstream.
Warleigh Weir and Tellisford Weir have no EA samples.

## What it may and may not say

- **May say:** what Wessex Water's lab counted at each point and when, per 100 ml, with "below" and "above" limits
  in words; how many were over 900; where the point is from the spot along the river; that these are the company's
  own samples, not the Environment Agency's.
- **May not say:** that a sample shows the water at the spot, or at any other time; that the water is safe; a
  rating; which source the E. coli came from; anything about SwimSignal's forecast. `claim.not_claimed` lists these.
- Credit, on the page and with the data: "River E. coli samples: Wessex Water Environmental Water Quality © 2026 by
  Wessex Water, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Selected and arranged by
  SwimSignal." The changes made are in `changes` and on the page (CC BY 4.0 asks for both).

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version`, `generated_at` | `"swimsignal.wessex-river-samples"`, `"1.0.0"`, export time |
| `line` | 900 E. coli per 100 ml, the inland "sufficient" standard's line, as in `ecoli_evidence.v1.json` |
| `units`, `time_note` | per 100 ml as the layer's Units field says; times as published with no time zone, read as UK local time |
| `claim` | `public_wording`, `not_claimed` |
| `who`, `attribution`, `changes` | whose samples; the CC BY 4.0 credit; what SwimSignal changed |
| `source` | title, item, layer, query, fetch time, rows, `licence_check` (wording, date, item and layer edit dates, count), SHA-256 of the cache files, network, overflow table, `spots.csv` and the script |
| `placement_rule` | the join, straight and along-river limits and how the distance is measured |
| `spots` | the linked spot ids, in the order the page gives them (downstream first) |
| `sites` | per spot: `spot_id`, `spot_name`, `river`, `point` (lat, lon, the joined `positions`, `snap_m`, `placement`, `side_channel`), `straight_m`, `along_m` (positive downstream of the spot), `direction`, `overflows_upstream` (`spot`, `point`, `between`), `checks`, `linked`, then for a linked spot `summary` and `samples` |
| `summary` | samples, over 900, over unknown (a limit that leaves it open), below and above the lab's limit, times with two results, first and last date, and `years`: per year samples, over 900, first, last, highest and its qualifier |
| `samples` | in time order: `t` (time as published, minutes), `ecoli`, `q` (`"<"`, `">"` or null; an operator of "NA" is null), `over` (over 900; null where a limit leaves it unknown; `">"` at or above 900 is true), `id` (the layer's OBJECTID), `same_time` |
| `coverage` | linked sites and samples |

A value with `q` is the lab's limit, not a measurement: the page writes "below 1,000" or "above 10,000", never the
number alone. Twelve times at Warleigh Weir have two results each (2022); both are kept, as the layer gives them.

## Refresh

The layer says it covers 2019 to 2025 and was last edited 5 June 2026. When it changes, refetch with
`rivers.py fetch` into a scratch cache (about 3 requests of 2,000 rows), rerun the export from a scratch
`DIPCAST_ROOT`, and bump the minor version. A new field or meaning is a new major version, which the site will not
publish until `build_site.write_wessex_samples` is changed to read it.
