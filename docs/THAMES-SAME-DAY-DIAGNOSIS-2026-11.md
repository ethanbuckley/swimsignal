# Thames Water's same-day loss to persistence: level or ranking?

The Accuracy page compares the live spill forecast with two simple rules
([SIMPLE-REFERENCES-LIVE-2026-11.md](SIMPLE-REFERENCES-LIVE-2026-11.md)). In Thames Water's area, on the same day, it
does worse than persistence ("tomorrow is like now"): skill −0.42 (−1.01 to −0.13) on target days to 8 November. The
interim read found the same on 29 September to 23 October: −0.46 (−1.03 to −0.07). The register's SIMPLE-REFS row
promises a diagnosis by 30 November 2026: is the loss a fault of level (the chances are wrong on average or too
spread out) or of ranking (the forecast orders spill days worse than persistence does)?

This is a description of seen data, not a test. It changes no rule, threshold, forecast, page wording, active window
or the 2027 primary evaluation. No Open-Meteo call and no new fetch.

## Stated before any score

Written on 13 November 2026 on branch `claude/thames-same-day-diagnosis-d85ae6`, from main at `5f1ece11`, and pushed
before the script that computes the figures existed. Nothing in this section changes after a figure is seen, except a
plain bug fix, which would be listed under "Changes after this statement" with what it changed.

### What has been seen already

- **Interim read** (29 Sep to 23 Oct, persistence chances fitted on the rows scored): Thames same day, 3,863 common
  rows, 93 spills; Brier 0.0297 against persistence 0.0204; skill −0.46 (−1.03 to −0.07); AUC 0.87 against
  persistence's 0.67; mean forecast 0.062 against a spill rate of 0.024.
- **Calibration check** (same rows): Thames same day O/E 0.38 (0.11 to 0.51), judged too high on average and too
  extreme by its stated rules.
- **The page** (trailing fit, to 8 Nov): −0.42 (−1.01 to −0.13), "worse".
- **Live recalibration test** and **live vs EDM labels**: Thames's forecast ran several times its observed rate on
  29 Sep to 16 Oct (0.0225 against 0.0042, all leads, in the labels record). A company intercept cut Thames's Brier
  from 0.0051 to 0.0023 in the recalibration test. Thames's live feed matches the EA's events where both exist.
- **A8's statement** (per-overflow offsets for the eight non-UU companies, window 26 Oct to 22 Nov, read 25 Nov) and
  the live-status shadow's (window 25 Oct to 21 Nov, read 23 Nov). Neither window's outcomes are read here.

So a level fault is expected from what is already known. What has not been measured: how much of the Brier gap is
level, how much is spread, whether any part is ranking, and whether the loss sits on spill starts or spill ends.

### Dates: stopped at the first unread window

The calibration check's record runs to target day 23 October. Two active windows cover part of it and have not been
read:

- lead calibration B: target days 18 October to 14 November, read on or after **16 November**;
- ensemble rain D4: from 23 October, read **21 November**.

So this diagnosis uses **target days 29 September to 17 October 2026** only. That leaves out the wet spell of 20 to
23 October, which held most of the record's spills. Expected consequence: Thames's same-day cell will hold few spills
(the labels record found Thames's observed rate near 0.004 before 17 October), and the figures may be reported but not
judged (rule below).

**Extension, fixed now.** On or after 21 November 2026, and before 30 November, the same script runs unchanged on
target days 29 September to 23 October (the calibration check's whole record), with `--to 2026-10-23`. Its figures are
added beside these, labelled as the extension; they replace nothing. If the script must change for that run, the
change is listed under "Changes after this statement".

### Data

Read only, checked by SHA-256 before and after the run:

- **Scored forecasts:** the calibration check's file, `verification_live.csv` published on 24 October 2026,
  `434f910a…6eb598` (117,324 rows). A copy is in the private repository (`outreach/social-2026-10-25/generator/data/`);
  the run reads a write-protected copy in a scratch folder.
- **Forecast log and poll files:** the calibration check used the `state` release of 24 October, which is no longer on
  this machine and is not fetched again. The run uses the `state` release of 9 November 2026, 21:22 UTC, the one the
  page's first results used: `dipcast.duckdb` `c5ed9dd5…6ebc4`, `live_history.parquet` `3a4847bd…28724`,
  `live_coverage.parquet` `a5bbf950…16be`, `poll_log.parquet` `dcc68a12…25c7`. The log and poll files only grow, and
  the persistence status uses readings up to each row's issue time.
- **Check that the later state rebuilds the same rows, without reading any outcome:** on target days 29 September to
  23 October, the run must find the interim read's counts: 117,324 rows joined at the same issue time, 91,444 with a
  known status, 107,650 with both days' rain, 91,391 common; at lead 0, 1,382 active and 19,130 quiet rows with a known
  status; Thames Water 17,426 known and 17,416 common. These counts use no `observed` value. If any differs, the run
  stops and this record reports the difference.
- `DIPCAST_ROOT`, `DIPCAST_STATE` and `DIPCAST_CACHE` point at an empty scratch folder before any `dipcast` import.

### The two persistence forecasts

Persistence's rule is the page's and the interim read's: an overflow is **active** at issue time T if its poll record
shows it spilling at T or at any moment in the 48 hours before, counting only spill that had started by its last
current reading at or before T; the status is **known** when readings cover those 48 hours with no stretch over 8
hours (`dipcast.simple_references.persistence_status`). To be scored, each side gets a chance:

- **P-trail (primary), the page's:** `simple_references.trailing_chances`, (spills + 0.5) ÷ (rows + 1) over scored
  rows of the same lead and side, all companies, target days I − 28 to I − 1, at least 100 rows. Fitted on rows from
  29 September; within this run that means no row after 17 October enters any fit.
- **P-in (secondary), the interim read's:** each side's observed spill rate at the lead, all companies pooled, over
  every row with a known status in 29 September to 17 October. It is fitted on the rows it scores, which flatters it.

### Rows and cells

A row is one overflow, target day and lead from the scored file, joined to its logged forecast at the same issue time.
The **cell rows** are those with a P-trail chance and a rain-rule chance (the page's common rows); P-in is scored on
the same rows. The forecast is `forecast_calibrated`; the outcome is `observed`.

- **Primary cell:** Thames Water, lead 0.
- **Contrast 1:** the other eight named companies together, lead 0.
- **Contrast 2:** Thames Water, leads 1 to 4 pooled.

### What is computed, for the forecast F and for each persistence forecast P

1. **Brier score and skill** of F against P, as on the page.
2. **Level, spread and association** (Murphy 1988; exact, no bands). For a forecast q and outcome y on the cell rows,
   Brier = (mean q − mean y)² + (s_q − r·s_y)² + s_y²(1 − r²), with s the standard deviations (divided by n) and r
   the correlation of q with y.
   - **level** = (mean q − mean y)²: wrong on average;
   - **spread** = (s_q − r·s_y)²: once level is right, still too spread out (or too narrow) for how well it tracks
     the outcome;
   - **association** = s_y²(1 − r²): what is left after the best straight-line rescaling of q. Only better ordering
     or more information lowers it.

   Level and spread together are the **calibration** part. s_y is the same for F and P on the same rows, so the
   association terms differ only through r.
3. **Reliability and resolution in bands.** F in the calibration check's seven bands (cuts 0.01, 0.03, 0.07, 0.15,
   0.40, 0.70); P in its two sides (active, quiet). Per forecast: reliability, resolution and uncertainty, plus the
   within-band remainder that makes them add up to the Brier score exactly (Stephenson, Coelho and Jolliffe 2008).
   With few spills per band, resolution in bands is biased upward; this is stated beside the figures, and the
   unbanded split in item 2 is the one the reading rule uses.
4. **Ranking.** AUC of F; AUC of persistence's active flag (the rule's own ordering, the same for P-trail and P-in);
   their difference. Ties count half (`evaluate_2027.auc`). And at persistence's own alert count: if F flagged as many
   rows as persistence flags active (the highest-F rows), how many spills would its flagged rows hold, against the
   spills on active rows.
5. **Spill starts and spill ends.** The cell rows split by persistence's side at issue:
   - **active rows:** persistence says "spill". A spill that day is a continuation; no spill is a **spill end**,
     where persistence is wrong;
   - **quiet rows:** persistence says "no spill". A spill that day is a **spill start**, where persistence is wrong.

   Per side: rows, spills, spill rate, mean F, mean P, Brier of F and P, F's AUC within the side (persistence has no
   ordering within a side). Each side's **contribution** to the cell's Brier difference is (side rows ÷ cell rows) ×
   (Brier F − Brier P on that side); the two contributions add to the cell's difference. Each side's difference is
   split into its level part, (mean F − mean y)² − (mean P − mean y)², and the rest. Active rows are also shown split
   into spilling at issue and stopped within the 48 hours before (counts and rates only).

### Intervals

- The page's two-way bootstrap (`simple_references.Draws`): overflows and 7-day blocks from 29 September resampled
  together, 2,000 draws, seed 20270501, 95% percentile intervals. Fitted chances are held fixed within a draw. A draw
  in which a cell has no spill gives no value for that cell; it is left out and counted.
- Blocks: 29 Sep–5 Oct, 6–12 Oct and 13–17 Oct (5 days). Three blocks make the block resampling crude. **Declared
  sensitivity:** the same draws with the blocks not resampled (overflows only), for the differences in items 1, 2, 4.
- Intervals are given for: the skill; each term of item 2 for F, for P and their difference (F − P); the AUC
  difference; the hits at persistence's alert count (difference); each side's contribution in item 5.

### Reading rule, fixed now

On the primary cell, with P-trail:

- **Calibration fault shown:** the interval of (level + spread)(F) − (level + spread)(P) lies above 0.
- **Ranking fault shown:** the interval of AUC(F) − AUC(active flag) lies below 0, or the interval of association(F) −
  association(P) lies above 0.
- **F ranks better, shown:** the AUC-difference interval lies above 0, or the association-difference interval lies
  below 0.
- Answer: "level (calibration)" if the first holds and no ranking fault is shown; "ranking" if a ranking fault is
  shown and the first does not hold; "both" if both hold; otherwise "not shown either way", with the point estimates'
  direction stated as a direction only.
- **Where the loss sits:** the side (starts or ends) whose contribution interval lies above 0. If neither, the side
  with the larger point contribution, called a direction only.
- **Too few:** if the primary cell holds fewer than 50 overflow-days with a spill (the calibration check's
  `MIN_JUDGED`), the figures are reported and the rule is **not applied**; the answer waits for the extension. The same
  holds for each contrast.

P-in and the overflow-only intervals are reported beside, and do not change the answer.

### What each outcome leads to

None of these changes a forecast or the page.

- **Level (calibration):** the remedy is a recalibration, not a new input. A8's per-overflow offsets are the existing
  level candidate for Thames. Next deliverable: a note committed before A8's read (25 November) that adds, as a
  labelled secondary beside A8's own verdict, A8's frozen offsets scored on Thames same-day rows against P-trail. If
  spread is shown as well (spread(F) − spread(P) above 0), offsets alone cannot fix it; then a Thames slope candidate
  is frozen on rows to 17 October and scored forward once the windows over its scoring dates have been read.
- **Ranking:** the forecast lacks something persistence has, most likely the current status. Next deliverable: a note
  committed before the live-status shadow's read (23 November) that adds the shadow candidate's Thames same-day cell
  against P-trail as a labelled secondary.
- **Both:** both notes.
- **Not shown, or too few:** the extension (on or after 21 November), then this rule applied to it, by 30 November.

### Script

`scripts/thames_same_day_diagnosis.py`, reusing `scripts/simple_references.py` for the join,
`dipcast.simple_references` for the status, rain and trailing fit, and `evaluate_2027.auc`. Output
`docs/THAMES-SAME-DAY-DIAGNOSIS-2026-11.json`.

## Changes after this statement

None yet.

## Results

Not yet run.
