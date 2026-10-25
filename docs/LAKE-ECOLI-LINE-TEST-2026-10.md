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

Not run.
