# PLACE-LEVEL read 0: statement, written before it is scored

Written 17 November 2026 for [#716](https://github.com/ethanbuckley/swimsignal/issues/716), after the
[river level candidate](RIVER-LEVEL-CANDIDATE-2026-11.md) and its
[bathing-water backtest](RIVER-LEVEL-BATHING-BACKTEST-2026-11.md), and before any range in this read has been
computed. **Nothing below the line "Result" existed when this was pushed.** The script was written after it and tested on
made-up rows only before the one run.

Nothing on the site changes. No forecast, frozen file, active window or the 2027 primary evaluation is touched. The
bench's held-out rows are not opened.

## The question

If someone takes n lab samples at a river place that has none, how large must n be before the place's range is
better than the range a place with no samples gets, on the samples that follow?

The candidate's run already showed two things at these points. A range with no samples holds (L1, 79.2% inside) but
is wide, a factor of 5.3 each way. A range with ten or more earlier samples holds too (L2, 75.7%) at a factor of
3.9. So "does the range hold" is not the question: it holds at n = 0. The question is how few samples buy the
narrower, better-centred range, and whether a level set from a handful of samples still holds months later.

## Why it matters

Stream size and overflow count do not give a place's level (0.18 across points). Only samples at the place do. If a
small number is enough, a group that samples anyway could earn its spot a reading with a range in one season. If it
takes many, or the level drifts, that plan does not work and the record should say so before anyone is asked to
sample.

## Evidence class

**Development.** Every row here was read on 16 November 2026. The form, its spreads and both earlier results came
from these rows. A pass supports a field pilot and a prospective check. No range is shown anywhere on this
evidence.

## What is used, unchanged

- The form `river-level-v1` and its fitting code, `scripts/river_unseen/level_candidate.py` (`fit`, `fixed`,
  `ranges`). No new form, input or spread is fitted or chosen.
- For the archive points: the same leave-one-river-system-out fits as the candidate's run, each on the other
  systems' seasons to 2016. The script checks that their tau and sigma match `docs/river-level/result.json` before
  it scores anything.
- For bathing-water rivers: the frozen `docs/river-level/river_level_v1.json` (`d7c34055…`) and
  `docs/river-level/bathing_sites.csv`.

## Rows

**Set A, which decides.** `heldout_rows_era5land.parquet` (`382a335e…`), seasons 2017 to 2022. A point is kept if it
has 30 or more samples in those seasons. Counted from the point, system and season columns only: **32 points in 25
river systems**. At each point the samples are put in time order. The first 20 are the place's "own samples". The
rest are scored: **1,673 samples**.

The fit for a point never saw its river system, and the point's own samples to 2016 are not used at all. So each
point stands in for a place where sampling starts in 2017.

**Set B, reported.** `seen_river_rows_era5land.parquet` (`7fac233d…`), 2023 to 2026. A site is kept on the same
rule: **14 bathing-water rivers, 548 scored samples**.

**Not in this read: Wessex Water's three river points.** Issue #716 listed them. Their 594 samples have no built
input rows (ERA5-Land rain, exposure, channel length). Building them needs a rain fetch, which is its own step with
its own statement.

## The levels compared

For n = 3, 5, 8, 12 and 20: the place's level is the mean residual of the **last n of its 20 own samples**, shrunk
by tau² / (tau² + sigma² / n), as in L2. The half-width is 1.2816 x sqrt(tau² sigma² / (n tau² + sigma²) + sigma²).

For n = 0: no level, half-width 1.2816 x sqrt(tau² + sigma²). This is L1.

Every n is scored on the same samples, and the newest sample used is the same for every n. So the comparison is of
n alone, not of how old the samples are.

What the formula says to expect if a level does not drift, from the fitted spreads (tau about 0.33, sigma about
0.45): half-width 0.72 log10 at n = 0, 0.62 at n = 5, 0.60 at n = 12, 0.59 at n = 20. Most of any gain should come
from the centre moving to the place's level, not from the range narrowing.

## Pass rule, fixed now

On Set A's 1,673 pooled samples, n passes when both hold:

1. between 72% and 88% of samples are inside the 8-in-10 range, with no more than 18% above it and no more than
   18% below it (the read's band and lab-limit rule);
2. the mean gain in log predictive density over n = 0 on the same samples has a 95% interval wholly above zero.
   The interval is from 2,000 resamples of river-system seasons, seed 20261115.

**The answer is the smallest n that passes.** If none of 3, 5, 8, 12 or 20 passes, the answer is "not shown by 20".

## Reported, deciding nothing

- For each n: the share inside with its interval, both tails, the median half-width, the density gain with its
  interval, and the correlation across points between the stated level and the measured one.
- The share inside by how long after the 20th sample a scored sample was taken: the same season, the next season,
  two or more seasons later. This is the drift check. The candidate's L2 missed more often below than above.
- The first n of the 20 in place of the last n, which adds an older level to a small n.
- A running level from every earlier sample from 2017, as a group that keeps sampling would have.
- By stream size band.
- Set B on the same rule, with `river-range-v0e` beside it. That range was fitted on Set B's rows and has the
  advantage.

## What each outcome leads to

- **Some n of 12 or fewer passes.** A draft ask to one group that samples a river anyway, for Ethan: that many
  samples, then 20 forecast-called pairs. A Lab page replaying one place's samples in date order, once the Wessex
  rows are built. That n becomes the least a place needs before a range is considered for it.
- **Only n = 20 passes.** The same, with the cost stated: 20 lab samples at about £30 each before a place has a
  range.
- **Rule 1 holds and rule 2 does not, at every n.** Samples at a place do not beat the no-sample range in the
  months that follow. A sampling network would still test the forecast's order. It would not earn a place a
  reading. The drift table says whether a shifting level is why.
- **Rule 1 fails at every n.** A level from a place's own recent samples misleads. The record says which tail and
  which gap. No further form is tried on these rows. The next candidate is the upgrade audit (RESTORE at Ilkley).

## Limits known now

- 48 of the 59 archive points are in the South West, and they run dirtier than bathing waters.
- All rows have been read. The form was written after seeing them.
- A lead 0 hindcast on ERA5-Land rain. No issued forecast is scored.
- The 20 own samples were taken on the Environment Agency's planned days, not on days a forecast picked. This
  read cannot say whether forecast-called days set a level faster.
- Set B has 14 sites, all on large rivers, where the candidate was weakest.
- Run once. A second run needs an amendment here first.

## Disclosure

Before this statement was written, the `bw_id`, `system` and `season` columns of both files were read to count
points and samples. No result column was read. Both files had the same SHA-256 before and after.

## Result, 17 November 2026: n = 5 at the archive points (development)

Run once, finishing at 22:43 UTC, at commit `276909e8`, the commit that carries the script. Logged in
`docs/place-level/runs.jsonl`; every figure is in `docs/place-level/result.json`. The three inputs had the same
SHA-256 before and after (`382a335e…`, `7fac233d…`, `d7c34055…`). The folds' tau and sigma matched the candidate's
record, and the counts matched this statement, before anything was scored. The run took 17 minutes of processor time
and 3 hours 13 minutes on the clock, on a busy machine.

### Set A, which decides: 32 archive points, 1,673 scored samples

| Level from | Inside | Interval | Above | Below | Half-width | Density gain over n = 0 | Rule 1 | Rule 2 |
|---|---|---|---|---|---|---|---|---|
| no samples (n = 0) | 79.7% | 76.4% to 83.0% | 13.3% | 7.0% | 0.72 | | | |
| last 3 | 77.6% | 74.2% to 81.1% | 14.5% | 8.0% | 0.64 | +0.054 (−0.004 to +0.112) | pass | fail |
| last 5 | 77.3% | 73.7% to 80.8% | 14.4% | 8.3% | 0.63 | +0.076 (+0.005 to +0.149) | pass | pass |
| last 8 | 76.9% | 73.3% to 80.8% | 13.8% | 9.3% | 0.62 | +0.084 (+0.003 to +0.171) | pass | pass |
| last 12 | 76.5% | 72.7% to 80.4% | 13.0% | 10.5% | 0.61 | +0.092 (+0.009 to +0.186) | pass | pass |
| last 20 | 76.9% | 73.2% to 80.7% | 11.9% | 11.2% | 0.60 | +0.111 (+0.025 to +0.205) | pass | pass |

**By the rule, the answer is n = 5.** It passes narrowly: the lower end of its gain is +0.005, and n = 3 misses by
0.004.

Reported, deciding nothing:

- **The stated level tracks the measured one better with more samples.** Across points the correlation is 0.17 with
  no samples, 0.55 with 3, 0.70 with 5 and 0.84 with 20.
- **Older samples are worth less.** With the first n in place of the last n, 3 and 5 do not pass rule 2 (+0.019 and
  +0.040, both intervals through zero). 8 does (+0.096, +0.026 to +0.172).
- **A running level does best.** With every earlier sample from 2017: 78.0% inside, gain +0.152 (+0.076 to +0.245).
- **No sign of drift breaking the range.** With the last 5, 73.3% inside in the same season (157 samples), 76.4% in
  the next (568) and 78.5% two or more seasons later (948).
- **Large streams stay weak.** 61.2% inside on 178 samples with the last 5, against 80.8% at medium streams (996)
  and 76.0% at small ones (499). A place's own samples do not fix that.

### Set B, reported: 14 bathing-water rivers, 548 scored samples

On the same rule the answer here is **not shown by 20**.

| Level from | Inside | Above | Below | Density gain over n = 0 |
|---|---|---|---|---|
| no samples (n = 0) | 89.1% | 4.2% | 6.8% | |
| last 3 | 85.2% | 4.7% | 10.0% | +0.053 (0.000 to +0.110) |
| last 5 | 83.6% | 4.2% | 12.2% | +0.040 (−0.025 to +0.107) |
| last 12 | 80.8% | 6.4% | 12.8% | +0.012 (−0.083 to +0.099) |
| last 20 | 78.5% | 4.9% | 16.6% | −0.038 (−0.169 to +0.069) |
| running | 82.5% | 5.5% | 12.0% | +0.073 (+0.003 to +0.143) |
| `river-range-v0e`, in sample | 83.0% | 7.3% | 9.7% | |

- Every range holds, and no fixed batch of own samples beats the no-sample range. The gain falls as n grows.
- The misses are below the range (16.6% with the last 20). That fits levels falling after the batch was taken.
  Almost every scored sample here is from a later season than the batch (4 of 548 are from the same season).
- The first n do worse than no samples: with the first 5, 21.9% fall below and the gain is −0.156 (−0.275 to
  −0.052).
- Only the running level is ahead, and narrowly.
- The no-sample range is too wide here (89.1% inside, over the 88% end of the band). The line was fitted on dirtier
  points.

### What is supported, as development evidence

- At river points like the archive's, five recent lab samples give a place a better range than none, and the gain
  grows with more.
- A level should be kept up to date. Recent samples beat old ones at the archive points. At bathing-water rivers a
  batch from an earlier season did not help, and a level that kept updating did.

### What is not supported

- That a one-off batch of samples earns a bathing-water river a lasting reading. Set B says it does not.
- Anything at large rivers. They were weakest in both sets, and every Set B site is one.
- Anything confirmed. Every row had been read, and the pass at n = 5 is narrow.
- That forecast-called sampling days set a level faster. These samples were taken on planned days.

### What this leads to

By the statement, a pass at 12 or fewer leads to a draft ask to one sampling group, for Ethan, and a replay page once
the Wessex rows are built. Set B changes the ask's shape: a group is asked to keep sampling through a season, with
the level updated at each sample, and not for one batch of five. The first place should be a small or medium river.

Nothing shows on the site. No further form is fitted on these rows.
