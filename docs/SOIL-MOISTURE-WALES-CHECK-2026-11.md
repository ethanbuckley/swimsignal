# Soil moisture in the E. coli estimate, checked on Welsh river samples: stated before any run

Written 25 October 2026. Step 4.1 of `docs/SOIL-MOISTURE-ECOLI-PLAN-2026-10.md`, approved by Ethan on 25 October.
This is a check, not a test of adoption. It refits nothing on Welsh data. No soil moisture for a Welsh sample has been
fetched, and no score has been computed. It was written before the result of the leads test
(`docs/SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.md`) was known. Results go below the line at the end. Nothing above it
changes after a result is seen.

## Why

Every soil-moisture figure so far is on the EA's English inland bathing waters, the rows the E. coli model is fitted
on. Wales is the one place with river E. coli samples the model has never seen. The W10 check (`scripts/check_ecoli_wales.py`,
10 October) found "NO SKILL SHOWN" there. Its 185 river samples at 11 stations have 11 exceedances. The estimate's mean
was 0.32 against an exceedance rate of 0.06. So the model is already too high in Wales. Welsh catchments are wetter
and more upland than most English ones. Soil moisture could make that worse or better. The question is whether it
helps or hurts where the model is already weak.

## The two estimates compared

Both are fitted on the same English rows, the leads test's 1,502, at lead 0. Neither is fitted on Welsh data.
- **Reference:** today's seven inputs. Its coefficients must equal `ecoli_model.json` written by `train_ecoli.py` in
  the same root, to 1e-9. Its Welsh predictions must equal the check's own `ecoli_estimate` column, to 1e-9.
- **Candidate:** the same plus `sm`. This is the leads test's lead-0 candidate: ECMWF IFS `soil_moisture_9_to_27cm` at
  00:00 UTC of the sample day, fitted on all English rows.

In Wales both are fed W10's inputs, unchanged: ERA5-Land rain over 48 and 24 hours to midday, the overflow exposure from
W10's trace and Gate A's spill model, lake = 0 and the sample day. The candidate also gets `sm` at the station's 0.1°
cell, at 00:00 UTC of the sample's local calendar day. It is held inside the range of `sm` in the English rows. A sample
with no `sm` takes the reference's figure, and the count is reported.

This differs from W10 in one way. The data folder is the frozen one the soil tests use (overflow key b5724303), not the
main checkout of 10 October. So the trace may differ a little from W10's, and the row counts are reported beside
W10's: 213 inland and 185 headline.

## The soil moisture for Wales

- **Source:** Previous Runs API, lead 0, `models=ecmwf_ifs` named explicitly. Step 1 found it equal to the default
  the English cache holds.
- **Where and when:** the stations that pass W10's rules 1 to 3, 18 of them in 9 cells. Only the calendar quarters
  that hold a sample: 26 cell-quarters, in 2023 to 2026.
- **Cost:** one request per quarter per group of up to 4 cells. One variable over at most 92 days weighs 1 a location:
  about 26 calls.

## What is reported

On W10's headline set (river points) and on all inland points, for each estimate:
- Brier score and AUC over 900;
- Spearman's rho with log E. coli, pooled and within station.

The candidate minus the reference gets a 95% interval from W10's bootstrap over sampling days (2,000 draws, seed 0).
Also per station with at least 14 samples: rho of each estimate with log E. coli, and the mean of each estimate.

## The one reading, stated now

**Clearly worse in Wales**, on the headline set, is either of these:
- the interval of Brier(candidate) − Brier(reference) lies wholly above zero;
- the interval of the within-station rho change lies wholly below zero.

If either holds, the plan's rule applies: the soil-moisture term does not appear on Welsh spots until it is
understood. It does not block England. Otherwise the result is "not clearly worse". With 11 exceedances, nothing
here can show the candidate is *better*, and no such claim will be made.

## What is expected, stated now

- **Brier worse.** Welsh soils at 9 to 27 cm are likely wetter than most English sites. A positive `sm` coefficient
  would then raise an estimate that is already too high. The interval may lie wholly above zero.
- **Ranks about the same.** Within station, day-to-day wetness may help ranking as it did in England (plan step 2:
  within-site rho up at 18 of 25 English sites). But with 185 samples the interval will be wide.

## Running

- The harness is `scripts/soil_moisture_eval/wales.py` and a `wales` mode in `run.sh`. It is committed after this file
  and before the fetch.
- The fetch runs once, from the harness commit, before any score.
- The run is from a `git archive` of the harness commit, offline, under the group's `heavy-run.lock` rules. The root is
  the frozen folder, as for the leads test, plus `wales_annual.parquet` and NRW's archive files from the main
  checkout. It runs `validate_ecoli.py`, `replay_ecoli_leads.py`, `train_ecoli.py`, then `wales.py`. Welsh rain is
  read in place from the main checkout's `rain` and `rain_w10` caches. English rain comes from the frozen folder's
  cache.

## Seen before writing

- W10's published summary (`data/processed/wales_ecoli_check.json`, 10 October).
- The station screen's counts for this check: 1,597 E. coli rows, 216 after rules 1 to 3, at 18 stations in 9 cells.
  By month: May 29, June 57, July 53, August 38, September 36, November 3. By year: 2023 30, 2024 22, 2025 142,
  2026 22. No E. coli value was looked at against any input.
- #344's results, the plan's step 1 and step 2 figures, and the leads test's statement. Not its result.

---

## Results

Added 25 October 2026, after the run. Everything above the line is as committed in 4ed72f3 and pushed before the
fetch. The harness came in 27720c9. It changed nothing above the line. The figures are in
`SOIL-MOISTURE-WALES-CHECK-2026-11.json`: scores and station summaries only, with no sample rows and no Dŵr Cymru rows.

**Reading: not clearly worse.** On the headline set, the candidate's Brier is *lower* than the reference's:
0.1039 against 0.1468. Neither rule for "clearly worse" holds.

### How it was run

- **The fetch.** 25 October, 21:58 GMT, from 27720c9. 11 requests, 26 calls, every hour present.
- **A first run, stopped before it scored.** It ran under the lock from 22:18 GMT. It was stopped at 22:24 because the
  rivers-only test (`docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md`) needed these rows unseen. It wrote no score.
- **The run that counts.** It ran as the `wales` step of that test's run, from a `git archive` of 7ab958e, with
  `wales.py` unchanged since 27720c9. Offline, 22:42 to 22:49 GMT, under the lock, 0 network attempts. `wales.py` took
  31 s.

### Checks. All hold.

- The reference's coefficients equal `ecoli_model.json` written in the same root: largest difference 0.0.
- Its Welsh predictions equal the check's own estimate: largest difference 0.0.
- **Rows:** 213 inland and 185 headline, the same counts as W10. 3 samples off the network. No row lacked rain,
  exposure or `sm`. No `sm` was held to the English range (0.052 to 0.494 m³/m³).
- 10 of the rain cell-spans are under 99% covered, by W10's rule. It counts the warm-up days. Every sample's 48-hour
  window and exposure was still complete, so no row was dropped.

### The headline set: 185 river samples, 11 stations, 11 over 900

| | Reference | Candidate | Candidate minus reference [95%] |
|---|---|---|---|
| Mean estimate | 0.334 | 0.225 | |
| Brier | 0.1468 | 0.1039 | −0.0429 [−0.0678, −0.0150] |
| AUC over 900 | 0.739 | 0.688 | −0.051 [−0.111, −0.001] |
| Spearman, pooled | 0.504 | 0.532 | +0.028 [−0.036, +0.095] |
| Spearman, within station | 0.513 | 0.494 | −0.019 [−0.110, +0.063] |

All inland points (213, 34 over 900): Brier 0.2165 against 0.1542, a difference of −0.062 [−0.091, −0.032]. AUC goes
from 0.320 to 0.622. Within-station rho changes by −0.051 [−0.154, +0.045].

**Welsh `sm`:** mean 0.210, range 0.141 to 0.407. The English rows' mean is 0.272.

**Per station** (11 with 14 or more samples): the candidate's mean estimate is lower at 10 of them. Rho rises at 4 and
falls at 7.

### Against what was expected

- **Brier worse: wrong.** I expected Welsh soils at 9 to 27 cm to be wetter than the English sites. They were drier:
  a mean of 0.21 against 0.27. So the candidate *lowered* an estimate that was too high, and Brier fell.
- **Ranks about the same: right within station** (−0.019, with an interval spanning zero). AUC fell by 0.051, and its
  interval just excludes zero.

### What this shows

On these 185 samples, adding soil moisture moves the estimate's level toward the observed rate. It does not improve
how it ranks days within a station. With 11 exceedances, nothing here says the candidate is better in Wales. By the
stated reading, it is not clearly worse.
