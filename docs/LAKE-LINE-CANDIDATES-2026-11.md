# Lake E. coli line chance and within-lake wet response: three candidates on 2024-2026 lake seasons

Written 6 November 2026, register row **3 / LAKE-CONC**, under `docs/RESEARCH-WORKFLOW.md`, as the development follow-up
to [LAKE-OWN-RATE-TEST-2026-11.md](LAKE-OWN-RATE-TEST-2026-11.md) (#625). **This protocol is committed and pushed before
any score of these candidates is computed.** #625's verdict ("fail") and its margins are unchanged; this is a new,
separately versioned analysis. Ethan's instruction for it (6 Nov 2026, relayed by the research session): develop "a
candidate based on the existing concentration-range model and/or a lake-specific wet-day response, with proper
group/time separation and an honest comparison to simple baselines".

## 0. What is seen, and what this can establish

- **Seen.** Every outcome scored here (637 EA samples at 12 lake bathing waters, May-September 2024-26) was read by
  #466, the lake spread, #584's training rows, #586 and #625. The candidates were designed after reading those results:
  #625 found the concentration model ranked lake samples best at the line (AUC 0.89) but sat too high there, and that a
  lake's own rate carries between-lake, not within-lake, information. Grouped and time-separated folds limit leakage of a
  row's own outcome into its forecast. They cannot make these rows unseen, and the design choices used them.
- **Not available.** #584's 2012-22 lake rows (Windermere ×4, Frensham) cannot be rebuilt: their archive rain for
  2012-2020 is not in the shared cache (it was fetched to #584's scratch copy, now gone), and rebuilding it needs
  Open-Meteo calls outside this task's budget. Only #584's committed summaries remain; nothing here uses them.
- **So:** a pass here supports a separately labelled shadow log and a prospective read on the 2027 lake season. It does
  not support showing a lake line chance, and it is not confirmation.
- **Power, stated before any score.** 16 results over 900 and 30 over 500 in the 637 rows. #625's intervals on a
  Brier difference at 900 were about ±0.004 around a Brier of 0.025: a 10% gain (0.0025) cannot be shown on these rows
  by any candidate. Within-site ranking uses all 637 concentrations (about 34-59 per site); a single site's Spearman rho
  has a standard error of about 0.14, so only the mean over 12 sites is informative.

## 1. Continuation record

| Field | Content |
|---|---|
| Identity | LAKE-CONC; owner: Claude session "lake own rate" (#625's); this PR; `scripts/lake_line_candidates.py` |
| Evidence before | #625 failed as stated (skill 0.042 vs 0.10; gain at Derwent Water only). #584 passed on 2012-22 for the concentration range. #466's site-intercept model ranked lakes best at the line but was too high there |
| Stage and claim | Development. Questions in section 4 |
| Next deliverable | This readout; by its rule (section 5), `shadow_lake_line_v1` beside `shadow_lake_range_v1`, or a recorded reason |
| Milestone and budget | This PR. Offline: cached inputs in a scratch root, no request; heavy-run lock held while fitting |
| Release route | Shadow only. No issued forecast, page, level or wording changes; no E. coli line on lake pages |

## 2. Data

- **Rows:** `scripts/concentration_study.py`'s `load_rows()` (train_ecoli's rows: inland bathing waters with monitored
  overflows upstream, 2024-26, archived lead-0 forecast rain at the spot, replayed lead-0 exposure), built in a scratch
  `DIPCAST_ROOT` holding copies of only the inputs it reads; the shared files are fingerprinted (SHA-256) before and
  after. The rows must equal `docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv` (bathing water, sample time, count) row
  for row, so the committed out-of-fold production forecasts join by index as in #625.
- **Fitting rows:** all 1,537 rows (900 river, 637 lake) outside the held-out fold, as #466 and lake-range-v1 were
  fitted. **Scored rows:** the 637 lake rows.
- **Own history** for the simple references: `data/research/ecoli_evidence.v1.json`, as #625 (2023-26, all samples).

## 3. The candidates and references, fixed now

All concentration models use `ecoli.FEATURES` (rain 48 h and 24 h at the spot, logit exposure, lake, lake × rain 48 h,
season) and `concentration_study.CensoredRI`'s censored normal on log10 E. coli ("<10" left-censored at 10, ">10000"
right-censored), with its own lake noise level. P(over a line) is the predictive mixture's tail above log10(line).

| Name | What it is | Role |
|---|---|---|
| **plain** | `CensoredRI(FEATURES, lake_sigma=True)`: lake-range-v1's form, refitted in each fold | The plain concentration model; base of A |
| **A** | plain's P(>900) and P(>500), recalibrated (below) | Candidate: calibrated line chance |
| **B** | plain plus a **lake-specific wet-day response**: a random slope per bathing water on `lake × wet`, with a fixed all-lake mean slope `lake × wet`, partially pooled (the slope's spread is fitted). `wet` = mean of the standardised log rain over 48 h and the standardised logit exposure, standardised on the fold's lake fitting rows. Intercept and slope are integrated by a 16 × 10 Gauss-Hermite grid; a lake not in the fold gets the prior (the all-lake response) | Candidate: within-lake response |
| **C** | B's P(>900) and P(>500), recalibrated as A | Candidate: both |
| production form | `production_form` from the committed predictions files: production's lake form refitted out of fold | Generic reference |
| #466 model | `candidate` from the committed predictions files (one noise level, soil moisture) | Reported, as in #625 |
| usual rate, own rate, last sample | As #625 (`scripts/lake_own_rate_test.py`), per scheme | Simple references |
| own-rate candidate | #625's candidate, m = 10 | Reported |

**72-hour rain** is not in the cached rows; the 48-hour window and the exposure (which carries spills from up to several
days before through travel time) stand in for "the preceding 24-72 h". Decided now.

**Recalibration (A, C), fixed now.** logit p' = a + b · logit p (p clipped to [0.0001, 0.9999]), a and b the posterior
mode under a ~ N(0, 1.5²), b ~ N(1, 0.5²), one map per line. It is fitted on **inner out-of-fold** predictions at the
lake rows of the outer fitting set: the outer fitting rows split by season, each season predicted by a model fitted on
the others. Where the outer fitting set holds one season (forward, 2025), no inner fold exists: A = plain and C = B,
reported as such. Nothing about the outer held-out rows enters the map.

## 4. Schemes, measures and questions

**Schemes** (every model refitted inside each fold; nothing fitted on a held-out row):

| Scheme | Held out | Folds | Scored lake rows |
|---|---|---|---|
| **leave-one-season-out** (main) | one season, all sites | 3 | 637 |
| **leave-one-lake-out and season** | one lake water body and one season: fitting rows are in neither (Windermere ×4, Coniston ×3, Rutland ×2 each one group) | 18 | 637 |
| **forward** | 2025 from 2024; 2026 from 2024-25 | 2 | 407 |

The committed production forecasts follow the same three fold definitions (`-loyo.csv`, `-cxy.csv`, `-fwd.csv`).

**Uncertainty:** 95% intervals from 2,000 resamples of water-body × season clusters (18; 12 forward) of paired
row differences, seed 20261106; ISO-week resampling reported beside them. For within-site rho differences, the resample
unit is the bathing water (12).

**Measures**, at 900 and 500 (Brier, skill over the usual rate, pooled AUC, mean within-site AUC over sites with both
outcomes, log loss, reliability: mean forecast against observed rate in five forecast bins, calibration-in-the-large and
calibration slope) and on the concentration (censored log score; mean over the 12 sites of within-site Spearman rho
between the forecast median, or the forecast chance for production, and the observed log10 count; central 80% coverage).

**Questions and conditions, main scheme:**

- **Q-A (a calibrated line chance), A and C separately:** (A1) Brier at 900 below production's form, interval wholly below
  zero; (A2) skill over the usual rate at least **0.10**, #625's margin unchanged, with the interval of Brier(usual) −
  Brier(candidate) above zero. Both: "a useful daily lake chance on seen data". (A3, reported) Brier(A) ≤ Brier(plain):
  recalibration helped.
- **Q-B (a within-lake wet response), B:** (B1) censored log score B − plain above zero, interval above zero; (B2) mean
  within-site rho B − plain above zero (point; interval reported).

**Shadow guardrails (non-inferiority), each candidate separately, fixed now:**

- **N1.** Brier(candidate) − Brier(production form) at 900: interval upper end below **+0.002** (about 8% of
  production's lake Brier) in all three schemes.
- **N2.** Brier(candidate) − Brier(plain) at 500: interval upper end below **+0.004** (about 8% of the usual rate's Brier
  there) in all three schemes. (Production has no 500 line.)
- **N3.** B and C: censored log score candidate − plain, interval lower end above **−0.02** in the main and forward schemes.
- **N4.** Without Derwent Water's rows, main scheme: Brier at 900 no more than the usual rate's + 0.001 (point).

## 5. What each outcome means, decided now

- **Every candidate that meets N1-N4** is logged in `shadow_lake_line_v1`, beside `shadow_lake_range_v1`, from merge.
  None is chosen among them on these rows. A candidate meeting N1-N4 but neither Q-A nor Q-B is logged as "not worse,
  gain not shown"; one meeting Q-A or Q-B is logged as "gain on seen data". The log stores P(>900) and P(>500) from each
  logged candidate, and B's median and 80% range when B or C is logged, at lake spots with overflows upstream, every
  lead, with a frozen model file pinned by hash. **No issued forecast, page, level, alert or wording changes; the over-900
  chance stays off lake pages.**
- **A candidate that fails a guardrail** is not logged; the record says which and by how much.
- **None meets N1-N4:** no logger; the code stays runnable; the record says what failed and what would reopen it.

**The 2027 read, fixed now for whatever is logged.** On or after **15 October 2027**: every EA sample with an E. coli
count, 1 May-30 September 2027, at a lake bathing water in the frozen file, paired with the logged row for its day issued
last before the sample time (lead 0; lead 1 reported). Against production's logged lake chance (`p_ecoli_gt900` in the
forecast log) and the usual lake rate frozen from 2023-26: Brier at 900 and 500, skill with the 0.10 margin, mean
within-site rho for B/C, intervals from ISO-week resamples (water bodies are too few for one season). A sample with no
logged row is counted, not filled. The read does not touch the 2027 primary evaluation or `shadow_lake_range_v1`.

## 6. Reported whatever the result

Every model in every scheme at both lines and on the concentration; by water body and by season; without Derwent Water;
the recalibration maps per fold; B's fitted slope spread and each lake's posterior mean slope; fit convergence; input
fingerprints; rows dropped. **Diagnosis, outside the scores:** what was different about Derwent Water's 2025 season (8
of its 12 results over 900): rain, exposure, sample timing and the candidates' forecasts on those days. It is described
only; nothing learned from it enters a scored candidate.

---

## Results

Run 6 November 2026 by `scripts/lake_line_candidates.py` (`rows`, `run`, `diagnose`, `export`) after the protocol was
pushed (3717a7aa). Scratch root with copies of the 2,074 cached input files; their SHA-256 were identical before and
after. The built rows equal the atlas row for row (rows file SHA-256 begins 037ce371). Every fit converged. The run took
about two minutes; the heavy-run lock was held for it. Files: `-scores.json` (every figure below, every fold's fit and
recalibration map), `-rows.csv` (each scored row's forecasts in each scheme), `-derwent.json` (the diagnosis).
**Development on seen data throughout.**

### Verdict

| Question or guardrail (main scheme unless named) | A (recalibrated) | B (lake wet response) | C (both) |
|---|---|---|---|
| A1. Brier at 900 below production, interval below zero | −0.00062 [−0.00432, +0.00314] **no** | (−0.00149 [−0.00777, +0.00287]) | −0.00081 [−0.00443, +0.00262] **no** |
| A2. Skill over the usual rate ≥ 0.10, interval above zero | 0.012 **no** | (0.047) | 0.019 **no** |
| A3. Brier at or below plain (reported) | 0.02434 vs 0.02415 **no** | | 0.02416 vs 0.02415 **no** |
| B1. Concentration log score above plain, interval above zero | | **+0.0205 [+0.0010, +0.0484] yes** (ISO weeks: [−0.0013, +0.0435]) | |
| B2. Mean within-site rho above plain | | −0.0045 [−0.057, +0.056] **no** | |
| N1. vs production at 900, upper end < +0.002, all schemes | **fails**: +0.0031 main | **fails**: +0.0029 main | **fails**: +0.0026 main |
| N2. vs plain at 500, upper end < +0.004, all schemes | passes | **fails**: +0.0050 lake-out | passes |
| N3. Concentration not worse than plain by 0.02 | passes (unchanged) | passes | passes |
| N4. Without Derwent Water, ≤ usual + 0.001 | passes | passes | passes |

**No candidate meets N1-N4, so by section 5 none is logged.** N1 fails in the main scheme only, and by interval width,
not by a loss: every candidate's Brier at 900 is below production's in all three schemes (points −0.0003 to −0.0025),
but the main scheme's interval upper ends (+0.0026 to +0.0031) pass the +0.002 margin. **That margin was narrower than
the intervals these 16 events allow (section 0 said so), so N1 could hardly have been met by any candidate here: a
design fault of this protocol, recorded, not corrected after the fact.** B also fails N2 at unseen lakes.

### The line chance, main scheme (637 rows; 16 over 900, 30 over 500)

| Model | Brier 900 | Skill | AUC pooled | AUC within site (4 sites) | Log loss | Calibration in the large / slope | Brier 500 | Skill 500 |
|---|---|---|---|---|---|---|---|---|
| **A** | 0.02434 | +0.012 | 0.881 | 0.46 | 0.0963 | +0.0014 / 0.93 | 0.04189 | +0.068 |
| **B** | 0.02347 | +0.047 | 0.891 | 0.47 | 0.0917 | +0.0093 / 1.12 | 0.04192 | +0.067 |
| **C** | 0.02416 | +0.019 | 0.886 | 0.47 | 0.0942 | +0.0005 / 0.91 | 0.04216 | +0.062 |
| plain | 0.02415 | +0.020 | 0.885 | 0.46 | 0.0948 | +0.0101 / 1.00 | 0.04199 | +0.066 |
| production form | 0.02496 | −0.013 | 0.468 | 0.40 | 0.1233 | +0.0009 / −0.28 | | |
| #466 model | 0.02544 | −0.033 | 0.885 | 0.39 | 0.1001 | −0.0054 / 0.60 | | |
| own-rate candidate (#625) | 0.02359 | +0.042 | 0.808 | 0.15 | 0.0997 | +0.0006 / 0.81 | | |
| usual rate | 0.02463 | 0 | 0.374 | 0.44 | 0.1212 | | 0.04495 | 0 |
| own rate | 0.02404 | +0.024 | 0.784 | 0.18 | 0.1222 | | 0.04211 | +0.063 |
| last sample | 0.02374 | +0.036 | 0.610 | 0.48 | 0.1075 | | 0.04376 | +0.027 |

- **The concentration models give the best line chance found so far at lakes, but not by a margin these rows can show.**
  B's skill of 0.047 is the highest of any lake line chance tested (the own-rate candidate 0.042, last sample 0.036);
  every interval against the usual rate spans zero ([−0.0032, +0.0075] for B). Nothing approaches #625's 0.10.
- **Recalibration did not help.** The plain line chance was already calibrated (slope 1.00) except for being too high on
  average (+0.010). The inner maps moved it to +0.0014, but with 7-13 inner events their intercepts ranged from −0.85
  to +0.22 between folds, and the Brier rose (A − plain +0.0002 [−0.0014, +0.0026]). #625's note that the concentration
  model "sat too high at the line" was about #466's model (one noise level), whose slope was 0.60.
- **Pooled AUC near 0.89 is between lakes again,** as #625 found for the own rate. Within a site, with 4 sites holding
  any result over 900, the AUCs (0.40-0.48) are noise.

### Within a lake: the concentration (all 637 rows)

| Scheme | Log score plain / B | B − plain | Mean within-site rho: plain / B / production | plain − production rho (by site) | B − plain rho |
|---|---|---|---|---|---|
| leave-one-season-out | −1.018 / −0.998 | **+0.0205 [+0.0010, +0.0484]** | 0.083 / 0.078 / −0.051 | +0.134 [−0.042, +0.286] | −0.005 [−0.057, +0.056] |
| leave-one-lake-out | −1.183 / −1.198 | **−0.0145 [−0.0262, −0.0009]** | 0.180 / 0.171 / −0.042 | **+0.222 [+0.105, +0.332]** | −0.009 [−0.042, +0.030] |
| forward | −1.027 / −1.007 | +0.0195 [−0.0083, +0.0615] | 0.222 / 0.240 / −0.078 | **+0.300 [+0.132, +0.472]** | +0.018 [−0.017, +0.058] |

Central 80% coverage, main scheme: plain 78.0%, B 77.9%.

- **The finding that holds across schemes is not a candidate's: the concentration model's median orders a lake's own
  samples better than production's line chance does.** Production's lake chance ranks a lake's samples slightly
  backwards (mean rho −0.04 to −0.08); the plain model's median ranks them forwards (0.08 to 0.22), with the
  difference's interval above zero at unseen lakes and forward. The size is modest: a rho of 0.2 orders pairs of samples
  correctly about 56% of the time.
- **B's lake-specific wet response fits known lakes' spread better but does not order their samples better.** Its log
  score gain in the main scheme (interval above zero by water-body season, spanning zero by ISO week) comes with no
  within-site rho gain, and at unseen lakes it is worse than plain: its fitted all-lake wet term misleads where the
  lake's own slope is unknown. The slope spread was about 0.2 log10 per unit of the wet index in every fold. The lakes
  with the steepest own slopes were Coniston Brown Howe and Monk Coniston and Windermere Millerground (+0.17 to +0.26);
  the flattest were Colwick (−0.27 to −0.34), Frensham and **Derwent Water (−0.06 to −0.11): the lake with most results
  over 900 responds less to wet days than the average lake.**

### Derwent Water's 2025 season (diagnosis, described only)

| Season | Samples | Over 900 | Median count | Median forecast rain 48 h | Rank correlation of count with rain / exposure |
|---|---|---|---|---|---|
| 2024 | 20 | 1 | 140 | 4.4 mm | +0.02 / +0.21 |
| 2025 | 20 | 8 | 445 | 5.7 mm | +0.07 / −0.16 |
| 2026 | 19 | 3 | 330 | 2.4 mm | −0.02 / +0.02 |

Monthly medians in 2025 rose from 59 (May) to 840 (July) and 980 (August); 2026 followed the same shape lower (390 in
July). **Six of the 12 results over 900 came with 0.6 mm of rain or less in the previous 48 hours**, including both of
2026's July results (1,300 and 1,500 at 0 mm, exposure near zero). The other water bodies had their wettest median in
2024, not 2025. So Derwent Water's high results are a summer-long rise that neither rain at the lake nor modelled spill
exposure tracks: a source the model does not see (candidates: a continuous discharge, wildfowl, low summer water;
none is identified here). **Inferred, not established.** Nothing from this diagnosis entered a candidate.

## What it means

**Established (seen 2024-26 data, grouped and time-separated folds):**
- No candidate gives a lake line chance with a gain these rows can show. The best (B) has skill 0.047 over the usual
  rate, interval spanning zero.
- The concentration model orders samples within a lake better than production's lake chance (rho difference +0.22 and
  +0.30 at unseen lakes and forward, intervals above zero). Production's lake chance carries no within-lake order.
- A lake-specific wet response improves the concentration fit at known lakes in one scheme only and does not improve
  within-lake order; it harms unseen lakes.

**Not established:** non-inferiority of any candidate to production at 900 (N1, interval width); anything about
2012-22 (rows not rebuildable without new Open-Meteo calls); the cause of Derwent Water's summer rise.

**Decision under the stated rule:** no `shadow_lake_line_v1` logger; no issued forecast, page or wording changes.

**Continuation decision (separate from the verdict, under the research workflow's "two decisions").** The 2027 lake
season can still test these candidates prospectively without a logger: `shadow_lake_range_v1` already records, for
every lake spot with overflows upstream and every lead, the inputs both models read (rain over 48 and 24 hours,
exposure, day, bathing water). So plain and B, with A's and C's maps, are **frozen now** in
`data/research/lake_line_frozen.v1.json` (SHA-256 `83a3a8d0929afb1ff178cc064e4fb8b4ec0af64810b5a2a1435108e3594a1c23`,
fitted on all 1,537 rows; `frozen_probs` reproduces them from the file alone, tested). The site does not load it
(tested). **The 2027 read for the frozen file, fixed now before any 2027 sample exists:** on or after 15 October 2027,
the rows and pairing of section 5 taken from `shadow_lake_range_v1` (a spot matched to a bathing water in the file
within 100 m; any other lake row uses the file's prior), each candidate's P(>900) and P(>500) computed by
`frozen_probs`, scored against production's logged lake chance and the frozen usual rate (0.02163 at 900, 0.04327 at
500): Brier, skill with the 0.10 margin, and, for plain and B, mean within-site rho against production's (the one result
here that held out of sample). ISO-week intervals. This is a read of a frozen file, not a shadow log; it changes nothing
live and does not touch the 2027 primary evaluation.

**What would reopen a lake line chance before 2027:** a measured input for Derwent Water's summer rise (for example a
continuous discharge record or a temperature or lake-level series), each under its own protocol; or #584's 2012-22 rows
rebuilt, which needs about 200 weighted Open-Meteo archive calls (a quota decision).

## Continuation record (after the run)

| Field | Content |
|---|---|
| Identity | LAKE-CONC; this PR; `scripts/lake_line_candidates.py`, `docs/LAKE-LINE-CANDIDATES-2026-11-scores.json`, `-rows.csv`, `-derwent.json`, `data/research/lake_line_frozen.v1.json` |
| Evidence | No candidate met the shadow guardrails (N1 by interval width; B also N2 at unseen lakes). B1 passed; Q-A and B2 failed. Concentration median orders a lake's samples better than production's chance (+0.22, +0.30, intervals above zero) |
| Stage and claim | Development. Supported: "the concentration model's median carries some within-lake order that production's lake chance lacks"; not supported: a daily lake line chance |
| Next deliverable | The 2027 read of the frozen file, on or after 15 Oct 2027, from `shadow_lake_range_v1`'s logged inputs |
| Budget | None spent: offline, cached inputs, no request |
| Release route | None live. The frozen file is research data; removing it changes nothing on the site |
