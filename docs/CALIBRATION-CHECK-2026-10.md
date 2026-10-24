# Calibration check of the live spill forecast, October 2026

A diagnostic report, prompted by the interim usefulness read (`docs/INTERIM-USEFULNESS-2026-10.md`,
PR #338). That read found the forecast ranks spill days well (AUC 0.88 same day) but scores no better
than "it is spilling now" on the Brier score. It inferred, without testing, that the forecast's chances
run too high in places. This check asks whether they do, where, and across which range of chances.

It changes nothing. No model is refitted, no threshold or level changes, no corrected forecast is made
or scored. A correction fitted and scored on these same rows would show an improvement by construction,
so none is reported.

## Stated before the run

Written on 24 October 2026 at about 22:30 UTC, before any figure below was computed. Committed on its own, ahead
of the script and the results.

### Data

The same fixed record as PR #338, checked by SHA-256 before the run:

| File | SHA-256 |
|---|---|
| `verification_live.csv` (published scored live spill forecasts) | `434f910aa0170ec59bba08eaf5f038b423caae0209b4c89ac75891de786eb598` |
| `dipcast.duckdb` (state release) | `8544507fda525c3cb7f3cb3e246d57728e911cbf54dbe6b9e35d519313aed4e7` |
| `live_history.parquet` | `b38bb6a8e7f58e501b11d01af03dd19006926b1b4bc74fc6437233fb61349052` |
| `live_coverage.parquet` | `75cdd298c062cc28b907b25bdaf8b1577496f0741775c0812f5be731c5542676` |
| `poll_log.parquet` | `b09aafb84e2a9be1ba4eedd03b0dceadc457f329b667a2f506e50cf424f63662` |

- **Rows, primary:** every scored row, 117,324: one monitored overflow, one target day (29 Sep to 23 Oct
  2026) and one lead (0 to 4). Forecast: `forecast_calibrated`, as the map and the Accuracy page use it.
  Outcome: `observed`.
- **Rows, secondary:** #338's common rows (status known and rain for both days), rebuilt with #338's own
  functions, so the calibration can be read beside #338's Brier comparison.

### Strata

- Company: the eight named companies in the file, each alone. Rows with no company ("unknown") are
  counted and not interpreted.
- Lead: lead 0 (same day) and leads 1 to 4 pooled (in advance), for every company; and each lead 0 to 4
  alone for all companies together.

### Diagnostics

1. **Mean forecast against prevalence** (calibration in the large): the mean forecast E, the observed
   spill rate O, and O/E. This alone says whether the chances are too high on average. It does not say
   where in the range they are wrong.
2. **Reliability across the range of chances.** The pre-registration's four bands for spills (cuts 0.15,
   0.40, 0.70; `scripts/evaluate_2027.py`, `SPILL_CUTS`), with the low band split at 0.01, 0.03 and 0.07,
   because most forecasts fall in it: seven bands. Per band: rows, distinct overflow-days, overflow-days
   with a spill, mean forecast, observed rate with its 95% interval.
3. **Logistic calibration**, fitted only to describe: the intercept a with the slope fixed at 1
   (a below 0: too high overall), and the slope b of logit(observed) = α + b × logit(forecast), forecast
   clipped to 0.0001–0.9999 (b below 1: too extreme, high chances too high and low ones too low; above 1:
   too timid). No forecast is made from these fits and none is scored.
4. **Brier decomposition** (Murphy) over the seven bands: reliability (the calibration loss), resolution
   and uncertainty. It separates a calibration problem from a ranking one. The band version is an
   approximation (within-band spread is ignored), and is reported as such.
5. **Stability**: O/E in each of the four 7-day blocks, by lead group, for all companies and for each
   company.

### Uncertainty and repeated leads

PR #338's two-way bootstrap (`evaluate_2027.Bootstrap`): overflows and 7-day blocks from 29 Sep resampled
together, 2,000 draws, seed 20270501, 95% percentile intervals. All leads of an overflow and day share
their draws, so the pooled lead group is not treated as five independent forecasts. Beside every row
count, the number of distinct overflow-days is given. Per-lead results are reported, and never combined
as if independent. There are only four blocks, and the last one (20–23 Oct, four days) holds most of the
spills, so every interval is crude. Any finding is stated with that limit.

### Missing data

Only scored rows are used, as on the Accuracy page. The cells that were not scored are not imputed:
no current feed, gaps over 8 h, too few polls, a missed deadline. They number 23,841 in the window
(verification.json). If scoring fails more on wet days, these rates describe drier conditions. The
secondary rows inherit #338's coverage (status known and rain present), and the counts are given.

### What would support or contradict overprediction (fixed now)

For one stratum:

- **Supports overprediction on average:** the O/E interval lies entirely below 1, and O/E is below 1
  in at least 3 of the 4 blocks.
- **Supports overprediction at higher chances (too extreme):** the slope b's interval lies entirely below
  1, and the observed rate is below the mean forecast in every band from 0.15 up that holds at least 20
  overflow-days with a spill.
- **Contradicts overprediction:** the O/E interval lies entirely above 1 (too low on average), or b's
  interval lies entirely above 1 (too timid).
- **Neither:** an O/E interval that contains 1 is reported as no clear evidence either way at this
  sample size, whatever the point estimate.
- A stratum with fewer than 50 overflow-days with a spill is reported but not judged.

### The persistence caveat from #338

#338 rebuilt "spilling at issue time" from the companies' event times as published later. In its
cross-check against the shadow's own logged status, 50 of 812 active rows were spill starts published
after the issue time and dated back. So that reference knew a little more than a swimmer could have,
which flatters it. This check uses no persistence reference in its primary results. One declared
sensitivity: on the rows where the shadow logged `spilling_at_issue` (from 20–21 Oct), the Brier score
of the forecast against persistence read from that logged, as-of-time status (its chance fitted on
those same rows, which still flatters it). That window is a single block, so it gets point estimates
only and no interval.

### Script

`scripts/calibration_check.py`, reusing #338's `scripts/interim_usefulness.py` for the rows and
`scripts/evaluate_2027.py` for the bootstrap.

## Results

Run on 24 Oct 2026 with `scripts/calibration_check.py` at this branch's results commit: the 20-draw trial
finished at 22:33:59 UTC and the full run at 22:35:51 UTC (95.6 s), after the statement was pushed at
22:32:34 UTC (commit `c745c48`). Output: `docs/CALIBRATION-CHECK-2026-10.json`. All five input hashes matched; the rows matched
#338's exactly (117,324 scored, 91,391 common, 1,145 overflows, 4 blocks). Before the full run, a
20-draw trial ran once to time the script and catch errors; its figures are not used.

### Verdict

**Overall, the forecast's chances run too high, and the higher chances run highest.** Both stated rules
are met for all companies together, same day and in advance:

| All companies | Mean forecast | Observed rate | O/E (95% interval) | Blocks with O/E below 1 | Slope b (95% interval) |
|---|---|---|---|---|---|
| Same day (lead 0) | 0.063 | 0.047 | 0.74 (0.65 to 0.87) | 4 of 4 | 0.74 (0.63 to 0.81) |
| In advance (leads 1–4) | 0.059 | 0.047 | 0.80 (0.62 to 0.91) | 4 of 4 | 0.74 (0.60 to 0.80) |

O/E 0.74 means the observed rate is about 26% below the mean forecast (0.047 against 0.063); the
forecast is about 34% above what was observed. In advance, 0.047 against 0.059: observed 20% below,
forecast 26% above.

The same holds on #338's common rows: O/E 0.74 and 0.81, slope 0.75 and 0.74, both rules met.

**It is not true everywhere.** By company, with at least 50 overflow-days with a spill:

| Company | Same day: O/E (interval); judged | In advance: O/E (interval); judged |
|---|---|---|
| Thames Water | 0.38 (0.11 to 0.51); too high on average, and too extreme | 0.42 (0.09 to 0.57); too high on average |
| United Utilities | 0.66 (0.39 to 0.94); too high on average | 0.73 (0.47 to 1.05); no clear evidence |
| Wessex Water | 0.66 (0.13 to 0.85); too high on average | 0.70 (0.11 to 1.00); too high on average |
| Southern Water | 0.64 (0.09 to 0.93); too high on average | 0.66 (0.06 to 0.96); too high on average |
| Anglian Water | 1.12 (0.69 to 2.18); too extreme, not too high on average | 1.39 (0.81 to 2.15); too extreme, not too high on average |
| Yorkshire Water | 1.21 (0.83 to 1.86); no clear evidence | 1.14 (0.66 to 1.71); too extreme |
| Severn Trent Water | 0.87 (0.30 to 1.65); no clear evidence | 0.95 (0.35 to 1.42); no clear evidence |
| South West Water | 1.04 (0.24 to 1.96); no clear evidence | 1.16 (0.16 to 1.88); no clear evidence |
| Northumbrian Water | 16 spill overflow-days: not judged | not judged |

"Too extreme" means the slope's interval is below 1 and every counted band from 0.15 up has an observed
rate below its mean forecast (rule 2 as stated). Each judgement is the stated rule applied mechanically;
the JSON holds every interval.

### Across the range of chances

All companies, same day. Rows equal overflow-days at lead 0. Observed rate with its 95% interval:

| Band | Rows | Overflow-days with a spill | Mean forecast | Observed (interval) |
|---|---|---|---|---|
| under 0.01 | 13,301 | 84 | 0.003 | 0.006 (0.004 to 0.011) |
| 0.01–0.03 | 2,992 | 72 | 0.017 | 0.024 (0.014 to 0.035) |
| 0.03–0.07 | 2,377 | 99 | 0.048 | 0.042 (0.027 to 0.060) |
| 0.07–0.15 | 1,927 | 133 | 0.104 | 0.069 (0.044 to 0.093) |
| 0.15–0.40 | 2,140 | 329 | 0.249 | 0.154 (0.105 to 0.188) |
| 0.40–0.70 | 753 | 273 | 0.527 | 0.363 (0.302 to 0.458) |
| 0.70 or more | 210 | 115 | 0.785 | 0.548 (0.411 to 0.743) |

In advance (leads 1–4 pooled) the pattern is the same: 0.240 forecast against 0.154 observed in the
0.15–0.40 band, 0.537 against 0.389 in 0.40–0.70, 0.766 against 0.559 at 0.70 or more. Its rows repeat
overflow-days across leads (for example 7,683 rows on 4,510 overflow-days in 0.15–0.40), and the
intervals resample them together.

What the bands show:

- Below 0.01 the forecast is slightly too **low**: 0.003 against 0.006, interval above the forecast.
- From 0.07 up it is too **high**: the observed rate is 30% to 38% below the mean forecast in each band
  (0.104 forecast against 0.069 observed; 0.249 against 0.154; 0.527 against 0.363; 0.785 against 0.548).
  Put the other way, the forecast is 43% to 62% above what was observed.
- Within 0.03–0.07 it is about right.
- This is the shape a slope below 1 describes: chances too spread out, high ones too high and the lowest
  slightly too low. The overall O/E is pulled below 1 by the upper bands.
- The 0.40 line is the High warning. Forecasts at 0.40–0.70 came true about 36% of the time same day.
  Of the High warnings (0.40 and up), 388 of 963 came true (40%), close to the Accuracy page's 42% over all leads.

By company, the upper bands are too high at Thames Water, United Utilities, Wessex Water, Anglian Water
and, below 0.40, Southern Water. They are close to their observed rate at Yorkshire Water (0.15–0.40:
0.235 against 0.232 same day), Severn Trent Water (0.231 against 0.221) and South West Water.

### Calibration loss and ranking (Brier decomposition, seven bands)

| All companies | Brier | Reliability (calibration loss) | Resolution | Uncertainty |
|---|---|---|---|---|
| Same day | 0.0390 | 0.0023 | 0.0075 | 0.0445 |
| In advance | 0.0397 | 0.0015 | 0.0064 | 0.0448 |

The calibration loss is about a third of the resolution same day. It is large enough to matter beside
#338's small margins against the simple rules (Brier differences of a few thousandths). But this check
fits nothing and scores nothing, so it does not show how much of that loss a correction would remove.
A correction fitted here and scored here would gain by construction.

### Stability across blocks

All companies, O/E per 7-day block, same day: 0.87, 0.67, 0.79 and 0.71 (the last block, 20–23 Oct,
holds 599 of the 1,105 overflow-days with a spill). In advance: 0.74, 0.80, 0.65, 0.89. Below 1 in all
four blocks both times. So the overall overprediction is not only the wet spell. By lead, it weakens
with lead time: O/E 0.69 at lead 1, 0.74 at 2, 0.83 at 3 (interval 0.58 to 1.00) and 0.99 at 4 (0.67 to
1.22, below 1 in one block). The slope stays below 1 at every lead (0.68 to 0.81).

### Sensitivity: persistence as it was known at issue time (as stated), and a correction to its reading

The stated sensitivity ran as written. On the rows where the shadow logged `spilling_at_issue` (same day
2,872 rows, 21–23 Oct; in advance 2,855 rows, 22–23 Oct; one wet spell, so point estimates only):

| Leads | Forecast Brier | Logged status at issue (spilling now) | #338's rebuilt "active" (now or within 48 h) | Skill vs logged | Skill vs rebuilt active |
|---|---|---|---|---|---|
| Same day | 0.125 | 0.121 | 0.098 | −0.04 | −0.28 |
| In advance | 0.142 | 0.163 | 0.143 | 0.13 | 0.01 |

**These two columns are two different prediction rules**, not two reconstructions of one rule. The
shadow logs `status == 1` at issue (`model/live_status.py` line 217): spilling now. #338's "active" also
counts a spill that ended in the `RECENT_SPILL_HOURS` (48 h) before the issue. The rows are the same
(2,872 and 2,855 in both). So the gap between them cannot be put down to backdated starts. A first draft
of this section did that; it is withdrawn (correction 3 below).

### Exploratory: the same rule, rebuilt and as logged

Added after the run and not part of the stated test. `scripts/persistence_like_for_like.py`, on the same
fixed record (hashes checked), output `docs/CALIBRATION-CHECK-2026-10-persistence.json`, run at 22:40 UTC.
It holds the rule fixed, spilling now, and compares #338's rebuilt `spilling_now` with the shadow's
logged `spilling_at_issue`. Exactly the same 5,727 rows (logged, status known to the rebuild, issue time
matched), each turned into a chance the same way (`fit_two_sided`, by lead, on those rows):

| Leads | Rows | Forecast Brier | Spilling now, logged | Spilling now, rebuilt | Skill vs logged | Skill vs rebuilt |
|---|---|---|---|---|---|---|
| Same day | 2,872 | 0.1251 | 0.1207 | 0.1215 | −0.036 | −0.030 |
| In advance | 2,855 | 0.1419 | 0.1631 | 0.1628 | 0.130 | 0.128 |

The two flag different rows: 43 both, 36 logged only, 50 rebuilt only, 5,598 neither. These are #338's
cross-check counts, now on the full shadow window. Scored here, the differences nearly cancel: the
rebuilt "spilling now" scores within 0.001 of the logged one. In this window, then, the hindsight in the
rebuild moves a spilling-now reference very little. The large gap in the first table comes from the rule:
"spilling now or in the last 48 hours" predicts better than "spilling now". So #338's reference is a
stronger rule than a swimmer's "is it spilling now?", and that is the main reason it is hard to beat.
#338's own word for the hindsight bias, "slightly", is consistent with this. The size of that bias for
the 48-hour rule itself is not measured here: the shadow logs no 48-hour status to compare with. This is
one wet window of a few days, with references fitted on the same rows.

### Corrections to the stated text, made after the run

Kept visible, not rewritten into the statement above:

1. **The "too timid" reading is withdrawn.** The statement says a slope interval above 1 "contradicts
   overprediction (too timid)". That is wrong. With a free intercept, a slope above 1 does not say the
   high chances are too low. Example from review: α = −2 and b = 1.5 give observed rates 0.005, 0.119
   and 0.785 for forecasts 0.1, 0.5 and 0.9: all below the forecast, though b is above 1. Calibration in
   the large (O/E, the intercept a) and the slope are separate dimensions. Any claim about over- or
   underprediction at high chances rests on the reliability bands above, as rule 2 already requires.
   This reading fired in no stratum, so no judgement changes. The script's label is left as run.
2. **Nine named companies, not eight.** The statement says "the eight named companies". The file has
   nine: Anglian, Northumbrian, Severn Trent, South West, Southern, Thames, United Utilities, Wessex and
   Yorkshire. All nine were analysed, as the strata rule intends. Northumbrian Water has 16 spill
   overflow-days, so it is reported, not judged.
3. **The sensitivity's first reading is withdrawn.** A first draft of the results, written before review
   and never published, said the sensitivity showed backdated starts flatter #338's persistence by more
   than #338 stated. That held the rule fixed only in name: the logged status is spilling now, the rebuilt
   one is spilling now or within 48 h. The section above labels the two as different rules, and an
   exploratory like-for-like comparison, marked as added after the run, replaces the causal claim.
4. **The statement's date was corrected before any result existed.** The first commit said "25 October
   2026 (UTC)". It was amended to "24 October 2026 at about 22:30 UTC" before the script was written, and
   then pushed (commit `c745c48`).

### Limits

- Four blocks, one of four days holding 54% of the spill overflow-days. The intervals are crude.
- Only scored rows. The 23,841 unscored cells are not imputed, so these rates describe the conditions
  under which scoring succeeded.
- Leads repeat the same overflow-days. The lead-group intervals account for this through the shared
  draws. The per-lead rows are not independent evidence and are not combined.
- October is outside the May–September season the spill model's month factors were fitted for. Whether
  the same bias holds in summer is not tested.
- A diagnostic only: nothing is refitted, and no correction is made or scored. Any recalibration needs
  its own stated test on data it was not fitted to.
