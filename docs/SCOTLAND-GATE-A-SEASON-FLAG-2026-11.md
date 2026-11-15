# Gate A and Scottish Water's bathing-season-only flag, 13 November 2026

Found on 10 November during the [2021 backtest](SCOTLAND-2021-BACKTEST-2026-11.md) and not acted on then. This note
says what the flag touches in [Gate A](SCOTLAND-HINDCAST-2026-11.md), what a correction would change, and how it
should be stated. **No Gate A score was recomputed for it.** The counts below are of rows and recorded spill-days
only. Contains Scottish Water data licensed under the Open Government Licence v3.0.

## 1. What was found

Established, from the reported workbook's summary sheet (column "Bathing Season Only Reporting?") and the code:

- Four overflows are flagged as reporting only in the bathing season: CSO007005 (Cawdor, Piperhill) for 2019 to
  2022, and CSO005517 (Inverness, Sunnyside), CSO002405 and CSO005890 (both St Andrews) for 2021 to 2022. The
  non-reported workbook has no such column.
- Gate A's loader (`ingest/sw_history.py`, `scripts/hindcast_scotland.py`) does not read the flag. In a flagged year
  it treats the overflow as counted all year. So a day outside the season counts as "no spill" when nobody was
  reporting.
- Scotland's bathing season is taken here as 1 June to 15 September, 107 days.
- The flag is not strict. CSO005517 has 2 recorded spill-days outside the season in 2021, a flagged year.

## 2. What it touches, counted

Counted on 13 November from the main checkout's files, read only, hashes the same before and after
(`sw_events.parquet` 11ef6d05, `sw_covariates.parquet` 1ee52787, the reported workbook 98b40a03). Gate A's set G is
693 overflow-years and 253,140 overflow-days.

| Where | What is touched | How much |
|---|---|---|
| Labels, 2022 | Three flagged overflows are in G in 2022 (CSO005517, CSO005890, CSO007005). CSO002405 is "no data" in 2022 and is not. Their days outside the season count as no spill | 774 overflow-days, 0.31% of G. Their 9 recorded spill-days of 2022 are all inside the season |
| Covariates | A row's spill count comes from the year before. 2022 rows use 2021's season-only counts (4, 1 and 3 spills). 2023 rows use 2022's (long-term averages 4.5, 1.5 and 2.0; the same three recorded 32, 77 and 33 spills in 2023, reporting all year). CSO002405's 2024 row averages its season-only 2021 count (6) with 2023 (27) | 7 overflow-years of 693, 1.0% |
| Earlier-years baseline | The baseline is each overflow's own spill-day rate over its earlier years. For the four, those years include season-only ones, so the rate is too low | 14 overflow-years of 693, 2.0%: every G row of the four |
| The calibration map | Fitted on G's rows of 2022 to 2024, these included | 10 of its overflow-years; 774 of its 168,095 rows carry a doubtful label |
| The 2021 backtest | Three of the four are in its set | Already reported both ways: 0.280 with them, 0.285 without, PASS either way |
| The live shadow and the mapped arm | 2026 forecasts use 2025 counts. All four reported all year in 2025 (uptime 99% to 100%) | Nothing |

From 2024 the other three overflows' long-term average uses only years with uptime of at least 90%, which leaves
the season-only years out. That is why the covariate effect stops there.

## 3. Which way it pushes

*Inferred, not run.*

- **Doubtful labels (2022).** Any spill outside the season was not reported, so it is scored as no spill. The
  forecast and the baseline are both low for these overflows that year. The sign of the effect on the skill is not
  known.
- **Counts too low (2022 to 2024).** The forecast is too low for these overflows, most in 2023. That works against
  the forecast. It is a very small part of the 72% level.
- **Baseline too low (all years).** The baseline is weaker than it should be for the four. That works for the
  forecast.
- **Size.** At most 2.0% of G's overflow-years are touched in any way. Gate A's lead-0 result was 0.18 (0.13 to
  0.23). A lower end of 0.13 is unlikely to reach zero from this. That is a judgement until the sensitivity below is
  run.

## 4. How a correction should be stated

1. **Gate A stands as run.** Its verdict, figures and summary file of 1 November are not edited or replaced. A
   dated note on the record points here (added with this file).
2. **One sensitivity, by a rule fixed here before it is run.** Set G without the four flagged overflows, in every
   year. Same code, model, seeds and bootstrap. All four parts of Gate A, and the map's level and gain on 2025 at
   leads 0 to 3. Reported in a table beside the original figures, headed "sensitivity on seen data, rule of
   13 November 2026".
3. **Why drop them and not repair them.** Dropping removes the label, covariate and baseline effects together and
   needs no new choice. The other route (count days outside the season as unobserved and season-only counts as
   missing) needs several choices that could be tuned after a look. It is not used.
4. **What each outcome leads to.** If all parts still pass, Gate A's record gains one line: "holds without the four
   season-only overflows", with the figures. If any part fails, the record says so in its first lines, the trial
   record's evidence table is corrected, and Ethan is told before anything else is built on Gate A. Then a diagnosis
   by year.
5. **The map is not refitted.** It is frozen, and its 2021 backtest passed with and without the flagged overflows.
   The sensitivity reports its 2025 figures without the four and changes nothing.
6. **The loader.** `sw_history` should read the flag and carry it as its own column or file, so later work can leave
   those overflow-years out by rule. `sw_covariates.parquet` must not change: its hash is in the live shadow's stamp
   (`cov=sw:c2f2f654`), and a new file would start a new arm inside Gate B's window. The 2026 backtest protocol (due
   by the end of February 2027) should name the flag.

## 5. Not done here

The sensitivity was not run and the loader was not changed. The brief for this work said not to re-score Gate A.
The run is offline if the cached rain for G is complete in the main checkout. That was not checked.

| Field | Content |
|---|---|
| Identity | SCOT-TRIAL; this file; Gate A's record |
| Evidence | Counts only (section 2). No score |
| Next deliverable | The sensitivity of section 4, as its own PR, with the loader change. No Open-Meteo call expected; stop and record the number if any is needed |
| Owner | Claude, a new session |
| Milestone | Before the 2026 backtest protocol, end of February 2027 |
