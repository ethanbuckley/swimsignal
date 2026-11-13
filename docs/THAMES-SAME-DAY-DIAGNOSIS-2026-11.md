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

None to the method. Two facts about the run, for the record:

- The script was committed (`29c8ce78`, 15:24:22 UTC) six seconds after the full run started (15:24:16 UTC). The file
  was not edited between the run and the commit (`git diff 29c8ce78 scripts/` prints nothing).
- Before the full run, a 20-draw trial ran once to catch errors (as the calibration check did). It printed the three
  cells' reading-rule lines. Its figures are not used. One of its lines differs from the full run's: with 20 draws the
  other eight companies' calibration difference read as shown; with 2,000 it does not.

## Results

Run on 13 November 2026, 15:24:16 to 15:24:54 UTC, with `scripts/thames_same_day_diagnosis.py` at `29c8ce78`, after the
statement was pushed at 15:21:32 UTC (`186a074c`). Output: `docs/THAMES-SAME-DAY-DIAGNOSIS-2026-11.json`.

**Checks.** All five input hashes matched before and after, and the source files they were copied from were unchanged.
The count check passed: the 9 November state rebuilds the interim read's rows exactly (117,324 joined at the same issue
time, 91,444 known, 107,650 with rain, 91,391 common, 1,382 active and 19,130 quiet at lead 0, Thames 17,426 and
17,416). The scratch `DIPCAST_ROOT` was empty after the run. 84,659 scored rows fall on 29 September to 17 October;
49,426 of them are cell rows, from 2 October (the first days lack 100 fitting rows on the active side). Bootstrap: 1,145
overflows, 3 blocks.

### Answer

**Not answerable yet by the stated rule.** Before 18 October, Thames Water's same-day cell holds 16 overflow-days with a
spill, below the 50 the rule needs, so the rule was not applied. As a direction only, on 2 to 17 October: the forecast's
extra Brier loss against persistence (0.0035) sits in calibration, almost all of it in the spread term (0.0029), not in
the level term (0.0001). No ranking fault is shown, but the forecast has no ranking advantage either: its AUC is 0.66
against persistence's 0.65, and its correlation with the outcome is 0.02. The loss falls on quiet overflows: the forecast
gave 0.07 or more to 196 Thames overflow-days, of which 1 spilled, while 10 of the 16 spills came at forecasts under
0.01. So in the dry part of the autumn, Thames's chances moved without tracking Thames's spills. Elsewhere, on the same
days, the forecast orders spill days better than persistence (AUC 0.88 against 0.70, difference 0.08 to 0.31) and no
calibration fault is shown. The whole record's answer waits for the extension to 23 October, run on or after
21 November, which adds the wet spell that held most of the 93 Thames spills in the interim read.

### How to read "spread" here

When the correlation with the outcome is near 0, the spread term is close to the forecast's own variance: a forecast
that varies without tracking the outcome pays for its variation there. So for Thames on these days, "a spread fault"
and "no ranking advantage" describe the same rows. A recalibration could flatten Thames's chances toward a constant and
remove most of the gap, but it would add no information: it would at best tie a near-constant persistence, which is
what persistence is at Thames on these days (16 of 2,563 rows active). In ratio terms the forecast is about three times
the observed rate (0.020 against 0.006), as the calibration check found, but at rates this low the squared gap of the
level term costs little.

### The figures

Brier terms are shown ×1,000. Intervals are 95%, from the two-way bootstrap unless the column says "overflows only".
P-in figures (fitted on the rows scored) are in the last column; they differ little from P-trail's. A cell with fewer
than 50 overflow-days with a spill is described, not judged.

#### Thames Water, same day

2,563 rows, 194 overflows, 16 spill rows on 16 overflow-days, 16 active rows.

| | Forecast | P-trail | Forecast − P-trail (overflow and week) | Same, overflows only | Forecast − P-in |
|---|---:|---:|---|---|---|
| Brier | 9.3 | 5.7 | 3.5 (−0.1 to 7.4) | 2.3 to 5.0 | 3.5 (−0.0 to 7.4) |
| Level | 0.2 | 0.1 | 0.1 (−0.2 to 0.6) | 0.0 to 0.2 | 0.1 (−0.2 to 0.6) |
| Spread | 2.9 | 0.0 | 2.9 (−0.1 to 6.0) | 1.9 to 3.5 | 2.8 (−0.1 to 6.0) |
| Calibration (level + spread) | 3.1 | 0.1 | 3.0 (−0.4 to 6.6) | 2.0 to 3.6 | 2.9 (−0.3 to 6.6) |
| Association | 6.2 | 5.6 | 0.6 (−0.0 to 3.0) | −0.0 to 2.3 | 0.6 (−0.0 to 3.0) |
| Skill against persistence | | | −0.61 (−2.14 to 0.02) | −1.36 to −0.35 | −0.61 (−2.13 to 0.01) |

Correlation with the outcome: forecast 0.017, P-trail 0.303. Mean forecast 0.0197, mean P-trail 0.0160, spill rate 0.0062.

Bands (×1,000): forecast reliability 2.9 (0.3 to 6.7), resolution 0.0 (0.0 to 0.2), remainder 0.1; P-trail reliability 0.1 (0.1 to 1.0), resolution 0.6 (0.0 to 3.0), remainder 0.0; uncertainty 6.2.

Ranking: AUC forecast 0.655 (0.483 to 0.875), active flag 0.654 (0.497 to 0.818); difference 0.001 (−0.276 to 0.374; overflows only −0.188 to 0.299). At persistence's 16 alerts: the forecast's top 16 rows hold 1 spill, the active rows 5; difference −4 (−16.7 to 0.0).

| Side | Rows | Spills | Spill rate | Mean forecast | Mean P-trail | Brier forecast | Brier P-trail | Forecast AUC within |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Active (spill ends) | 16 | 5 | 0.312 | 0.011 | 0.252 | 0.3066 | 0.2161 | 0.44 |
| Quiet (spill starts) | 2,547 | 11 | 0.004 | 0.020 | 0.014 | 0.0074 | 0.0044 | 0.68 |
| Active, spilling at issue | 2 | 2 | 1.000 | 0.004 | 0.251 | 0.9916 | 0.5612 | |
| Active, stopped in the 48 h before | 14 | 3 | 0.214 | 0.013 | 0.253 | 0.2088 | 0.1668 | 0.45 |

| Contribution to forecast − P-trail (×1,000) | Total | Level part | Rest |
|---|---|---|---|
| Quiet rows (spill starts) | 3.0 (0.2 to 6.8) | 0.1 (−0.2 to 0.7) | 2.8 (0.3 to 6.1) |
| Active rows (spill ends) | 0.6 (−0.3 to 2.2) | 0.5 (−0.3 to 2.2) | 0.0 (−0.0 to 0.1) |

Forecast bands:

| Band | Rows | Spills | Mean forecast | Spill rate |
|---|---:|---:|---:|---:|
| under 0.01 | 2,036 | 10 | 0.003 | 0.005 |
| 0.01–0.03 | 188 | 3 | 0.016 | 0.016 |
| 0.03–0.07 | 143 | 2 | 0.049 | 0.014 |
| 0.07–0.15 | 96 | 0 | 0.103 | 0.000 |
| 0.15–0.40 | 95 | 1 | 0.245 | 0.011 |
| 0.40–0.70 | 5 | 0 | 0.471 | 0.000 |
| 0.70 or more | 0 | 0 | | |


#### Other eight companies, same day

10,616 rows, 946 overflows, 344 spill rows on 344 overflow-days, 659 active rows.

| | Forecast | P-trail | Forecast − P-trail (overflow and week) | Same, overflows only | Forecast − P-in |
|---|---:|---:|---|---|---|
| Brier | 26.7 | 29.2 | −2.4 (−6.4 to 0.7) | −4.6 to −0.1 | −1.9 (−5.8 to 1.3) |
| Level | 0.0 | 0.0 | 0.0 (−0.1 to 0.1) | −0.1 to 0.1 | 0.0 (−0.1 to 0.1) |
| Spread | 0.6 | 0.1 | 0.5 (−0.2 to 1.6) | 0.1 to 1.3 | 0.6 (−0.2 to 1.7) |
| Calibration (level + spread) | 0.6 | 0.1 | 0.6 (−0.2 to 1.6) | 0.0 to 1.4 | 0.6 (−0.2 to 1.7) |
| Association | 26.1 | 29.1 | −3.0 (−6.3 to −0.4) | −4.8 to −1.3 | −2.5 (−5.8 to 0.3) |
| Skill against persistence | | | 0.08 (−0.02 to 0.25) | 0.00 to 0.15 | 0.07 (−0.05 to 0.23) |

Correlation with the outcome: forecast 0.410, P-trail 0.269. Mean forecast 0.0371, mean P-trail 0.0286, spill rate 0.0324.

Bands (×1,000): forecast reliability 0.7 (0.2 to 2.2), resolution 4.9 (3.1 to 7.9), remainder −0.5; P-trail reliability 0.0 (0.0 to 0.5), resolution 2.7 (0.8 to 5.6), remainder 0.5; uncertainty 31.4.

Ranking: AUC forecast 0.877 (0.808 to 0.969), active flag 0.701 (0.619 to 0.791); difference 0.176 (0.075 to 0.313; overflows only 0.141 to 0.213). At persistence's 659 alerts: the forecast's top 659 rows hold 174 spills, the active rows 155; difference 19 (−40.0 to 81.0).

| Side | Rows | Spills | Spill rate | Mean forecast | Mean P-trail | Brier forecast | Brier P-trail | Forecast AUC within |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Active (spill ends) | 659 | 155 | 0.235 | 0.140 | 0.243 | 0.1641 | 0.1858 | 0.76 |
| Quiet (spill starts) | 9,957 | 189 | 0.019 | 0.030 | 0.014 | 0.0176 | 0.0188 | 0.87 |
| Active, spilling at issue | 11 | 11 | 1.000 | 0.511 | 0.227 | 0.3260 | 0.5992 | |
| Active, stopped in the 48 h before | 648 | 144 | 0.222 | 0.134 | 0.244 | 0.1613 | 0.1788 | 0.75 |

| Contribution to forecast − P-trail (×1,000) | Total | Level part | Rest |
|---|---|---|---|
| Quiet rows (spill starts) | −1.1 (−5.4 to 2.3) | 0.1 (−0.1 to 0.4) | −1.2 (−5.3 to 1.9) |
| Active rows (spill ends) | −1.3 (−3.2 to 0.4) | 0.6 (−0.4 to 1.5) | −1.9 (−4.2 to 0.5) |

Forecast bands:

| Band | Rows | Spills | Mean forecast | Spill rate |
|---|---:|---:|---:|---:|
| under 0.01 | 7,179 | 36 | 0.003 | 0.005 |
| 0.01–0.03 | 1,191 | 38 | 0.017 | 0.032 |
| 0.03–0.07 | 865 | 44 | 0.047 | 0.051 |
| 0.07–0.15 | 612 | 41 | 0.103 | 0.067 |
| 0.15–0.40 | 582 | 99 | 0.242 | 0.170 |
| 0.40–0.70 | 141 | 60 | 0.523 | 0.426 |
| 0.70 or more | 46 | 26 | 0.796 | 0.565 |


#### Thames Water, leads 1 to 4

6,995 rows, 194 overflows, 56 spill rows on 15 overflow-days, 38 active rows.

| | Forecast | P-trail | Forecast − P-trail (overflow and week) | Same, overflows only | Forecast − P-in |
|---|---:|---:|---|---|---|
| Brier | 10.4 | 7.9 | 2.5 (1.4 to 3.6) | 1.8 to 3.5 | 2.6 (1.5 to 3.9) |
| Level | 0.3 | 0.1 | 0.2 (−0.0 to 0.3) | 0.1 to 0.3 | 0.1 (−0.0 to 0.3) |
| Spread | 2.2 | 0.0 | 2.2 (0.8 to 2.7) | 1.5 to 2.6 | 2.1 (0.4 to 2.7) |
| Calibration (level + spread) | 2.4 | 0.1 | 2.3 (0.9 to 2.9) | 1.6 to 2.8 | 2.2 (0.4 to 2.9) |
| Association | 7.9 | 7.7 | 0.2 (−0.0 to 2.4) | −0.0 to 1.4 | 0.4 (−0.0 to 3.3) |
| Skill against persistence | | | −0.32 (−0.94 to −0.16) | −0.82 to −0.19 | −0.33 (−0.97 to −0.16) |

Correlation with the outcome: forecast 0.018, P-trail 0.164. Mean forecast 0.0246, mean P-trail 0.0187, spill rate 0.0080.

Bands (×1,000): forecast reliability 2.3 (1.6 to 3.0), resolution 0.0 (0.0 to 0.1), remainder 0.2; P-trail reliability 0.2 (0.1 to 2.1), resolution 0.4 (0.0 to 3.3), remainder 0.0; uncertainty 7.9.

Ranking: AUC forecast 0.599 (0.456 to 0.856), active flag 0.587 (0.496 to 0.740); difference 0.011 (−0.216 to 0.359; overflows only −0.178 to 0.276). At persistence's 38 alerts: the forecast's top 38 rows hold 0 spills, the active rows 10; difference −10 (−54.0 to 0.0).

| Side | Rows | Spills | Spill rate | Mean forecast | Mean P-trail | Brier forecast | Brier P-trail | Forecast AUC within |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Active (spill ends) | 38 | 10 | 0.263 | 0.020 | 0.130 | 0.2563 | 0.2050 | 0.41 |
| Quiet (spill starts) | 6,957 | 46 | 0.007 | 0.025 | 0.018 | 0.0090 | 0.0068 | 0.63 |
| Active, spilling at issue | 1 | 1 | 1.000 | 0.003 | 0.167 | 0.9934 | 0.6935 | |
| Active, stopped in the 48 h before | 37 | 9 | 0.243 | 0.020 | 0.129 | 0.2364 | 0.1918 | 0.42 |

| Contribution to forecast − P-trail (×1,000) | Total | Level part | Rest |
|---|---|---|---|
| Quiet rows (spill starts) | 2.2 (1.3 to 3.0) | 0.2 (−0.0 to 0.4) | 2.1 (1.3 to 2.7) |
| Active rows (spill ends) | 0.3 (−0.1 to 1.3) | 0.2 (−0.1 to 1.3) | 0.1 (−0.0 to 0.1) |

Forecast bands:

| Band | Rows | Spills | Mean forecast | Spill rate |
|---|---:|---:|---:|---:|
| under 0.01 | 4,478 | 31 | 0.004 | 0.007 |
| 0.01–0.03 | 1,132 | 6 | 0.018 | 0.005 |
| 0.03–0.07 | 653 | 9 | 0.046 | 0.014 |
| 0.07–0.15 | 478 | 7 | 0.102 | 0.015 |
| 0.15–0.40 | 251 | 3 | 0.219 | 0.012 |
| 0.40–0.70 | 3 | 0 | 0.460 | 0.000 |
| 0.70 or more | 0 | 0 | | |


### Reading rule, applied as stated

| Cell | Spill overflow-days | Applied | Answer |
|---|---:|---|---|
| Thames Water, same day (primary) | 16 | no, fewer than 50 | none yet |
| Other eight companies, same day | 344 | yes | not shown either way; the forecast ranks better, shown (AUC difference 0.08 to 0.31, association difference −6.3 to −0.4 ×1,000) |
| Thames Water, leads 1 to 4 | 15 | no, fewer than 50 | none yet |

### What the figures suggest, inferred and not tested

- Thames's chances come from the spill model's first layer alone. A8's record says per-overflow offsets exist only for
  United Utilities. If layer 1 responds to forecast rain at Thames overflows that rarely spill in autumn, it would give
  the pattern above: chances spread over dry days, none of it tracking the outcome. This was not checked against the
  rain inputs.
- In the interim read's whole record (to 23 October), Thames's same-day AUC was 0.87 against persistence's 0.67. Here,
  before the wet spell, it is 0.66 against 0.65. So the forecast's Thames ranking may hold in wet weather and fail in
  dry. The extension will show whether that holds on the same rule; the split by weather was not stated, so it would be
  exploratory.
- If the extension shows the same pattern, A8's per-overflow offsets (a level shift) are unlikely to close the gap on
  their own, since level costs little here. A shrink of Thames's chances toward its rate (a slope) would be the
  calibration remedy to test.

### Limits

- 16 events in the primary cell. The two-way intervals rest on 3 week-blocks, the last of 5 days; 27 of 2,000 draws had
  no Thames spill and give no value. The overflows-only intervals are narrower and are a sensitivity, not the reading.
- Days run from 2 to 17 October, the drier part of the record. Nothing here describes Thames in a wet spell.
- Persistence's status is rebuilt from a later state release, as on the page; it reads event times published after
  the issue (flatters persistence a little, measured at 50 of 812 active rows in the interim read).
- The quiet side holds both the spill starts and the dry days that stayed dry; the loss there is mostly chances given
  on rows that did not spill.

### Next

Per "What each outcome leads to": **too few, so the extension.** On or after 21 November 2026 (after ensemble rain's
read) and before 30 November, run unchanged:

```bash
DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch> DIPCAST_CACHE=<scratch> uv run python scripts/thames_same_day_diagnosis.py --scored <verification_live.csv 434f910a> --state <state folder> --to 2026-10-23 --out docs/THAMES-SAME-DAY-DIAGNOSIS-2026-11-extension.json
```

The state folder must pass the script's count check; it stops otherwise. The 9 November copies used here are in this
run's scratch folder and in the page session's, neither of which is permanent. A later `state` release passes if the
forecast log and poll files still hold the October rows; the count check settles it.

Then apply the reading rule to its Thames same-day cell and add the answer here, beside these figures. Its outcome
decides the note for A8's read (level), for the live-status shadow's read (ranking), or both. If the extension shows
calibration with no ranking advantage, as here, the note names a Thames slope candidate, not A8's offsets alone. The
live-status shadow's read is 23 November and A8's is 25 November, both before the extension can be finished with
certainty, so those two notes may come after the reads they would accompany; in that case they are labelled as
written after the read.
