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

---

## Results

Added 25 October 2026, after the run. Everything above the line is as committed in 2c64572 (21:50 GMT) and pushed
before the run. The harness came in 10662df. It changed nothing above the line.

**Verdict: the test fails, on condition 3 only.** At lead 1, lakes are 0.00061 worse than today's model, against a
margin of 0.0005. Conditions 1, 2 and 4 hold. By the rule stated above, `sm` is not adopted, and the plan's "What would
stop it" applies. The figures are in `SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.json`.

### How it was run

- From a `git archive` of 10662df, offline, with `run.sh leads` under the group's `heavy-run.lock`. It started at
  22:01:32 GMT with 52% memory free and ended at 22:08:28. 0 network attempts in all four steps. Run times:
  `validate_ecoli` 173 s, `replay_ecoli_leads` 101 s, `train_ecoli` 97 s, `leads.py` 43 s. Peak memory 3.0 GB.
- The data are the frozen folder (overflow key b5724303) and the #344 soil cache. No new fetch.

### Checks. All hold.

- **The reference equals `train_ecoli.py`'s by-lead table** ("replayed exposure") at every lead, all and rivers:
  0.0921 / 0.1354, 0.0966 / 0.1425, 0.0985 / 0.1458, 0.1025 / 0.1524, 0.1015 / 0.1506.
- **Rows:** 1,502 (212 over 900, 31 sites). No row lacked `sm_k` at any lead, so no row fell back to the reference.
  Rows held at the edge of their fold's `sm_0` range: 18, 15, 11, 13 and 11 at leads 0 to 4.

### Held-out Brier by lead (leave one year out)

| Lead | All: today / with `sm` | Gain [95%] | Rivers: today / with `sm` | Lakes: today / with `sm` | Lakes change |
|---|---|---|---|---|---|
| 0 | 0.09215 / 0.08498 | +0.00716 [+0.00270, +0.01169] | 0.13537 / 0.12341 | 0.02625 / 0.02641 | +0.00016 |
| 1 | 0.09661 / 0.08720 | +0.00941 [+0.00472, +0.01433] | 0.14248 / 0.12649 | 0.02670 / 0.02731 | **+0.00061** |
| 2 | 0.09853 / 0.08872 | +0.00982 [+0.00485, +0.01498] | 0.14584 / 0.12946 | 0.02642 / 0.02661 | +0.00019 |
| 3 | 0.10250 / 0.09327 | +0.00923 [+0.00394, +0.01461] | 0.15240 / 0.13694 | 0.02643 / 0.02669 | +0.00026 |
| 4 | 0.10145 / 0.09375 | +0.00770 [+0.00289, +0.01270] | 0.15055 / 0.13752 | 0.02660 / 0.02703 | +0.00044 |

Lakes change is the candidate's Brier minus today's: a positive figure is worse. Bold marks the one above the margin.

The rivers gain is +0.0120 to +0.0164 at every lead. Its interval lies above zero at every lead; the lowest lower end
is +0.0046, at lead 0. The lakes gain interval at lead 1 is −0.00113 to −0.00002, wholly below zero. At the other
leads it includes zero.

AUC, all: lead 0 0.816 to 0.852, lead 1 0.805 to 0.843, lead 2 0.802 to 0.843, lead 3 0.793 to 0.833, lead 4 0.796 to
0.834.

### The conditions

1. **Lead 0, a gain:** +0.00716, at least 0.0005, and the interval lies above zero. Holds.
2. **Leads 1 to 4, not worse:** every lead is better, by +0.0077 to +0.0098. Holds.
3. **Rivers and lakes apart:** rivers are better at every lead. Lakes are worse at every lead, by 0.00016 to 0.00061.
   Lead 1 is over the margin. Fails.
4. **The sign:** `sm` is +0.892 per SD in the fit on all rows. Holds.

### Reported, not conditions

- **`sm`'s coefficient by fold:** 0.657 without 2024, 0.952 without 2025, 1.006 without 2026.
- **Lead 0, other evaluations:** leave one site out 0.09119 to 0.08664. Forward (997 rows) 0.08240 to 0.08162, a gain
  of 0.0008, against #344's 0.0028 with the input 48 hours before the sample.
- **#344's input on the same rows** (48 hours before the sample), leave one year out: 0.08508. The issue-time input
  gives 0.08498, about the same.
- **Persistence.** The correlation of `sm_k` with `sm_0` is 0.991, 0.980, 0.965 and 0.950 at leads 1 to 4. The mean
  absolute change is 0.007 to 0.020 m³/m³, against an SD of 0.10 across rows.
- **Within-site rank at lead 0:** rho rises at 17 of 25 sites, median +0.068. Rivers: 10 better, 4 worse, median
  +0.143. Lakes: 7 better, 3 worse, median +0.047.

### Against what was expected

- Conditions 1, 2 and 4: as expected, though the gain did not shrink with lead. It is largest at leads 1 to 3.
- Condition 3: expected to be the one at risk, on lakes. It failed there, at lead 1.

### What this shows

Established, on these rows:
- Issue-time soil moisture, held for four days, keeps almost all of #344's gain at every lead the site shows. All rows:
  +0.0072 to +0.0098. Rivers: +0.012 to +0.016.
- On lakes it makes the estimate a little worse at every lead. At lead 1 it is worse beyond the stated margin, with an
  interval that excludes zero.

Inferred, not tested:
- Lakes have 16 exceedances in 595 samples. A term that lifts risk on wet days adds false alarms there and finds
  little. A lake responds to the catchment's wetness over weeks, through its residence time, not to the root zone
  near the sample point.
- A rule that used `sm` on rivers only would be fitted after seeing these lake figures. It would need its own
  statement and data this test has not seen, such as the 2027 season or the Welsh river samples.

### What follows

As stated for a failure: `sm` is not adopted. This PR stays a record: the plan's step 1 and 2 results, this file,
the results and the harness. Any rivers-only variant is a new question for Ethan, needing its own statement.
