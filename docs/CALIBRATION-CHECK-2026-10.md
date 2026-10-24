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
