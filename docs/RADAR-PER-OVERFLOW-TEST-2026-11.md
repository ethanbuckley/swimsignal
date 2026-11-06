# Radar rain at each overflow's own position: the test, stated before any run

Written 6 November 2026. Nothing has been run. No spill model has been fitted or scored on per-overflow radar, and no
score of any kind has been computed for this test. Results go below the line at the end. Nothing above it changes
after a result is seen.

## Why

The spill model reads rain per 0.1° cell, about 10 km across. A storm over one town and not the next is averaged
out. On 24 October 2026 Ethan asked for rain at each overflow's own position to be kept
(`docs/MET-OFFICE-DATA-2026-10.md` §6 and §9). PR #362 saved it: the Met Office 1 km radar at each of the 14,630
overflows, hourly, 21 November 2024 to 25 October 2026. Nothing has tested it.

The sibling test, #343 (`docs/RADAR-RAIN-CHECK-2026-10.md`), found:
- cell radar is a good record of the rain that fell (ratio 1.08, Spearman 0.876 against 291 EA gauges);
- fed to the production model (trained on United Utilities only) with no refit, cell radar barely beat the lead-0
  forecast: Brier 0.0339 against 0.0343, interval −0.00095 to +0.00010. Verdict B, "the model is the main limit".

#343 could not say whether finer rain helps a model that is fitted on that rain. This test refits the same model
form on each rain source, so each source gets its own fit.

## The question

At lead 0 (the "right now" and today level), does rain at the overflow's own position predict that overflow's
spill-days better than the ~10 km cell radar and the production rain input?

## The data

All of it is already on this machine. The run makes no network request.

- **Rain at each overflow.** `~/Documents/GitHub/swimsignal-private/radar-per-overflow/data/overflows/`,
  `radar_overflows_<YYYY-MM-DD>.parquet`, one file per UTC day, 21 November 2024 to 25 October 2026 (704 files).
  Columns: `site_id`, `time` (UTC, hour-ending, as Open-Meteo labels hours), `radar_mm` and `coverage` (the mean over
  the 3 × 3 block of 1 km pixels around the overflow), `centre_mm` and `centre_coverage` (the one pixel). Written by
  `scripts/fetch_met_office_radar.py` at 5900268 (identical to main's), for the overflow table with network key
  b5724303. **This data is private and is never published.** Only summary scores leave the run folder.
- **Rain per cell, radar.** `data/raw/met_office_radar/radar_<cell>_<YYYY-MM>.parquet` in the main checkout, as #343
  used it (499 cells).
- **Production rain at lead 0.** Open-Meteo Previous Runs, `cache/rain*/leads_<cell>_<year>.parquet`, lead 0, as
  #343 and `scripts/verify_leads.py` built it.
- **ERA5-Land.** `cache/rain*/archive_*` (`training.load_rain`), for the 7-day, 30-day and antecedent features in
  every arm, and as one reference arm.
- **Labels.** Spill days from the EA start/stop files (`ea_events_<company>.parquet`, all nine English companies,
  2024–2025), with `training.site_years` choosing the overflow-years, as #343 did. For the 2026 check below: Thames
  Water's own alert-stream events (`api_events_thames_water.parquet`, to 19 October 2026).
- **Urban or rural.** `overflow_urban_area.parquet`: an overflow within 100 m of an ONS 2022 built-up area is urban;
  further, or none, is rural.

Everything is read from the main checkout and the private folder, and treated as read-only. Each input is
fingerprinted (SHA-256) before and after the run; the two lists must match.

## The rain arms

Every arm uses the same model form, the same rows and the same features. Only the source of the short-range rain
features changes: `rain_d`, `max1h_d`, `max3h_d`, `max6h_d` (the day), `rain_d1`, `rain_d2` (the two days before) and
`rain_3d` (their sum). `rain_7d`, `rain_30d` and `api` come from ERA5-Land in every arm, as in #343, so the test
isolates the day's and the last two days' rain. Season and site features are the same in every arm.

| Arm | Short-range rain from |
|---|---|
| **C** cell radar | the 0.1° cell's radar, as #343 |
| **L3** local block (the deciding arm) | the 3 × 3 block of 1 km pixels around the overflow |
| L1 local pixel | the overflow's own 1 km pixel |
| P production | Open-Meteo lead 0, as #343's "lead 0" |
| E ERA5-Land | ERA5-Land, what production was trained on (reference only) |
| C-lag issue-time cell | the day from P; the two days before from C |
| L3-lag issue-time local | the day from P; the two days before from L3 |

L3 is the deciding arm, chosen now. A 3 × 3 block is less noisy than one pixel and covers the error in an overflow's
position (positions are snapped within a few hundred metres). L1 is reported, not decided on.

The "-lag" arms are what a live build could have at issue time: yesterday's and the day before's radar are complete
by then, today's is not. The full-day arms (C, L3, L1) use the whole day's radar, so they are an upper bound on what
radar can add at lead 0. The lag arms decide nothing.

**Coverage.** An hour of L3 counts only with `coverage` at least 0.9; of L1, with `centre_coverage` at least 0.9; of
C, with its own `coverage` at least 0.9 (as #343). A day needs at least 20 valid hours
(`features.MIN_HOURS_PER_DAY`), or its total is unknown. **Low coverage is missing, never zero rain.** A row is
scored only where every arm has the day and both days before. Rows dropped this way are counted.

## The model form

`SpillModel`, unchanged: layer 1 `fit_pooled` (gradient-boosted trees, monotone in rain, dry days subsampled at 0.25,
seed 0), then layer 2 `fit_site_offsets` (prior 15, recency 1.0, since one year is used). Nothing is tuned. The same
settings, seed and rows are used for every arm.

## Rows

The nine English companies' overflows from `training.site_years(..., 2025)` (covariates from the 2024 return), less
those whose cell has no cell radar or no 2025 lead-0 forecast (so every arm exists), for every day of 2025. United
Utilities is included: this is a fresh fit, not the UU-trained production model.

## Training and testing: blocked cross-fit with an embargo (primary)

2025 is cut into six two-month blocks. Fold A tests January–February, May–June and September–October. Fold B tests
March–April, July–August and November–December. Each fold's model is fitted on the other fold's blocks, less every
day within 7 days of one of its own test blocks (the embargo: weather persists for days and the lag features reach
back two days). Both folds' training data cover every season. Each row is scored once, out of fold, and the two
folds' predictions are pooled.

All of 2025 was scored in #343, with a different model (the production model, no refit) and only cell radar, lead 0
to 4 and ERA5-Land. Local radar has never been scored on it, and nothing in this design was chosen from #343's
per-row results. These figures are development evidence on seen labels, not fresh confirmation.

## The 2026 forward check (secondary)

Each arm's model is refitted on all 2025 rows (no fold) and frozen. It is then scored on Thames Water's overflows from
1 January to 31 August 2026 (the end of the cached ERA5-Land for 2026), labelled by Thames Water's alert-stream
events. Rows: Thames overflows in the 2025 row set that appear in the stream file, in cells with 2026 lead-0
forecasts and ERA5-Land. These labels are later than every fit. They are one company, and a different label source
(in #253, the stream's latest event matched the EA file to the minute at 281 of 342 Thames overflows). This check decides nothing on its own.

## The metric and the decision

Brier score on out-of-fold probabilities. Skill against C is 1 − Brier(L3) / Brier(C).

**The interval.** A two-way cluster bootstrap (overflows and ISO weeks resampled independently, each row weighted by
the product of its overflow's and its week's draw counts), 2,000 draws, seed 20261106. Weeks rather than days,
because weather is shared across days in a week; this is the wider of the two. The overflow × day interval and #343's
week-only interval are reported as well.

**The margin, stated now: 1% of C's Brier.** That is about 0.0004 at #343's levels, the size of #343's radar-over-
forecast gain, which was inside the noise. A smaller gain would not pay for a live per-overflow radar pipeline.

**The verdict, one of four:**
- **H. Local rain clearly helps** if L3 − C has a 95% interval wholly below zero, skill against C is at least 0.01,
  and L3 − P also has an interval wholly below zero.
- **S. A small gain** if L3 − C has an interval wholly below zero but H does not hold.
- **N. Not shown** if the interval of L3 − C includes zero. The record says whether the interval also rules out a
  gain of 1% (its lower end above −1% of C's Brier).
- **W. Worse** if the interval of L3 − C lies wholly above zero.

## Reported whatever the verdict

Brier, AUC, the share of spill days at probability 0.4 or more (the High line) and of dry days at 0.4 or more, for
every arm. L1 − C, L3 − L1, C − P, L3 − P, L3-lag − P and L3-lag − C-lag with intervals. By company, by urban and
rural, and by season (December–February and so on): Brier of each arm and L3 − C, with no decision. The 2026 forward
check's same figures. A description of how the rain sources differ: the share of overflow-days where L3's daily total
differs from C's by 5 mm or more, and their correlation.

**The no-refit check (secondary, as #343).** The production `spill_model.pkl` fed C, L3, L1 and P on #343's own
Question 3 rows (2025, United Utilities left out, no refit). Brier and the L3 − C interval are reported. This is the
direct sibling of #343's figure.

**Exploratory, decides nothing.** Where cell rain should miss most: L3 − C on (a) June–August rows, (b) the tenth of
test rows with the largest difference between L3's and C's day totals, (c) the same within June–August.

## Compute and network caps

- No network: the scoring runs under `scripts/lake_distance_eval/run_offline.py`, which refuses every outgoing
  connection and counts attempts. The count must be 0.
- 21 model fits (7 arms × 2 folds + 7 for the forward check). Stop if the run exceeds 2 hours or 12 GB peak memory
  (the machine has 16 GB).
- The scoring holds the group's heavy-run lock and waits for it if another session has it.
- Isolation: a `git archive` of the harness commit; scratch `DIPCAST_ROOT` and `DIPCAST_STATE` holding copies of the
  processed files read; `DIPCAST_CACHE` pointed at the shared cache, read-only; outputs in a scratch folder outside
  every checkout.

## What is expected, stated now

N. #343 found that the model, not the rain, was the main limit; within a 10 km cell, rain differences on most days
are small next to the spread between overflows. If anything shows, it will be in June–August, where showers are
local.

## What follows

Nothing changes on the site or in production from this test, whatever the result. Any live use of radar would change
the 2027 forecast stamp (`docs/PREREGISTRATION-2027.md` §2) and need a dated amendment before 1 May 2027.
- **H:** freeze the L3 candidate (code, settings and fitted model hash committed). The next deliverable is the
  issue-time question: can the build read the latest radar composites for every overflow at issue time, how long
  does it take, and at what cost? The full-day arm used radar for the whole day; a live build has it only up to
  issue time, so the issue-time version (radar to the hour of issue, forecast for the rest) gets its own stated test.
  Anything unresolved is recorded as a blocker.
- **S:** record the gain. If L3-lag also beats C-lag, the issue-time path is worth a cost estimate; otherwise
  archive as N.
- **N or W:** archive per-overflow radar as a spill-model input, with this evidence. The private data stays for
  river-rise and event-timing questions. It reopens if a model that knows each company is adopted (A8, upgraded-
  overflow option B or a nine-company refit), or when the EA 2026 start/stop files add a second labelled year. The
  exploratory figures say whether a summer-only or storm-day use is worth stating as its own test.

## Seen before writing

- The per-overflow folder's file list, `run.sh`, the end of `run.log` and the session note (704 files, 92 hours with
  no data, 20 hours with coverage under 0.9).
- One day's file, 1 July 2025: its columns and summary statistics (every coverage 1.0). No label was joined.
- `overflows_b5724303.parquet`, `overflow_pixels.parquet` and `overflow_urban_area.parquet`: columns, two rows, and
  the share within 0 m of a built-up area (40%).
- The spans of the EA start/stop files (2024–2025), the Thames stream file (April 2022 to 19 October 2026; 460
  overflows with 2026 events) and the lead and ERA5-Land caches (2026 ERA5-Land to 31 August and 6 September).
- `docs/RADAR-RAIN-CHECK-2026-10.md` and its harness, `SpillModel`, `features` and `training`, read for method.
- No score of any kind has been computed for this test.

---

## Results

Not yet run.
