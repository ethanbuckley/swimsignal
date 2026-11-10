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
on which that rule has a chance, with target day from I − 28 to I − 1. The page's outcome for target day I − 1 is
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

None yet.

## Results

Not computed at the time of the statement. The page shows them on every build.
