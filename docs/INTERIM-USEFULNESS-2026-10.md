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
