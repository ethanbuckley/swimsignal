# Two simple rules beside the live forecast, November 2026

The Accuracy page scores the live spill forecast against one reference: each overflow's long-run rate. The interim
usefulness read ([INTERIM-USEFULNESS-2026-10.md](INTERIM-USEFULNESS-2026-10.md), 24 October) scored two simpler rules
once, by hand, and found the forecast's margin over them small, with same-day persistence ahead of it. The strategy
review of 6 November (step 5 of its 90-day list) asks for those rules on the page, on every build, with intervals.
This record states the rules, how each gets a chance, the rows, the score and the interval, and what the page says.

It is a running description of the live record. It changes no forecast, threshold, alert, active window or the 2027
primary evaluation. The 2027 use of the same rules is filed separately, as
[amendment 4](PREREGISTRATION-2027-AMENDMENT-4.md).

## Stated before any score

Written on 10 November 2026 on branch `claude/priceless-grothendieck-ac0416`, from main at `d644dc90`, and pushed
before the code that scores the rules existed. Nothing in this section changes after a score is seen, except a plain
bug fix, which would be listed under "Changes after this statement" with what it changed.

### What has been seen already

- The interim read scored both rules on target days 29 September to 23 October 2026, with each rule's chances fitted
  on the rows it scored. So those dates are not fresh for either rule. Its rain thresholds (10 mm and 5 mm) and the
  48-hour window were set before its run, from `model.verify.rain_rule` and `config.RECENT_SPILL_HOURS`.
- Later checks on the live record (the calibration check, `scripts/persistence_like_for_like.py`, the live-status
  2026 backtest) looked at persistence-like rules on overlapping dates.
- New here, and never computed before this statement: the trailing fit of each rule's chances (below), and any score
  after 23 October.

So the page's figures are a description of the record, not a confirmatory test. The clean prospective use is the 2027
season, under amendment 4.

### The rows

The Accuracy page's own scored rows, as `forecast_log.verify_live` selects them on each build: one row per monitored
overflow, target day and lead 0 to 4, the latest forecast issued by 08:00 on the issue day, with rain data, on an
overflow-day that passes the coverage rule. The forecast is the published one (`forecast_calibrated`, `p_cal`). The
outcome is the page's (1 a recorded spill that day, 0 none). Target days run from 29 September 2026 to the day
before the build.

### Rule P: same-day persistence

"Tomorrow is like now." For a row issued at time T, the overflow is **active** if its poll record shows it spilling
at T, or at any moment in the 48 hours (`config.RECENT_SPILL_HOURS`) before T. This is what the site's map calls
spilling now or spilled recently. The rebuild is the interim read's (`scripts/interim_usefulness.py`,
`persistence_status`, with its post-statement bug fix), moved into the package unchanged in meaning:

- spill intervals from `live_history.parquet` by `model.live_status.poll_events`, overlapping ones merged;
- only spill that had started by the overflow's last current reading at or before T counts;
- a current reading is a poll in `poll_log.parquet` whose half-hour slot in `live_coverage.parquet` shows a current
  reading of that overflow;
- the status is **known** when those readings cover the 48 hours before T with no stretch over 8 hours
  (`forecast_log.MAX_GAP_H`), the stretch from the last reading to T included. A row whose status is not known has no
  P chance.

Known weakness, kept: the rebuild reads event times the feeds published after T and dated back. The interim read
measured this on its cross-check: 50 of 812 active rows were spilling at issue in the rebuild but not in the shadow's
log. This flatters P a little, which makes the page harder on the forecast, not easier.

### Rule R: the rain rule

"Spill if the forecast says it will be wet." The 48-hour rain is the logged `rain_mm` at the overflow's rain cell for
the target day plus the logged `rain_mm` for the day before. For leads 1 to 4 the day before comes from the same issue.
For lead 0 it comes from the latest logged forecast of that overflow for the day before, issued before T. A row
missing either day has no R chance. The row is **wet** when the 48-hour rain is **over 10 mm** (strictly greater), the
threshold of `model.verify.rain_rule`, used in the 2025 holdout and stated in the interim read before its run.

10 mm is the only threshold shown. The interim read also reported 5 mm; it is not carried here, so the page cannot
pick the better of two after seeing them.

### Each rule's chances: fitted only on what was known at issue

A rule says yes or no. To score it like a forecast, each side gets a chance. For a row with issue day I and lead L, a
side's chance is

> (spills + 0.5) ÷ (rows + 1)

over the **fitting rows**: scored rows of the same lead L, on the same side of the same rule, all companies pooled,
on which that rule can be applied (status known for P; both days' rain for R), with target day from I − 28 to I − 1. The page's outcome for target day I − 1 is
known to the 08:00 build of day I. Nothing from day I or later enters. If the side has fewer than 100 fitting rows,
the row has no chance from that rule.

Why this form: a chance fitted on the rows it scores (the interim read's) uses hindsight and flatters the rule; a
chance frozen once would go stale as the seasons change. The trailing four weeks keep each rule a forecast someone
could have issued that morning, and adapt to the season. The half-spill and one-row terms keep a side with no spill
yet off exactly 0. The 28 days, the 0.5 and 1, and the 100-row floor are chosen here, before any score.

### Common rows

Rows with both a P and an R chance. Every comparison with P or R uses only these rows. The page shows how many of the
scored rows they are, overall and by company. The skill against the long-run rate is also given on these rows, so the
three can be read side by side.

### The score

Brier skill of the forecast against a reference, on the same rows: 1 − Brier(forecast) ÷ Brier(reference). 0 is no
better than the reference; above 0, better; below 0, worse. The page shows each reference's own Brier score too.

Cells: all companies at lead 0 (same day); all companies at leads 1 to 4 pooled (in advance); and each company, at lead
0 and at leads 1 to 4.

### The interval

The page has no resampling for its live scores, so this uses the 2027 pre-registration's two-way bootstrap (section
10), on overflow and week:

- each draw resamples the overflows with replacement and, independently, the 7-day blocks with replacement; a row
  counts (times its overflow was drawn) × (times its block was drawn); all leads of an overflow-day share both draws;
- blocks are 7 days from 29 September 2026 (29 Sep–5 Oct, 6–12 Oct, ...), the last one possibly shorter;
- 2,000 draws from numpy's `default_rng(20270501)`, made once per build, shared by every cell;
- 95% interval: the 2.5th and 97.5th percentiles, numpy's default interpolation;
- each rule's fitted chances are held fixed within a draw; a draw in which a cell has no weight, or its reference's
  Brier score is 0, gives no skill for that cell, is left out of its interval and is counted.

### What the page says

For each cell and each rule, from the interval:

- lower end above 0: "SwimSignal beats [rule] here";
- upper end below 0: "SwimSignal does worse than [rule] here";
- otherwise: "not shown either way yet".

The rows are plain table rows beside the forecast's own figures. Where the forecast does not beat a rule, the page
says so in words, not only in the number. In particular, from April 2027 the claim "beats a rain rule" (or
"beats persistence") may be made for a cell only while that cell reads "beats" on the page as built; otherwise it is
withheld. A company cell with fewer than 20 spill rows among its common rows is shown as too few to judge.

### Implementation and checks

- Package module `src/dipcast/simple_references.py`, called by `forecast_log.verify_live`, writing `live.simple_refs`
  in `verification_live.json`. The page reads it. The scored CSV gains no column.
- A reproduction script, `scripts/simple_references.py`, reads the published scored CSV and the state release's four
  files and prints the same figures. It is the code amendment 4 names for 2027.
- Unit tests on synthetic rows: the trailing fit never reads a target day on or after the issue day; the floor and
  smoothing; the wet rule is strict; the bootstrap matches `evaluate_2027.Bootstrap`'s weights.
- A check against the interim read: on 29 September to 23 October with the interim's in-sample fit, the module must
  reproduce the interim's persistence and rain-over-10-mm skill figures for all companies, to rounding. This checks the
  moved code, not the rules.
- Build time: the bootstrap aggregates rows to overflow × block cells first, so each draw is two small matrix
  products. The status rebuild is vectorised per overflow.

### What follows

Every outcome leads to the page showing what it shows; nothing is adopted or withdrawn by these rows.

- Where the forecast does not beat a rule, the next deliverable is a diagnosis of that cell, using the existing
  calibration check (is it level or ranking?), not a model change.
- The 2027 season gives the prospective figures (amendment 4).

## Changes after this statement

1. **Wording, 10 November 2026, before any score was computed.** The fitting rows were described as rows "on which
   that rule has a chance", which is circular (a chance needs the fit). They are the rows on which the rule can be
   applied: status known for P, both days' rain for R. The intended rule is unchanged.

## First results, 10 November 2026

Computed after the statement and its clarification were pushed (commits `2240c42f` and `70416255`, 00:36 and 00:37 UTC
on 10 November). The page recomputes them on every build; these are the first, kept as a record.

**Inputs**, read only: the `state` release of 9 November 2026, 21:22 UTC (`dipcast.duckdb` `c5ed9dd5…6ebc4`,
`live_history.parquet` `3a4847bd…28724`, `live_coverage.parquet` `a5bbf950…16be`, `poll_log.parquet` `dcc68a12…25c7`)
and the published `verification_live.csv` of the same build (`2a1dfb30…842b`, 162,005 rows, target days 29 September
to 8 November 2026). Every row joined its logged forecast with the same issue time (162,005 of 162,005).
`forecast_log.verify_live` run on the same state in a scratch folder gave the same rows and the same figures to the
CSV's four-decimal rounding.

**Check of the moved code.** With the interim read's own in-sample fit on 29 September to 23 October,
`scripts/simple_references.py --interim-check` gives 117,324 rows, 91,444 with a known status, 107,650 with both days'
rain and 91,391 common, and skill −0.05 against persistence and 0.07 against rain over 10 mm on the same day, 0.09 and
0.07 in advance: the interim read's figures. The unit tests also check the status and rain code against the interim
script's on random inputs.

### What the page says now

| Cell | Forecasts | Spills | SwimSignal's Brier | Against persistence | Against rain over 10 mm | Against the long-run rate |
|---|---:|---:|---:|---|---|---|
| Same day | 25,613 | 1,476 | 0.0415 | 0.06 (−0.05 to 0.15), not shown | **0.18 (0.05 to 0.23), beats** | 0.28 (0.21 to 0.48), beats |
| In advance (1–4 days) | 77,060 | 5,397 | 0.0512 | 0.21 (−0.04 to 0.29), not shown | 0.18 (−0.03 to 0.24), not shown | 0.23 (0.18 to 0.38), beats |

Skill with its 95% interval, two-way bootstrap over 1,304 overflows and 6 blocks. The rules' own Brier scores: same day
persistence 0.0440, rain 0.0504, long-run rate 0.0577; in advance 0.0647, 0.0621 and 0.0662.

- **Same day, SwimSignal beats the rain rule** and is not shown better or worse than persistence.
- **In advance, it beats neither rule.** Both intervals cross 0. So on this record the claim "beats a rain rule" can
  be made for the same-day forecast and must be withheld for forecasts made in advance.
- Against the best of the three references in each draw (in the JSON, not on the page): same day 0.06 (−0.05 to
  0.13), in advance 0.18 (−0.05 to 0.23). Neither is shown above 0.

By company:

| Company | Same day: persistence | Same day: rain | In advance: persistence | In advance: rain |
|---|---|---|---|---|
| Anglian Water | −0.06 (−0.21 to 0.15) | 0.04 (−0.06 to 0.15) | 0.01 (−0.08 to 0.10) | 0.02 (−0.05 to 0.08) |
| Northumbrian Water | too few (18 spills) | too few | 0.23 (−0.13 to 0.45) | 0.20 (−0.01 to 0.40) |
| Severn Trent Water | −0.10 (−0.62 to 0.11) | 0.03 (−0.46 to 0.18) | 0.10 (−0.18 to 0.32) | 0.08 (−0.19 to 0.16) |
| South West Water | 0.24 (−0.79 to 0.56) | 0.41 (−0.21 to 0.64) | 0.34 (−0.74 to 0.53) | 0.34 (−0.44 to 0.50) |
| Southern Water | 0.27 (−0.49 to 0.99) | 0.43 (−0.06 to 0.84) | 0.49 (−0.99 to 0.57) | 0.44 (−0.87 to 0.53) |
| Thames Water | **−0.42 (−1.01 to −0.13), worse** | −0.20 (−0.41 to 0.03) | −0.03 (−0.51 to 0.13) | −0.05 (−0.43 to 0.09) |
| United Utilities | **0.25 (0.10 to 0.34), beats** | **0.27 (0.16 to 0.35), beats** | **0.32 (0.09 to 0.46), beats** | **0.27 (0.06 to 0.41), beats** |
| Wessex Water | −0.02 (−0.44 to 0.54) | 0.20 (−0.30 to 0.29) | 0.26 (−0.60 to 0.33) | 0.22 (−0.67 to 0.29) |
| Yorkshire Water | 0.10 (−0.09 to 0.23) | **0.19 (0.01 to 0.31), beats** | 0.19 (−0.01 to 0.30) | 0.15 (−0.01 to 0.25) |

- In Thames Water's area the same-day forecast does worse than persistence. This repeats the interim read's finding
  on a longer record and with a rule fitted only on earlier days.
- United Utilities, the one company the spill model was trained on, is the only company where the forecast beats both
  rules at both leads.

### Coverage

102,673 of 162,005 scored forecasts (63%) have both rules, from 2 October (the first days lack 100 fitting rows on
the active side). Status known: 78% of same-day rows, 69% of advance rows. Both days' rain: 92% of advance rows.

Whole issue days have no known status: 27 and 28 October, 3, 4, 6 and 7 November. On those days the site ran 4 to
18 times (48 scheduled), and an overnight gap between runs exceeded the 8-hour rule. So the comparison leaves out days
when the pipeline ran rarely. Whether those days were wetter or drier than the rest was not checked. Southern Water
has a known status on only 20–32% of its rows, as the interim read found (its feed stamps records only on change).

### What the numbers suggest, inferred and not tested

- The persistence figure moved from −0.05 (interim, in-sample fit, to 23 October) to +0.06 (trailing fit, to
  8 November). Two things changed at once: the chances are now fitted on earlier days only, and two more weeks were
  added. Which one moved it was not separated.
- Six 7-day blocks, the last of six days. The intervals will narrow as weeks are added, and one wet spell still
  weighs heavily.

### Next

Per "What follows": the cells where the forecast does not beat a rule get a diagnosis, not a model change. Thames
Water same day is the first: the calibration check (`docs/CALIBRATION-CHECK-2026-10.md`) already found its chances
too high on average and too extreme, so the question is whether the loss to persistence is level or ranking. The page keeps the figures current; the prospective test is the 2027 season under amendment 4.
