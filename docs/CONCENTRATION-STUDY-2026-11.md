# A catchment-aware distribution of E. coli: data audit, misses atlas and one exploratory comparison

Protocol written 30 October 2026, after the data audit (section 2) and **before any atlas figure or any score of the
candidate or its comparators was computed**. Committed and pushed before the `atlas` and `run` steps. Results go
below the line at the end. Nothing above the line changes after a result is seen.

Harness: `scripts/concentration_study.py` (`audit`, `atlas`, `run`). Tests: `tests/test_concentration_study.py`.
Assigned by Codex, coordinating at Ethan's explicit request, 30 October 2026, as a bounded exploratory study. It is
separate from the spill-duration work (PRs #459, #461), whose verdict and unread 2026 durations it does not touch.

**This is exploratory, on years every earlier E. coli test has used (2024-26). Nothing here is a fresh
confirmation, and nothing is adopted.** The 2027 pre-registration (`docs/PREREGISTRATION-2027.md`) and every
production path stay as they are: this work writes only to `scripts/concentration_study.py`, its test, and files
beside this document.

## 1. The question

The production E. coli model is a logistic regression for "over 900 cfu/100 ml" (`src/dipcast/model/ecoli.py`). It
throws away how far over or under a sample was, reads "<10" as 10, and has no term for a site's own background:
every site with the same rain and exposure gets the same chance.

**Does learning each bathing water's background separately from its response to rain and upstream spills improve
future predictions at the same site, and does it transfer to a catchment the model has not seen?** A good pooled
ranking of dirty against cleaner sites is not enough: the 2027 pre-registration already scores each site's own rate
as its baseline, and so does the background-only comparator here.

## 2. What was seen before this was written

- **The audit** (`-audit.json`, `-audit-by-year.csv`, `-audit-by-site.csv`; section 3): counts of rows, sites,
  site-years, censored values, wet samples and exceedances, per site and year. No prediction.
- **The catalogue of earlier tests** (section 4), from their documents. Their headline scores are published.
- **The 2026 issued-forecast summary** in the live `verification_live.json` (section 5).
- **Documentation:** the abstract-level descriptions of Seis et al. (2024) and of KWB's flusshygiene package (section 9).

Not seen: any out-of-fold prediction of these rows by any model in this study, the atlas, or any score below.

## 3. Data audit

### Sources, and what survives the pipeline

| Source | What it holds | What the pipeline keeps |
|---|---|---|
| `data/raw/bwq_samples.parquet` (EA bathing-water service, `ingest/bwq.py`, fetched 12 Sep 2026) | 2,165 rows, 38 inland bathing waters, 2023 to 7 Sep 2026. E. coli and enterococci counts, each with a qualifier (`=`, `<`, `>`), abnormal-weather and discountable flags | Qualifiers kept in the raw file. **Dropped** by `validate_ecoli.py`, so every model so far read "<10" as 10 and ">10000" as 10,000 (`PREREGISTRATION-2027.md` line 28 says the same) |
| `ecoli_samples.parquet` in the `state` release (Water Quality Archive, `ingest/wqa.py`, 30 Oct 2026) | 713 samples of 2026 to 28 Sep, statutory monitoring (purpose MS) only, determinand 2348 ("E. coli : Confirmed : MF", membrane filtration), qualifier kept | Used by the live verifier. 114 of its 2026 samples are not in the cached raw file (mostly September); the 601 in both agree on every count and qualifier |
| `ecoli_validation_rows.parquet` (frozen, SHA-256 `ec8c60b3…`, named by the 2027 pre-registration) | The 2,165 rows with reanalysis rain and hindcast exposure | Read only, never rewritten here |

- **Method and purpose.** The bathing-water service gives neither. The Archive's determinand code fixes the method
  (membrane filtration, confirmed) and `ingest/wqa.py` keeps only purpose MS, leaving out follow-up samples taken
  after a failure (SI), which would tilt the set towards bad days. The cached raw file is the bathing-water
  service's in-season list, which matched the Archive's MS samples on 28 Sep 2026 (`ingest/wqa.py` docstring).
- **Censoring as reported.** Every "<" value is 10 and every ">" value is 10,000. No other limit occurs. These are
  used as the censoring points; no detection limit is assumed beyond what the lab reported.
- **Repeats.** 14 raw rows repeat another row's site and time exactly, with identical values (12 sample times, one
  listed three times). They are one sample each here. The frozen validation rows, and so every earlier fit, carry them.
- **Abnormal weather and discountable:** no sample has an abnormal-weather flag; 3 are marked discountable. Kept, as
  every earlier test kept them.

### The study rows

`train_ecoli.py`'s rows (`soil_moisture_eval/diagnostics.rows_q1`): samples at bathing waters with overflows upstream,
2024-26, with archived lead-0 forecast rain, replayed lead-0 exposure and soil moisture at issue. From the main
checkout's caches on 30 October these are **1,548 rows, 1,537 after 11 repeat rows are dropped**, against the 1,502 the
production model was fitted on (the validation rows and exposure file are the same; *inferred:* the archived-rain
cache has grown since). So the production comparator is "the production model's form, refitted within each fold",
not the production file.

| | Rows | Sites | Over 900 | Below 10 ("<10") | Above 10,000 | Wet (48 h rain > 10 mm) | Wet and over 900 |
|---|---|---|---|---|---|---|---|
| Rivers 2024 | 284 | 14 | 99 | 1 | 7 | 49 | 34 |
| Rivers 2025 | 280 | 14 | 50 | 2 | 1 | 36 | 23 |
| Rivers 2026 | 336 | 20 | 43 | 1 | 2 | 39 | 18 |
| Lakes 2024 | 230 | 12 | 3 | 88 | 0 | 71 | 1 |
| Lakes 2025 | 225 | 12 | 9 | 77 | 0 | 77 | 2 |
| Lakes 2026 | 182 | 12 | 4 | 68 | 0 | 55 | 1 |

- 32 sites in 18 connected groups; 84 site-years. Fourteen rivers have three seasons (2024-26), six have only 2026.
- **Lakes almost never pass 900:** 16 of 637, and 12 of those at Derwent Water. A lake "over 900" score says little;
  lakes matter here for the distribution, where 36% of their results are "<10".
- **Rivers carry the question:** 192 of 900 over 900; wet samples are over 900 far more often (75 of 124).

### Data that exist but are not used here

- **Earlier seasons.** Most lake bathing waters were designated in 1998 and Ilkley in 2021; the EA services hold their
  samples from then. Only 2023 onwards is cached. Rivers designated in 2024 have no earlier samples to fetch.
- **Wales** (NRW, 185 samples at 11 stations, `SOIL-MOISTURE-WALES-CHECK-2026-11.md`) and **Wessex Water's** river
  samples (CC BY, 2020-25, used in `SOIL-MOISTURE-RIVERS-TEST-2026-11.md`). Not used: their inputs differ, and the
  sonde test that wanted the Wessex samples is parked until after the 2027 season (#403) and stays parked.
- **Private samples** (Waterhead, Sheffield lab data): not used; their permissions are separate.

## 4. What earlier tests already examined

All on the same samples, 2024-26 (1,502 rows unless stated). Row-level out-of-sample predictions were never saved,
only summaries.

| Test | PR | Verdict |
|---|---|---|
| Evaluation pins | #199 | adopted; no Brier change told from zero |
| Transport fit (speed, T90, dilution) | #248 | adopted; LOYO Brier 0.0938 to 0.0919 |
| Transport fit 2; urban dilution; spill size; PE size; die-off weather; dry spell; farm pressure; lake wind; lower lake line; flow dilution | #249, #172, #197, #210, #303, #318, #332, #345, #342, #404 | failed |
| Lake path; lake residence (at spill-time flow); lake distance | #176, #211/#213, #231 | adopted as defaults, changes near zero |
| Lake direction | #313 | passed, parked |
| Soil moisture (E. coli) | #344, #360, #361 | in the river model; its gain is in level, not in ranking within a station |
| Sonde signal | #403 | parked, never run |
| Sampling priorities | #381 | failed, synthetic only |

Production's own held-out figures (`data/processed/ecoli_model_eval.json`): LOYO Brier 0.0919, AUC 0.817 (rivers
0.758, lakes 0.538); leave-one-site-out lakes AUC 0.250. No earlier test modelled log concentration, used the
censoring, or pooled sites partially.

## 5. Issued forecasts

The only genuinely issued E. coli forecasts paired with samples are the live verifier's: **39 samples at 27 sites,
16 to 25 September 2026, 160 sample-lead pairs**, Brier 0.104 against climatology 0.100, AUC 0.51, 3 samples over 900.
Too few for an atlas. They are reported as they are, and nothing below is compared with them as if it were an issued
forecast.

## 6. The misses atlas (step `atlas`)

Production's form, refitted inside each fold, scored out of fold: **retrospective hindcasts with archived lead-0
forecast rain and replayed exposure, not issued forecasts**. Three schemes: forward in time (2024 predicts 2025;
2024-25 predict 2026), leave one year out, leave one site out. At the site's river warning line, 0.25:
- **false reassurance:** over 900 with a forecast under 0.25; **false alarm:** under 900 with 0.25 or more;
- broken down by river or lake, site, connected group, month, wet or dry (48 h rain over 10 mm), and whether any
  upstream rain was missing;
- each Brier split into a **between-site part** (a site's mean forecast against its rate) and a **within-site part**
  (the rest).

These are unexplained mismatches. None is evidence against a particular overflow, company or source.

## 7. The candidate and its comparators (step `run`)

**Candidate: a censored normal model of log10 E. coli with a random intercept per bathing water.**
- log10 E. coli = fixed responses + the site's background + noise. Noise N(0, σ²); background N(0, τ²) per site,
  integrated out with 24-point Gauss-Hermite quadrature. "<10" is left-censored at 10 and ">10000" right-censored at
  10,000.
- Fixed responses: production's eight inputs for rivers (48 h and 24 h rain, the logit of upstream exposure, lake,
  lake × 48 h rain, season as sine and cosine, soil moisture), standardised on the training fold. This is the small
  event-response part; the inputs are production's, so a difference comes from the site background and the
  concentration likelihood, not from new inputs.
- A site seen in training gets its background's posterior from its training samples; a new site gets the prior.
- P(over 900) from the mixture over the quadrature nodes. Fitted by maximum likelihood (L-BFGS-B).

**Comparators, all refitted inside each fold:**
1. **Production's form:** the logistic regression on the soil-moisture inputs for river rows, on the seven inputs for
   lake rows, both fitted on all training rows (as production's two files were).
2. **Rain and season:** the logistic regression on rain, lake and season (`train_ecoli.py`'s "rain + season").
3. **Site background only:** the same censored random-intercept model with only a lake term: each site's own level,
   no response to rain or spills.
4. Climatology by type, reported.

**One candidate.** No other structure (random slopes, other inputs, other likelihoods) is fitted or reported. If the
fit fails to converge in a fold, that is reported, not tuned.

## 8. Evaluation

- **Forward in time (primary, within-site):** 2024 predicts 2025; 2024-25 predict 2026. Each year's storms are
  never in its training. Scored on rivers at sites seen in training ("seen sites"); new 2026 sites reported apart.
- **Leave one year out:** reported.
- **Connected group and year held out (transfer):** for each connected group and year, trained on rows in neither
  that group nor that year, so neither a connected site nor the same storm is in training. Reported.
- Every standardisation and fit is inside the fold.
- **Measures:** Brier and false reassurance / false alarms at 0.25 for every predictor; for the two censored models,
  the mean log predictive score (density on the log10 scale, mass for a censored value) and a randomised PIT
  (deciles; the share inside the central 80%); within-site Spearman's ρ of each predictor against log10 E. coli
  (median over sites with at least 15 rows).
- **Uncertainty:** paired differences get 95% intervals from a bootstrap over ISO weeks (one storm reaches many
  sites in a week): 2,000 resamples, seed 0.

### Rules, fixed now

On rivers, forward in time, seen sites:
- **P1a.** The candidate's Brier is below the site-background-only comparator's, interval of the difference wholly
  below zero (it adds within-site skill to the site's own level).
- **P1b.** The candidate's Brier is below production's form, interval wholly below zero.
- **P2a.** The candidate's mean log score is above the background comparator's, interval wholly above zero.
- **P2b.** The candidate's central 80% interval holds between 70% and 90% of the observations.

**"Promising"** if all four hold; otherwise **"not shown"**. Either way it is a description of reused data. A
"promising" result earns a statement for a fresh period (2027 samples, or earlier lake seasons fetched for the
purpose), with its own approval. Nothing is deployed from this study.

## 9. Literature checked (bounded lookup: 6 of a budgeted 8 page requests, about 5 minutes)

- **Seis et al. (2024), Water Research 252, 121186.** From the abstract (KWR library record): five data-driven
  approaches at three German river bathing sites, including Bayesian models with Dirichlet-process clustering, linear
  regression, random forests and a "zero model"; validated with "longest dry period" and sequential training; the
  Bayesian approaches flagged over 90% of contamination events. *Not read:* the full paper (ScienceDirect refused;
  the TU Delft repository did not connect). Whether it pools across sites or treats censoring is not known from
  the abstract.
- **KWB flusshygiene (R):** a Bayesian linear model of E. coli concentration from flow, rain and treated wastewater,
  with bathing quality judged from predicted 90th and 95th percentiles. No censoring or pooling mentioned.
- Not looked up within the budget: the EA Water Quality Explorer's documentation. The method code and purpose
  filter above come from `ingest/wqa.py`, written against that service on 28 Sep 2026.
- CAMELS-GB v2 and UK-Flow15 hold hydrology only, no bacterial labels: for a later extension, not this study.

## 10. Resources

- Offline. No Open-Meteo calls, no measurement downloads. The study reads the main checkout's caches through
  `DIPCAST_ROOT`.
- `atlas`: 3 schemes of logistic fits, under a minute. `run`: 2 + 3 + about 50 folds, each with two censored fits;
  estimated 10 to 20 minutes on this Mac. Written files are small CSV and JSON beside this document, including
  row-level out-of-fold predictions (public EA samples, Open Government Licence).

---

## Results

Run 30 October 2026 from harness commit 99ee70b3 (protocol pushed in it), offline, on the main checkout's caches.
`atlas` under a minute; `run` 21:26:54 to 21:27:39 UTC, exit 0. Every censored fit converged (2 + 3 + 50 folds, two
fits each); τ 0.23 to 0.38 and σ 0.47 to 0.52 (log10 units) across folds. Files beside this document: `-atlas.csv`,
`-atlas-rows.csv`, `-predictions-fwd.csv`, `-predictions-loyo.csv`, `-predictions-cxy.csv`, `-scores.json`,
`-checks.json`. **All of it is reused 2024-26 data: description and exploration, not confirmation.**

### The misses atlas (production's form, refitted in each fold; retrospective, not issued)

| Scheme | Water | Samples | Over 900 | Hits | False reassurance | False alarms | Brier | Between-site part | Within-site part |
|---|---|---|---|---|---|---|---|---|---|
| Forward | rivers | 616 | 93 | 38 | 55 | 27 | 0.105 | 0.008 | 0.097 |
| Forward | lakes | 407 | 13 | 0 | 13 | 0 | 0.031 | 0.007 | 0.025 |
| Leave one year out | rivers | 900 | 192 | 121 | 71 | 124 | 0.123 | 0.011 | 0.112 |
| Leave one site out | rivers | 900 | 192 | 125 | 67 | 138 | 0.126 | 0.014 | 0.112 |

- **Nearly all the error is within sites, over time.** The between-site part is 0.008 to 0.014 of a river Brier of
  0.105 to 0.126. Ranking dirty against cleaner sites is not where the model loses.
- **Most missed exceedances come on dry days.** Forward, all water: 50 of the 62 exceedances on dry days (48 h rain
  of 10 mm or less) had a forecast under 0.25, against 18 of 44 on wet days.
- **Where, forward in time (rivers):** false reassurance concentrates at Ilkley (10 of 11 exceedances missed; mean
  forecast 0.09 against an observed share of 0.30), the Tone (5 of 12), the Nidd (5 of 7), the Swale (4 of 5, new in
  2026) and the Frome (4 of 5). False alarms concentrate at Friars Meadow on the Stour (8 forward, 20 leave-one-year-out).
- **Lakes:** every one of the 13 forward exceedances was missed, and 12 of the 16 in all years are at Derwent Water.
- **By month:** September has the most false alarms in every scheme (13 forward, 39 leave-one-year-out).
- **Coverage cannot be judged here:** every study row has complete upstream rain, because the row filter
  (`MAX_MISSING_SHARE`) drops the others upstream of this study.
- These are unexplained mismatches between forecast and sample. None is evidence against any overflow or source.

### Verdict: not shown

| Rule (rivers, forward, seen sites; 514 samples, 81 over 900) | Result |
|---|---|
| P1a candidate's Brier below background-only, interval below zero | **pass:** 0.1071 against 0.1729, difference [−0.082, −0.049] |
| P1b candidate's Brier below production's form, interval below zero | **fail:** 0.1071 against 0.1069, difference [−0.013, +0.013] |
| P2a log score above background-only, interval above zero | **pass:** −0.629 against −0.824, difference [+0.132, +0.257] |
| P2b central 80% interval holds 70% to 90% | **pass:** 85.8% |

### What else the run shows (reported, not rules)

| Rivers | Candidate | Production's form | Rain + season | Background only |
|---|---|---|---|---|
| Forward, seen sites: Brier | 0.107 | 0.107 | 0.121 | 0.173 |
| hits / false reassurance / false alarms at 0.25 | 59 / 22 / 104 | 36 / 45 / 26 | | |
| within-site ρ (median of 14 rivers) | 0.31 | 0.31 | | |
| Forward, new 2026 sites (102 samples): Brier | 0.095 | 0.095 | 0.102 | 0.138 |
| Group and year held out (transfer, 900 samples): Brier | 0.132 | 0.126 | 0.147 | 0.186 |

- **On rivers the candidate ties production's form.** Same Brier, same within-site ranking. It sits at another point
  at the 0.25 line: it halves false reassurance (22 against 45) and quadruples false alarms (104 against 26). That is a
  different threshold behaviour, not more skill.
- **The site background is real but small next to within-site variation:** its spread τ is about 0.29 log10 units
  (a factor of about 2), against within-site noise σ of about 0.5 (a factor of about 3) left after rain, exposure,
  soil and season. The background-only model is far worse than production (0.173 against 0.107): what happens on the
  day matters more than which site it is.
- **Site by site, forward** (a description): the background corrects persistent under-forecasts at Ilkley (mean
  forecast 0.23 against observed 0.30; production 0.09), the Tone, the Stour and the Frome, and overshoots where a
  site was dirtier in 2024 than later, most at Sheep's Green on the Cam (0.45 against 0.22). Five rivers better, nine
  worse. A background learned from one or two seasons carries a wet year forward.
- **Transfer does not help:** at a held-out connected group in a held-out year the candidate has only the prior, and
  is slightly worse than production's form (0.132 against 0.126; difference [−0.00003, +0.0116]).
- **Lakes: better ranking, wrong spread.** Within a lake site the candidate's median ranks samples better than
  production's chance of over 900 (median ρ 0.27 against −0.11 forward; 0.20 against −0.02 leave-one-year-out),
  because it uses every count and the "<10" results rather than 16 exceedances. But its central 80% interval holds
  only 65% of lake results (56% at held-out groups), with too many results in the top tenth: one noise level σ is
  shared by rivers and lakes, and lake counts have a heavier upper tail. *Inferred, not tested:* lakes need their
  own spread. That would be a second candidate, so it is not fitted here.

### What this means

- **The question as asked is answered for rivers, on these data: no.** Learning each site's background separately
  does not improve future within-site predictions beyond production's form, and does not transfer. The atlas says
  why: production's misses are within-site and mostly on dry days, and a site constant cannot see a dry-day spike.
- **The concentration target itself is not the problem:** the censored model matches the over-900 classifier on
  rivers while also giving a full distribution, a log score and calibrated intervals there (85.8%).
- Nothing is adopted. The 2027 pre-registration and every production path are unchanged.

### The data gap, and the smallest studies that could close it

1. **What explains within-site variation on dry days.** Neither the model nor the earlier tests had an input for it.
   Candidates with a physical reason: the river's level and whether it is rising or falling at the sample time
   (stage at the nearest gauge), live spill status at the sample time rather than replayed exposure, and the time
   since the last spill ended. The smallest observational study: at two or three rivers with many dry-day misses
   (Ilkley, the Tone, the Nidd), with a partner, sample twice weekly through one season, logging gauge stage and the
   live spill feed at each sample, plus several samples through two or three storms. Lab counts stay the reference.
2. **Lakes, using data that already exist.** Most lake bathing waters have EA samples back to 1998, but only 2023
   onwards is cached. A lake-only statement (its own spread, fitted on seasons before 2023 or on 2024-26, scored on
   seasons this study never read) could test the better within-lake ranking honestly. It needs a bounded fetch from
   the EA bathing-water service: about 18 lakes × 8 seasons × about 20 samples, a few dozen requests. It would need
   its own approval, and production's lake model is not used for alerts today.
3. **More seasons per river.** Fourteen rivers have three seasons and six have one. 2027 adds a season and is the
   frozen evaluation year; nothing here touches it.
