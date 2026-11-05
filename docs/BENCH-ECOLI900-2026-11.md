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
| `hindsight` | SwimSignal's model output (MIT code), from archived Open-Meteo rain and replayed exposure from water companies' spill data | **Unresolved for a new dataset release.** It sits in a file this repository already publishes, but two questions are open: whether values derived from Open-Meteo's free API may be redistributed in a dataset (a question to Open-Meteo, Ethan's contact); and which companies' spill histories the replayed exposure draws on (the scoping lists Southern and Yorkshire Water event histories as having no stated licence; not checked here) |
| `p_fwd` (review variant only) | SwimSignal's model output, `docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv` | As `hindsight`: unresolved for a release |

No rain column is included, so no Open-Meteo values are redistributed directly. **A released dataset must leave out
`hindsight` and `p_fwd` until both questions are settled** (the scoping's stop rule: drop the column). The task and
baselines 1 and 2 stand without them; the model would then be scored by whoever runs it, as any submission.

## Results under the protocol (first run, 5 November 2026; `python scripts/bench_ecoli900.py`)

**Leave one season out trains on later seasons as well as earlier ones. These are not prospective backtests.** The
model hindsight was refitted the same way. The review below gives forward-only results.

Brackets are 95% intervals from the bootstrap of sites. Skill is against baseline 1 (0 = no better). The protocol's
AUC is pooled across seasons; the within-season AUC beside it was added by the review (see below for why).

**All rows** (2,265 samples, 230 over 900, 38 sites)

| Baseline | Brier | Skill vs month rate | AUC pooled | AUC within season |
|---|---|---|---|---|
| 1. Month-of-year rate | 0.0931 [0.0588, 0.1334] | 0 | 0.433 [0.397, 0.484] | 0.536 [0.486, 0.620] |
| 2. Last sample | 0.0852 [0.0547, 0.1192] | 0.085 [0.023, 0.136] | 0.621 [0.531, 0.684] | 0.613 [0.562, 0.641] |

**Rows with a hindsight** (1,537 samples, 208 over 900, 32 sites)

| Baseline | Brier | Skill vs month rate | AUC pooled | AUC within season |
|---|---|---|---|---|
| 1. Month-of-year rate | 0.1204 [0.0750, 0.1721] | 0 | 0.440 [0.402, 0.485] | 0.478 [0.437, 0.525] |
| 2. Last sample | 0.1099 [0.0718, 0.1522] | 0.087 [0.006, 0.139] | 0.644 [0.547, 0.708] | 0.636 [0.572, 0.673] |
| 3. Model hindsight | 0.0824 [0.0542, 0.1135] | 0.315 [0.173, 0.409] | 0.854 [0.757, 0.913] | 0.838 [0.753, 0.905] |

Paired Brier differences (same bootstrap draws; positive means the second baseline's error is lower): month rate minus
last sample 0.0105 [0.0006, 0.0215]; month rate minus hindsight 0.0379 [0.0143, 0.0637]; last sample minus hindsight
0.0275 [0.0118, 0.0462].

## Review, 5 November 2026 (after the first run)

The protocol's scores above stand as first recorded. Two reviews then checked them: my own, and an independent one
(which also confirmed 2,265 boolean outcomes and no duplicate site timestamps). What they changed is a set of variants
and added measures, put into the script after the first run and so themselves exploratory.

**Checked and sound.**
- *Outcomes.* No sample lacks a count. Censored counts never straddle the line: every ">" count (12) is over 900 and
  every "<" count (351) is under it, and the `over` flag matches the count on every row. Two counts 6 minutes apart at
  one site (2023-08-25: 790 and 73) are kept as the file has them, a likely repeat sample.
- *Populations.* Each table scores every baseline on the same rows; the hindsight rows are the 1,537 the concentration
  study used (its `p_loyo` matches `hindsight` on every row, to within the file's 3 decimals).
- *Intervals.* Sites are resampled with replacement, all of each site's rows together. **A difference between two
  baselines is judged only by its own paired interval**, from the same draws, never by whether two separate
  intervals overlap.

**The pooled AUC, qualified.** Under leave one season out each season's predictions come from a different fit, so a
pooled AUC also ranks one fit's numbers against another's. That can push it below 0.5 for a predictor with no such
fault. Within each season, where every prediction comes from one fit, the month-of-year rate's AUC is 0.536
[0.486, 0.620] on all rows and 0.500 [0.444, 0.556] fitted forward: no evidence that it ranks samples better or
worse than chance. The earlier statement that it "ranks worse than chance" is withdrawn.

**Leakage found, and the variants that remove it.**
- *Later seasons.* Variant **forward only**: baselines 1 and 2 fitted on earlier seasons alone (2023 cannot be
  scored), and the model's own forward fit (`p_fwd`: 2024 predicts 2025, 2024-25 predict 2026) in place of the
  hindsight. No hindsight appears in a forward table. This is closer to a backtest but still not prospective: the
  model's form was developed on these seasons, with archived rain and replayed exposure, not issued forecasts.
- *A result not yet known.* 37 samples follow the site's previous sample within 2 days. The file has no report dates,
  so when each result became known cannot be checked here; it is bracketed instead (below).

**Forward only** (2025-26, the 1,023 rows with a forward model estimate, 106 over 900, 32 sites)

| Baseline | Brier | Skill vs month rate | AUC within season |
|---|---|---|---|
| 1. Month-of-year rate (earlier seasons) | 0.0927 | 0 | 0.500 [0.444, 0.556] |
| 2. Last sample (earlier seasons) | 0.0948 | -0.023 [-0.094, 0.045] | 0.593 [0.542, 0.631] |
| 2. The same, a result counted only when 3 days old | 0.0955 | -0.030 [-0.108, 0.040] | 0.580 [0.521, 0.621] |
| 3. Model, forward fit | 0.0756 [0.0478, 0.1074] | 0.184 [0.068, 0.319] | 0.801 [0.708, 0.881] |

Paired Brier differences: month rate minus model 0.0171 [0.0062, 0.0321]; last sample minus model 0.0192
[0.0070, 0.0335]; month rate minus last sample -0.0021 [-0.0082, 0.0040].

- **On these rows the model's forward fit has lower error than both simple baselines**, by paired intervals that
  exclude zero. Its skill is 0.18; the hindsight's 0.32 above uses a different set of samples and a different fitting
  scheme, so the figures do not isolate the effect of the fitting scheme. This is a retrospective hindcast on seen
  seasons, not prospective performance.
- **The difference between the last sample and the month rate is uncertain on these rows**: its interval includes
  zero, with and without the turnaround rule.

**Turnaround: how the last sample depends on when a result is known** (forward fits, all 1,944 rows of 2024-26;
month rate minus last sample, so positive means the last sample helps)

| A previous result counts if its sample was at least | Paired difference |
|---|---|
| 0 days (the protocol) | 0.0063 [0.0007, 0.0127] |
| 1 day | 0.0060 [0.0002, 0.0128] |
| 2 days | 0.0054 [-0.0004, 0.0122] |
| 3 days | 0.0048 [-0.0005, 0.0110] |
| 5 days | 0.0028 [-0.0016, 0.0075] |
| 7 days | -0.0028 [-0.0083, 0.0019] |

The last sample's small advantage across all rows rests on results known within a day or so; from a 2-day
turnaround its interval includes zero. The Agency's actual reporting times are not in this file and have not been
checked, so which row applies is open. A submitted model should state what it assumes.

## Data card

- **Seen data.** All of it. The model whose estimates are baseline 3 was developed on these seasons; refitting it
  leaving a year out, or forward, limits but does not remove that advantage.
- **Repeat samples.** Some sites were sampled again within a day or two, often after a high result. The task keeps
  every sample; a submitted model should not use a result it could not have known (see the turnaround table).
- **Gaps.** 2023 has no hindsight (`before_2024`); 306 rows at sites with no monitored overflow upstream and 101
  archive-only rows have none either. Samples are taken on the Agency's schedule, not at random: weekly or
  fortnightly, in daytime, in the season.
- **Lakes and rivers are pooled.** The site gives no E. coli warning at lakes; the scores here count them all the same.
- **Not claimed.** That the task represents UK water quality in general; that a better score means a model is fit to
  guide swimming; that a sample shows the water at another time; that any figure here is prospective performance.

## Open decisions (Ethan's)

The dataset's own licence and a DOI archive; whether outside submissions are accepted and who reviews them; and the
two licence questions on `hindsight` and `p_fwd` above, which keep those columns out of any release until settled.
This candidate derives everything from files already in the repository and publishes no new data.
