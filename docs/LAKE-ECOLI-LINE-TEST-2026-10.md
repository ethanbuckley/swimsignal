# A lower E. coli line for lakes: the test, stated before any run

Written 25 October 2026. Nothing has been run. No lake sample has been counted at any line other than 900. Results go
below the line at the end. Nothing above it changes after a result is seen.

## Why

On rivers the site shows the chance that an EA sample would be over 900 E. coli per 100 ml. Lakes get no such figure.
At 900 the model showed no ranking skill on lakes. In the published fit there were 16 samples over 900 in 595 lake
samples, 2024 to 2026: a rate of 2.7%, against 22% on rivers (`data/processed/ecoli_model.json`,
`meta.base_rate_by_type`: lake 0.0269, river 0.2161; the 595 is the lake `n` in `ecoli_model_eval.json`'s bootstrap).

On 25 October 2026 Tim Boden of Ambleside Action for a Future sent 59 weekly samples from Waterhead, Windermere
(2025–26). None was over 900. Ethan asked whether 900 is too high a line for lakes. He wants a lower line, chosen for a
health reason, tested properly.

The question: **at a lower line chosen from health guidance, does the E. coli model rank lake sample days well enough
to show a lake estimate?**

## The lines, chosen before any count

The lines were chosen from the guidance alone. No lake sample was counted at any of them before this file was pushed.

### What the guidance says

**UK: the Bathing Water Regulations 2013, Schedule 5** (SI 2013/1675), read on legislation.gov.uk on 25 October 2026.
For inland waters, E. coli per 100 ml:
- Excellent 500, Good 1,000: each "Based upon a 95-percentile evaluation".
- Sufficient 900: "Based upon a 90-percentile evaluation".

The percentile is not a share of samples. Paragraph 2 takes log10 of each count, their mean μ and standard deviation σ,
and computes the 90th percentile as antilog(μ + 1.282σ) and the 95th as antilog(μ + 1.645σ). A water is classed once,
"at the end of every bathing season", from its set of samples (paragraph 3).

SI 2025/1129 (the Bathing Water (Amendment) (England and Wales) Regulations 2025) changes only the 95th percentile's
factor. Regulation 12 replaces 1.65σ with 1.645σ. The page records it in force from 21 November 2025 for England and
1 April 2026 for Wales. The values 500, 1,000 and 900 are unchanged. The page says "There are currently no known
outstanding effects" for Schedule 5.

**US: EPA Recreational Water Quality Criteria 2012** (Office of Water 820-F-12-058). Culturable E. coli in fresh
water, cfu/100 ml:

| | Geometric mean (GM) | Statistical threshold value (STV) | Beach action value (BAV) |
|---|---|---|---|
| 36 illnesses per 1,000 bathers | 126 | 410 | 235 |
| 32 illnesses per 1,000 bathers | 100 | 320 | 190 |

- The GM and STV are the criteria (Table 1). The GM should not be exceeded in any 30-day interval. No more than 10% of
  samples in that interval should exceed the STV. The STV "approximates the 90th percentile" of the water-quality
  distribution.
- The BAV is not part of the criteria (section 5.1, Table 5). It is the estimated 75th percentile of the same
  distribution. EPA suggests it as "a conservative, precautionary tool" for beach notices: any single sample above it
  could trigger a notice until a sample below it comes back.
- The illness rate is NEEAR gastrointestinal illness (NGI), from EPA's own epidemiological studies.

**WHO: Guidelines on recreational water quality, Volume 1, 2021** (ISBN 978-92-4-003130-2). WHO sets its guideline
on intestinal enterococci only: 200 per 100 ml as a 95th percentile. It sets no E. coli value. Its reason: "No
statistical relationship has been established for Escherichia coli" that supports a dose–response value (footnote to
the guideline value; also section 2.1.2). It notes that many places use 100 E. coli per 100 ml in fresh water, from
Wiedenmann et al. (2006). That trial (Environmental Health Perspectives 114(2):228–236) found no-adverse-effect levels
of 78 to 180 E. coli per 100 ml. Its exposure was the mean of samples taken every 20 minutes while people bathed.

### How a single-sample line relates to these

The model forecasts one sample: the chance that the next routine sample is over a line. Most of the guidance above
classifies a water over many samples. They meet like this.
- **A 95th-percentile line of 500.** A lake whose fitted 95th percentile is exactly 500 has, on the log-normal model,
  a 5% chance per sample of being over 500. So the season's mean of the daily chance "over 500" is a day-by-day version
  of the Excellent test. It is not the same test. The class uses a fitted log-normal over the whole set, not the share
  of samples over. The two differ when the counts are not log-normal. (Inferred from paragraph 2, not checked on data.)
- **900, today's line.** 900 is the edge between Sufficient and Poor. A water just Sufficient has 10% of samples over
  900. So today's target is the Poor tail. That is why lakes, most of them Excellent or Good, have so few events.
- **The BAV of 235.** It is the 75th percentile of a water that just meets the GM of 126. So at such a water about one
  sample in four is over 235. A sample over 235 is a reason for a precautionary notice. It does not by itself mean the
  water fails the criteria. EPA wrote it for single samples. It is the only value here that was.

### The two candidates

1. **500 cfu/100 ml, the UK Excellent line for inland E. coli.** It is the UK's own health-based top class, in the
   EA's own unit and sampling. A forecast of "over 500" ties to the class swimmers already see.
2. **235 cfu/100 ml, the US EPA beach action value** (at 36 NGI per 1,000). It is the only candidate written as a
   single-sample action line. It is precautionary by design. Ethan's brief says Tim Boden's Waterhead report uses the
   EPA values. That was not checked here: his report holds Waterhead counts, and no lake count at a candidate line was
   to be seen before this file was pushed.

Each is scored and decided on its own.

**Not chosen, and why.**
- 410 (EPA STV): a 90th-percentile criterion. It sits between the two candidates and adds no new health basis.
- 190 (EPA BAV at 32 NGI per 1,000): the stricter EPA set. 235 matches the 126/410 set that EPA lists first.
- 1,000 (UK Good): above today's 900.
- 100 (Wiedenmann et al.): WHO does not adopt it. The trial's exposure was a mean over each bather's time in the
  water, not one routine sample.

**Units.** The EA counts E. coli by membrane filtration (determinand 2348, `ingest/wqa.py`). EPA's values assume
Method 1603, also membrane filtration of culturable E. coli. The media differ. The counts are treated as comparable.
That is assumed, not checked.

## The data

As `scripts/train_ecoli.py` uses it, with its filters:
- EA statutory samples at the inland designated bathing waters with monitored overflows upstream (`upstream > 0`),
  from `data/processed/ecoli_validation_rows.parquet`;
- rows with E. coli, 48 h and 24 h rain and exposure; then rows with archived forecast rain at every lead 0 to 4 and
  a replayed exposure shown at every lead (`MAX_MISSING_SHARE`). This drops 2023, which has no lead 1–4 rain.

In the published run that left 1,502 rows at 31 sites, 2024 to 2026. Of them, 595 are lake samples.

The rows file in the main checkout is older (written 14 September 2026). It has
641 lake rows in 2024–26, at 12 lakes: Derwent Water at Crow Park; Windermere at Lakeside YMCA, Millerground Landing,
Rayrigg Meadow and Fellfoot; Coniston Water at Brown Howe, Boating Centre and Monk Coniston; Colwick Country Park (West
Lake); Rutland Water at Whitwell Creek and Sykes Lane; Frensham Great Pond. Which of these are in the published 595 was
not checked.

The run uses the rows file rebuilt by `validate_ecoli.py` at the harness commit. It reports its own counts. If they
differ from the published 1,502 rows and 595 lake rows, the difference is reported before any score at 235 or 500.

Waterhead is not an EA bathing water. It is not in these rows. Tim Boden's 2025–26 samples are not used: they have been
seen, and they are private material. They stay out of the repo.

**The outcome.** A sample scores 1 when its count is over the line, 0 otherwise. A count exactly on the line scores 0,
as at 900. A count published as "<10" reads as 10 (`ingest/wqa._count`).

## The model

`ecoli.FEATURES` (48 h and 24 h rain, overflow exposure, lake flag, lake × 48 h rain, two season terms), fitted by
`ecoli.fit` (logistic regression on standardised inputs, C = 1). Fitted on all rows, rivers and lakes, as
`train_ecoli.py` does. Only the outcome changes: over the line instead of over 900. The lake rows' predictions are
scored.

Nothing else changes: not the inputs, the rain, the exposure, the fitting or the rows.

## The evaluations

Three, as `train_ecoli.py` runs them, with its functions:
- **Leave one site out (LOSO), the main one.** `leave_one_out` by bathing water. Each lake is predicted by a model
  that never saw it. This matches the promise of a figure at any lake.
- **Leave one year out (LOYO).** `leave_one_out` by calendar year: 2024, 2025, 2026.
- **Forward.** Fitted on 2024 with the exposure from the 2023–24 spill model (`risk_hold_lead0`), scored on 2025–26,
  as its forward block does. If that exposure is missing, the forward check cannot be made and the line cannot pass.

**Interval.** `train_ecoli.cluster_bootstrap` with whole sites as clusters (`bw_id`), on lake rows only, 2,000
resamples, its seed (1). There are about 12 lakes, so intervals will be wide. Two lines are tried, so each interval is
97.5% (the 1.25th to 98.75th percentile), not 95%. The harness also computes the model's lake AUC in the same draws.

## The references

Both are fitted in each training fold, from that fold's lake rows only.
- **R1, the lake base rate.** The share of training lake samples over the line. This is `train_ecoli.py`'s
  "climatology by type".
- **R2, a 48-hour rain rule.** Two shares from training lake samples: over the line when the lead-0 forecast rain over
  the 48 hours to the sample was 10 mm or more, and when it was less. 10 mm is `train_ecoli.HEAVY_RAIN_MM`. It is
  fixed now and not tuned. A group with no training rows takes R1.

## The test, for each line

**The gate, checked first.** These are the first counts at the line anyone sees. The line is judged only if the lake
rows hold:
- at least 30 samples over the line;
- at 5 or more lakes;
- at least 5 in each of 2024, 2025 and 2026.

Below that, the line is "too few to judge". Its scores are still reported, as description. It cannot pass. With 16
events at 900, nothing could be judged on lakes. 30 events at 5 lakes is the least that gives a site bootstrap
something to resample.

**A line passes if all seven hold.**
1. **LOSO, Brier against R1.** Skill (1 − Brier ÷ R1's Brier) is at least 0.02, and the 97.5% interval of the Brier
   gain has its lower end above zero.
2. **LOSO, Brier against R2.** The model's Brier is no worse than the rain rule's (gain at least 0). If a rain rule
   alone does as well, the model adds nothing a swimmer cannot get from the weather forecast.
3. **LOSO, ranking.** The model's lake AUC is at least 0.65, and its 97.5% interval has its lower end above 0.50.
4. **LOYO, Brier against R1.** The pooled gain is above zero, and it is above zero in at least 2 of the 3 held-out
   years.
5. **Forward, Brier against R1.** The gain on 2025–26 lake rows is above zero.
6. **Placebo.** The lake outcomes are shuffled within each lake (river rows untouched), 200 times, numpy
   `default_rng(20261025)`. LOSO is rerun on each. The real LOSO Brier gain against R1 must be above the 95th
   percentile of the 200 placebo gains (above the 190th when ranked). Shuffling within a lake keeps each lake's rate
   and breaks the link to the day. So this shows the signal is in which days, not only in which lake.
7. **Face check, a stop rule.** At 900 the harness reproduces `train_ecoli.py`'s LOYO, LOSO and forward predictions,
   from a run in the same root, to within 1e-9 on every row. 0 network attempts during the scoring. If either fails,
   I stop and report it before any score at 235 or 500 is looked at.

Why these margins. A skill under 0.02 would barely move a lake's figure (inferred, not tested). An AUC of 0.65 is a
low bar: the river model's LOSO AUC is 0.81. At 900 the lake LOSO AUC was 0.25, below chance, and LOYO 0.54.

## What follows

**Whatever the verdict, nothing on the live site changes in this PR or because of it.** Rivers stay at 900 in every
case.

**A line passes.** Ethan decides whether lakes get an estimate at that line. If he says yes, it comes in separate PRs:
- a separate model file for lakes at the line, fitted on all rows (not `ecoli_model.json`, which stays at 900);
- wording that names the line and its source, for example "the chance a sample would be over 235, the US beach action
  value";
- lake band cuts, decided then, not here.

To be in the 2027 frozen model, these must land before the freeze tag (before 1 May 2027,
`docs/PREREGISTRATION-2027.md` section 15).

**Both pass.** Both are reported. This statement prefers 235, because it is the only one written for a single sample.
Ethan picks.

**A line fails, or is too few to judge.** Lakes keep no estimate at that line. This PR stays as the record.

## The prospective part: 2027

2024 to 2026 have been seen, and Tim Boden's 2025–26 samples too. The only clean test is 2027. This part runs whatever
the retrospective verdict, if Ethan approves a shadow log.

- **Frozen.** For each line, a model fitted on all 2024–26 rows at that line, by the harness. Saved as its own file.
  Its SHA-256, and R1 for each line (the 2024–26 lake share over it), go into a dated amendment to section 17 of
  `docs/PREREGISTRATION-2027.md`, before 1 May 2027. No refit after that.
- **Issued.** A shadow log, in a separate PR merged before the freeze tag. Each build logs each lake spot's chance at
  each line, leads 0 to 4, from the inputs the live E. coli estimate uses at that build. The spots: every lake bathing
  water with overflows upstream, and Windermere Waterhead. Shadow figures are not shown on the site.
- **Scored.** EA statutory lake samples (sampling purpose MS) from 1 May to 30 September 2027. Paired as section 5 of
  the pre-registration: same bathing water, the sample's local date, the latest forecast issued strictly before the
  sample time. Same day (lead 0) decides; leads 1 to 4 are reported.
- **Tim Boden's Waterhead samples**, if he sends 2027 samples. With sample times, the same pairing. With dates only,
  the forecast issued by 08:00 local time that day. They are scored as their own group, not pooled: his lab and method
  may differ from the EA's (not checked). No sample is left out for being high.
- **Pass in 2027, per line:** at least 10 EA lake samples over the line, or it is too few to judge; Brier skill
  against the frozen R1 above zero, with the 97.5% site-bootstrap interval's lower end above zero; AUC above 0.5.
  Tim's group is description only.

Expected size: about 200 EA lake samples a year (595 in the published rows over three years). At 500, too few events
is likely.

## What is expected, stated now

I do not know how many lake samples cross 235 or 500. These are guesses.
- **235 will most likely clear the gate. 500 may not.**
- **The likeliest failures are conditions 3 and 6.** Many lake-shore exceedances come from birds, dogs, bathers or a
  nearby beck, which the model cannot see. Overflow water is diluted in a lake. At 900 the lake ranking was below
  chance.
- **If a line passes, it is most likely 235, on rain.** Tim Boden's own Waterhead model is driven by rain. Then
  condition 2 is the hard one: the model must not lose to a plain rain rule.
- My overall expectation: neither line passes.

## Running

- The harness is `scripts/lake_ecoli_line_eval/`. It is committed after this file is pushed and before any score. The
  statement above the line does not change when it is added.
- It runs from a `git archive` of the harness commit, in a scratch folder, offline (every outgoing connection refused
  and counted, `scripts/lake_distance_eval/run_offline.py`), on a frozen copy of the data folder whose hashes go in the
  results. No fetch: the lead rain is already cached.
- The order: face check at 900; then the gate counts at both lines; then the scores at both lines.
- One run, alone. It starts when `memory_pressure` reads 35% free or more and no other evaluation, training, build or
  test runs on this machine.
- It runs after Ethan has read this statement.

## What will be reported

Whatever the verdict:
- the gate counts at each line: samples over, lakes with one or more, by year;
- each condition with its figure and interval;
- LOSO, LOYO and forward tables at each line and at 900: model, R1 and R2, Brier, skill and AUC, lakes and rivers;
- LOSO lake figures by lake;
- the 200 placebo gains (lowest, median, 95th percentile, highest);
- the coefficients per standard deviation of the all-rows fit at each line;
- data hashes, run time, peak memory and network attempts.

## Seen before writing

- The published 900 figures, from `data/processed/ecoli_model.json` and `ecoli_model_eval.json` at main `389f053`:
  1,502 rows, 31 sites, years 2024–26; base rate lake 0.0269, river 0.2161; full model lake Brier LOYO 0.0262 (AUC
  0.538), LOSO 0.0269 (AUC 0.250); climatology lake LOYO 0.0264, LOSO 0.0270.
- The lake `n` (595) in that file's bootstrap entries.
- One count from the main checkout's older `ecoli_validation_rows.parquet` (14 September), with `train_ecoli.py`'s
  first filter: lake rows by year (2023: 162, 2024: 230, 2025: 227, 2026: 184), by lake, and the lake names. It also
  counted 16 lake samples over 900 in 2024–26 in that file. No other line was counted. No other E. coli value was
  looked at.
- The three sources above, opened on 25 October 2026.
- Tim Boden's data and report were not opened in writing this.
- No score of any kind has been computed for this test.

---

## Results

Added 26 October 2026, after the run. Everything above the line is as committed in ac53332 (25 October 2026) and
pushed before the run. The harness came in 5b5efc8, with one fix in 711e850 (below). Neither changed anything above
the line. The near-miss addendum after this section was committed in 629be10, before the run.

**Verdict: both lines fail. Nothing is adopted. Lakes keep no E. coli estimate.** Each line meets the gate and six of
the seven conditions. Each fails condition 3, ranking:
- 235: lake LOSO AUC 0.632, against 0.65 needed. Its interval's lower end, 0.534, is above 0.5.
- 500: lake LOSO AUC 0.535, interval 0.442 to 0.874.

This PR is a record: this file, the harness, `-score.json`, `-face.json` and the two fitted model files.

### How it was run

- From a `git archive` of 711e850, offline, with `scripts/lake_ecoli_line_eval/run.sh`. 26 October 2026, 07:34:46 to
  07:40:50 UTC, under the shared heavy-run lock, after the radar backfill (PR #362) released it. `memory_pressure`
  read 52% free. Nothing else ran.
- 0 network attempts in each of the four steps. Times: `validate_ecoli` 145 s, `replay_ecoli_leads` 68 s, face
  check 92 s, scoring 36 s. Peak memory 3.9 GB (`replay_ecoli_leads`). No Open-Meteo calls.
- Data: the die-off test's frozen folder, as the soil test used it. Its `processed` and `raw` files (river network
  excepted) hash to `dbded7ac`, the SHA-256 of their sorted `shasum -a 256` listing. The rebuilt rows file hashes to
  `63623259…`, the exposure file to `44af2a79…`.
- Main's defaults: velocity 0.2 m/s, T90 72 h, dilution power 0.5, lake path `residence_spill`.

**A first try stopped, on a harness fault.** 07:28:47 to 07:34:08 UTC, from 5b5efc8. The face check ran and passed,
with 0 network attempts in every step. Then `run.sh` stopped: its check wanted `network attempts: 0` alone on a line.
The offline wrapper printed it straight after unflushed table output, on the same line. 711e850 reads the count
wherever it lands. Nothing at 235 or 500 was counted or scored in that try. The second run repeated every step.

**Seen before the run, besides "Seen before writing":** the first try's face-check output, which holds only the
900 figures.

### Face check. Holds.

LOYO, LOSO and forward predictions at 900 equal `train_ecoli.main()`'s, row by row: largest difference 0.0, the same
rows missing (505 forward rows, the 2024 training year). LOYO Brier 0.092145, LOSO 0.091188, the same as the
`ecoli_model_eval.json` written in that root.

### The rows and what is missing

- 1,502 rows at 31 sites, 2024 to 2026: the published counts. 595 are lake samples, at 11 lakes, not the 12 in the
  older file. 16 lake samples are over 900.
- Dropped before scoring, by `train_ecoli.py`'s own filters: 182 samples with no archived forecast rain at every lead
  (all of 2023), 142 of them at lakes; 0 for missing exposure.
- No lake row lacks a LOSO or LOYO prediction. Forward scores 2025–26 only: 380 lake rows.

### The gate. Both lines are judged.

| | 235 | 500 | Needed |
|---|---|---|---|
| Lake samples over the line | 86 | 30 | 30 |
| Lakes with one or more | 11 | 6 | 5 |
| 2024 / 2025 / 2026 | 22 / 32 / 32 | 9 / 12 / 9 | 5 each |
| Lake rate (all rows) | 0.1445 | 0.0504 | |

Lake samples a year: 215, 212, 168. 500 clears the gate with exactly 30.

### Lake scores

Brier score, AUC in brackets, skill against R1 after the slash. R1 is the lake base rate, R2 the 10 mm rain rule.

| | Model | R1 | R2 |
|---|---|---|---|
| **235, LOSO** | 0.11933 (0.632) / 0.075 | 0.12901 (0.194) | 0.12349 (0.487) / 0.043 |
| 235, LOYO | 0.11781 (0.665) / 0.059 | 0.12516 (0.422) | 0.11926 (0.598) / 0.047 |
| 235, forward | 0.13434 (0.688) / 0.070 | 0.14442 | 0.13759 (0.636) / 0.047 |
| **500, LOSO** | 0.04807 (0.535) / 0.028 | 0.04945 (0.134) | 0.04933 (0.232) / 0.002 |
| 500, LOYO | 0.04651 (0.658) / 0.030 | 0.04794 (0.465) | 0.04779 (0.565) / 0.003 |
| 500, forward | 0.05096 (0.660) / 0.027 | 0.05239 | 0.05222 (0.599) / 0.003 |
| 900, LOSO | 0.02692 (0.244) / 0.002 | 0.02698 (0.080) | 0.02701 (0.140) / −0.001 |
| 900, LOYO | 0.02625 (0.537) / 0.005 | 0.02638 (0.375) | 0.02651 (0.399) / −0.005 |
| 900, forward | 0.03331 (0.594) / 0.004 | 0.03345 | 0.03376 (0.411) / −0.009 |

R1's AUC in LOSO and LOYO is below 0.5 by construction: a lake left out gets the other lakes' rate, which is lower
where its own rate is high. Forward R1 is one constant (AUC 0.5). River figures are in `-score.json`, as description.

LOSO Brier gain, lakes, site-cluster bootstrap (11 lakes, 2,000 draws, seed 1; the replayed draws equal
`cluster_bootstrap`'s 95% output exactly):

| | Gain | 97.5% interval | 95% interval |
|---|---|---|---|
| 235, over R1 | +0.00968 | +0.00245 to +0.01863 | +0.00311 to +0.01731 |
| 235, over R2 | +0.00416 | −0.00132 to +0.00923 | −0.00072 to +0.00866 |
| 500, over R1 | +0.00137 | +0.00007 to +0.00308 | +0.00019 to +0.00287 |
| 500, over R2 | +0.00125 | −0.00017 to +0.00288 | +0.00001 to +0.00272 |

Model lake AUC, LOSO, 97.5% interval in the same draws: 235: 0.534 to 0.769. 500: 0.442 to 0.874. No draw lacked an
event.

LOYO gain over R1 on lakes, by held-out year:

| | 2024 | 2025 | 2026 | Pooled |
|---|---|---|---|---|
| 235 | +0.00405 | +0.00506 | +0.01447 | +0.00735 |
| 500 | +0.00159 | +0.00056 | +0.00230 | +0.00143 |

Placebo, 200 within-lake shuffles, LOSO gain over R1:

| | Real | Lowest | Median | 95th percentile | Highest | At or above real |
|---|---|---|---|---|---|---|
| 235 | 0.009678 | −0.000699 | 0.004150 | 0.007013 | 0.009678 | 1 of 200 |
| 500 | 0.001372 | −0.000683 | 0.000629 | 0.001357 | 0.001761 | 10 of 200 |

At 235 the highest placebo is 0.0096779, just above the real 0.0096777. They are not the same value.

### The conditions

| | 235 | 500 |
|---|---|---|
| 1. LOSO skill ≥ 0.02, gain interval above 0 | 0.075, +0.00245. **Holds** | 0.028, +0.00007. **Holds** |
| 2. LOSO no worse than R2 | +0.00416. **Holds** | +0.00125. **Holds** |
| 3. LOSO AUC ≥ 0.65, interval above 0.5 | 0.632, 0.534. **Fails** | 0.535, 0.442. **Fails** |
| 4. LOYO gain > 0, and in 2 of 3 years | +0.00735, 3 of 3. **Holds** | +0.00143, 3 of 3. **Holds** |
| 5. Forward gain > 0 | +0.01008. **Holds** | +0.00143. **Holds** |
| 6. Placebo above its 95th percentile | 0.009678 > 0.007013. **Holds** | 0.001372 > 0.001357. **Holds**, by 0.000015 |
| 7. Face check | **Holds** | **Holds** |

### LOSO by lake

At 235, Brier for model / R1 / R2:

| Lake | Samples | Over 235 | Model | R1 | R2 |
|---|---|---|---|---|---|
| Derwent Water at Crow Park | 58 | 32 | 0.4168 | 0.4509 | 0.4317 |
| Coniston Water, Boating Centre | 57 | 15 | 0.1837 | 0.2111 | 0.1954 |
| Coniston Water, Brown Howe | 57 | 12 | 0.1538 | 0.1715 | 0.1470 |
| Coniston Water, Monk Coniston | 57 | 8 | 0.1232 | 0.1207 | 0.1125 |
| Windermere, Fellfoot | 59 | 8 | 0.1169 | 0.1173 | 0.1243 |
| Windermere, Lakeside YMCA | 57 | 3 | 0.0601 | 0.0602 | 0.0736 |
| Rutland Water Whitwell Creek | 52 | 3 | 0.0584 | 0.0634 | 0.0624 |
| Rutland Water Sykes Lane | 48 | 2 | 0.0437 | 0.0525 | 0.0419 |
| Windermere, Millerground Landing | 59 | 1 | 0.0359 | 0.0367 | 0.0392 |
| Windermere, Rayrigg Meadow | 57 | 1 | 0.0318 | 0.0370 | 0.0387 |
| Frensham Great Pond | 34 | 1 | 0.0346 | 0.0435 | 0.0354 |

At 500, Derwent Water holds 17 of the 30 samples over the line. The table for 500 is in `-score.json`.

Coefficients per SD, all-rows fit: 235: `logit_risk` +0.996, `lrain48` +0.217, `lake_x_lrain48` −0.362, `lake`
−0.726. 500: +1.033, +0.473, −0.811, −0.341. The rest are in `-score.json`.

### What this means

Checked:
- At both lines, the model's lake figures beat the lake base rate on Brier score in every evaluation. At 235 the gain
  is larger than all but one of 200 placebos.
- Neither line ranks lake days well enough by the stated bar. 235 misses on the point AUC (0.632 against 0.65). 500
  misses on both parts.
- Derwent Water holds 32 of the 86 lake samples over 235 and 17 of the 30 over 500. It gives the largest single Brier
  gain at 235.

Inferred, not tested:
- Much of the Brier gain may come from telling lakes apart (Derwent Water's rate against Windermere's), not from
  telling days apart. The placebo keeps each lake's rate, and at 235 the real gain still beats it. So some of the
  signal is in the days. How much was not split out.
- With 1 to 3 samples over 235 at most Windermere sites, the test cannot say whether the model ranks days there.
  Waterhead's own record would bear on that, prospectively.

### What follows

As stated above the line: nothing changes on the site. Lakes keep no E. coli estimate. Rivers stay at 900. The live
model, `ecoli_model.json`, is untouched.

The prospective 2027 part was stated to run whatever this verdict, if Ethan approves a shadow log. The two fitted
files are kept for that. They are not used by anything:
- `LAKE-ECOLI-LINE-TEST-2026-10-model-235.json`: SHA-256 `46d675e6459d4da5d432591448382ee5b82a6633379056a5d1254faeb4fc0c45`;
- `LAKE-ECOLI-LINE-TEST-2026-10-model-500.json`: SHA-256 `4398e1d3f52267d4d3394826eb2a8a1fa53af9dcbe7ba360313a54e105986170`.

Whether to run that shadow, and the section 17 amendment it needs, are Ethan's decisions.

## Addendum, 26 October 2026: a framework for near misses in later tests

Written before this test's run, at Ethan's request, and before any score at 235 or 500 was seen. It changes nothing
above the line. It does not apply to this test, and it does not reopen any past verdict. A past near miss can only be
tested again under a new statement, on new data.

**The problem.** Several tests have ended with a gain whose interval narrowly crosses zero. The rule "lower end above
zero" then gives "fails", which reads the same as "made things worse". The labels below keep these cases apart. Every
label is fixed before the data, and none of them adopts anything.

### Labels

Each statement names one primary comparison, an interval level, a benefit margin B and a harm margin H, both in the
primary score's units. Then, from the interval (L, U) and the point estimate d of the gain:
- **Better:** d ≥ B and L > 0.
- **Promising, not shown:** d > 0, L ≤ 0 and L > −H, and no secondary check is labelled harm. Not adopted. It may go to
  the forward step below.
- **No useful difference:** −H < L and U < B.
- **Possible harm:** L ≤ −H and d ≤ 0.
- **Harm:** U < 0.
- **Too uncertain:** L ≤ −H and U ≥ B. The data cannot tell.

The first label that fits, in this order, is the result.

**Note, 26 October 2026 (Ethan's decision).** In this order "Harm" can never be the label: an interval wholly below
zero is labelled "No useful difference" (L > −H) or "Possible harm" (L ≤ −H) first. So wherever a statement says "no
secondary check is labelled harm", later tests read it as "labelled Possible harm or Harm". Found while writing the
river-rises harness (PR #383). It changes no past verdict.

### Margins, set before the data

- **B, the benefit margin,** is the smallest gain that changes what a swimmer sees. It is worked out from predictions
  alone, never from outcomes: for example, the change in the primary score when a stated share of forecasts move across
  a band cut (`ECOLI_CUTS`, `SPILL_CUTS`). The statement shows the working.
- **H, the harm margin,** is the largest loss accepted as noise. It is no larger than B.
- Both are written down before any outcome of the test is read. Neither may be taken from an earlier test's result on
  the same data.

### The forward step for "promising, not shown"

- The candidate is frozen (file hash), runs in shadow and is logged but not shown, for a window stated in advance.
- Only samples or spill days after the shadow starts count. They are not pooled with the data that found the gain.
- The forward test uses the same B and H. It needs "better" to support adoption.
- A second "promising, not shown" is not stacked onto the first to make a pass.

### What else must hold before Ethan is asked to adopt

Each with its own margin, stated in advance:
- **Coverage:** the share of spot-days or samples with a figure is not lower than the live model's by more than a
  stated amount. A missing input has a tested fallback.
- **Calibration:** the mean forecast matches the observed rate within a stated amount, and the reliability by band is
  no worse than the live model's.
- **False alarms and misses** at the site's warning lines (0.25 for E. coli, 0.40 for spills): the miss rate and the
  false-alarm rate are each no worse than the live model's by more than a stated amount. Both are reported.
- **Groups:** no group listed in advance (company, river or lake, lead) is labelled harm.
- **Resources:** Open-Meteo calls within the daily ledger with headroom, build time, data licence, and upkeep.

### Sample size, set in advance

- Power is computed before the forward window starts, at a stated level (80% or 90%) for a gain of B.
- The spread of the per-cluster gain comes from an earlier, finished test on other data, or from a simulation. Never
  from the data being judged.
- Clustering is allowed for: clusters (sites, weeks), not rows, are the unit. Number of clusters ≈
  ((z for the interval + z for the power) × spread ÷ B)².
- A minimum number of events is stated, as in this test's gate.
- If the window cannot reach that power, the statement says so in advance, and the result is description only.
