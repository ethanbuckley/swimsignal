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
