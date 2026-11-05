# A lake E. coli chance from the lake's own rate: development test on 2024-2026 lake seasons

Written 5 November 2026, register row **3 / LAKE-CONC**, under `docs/RESEARCH-WORKFLOW.md`. **This protocol is
committed before any score is computed.** Development on seen data: every outcome below was read by #466, the lake
spread, #584's training rows and the forecast-record exploration (#586). Nothing here changes a production model, a
shown value, the 2027 primary evaluation or `shadow_lake_range_v1`.

## Continuation record

| Field | Content |
|---|---|
| Identity | LAKE-CONC; owner: Claude session "lake own rate" (started by the research session); this PR; code `scripts/lake_own_rate_test.py` |
| Evidence before this test | #586 (outcomes to 30 Sep 2026, hindsight estimates): at 12 lakes the over-900 estimate was no better than the usual lake rate (Brier 0.025 against 0.025) and ranked samples no better than chance (AUC 0.47), while each lake's own past over-900 rate ranked them well (AUC 0.81). The register names "a lake model that starts from the lake's own rate" as this row's candidate |
| Stage and claim | Development. Question: does an over-900 chance that starts from the lake's own sample rate, shrunk toward the generic lake forecast where the lake has few samples, beat the generic forecast and the simple references by a useful margin on grouped and time-embargoed splits of 2024-26? |
| Next deliverable | This test's readout; by its result, a separately labelled shadow log for the 2027 lake season, or a recorded reason to stop and what would reopen it |
| Milestone and budget | This PR. Offline: committed files only, no fetch, no dipcast import, no Open-Meteo or EA request. Runs in under a minute |
| Release route | A pass gives a shadow log only (`shadow_lake_own_rate_v1`, beside `shadow_lake_range_v1`); the over-900 chance stays off lake pages until the 2027 read. Rollback: the log is a separate table and a separate module behind a pinned file hash |

## 1. The question

The site computes an over-900 chance at lake spots with production's form (`ecoli.FEATURES`: rain at the spot,
exposure, lake flag, season) and hides it: at lakes it had no skill. That form has no term for the lake itself. The
lake range (#584, #585) already starts from the lake's own level for the *concentration*, through a random intercept
per bathing water, and is logged in `shadow_lake_range_v1` for the 2027 read; it is not retested here. The open
question is the *exceedance chance*: a result over 900 per 100 ml (the inland "sufficient" line, the line the site warns
at for rivers). #586 found a lake's own past rate ranks its samples far better than the generic estimate. This test asks
whether a chance built on that rate is useful, not only better ranked.

## 2. Data: committed files only

- **Rows.** `docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv`: the concentration study's 1,537 samples, 2024-26, at
  inland bathing waters with monitored overflows upstream. Its **637 lake rows** at 12 lake bathing waters on six
  water bodies (Windermere ×4, Coniston Water ×3, Rutland Water ×2, Derwent Water, Colwick, Frensham) are this test's
  population. Each row has the sample's E. coli count and the lab's qualifier ("<10" is a left-censored value).
- **Out-of-fold generic forecasts,** joined by row index to `docs/CONCENTRATION-STUDY-2026-11-predictions-loyo.csv`,
  `-cxy.csv` and `-fwd.csv`, which `scripts/concentration_study.py run` committed: `production_form` (production's
  lake form refitted in each fold, lead-0 archived forecast rain and replayed exposure: the generic lake forecast),
  and the concentration model's `candidate` P(>900), `candidate_median`, `candidate_sigma`, `candidate_logscore` and
  `background_logscore`. The join is checked: the atlas's `p_loyo` and `p_fwd` columns must equal `production_form`
  row for row.
- **Own history.** `data/research/ecoli_evidence.v1.json` (1.1.0): every EA sample at each lake bathing water, May to
  September 2023-26, including the 101 samples at study sites that are only in the Water Quality Archive. A lake's own
  rate uses every published sample, as the live site would, not only the rows with a generic forecast.
- **Seen.** All of these outcomes are development data. Grouped and time-embargoed splits (section 4) limit leakage
  between a row and the history that predicts it; they cannot make the data unseen. The candidate's form was chosen
  after #586 reported the own-rate AUC on these same rows. A pass therefore supports a shadow log and a prospective
  2027 read, never adoption.
- No fetch, no `dipcast` import, no quota. Input files are hashed before and after the run.

## 3. The models, fixed now

Let `g` be the generic forecast for a sample's day (out of fold), `k` and `n` the lake site's own samples over the
line and in total in the seasons its scheme allows (section 4), and `m` the shrinkage weight.

| Name | What it is | Role |
|---|---|---|
| **candidate** | `(k + m·g) / (n + m)`: the lake's own over-900 rate, shrunk toward production's lake form; `g` = `production_form` | Primary |
| production form | `production_form`: the deployed lake form refitted out of fold; no term for the lake | The generic lake forecast |
| concentration model | `candidate` P(>900) from the concentration study: site intercept plus weather, out of fold | Second generic, reported (it already carries a site level) |
| usual rate | the over-900 share of all lake samples at the 12 sites in the allowed seasons | Simple reference and the skill baseline |
| own rate | `k / n`, with the usual rate when `n` is 0 | Simple reference |
| last sample | the previous sample at the site within 30 days: the allowed seasons' lake over-900 rate after an over-900 sample, or after one under it; the usual rate when there is none | Simple reference |

**Shrinkage weight, fixed now: m = 10.** At 10 own samples the lake's own rate and the generic forecast weigh the
same; a lake's first season (about 20 samples) already makes its own rate dominate; after three seasons (about 60)
the generic contributes one part in seven. A lake with no samples gets the generic forecast: the fallback for
unsampled lakes. m = 5 and m = 30 are reported as sensitivity, never selected.

**Over 500 per 100 ml** (the line in the Excellent standard), secondary: the same candidate with `k` counted over 500
and `g` the concentration model's P(>500), computed from its out-of-fold median and noise level as a normal on log10
(an approximation: it ignores the spread of the site's intercept, small at a sampled site, understated at a held-out
lake). Production's form has no 500 line, so it is not a comparator there.

**Log-concentration**, secondary: a normal on log10 E. coli for each sample from (a) the lake's own level only: the
site's mean and standard deviation of log10 in the allowed seasons, a value below the lab's limit taken as 10, and
(b) that level shrunk toward the concentration model's out-of-fold median with the same `n / (n + m)` weight and the
model's noise level. Both scored by the censored log score ("<10" scored as the probability below 10), beside the
committed `candidate_logscore` and `background_logscore`. The expectation, stated now: the concentration model's
random intercept already does this, so (b) should not beat it; the comparison shows whether a plain own level is
enough for the concentration as it may be for the chance.

## 4. Schemes

| Scheme | The generic forecast is fitted on | The lake's own history (`k`, `n`) comes from | Rows |
|---|---|---|---|
| **leave-one-season-out** (main) | the other seasons, all sites (`-loyo.csv`) | the site's samples in the other seasons, 2023-26 | 637 |
| **leave-one-lake-out and season** | rows at neither this water body nor this season (`-cxy.csv`; Windermere's four sites are one group there, as are Coniston's three and Rutland's two) | the site's samples in the other seasons, 2023-26 | 637 |
| **forward** (time-embargoed) | earlier seasons (`-fwd.csv`: 2025 from 2024; 2026 from 2024-25) | the site's samples in earlier seasons only, 2023 included | 2025 and 2026 lake rows |

Leave-one-season-out is the main scheme (most rows). The other two are guardrails: the lake-out scheme shows what the
candidate does where the generic never saw the lake; the forward scheme shows what the site could have known on the day.

**Uncertainty.** 95% intervals from 2,000 cluster resamples of paired differences, seed 20261105, fixed now.
**Clusters are water body × season** (18 in the main scheme, 12 forward), so a Windermere season is one draw, and one
lake's bad summer cannot be split across draws. 18 clusters is few: intervals are approximate and reported as such,
and an ISO-week resample (the earlier tests' choice) is reported beside them as sensitivity.

## 5. Conditions, fixed now

Main target: a result over 900 per 100 ml. Main metric: the Brier score. Main scheme: leave-one-season-out, the 637
lake rows. Skill = 1 − Brier(candidate) / Brier(usual rate).

**Runnable gate.** At least 15 results over 900 in the main scheme's rows; with fewer, the verdict is "too few to
judge" and every figure below is description only. (#586 counted 16 on these rows.)

1. **Useful margin.** Skill over the usual rate at least **0.10**, with the interval of Brier(usual) − Brier(candidate)
   above zero. Why 0.10: the usual lake rate is a few per cent; a chance that cuts the usual rate's error by less than a
   tenth would read as that rate on nearly every day, and the page already shows a lake's past-sample count over 900
   (#585). Below that, a daily figure adds nothing a reader could act on.
2. **Beats the generic.** Brier(candidate) − Brier(production form) below zero, interval wholly below zero.
3. **Adds to the plain own rate.** Brier(candidate) − Brier(own rate) at or below zero (point estimate; interval
   reported). If the plain own rate is better, the daily generic part hurts and the candidate is not the right form.

**Guardrails.**

- **G1, not one lake's gain.** With Derwent Water's rows left out (it holds most of the over-900 results, #586's per-site
  counts), Brier(candidate) − Brier(production form) at or below zero and skill over the usual rate above zero (point
  estimates).
- **G2, no harm out of sample.** In the lake-out and forward schemes, the interval of Brier(candidate) − Brier(production
  form) is not wholly above zero.
- **G3, one cluster per water body.** Windermere's four sites (the brief said three; the data hold four: Fellfoot,
  Lakeside YMCA, Millerground Landing, Rayrigg Meadow) are one cluster in every resample and one group in the lake-out
  scheme, as are Coniston's three and Rutland's two.

**What each outcome means, decided now.**

- **Pass** (1, 2, 3 and G1-G3): an over-900 chance from the lake's own rate and the daily generic forecast is supported
  for development. Next: a separately labelled shadow log, `shadow_lake_own_rate_v1`, beside `shadow_lake_range_v1`,
  written by the forecast at lake bathing waters with own samples, from merge; the over-900 chance stays off lake pages;
  the 2027 lake samples (May-September) are the prospective read, on or after 15 October 2027, against production's lake
  form, the usual rate, the own rate and the last sample, with this margin.
- **Gain under the margin** (2, 3 and G1-G3 pass; the skill interval is above zero but skill is under 0.10): a real but
  small gain. The shadow log still goes in (it costs no request and changes no page), and the 2027 read applies the
  0.10 margin prospectively. The record says the margin was not met on seen data.
- **Fail** (2 fails, or the skill interval includes zero, or a guardrail fails): no shadow log, no lake chance. The record
  says which condition failed and by how much. Reopen when the 2027 lake season adds its samples (more over-900
  results) or with a candidate of a different kind, for example a within-season signal at the lake (wet against dry
  days from its own samples), not a rerun of this one.
- **3 fails** (the plain own rate beats the candidate): no shadow log of the candidate. The supported statement is the
  one #585 already shows, a lake's past samples and how many were over 900; the record says the daily generic part
  made the chance worse, and the next candidate must add information within a lake's season.

## 6. Reported whatever the result

For every scheme and line (900 and 500): Brier, skill over the usual rate, pooled AUC and the mean of per-site AUCs at
sites with both classes, log loss, and the paired Brier differences with both resampling schemes, for the candidate,
production form (900 only), concentration model, usual rate, own rate and last sample; the same by water body and by
season; m = 5 and 30; the log-concentration log scores of section 3; the six lake bathing waters with no overflow
upstream (Hampstead Heath ×3, the Serpentine, Henleaze, Cotswold: no generic forecast, so the candidate shrinks toward
the usual rate) as a supplementary population; input hashes; rows dropped at each rule.

---

## Results

Run 5 November 2026 by `scripts/lake_own_rate_test.py` after the protocol was pushed (95287b4c). Input hashes were the
same before and after. Files: `LAKE-OWN-RATE-TEST-2026-11-scores.json` (every figure below) and `-rows.csv` (the main
scheme's rows at 900 with every forecast). The join check passed: the atlas's `p_loyo` and `p_fwd` equal the
predictions files' `production_form` row for row. **Development on seen data; nothing here is a confirmation.**

**Population.** 637 lake rows, 12 lake bathing waters, 6 water bodies, 2024-26; 16 results over 900 and 30 over 500.
Own history per row: 40 to 61 samples (median 50) from the other seasons of 2023-26, 832 samples in all. 18
water-body-by-season clusters in the main scheme.

### Verdict: fail

| Condition (main scheme, 900 per 100 ml) | Result | |
|---|---|---|
| Gate: at least 15 results over 900 | 16 | runnable |
| 1. Skill over the usual rate at least 0.10, interval above zero | skill **0.042**; Brier(usual) − Brier(candidate) +0.00104 [−0.00235, +0.00574] (ISO weeks: [−0.00116, +0.00363]) | **fail** |
| 2. Beats production's form, interval wholly below zero | −0.00138 [−0.00610, +0.00198] (ISO weeks: [−0.00385, +0.00084]) | **fail** |
| 3. Not worse than the plain own rate | −0.00045 [−0.00205, +0.00073] | pass |
| G1. Without Derwent Water: at or below production, skill above zero | 578 rows, 4 events: 0.00711 against 0.00753, but skill **−0.010** | **fail** |
| G2. Lake-out and forward: no harm against production | −0.00304 [−0.00884, +0.00065] and −0.00167 [−0.00559, +0.00028] | pass |

By the rule fixed in section 5, **no shadow log and no lake chance.** The skill interval includes zero, production's
form is not beaten with the interval below zero, and the gain is one lake's.

### Every model on the main scheme, 900 per 100 ml

| Model | Brier | Skill over the usual rate | AUC, pooled | Mean AUC within a site (4 sites with an event) | Log loss |
|---|---|---|---|---|---|
| **candidate** (m = 10) | 0.02359 | +0.042 | 0.808 | 0.146 | 0.0997 |
| production form | 0.02496 | −0.013 | 0.468 | 0.398 | 0.1233 |
| concentration model (site intercept) | 0.02544 | −0.033 | 0.885 | 0.387 | 0.1001 |
| usual rate | 0.02463 | 0 | 0.374 | 0.441 | 0.1212 |
| own rate | 0.02404 | +0.024 | 0.784 | 0.184 | 0.1222 |
| last sample | 0.02374 | +0.036 | 0.610 | 0.481 | 0.1075 |
| candidate, m = 5 / m = 30 | 0.02375 / 0.02343 | +0.036 / +0.049 | 0.809 / 0.818 | 0.146 / 0.146 | 0.1022 / 0.0992 |

- **The ranking gain is between lakes, not within one.** The pooled AUC of 0.81 (as #586 found) comes from Derwent
  Water, which holds **12 of the 16** results over 900 in 59 rows; the other five water bodies hold 4 in 578. Within a
  site the own rate from the other seasons ran the wrong way: at Derwent Water the season with 8 of its 12 results
  (2025) had the lowest own rate from the other seasons (0.098, against 0.268 for 2024 and 0.225 for 2026). The mean
  within-site AUC of the candidate is 0.15. A lake's own rate says which lake runs high; it does not say which day or
  which season.
- **The Brier gain is small and one lake's.** 0.0236 against 0.0246 for the usual rate (4%, interval spanning zero).
  At Derwent Water the candidate scored 0.185 against 0.197 for the usual rate; at Coniston Water (4 events in 171
  rows) it was worse (0.0238 against 0.0228); at the four water bodies with no result over 900 every model scores near
  zero and the differences are in the fourth decimal.
- **The concentration model ranks best (AUC 0.89) and is worst calibrated** at the line (skill −0.033): its site
  intercept carries the between-lake information, but its P(>900) sits too high at the lakes that stay low. This was not
  a stated condition; it is noted for the next candidate (below), not acted on.
- **m barely matters** (0.0234 to 0.0238 across 5, 10, 30): with 40 or more own samples, the generic forecast's weight
  is small whichever m is used.

### The other schemes, 900 per 100 ml

| Scheme | Rows / events | Candidate | Production | Usual | Own | Skill | Candidate − production |
|---|---|---|---|---|---|---|---|
| leave-one-lake-out and season | 637 / 16 | 0.02358 | 0.02663 | 0.02463 | 0.02404 | +0.043 | −0.00304 [−0.00884, +0.00065]; ISO weeks [−0.00572, −0.00063] |
| forward (2025-26) | 407 / 13 | 0.02973 | 0.03140 | 0.03142 | 0.02977 | +0.054 | −0.00167 [−0.00559, +0.00028] |

Where the generic model never saw the lake, production's form is worse than the usual rate (AUC 0.21) and the candidate's
lead over it grows; the week-cluster interval is then below zero, the water-body-by-season interval is not. Forward,
with 2023 in the own history, the picture is the same as the main scheme: the own rate carries nearly all of it.

### 500 per 100 ml (secondary)

| Scheme | Events | Candidate | Concentration model | Usual | Own | Skill (candidate / own) | Candidate − concentration |
|---|---|---|---|---|---|---|---|
| leave-one-season-out | 30 | 0.04225 | 0.04516 | 0.04495 | 0.04211 | +0.060 / +0.063 | −0.0029 [−0.0087, +0.0005] |
| leave-one-lake-out and season | 30 | 0.04147 | 0.04663 | 0.04495 | 0.04211 | +0.077 / +0.063 | −0.0052 [−0.0185, +0.0027] |
| forward | 21 | 0.04512 | 0.04729 | 0.04926 | 0.04511 | +0.084 / +0.084 | −0.0022 [−0.0074, +0.0006] |

More events, the same shape: a 6-8% gain over the usual rate with every interval spanning zero; Derwent Water holds 17
of the 30; the plain own rate does as well as the candidate; the generic concentration model's P(>500) (the normal
approximation of section 3) is no better than the usual rate.

### Log-concentration (secondary)

Mean censored log score of log10 E. coli, main scheme: own level −1.196; own level shrunk toward the model −1.157;
concentration model −1.133; background (site intercept, no weather) −1.091. Own level shrunk minus the concentration
model: −0.024 [−0.100, +0.075]; own level minus background: −0.105 [−0.174, −0.025]. As expected in section 3, a plain
own level does not beat the random-intercept models on the concentration. Where the lake is held out of the generic
fit, the lake's own level is far better than the model's (−1.196 against −1.441, +0.245 [−0.008, +0.565]): the
model's lake prior is a poor stand-in for a lake it never sampled, which supports the "average lake" caution on the page.

### Supplementary: the six lake bathing waters with no overflow upstream

426 samples 2023-26 (Hampstead Heath ×3, the Serpentine, Henleaze, Cotswold), 4 over 900 and 16 over 500, leave one
season out, the candidate shrunk toward those six's usual rate. Over 900: 0.00943 against 0.00940 (usual). Over 500:
0.03598 against 0.03625, −0.00027 [−0.00129, +0.00097]; AUC 0.63 against 0.41. Nothing to act on; the past-sample tile
#585 shows at these waters already states their counts.

## What it means

**Established, on these seen rows:** an over-900 chance built on a lake's own rate scores 4% better than the usual
lake rate on 2024-26 lake samples, with the interval spanning zero, and ranks samples across lakes well (AUC 0.81)
because one lake, Derwent Water, holds three quarters of the results over 900. Within a lake, the own rate from other
seasons ranked a season's samples backwards. Production's lake form is no better than the usual rate on these rows in
any scheme (AUC 0.47; 0.21 where it never saw the lake).

**Precisely what failed:** condition 1 (skill 0.042 against 0.10, interval [−0.002, +0.006] on the Brier difference),
condition 2 (candidate minus production −0.0014, interval reaching +0.0020) and guardrail G1 (without Derwent Water,
skill −0.010 on 4 events). Conditions 3 and G2 passed.

**Not established:** that a daily lake chance cannot be built. The gate was met, but 16 events at 12 sites give an
interval about ±0.004 wide on a Brier of 0.025, so a 10% margin could not have been shown by any candidate on these
rows; the test was runnable and underpowered for its margin. It was also not shown that the ranking gain is useless: the
between-lake information it carries is what #585's past-sample tile already states in words.

**What would reopen this row's exceedance question** (not a rerun of this candidate): (a) the 2027 lake season's samples
(about 250 rows at these 12 sites, judged forward with the own history frozen before 1 May 2027), which doubles the
events only if a bad season recurs; (b) a candidate that carries a within-season signal at a lake, for example a
lake-specific wet-day response or a recalibrated line probability from the lake range model (whose site intercept
ranked best here, AUC 0.89, but sat too high at the line); (c) an account of Derwent Water's 2025 season, which held 8
results over 900 in 20 samples while its other seasons held 4 in 41. Each needs its own protocol before any outcome
is read.

**No change to the site:** the over-900 chance stays off lake pages; `shadow_lake_range_v1` runs unchanged for its
2027 read; no new shadow log is added.

## Continuation record (after the run)

| Field | Content |
|---|---|
| Identity | LAKE-CONC; this PR; `scripts/lake_own_rate_test.py`, `docs/LAKE-OWN-RATE-TEST-2026-11-scores.json`, `-rows.csv` |
| Evidence | Fail as stated: skill over the usual rate 0.042 [interval on the Brier difference −0.002 to +0.006] against a margin of 0.10; production not beaten with the interval below zero; the gain is Derwent Water's alone |
| Stage and claim | Development; the exceedance candidate is archived in this version. Supported: "a lake's own past rate says which lakes run high, not which day"; the lake range (concentration) stays in shadow for 2027 |
| Next deliverable | None scheduled for this candidate. The lake range's 2027 read (on or after 15 Oct 2027) stays the row's milestone; an exceedance candidate of a different kind, if one is proposed, gets its own protocol |
| Budget | None spent: offline, committed files, no request |
| Release route | Not applicable: no shadow log, no page change |
