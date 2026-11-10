# Scotland trial: frozen-model backtest on 2021

Protocol written 10 November 2026, committed and pushed before either archived Scottish Water file is downloaded.
Route: [Backtest instead of waiting](RESEARCH-WORKFLOW.md). Set out in section 5 of the
[2026 backtest inventory](SCOTLAND-2026-BACKTEST-INVENTORY-2026-11.md) (PR #654). Contains Scottish Water data
licensed under the Open Government Licence v3.0.

Nothing below may change after a 2021 forecast is scored. A different rule would be a new, dated rule beside this
one, and the record would report both.

## 1. The question

Does the Scotland trial's forecast, frozen as it stands, beat each overflow's own earlier-years spill rate, at the
right level, on 2021? 2021 is a year the spill model, the covariate rule and the calibration map were never fitted,
chosen or checked on.

A pass supports the existing limited release only: three SEPA lochs, labelled trial. It changes no level, threshold,
wording or switch. `DIPCAST_SCOTLAND_TRIAL` stays Ethan's.

## 2. What is frozen

| Part | File | Identity |
|---|---|---|
| Spill model | `data/processed/spill_model.pkl` | SHA-256 `faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e`, stamp `808da63d`, trained on United Utilities 2023-25. Layer 1 (`predict_pooled`). Not refitted |
| Calibration map | `data/processed/scotland_calibration.json` | SHA-256 `447a02a1556fd811719bc49776131ef1a2e386020ad5449030624755b172811d`. Platt map on the logit, a = 0.44928584513880876, b = 0.7496750672880154, fitted 2022-24 (commit 42efc002) |
| Covariate rule | `src/dipcast/ingest/sw_covariates.py` | The rule of 10 Oct 2026, code unchanged. The committed table `data/processed/sw_covariates.parquet` (SHA-256 `1ee52787be8b78fda1d7f44cee31deb0f35a0f3c9c1d9d9c31317c63c5f3e672`) has no return year 2020, so 2021's covariates are computed by the same code (section 4) |
| Scoring code | `scripts/hindcast_scotland.py`, `scripts/hindcast_wales.py` | As at `origin/main` d644dc90. Gate A's definitions of labels, eligibility, set G, the earlier-years baseline and the bootstrap, unchanged |
| Gate A's own model (reported only) | `data/processed/spill_model_holdout_2025.pkl` | SHA-256 `882f9d4fb2c9314943fa861d8c6f4c62d8cd1eb57f1aa25059f4eb27d07068dc` |

The trial applies the map to the model's raw chance for Scottish rows (`scotland_trial.calibrate`), so the forecast
scored here is `apply_map(predict_pooled(features))`.

## 3. What was seen before this protocol

- **2021's annual counts were already used, as inputs.** In Gate A and in the map's fit, 2022's rows took their
  covariates (lta_spills, spill_hours) from 2021's counts and their earlier-years baseline from 2021's spill-days.
  So the map was fitted on rows whose inputs included 2021 counts. No 2021 day was forecast or scored by anyone.
- Aggregates already read: 10,712 events in 2021 in `sw_events.parquet`; 133 overflows with a 2021 count, 95 of
  them eligible by Gate A's rules (`SCOTLAND-HINDCAST-2026-11.json`, coverage). 48 of the 66 rain cells of those 133
  overflows have 2021 rain cached.
- The archived editions: only their URLs, capture dates and sizes. Not downloaded or opened.
- Not known: how many of 2021's eligible overflows have a 2020 count, so the size of the test set is not known.

## 4. Data

**Test year.** 2021 only, at lead 0.

**2021 labels.** From the local `data/processed/sw_events.parquet` (SHA-256
`11ef6d05c99cf2ce929da7bce845ef7a0747163275a8414a666665a8299b5f68`, built 4 Oct 2026 from Scottish Water's
reported 2021-2025 edition of August 2026), by `hindcast_scotland.labels`: a spill-day is a UTC day touched by an
event over 15 min 30 s or of unknown duration; a day record labels its local date. This is the file Gate A used.

**History before 2021.** From the two archived editions of Scottish Water's reported-to-SEPA file:

- the 2020-2024 edition (`…SEPA-20202024--Summary---280325-v1.xlsx`, captured 7 Oct 2025, 5,033,567 bytes) for 2020;
- the 2017-2021 edition (captured 19 Dec 2022, 3,817,619 bytes) for every year before 2020 that it holds.

Each year comes from the newest edition that holds it. 2021 rows in the archived editions are not used for labels
or covariates.

*Amendment 1, 10 Nov 2026, before either download.* The sizes above are the Internet Archive's CDX `length` field,
which is the length of the compressed archive record, not of the file. They identify the capture, not the bytes.
The files are fetched by capture, with the `id_` form so the archive returns them unaltered:

- `https://web.archive.org/web/20221219134526id_/https://www.scottishwater.co.uk/-/media/ScottishWater/Document-Hub/Key-Publications/Urban-Water-Improvements/141222SWReportedOverflowEventDataToSEPA20172021SummaryLatest.xlsx`
- `https://web.archive.org/web/20251007090441id_/https://www.scottishwater.co.uk/-/media/ScottishWater/Document-Hub/Key-Publications/Improving-Urban-Waters/CSO-DATA/SW-Reported-Overflow-Event-Data-to-SEPA-20202024--Summary---280325-v1.xlsx`

Each file's own size and SHA-256 are recorded. A reply that is not an xlsx workbook stops the run.

**Reading them.** `sw_history.read_workbook` where the layout matches (summary sheet, "Overflow Events in <year>"
sheets, the same column names). Where it does not, a loader for the older layout maps each column by its header
text to the same meaning. If a column's meaning cannot be read from its header or the edition's own guide, stop
and record it rather than guess. Asset IDs: `sw_history.assign_sites` with the edition's own summary first, then
the local reported and non-reported workbooks' summaries, so an old ID maps to the current one by measurement
point. The time-zone rule, day records, text cells and the 60-day cut are sw_history's.

**Covariates for 2021's rows.** `sw_covariates.covariates(events, yearly, first_year=F)` over the local events and
the archived years together, where F is the first year the archived editions hold. This follows the rule's own
words: FIRST_YEAR is "the first year the Scottish files hold". F is passed as an argument; the module's default
stays 2021. A run for 2021 uses return year 2020 (`covariates_for`). Positions, API type and the emergency flag
are joined as `scripts/fetch_scotland_history.py` joins them.

**Set G(2021).** Gate A's set G with test year 2021: overflow-years of 2021 counted in 2021 and in 2020, with a
position, not emergency (API type or name), and uptime not below 50% (unknown uptime kept).

**Earlier-years baseline.** Gate A's: the overflow's spill-day rate over its eligible counted years before 2021 (all
years the archived editions hold); where it has none, the rate of all such overflow-years in the same calendar
month; clipped to 0.001 to 0.95.

**Rain.** ERA5-Land hourly rain per 0.1° cell from Open-Meteo's archive, for 2021 and for 2020 (January's
antecedent windows reach back 30 days), features from `features.daily_rain_features` as Gate A builds them.
`FIRST_RAIN_YEAR` is 2020 for this run only. Rows whose day has no rain total are dropped. No archived forecasts:
leads 1 to 3 are not tested.

## 5. Checks before any 2021 forecast is made

1. Each download goes into its own new empty folder outside the repository. Its SHA-256 and size are recorded. It is
   read only with `python -I`.
2. **Covariate code unchanged.** `sw_covariates.covariates` with first_year 2021 on the local events alone must
   reproduce the committed `sw_covariates.parquet`'s covariate columns. If not, stop.
3. **Edition overlaps, counts only.** 2020 counts per overflow between the two archived editions, and 2021 counts
   per overflow between the 2017-2021 edition and the local file. Reported, not used to choose anything.
4. Inputs above hashed before and after the run; the shared caches and the main checkout are read only.

## 6. The forecast, the metric and the pass rule

**Scored forecast.** The trial's: production model `808da63d`, layer 1, Scottish year-before covariates (a missing
value takes the median of the year's G overflows, then the model default, as Gate A), Scotland's map applied.

**Reported beside it, not gated.** The same model unmapped; Gate A's arm (holdout model, Scottish covariates,
unmapped); default covariates; England's lead-0 calibration on the raw chance; the flat rate (uses the answer).

**Metric.** Brier score. Brier skill score (BSS) = 1 − Brier(forecast) / Brier(reference). Intervals:
`hindcast_wales.Scorer`, a cluster bootstrap over overflows × ISO weeks, 2,000 draws, seed 0, 95% percentile.

**Pass rule.** All three must hold:

- **B1 (Gate A's G1 on 2021).** The lower end of the 95% interval of BSS, trial forecast against earlier years, is
  above zero.
- **B2 (the map's R1).** The trial forecast's level, sum of forecasts / spill-days, is between 0.9 and 1.1.
- **B3 (the map's R2).** The lower end of the 95% interval of 1 − Brier(mapped) / Brier(unmapped) is above zero.

G(2021) with rain needs at least 10 overflows and 100 spill-days (Gate A's minimum); otherwise the result is
**NOT COMPLETE**. **PASS** if all three hold, **FAIL** if any fails.

**Reported, not gated.** Reliability by tenths; wet and dry days (over 10 mm on the day and the day before); by
overflow type and local authority; a history-length sensitivity with the earlier-years baseline and lta_spills from
2020 alone (first_year 2020), as Gate A's 2022 rows had one year of history.

## 7. Differences from the live forecast

- Rain is the rain that fell (ERA5-Land), not issue-time forecasts. This is lead 0, a hindcast.
- About 95 reported overflows at most, not the trial's 1,485, and no live feed behaviour.
- 2021 events come from an edition published in 2026; the 2020 history from one published in 2025. A forecast
  issued in 2021 would have had the 2020 count from an earlier edition.
- England's leads 4 and 5 and the live-status inputs are not involved.

## 8. Rain budget and pace

The needed cell-years are counted after the loader runs and before any fetch. The ceiling is the inventory's: 18
cell-years of 2021 and 66 of 2020, 84 in all. By the hindcast scripts' count (`archive_calls`, days / 14 per
cell-year, about 26.1) that is about 2,190 calls, Ethan's approved total. By Open-Meteo's own rule
(`rainfall.call_weight`, one variable at a tenth of days / 14) it is about 220. The pace uses the larger count:
at most 1,000 a UTC day while the D4 ensemble-rain read runs (to 19 November), booked in a ration ledger
(`rainfall.spend`, `DIPCAST_OPEN_METEO_DAILY_CALLS=1000`) in a scratch cache, at most 500 an hour, stopping at the
first refusal. About three UTC days of wall time. No fetch beside another Open-Meteo job on this Mac.

## 9. What follows each outcome

- **PASS.** Recorded in this file, the inventory, the register and the catalogue. The trial's evidence gains "checked
  on 2021, a year neither model nor map saw". It supports the existing limited release only. Gate B continues as
  monitoring. Next deliverable: the shadow arm with Scotland's map (trial next step 2).
- **FAIL on B1.** The trial's claim that it beats each overflow's history is not confirmed on an unseen year. Record
  it, and tell Ethan the evidence no longer supports switching the trial on. Next deliverable: a diagnosis by overflow
  type, history length and edition; any new candidate gets its own protocol and is scored on years not yet used
  (2018-20 from the same archive, about 1,700 calls a year by the scripts' count).
- **FAIL on B2 or B3 only.** The ranking holds; the map's level is not confirmed. Next deliverable: the level by
  year 2021-25, and any refitted map tested under its own protocol on 2018-20, not on 2021.
- **NOT COMPLETE.** Record the counts. Next deliverable: add 2018-20 as test years under a new protocol, with
  Ethan's yes to their calls.
