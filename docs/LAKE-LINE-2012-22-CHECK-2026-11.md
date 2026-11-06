# The frozen lake concentration models on 2012-2022 lake seasons: an out-of-time development comparison

Written 6 November 2026, register row **3 / LAKE-CONC**, under the workflow's "Develop promising work now". **This
protocol is committed and pushed before any request is made and before any 2012-22 outcome is joined to these
models.** Ethan's instruction (6 Nov, relayed by the research session): "assess whether that historical data can be
fetched within an explicit free/capped budget and used for a properly labelled additional development comparison now,
without disturbing active evaluations. Reuse caches first; do not describe previously examined outcomes as independent
confirmation."

## What this is, and what it is not

- **An out-of-time development comparison on previously examined 2012-22 outcomes.** #584 examined these 962 samples
  for the lake range's coverage and log score. They were never used to fit, select or tune the line candidates, the
  plain model or B. Both are read from `data/research/lake_line_frozen.v1.json` (SHA-256 `83a3a8d0…`), frozen in
  8cb721d6 before this protocol, and are **not refitted**.
- **Not independent or fresh confirmation.** The outcomes were seen by #584. The question tested here comes from
  2024-26 rows that were themselves seen.
- **Nothing active is touched.** All writes go to scratch. `shadow_lake_range_v1`, its 2027 read, the frozen file's
  2027 read and the 2027 primary evaluation are unaffected.

## Feasibility and budget, fixed now

- **Cache first.** 2012-22 archive rain for these cells is not cached (the shared cache holds them for 2023-26 only;
  #584's scratch cache is gone). Every cached 2023-26 archive file is copied read-only into a scratch `DIPCAST_CACHE`;
  only missing cell-years are fetched.
- **Caps:** at most **300 weighted Open-Meteo archive calls** (#584 measured 172 for these cells) and **10 EA
  requests** (#584 used 5). Fetched as #584 did: ten cells a request, half a second apart, `strict`, so the first 429
  or failed request stops the fetch. A ledger records every request and its weight.
- **Scratch only:** `DIPCAST_ROOT`, `DIPCAST_STATE`, `DIPCAST_CACHE` and `LAKE_RANGE_OUT` point at scratch copies;
  shared inputs are fingerprinted (SHA-256) before and after. The heavy-run lock is held for the fetch and fits.
- **The rows are #584's.** Built by #584's own code from an archive of its results commit (0be59d2d), with the same
  shared inputs (all dated before #584's run). **Reproduction check, before any new score:** the test rows must number
  962 and the training rows 1,672, and #584's `run` stage on them must reproduce its committed scores
  (`docs/LAKE-RANGE-HINDCAST-TEST-2026-11-scores.json`). If not, the difference is recorded and the comparison is
  labelled as on rebuilt rows.

## Models, fixed now

| Name | Source | Role |
|---|---|---|
| **plain** | the frozen file's plain model: median and P(over a line) | Candidate |
| **B** | the frozen file's lake wet-response model | Candidate |
| production form | production's over-900 logistic form, refitted on #584's 2023-26 training rows, as #584 did | Primary comparator |
| deployed production | `data/processed/ecoli_model.json` as deployed (fitted on 2024-26) | Reported |
| lake-range-v1 | `data/processed/ecoli_lake_range.json` (frozen, #585): median and range | Reported (concentration) |
| usual rate, own rate | frozen from 2023-26: the lake rate (0.02163 over 900, 0.04327 over 500) and each site's rate | Reported |

Known differences, stated now: the frozen models were fitted on archived **forecast** rain; these rows carry
**reanalysis** rain. The past exposure uses today's overflow list and a spill model trained on 2023-25 (#584's known
weakness), so exposure before 2020 is approximate.

## The question, measure and uncertainty, fixed now

- **Primary: does the concentration model's median order a lake's own samples better than production's chance?**
  Measure: the mean over the 5 sites (Windermere ×4, Frensham Great Pond) of the within-site Spearman rho between a
  model's daily score and the observed log10 E. coli (the plain or B median; production's P(over 900)). Differences
  **plain − production form** and **B − production form**, with a 95% interval from 2,000 resamples of site × season
  clusters (55 clusters, seed 20261106). It **holds** for a model if its interval is above zero.
- **Reported whatever the result:** rho by site and by season (2012-13 sat above #584's range); the same differences
  against deployed production; censored log score of plain, B and lake-range-v1 and their differences; central 80%
  coverage; over 500: Brier, skill against the usual rate, pooled AUC (28 results: weak). **Over 900: 9 results, too
  few to judge a line chance; counts only, no score.**

## What each outcome leads to, fixed now

- **Holds for plain or B:** the within-lake ordering carries back eleven seasons in time at these lakes. Next
  deliverable: a proposal to show the concentration median's day-to-day direction at lake spots (higher or lower than
  the lake's usual), judged by the existing 2027 read of `shadow_lake_range_v1`. It is not a line chance, and it needs
  Ethan's wording decision before anything is shown.
- **Fails for both:** the ordering found on 2024-26 does not carry back in time at these lakes. Record it; keep only the
  2027 reads already fixed; no display proposal.
- **Holds for one only:** recorded with both figures; the proposal names that model only.

---

## Results

Run 6 November 2026 after the protocol was pushed (96392731). Label: **an out-of-time development comparison on
previously examined 2012-22 outcomes.**

**Cost and feasibility.** The fetch was feasible within the stated caps.

| Request | Count | Cap |
|---|---|---|
| Open-Meteo archive (6 cells, 2012-2022, ten cells a request, half a second apart, strict) | 11 requests, **172.2 weighted calls**, none refused | 300 |
| EA bathing-water listings (one per sampling point) | 5 | 10 |

The ledger is `LAKE-LINE-2012-22-CHECK-2026-11-ledger.json`. Every 2023-26 archive file was copied read-only from the
shared cache into a scratch cache first. The 2,469 shared input files had the same SHA-256 before and after, and no
file was written to the shared cache. The heavy-run lock was held throughout.

**Reproduction check (before any new score).** #584's own code (an archive of 0be59d2d) rebuilt **962 test rows and
1,672 training rows**, with the same drops at every rule (994 listed, 32 repeats; 478 training rows with no overflow
upstream, 14 repeats, 1 rain window). Rerunning #584's `run` stage gave the same verdicts on all three conditions, with
the candidate's 80% coverage 78.9% and log score −0.9049 against #584's −0.9048. One contrast (candidate − shared
spread) moved from +0.0678 to +0.0700. Inferred: the rows are #584's, refitted under newer numerical libraries.
**Correction to the protocol:** there are 52 site × season clusters, not 55, because Rayrigg Meadow has no samples in
2012-14.

**Population.** 962 rows at 5 sites (Windermere ×4, Frensham Great Pond), 2012-22; 477 below the lab's limit; 28 over
500; **9 over 900, too few to judge a line chance: counts only.**

### Primary: within-lake order

| Score | Mean within-site rho | Lakeside YMCA | Millerground | Rayrigg Meadow | Fellfoot | Frensham |
|---|---|---|---|---|---|---|
| plain median (frozen) | **0.279** | 0.335 | 0.329 | 0.418 | 0.134 | 0.179 |
| B median (frozen) | **0.305** | 0.335 | 0.337 | 0.393 | 0.161 | 0.300 |
| lake-range-v1 median (frozen, live on the page) | 0.287 | 0.347 | 0.346 | 0.431 | 0.137 | 0.173 |
| production form, refitted on 2023-26 | 0.123 | 0.191 | 0.221 | 0.238 | −0.021 | −0.014 |
| deployed production | 0.074 | 0.083 | 0.119 | 0.122 | −0.025 | 0.070 |

| Difference (95% interval, site × season clusters) | |
|---|---|
| **plain − production form** | **+0.156 [+0.090, +0.218]: holds** |
| **B − production form** | **+0.182 [+0.122, +0.244]: holds** |
| plain − deployed production | +0.205 [+0.127, +0.287] |
| B − deployed production | +0.231 [+0.165, +0.305] |
| B − plain | +0.026 [−0.010, +0.063] |

**By season** (mean within-site rho, plain / B / production form): 2012 0.40 / 0.42 / 0.09; 2013 0.06 / 0.24 / −0.05;
2014 0.04 / 0.11 / 0.04; 2015 0.12 / 0.21 / 0.19; 2016 0.33 / 0.34 / 0.17; 2017 0.25 / 0.32 / 0.31; 2018 0.32 / 0.41 /
0.07; 2019 0.47 / 0.47 / 0.11; 2021 0.30 / 0.27 / 0.01; 2022 0.29 / 0.26 / 0.27. 2020 had 15 samples (3 per site):
too few. Plain's median ranks above production's chance in 8 of 10 seasons (not 2015 or 2017); B's in 9 of 10 (not
2022, by 0.003).

### Reported: the concentration and the 500 line

| | plain | B | lake-range-v1 |
|---|---|---|---|
| Mean censored log score | −0.933 | −0.937 | **−0.903** |
| Inside the central 80% range | 80.3% | 79.4% | 78.9% |

plain − lake-range-v1: −0.031 [−0.048, −0.012]; B − lake-range-v1: −0.035 [−0.055, −0.012]; B − plain: −0.004
[−0.017, +0.010]. **The live lake-range-v1 fits these seasons' spread better than either frozen model.** It was fitted
on archive rain, as these rows are; the frozen models were fitted on archived forecast rain (stated in the protocol).

Over 500 (28 results, weak): Brier plain 0.02829, B 0.02821, lake-range-v1 0.02816, usual rate 0.02846, own rate
0.02890; skill over the usual rate 0.006 to 0.011. No line chance is supported.

## What it means

- **Established, as development evidence:** at Windermere and Frensham, over 11 seasons none of these models was fitted
  on, the concentration models' median orders a lake's own samples better than production's lake chance. Both frozen
  models hold, with intervals clear of zero. This matches the 2024-26 result (+0.22 and +0.30 at unseen lakes and
  forward).
- **Less independent than it looks:** #584 already published per-site rho for its candidate, a close relative of
  lake-range-v1, against production's chance on these rows (0.34 against 0.18 at Lakeside, and so on). What is new
  here: two models frozen on 2024-26 data, an interval, and the per-season breakdown.
- **Not established:** a line chance (9 results over 900); that B's wet response adds order (+0.026, interval spanning
  zero); anything at lakes other than Windermere and Frensham.

**Next deliverable, by the stated rule ("holds"):** a proposal to show the day-to-day direction of the concentration
median at lake spots, judged by the existing 2027 read of `shadow_lake_range_v1`. It is a wording proposal for Ethan,
not a line chance and not built here. **Proposal:** the lake-range tile already shows "most likely about X". Add one
line saying whether today's likely reading is higher or lower than this lake's usual for the time of year, from
lake-range-v1 itself (its median against its own median on a dry day at the same date). No new model is needed:
lake-range-v1 is the best-fitting of the three here and orders samples as well as plain. **Its 2027 check, fixed now:**
the same within-site rho comparison against production's logged lake chance, on 2027 samples paired with lead-0 rows
of `shadow_lake_range_v1`. Nothing is shown until Ethan decides the wording.

## What can actually run in 2027 from the shadow inputs

| Read | Inputs it needs | Where they come from | Status |
|---|---|---|---|
| lake-range-v1 range and order (the existing 2027 read, `docs/LAKE-RANGE-WORDING-2026-11.md`) | its logged median and range | `shadow_lake_range_v1`, written by every build since #585 (merged 1 Nov 2026) | **Logging, checked 6 Nov** (below) |
| Frozen plain, B, A, C (`lake_line_frozen.v1.json`) | rain over 48 and 24 hours, exposure, day, bathing water | the same `shadow_lake_range_v1` rows, computed by `frozen_probs` at read time | Runnable: needs no logger |
| Production's lake chance, the comparator | `p_ecoli` | `forecast_points` in the same state database, same issues | Logged since 15 Sep 2026 |
| The usual and own rates | frozen 2023-26 rates | the frozen file and `ecoli_evidence.v1.json` | Frozen |
| 2027 outcomes | EA samples, May-September 2027 | the EA's bathing-water service | From May 2027 |

**Readiness, checked 6 November 2026 by the research session.** It opened the state release's `dipcast.duckdb` (6 Nov
01:17 UTC, 238,563,328 bytes) read-only in its own scratch; this session did not download it.

- `shadow_lake_range_v1` holds **4,180 rows**, issued 1 Nov 19:25 UTC to 6 Nov 01:10 UTC: 836 issue times × 5 leads
  (0-4), 22 lake spots per issue (basis "tested" 5, "own samples" 6, "average lake" 11).
- **All 11 lake bathing waters in lake-range-v1 have rows** (190 each): the five tested sites (Windermere ×4, Frensham),
  Coniston ×3, Rutland ×2 and Derwent Water.
- `rain_48h`, `rain_24h`, `risk` and `median`: no nulls. Every row so far is out of season, as expected in November.
  Rule `lake-range-v1`, model hash `5566b12e…`, and each build's code version are recorded.
- `forecast_points.p_ecoli` exists, so production's lake chance is logged on the same issues.
- Builds per day, 1-5 Nov: 7, 10, 4, 4, 12. The cadence is irregular, but every day has at least one issue, which is
  enough for a read that pairs each sample with the last issue before it (lead 0).

**Gap: Colwick Country Park (West Lake), `ukf1400-09750`, has no row,** not even as an "average lake" spot. That is
correct, not a fault. The site's pin for Colwick has no monitored overflow upstream (#199, merged 12 Oct: the EA's
profile says the lake is not directly connected to a river), so the forecast gives it no E. coli figure and no lake
range. Consequences, stated now:

- **The 2027 reads drop Colwick.** Its 2027 samples are counted as "no logged row", not filled, as each read already
  says. This applies to the frozen-file read (`lake_line_frozen.v1.json` has 12 lake sites, Colwick among them), to
  lake-range-v1's read (its water bodies are Windermere, Coniston, Derwent Water, Rutland and Frensham; Colwick is not
  among them), and to the wording proposal (no lake range at Colwick, so no line).
- **It is not a new question for Ethan:** the pin was his decision in #199. One inconsistency is recorded rather than
  fixed: the 2024-26 study rows behind the frozen models (built 14 Sep, before #199) carry Colwick's 45 samples with
  exposure from the superseded Trent pin. Colwick had no result over 900. Its effect on the shared exposure term was not
  measured.

**Short re-check at the season's start:** in the first week of May 2027, confirm that `shadow_lake_range_v1` rows are
marked in season and still have no null inputs. A gap found then can be fixed before most of the season's samples.
