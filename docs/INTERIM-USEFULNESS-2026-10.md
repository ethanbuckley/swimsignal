# Interim usefulness read, October 2026

Does the live spill forecast beat simple rules a swimmer or an organiser could use without it? This
is an interim read of the live record from 29 Sep 2026, after the outside review of 24 Oct and the
winter plan of 25 Oct (version 2), which made usefulness the central question. It decides what
SwimSignal may promise swimmers and organisations this winter. It changes no model, page,
pre-registration or live score.

The Accuracy page compares the forecast with one reference only: each overflow's long-run rate. On
24 Oct (verification.json built 20:37 BST, target days 29 Sep to 23 Oct) its Brier skill against that
rate was 0.21 overall. Two simpler references were never scored: "it is spilling now, or spilled in
the last two days" and "it rained a lot in the last two days". This read adds both.

PR #262 (the live-status shadow, window 25 Oct to 21 Nov) tests live status as a model *input*.
This read uses live status as a *rival forecast*. They are different questions.

## Stated before the run

Stated on 24 Oct 2026, on branch `docs/interim-usefulness-2026-10` from main at `9be5601`. This
section is committed before any score was computed. Nothing in it changes after the results,
except a plain bug fix in the script, which would be listed under the results with what it changed.

### Data

- **Scored forecasts.** The published `data/verification_live.csv` (verification.json →
  `live.scored_csv`), fetched from swimsignal.co.uk on 24 Oct 2026 at 23:09 BST, from the build of
  20:37 BST. 117,324 rows, target days 29 Sep to 23 Oct 2026. SHA-256 `434f910a…6eb598`. The forecast
  is `forecast_calibrated`. A row is one overflow, one target day, one lead.
- **Forecast log and poll files.** The `state` release's assets of 24 Oct 2026 09:51 UTC:
  `dipcast.duckdb` (SHA-256 `8544507f…13aed4e7`), `live_history.parquet` (`b38bb6a8…61349052`) and
  `live_coverage.parquet` (`75cdd298…f5542676`). Downloaded, read only. No pipeline run, no
  Open-Meteo call, no workflow.
- **Issue time.** Each scored row's `issued_at`. The row is joined to its forecast-log row by
  overflow, target day, lead and issue time, as `forecast_log.select_decision_forecasts` picks it
  (latest issued by 08:00 local on the issue day, live-fed, rain present).

### References

Each is a chance per row. Each is scored on the same rows as the forecast.

1. **Long-run rate.** The `climatology` column, as the Accuracy page uses it.
2. **Persistence.** The overflow is *active* at issue time T if its poll record shows it spilling
   at T or spilling at any moment in the `RECENT_SPILL_HOURS` (48 h) before T. Spill intervals come
   from `live_history.parquet` by `model.live_status.poll_events` (the scorer's own rule), merged per
   overflow. To avoid hindsight, only spill that had started by the overflow's last current reading
   at or before T counts. The status is *known* when `live_coverage.parquet` holds current readings
   over the 48 h before T with no stretch longer than 8 h (the scorer's `MAX_GAP_H`), the stretch
   from the last reading to T included. Rows whose status is not known have no persistence chance.
   An active row gets one fixed chance, a quiet row another. Each chance is the observed spill rate
   of that group over the whole window, fitted separately at each lead, pooled over companies.
   **This flatters the reference**: it is fitted on the same rows it is scored on.
3. **Rain rule.** The 48 h rain at the overflow's rain cell is the logged `rain_mm` for the target
   day plus the logged `rain_mm` for the day before. For lead 1 to 4 the day before comes from the
   same forecast (the same issue time). For lead 0 it comes from the latest logged forecast of that
   overflow for the day before, issued before T. This is forecast rain, what the forecast itself
   used, not rain as it fell. The rule is wet above 10 mm, and separately above 5 mm, as in
   verification.json → `holdout` (`model.verify.rain_rule`). Wet and dry rows each get the observed
   spill rate of their group over the whole window, fitted at each lead, pooled over companies. **This
   also flatters the reference.** A row missing either day's rain has no rain-rule chance.

The **best reference** in a cell is, in each bootstrap draw and in the point estimate, the one of the
four (long-run rate, persistence, rain over 10 mm, rain over 5 mm) with the lowest Brier score on
that cell's rows. Taking the best of four per draw is stricter on the forecast than fixing one.

### Rows

- **Common rows**: scored rows that have all four reference chances. Every comparison against
  persistence, the rain rule or the best reference uses only these rows.
- The long-run-rate skill is also reported on all scored rows, to tie back to the Accuracy page.
- Coverage is reported: the share of scored rows with a known status, with both days' rain, and
  in the common rows, overall and by company.

### Scores

- Brier skill against reference R: 1 − Brier(forecast) ÷ Brier(R), on the same rows.
- AUC: `scripts/evaluate_2027.py`'s `auc` (Mann-Whitney, ties count half), for the forecast and for
  each reference.
- Cells: each company, and all companies together; lead 0, leads 1 to 4 pooled, and each lead 0 to 4.
- Counts: rows, spill rows, and distinct overflow-days with a spill, so readers see that leads repeat
  the same event.

### Uncertainty

- The pre-registration's two-way bootstrap (`docs/PREREGISTRATION-2027.md` §10), reusing
  `scripts/evaluate_2027.py`'s `Bootstrap`: overflows and 7-day blocks resampled together, a row
  counted (times its overflow was drawn) × (times its block was drawn). All leads of an overflow-day
  share the draws. 2,000 draws from `default_rng(20270501)`. Blocks are 7 days from 29 Sep 2026:
  29 Sep–5 Oct, 6–12 Oct, 13–19 Oct and 20–23 Oct (4 days).
- 95% intervals: 2.5th and 97.5th percentiles. A draw with no spill, or none of a cell's rows, has
  no skill or AUC; it is left out and counted.
- The fitted chances of references 2 and 3 are fixed at their whole-window values in every draw.
- *Expected now:* intervals will be wide. Four blocks is a crude cluster count, and the wet spell
  from 19 Oct may carry most of the spills. A draw that leaves out the last block loses most events.

### The promise rule, fixed now

For each company, at **leads 1 to 4 pooled**, on the common rows:

- If the **lower 95% bound** of the Brier skill against the **best reference** is above 0, the
  forecast may be described as "warns in advance in [company]'s area", with the dated figure.
- Otherwise only: "shows what the upstream monitors say now; the forecast is still being tested".

A company with no spill in its common rows at leads 1 to 4 gets the second wording. The rule is
applied once, to this run. It does not bind the 2027 evaluation.

### Script

`scripts/interim_usefulness.py`, committed with the results. It prints a JSON summary, committed as
`docs/INTERIM-USEFULNESS-2026-10.json`.

## Results

Run on 24 Oct 2026 with `scripts/interim_usefulness.py` at this branch's results commit. Output:
`docs/INTERIM-USEFULNESS-2026-10.json`. 2,000 draws, seed 20270501, 1,145 overflows, 4 blocks.

### Verdict

**No company passes the promise rule.** For every company, the lower 95% bound of skill against
the best reference at leads 1 to 4 is at or below 0. So for every company, this winter, the wording
is: "shows what the upstream monitors say now; the forecast is still being tested".

| Company | Skill against the best reference, leads 1–4 (95% interval) | Best reference | Wording allowed |
|---|---|---|---|
| All companies | 0.07 (−0.05 to 0.12) | rain > 10 mm | still being tested |
| Anglian Water | −0.005 (−0.08 to 0.06) | persistence | still being tested |
| Northumbrian Water | 0.13 (−0.11 to 0.37) | rain > 5 mm | still being tested |
| Severn Trent Water | 0.06 (−0.15 to 0.12) | rain > 5 mm | still being tested |
| South West Water | 0.20 (−0.94 to 0.37) | long-run rate | still being tested |
| Southern Water | 0.40 (−0.23 to 0.50) | rain > 10 mm | still being tested |
| Thames Water | −0.10 (−0.47 to 0.02) | rain > 10 mm | still being tested |
| United Utilities | 0.05 (−0.17 to 0.14) | rain > 5 mm | still being tested |
| Wessex Water | 0.11 (−0.53 to 0.19) | rain > 10 mm | still being tested |
| Yorkshire Water | 0.07 (−0.04 to 0.18) | rain > 5 mm | still being tested |

What the numbers say, checked:

- Against the long-run rate, the forecast has skill: 0.21 same day and 0.19 in advance, both
  intervals above 0. On all scored rows it is 0.21 and 0.20, which matches the Accuracy page.
- Against the simple rules the margin is small. In advance, all companies together: 0.09 against
  persistence, 0.07 against rain over 10 mm, 0.08 against rain over 5 mm. Every interval crosses 0.
- On the same day, persistence beats the forecast: skill −0.05 (−0.19 to 0.17). In Thames Water's
  area the forecast is worse than persistence (−0.46, −1.03 to −0.07) and worse than both rain
  rules on the same day. In Wessex Water's area it is worse than the best reference on the same
  day (−0.30, −0.56 to −0.08).
- In advance, two companies have a point estimate against the best reference below 0: Thames Water
  (−0.10) and Anglian Water (−0.005).
- The forecast ranks better than every reference. All companies: AUC 0.88 same day and 0.84 in
  advance, against 0.61 to 0.77 for the references. The same holds in every company cell except
  Southern Water at leads 3 and 4 taken alone, which hold very few spills on the common rows.
- One wet spell carries the result. The last block (20–23 Oct, 4 days) holds 599 of the 1,106
  overflow-days with a spill, 54%. A bootstrap over 4 blocks is crude.

What the numbers suggest, inferred and not tested here:

- The forecast ranks well but its chances run too high in some areas, which costs it on the Brier
  score. Same day, all companies: mean forecast 0.067 against a spill rate of 0.050. Thames Water:
  0.062 against 0.024. United Utilities: 0.133 against 0.089. This would explain a forecast that
  wins on AUC and loses to persistence on Brier. A calibration check would settle it; none was run.
- The references are flattered (fitted on the same rows) and the forecast is not. Fitted from
  earlier data, persistence and the rain rule would likely score worse, and the forecast's skill
  against them would rise. So the verdict leans against the forecast. By how much was not measured.

### A bug fixed after the statement

The first version of the script placed each poll reading at the middle of its half-hour slot in
`live_coverage.parquet` (`live_status.reading_times`). The poll a build makes just before it issues
(for example 05:08 UTC for a 05:10 issue) then fell after the issue time. It was dropped, so spills
that began since the previous poll did not count. The cross-check against the shadow found it: on
the rows from 21 Oct, the shadow logged 79 overflows spilling at issue and the rebuild found 9.

The fix reads the real poll times from `poll_log.parquet` and keeps a poll for an overflow only where
its coverage slot shows a current reading. It changed the rows with a known status from 91,454 to
91,444, and the lead-0 rows counted active from 1,237 to 1,382. A 20-draw trial of the first version
had printed some skill figures before the fix; they are not used. The fix adds a fourth input file,
`poll_log.parquet` from the same release (its hash is in the JSON). The cross-check's output was also
extended to count active rows. No other change was made after the statement.

After the fix, all 79 shadow-spilling rows are active in the rebuild. 43 of them are also spilling
at the issue time in the rebuild; the other 36 had stopped before the issue time, by the stop times
the companies published later (one checked by hand: AWS01327 stopped at 04:17 UTC on 23 Oct, but the
05:08 poll still showed it discharging). In the other direction, 50 rows are spilling at issue in the rebuild but
not in the shadow. *Inferred:* these are spill starts published after the issue time and dated
back, so the rebuild knew a little more than a swimmer could have. This flatters persistence
slightly (50 of 812 active rows in that check).

### Skill by company

Brier skill, 1 − Brier ÷ reference Brier, with the 95% interval, on the common rows. 0 means no
better than the reference. "Best of four" takes, in each draw, whichever reference scored best.

| Company | Leads | Long-run rate | Persistence | Rain > 10 mm | Rain > 5 mm | Best of four | Best is |
|---|---|---|---|---|---|---|---|
| All companies | 0 | 0.21 (0.08 to 0.44) | −0.05 (−0.19 to 0.17) | 0.07 (0.01 to 0.14) | 0.08 (0.02 to 0.14) | −0.05 (−0.19 to 0.12) | persistence |
| All companies | 1–4 | 0.19 (0.11 to 0.40) | 0.09 (−0.04 to 0.17) | 0.07 (−0.04 to 0.12) | 0.08 (−0.03 to 0.14) | 0.07 (−0.05 to 0.12) | rain > 10 mm |
| Anglian Water | 0 | 0.10 (−0.00 to 0.33) | −0.07 (−0.26 to 0.18) | 0.02 (−0.06 to 0.11) | 0.01 (−0.07 to 0.10) | −0.07 (−0.26 to 0.04) | persistence |
| Anglian Water | 1–4 | 0.10 (0.01 to 0.38) | −0.00 (−0.08 to 0.14) | 0.01 (−0.04 to 0.07) | 0.02 (−0.03 to 0.08) | −0.00 (−0.08 to 0.06) | persistence |
| Northumbrian Water | 0 | 0.26 (−0.02 to 0.57) | 0.20 (−0.33 to 0.57) | 0.14 (−0.18 to 0.51) | 0.16 (−0.17 to 0.51) | 0.14 (−0.36 to 0.48) | rain > 10 mm |
| Northumbrian Water | 1–4 | 0.20 (−0.01 to 0.45) | 0.16 (−0.10 to 0.44) | 0.13 (−0.03 to 0.39) | 0.13 (−0.05 to 0.40) | 0.13 (−0.11 to 0.37) | rain > 5 mm |
| Severn Trent Water | 0 | 0.24 (0.07 to 0.81) | −0.05 (−0.38 to 0.60) | 0.01 (−0.43 to 0.15) | 0.05 (−0.29 to 0.20) | −0.05 (−0.48 to 0.11) | persistence |
| Severn Trent Water | 1–4 | 0.22 (0.07 to 0.73) | 0.08 (−0.10 to 0.37) | 0.06 (−0.11 to 0.13) | 0.06 (−0.10 to 0.13) | 0.06 (−0.15 to 0.12) | rain > 5 mm |
| South West Water | 0 | 0.36 (−0.12 to 0.61) | 0.18 (−1.20 to 0.54) | 0.35 (−0.51 to 0.60) | 0.38 (−0.26 to 0.63) | 0.18 (−1.32 to 0.54) | persistence |
| South West Water | 1–4 | 0.20 (−0.18 to 0.42) | 0.22 (−0.94 to 0.48) | 0.23 (−0.65 to 0.42) | 0.25 (−0.59 to 0.45) | 0.20 (−0.94 to 0.37) | long-run rate |
| Southern Water | 0 | 0.31 (0.20 to 0.72) | 0.08 (−0.67 to 0.26) | 0.30 (0.00 to 0.38) | 0.30 (−0.14 to 0.38) | 0.08 (−0.67 to 0.20) | persistence |
| Southern Water | 1–4 | 0.46 (0.34 to 0.77) | 0.49 (−0.21 to 0.57) | 0.40 (−0.10 to 0.50) | 0.46 (0.25 to 0.58) | 0.40 (−0.23 to 0.50) | rain > 10 mm |
| Thames Water | 0 | 0.13 (−0.29 to 0.79) | −0.46 (−1.03 to −0.07) | −0.28 (−0.56 to −0.09) | −0.30 (−0.63 to −0.07) | −0.46 (−1.03 to −0.13) | persistence |
| Thames Water | 1–4 | 0.22 (−0.07 to 0.74) | −0.08 (−0.33 to 0.07) | −0.10 (−0.46 to 0.02) | −0.08 (−0.26 to 0.04) | −0.10 (−0.47 to 0.02) | rain > 10 mm |
| United Utilities | 0 | 0.18 (−0.11 to 0.34) | 0.10 (−0.38 to 0.31) | 0.13 (−0.25 to 0.31) | 0.11 (−0.26 to 0.29) | 0.10 (−0.38 to 0.26) | persistence |
| United Utilities | 1–4 | 0.11 (−0.04 to 0.25) | 0.06 (−0.14 to 0.18) | 0.05 (−0.15 to 0.17) | 0.05 (−0.15 to 0.17) | 0.05 (−0.17 to 0.14) | rain > 5 mm |
| Wessex Water | 0 | 0.28 (0.08 to 0.83) | −0.30 (−0.52 to 0.27) | 0.05 (−0.45 to 0.15) | 0.08 (−0.21 to 0.18) | −0.30 (−0.56 to −0.08) | persistence |
| Wessex Water | 1–4 | 0.29 (0.13 to 0.84) | 0.17 (−0.19 to 0.40) | 0.11 (−0.53 to 0.19) | 0.15 (−0.15 to 0.27) | 0.11 (−0.53 to 0.19) | rain > 10 mm |
| Yorkshire Water | 0 | 0.22 (0.12 to 0.42) | 0.08 (−0.13 to 0.19) | 0.12 (0.02 to 0.23) | 0.11 (0.00 to 0.24) | 0.08 (−0.13 to 0.18) | persistence |
| Yorkshire Water | 1–4 | 0.16 (0.08 to 0.32) | 0.09 (−0.02 to 0.22) | 0.07 (−0.02 to 0.18) | 0.07 (−0.04 to 0.19) | 0.07 (−0.04 to 0.18) | rain > 5 mm |

AUC of the forecast (95% interval) and of each reference, same rows. 0.5 is chance, 1 is perfect.
The references take only two values, so many of their pairs tie.

| Company | Leads | Forecast | Long-run rate | Persistence | Rain > 10 mm | Rain > 5 mm |
|---|---|---|---:|---:|---:|---:|
| All companies | 0 | 0.88 (0.79 to 0.91) | 0.70 | 0.74 | 0.75 | 0.77 |
| All companies | 1–4 | 0.84 (0.76 to 0.89) | 0.70 | 0.61 | 0.74 | 0.74 |
| Anglian Water | 0 | 0.77 (0.58 to 0.87) | 0.64 | 0.71 | 0.68 | 0.70 |
| Anglian Water | 1–4 | 0.76 (0.59 to 0.85) | 0.64 | 0.64 | 0.68 | 0.68 |
| Northumbrian Water | 0 | 0.75 (0.42 to 0.99) | 0.60 | 0.63 | 0.68 | 0.66 |
| Northumbrian Water | 1–4 | 0.79 (0.60 to 0.97) | 0.63 | 0.56 | 0.63 | 0.67 |
| Severn Trent Water | 0 | 0.91 (0.75 to 0.96) | 0.68 | 0.76 | 0.82 | 0.79 |
| Severn Trent Water | 1–4 | 0.88 (0.73 to 0.92) | 0.68 | 0.62 | 0.72 | 0.78 |
| South West Water | 0 | 0.87 (0.56 to 0.97) | 0.67 | 0.78 | 0.79 | 0.68 |
| South West Water | 1–4 | 0.82 (0.56 to 0.90) | 0.67 | 0.66 | 0.76 | 0.69 |
| Southern Water | 0 | 0.90 (0.82 to 0.94) | 0.72 | 0.79 | 0.68 | 0.71 |
| Southern Water | 1–4 | 0.95 (0.38 to 0.97) | 0.72 | 0.32 | 0.86 | 0.66 |
| Thames Water | 0 | 0.87 (0.52 to 0.93) | 0.63 | 0.67 | 0.81 | 0.80 |
| Thames Water | 1–4 | 0.86 (0.51 to 0.92) | 0.63 | 0.58 | 0.80 | 0.77 |
| United Utilities | 0 | 0.88 (0.85 to 0.92) | 0.76 | 0.68 | 0.67 | 0.71 |
| United Utilities | 1–4 | 0.85 (0.80 to 0.90) | 0.80 | 0.61 | 0.67 | 0.68 |
| Wessex Water | 0 | 0.93 (0.81 to 0.95) | 0.74 | 0.85 | 0.88 | 0.86 |
| Wessex Water | 1–4 | 0.91 (0.70 to 0.92) | 0.75 | 0.62 | 0.86 | 0.81 |
| Yorkshire Water | 0 | 0.83 (0.72 to 0.94) | 0.62 | 0.67 | 0.66 | 0.71 |
| Yorkshire Water | 1–4 | 0.76 (0.64 to 0.89) | 0.61 | 0.57 | 0.65 | 0.70 |

### Each lead, all companies

| Lead | Rows | Spill rows | Long-run rate | Persistence | Rain > 10 mm | Rain > 5 mm | Best of four | Best is | AUC |
|---|---:|---:|---|---|---|---|---|---|---|
| 0 | 20,459 | 1,014 | 0.21 (0.08 to 0.44) | −0.05 (−0.19 to 0.17) | 0.07 (0.01 to 0.14) | 0.08 (0.02 to 0.14) | −0.05 (−0.19 to 0.12) | persistence | 0.88 (0.79 to 0.91) |
| 1–4 | 70,932 | 3,626 | 0.19 (0.11 to 0.40) | 0.09 (−0.04 to 0.17) | 0.07 (−0.04 to 0.12) | 0.08 (−0.03 to 0.14) | 0.07 (−0.05 to 0.12) | rain > 10 mm | 0.84 (0.76 to 0.89) |
| 1 | 19,252 | 986 | 0.20 (0.08 to 0.43) | 0.07 (−0.02 to 0.21) | 0.06 (−0.02 to 0.13) | 0.08 (0.00 to 0.15) | 0.06 (−0.03 to 0.13) | rain > 10 mm | 0.86 (0.76 to 0.92) |
| 2 | 18,277 | 928 | 0.23 (0.15 to 0.40) | 0.12 (−0.03 to 0.20) | 0.09 (−0.08 to 0.16) | 0.11 (−0.06 to 0.18) | 0.09 (−0.08 to 0.16) | rain > 10 mm | 0.87 (0.79 to 0.91) |
| 3 | 17,319 | 860 | 0.18 (0.10 to 0.39) | 0.08 (−0.10 to 0.18) | 0.05 (−0.09 to 0.11) | 0.06 (−0.11 to 0.13) | 0.05 (−0.12 to 0.11) | rain > 10 mm | 0.84 (0.74 to 0.88) |
| 4 | 16,084 | 852 | 0.17 (0.10 to 0.34) | 0.08 (−0.08 to 0.16) | 0.07 (−0.04 to 0.13) | 0.07 (−0.04 to 0.12) | 0.07 (−0.08 to 0.12) | rain > 5 mm | 0.80 (0.70 to 0.84) |

### Counts: leads repeat the same event

Lead 0 has one row per overflow-day, so spill rows equal overflow-days with a spill. Leads 1 to 4
score the same overflow-day up to four times: 3,626 spill rows come from 1,009 overflow-days.


| Company | Leads | Rows (common) | Spill rows | Spill overflow-days | Spill rate | Mean forecast |
|---|---|---:|---:|---:|---:|---:|
| All companies | 0 | 20,459 | 1,014 | 1,014 | 0.050 | 0.067 |
| All companies | 1–4 | 70,932 | 3,626 | 1,009 | 0.051 | 0.063 |
| Anglian Water | 0 | 2,958 | 107 | 107 | 0.036 | 0.034 |
| Anglian Water | 1–4 | 10,414 | 409 | 105 | 0.039 | 0.030 |
| Northumbrian Water | 0 | 245 | 12 | 12 | 0.049 | 0.047 |
| Northumbrian Water | 1–4 | 847 | 48 | 16 | 0.057 | 0.036 |
| Severn Trent Water | 0 | 2,208 | 77 | 77 | 0.035 | 0.048 |
| Severn Trent Water | 1–4 | 7,741 | 308 | 79 | 0.040 | 0.046 |
| South West Water | 0 | 426 | 61 | 61 | 0.143 | 0.142 |
| South West Water | 1–4 | 1,577 | 242 | 62 | 0.153 | 0.129 |
| Southern Water | 0 | 575 | 66 | 66 | 0.115 | 0.132 |
| Southern Water | 1–4 | 1,155 | 107 | 59 | 0.093 | 0.106 |
| Thames Water | 0 | 3,863 | 93 | 93 | 0.024 | 0.062 |
| Thames Water | 1–4 | 13,553 | 371 | 94 | 0.027 | 0.062 |
| United Utilities | 0 | 2,632 | 235 | 235 | 0.089 | 0.133 |
| United Utilities | 1–4 | 9,120 | 731 | 232 | 0.080 | 0.122 |
| Wessex Water | 0 | 5,090 | 196 | 196 | 0.039 | 0.059 |
| Wessex Water | 1–4 | 17,881 | 768 | 195 | 0.043 | 0.059 |
| Yorkshire Water | 0 | 2,448 | 155 | 155 | 0.063 | 0.051 |
| Yorkshire Water | 1–4 | 8,598 | 603 | 156 | 0.070 | 0.055 |


By 7-day block, all scored rows (not only the common ones):

| Block | Rows | Spill rows | Overflow-days with a spill |
|---|---:|---:|---:|
| 29 Sep – 5 Oct | 32,895 | 745 | 149 |
| 6 – 12 Oct | 25,379 | 711 | 146 |
| 13 – 19 Oct | 36,925 | 1,053 | 212 |
| 20 – 23 Oct | 22,125 | 2,995 | 599 |

### Coverage

Every scored row joined its forecast-log row with the same issue time (117,324 of 117,324). The
common rows are those with a known status and both days' rain.

| Company | Scored rows | Status known | Rain both days | Common rows | Common share |
|---|---:|---:|---:|---:|---:|
| All companies | 117,324 | 91,444 | 107,650 | 91,391 | 78% |
| Anglian Water | 16,004 | 13,392 | 14,769 | 13,372 | 84% |
| Northumbrian Water | 1,398 | 1,092 | 1,318 | 1,092 | 78% |
| Severn Trent Water | 12,055 | 9,955 | 11,058 | 9,949 | 83% |
| South West Water | 2,345 | 2,003 | 2,345 | 2,003 | 85% |
| Southern Water | 8,635 | 1,730 | 7,645 | 1,730 | 20% |
| Thames Water | 20,863 | 17,426 | 19,222 | 17,416 | 83% |
| United Utilities | 14,395 | 11,754 | 13,284 | 11,752 | 82% |
| Wessex Water | 28,104 | 22,985 | 25,658 | 22,971 | 82% |
| Yorkshire Water | 13,445 | 11,047 | 12,281 | 11,046 | 82% |

- Southern Water has a known status on only 20% of its rows, so its comparison rests on 1,730
  rows and 158 of the 2,000 draws had no spill in its leads 1–4 cell. The shadow test's doc
  (`docs/LIVE-STATUS-SHADOW-TEST-2026-10.md`) gives the likely reason: Southern stamps a record only
  when it changes, so in a quiet spell the coverage file counts its polls as stale. Not re-checked here.
- About 8% of rows lack one of the two days' rain. Why was not checked.

### Long-run-rate skill on all scored rows

The tie to the Accuracy page: the forecast against the long-run rate on every scored row, with no
reference coverage required.


| Company | Leads | Rows | Skill | 95% interval | AUC |
|---|---|---:|---:|---|---:|
| All companies | 0 | 23,700 | 0.21 | 0.08 to 0.40 | 0.87 |
| All companies | 1–4 | 93,624 | 0.20 | 0.12 to 0.34 | 0.84 |
| Anglian Water | 0 | 3,266 | 0.09 | −0.01 to 0.27 | 0.74 |
| Anglian Water | 1–4 | 12,738 | 0.11 | 0.01 to 0.31 | 0.74 |
| Northumbrian Water | 0 | 291 | 0.23 | −0.01 to 0.53 | 0.79 |
| Northumbrian Water | 1–4 | 1,107 | 0.16 | −0.02 to 0.40 | 0.76 |
| Severn Trent Water | 0 | 2,431 | 0.20 | 0.07 to 0.47 | 0.90 |
| Severn Trent Water | 1–4 | 9,624 | 0.20 | 0.07 to 0.48 | 0.86 |
| South West Water | 0 | 493 | 0.37 | −0.07 to 0.63 | 0.86 |
| South West Water | 1–4 | 1,852 | 0.22 | −0.12 to 0.48 | 0.81 |
| Southern Water | 0 | 1,733 | 0.28 | −0.07 to 0.57 | 0.91 |
| Southern Water | 1–4 | 6,902 | 0.30 | 0.16 to 0.47 | 0.91 |
| Thames Water | 0 | 4,228 | 0.16 | −0.28 to 0.79 | 0.87 |
| Thames Water | 1–4 | 16,635 | 0.27 | −0.04 to 0.78 | 0.87 |
| United Utilities | 0 | 2,917 | 0.19 | −0.09 to 0.34 | 0.88 |
| United Utilities | 1–4 | 11,478 | 0.11 | −0.02 to 0.21 | 0.83 |
| Wessex Water | 0 | 5,634 | 0.28 | 0.08 to 0.76 | 0.93 |
| Wessex Water | 1–4 | 22,470 | 0.30 | 0.14 to 0.73 | 0.90 |
| Yorkshire Water | 0 | 2,691 | 0.24 | 0.12 to 0.47 | 0.84 |
| Yorkshire Water | 1–4 | 10,754 | 0.19 | 0.09 to 0.39 | 0.77 |


### The fitted chances

Fitted on the whole window, per lead, all companies pooled. "On" is active, or wet.

| Lead | Persistence on | Persistence off | Rain > 10 mm on | off | Rain > 5 mm on | off |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 0.389 (1,382) | 0.025 (19,130) | 0.148 (5,008) | 0.020 (18,635) | 0.118 (7,788) | 0.012 (15,855) |
| 1 | 0.270 (1,118) | 0.038 (18,134) | 0.147 (5,149) | 0.019 (17,474) | 0.105 (8,752) | 0.013 (13,871) |
| 2 | 0.223 (1,019) | 0.041 (17,258) | 0.150 (4,972) | 0.018 (16,552) | 0.102 (9,071) | 0.010 (12,453) |
| 3 | 0.177 (960) | 0.042 (16,359) | 0.152 (4,138) | 0.025 (16,298) | 0.103 (8,406) | 0.013 (12,030) |
| 4 | 0.171 (873) | 0.046 (15,211) | 0.141 (3,126) | 0.032 (16,298) | 0.106 (6,408) | 0.022 (13,016) |

Row counts in brackets are the rows each chance was fitted on.

### Limits

- Four 7-day blocks, the last of 4 days, and one wet spell. The intervals are wide, and a few more
  wet weeks could move every figure. This is an interim read, not a result for 2027.
- Both simple references are fitted on the rows they are scored on. That flatters them.
- The rebuilt status uses event times the feeds published later, which flatters persistence a little.
- The rain rule uses forecast rain from the log, not rain as it fell. The 2025 holdout used ERA5-Land.
- The forecast changed during the window (version stamps in verification.json); the read pools
  versions, as the Accuracy page does.
- PR #262's shadow tests live status as a model input, on 25 Oct to 21 Nov. This read did not use
  or change it.

## Draft amendment for `docs/PREREGISTRATION-2027.md` §17

Not filed. Ethan decides whether to add it before 1 May 2027. The wording below would go under §17
as written, with its date set to the day it is filed.

> ### Amendment 2, [date filed]: persistence and a rain rule as secondary references
>
> **Why.** Section 7 compares the spill forecasts with climatology only. A swimmer or an organiser
> can do without SwimSignal by looking at the overflow map ("it is spilling, or spilled in the last
> two days") or at the rain. An interim read of the live record from 29 September to 23 October 2026
> (`docs/INTERIM-USEFULNESS-2026-10.md`) found skill against climatology of about 0.2, but skill
> against these simpler rules near 0.07 in advance, with every interval crossing 0, and persistence
> better than the forecast on the same day. This amendment adds both rules as **secondary**
> references. Climatology (section 7) stays primary, and the four primary outcomes (section 8) are
> unchanged.
>
> **Reference P: persistence.** For each scored row, the overflow is *active* when the poll record
> shows it spilling at the forecast's issue time, or at any moment in the `RECENT_SPILL_HOURS` (48 h)
> before it, counting only spill that had started by the overflow's last current reading at or
> before the issue time. Spill intervals are read from `live_history.parquet` by
> `model.live_status.poll_events`; current readings are the polls in `poll_log.parquet` whose
> half-hour slot in `live_coverage.parquet` shows a current reading of the overflow. The status is
> *known* when the readings cover the 48 h before the issue with no stretch over 8 h (the scorer's
> `MAX_GAP_H`), the stretch to the issue time included. Where the shadow's logged
> `spilling_at_issue` exists for the row, it is used for "spilling at the issue time" in place of the
> rebuilt one.
>
> **Reference R: the rain rule.** The logged `rain_mm` for the target day plus that for the day before
> (from the same issue for leads 1 to 4; for lead 0 from the latest logged forecast of the day
> before, issued before it), above 10 mm. The 5 mm rule is reported beside it.
>
> **Their chances.** Each rule gives one chance on each side, at each lead, all companies pooled,
> fitted on every scored live row from 29 September 2026 to 30 April 2027 and frozen on 1 May 2027 in
> `data/eval2027/simple_references.json`, with its hash in section 13. The same rules refitted on
> the 2027 season itself are reported beside them, labelled as flattering the references.
>
> **Rows.** P and R are scored only on rows where both exist; coverage is reported by company and
> by 7-day block, as in section 9. The skill against climatology is also reported on these rows.
>
> **What is reported.** For each stratum of section 7: skill against P, against R (10 mm and 5 mm)
> and against the best of climatology, P and R in each draw, with section 10's intervals and the
> AUC of each. None of these is a primary outcome and none changes section 8's rule.
>
> **Inputs.** The evaluation reads the forecast log (`dipcast.duckdb`) and the three poll files from
> the `state` release as archived on 1 October 2027, with their hashes recorded in the results. The
> rebuild of the status from these files is `scripts/interim_usefulness.py`'s, moved into
> `scripts/evaluate_2027.py` before the freeze and tested there.
