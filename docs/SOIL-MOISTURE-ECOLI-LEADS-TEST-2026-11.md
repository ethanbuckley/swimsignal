# Soil moisture in the E. coli estimate at every lead the site shows: the test, stated before any run

Written 25 October 2026. Step 3 of `docs/SOIL-MOISTURE-ECOLI-PLAN-2026-10.md`, approved by Ethan on 25 October.
Nothing has been run. No score with the input below has been computed, at any lead. Results go below the line at the
end. Nothing above it changes after a result is seen.

## Why

#344 (`docs/SOIL-MOISTURE-TEST-2026-10.md`, Question 1) found that soil moisture improves the E. coli model:
leave-one-year-out (LOYO) Brier 0.0921 to 0.0851. Its input was `soil_moisture_9_to_27cm` 48 hours before the sample,
at lead 0. The site shows today and four days ahead. For a day two or more days ahead, the hour 48 hours before the
sample is still in the future when the forecast is made. Past soil-moisture *forecasts* are not archived (#344 found
`_previous_day1` empty). So #344 does not show what the site could use.

This test asks one question: **does soil moisture still help when the build can only know the soil moisture at the
time it issues the forecast, held for every lead?**

## The input

- **Source.** `soil_moisture_9_to_27cm` from ECMWF IFS (`models=ecmwf_ifs`, pinned in step 1 of the plan), Previous
  Runs lead 0, at the sample's 0.1° rain cell. This is the #344 cache (`data/cache/soil/q1_*`, SHA-256 of its
  listing `e5602fb6`), 1 April to 30 September of 2023–26. No new fetch.
- **Issue time.** For a sample on UTC day *d* at lead *k*, the forecast is issued at 00:00 UTC on day *d* − *k*. This is
  the live-status test's convention (`docs/LIVE-STATUS-FEATURE-TEST-2026-10.md`). The site builds later in the day, so
  this is the conservative end.
- **`sm_k`** = the cached value at that hour. The ground's wetness is held from issue time for every lead (persistence).
  - At lead 0 this is 00:00 UTC of the sample day, about 11 hours before a typical sample. It differs from #344's input
    (48 hours before the sample). It is newer, and it carries part of the 48-hour window's rain.
  - At leads 1 to 4 it is 1 to 4 days older than that.
  - The earliest hour any row needs is about 29 April (a 3 May sample at lead 4), inside the cache.
- **A limit, stated now.** At 00:00 UTC the latest ECMWF run on the API was started 6 to 12 hours earlier. So the value
  a live build reads for that hour is a short forecast, not the lead-0 value used here. Root-zone soil moisture changes
  over days, so the difference should be small. It is not measured here.

## The model and the evaluation

- **Rows.** `train_ecoli.py`'s rows: the samples with forecast rain and replayed exposure at every lead, 1,502 in the
  frozen data folder #344 used (overflow key b5724303).
- **Candidate.** Today's seven inputs plus `sm`, standardised like the others. It is fitted on lead-0 rows with `sm_0`,
  exactly as `train_ecoli.py` fits today's model on lead 0.
- **Scoring at lead *k*.** `train_ecoli.py`'s by-lead table: leave one year out, each fold fitted on lead 0 and scored
  with the lead-*k* inputs. These are lead-*k* rain, lead-*k* replayed exposure (its "replayed exposure" rows) and,
  for the candidate, `sm_k`.
- **The reference** is today's model scored the same way. Its figures must equal `train_ecoli.py`'s own by-lead table
  ("replayed exposure") in the same root, at every lead. If they do not, I stop and report before going on.
- **Range.** In each fold, `sm_k` is held inside the range of `sm_0` in the rows that fold was fitted on, at the nearer
  end. This is the live rule (plan, step 3). The share of rows held is reported per lead.
- **Missing soil moisture.** A row with no `sm_k` is scored with the reference model's prediction from the same fold.
  It is never given a guessed value. The share is reported per lead. None is expected.
- **Interval.** `train_ecoli.py`'s cluster bootstrap over (site, ISO week) blocks, with its seed, on the gain of the
  candidate over the reference at each lead.

## The test passes if all four hold

1. **Lead 0, a gain.** The LOYO Brier improves by at least 0.0005, and the 95% interval of the improvement lies above
   zero.
2. **Leads 1 to 4, not worse.** At each lead, the candidate's LOYO Brier is no worse than the reference's by more than
   0.0005.
3. **Rivers and lakes apart.** At every lead, 0 to 4, neither is worse than the reference by more than 0.0005.
4. **The sign.** In the candidate fitted on all lead-0 rows, `sm`'s coefficient is above zero.

## Reported, not conditions

- At each lead: Brier, AUC and the gain with its interval, for all, rivers and lakes.
- At lead 0: leave one site out, and forward (fitted to 2024, scored on 2025–26), as `train_ecoli.py` runs them.
- `sm`'s coefficient per SD in each LOYO fold, and in the fit on all rows.
- The correlation of `sm_k` with `sm_0` at each lead, and its mean absolute change.
- At lead 0, beside the candidate: #344's input (48 hours before the sample) scored on the same rows, as a link to
  #344's figures.
- Within-site Spearman's rho of log E. coli against the probability at lead 0, as in the plan's step 2.

## What is expected, stated now

- **Condition 1 holds.** The issue-time value is newer than #344's and still before most of the sample day. I expect a
  gain smaller than #344's +0.0071, because part of what it carries is the window's rain, which `lrain48` already has.
  I expect it well above the margin.
- **Condition 2 holds.** I expect the gain to shrink with lead and to stay above zero at lead 4. Root-zone moisture
  over four days moves much less than rain does. The step 2 diagnostics found the gain in every month.
- **Condition 3 is the one most at risk, on lakes.** #344's lakes were 0.0002 worse with `sm`, against a margin of
  0.0005. Lakes have 16 samples over 900.
- **Condition 4 holds.** `sm`'s coefficient was above zero in every fold of #344's run.

## Running

- The harness is `scripts/soil_moisture_eval/leads.py`, with a `leads` mode in `run.sh`. It is committed after this
  file and before the run. The statement above the line does not change when it is added.
- It runs from a `git archive` of the harness commit, offline (every outgoing connection refused and counted), on a
  fresh scratch root copied from the frozen data folder. The chain is #344's: `validate_ecoli.py`,
  `replay_ecoli_leads.py`, `train_ecoli.py`, then `leads.py`.
- One run, under the group's `heavy-run.lock` rules: no other evaluation, training, build or test running, and 35%
  memory free.

## What follows

**It passes.** The adoption PR of the plan's step 5 becomes possible. It is Ethan's decision, together with the Wales
check (step 4.1), which is stated separately.

**It fails.** `sm` is not adopted. The plan's "What would stop it" applies. This PR stays a record: this file, the
results and the harness.

Nothing is adopted or deployed in this PR. Changing a model input is allowed until the 2027 freeze tag
(`docs/PREREGISTRATION-2027.md`). The PR is left for Ethan to merge.

## Seen before writing

- #344's results, in full (`docs/SOIL-MOISTURE-TEST-2026-10.md`).
- The plan's step 2 diagnostics, computed today on #344's input (48 hours before the sample, lead 0 only):
  - within-site rho rose at 18 of 25 sites;
  - the gain was positive in every month, May to September;
  - `sm`'s coefficient was 0.64 to 0.94 across the three LOYO folds.
- The plan's step 1 probes: soil moisture at two cells on days outside the test window only.
- Today's by-lead table, written by `train_ecoli.py` in #344's root. LOYO Brier with replayed exposure, leads 0 to 4:
  0.0921, 0.0966, 0.0985, 0.1025, 0.1015. Rivers: 0.1354, 0.1425, 0.1458, 0.1524, 0.1506.
- No `sm_k` has been computed for any row, at any lead. No score with it exists.
