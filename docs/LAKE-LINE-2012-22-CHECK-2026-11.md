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
