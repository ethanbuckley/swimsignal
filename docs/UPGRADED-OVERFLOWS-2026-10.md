# Upgraded storm overflows in the spill forecast: Ilkley

Written 22 October 2026. A record of checks, not a test: nothing here changes a model setting, a map or a score.
The question came from Ilkley Clean River's email of 21 October 2026. It said Ilkley's storm flows are now
treated by storage and a wetland, and asked for different wording on spill notices.

Each finding is marked **established** (read from a file or recomputed here) or **inferred** (a reasonable
reading that a named source would settle).

## Answer

- **The forecast treats an upgraded overflow as if nothing changed, and will for years.** `lta_spills` is the
  EA's long-term average. For Ilkley's overflows that is a running mean of every yearly count since 2020. The build
  reads a copy of the returns committed on 13 Sep 2026, and nothing refreshes it. A refresh after the 2026 returns
  (likely late March 2027) would move Middleton from 36 to about 33.
- **The upgraded overflows have nearly stopped discharging since spring 2026.** That holds for the six overflows
  above Cromwheel that Yorkshire Water names. In April to August 2026 the model expected 23.0 spill days from them,
  and the EA's own 2026 file shows 1. The ten other overflows above Cromwheel showed 49 against 68.7. From January to
  March 2026 the six were normal: 40 against 30.1.
- **Middleton alone barely moves Cromwheel's level.** Setting Middleton's `lta_spills` to 10 changes 31 of 547
  moderate-or-higher days in 2024 to 15 Oct 2026, each by one level. The six named overflows together are what
  matter. At 10 spills a year each, 285 of those days drop a level; at 1 a year, 383.
- **The model's response to `lta_spills` is jagged and not monotone.** At Middleton, with 2025's inputs, a
  covariate of 0 gives 8.1 expected spill days a year, 2 gives 3.3 and 10 gives 12.2. Any override that writes a
  small number into this covariate makes the forecast depend on an arbitrary choice.
- **Recommendation: option C now.** Say so on the spot page, from a dated file of cited upgrades that the model does
  not read. Pre-register a test of option B (each overflow's own record since its upgrade) and decide it before
  the 2027 freeze on 30 April 2027. Do not write design targets into `lta_spills` (option A).

## 1. Which return year feeds `lta_spills`

**Established.**
- `overflows.latest_annual_returns()` keeps each overflow's latest return year. The build reads
  `data/processed/annual_returns.parquet`, a file in git last changed in commit 8ac835f (13 Sep 2026). No workflow
  refreshes it: no file in `.github/workflows/` names it.
- That latest year is 2025 for all six named overflows. The live spot file (`data/spot/bw-uke4100-08901.json`, build
  of 21 Oct 21:50 BST) gives Middleton 36, Rivadale View 48.5 and Bridge Lane 4.17. These are the 2025 rows exactly.
- `lta_spills` is the EA's `longterm_average_spill_count_calculated`. For all six named overflows, every year's value
  from 2022 to 2025 equals the mean of all yearly counts from 2020 to that year. This needs 2020 counts of 40, 61,
  16, 6, 21 and 6 (Middleton, Rivadale View, Bridge Lane, Low Mill Lane 179, Addingham 3xDWF, Addingham 6xDWF).
  Middleton's 2025 value is (40 + 31 + 34 + 49 + 38 + 24) / 6 = 36.
- The other two covariates are the return year's own figures: `spill_hours` (214.5 h for Middleton in 2025) and
  monitor uptime. They would follow an upgrade within a year.
- No Yorkshire overflow has a per-overflow calibration. The production model is trained on United Utilities
  2023-2025 only, and its 2,271 site offsets are all United Utilities ids. At Ilkley the three covariates are the
  only inputs that differ between overflows.

**Inferred.**
- The 2025 returns were reported on 27 March 2026
  ([Water Magazine](https://www.watermagazine.co.uk/2026/03/27/storm-overflow-spills-fall-sharply-in-2025-environment-agency-data-reveals/)),
  so the 2026 returns are likely to appear in late March 2027.
- The 2020 counts are implied by the arithmetic, not read: the parquet starts at 2021.
- Suppose the EA keeps the same rule and counts 12 to 16 spills for Middleton in 2026 (the EA file has 16 spill
  days, all before April). Middleton's average then becomes 32.6 to 33.1, and Rivadale View's about 42.9. On the
  curve in section 3, that cuts Middleton's expected spill days by about 2 a year.
- The 2027 protocol (`docs/PREREGISTRATION-2027.md`, freeze steps 3 and 4) already asks for a refresh decision by
  mid-April 2027. A refresh changes the covariates of every overflow, not only Ilkley's.
- For United Utilities overflows the same problem also sits in the site offsets. They are fitted on 2023-2025
  events, and `train.py`'s default `--recency` is 1.0 (no down-weighting of older years).

## 2. Discharges since the upgrades, against what `lta_spills` implies

**Sources.**
- The EA's start/stop file "Yorkshire Water Detailed Data 2026.xlsx" covers 1 Jan to 31 Aug 2026. It comes from
  "2026 year to August Detailed EDM Start-Stop Data.zip", revised 20 Oct 2026, in
  [the EA dataset](https://environment.data.gov.uk/dataset/e9677ac1-fd32-4ceb-88a0-2735be5f27c7).
- Yorkshire Water's live feed as polled by SwimSignal (`live_history.parquet`, from 11 Sep 2026) covers the time
  after the EA file ends.
- "Expected" is the production model run on ERA5-Land archive rain at lead 0, with the year-before return. These
  are the inputs the live forecast reads.
- PR #258's earlier-spill files hold no Yorkshire overflow, so they add nothing here.
- The page names "Low Mill Lane CSO" and "Addingham SPS CSO". These are taken to be Low Mill Lane 179 (Low Mill
  Lane 27 has no spills on record) and the two Addingham No 1 SPS overflows. Both matches are by name only
  (**inferred**). The other four names match exactly.

**No source gives a completion date for any of these upgrades.** Yorkshire Water's
[Addingham and Ilkley page](https://www.yorkshirewater.com/about-us/what-we-do/making-yorkshire-brilliant/addingham-and-ilkley)
(read 21 Oct 2026) is in the future tense: the works and wetland "will all be completed in Summer 2026". For
Middleton it says "we'll be packing up in Summer 2026"; Bridge Lane's work runs "from 17 November 2025 until Summer
2026". So each window below starts the day after the overflow's last discharge, not at a completion date.

**Established.** Spill days from the day after each overflow's last discharge to 15 Oct 2026, against the same
calendar window in earlier years (`-since-last.csv`). Observed 2026 counts the EA file to 31 Aug, then the polls.

| Overflow | Last discharge (EA file / feed) | 2026: expected, observed | 2025: expected, observed | 2024: expected, observed |
|---|---|---|---|---|
| Ilkley Middleton CSO | 31 Mar / 31 Mar | 6.5, 0 | 7.5, 5 | 10.1, 16 |
| Rivadale View CSO | 8 May / 8 May | 7.7, 0 | 9.3, 6 | 11.0, 14 |
| Bridge Lane CSO | none in 2026 / 18 Feb | 0.5, 0 | 0.6, 0 | 2.0, 0 |
| Low Mill Lane 179 CSO | 7 Feb / 7 Feb | 2.3, 0 | 2.5, 4 | 3.8, 3 |
| Addingham No 1 SPS 3xDWF | 16 Feb / 22 May | 7.0, 0 | 11.3, 11 | 11.8, 16 |
| Addingham No 1 SPS 6xDWF | 30 Mar / 20 Apr | 9.4, 0 | 11.4, 10 | 13.0, 10 |

By group and season (`-observed.csv`). The six are the overflows named on Yorkshire Water's page; the ten are the
other overflows upstream of Cromwheel.

| Spill days | Six named: expected | Six named: observed | Ten others: expected | Ten others: observed |
|---|---|---|---|---|
| Jan-Mar 2024 | 59.5 | 73 | 112.9 | 165 |
| Apr-Aug 2024 | 46.8 | 52 | 108.1 | 152 |
| Jan-Mar 2025 | 21.8 | 39 | 45.8 | 52 |
| Apr-Aug 2025 | 21.6 | 8 | 66.5 | 113 |
| Jan-Mar 2026 | 30.1 | 40 | 71.0 | 63 |
| **Apr-Aug 2026** | **23.0** | **1** | 68.7 | 49 |

The live forecast's own record agrees. Its logged lead-0 chances for 14 Sep to 20 Oct 2026 sum to 6.4 spill days for
the six, and the feed shows 0. For the ten others, 22.1 against 15 (`-log.csv`).

**What this rests on, and its limits.**
- A silent monitor is not proof of an upgrade. Of 311 Yorkshire Water overflows with a live feed and a 2025 average of
  30 to 45, 17 (5.5%) have shown no discharge since before 1 Apr 2026 (`-silence.csv`). One has shown none since
  before 2025, which looks like a fault. Four regular spillers on one company list (Middleton, Rivadale View and the
  two Addingham overflows) going quiet in the same spring, while ten others nearby kept spilling, is much harder to
  explain by faults. That is **inferred**, not tested.
- The EA file and the feed disagree on a few short events. The feed shows Addingham discharges on 20 Apr and 22 May
  and a Bridge Lane one on 18 Feb that the EA file lacks. For Addingham 3xDWF, two polls on 21 Oct gave different
  latest events (22 May and 13 May). None of these changes the totals above by more than 3.
- The six were already low in April to August 2025: 8 against 21.6, while the others were high, 113 against 66.5.
  Work may have started then, or storage or overpumping during construction may have held flows back. **Inferred**:
  Yorkshire Water's page gives no dates for this.
- The model under-forecast Middleton before 2026: 25.5 expected against 42 observed in 2024, and 21.6 against 26 in
  2025. So the 2026 gap is not the model being high at this overflow.

## 3. How much `lta_spills` moves the forecast

**Established.** Middleton's expected spill days with only its `lta_spills` changed, everything else as the live
forecast had it (`-lta-curve.csv`):

| `lta_spills` | 0 | 1 | 2 | 5 | 10 | 20 | 30 | 36 | 50 | 100 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025 inputs (own value 38.4) | 8.1 | 5.4 | 3.3 | 6.6 | 12.2 | 15.0 | 19.6 | 21.6 | 25.9 | 49.7 |
| 2026 inputs to 15 Oct (own value 36) | 5.0 | 2.9 | 1.8 | 4.2 | 6.5 | 8.3 | 12.2 | 12.7 | 16.4 | 32.9 |
| 2024 inputs (own value 38.5) | 14.4 | 8.3 | 4.8 | 10.1 | 18.3 | 18.9 | 35.8 | 27.1 | 31.8 | 54.8 |

- The effect is large but less than proportional. Cutting 36 to 10 (-72%) cuts expected spill days by 28% to 49%.
  Cutting to 1 still leaves 3 to 8 spill days a year.
- On Middleton's wettest days in 2025 (chance 0.3 or more at its own value, 15 days), the mean chance is 0.563 at
  36, 0.401 at 10 and 0.225 at 1.
- The curve is not monotone. 0 forecasts more than 1 or 2, and with 2024's inputs 30 forecasts more than 36. In 2024,
  setting 10 raised Middleton's chance on 42 days. The spill model constrains only the rain features
  (`features.MONOTONE`); the site covariates are left free.

**Cromwheel's level, 1 Jan 2024 to 15 Oct 2026** (`-levels.csv`). Cromwheel had 547 days at moderate or above in
this period. Every change below is one level down; none is up.

| Scenario | Days whose level drops | Mean risk drop | Largest |
|---|---|---|---|
| Middleton at 10 | 31 (6%) | 0.007-0.012 | 0.077 |
| Middleton at 10, spill hours scaled to match | 37 | 0.009-0.014 | 0.095 |
| Middleton at 1 | 50 (9%) | 0.015-0.018 | 0.111 |
| The four named CSOs capped at 10 | 83 (15%) | 0.025-0.028 | 0.177 |
| The four named CSOs capped at 1 | 141 (26%) | 0.038-0.041 | 0.281 |
| The six named overflows capped at 10 | 285 (52%) | 0.065-0.091 | 0.336 |
| The six named overflows capped at 1 | 383 (70%) | 0.097-0.136 | 0.485 |

Bridge Lane (4.17) and Low Mill Lane 179 (7.33) are already under 10, so "capped at 10" changes only Middleton,
Rivadale View and the two Addingham overflows.

Middleton alone matters little because on the days that are high, other overflows near the spot are also likely to
spill. The spot's risk is 1 - (product over overflows of 1 - weight x chance), so once a few terms are large,
taking one away changes little.

**The week of 21-25 October 2026** (`-week.csv`). The published levels are moderate, moderate, high, very high, very
high. Replacing Middleton's term in the published build with its chance at 10 a year leaves every level the same
(risk 0.250, 0.223, 0.620, 0.895, 0.759).
- Middleton's chance at 10 a year was scaled from a forecast fetched at 22:57 UTC, which was wetter for 23-24 Oct.
  On that forecast, all six named overflows at 1 a year would give moderate, low, high, high, high.
- That forecast is not kept in the repo, so this table cannot be rebuilt later.

## 4. Options

**A. A dated override file that feeds the model.** `data/raw/overflow_upgrades.csv` would hold one row per overflow:
what changed, the completion date, a design or measured spill rate, the source URL, a quote and the date checked.
From the completion date the model would read the override in place of `lta_spills`.
- Code: small, about half a day with tests (read it in `build_overflows` after `latest_annual_returns`).
- No source can fill the date column for Ilkley today: Yorkshire Water's page is in the future tense.
- The value to write is a target, not a measurement. "One discharge per bathing season" is not an annual count, and
  the jagged curve (0 gives more than 2) makes the result depend on which small number is chosen.
- Every upgrade nationally needs a row and a source, checked by hand.
- It changes forecasts, so it needs a pre-registered test, which few upgraded overflows would give little power.

**B. Each overflow's own record since its upgrade.** Extend layer 2 (the Gamma-Poisson observed/expected offset in
`spill_model.py`) to every company. Fit it only on events after a start date, from the EA start/stop files and
SwimSignal's polls.
- It uses measurements, works for every overflow, and also catches overflows that get worse.
- It needs a start date per overflow (from A's file, or a change-point rule).
- A rule would read a dead monitor as an upgrade and lower the forecast: the wrong direction for swimmers. 17 of 311
  similar Yorkshire Water overflows are silent since April. It would need a check that the monitor is alive.
- With the current prior (15 pseudo spill-days) it moves slowly. Middleton since 1 April (0 observed, 6.5 expected)
  gives an odds multiplier of 15 / 21.5 = 0.70. A full quiet year at 2025's expectation (21.6) would give
  15 / 36.6 = 0.41. That is a little stronger than `lta_spills` = 10, which cut 2025's expected spill days by 44%
  (section 3). **Inferred**: the arithmetic of the prior, not a refit.
- Cost: about 2 to 4 days, then a shadow window and a pre-registered test like PRs #254 and #262.

**C. Leave the model, and say so on the spot page.** Keep the same dated, cited file as A, but only the page reads
it. Beside each listed overflow the page would say:
1. Yorkshire Water says it has upgraded the overflow, with the source.
2. Its monitor has shown no discharge since the date in the data.
3. The forecast still uses its spill counts for 2020 to 2025, so it may overstate the risk from it.
- Cost: about half a day with tests. No model test.
- The forecast stays high at Ilkley. Over-warning is the safe direction for swimmers, but it costs trust with
  Ilkley Clean River and Yorkshire Water.

**Recommendation: C now, and a pre-registered test of B for 2027.**
- C answers Ilkley Clean River's request honestly without a model change, and fits the reply drafted on 21 October:
  it says the discharges are still counted.
- The test of B should be written before it is run, scored on 2026 data (EA file to August, polls since 11
  September), and decided before the 30 April 2027 tag.
- Not A: its dates cannot be cited yet, and a design target in a non-monotone covariate is a guess the forecast
  would then present as data.

## Corrections to the brief

- Yorkshire Water's page does not say "at most 10 a year". It says "one discharge per bathing water season" for the
  scheme and "one per bathing season" for Middleton's 920 m³ tank. The 10-a-year figure is probably the national
  long-term target for all overflows. **Inferred**, not checked.
- "Until the 2026 return is published" is not enough. The build does not fetch returns, and the EA's average keeps
  six years of pre-upgrade counts in it.

## Rerunning

```bash
uv run python scripts/check_upgraded_overflows.py --state STATE_DIR --ea-2026 "Yorkshire Water Detailed Data 2026.xlsx" --rain-2026 RAIN_2026_DIR --forecast-rain FORECAST.parquet
```

`STATE_DIR` holds `dipcast.duckdb`, `live_latest.parquet` and `live_history.parquet` from the `state` release of
21 Oct 2026 10:33 UTC. The 2026 archive rain for the five cells came from one Open-Meteo request on 21 Oct 2026, and
the week's forecast from one more. The script's docstring gives every input.

## Follow-ups seen, not done

- **Scan for other changed overflows.** The EA's 2026 zip holds all ten companies to August. A national list of
  overflows far below the model's expectation since spring 2026 would find other upgrades and dead monitors.
- **The EA import route has broken.** The per-company files that `scripts/import_ea_events.py` downloads are gone.
  On 22 Oct 2026, "Yorkshire 2025 Detailed EDM Data.xlsx" returned ResourceNotFound; that route worked on 16-17 Oct.
  The dataset was revised on 20 Oct. The data now comes as one zip per year ("2025 Detailed EDM Start-Stop
  Data.zip", 27,970,711 bytes), through the same signed-link route. Since fixed: both EA importers now read
  the yearly zips (`edm_events.ea_yearly_zips`, `ea_zip_members`).
- **The EA revised the annual returns in August 2026** (Anglian Water; one Northumbrian site), per data.gov.uk.
  Whether the committed `annual_returns.parquet` includes the revision was not checked.
