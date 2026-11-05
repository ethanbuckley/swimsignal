# BENCH, first task: E. coli over 900 at inland bathing waters (release candidate 0)

Written 5 November 2026, before any score below was computed. Part of BENCH in
[the ambitious-research scoping](AMBITIOUS-RESEARCH-SCOPING-2026-11.md) (section 5) and the
[recovery register](RESEARCH-RECOVERY-2026-10.md). **Exploratory, on seen data:** every outcome here was already
published, and several were used to develop the model. This is a benchmark of baselines, not a model test, and it
changes nothing in the forecast. No 2027 outcome is read; no active evaluation window is touched.

## Protocol (fixed before scoring)

- **Task.** For each Environment Agency lab sample at the 38 inland bathing waters in
  `data/research/ecoli_evidence.v1.json` (May to September 2023-26), give a probability that E. coli was over
  900 per 100 ml (`over`). One row per sample; 2,265 rows, from the committed file alone.
- **Split.** Leave one season out: a baseline that learns is fitted on the other seasons and scored on the left-out
  one, for each of 2023, 2024, 2025 and 2026; scores pool the four.
- **Baselines.**
  1. *Month-of-year rate*: the share of samples over 900 in the same calendar month, all sites pooled, in the other
     seasons.
  2. *Last sample*: the share over 900 in the other seasons among samples whose previous sample at the same site, in
     the same season, was over (or was not); a season's first sample at a site gets baseline 1.
  3. *Model hindsight*: `hindsight` as published, the production model's form refitted leaving out each year
     (docs/CONCENTRATION-STUDY-2026-11.md). Not the forecast the site issued. Present on 1,537 rows (2024-26, sites with
     a monitored overflow upstream, not archive-only); missing on the rest, never imputed.
- **Scores.** Brier score; Brier skill against baseline 1 (1 - Brier / Brier of baseline 1); AUC.
  On all rows for baselines 1 and 2, and on the 1,537 rows with a hindsight for all three.
- **Intervals.** 95%, from 2,000 bootstrap resamples of sites (seed 20261105), for each score and for each
  difference from baseline 1.
- **Reproduce.** `python scripts/bench_ecoli900.py` prints the scores as JSON. The test
  `tests/test_bench_ecoli900.py` holds them to 4 decimals.

## Licence manifest

| Column | Source | Licence |
|---|---|---|
| site, date and time, E. coli count and qualifier (`bwq`) | Environment Agency, bathing water quality data | Open Government Licence v3.0 |
| the same (`wqa`, 114 rows in 2026) | Environment Agency, Water Quality Archive | Open Government Licence v3.0 |
| `kind` (river or lake) | SwimSignal's spot list | MIT, with the repository |
| `hindsight` | SwimSignal's model output (MIT code), from archived Open-Meteo rain and replayed exposure from water companies' spill data | Already published in this file. Two open questions: whether values derived from Open-Meteo's free API may be redistributed in a dataset (Open-Meteo, Ethan's contact); and which companies' spill histories the replayed exposure draws on. The scoping lists Southern and Yorkshire Water event histories as having no stated licence; whether either sits behind this column has not been checked |
| `p_fwd` (review variant only) | SwimSignal's model output, `docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv` | As `hindsight` |

No rain column is included, so no Open-Meteo values are redistributed directly. No input here comes from a source
the scoping lists as not publishable.

## Results under the protocol (first run, 5 November 2026; `python scripts/bench_ecoli900.py`)

Brackets are 95% intervals from the bootstrap of sites. Skill is against baseline 1 (0 = no better, 1 = perfect).

**All rows** (2,265 samples, 230 over 900, 38 sites)

| Baseline | Brier | Skill vs month rate | AUC |
|---|---|---|---|
| 1. Month-of-year rate | 0.0931 [0.0588, 0.1334] | 0 | 0.433 [0.397, 0.484] |
| 2. Last sample | 0.0852 [0.0547, 0.1192] | 0.085 [0.023, 0.136] | 0.621 [0.531, 0.684] |

**Rows with a hindsight** (1,537 samples, 208 over 900, 32 sites)

| Baseline | Brier | Skill vs month rate | AUC |
|---|---|---|---|
| 1. Month-of-year rate | 0.1204 [0.0750, 0.1721] | 0 | 0.440 [0.402, 0.485] |
| 2. Last sample | 0.1099 [0.0718, 0.1522] | 0.087 [0.006, 0.139] | 0.644 [0.547, 0.708] |
| 3. Model hindsight | 0.0824 [0.0542, 0.1135] | 0.315 [0.173, 0.409] | 0.854 [0.757, 0.913] |

**What these say, and do not.**

- The month-of-year rate ranks samples worse than chance (AUC 0.43 to 0.44, interval under 0.5). Pooled across sites,
  a month's past rate does not tell this season's high samples from low ones. Fitted forward only it is still under
  or at chance (0.45, and 0.51 on 2025-26): so it is not only the known pull of leaving the scored season out. It is
  the reference for skill, not a serious forecast.
- The last sample at the same site helps a little (skill about 0.09, interval above 0).
- The model's hindsight does much better on the rows it covers: skill 0.32, AUC 0.85. **It is not prospective
  performance.** Refitted leaving each year out, it learned from later seasons as well as earlier ones, and the model
  was developed on these seasons. The review below gives the forward figure (skill 0.18), which is the fairer one. The
  live E. coli record is on the Accuracy page.
- The 728 rows with no hindsight (2023, sites with no overflow upstream, archive-only rows) are where a submitted model
  would have to stand without the production model's help.

## Review, 5 November 2026 (after the first run)

The protocol's scores above stand as fixed. A review then checked them; what it changed is a set of variants, added to
the script after the first run and so themselves exploratory.

**Checked and sound.**
- *Outcomes.* No sample lacks a count. Censored counts never straddle the line: every ">" count (12) is over 900 and
  every "<" count (351) is under it, and the `over` flag matches the count on every row. Two counts 6 minutes apart at
  one site (2023-08-25: 790 and 73) are kept as the file has them, a likely repeat sample; no sample is in the file
  twice from its two sources.
- *Populations.* Each table scores every baseline on the same rows; the hindsight rows are the 1,537 the concentration
  study used (its `p_loyo` matches `hindsight` on every row, to within the file's 3 decimals).
- *Intervals.* Sites are resampled with replacement, all of each site's rows together; every interval comes from the
  same draws for all the baselines in a table.

**Leakage found, and the variants that remove it.**
- *Future seasons.* Leaving one season out lets baselines 1 and 2 learn from later seasons, and the hindsight was
  refitted the same way. Variant **forward only**: baselines 1 and 2 fitted on earlier seasons alone (2023 cannot be
  scored), and the model's own forward fit (`p_fwd`: 2024 predicts 2025, 2024-25 predict 2026) in place of the
  hindsight. No hindsight appears in a forward table.
- *A result not yet known.* 37 samples follow the site's previous sample within 2 days, before its lab result would
  usually be out. Variant **result known**: a previous result counts only when its sample was at least 3 days older.
  Three days is an assumption about lab turnaround, not a checked figure.

**Forward only** (2025-26, the 1,023 rows with a forward model estimate, 106 over 900, 32 sites)

| Baseline | Brier | Skill vs month rate | AUC |
|---|---|---|---|
| 1. Month-of-year rate (earlier seasons) | 0.0927 | 0 | 0.512 [0.460, 0.559] |
| 2. Last sample (earlier seasons) | 0.0948 | -0.023 [-0.094, 0.045] | 0.588 [0.540, 0.631] |
| 2. The same, result known 3 days | 0.0955 | -0.030 [-0.108, 0.040] | 0.567 [0.498, 0.616] |
| 3. Model, forward fit | 0.0756 [0.0478, 0.1074] | 0.184 [0.068, 0.319] | 0.785 [0.674, 0.880] |

- **The last sample's small skill does not survive.** Fitted forward, with or without the 3-day rule, its interval
  spans zero.
- **The model keeps a clear lead, smaller than its hindsight suggests**: skill 0.18 forward against 0.32 in hindsight.
  Use 0.18 when quoting how the model does against these baselines; it is still a retrospective hindcast with
  archived rain and replayed exposure, not an issued forecast.

## Data card

- **Seen data.** All of it. The model whose hindsight is baseline 3 was developed on these seasons; its leave-one-year
  -out refit limits, but does not remove, that advantage.
- **Repeat samples.** Some sites were sampled again within a day or two, often after a high result. The task keeps
  every sample; a submitted model should not use a result it could not have known (see the review).
- **Gaps.** 2023 has no hindsight (`before_2024`); 306 rows at sites with no monitored overflow upstream and 101
  archive-only rows have none either. Samples are taken on the Agency's schedule, not at random: weekly or
  fortnightly, in daytime, in the season.
- **Lakes and rivers are pooled.** The site gives no E. coli warning at lakes; the scores here count them all the same.
- **Not claimed.** That the task represents UK water quality in general; that a better score means a model is fit to
  guide swimming; that a sample shows the water at another time.

## Open decisions (Ethan's)

The dataset's own licence and a DOI archive; whether outside submissions are accepted and who reviews them; the
Open-Meteo redistribution question above. This candidate derives everything from a file already in the repository,
so it publishes no new data until those are settled.
