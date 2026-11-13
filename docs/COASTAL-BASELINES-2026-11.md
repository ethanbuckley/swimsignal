# Coastal samples: a coverage explorer and baselines for E. coli exceedance

Written 13 November 2026. Main was at `5f1ece11`. This is the first coastal step the
[recovery register](RESEARCH-RECOVERY-2026-10.md) names ("Sea currents/coastal model"): an auditable sample and
coverage table, then several simple baselines. It follows [the scoping note](SEA-CURRENTS-SCOPING-2026-10.md).

This file states the work **before any baseline is scored and before any sample result is joined to rain, spills or
the EA's forecast**. Results go below the line at the end. Nothing above the line changes after a result is seen; a
change is an amendment, dated, with both versions kept.

What was known when this was written: the scoping note's counts (32,874 samples at 404 sites, 1.5% over 500), the
site list, one day of the EA's 2022 risk predictions (422 rows, read to see whether the history is open), and the
shapes of the cached rain and spill tables. No sample result had been read by this work.

## What this is, and is not

- **It is development evidence on seen data.** The 2022 to 2026 samples have been summarised before (the scoping
  note, and the "typical readings" on the coverage page). Nothing here is a confirmation.
- **It is not a coastal forecast.** Nothing coastal is shown as a forecast on the site. Baselines are yardsticks: a
  later candidate model has to beat them.
- **It is not a test of tides or currents.** A weak spill-only association would not show that tides or currents add
  nothing. Dilution and direction can change how a spill reaches a beach.
- No frozen file, issued prediction, active window or the 2027 primary evaluation is touched.

## 1. Data, and how it is fetched

All from the Environment Agency, Open Government Licence v3.0, fetched from this Mac, not from CI
(`scripts/coastal_baselines/fetch.py`).

| What | Service | Requests, sized before the run | Cap | Pace |
|---|---|---|---|---|
| Site list with sampling point positions | bathing-water service, `doc/bathing-water.json` | 1 to 3 | 730 for the service | 10 s |
| E. coli, determinand 2348, statutory samples (`MS`), 2022 to 2026, at the 407 mapped archive points | Water Quality Archive | about 200 (17 groups of 25 points, 5 years, 2 to 3 pages) | 430 for the service | 3 s |
| Intestinal enterococci, determinand 3723, same | Water Quality Archive | about 200 | same cap | 3 s |
| The EA's daily risk predictions, 15 May to 30 September, 2022 to 2026 | bathing-water service, `stp-risk-prediction.json?predictedOn=` | 695 days, 1 a day, plus 1 probe | same 730 | 10 s |

- **Wall time:** archive about 400 requests at about 5 s each, 35 minutes. Bathing-water service about 700 requests
  at about 12 s each, 2.3 hours. The slow pace is deliberate: its gateway refused a home connection after 55 requests
  1.3 s apart on 3 October (`scripts/compare_prf.py`).
- **Refusals:** an HTTP 401, 403 or 429 stops that service for the run. It is recorded in the ledger and not
  retried. A 502, 503 or 504 is retried after 30 s and 90 s, and each try counts against the cap.
- **Ledger:** one line per request sent (time, what was asked, status, bytes, items, SHA-256 of the body). The
  ledger is committed. Raw responses are not.
- **Order:** E. coli, then enterococci, then the risk predictions newest season first, so a refusal costs the least
  useful part.
- **Open-Meteo calls: none.** Rain comes from radar already cached (section 4).
- **Not fetched, on purpose:** samples before 2022. The archive holds statutory samples back to at least 2012. They
  are left unread so that a later candidate can be frozen and then backtested on years that played no part in
  choosing it (workflow, "Backtest instead of waiting").

Shared inputs read in place, never written: the main checkout's `data/processed/overflows.parquet`,
`ea_events_*.parquet`, `dcww_ea_events.parquet` and `river_network.pkl`, and the per-overflow radar in
`swimsignal-private/radar-per-overflow/data/overflows/`. Each is fingerprinted before and after (size and SHA-256;
for the radar folder, file count, total bytes and a hash of the listing). The manifest records them.

## 2. The sample table

- One row per site and sampling time. Site is the bathing water id (`ukXXXXX-NNNNN`), through
  `data/raw/coastal_wqa_points.json`.
- Sampling time is the archive's `phenomenonTime`, read as UK local time where it carries no offset.
- A result of `<10` is kept as value 10 with qualifier `<`. A `>` result keeps its value and qualifier.
- Two results for one site and minute: if equal, one is kept. If they differ, the higher is kept. Both cases are
  counted in the manifest.
- Enterococci are joined to the E. coli row of the same site and minute.
- Kind (coast or estuary), region, sewerage company and position come from the site list.

## 3. The explorer

Tables, per site and year, and per site (`data/research/coastal/`):

- **Counts:** samples, first and last date, share below the detection limit.
- **Statutory lines:** share of single samples over each line the classification uses for coastal and transitional
  waters. E. coli 250 (excellent) and 500 (good, sufficient). Enterococci 100 (excellent), 185 (sufficient) and 200
  (good). The classification applies these to a percentile of four seasons, not to one sample. A single sample over
  a line is not a failed standard.
- **After rain:** share of samples with at least 1 mm in the 24 hours before, and at least 10 mm in the 72 hours
  before (rain as in section 4). Beside each, the same share over every season day at 12:00 UTC, so it can be seen
  whether sampling days were wetter or drier than the season. Only where radar is cached: 2025 and 2026.
- **Gaps:** in the season (15 May to 30 September), the longest run of days between samples, counting the run from
  15 May to the first sample and from the last to 30 September, and the number of calendar weeks with no sample.
- **Join coverage:** overflows within 2 km and 5 km, river-connected overflows (section 4), whether radar rain
  exists, whether spill files cover the year, whether an EA prediction was in force at each sample.

A site with no mapped archive point, or no sample, is listed with the reason. Missing rain is blank, never zero.

## 4. Target, baselines and their inputs

**Target.** A sample "exceeds" when its E. coli is over 500 cfu per 100 ml. A `<` result never exceeds. A `>`
result exceeds when its value is 500 or more. Rows scored are statutory samples from 1 May to 30 September.

A second target, over 250, is reported in the same tables for information. No decision rests on it.

**The history set.** For a fold with test years T and test sites G, the history set H is every sample row that is
not in a test year and not at a test site (all of 2022 to 2026 otherwise). Every fitted number comes from H.

| Baseline | What it predicts | Inputs | Years with the input |
|---|---|---|---|
| B0 pooled rate | One number: the exceedance rate in H | none | 2022–26 |
| B1 site rate | The site's own rate in H, shrunk towards the pooled rate | sample history | 2022–26 |
| B2 month | The pooled rate of the sample's calendar month in H | date | 2022–26 |
| R static reference | Logistic regression on the logit of the site rate and month indicators | history, date | 2022–26 |
| B3 last sample | Logistic regression on the previous result at the site | the previous statutory E. coli sample in the same year | 2022–26 |
| B4 recent rain | Logistic regression on rain before the sample | radar rain in the 24 h and 72 h before | 2025–26 |
| B5 recorded spills | Logistic regression on recorded spill hours before the sample | EA event files; overflow positions; river network | 2024–25 |
| B6 EA forecast | The exceedance rate in H under each level of the EA's risk prediction in force | the EA's daily risk predictions | 2022–26, if the fetch completes |
| B7 combined | R plus last sample plus rain; and, where spills also exist, plus spills | all of the above | 2025–26; with spills 2025 only |

Details, fixed here:

- **Site rate (B1, and inside R).** `(k + m·p0) / (n + m)`: k exceedances in n samples at the site in H, p0 the
  pooled rate in H, and m the prior strength from H by the method of moments
  (`m = p0(1−p0)/v − 1`, v the between-site variance of the raw rates less the sampling part `p0(1−p0)·mean(1/n)`,
  sites with at least 10 samples; m held between 1 and 500). For a row in H, its own year is left out of k and n,
  so a training row never sees its own outcome. A held-out site has no history: its site rate is p0, so B1 equals
  B0 there. That is the honest position for a beach with no samples.
- **Month (B2).** Months with fewer than 50 rows in H use the pooled rate.
- **Last sample (B3).** `x1 = log10(previous result) − 1`, zero when there is none. `x2 = 1` when there is none. The
  previous sample is the latest earlier statutory sample at the site in the same calendar year. Its result may not
  have been published by the next sampling day. This baseline is therefore a little optimistic about what was known.
- **Rain (B4).** A site's hourly rain is the mean of `radar_mm` (the 3 × 3 km block) over the overflows within 5 km
  of its sampling point, from the per-overflow radar files (21 November 2024 to 25 October 2026). `r24` and `r72`
  are the sums over the 24 and 72 hours whose hour-ending label is at or before the sample time. Features:
  `log1p(r24)`, `log1p(r72)`. A row is not covered when the site has no overflow within 5 km or the mean radar
  `coverage` over the 72 hours is under 0.9. This is observed rain up to the sample: a same-day input, not a rain
  forecast.
- **Spills (B5).** Spill hours are the hours of recorded events that fall in the 72 hours before the sample, summed
  over overflows in three groups that do not overlap:
  `near`: within 2 km of the sampling point in a straight line;
  `ring`: 2 to 5 km;
  `river`: more than 5 km away, on a river link from which the network runs downstream, within 30 km, to a network
  node within 2 km of the sampling point (the river network as main loads it, `upstream_edges`).
  Features: `log1p` of each. An overflow with no event in a year's file counts as zero hours: the files cannot tell a
  silent overflow from an unmonitored one. Positions are the overflow table's, which are often not where the water
  enters the sea (scoping note, section 3). These are records published after the year, not a live feed.
- **EA forecast (B6).** The prediction in force is the latest one for the site published at or before the sample
  time and not yet expired (`compare_prf.ea_at_samples`' rule). Rows with none in force are not scored for B6.
  Also reported: how many exceedances had an "increased" prediction in force, and the exceedance rate under it. Where
  the EA marks a site-season as having its own pollution risk forecast (`prfOriginType = PRF_PROVIDED`), the same
  figures are given for those site-seasons alone. In seasons where the field is absent, that split is not made.
- **Each input alone and on top of R.** B3 to B6 are each fitted two ways: on their own features, and added to R's
  features. The second answers the useful question: does the input add anything once the site and month are known?
- **Logistic regressions** are scikit-learn's `LogisticRegression` with `C = 1e6` (in effect no penalty), fitted on
  rows of H that have the input.

## 5. Held-out splits

Sites are put in five groups by `int(sha256(site id)[:8], 16) mod 5`.

| Split | Test rows | History H |
|---|---|---|
| Y, whole years | each year in turn | the other years, all sites |
| G, whole sites | each site group in turn, all years | the other four groups |
| YG, both | one year at one site group, for every pair | other years at other site groups |
| F, forward | 2025, then 2026 | earlier years only, all sites |

Predictions are pooled over a split's folds. Split Y uses later years to predict earlier ones; split F does not.
A baseline is scored only on the years its input exists, and each table gives B0 and R on the same rows.

## 6. Scores and intervals

For each baseline and split, on its covered rows: rows, sites, exceedances; Brier score; Brier skill against B0
and against R (`1 − BS/BS_ref`); AUC; log loss (probabilities held within 0.001 and 0.999); mean prediction beside
the observed rate; and per-year point estimates.

Intervals are 95% percentile intervals from 2,000 bootstrap resamples of whole sites (seed 20261113), with every
difference paired inside each resample. Years are too few to resample (two to five), so the per-year figures stand
in for year-to-year spread. That is a real limit: the intervals describe site-to-site sampling only.

**The comparison that decides the next step:** for rain, spills, last sample and the EA forecast, the Brier
difference of "R plus the input" against R, in splits Y and YG. An input is called **supported as a candidate
input** when the interval excludes zero in its favour in both. No correction is made for looking at several inputs;
this is development evidence and is labelled so.

## 7. What each outcome leads to

Stated before the scores:

- **Rain or spills supported:** the next deliverable is a coastal exposure candidate built on that input (distance
  and time weights fitted with nested held-out fitting on 2022–26), frozen, then backtested on the unread 2012–21
  samples. Rain reaches back that far in archives; spill records mostly do not, so a rain-led candidate is the one a
  backtest can confirm.
- **Neither supported:** not a closure. The next deliverable is a diagnosis: which sites carry the exceedances, how
  many came in dry weather, and whether outlet position, river flow or tide state at the sample hour is the missing
  input. The currents question stays open, with what data it needs.
- **The EA forecast beats the rest where it runs:** it becomes the comparator any coastal candidate has to beat
  there, and a candidate is aimed at the sites without one, or at a probability and lead time the EA's two-level
  same-day warning does not give.
- **Too few exceedances to tell** (intervals too wide to separate R from R plus any input): say so, with the number
  of exceedances, and name the extra seasons needed. The 2012–21 samples are the cheapest source.
- **Whatever the scores:** the explorer tables can go on as a public research observation after a design pass. No
  coastal forecast is shown.

## 8. Limits known before scoring

- Two thirds of results are below the detection limit and exceedances are about 1.5%. A whole season has about 100.
- Samples are taken in the season, in working hours, on planned days. They are not a random sample of sea states,
  tides or hours.
- 19 sites have no mapped archive point and 3 mapped sites had no sample in the scoping fetch.
- Bathing-water rules let the EA disregard some samples taken during a short-term pollution warning. The archive's
  `MS` rows do not say which. Whether that removes exceedances from this table is not known.
- The EA's forecast may itself use rain. Its warning and the rain baseline are not independent sources.
- Split Y trains on later years. Rows of one site in one season are not independent, which the site bootstrap covers
  only in part.

## 9. Budget

Requests as in section 1. Scoring: one process, up to 4 cores, a 30-minute cap, the river network loaded once
(113 MB file). No model artifact is written to a shared folder. Outputs go to a scratch directory, then the small
tables are committed.

## 10. Clarifications made while writing the scoring code, before the first score

Added 13 November 2026 after the scoring code was written and tested on made-up data, and before any real row was
scored. They settle points the sections above left open. They change no rule.

- **The deciding comparison fits both sides on the same rows.** "R plus the input" can only be fitted on history
  rows that have the input. R is therefore refitted on those same rows (written `R|input`) for that comparison.
  Otherwise the difference would mix the input's effect with a recalibration to the years the input covers. R
  fitted on all history rows is still reported beside it.
- **A radar hour with no value adds nothing to a rain sum.** Whether the window counts is decided by the coverage
  rule alone (mean coverage over the 72 hours of at least 0.9).
- **The EA forecast baseline needs at least 20 history rows under a level** to use that level's rate. With fewer it
  uses the pooled rate.
- **Split F needs an earlier year that has the input.** So it tests rain on 2026 only and spills on 2025 only.
- **B7 with spills has one year (2025).** It is scored in split G only.
- **AUC is computed on predictions pooled over a split's folds.** B0 is one number per fold, so its pooled AUC is
  near 0.5 but not exactly 0.5. Per-year figures are given beside the pooled ones.

---

*Results go below this line.*

## Results, 13 November 2026

Run from code at `0cbf932a`, after the protocol (`ee9dc62f`) and the scoring code (`56907fdc`) were pushed. Every
figure is **development evidence on seen data** (2022 to 2026). None is a confirmation, and nothing here is shown on
the site.

### In short

- **Rain is supported as a candidate input**, by the rule in section 6, for E. coli over 500. Added to the site and
  month reference, it lowers the Brier score in whole-year and year-and-site held-out splits, and raises the AUC
  from 0.73 to 0.81 (whole years). The gain is small in absolute terms: the best Brier skill against the pooled rate
  is 3.4%.
- **Recorded spills, the last sample and the EA's forecast are not supported** by that rule. Each improves ranking
  (AUC) in every split, but the Brier interval includes zero in the whole-year split.
- **Rain and the EA's forecast are level on Brier score.** Rain ranks samples better (AUC about 0.70 against 0.54 on
  the same rows).
- **This does not show that tides, currents or spills add nothing.** Spill positions are often not where water
  enters the sea, and direction and dilution were not modelled.

### Fetch

- 1,029 requests: 331 to the Water Quality Archive, 698 to the bathing-water service. Both stayed under their caps
  (430 and 730). **No refusal.** One 502 and two dropped connections were retried.
- All 1,026 saved responses hash to the value the ledger recorded for them. Every paged request group added up to
  the archive's own `totalItems`.
- The EA's daily risk predictions are open back to 2022: 301,362 rows over 695 season days. The field that says
  whether a site has its own pollution risk forecast (`prfOriginType`) is filled from 2024 only.
- Shared inputs were unchanged by the build (fingerprints before and after are identical).
- Manifest: `data/research/coastal/manifest.json`. Committed tables: `data/research/coastal/`. Raw responses,
  per-sample rain and held-out predictions are not committed; the manifest hashes them.

### Explorer

Tables: `sites.csv` (426 sites), `site_year.csv` (2,003 site-seasons), `year_summary.csv`.

| Year | Samples | Sites | Over 250 | Over 500 | Enterococci samples | Enterococci over 185 | With rain | With spill hours | EA prediction in force |
|---|---|---|---|---|---|---|---|---|---|
| 2022 | 6,758 | 400 | 225 | 105 | 6,754 | 314 | 0 | 0 | 6,274 |
| 2023 | 6,735 | 401 | 268 | 106 | 6,733 | 291 | 0 | 0 | 6,295 |
| 2024 | 6,464 | 400 | 271 | 132 | 6,464 | 285 | 0 | 6,464 | 6,032 |
| 2025 | 6,579 | 399 | 188 | 84 | 6,579 | 201 | 6,534 | 6,579 | 6,164 |
| 2026 | 6,339 | 403 | 180 | 72 | 6,282 | 204 | 6,303 | 0 | 6,270 |

- **Coverage.** 404 of 426 sites have samples. 19 have no mapped archive point and 3 mapped points (Ingoldmells,
  Clevedon Beach, Dunster Beach) have no statutory E. coli result in 2022 to 2026. 398 sites have all five seasons.
- **Gaps.** The median site-season has 19 samples, a longest gap of 14 to 15.5 days and 5 to 7 calendar weeks
  with no sample. 31 to 56 site-seasons a year have a gap over 21 days.
- **Where exceedances are.** 195 sites had at least one sample over 500; 209 had none. The 20 worst sites hold 32%
  of all exceedances, the 40 worst 48%. North West sites run at 5.7% over 500, against 0.8% in the South West and
  Anglian regions.
- **After rain.** In 2025, 34.8% of samples had at least 1 mm in the 24 hours before, against 33.7% of season days
  at noon. In 2026, 29.0% against 25.4%. Sampling days were not drier than the season.
- **Overflows.** 351 sampled sites have an overflow within 2 km, 401 within 5 km, and 139 have river-connected
  overflows further away. The nearest overflow is 0.69 km away at the median site.

### Baselines, E. coli over 500, whole-year split (Y)

Brier skill and AUC with 95% site-bootstrap intervals. Rain covers 2025–26, spills 2024–25.

| Baseline | Rows | Exceedances | Brier | Brier skill against B0 (95%) | AUC (95%) |
|---|---|---|---|---|---|
| B0 pooled rate | 32,868 | 499 | 0.01496 | 0 | 0.444 (0.417 to 0.470) |
| B1 site rate | 32,868 | 499 | 0.01478 | 0.012 (0.005 to 0.020) | 0.678 (0.634 to 0.717) |
| B2 month | 32,868 | 499 | 0.01494 | 0.001 (−0.000 to 0.002) | 0.576 (0.549 to 0.602) |
| R site and month | 32,868 | 499 | 0.01472 | 0.016 (0.007 to 0.026) | 0.702 (0.664 to 0.739) |
| B3 last sample | 32,868 | 499 | 0.01485 | 0.007 (0.003 to 0.011) | 0.623 (0.589 to 0.655) |
| R + last sample | 32,868 | 499 | 0.01470 | 0.017 (0.009 to 0.026) | 0.715 (0.679 to 0.750) |
| B4 rain | 12,837 | 156 | 0.01185 | 0.014 (0.008 to 0.020) | 0.707 (0.661 to 0.754) |
| R, rain rows | 12,837 | 156 | 0.01176 | 0.021 (0.011 to 0.031) | 0.728 (0.679 to 0.771) |
| R + rain | 12,837 | 156 | 0.01163 | 0.033 (0.018 to 0.049) | 0.808 (0.770 to 0.842) |
| B5 spills | 13,042 | 216 | 0.01620 | 0.006 (−0.002 to 0.015) | 0.608 (0.563 to 0.656) |
| R, spill rows | 13,042 | 216 | 0.01621 | 0.006 (−0.003 to 0.015) | 0.622 (0.569 to 0.674) |
| R + spills | 13,042 | 216 | 0.01621 | 0.005 (−0.004 to 0.016) | 0.707 (0.666 to 0.747) |
| B6 EA forecast | 31,035 | 481 | 0.01512 | 0.009 (0.004 to 0.014) | 0.494 (0.466 to 0.522) |
| R, EA forecast rows | 31,035 | 481 | 0.01502 | 0.016 (0.007 to 0.026) | 0.706 (0.667 to 0.742) |
| R + EA forecast | 31,035 | 481 | 0.01497 | 0.019 (0.009 to 0.030) | 0.724 (0.687 to 0.757) |
| B7 R + last + rain | 12,837 | 156 | 0.01161 | 0.034 (0.018 to 0.051) | 0.811 (0.770 to 0.846) |

The other splits are in `data/research/coastal/scores.md`. In the splits that hold out whole sites (G and YG), B1
equals B0 by design: a beach with no history gets the pooled rate. There R is the month alone.

### The deciding comparison: R plus the input against R fitted on the same rows

Brier difference below zero favours the input.

| Input | Split | Rows | Exceedances | Brier difference (95%) | AUC, R alone | AUC with the input |
|---|---|---|---|---|---|---|
| Last sample | Y | 32,868 | 499 | −0.00002 (−0.00008 to 0.00004) | 0.702 | 0.715 |
| Last sample | YG | 32,868 | 499 | −0.00008 (−0.00012 to −0.00004) | 0.575 | 0.641 |
| **Rain** | **Y** | 12,837 | 156 | **−0.00014 (−0.00028 to −0.00001)** | 0.728 | 0.808 |
| **Rain** | **YG** | 12,837 | 156 | **−0.00010 (−0.00020 to −0.00002)** | 0.607 | 0.743 |
| Spills | Y | 13,042 | 216 | 0.00000 (−0.00013 to 0.00013) | 0.622 | 0.707 |
| Spills | YG | 13,042 | 216 | −0.00010 (−0.00018 to −0.00001) | 0.483 | 0.602 |
| EA forecast | Y | 31,035 | 481 | −0.00005 (−0.00014 to 0.00004) | 0.706 | 0.724 |
| EA forecast | YG | 31,035 | 481 | −0.00011 (−0.00016 to −0.00006) | 0.572 | 0.601 |

- **Supported as a candidate input: rain only.** Its upper bounds (−0.00001 and −0.00002) are close to zero. No
  correction for several inputs was made, as the protocol said. Forward (train on earlier years only), rain's
  difference on 2026 is −0.00010 (−0.00027 to 0.00007), with AUC 0.75 to 0.82.
- **Spills** help ranking in every split (AUC +0.06 to +0.12) and lower the Brier score when whole sites are held
  out, but not in the whole-year split, where the two seasons with spill files are 2024 and 2025 alone.
- **For information, over 250:** no input is supported. Every input's Brier interval excludes zero in YG and
  includes it in Y.

### The EA's forecast

- An "increased" prediction was in force at 660 of 31,035 scored samples. 66 of them exceeded 500 (10.0%),
  against 1.4% under "normal". So it caught 14% of exceedances (66 of 481).
- At the site-seasons where the EA runs its own pollution risk forecast (2024–26 only), it caught 26% (45 of 170).
  "Increased" there is followed by an exceedance 10.1% of the time.
- **Rain against the EA's forecast**, on the same 12,357 rows: Brier difference 0.00001 (−0.00015 to 0.00018) in
  split Y, so level. AUC 0.705 against 0.544. At the EA's own forecast sites (5,801 rows), level again on Brier,
  0.00015 (−0.00014 to 0.00050), with rain's AUC higher by 0.095 (0.004 to 0.187).
- So section 7's outcome "the EA forecast beats the rest where it runs" did not occur. It stays the comparator a
  coastal candidate must also beat, because it is what a swimmer is shown today.

## What follows

Section 7 said: rain supported leads to a coastal exposure candidate built on rain, frozen, then backtested on the
unread 2012–21 samples. That is the next deliverable.

1. **Candidate C1, rain at the beach.** Site and month (R), the last sample, and rain over 24 and 72 hours, with the
   window lengths and the distance rule chosen by nested held-out fitting on 2022–26. It must use **archive rain**,
   not radar: radar starts in November 2024 and the backtest years need the same source. Cached archive rain
   (`data/cache/rain_nine`) covers 158 of the 183 coastal 0.1° cells for December 2023 to 2025 and 169 cells for
   January to August 2026. 2022, 2023 and 2012–21 would be new Open-Meteo archive calls: about 183 cells × 12
   seasons at weight about 1.1, roughly 2,400 weighted calls, which is 8 days at 300 a day from spare budget. A
   protocol must state that before any call.
2. **Frozen-model backtest on 2012–21.** Fetch the 2012–21 statutory samples (about 350 archive requests) only after
   C1 is frozen and its hash committed. Compare with R, B0 and the EA's forecast on the same rows.
3. **Spills and currents stay open.** Spills ranked samples in every split. The useful next step there is outlet
   position (the EA profiles' outfall points, `docs/OVERFLOW-SEA-OUTFALLS-2026-10.md`) and spill direction, which
   needs currents (a Copernicus Marine account, Ethan's step). A weak spill-only Brier result does not close it.
4. **The explorer** can become a Research page observation after a design pass (`docs/DESIGN.md`). It would show
   past samples and coverage only. No coastal forecast is shown.

Owner: the research sessions. Milestone: C1's protocol, pushed before any new rain call.

## Limits of these results

- Seen data. These outcomes were summarised before (scoping note, typical readings), and this work chose its
  baselines knowing the shape of the data, though not these scores.
- The Brier skills are small (at best 3.4% against the pooled rate). None of these models is a usable public
  probability, and none is shown.
- Rain here is radar observed up to the sample time: a same-day input, not a forecast. Inferred, not checked: a live
  feed arrives with some delay, so the last hour or so before a sample would not be known at issue time.
- The last-sample baseline assumes the previous result was known by the next sampling day, which flatters it a
  little.
- Two to five years per input: the intervals describe site-to-site sampling, not year-to-year spread.
- Spill hours count overflows with no event as zero, and use overflow positions that are often not the outlet.
