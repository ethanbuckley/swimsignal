# LEDGER stage 2: the season hindcast, statement written before it is run

Written 19 November 2026 against main `ca994f26`. Register row **LEDGER** (`docs/RESEARCH-RECOVERY-2026-10.md`).
Owner: Ethan, with a Claude session doing the work. Route: bounded exploration. **Stage: development. This is not a
confirmation and not a test of the forecast's skill.** Nothing here changes a forecast, an issued prediction, a frozen
window, option B's files, the Ilkley audit statement, `data/eval2027/` or the 2027 primary evaluation.

**This statement is pushed before any season figure is computed.** A results section is added below it afterwards,
in the same PR. It does not change anything above it.

Ethan decided on 19 November 2026 that the ledger stays an unpublished Lab prototype, that overflows are not named
nationally in public, that the by-company table is not shown, and that the season hindcast goes ahead now.

## Why a second calculation

Ledger v1 (`data/research/overflow_ledger.v1.json`, [contract](OVERFLOW-LEDGER-CONTRACT-v1.md)) gives a year figure
per overflow: the EA's long-term average spill count times the overflow's summed weight. The brief asked for a season
figure, such as modelled high-level spot-days per overflow over a bathing season. That needs each overflow's spill
state on each day of a season. The forecast log holds daily chances only from 12 October 2026, after the season. So a
past season has to be rebuilt. Ledger v1, its contract and its script stay as they are.

## What already exists (inventory, 19 November 2026)

Searched the main checkout's `data/processed/` and `data/cache/`, and the hindcast scripts. Nothing is fetched.

| Input | Where | Coverage for this work |
|---|---|---|
| EA start/stop files, nine English companies | main checkout `data/processed/ea_events_<company>.parquet` (16 Oct 2026) | 1 January to 31 December 2024 and 2025, every company. Open Government Licence |
| EA start/stop files, Dŵr Cymru's overflows in England | main checkout `data/processed/dcww_ea_events.parquet` (4 Oct 2026), read from the EA's own zips | 2024, 2025 and 2026 to July. 39 of the ledger's 40 Dŵr Cymru overflows appear in it. Open Government Licence |
| EA 2026 start/stop file | `swimsignal-private/event-layers-2026/`, not in the main checkout | 1 January to 31 August 2026 (Thames to 31 July). **Does not cover the 2026 season** |
| Annual returns | committed `data/processed/annual_returns.parquet` | Returns 2021 to 2025. 1,368 of the 1,414 overflows in the 2025 return |
| Archive rain (ERA5-Land, Open-Meteo archive) | main checkout `data/cache/rain/` (the forecast's cache) for 207 of the 336 rain cells; `data/cache/rain_nine/` (written by `scripts/fetch_rain_nine.py` with the same request code) for the other 129 | Every cell has a whole-year file for 2024 and 2025, and every hour from 1 April to 30 September of both years has a value |
| The production spill model and lead calibration | committed `data/processed/spill_model.pkl` (MD5 `808da63d`), `lead_calibration.json` (MD5 `9b3cc24c`) | The same two files CATCH-SIM ran, and the stamp on the last logged forecast. Fitted on United Utilities 2023 to 2025 ("United Utilities 2023-2025 (refit on all years; verified on 2025 before refit)", the model's `trained_on`) |
| A hindcast of daily chances and spot levels | `scripts/lab_catch_sim.py` (CATCH-SIM, PR #588), `Hindcast` class | Two spots only, 2024 and 2025, whole years. Its committed series are the reproduction target below |
| The forecast log | the `state` release | Chances per overflow from 12 October 2026 only. Not used |

So two past seasons can be rebuilt with no fetch: **2024 and 2025**. The 2026 season cannot yet: no record held here
covers September 2026 for most companies, and the 2026 parquets are not in the main checkout.

Before writing this I counted, per company and year, how many of the ledger's overflows have at least one EA event in
each season window, and I checked the rain files for gaps. Those are input counts. No spill day total, chance or
level was computed for any season.

## The seasons and the rows

- **Seasons.** 15 May to 30 September, local days (Europe/London), 139 days. **2025 is the headline.** 2024 is the
  second season, shown beside it so a reader can see how much a figure moves between years. Two seasons are a spread,
  not an interval.
- **Rows.** The 1,414 overflows and 2,099 links of `data/research/overflow_ledger.v1.json`, read from that file and
  hashed. Each link's weight and travel time are the file's (the exhibit 2 export of 17 November 2026, rounded there
  to 5 decimals and 0.1 hours). The 89 spots with overflows get figures. The 29 with none and the 3 off the mapped
  rivers are listed with no figure, and are not called clean.

## Each overflow's spill state on each day

Two sources. Each overflow uses one of them in a given season.

**Recorded.** 1 on a day the EA start/stop file holds an event at the overflow, else 0. A day is a UTC day touched by
an event, as `features.spill_days` counts it for the model's training labels, placed on the local day of the same
date. A record is **usable** for a season when all three hold:

1. its company's EA file for that year is held and covers 15 May to 30 September (all ten companies, both years);
2. that year's annual return gives the overflow EDM operational for 90% of the year or more;
3. the file holds at least one event at it that year, or the return gives it 0 spills that year. A return with spills
   but no event in the file means the two disagree on the id, so the record is not used.

**Modelled.** CATCH-SIM's base hindcast, by calling its code: `lab_catch_sim.Hindcast`. The production spill model on
the archive rain of the overflow's cell, with the covariates of the annual return of the year before, and lead-0
calibration. Three things differ from CATCH-SIM's run:

- the day grid starts on 1 May, 14 days before the season, more than the longest travel time (152.5 hours) needs;
- each overflow's company is its own, where CATCH-SIM had one company a spot;
- the rain is read for the season's year and the year before. For 2024, 200 cells have a whole 2023 file, 130 have
  December 2023 only and 6 start on 1 January 2024. The 30-day sum is complete by 1 May in every case, and what the
  antecedent index (daily decay 0.85) keeps of rain before 1 January is below 0.85^120, about 3 in a billion.

A missing covariate is filled as CATCH-SIM's code fills it: the company's median over the overflows in the run (here
all 1,414), then the run's median. That differs from the forecast, which fills over the whole overflow table.
Overflows filled: 51 for 2025 and 62 for 2024. They are marked in the file.

**Coverage of usable records (input counts):**

| Company | 2024 usable | 2025 usable | Ledger overflows |
|---|---|---|---|
| Anglian Water | 165 | 168 | 178 |
| Dŵr Cymru Welsh Water | 37 | 37 | 40 |
| Northumbrian Water | 15 | 20 | 26 |
| Severn Trent Water | 234 | 243 | 264 |
| South West Water | 29 | 30 | 33 |
| Southern Water | 99 | 103 | 120 |
| Thames Water | 187 | 189 | 198 |
| United Utilities | 140 | 136 | 148 |
| Wessex Water | 232 | 243 | 285 |
| Yorkshire Water | 107 | 108 | 122 |
| **All** | **1,245 (87% of link weight)** | **1,277 (90% of link weight)** | **1,414** |

Of the usable records, 110 (2024) and 169 (2025) are overflows with no event in the file and 0 spills in the return.
They count as recorded with no spill day.

## The spot's level on each day

At each spot, the overflows' daily states go through CATCH-SIM's `Hindcast.risk`, which applies the forecast's own
rule: each state is moved later by its travel time and the spot's risk is `1 − Π(1 − w·p)`. The level comes from the
page's cuts on the shown score (15, 40, 70). **High level** means high or very high: a shown score of 40 or more.
This script holds no transport code of its own. The weights come from ledger v1, and the combination from CATCH-SIM.

Two runs for each season:

- **Run A, recorded where usable (the headline).** Usable overflows take their recorded states. The rest take their
  modelled chances. A spot whose overflows all have usable records is wholly recorded. Each spot's share of link
  weight on records is in the file.
- **Run B, modelled throughout.** Every overflow takes its modelled chance. This is the forecast's own view of the
  season from rain, and it is the run checked against CATCH-SIM.

## The season figure

For each overflow, season and run, CATCH-SIM's removal rule at every spot it reaches: its state is set to 0 on every
day, and the spot's level is recomputed.

- **`high`, the season figure:** spot-days at high level or above with every overflow, and below high with this
  overflow taken out. Added over the spots it reaches. Units: spot-days.
- **`moderate`, a second figure fixed now:** spot-days at moderate or above with every overflow, and low with this
  overflow taken out. It is fixed before the run so that a season with few high days cannot lead to a threshold
  chosen afterwards.
- **`lowered`:** spot-days whose level falls at all, as CATCH-SIM reports for its two spots.

Beside them, per overflow and season: recorded spill days in the season (usable records only, else null), expected
spill days (the sum of the modelled chances, for every overflow), and which source run A used.

Per spot, season and run: days at high level or above, and how many of those no single removal brings below high.

**These figures do not add up.** A day that needs two overflows together counts once at each. A day that three
overflows each reach alone counts at none of them. So an overflow's figure is not a share of a spot's days, and the
overflows' figures at one spot do not sum to its days.

## Recorded and modelled, said plainly

| Part | Recorded or modelled |
|---|---|
| Which days an overflow spilled, where the record is usable | Recorded by the company's monitor, published by the EA |
| Which days an overflow spilled, elsewhere | Modelled, from rain |
| Which spots an overflow reaches, its weight and travel time | Modelled (the forecast's network, river speed, T90 and dilution) |
| The spot's risk, its level and every spot-day count | Modelled. No sample is joined. No spot-day is observed water |

## Limits known before the run

- Companies define an event differently (`ea_events_summary.csv`: median length 0.03 to 1.25 hours by company and
  year; Yorkshire Water joins events into fewer, longer ones). A spill day is less affected than an event count, but
  recorded days compare better within a company than across.
- A recorded spill day is a UTC day; the grid is local days. In summer the two differ by one hour.
- A recorded day is 1 however long the spill. The model has no volume and neither does this.
- Weights and travel times are fixed, as in the forecast. A real spill moves faster in a flood.
- The modelled chance for United Utilities' overflows is in-sample for both seasons.

## Checks

1. **Inputs.** SHA-256 of every shared input before and after. The run fails if one changed. Nothing is fetched. A
   scratch `DIPCAST_ROOT` and `DIPCAST_STATE` hold copies of the three committed model files. The run fails if any
   other file appears in the scratch root.
2. **No missing day.** Every overflow has a modelled chance on every day of each grid. The run fails if not.
3. **Removal never raises a level.** Checked on every spot-day, run and season. The run fails if it does.
4. **Reproduction.** Run B's levels at Cromwheel (`bw-uke4100-08901`) and Waterhead (`osm-windermere-waterhead`),
   15 May to 30 September 2024 and 2025, against CATCH-SIM's committed series
   (`prototypes/research-lab/workspace/whatif/data/{cromwheel,waterhead}.json`, rain x1.0, nothing removed).
   **Pass:** every level equal, every shown score within 1 point, and at least 99% of shown scores equal. The
   tolerance is for the export's rounding of travel times to 0.1 hours; CATCH-SIM used the log's unrounded values.
   The weights already agree to 5 decimals at all 20 links.
5. **The file adds up.** Each overflow's figures equal the sum of its per-link counts, and each spot's counts match
   its links (`--check`, and a test).

## Reported beside the figures, deciding nothing

- Per company and season: recorded spill days ÷ expected spill days over the overflows with usable records. For
  United Utilities this is in-sample: the model was fitted on those years. For the other nine companies the model never
  saw these spills, but earlier tests here did. It is a description, not a calibration test.
- Per spot: high days in run A and in run B.
- Spearman correlation of the overflows' `high` figures, run A against run B, and 2024 against 2025, over overflows
  with a figure above 0 in either.

## What it will claim, and what it will not

- **May say:** "In the 2025 bathing season, by the forecast model's weights and the EA's recorded spill days, this
  overflow's spills took N spot-days at listed swim spots to the model's high level that would otherwise have been
  below it." With "modelled from rain" in place of "recorded" where the record was not usable.
- **May not say:** that any spot-day had bad water, or any sample result. Any share of the bacteria at a spot. That an
  overflow or company broke a permit or a rule. How much an overflow discharged. Anything ranking companies. That the
  model's level is right: at 59 unseen river points the production estimate ordered a point's days at 0.376, against
  0.355 for rain alone (`docs/RIVER-UNSEEN-PROTOCOL-2026-11.md`).
- Every figure is labelled "an account of the model, not of measured bacteria", as in v1.

## What follows each outcome

| Outcome | Next |
|---|---|
| Checks 1 to 5 pass | The season file and its contract are committed. Next deliverable: the season figure in the prototype page, still left out of the build. Then the Ilkley audit, on or after 2 December 2026 |
| Check 4 fails | The file is written with the failure stated, and no page shows the figure. Next deliverable: the cause, found by comparing day by day with CATCH-SIM's inputs |
| Run A and run B disagree a lot: a company's recorded ÷ expected outside 0.5 to 2, or the A-to-B correlation below 0.5 | Run A stays the headline where records are usable. Next deliverable: a diagnosis of which overflows and companies carry the gap. No change to the forecast follows from this record |
| 2024 and 2025 correlate below 0.5 | Both seasons are shown and a single season's figure is called unstable in the record and the contract |
| Any outcome | The register row and catalogue entry are updated in this PR. The 2026 season is added when the EA's full 2026 file is held |

## Budget and what is not touched

Offline. At most 1 CPU-hour on 4 cores. Zero Open-Meteo calls, zero EA requests, zero other fetches. Not touched:
ledger v1's file, contract and script; `docs/RESTORE-ILKLEY-STATEMENT-2026-11.md`; option B's files; every frozen
window; `data/eval2027/`; the forecast model and its calibration; the main checkout's caches, which are read only.
The output goes to `data/research/overflow_ledger_season.v1.json` with its own contract. Nothing is published: the
prototype page stays in `build_site.LAB_UNPUBLISHED`, and the new file is not in `LAB_DATA`.

---

## Results (run 19 November 2026, after the statement was pushed in c06bc356 and the code in 073372d6)

Development evidence on seen data. One run of `scripts/export_overflow_ledger_season.py` at 073372d6, 77 seconds on one
core, 20:42 to 20:44 UTC. The 10 EA event files, 1,002 rain files, the committed model, calibration and returns,
ledger v1 and CATCH-SIM's two series files were hashed before and after: unchanged. Nothing was fetched. No file was
written into the scratch root other than the two model copies. File: `data/research/overflow_ledger_season.v1.json`
(250 kB). Nothing above this line was changed after the run.

### Checks

| Check | Result |
|---|---|
| 1. Inputs | Passed |
| 2. No missing day | Passed: every overflow has a chance on all 153 grid days in both seasons |
| 3. Removal never raises a level | Passed |
| 4. Reproduction | **Failed as stated.** Cromwheel 2025: 139 of 139 levels equal, 137 of 139 shown scores equal, largest difference 1 point. The rule asked for at least 99% equal, which is 138 of 139. Cromwheel 2024 and Waterhead in both seasons: every score equal |
| 5. The file adds up | Passed (`--check` and the tests) |

**The cause of check 4 (the statement's next step for a fail, done here).** I rebuilt Cromwheel 2025 in run B with the
forecast log's unrounded weights and travel times, the values CATCH-SIM used. The log is the copy CATCH-SIM read
(SHA-256 `3d8e70c9…`), hashed before and after: unchanged. Established:

- With the log's travel times, 139 of 139 shown scores equal CATCH-SIM's. With ledger v1's weights and the log's
  travel times, also 139 of 139.
- Ledger v1 rounds travel times to 0.1 hours (largest difference from the log 0.049 hours). That moves the risk by
  0.00008 on 11 June 2025 (0.46443 against 0.46451) and by 0.00013 on 11 September 2025 (0.41457 against 0.41445).
  Both days sit at a rounding edge of the shown score, so the score moves by 1 point. No level moves.

So the season code reproduces CATCH-SIM day for day, and the difference comes from the export's rounding. The
tolerance I set allowed one such day in 139, and two occurred. The verdict stays "failed as stated" and the threshold
is not changed. As the statement says, no page shows the figure. Whether to accept the diagnosis is Ethan's call
(below). How many spot-days at other spots sit within rounding of a level cut is not measured.

### Corrections to the statement's input counts

- **Covariates filled: 57 for 2025 and 156 for 2024, not 51 and 62.** The statement counted only overflows absent from
  the return. CATCH-SIM's code also fills a gap inside a return row: 6 overflows for 2025, and 94 for 2024, 89 of
  which have no long-term average in the 2023 return. They are marked in `covariates_filled`.
- Usable records: 1,277 for 2025 and 1,245 for 2024, as stated. Every company's file covers both seasons.
- Events over 60 days at used records that touch a season: none, so the training label's 60-day cap changed nothing.

### The season figure

Run A, recorded where usable (the headline):

| | 2025 | 2024 |
|---|---|---|
| Spot-days at high level or above, all spots | 986, at 52 of 89 spots | 1,276, at 67 |
| Of those, days no single removal brings below high | 588 (60%) | 768 (60%) |
| Overflows with a `high` figure above 0 | 182 of 1,414 | 311 |
| Those figures added | 671 | 964 |
| Largest figure; median of those above 0 | 35; 2 | 34; 2 |
| Recorded spill days in the season, used records | 6,438 (median 1 an overflow; 488 with none) | 10,904 (median 7; 188 with none) |

Run B, modelled throughout: 925 high spot-days at 49 spots in 2025 and 1,139 at 58 in 2024. 354 and 419 overflows have
a figure above 0.

At Cromwheel, run A gives 21 high days in 2025 (16 of them need two or more overflows out) and run B gives 39. In 2024,
26 and 38. Waterhead has no high day in either run or season.

**What this shows (established, from the file).** In run A, 60% of the spots' high days need two or more overflows
taken out before they fall below high, in both seasons. The removal rule puts those days down to no overflow. So an
overflow's season figure counts only the days it carries alone. At a spot with many overflows it leaves most high
days out.

### Reported beside the figures, deciding nothing

Recorded ÷ expected spill days over used records, by company:

| Company | 2025 | 2024 |
|---|---|---|
| Anglian Water | 0.76 | 1.68 |
| Dŵr Cymru Welsh Water | 1.15 | 1.40 |
| Northumbrian Water | 1.35 | 1.21 |
| Severn Trent Water | 1.41 | 1.48 |
| South West Water | 1.08 | 1.13 |
| Southern Water | 1.26 | 1.62 |
| Thames Water | **0.18** (136 recorded, 745 expected) | 1.16 |
| United Utilities (in-sample) | 1.00 | 0.91 |
| Wessex Water | 0.71 | 1.15 |
| Yorkshire Water | 1.14 | 1.39 |

Spearman correlation of the overflows' `high` figures: run A against run B 0.14 (2025) and 0.11 (2024); 2024 against
2025 in run A 0.18.

### What the outcomes lead to, as stated

- **Run A and run B disagree a lot** (correlations 0.14 and 0.11, and Thames 2025 at 0.18, outside 0.5 to 2). Run A
  stays the headline where records are usable. Next deliverable: a diagnosis of which overflows and companies carry the
  gap. No change to the forecast follows from this record.
- **2024 and 2025 correlate at 0.18, below 0.5.** Both seasons are shown, and a single season's per-overflow figure is
  called unstable here and in the contract.
- **Check 4 failed.** No page shows the figure. The cause is found (above).

### A first look at the gap (added after the run, exploratory)

- **Spots agree; overflows do not.** Over the 89 spots, the high days of run A and run B correlate at 0.90 (2025) and
  0.88 (2024). The two runs agree on which spots have high days. They disagree on which overflow a high day is put
  down to.
- In 2025, 218 overflows have a figure in run B only. 202 of them have usable records and 68 recorded no spill day in
  the season. Their median is 2 recorded days against 4.5 expected. 46 overflows have a figure in run A only, with a
  median of 9 recorded days against 3.5 expected.
- Why Thames recorded so few spill days in summer 2025 against the model's expectation is not checked. A dry summer,
  overflow upgrades and gaps in the records are candidates (inferred).

### Established and inferred

- **Established (from the file and the diagnosis run):** the figures above; the season code gives CATCH-SIM's levels
  at both spots in both seasons and its scores exactly once rounding is removed; 60% of high spot-days depend on no
  single overflow; the per-overflow figure correlates at 0.18 between seasons and 0.11 to 0.14 between runs; spot
  high days correlate at 0.88 to 0.90 between runs.
- **Inferred, not checked:** that the per-overflow figure's instability comes mostly from days that need several
  overflows together and from the difference between a certain recorded spill and a fractional chance; the Thames
  candidates above; that the 0.1-hour rounding moves few levels at other spots.

### Limits

- The level is the model's. No sample is joined, and the chain's support at rivers is weak (0.376 against 0.355).
- Weights and travel times are v1's, from the overflow table of 30 October 2026, for both seasons. Upgrades between
  2024 and 2026 are not in them.
- Recorded days compare better within a company than across. United Utilities' modelled chances are in-sample.
- Two seasons are a spread, not an interval.

### Needs Ethan (not decided here)

1. **Check 4.** Accept the diagnosis (the export's 0.1-hour rounding, with every level equal) and let the season figure
   go onto the prototype page, still unpublished. Or ask for a rebuild with unrounded travel times first, which needs
   exhibit 2's export to carry more decimals, a change outside the ledger.
2. **What a page shows.** The per-overflow figure is unstable (0.18 between seasons). Spot high days are steadier
   between runs (0.88 to 0.90). A page could show spot high days per season, with each overflow's recorded spill days
   and its `high` figure beside them, labelled as one season's model accounting.

### Next (register row)

| Field | Content |
|---|---|
| Identity | LEDGER stage 2; Claude session for Ethan; this PR; `scripts/export_overflow_ledger_season.py`, `data/research/overflow_ledger_season.v1.json`, [contract](OVERFLOW-LEDGER-SEASON-CONTRACT-v1.md) |
| Evidence | Development, seen data. Check 4 failed as stated (137 of 139 scores at Cromwheel 2025; cause: rounding; every level equal). Per-overflow figure unstable: 0.18 between seasons, 0.11 to 0.14 between runs. 60% of high spot-days depend on no single overflow |
| Stage and claim | Exploration, research file, not published. Claim: in a named past season, the spot-days the model would have put at high with an overflow and below high without it |
| Next deliverable | The gap diagnosis the statement names: which overflows and companies carry the difference between runs A and B, Thames 2025 first, from the same file and inputs, by 15 December 2026. Then the Ilkley audit on or after 2 December 2026 |
| Release route | Ethan's two decisions above. Rollback: delete the season file, its script, contract and tests |
