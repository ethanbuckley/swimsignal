# Lake observations: the derived-data contract, version 1

Written 30 October 2026 for the satellite recovery (`docs/SATELLITE-RECOVERY-2026-10.md`). This is the one file the
product's Research/Labs page and lake viewer read. It is produced by `scripts/export_lake_observations.py` from the
caches the satellite tests already made. No new imagery is needed to produce it.

**Status: adopted** by the product chat (30 October 2026), which builds the page from it; amended to 1.1 below.
Additive changes raise the minor version; removing or renaming a field raises the major version.

## What it may and may not say

- **May say:** a dated satellite reading of a vegetation and chlorophyll-sensitive index (NDCI) at a lake, from the
  most recent clear Sentinel-2 image, and how it compares with the same lake's earlier readings.
- **May not say:** anything about harmful algae, blue-green algae, toxins or cyanobacteria; "algae-free", "clear" or
  "safe"; any swimming advice; a chlorophyll concentration in µg/l. NDCI is not converted to chlorophyll: the
  lab-chlorophyll test (#386) found a promising but unvalidated relation (pooled ρ 0.502, interval 0.300 to 0.667, the
  lower end just short of its 0.3 rule), and the visual-algae and incident tests (#377, #385) were weak.
- Every reading carries its image date. An old reading is shown as old, never as current.
- Readings vary as measurements. Two usable scenes of the same lake on the same date differ by a median of 0.03
  NDCI and by 0.17 at the 90th percentile, against a typical within-lake spread (SD) of 0.10 (`quality`, 393
  same-date pairs). The page shows the real observations and explains this variability, and does not read small
  changes as biological trends. These figures describe variability; they are not an uncertainty bound.
- Several sites can sit on one water body (four on Windermere, three on Coniston Water, two on Rutland Water). They
  share imagery and weather and are not independent lakes: `water_body_key` and `shares_water_body_with` say which.
- `claim.public_wording` holds the approved sentence. The UI shows it beside any reading.

## File

`data/research/lake_observations.v1.json`, UTF-8 JSON, one object:

| Field | Type | Meaning |
|---|---|---|
| `schema` | string | always `"swimsignal.lake-observations"` |
| `version` | string | semantic version of this contract, `"1.0.0"` |
| `generated_at` | string | ISO 8601 UTC time the export ran |
| `as_of` | string | ISO date the freshness of every reading is measured against (the export date unless set) |
| `processing` | object | how readings were made: `version` (`"s2c1-l2a.ndci-core-median.v1"`), `code` (the scripts and commit), `sources` (each cache file's path label and SHA-256) |
| `claim` | object | `index`, `definition`, `public_wording`, `not_claimed` (list of strings) |
| `freshness_rules` | object | the day limits below, as numbers |
| `attribution` | list | notices the UI must show: "Contains modified Copernicus Sentinel data [years]" and the EA's Open Government Licence line |
| `lab_definition` | object | what every `lab` value is: `target`, `determinand`, `unit`, `method_note`, `censoring`, `source` (below) |
| `quality` | object | how far one reading can be trusted, measured on the data: `same_date_pairs`, `same_date_abs_difference_median` and `_p90` (two usable scenes of one site on one date), `within_site_sd_median`, and a `note` |
| `lakes` | list | one record per lake site (below) |
| `coverage` | object | counts over all lakes, for build health (below) |

### A lake record

| Field | Type | Meaning |
|---|---|---|
| `lake_id` | string | stable id. A bathing water's is its spot id (`"bw-ukd1203-45650"`); another monitoring point's is `"wqa-<point>"` |
| `name` | string | the site's name |
| `water_body` | string | the lake it is on (several sites can share one) |
| `wfd_waterbody_id` | string or null | the Water Framework Directive water body, where the tests recorded it |
| `lat`, `lon` | number | the site's point (WGS84); readings are taken around it |
| `site_ids` | object | `bathing_water` and/or `wqa_point`, where they exist |
| `depth_m`, `lake_type` | number or null, string or null | HydroLAKES mean depth; `"shallow"` below 3 m, else `"deeper"` (#386's rule) |
| `mask` | object | `site_radius_m` (300), `pixel_m` (20), `min_core_pixels` (9), `min_clear_share` (0.8), `tiles` (per Sentinel-2 tile: `n_core`, `passes`), `passes_size_rule` |
| `series_scope` | string | `"every_scene"` (every image May-September of the years covered) or `"near_lab_samples"` (only images within a day of a lab sample: not a full record) |
| `water_body_key`, `shares_water_body_with` | string, list | a key for the water body, and the other sites on it (not independent lakes) |
| `coverage_label` | string | plain words for `series_scope`; for `near_lab_samples`: "selected historical coverage: only images within a day of a lab sample" |
| `processed_to` | string | the last date this site's images were processed to (a refresh can extend it) |
| `latest` | object | the most recent primary reading **in this dataset** (`scope: "latest_in_dataset"`), not the latest image available: `date`, `datetime`, `item_id`, `ndci`, `clear_share`, `season`, `experimental`, `age_days`, `freshness` (`recent`, `older`, `stale`, `none`), and `reasons` (list, below) |
| `seasons` | list | per year: `scenes` (images over the site), `usable`, `usable_share`, `median_ndci` of usable readings, `first`, `last` usable dates |
| `series` | list | every shown reading: `date`, `datetime`, `item_id`, `tile`, `processing_baseline`, `clear_core`, `n_core`, `ndci`, `primary` (true for one reading a date: the most clear core pixels, then the first item id, the test's own rule), `season` (`in_season` or `out_of_season`), `experimental`, `source` (`test_cache` or `refresh:<root>`); refreshed readings add `sun_elevation_deg` and `clear_water_share` |
| `excluded` | list | refreshed scenes that were clear but not shown, each with `date`, `item_id`, `reason` (`invalid_band_values`, `snow_or_ice_in_core`, `sun_too_low`, `core_not_classed_water`) and `source` |
| `refreshes` | list | each refresh applied to this site: `source`, `from`, `to`, `scenes`, `shown`, its features file's SHA-256, requests and bytes |
| `lab` | list | laboratory measurements with an explicit target, method, date and censoring only (below); empty otherwise |

### Freshness and reasons

`age_days` and `freshness` are **as of the export** (`as_of`). The page must recompute them at viewing time from
`latest.date` and `freshness_rules`, never show the exported values as current. `recent` ≤ 14 days, `older` 15 to 60,
`stale` > 60, `none` when there is no usable reading. No reading may be dated after `as_of`, and no age may be negative. `reasons` explains every gap, from this fixed list:

| Reason | Meaning |
|---|---|
| `too_small` | fewer than 9 core pixels on every tile: the site's water is too narrow for 20 m pixels, so no reading is made |
| `no_usable_scene` | images exist but none had at least 80% of core pixels clear |
| `season_closed` | `as_of` is outside May-September, the months processed; the latest reading is from the last season |
| `not_refreshed` | the series ends before `as_of` because no newer images have been processed (the date is in `processing`) |
| `series_partial` | `series_scope` is `near_lab_samples` |

### A lab measurement

What every value measures is given once, in `lab_definition`: target `"chlorophyll (acetone extract)"`, EA determinand
`"7887"`, unit `"µg/l"`, the method note (*not confirmed as chlorophyll-a; the phaeopigment correction is not
stated*), the censoring rule and the source (EA Water Quality Archive, Open Government Licence v3.0). The export stops
if any row is another determinand or unit. Each row:

| Field | Meaning |
|---|---|
| `sample_time` | as the Water Quality Archive gives it (local time, no zone) |
| `value`, `censored` | the number, and `"<"` when the lab reported "below" (then `value` is the reported limit, never halved) or null |
| `purpose` | the Archive's sampling purpose, verbatim |

Visual algae checks (the sampler's four-level look, determinand 4824) are not in this file: they are field
observations, not lab measurements, and the site already shows them elsewhere.

### Coverage

`lakes`, `with_reading`, by `freshness`, by each `reason`, `too_small`, and `scenes` / `usable` in total. The build
health check (`scripts/export_lake_observations.py check`) fails when the file breaks this contract.

## Versioning and provenance

- `processing.version` changes whenever a reading could change (mask, clear rule, index, source collection).
- `processing.sources` lists each input's SHA-256, so any reading can be traced to the cache it came from.
- `processing.code.sha256` gives the SHA-256 of the exporter, the refresher and every reading script at export time;
  these are the code provenance (a commit id read at export can predate uncommitted edits).
- The export never writes to the caches it reads; it records their hashes before and after, and stops if they differ.

## Amendment 1.1 (30 October 2026, prospective): dated out-of-season readings

Decided by Codex for Ethan, 30 October 2026, before any October reading was displayed. May-September was the season
in which the biological relation (NDCI against lab chlorophyll, algae checks) was tested; it is not a rule that a
correctly extracted index from another month cannot be shown. So:

- A **refresh** (`scripts/refresh_lake_observations.py`) may add newer readings, made with the test's code and saved
  cores, from a separate research root that is never the test cache. The export takes refresh roots explicitly
  (`--refresh`), checks their SHA256SUMS, and records each in `processing.refreshes` and the site's `refreshes`.
- Every refreshed reading must meet the test's rule (at least 80% of core pixels clear) **and** have a valid index at
  every clear core pixel, no snow or ice in the core, and the sun at least 15° up. A reading outside May-September
  must also have at least 90% of its clear core pixels classed as water. A scene that fails is listed in `excluded`
  with its reason, never shown.
- A reading outside May-September is `season: "out_of_season"`, `experimental: true`. The page labels it as a dated,
  out-of-season experimental index, with no chlorophyll or algae inference.
- **Why 90% water:** in the first refresh (Rutland Water Sykes Lane, October 2026), one of two scenes on 27 October
  had 31 of 162 clear core pixels (19%) classed as vegetation or bare ground and read 0.059 against −0.016 from the
  other satellite the same day; the four other clear scenes had at most 4% not classed water. Set after seeing that
  one case, as a display-quality rule; it is not a test result and changes no earlier reading.
- **Unchanged:** the historical May-September series and its rule; the 2027 confirmation population and season
  (`docs/SATELLITE-RECOVERY-2026-10.md`, section 5), which stays May-September.
