# Satellite lake readings: recovery, derived data, operations and the 2027 confirmation

Written 30 October 2026, at Codex's request on Ethan's behalf: find the satellite algae work, recover what it made and
make it useful and live, honestly labelled. It follows the research workflow and recovery register of PR #469
(`docs/RESEARCH-WORKFLOW.md`, `docs/RESEARCH-RECOVERY-2026-10.md`). This is **bounded development and observational
display**. It does not rewrite the failed or parked tests (#377, #385, #386, #396), and it changes no frozen study:
the 2027 pre-registration, the live-status and A8 shadow windows and option B are untouched.

Ownership: this branch (PR #468) owns the science, data and extraction. The product chat owns the Research/Labs page
and lake viewer, and has adopted the contract (`docs/LAKE-OBSERVATIONS-CONTRACT-v1.md`, now 1.1).

## 1. What exists (inventory, 30 October 2026)

All in `~/Documents/GitHub/swimsignal-private/` (not in git). Every derived file hashes to the SHA-256 the tests
committed before scoring, so the readings are exactly the ones the tests judged. Nothing was re-downloaded.

| Cache | File | SHA-256 (first 16) | Holds |
|---|---|---|---|
| `lake-algae-sat/out` (#377, bathing-water lakes) | `features.parquet` | `41f234d3a953df24` (= committed) | 7,523 rows: one per site and Sentinel-2 scene, May-Sep 2020-2026, 14 sites past the size rule; 1,749 usable readings |
| | `sizes.json` | `f1ea6f79750f34ce` | core pixels per site and tile, size rule (18 sites; 4 too small) |
| | `cores/*.npz` (18) | | each tile's core-pixel mask (101 × 101 at 20 m) |
| | `items/*.json` (18) | | the STAC items found (date, tile, processing baseline, asset links) |
| | `checks.parquet` | `f036b6ebf62e29a2` (= committed) | 1,857 EA visual algae checks (determinand 4824) |
| | `scl/` | 9,238 windows, 36 MB | scene-classification windows (resume cache) |
| `lake-chlorophyll/out` (#386, chlorophyll points) | `features.parquet` | `58bce46681d7b9dd` (= committed) | 1,561 rows at 38 points, scenes within 1 day of a lab sample only; 414 usable |
| | `values.parquet` | `8327417da5c5e512` (= committed) | 1,774 EA chlorophyll results (determinand 7887, µg/l), 2021-2026, with "<" censoring |
| | `sizes.json`, `cores/` (40), `items/` (40) | `f1aafa837bd96a78` | as above; 38 of 40 points pass the size rule; items cover every scene May-Sep 2020-2026 |
| `lake-algae-incident/out` (#385) | `incidents.json` | `68ca1552bea27546` | EA harmful-algae incident records at 3 water bodies |

Raw band reads (B4, B5) were not kept. **Reproducible offline:** every reading, mask, size-rule decision and score of
the three tests. **Reproducible with network:** the band values behind a reading (public AWS buckets, no account),
with the same code and the saved cores. Code: `scripts/lake_algae_sat_eval/`, `scripts/lake_chlorophyll_eval/`,
`scripts/lake_algae_incident_eval/`.

## 2. The derived dataset (first release: historical observations)

`scripts/export_lake_observations.py export [--refresh ROOT ...]` builds `data/research/lake_observations.v1.json`
from the caches, offline, recording every input's and every script's SHA-256 and stopping if an input changes.

As exported for 30 October 2026 (with the one refresh in section 4):
- **55 sites on 48 water bodies:** the 18 bathing-water lakes (every scene May-September) and 37 other EA chlorophyll
  points (selected historical coverage: only scenes within a day of a lab sample). Sites on one water body are not
  independent lakes; the file says which share one.
- **49 with a reading; 6 too small** for 20 m pixels (the three Hampstead Heath ponds, Henleaze Lake and two
  chlorophyll points). 2,097 usable historical readings of 8,802 scenes, plus 4 experimental October readings.
- **1,774 lab chlorophyll values,** 63 censored ("<" with the reported limit, never halved).
- **Measurement variability** (`quality`): two usable scenes of one site on one date differ by a median of 0.032
  NDCI (0.166 at the 90th percentile; 393 pairs), against a typical within-site spread (SD) of 0.105. The page shows
  the real observations and explains this; it does not read small changes as biological trends. These figures
  describe variability, not an uncertainty bound.

The claim is a dated satellite index sensitive to chlorophyll and green material: no harmful-algae or toxin claim,
no chlorophyll concentration, no swimming advice. NDCI and the distinct lab chlorophyll observations can be shown
together now (each on its own scale, each dated); that needs no test to pass first.

## 3. Operational checks

`export_lake_observations.py check` (run in CI by `tests/test_export_lake_observations.py`, 13 tests) fails when:
- the claim wording is missing or uses a safety phrase, or the Copernicus notice is missing;
- a site lacks a reason for a missing reading, or a partial series is not flagged;
- a reading breaks the 80% clear rule, lies outside −1 to 1, is out of date order, or a date has other than one
  primary reading; `latest` is not the last primary reading;
- any reading is dated after `as_of`, any image time is after `generated_at`, or an age is negative;
- an out-of-season reading is not experimental, did not come from a refresh, or breaks the water-share rule;
- a lab value lacks a time or value, or has unknown censoring.

The page recomputes image age at viewing time (the exported `age_days` is as of the export). Proposed build-health
warnings for the product chat: in season, more than half the sites with a reading older than 14 days at build time;
a site changing from a reading to `too_small`; a source hash differing from the last export.

## 4. Refreshing

`scripts/refresh_lake_observations.py` makes newer readings exactly as the test did (its code, its saved cores, its
capped client: listed public hosts, no account, no retries, stop on error), for either site set (`--set bathing` or
`--set chlorophyll`), into a separate root. It never writes to the test caches; every run hashed them before and
after (`048e0c174a2965cc` each time).

- **Plan, 30 October** (catalogue only, 14 requests): 315 scenes over the 14 bathing lakes, 1-30 October. A full
  October refresh would cost about 1,030 requests and 208 MB at the test's clear-scene share (23%), at most 2,240
  requests and 860 MB. Not run: the historical release does not need it.
- **One-lake operational refresh, 30 October,** Rutland Water Sykes Lane, cap 80 requests and 30 MB: 18 scenes, 5
  clear, 57 requests, 17 MB. Stored at `swimsignal-private/lake-observations-refresh/2026-10-30-ukf2208-09702/`
  (features, run record, request ledger, the 18 scene-classification windows, SHA256SUMS). Per clear scene:

  | Date | Satellite | Sun elevation | Clear core | Not classed water | Valid index | Snow/ice | NDCI | Shown |
  |---|---|---|---|---|---|---|---|---|
  | 2 Oct | S2C | 33.6° | 163 of 163 | 7 (4.3%) | 163 | 0 | 0.022 | yes |
  | 10 Oct | S2B | 30.8° | 141 | 0 | 141 | 0 | 0.048 | yes |
  | 14 Oct | S2A | 29.1° | 148 | 6 (4.1%) | 148 | 0 | 0.078 | yes |
  | 27 Oct | S2B | 24.5° | 163 | 4 (2.5%) | 163 | 0 | −0.016 | yes (primary) |
  | 27 Oct | S2A | 24.7° | 162 | 31 (19.1%) | 162 | 0 | 0.059 | **no:** core not classed water |

  Processing baseline 05.13 throughout, scale and offset from each item. The extraction is sound for four of the
  five scenes, so they are shown as dated, out-of-season experimental readings (contract amendment 1.1); the fifth is
  listed in `excluded` with its reason.
- **Collection for 2027** (section 5): weekly in season at the confirmation sites, by the same tool.

## 5. Fresh-data confirmation: DRAFT, for review

**Status: draft, not yet reviewed.** It is written before any 2027 reading or sample exists; margins below are
proposals to settle in review, before 1 May 2027.

**What #386 gives.** A promising association (pooled ρ 0.502, interval 0.300 to 0.667; placebo beaten 200 of 200)
and, at shallow lakes, exploratory held-out calibration skill 0.301 (interval 0.052 to 0.475) against each lake's own
mean. The shallow result was found after the fact, so it supports a hypothesis that fresh data must test; it is not
nothing, and it is not a confirmation.

**The claim to test** (the next thing the site might say): at shallow lakes, an NDCI-to-chlorophyll calibration
fitted on earlier seasons predicts the next season's lab chlorophyll better than the lake's own past mean, with
prediction intervals that cover as stated. Until that holds, the page shows NDCI as an index, beside lab values, and
makes no chlorophyll estimate.

- **Sites, frozen now:** the 14 shallow points (HydroLAKES mean depth under 3 m) of
  `docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json`, with their saved cores in `lake-chlorophyll/out/cores`; the 24
  other points as the secondary set. Each by its WQA point id, WFD water body and coordinates as recorded there.
- **Processing, frozen now:** `s2c1-l2a.ndci-core-median.v1`, the saved cores, 80% clear, one primary reading a date,
  pairing within 1 day, censored lab values as #386 handled them (limit / 2) so the two years compare.
- **Calibration:** #386's leave-one-lake-out form, refitted on all 2021-2026 pairs before 1 May 2027 and frozen
  (file hash recorded), then applied unchanged to 2027 pairs.
- **Primary measure:** skill of the 2027 predictions against each lake's 2021-2026 mean (#386's skill definition), 95%
  interval by a bootstrap over lakes (2,000 resamples, seed 20271101). **Proposed margin:** useful if the interval's
  lower end is above 0 and the point estimate is at least 0.10. Why 0.10: #386 used it as its benefit margin; it
  means a tenth less squared error than simply quoting the lake's usual level, about the smallest gain a reader
  would notice. To settle in review.
- **Interval coverage:** the calibration's 80% prediction intervals hold between 70% and 90% of 2027 shallow-lake
  samples.
- **Supporting, reported:** Spearman association and the within-lake-and-season placebo, as in #386.
- **Minimum data:** at least 30 shallow-lake pairs at 6 or more lakes; below that, "too few to judge", not a fail,
  and 2028 is pooled with 2027 under the same frozen calibration. *Inferred:* #386 found 89 shallow pairs over five
  seasons, so one season may be short; weekly logging and three satellites should raise the pairing rate.
- **Collection, starting 1 May 2027:** a weekly refresh at the 38 chlorophyll points (the 14 shallow among them) and the
  14 bathing lakes, each run stored as its own root under `swimsignal-private/lake-observations-refresh/` with
  SHA256SUMS, so every reading is dated and logged before the Archive publishes the season's lab values (it lags by
  weeks). Lab values fetched once after 31 October 2027. Separate from every 2027 primary evaluation file.
- **Cost of collection,** from the scenes the tests' own searches found over each site in 2026
  (`refresh_lake_observations.py cost`): chlorophyll points 4,970 scenes a season, about **16,200 requests and 3.3 GB**
  at the test's clear share (worst case 35,300 requests, 13.6 GB); bathing lakes about 5,300 requests and 1.1 GB.
  About 1,000 requests and 200 MB a week for both. Public buckets, no account, no Open-Meteo calls.

## 6. Release checklist (Research/Labs page, historical first release)

1. The page reads `lake_observations.v1.json` through contract 1.1 (adopted).
2. `claim.public_wording` beside every reading; the image date with every value; `attribution` shown.
3. Image age computed at viewing time; an older reading labelled with its date; `season_closed` explained.
4. `too_small`, `series_partial` and `coverage_label` in plain words; no empty chart without a reason; sites that
   share a water body shown as one lake's sites, not as independent lakes.
5. Real observations plotted; measurement variability explained from `quality`; no small change described as a trend.
6. Out-of-season readings labelled as dated, experimental index readings.
7. No wording about algae, toxins, safety or swimming, on the page or in its metadata (titles, share cards, alt text).
8. Lab chlorophyll on its own axis with `lab_definition` (target, method note, censoring); never as if NDCI were µg/l.
9. `export_lake_observations.py check` passes on the committed file (CI).
10. Normal review under the delegated workflow (#469); rollback is removing the page's link to the file.

## 7. Queued next, as separate bounded developments (not started)

Each gets its own statement and branch under #469's workflow; none reruns an old test to "pass" it.
1. **Regional routing of the nine-company v2 model,** keeping the current model for United Utilities (v2 failed only
   there, +3.4%).
2. **Lake-specific concentration uncertainty:** the concentration study (#466) found its single spread too narrow at
   lakes (central 80% interval held 65%); a lake spread, judged on lake seasons it never read.
3. **Spill-duration calibration:** the calibration test (#461) stopped at its gate; a new attempt needs a new reason
   and must not set its gate from the 2024-25 out-of-fold figures. The January-August 2026 durations stay unread.

## 8. Handoff

- **PR #468** (this branch): contract 1.1, exporter, refresher, derived file, tests, this document.
- **PR #469** (Codex, `codex/research-recovery-20261030`): the research workflow and recovery register this follows.
- **Product chat:** builds the Labs page and viewer from contract 1.1; the release checklist above is its acceptance
  list.
- **Open for review:** the section 5 draft (margins and minimum data); where the weekly 2027 refresh runs (a scheduled
  workflow or by hand; it needs no secret); whether to run the full October refresh at the 14 bathing lakes
  (about 1,030 requests, 208 MB) for the experimental display.
