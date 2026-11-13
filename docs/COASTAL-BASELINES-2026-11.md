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

## 10. Clarifications made while writing the harness, before the first score

Added 13 November 2026 after the harness was written and tested on made-up data, and before any real row was
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
