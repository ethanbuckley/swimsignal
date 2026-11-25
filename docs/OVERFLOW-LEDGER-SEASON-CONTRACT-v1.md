# The overflow ledger's season figure: the data contract, version 1

Written 19 November 2026, register row **LEDGER** (`docs/RESEARCH-RECOVERY-2026-10.md`), route "bounded exploration"
(`docs/RESEARCH-WORKFLOW.md`). Produced by `scripts/export_overflow_ledger_season.py`. Checked by the same script
(`--check`) and by `tests/test_overflow_ledger_season.py`. File: `data/research/overflow_ledger_season.v1.json`. The
statement, pushed before the run, and the record of the run: [OVERFLOW-LEDGER-SEASON-2026-11.md](OVERFLOW-LEDGER-SEASON-2026-11.md).

The file is not copied into the site build (it is not in `build_site.LAB_DATA`) and no published page reads it.
Ethan decided on 19 November 2026 that the ledger stays an unpublished Lab prototype.

## Why a separate file

Ledger v1 ([contract](OVERFLOW-LEDGER-CONTRACT-v1.md)) adds up the model's weights. This file is a second calculation:
a hindcast of two past bathing seasons, with its own inputs (archive rain, EA spill records, the spill model). So it
has its own schema and version. Ledger v1's file, contract and script are unchanged. This file names the v1 file it
was built on, with its SHA-256, and lists overflows and spots in v1's order.

## What it is

An account of the forecast model for two past bathing seasons. For each monitored overflow in ledger v1, it counts the
spot-days at the listed spots it reaches when the model's level was high with the overflow and below high without it.

- Each overflow's daily state is its **recorded** spill day (EA start/stop file) where the record is usable, and
  its **modelled** chance from archive rain elsewhere (run A). Run B uses the modelled chance throughout.
- The weights and travel times are ledger v1's: the exhibit 2 export of the forecast's own.
- The modelled chance, the spot's risk and the removal rule are CATCH-SIM's (`scripts/lab_catch_sim.py`, `Hindcast`),
  called and not copied. The script holds no transport code; a test checks that.

## What it may and may not say

- **May say:** in the 2025 (or 2024) bathing season, by the forecast model's weights and the EA's recorded spill days,
  this overflow's spills took N spot-days at listed swim spots to the model's high level that would otherwise have
  been below it. "Modelled from rain" replaces "recorded" where the record was not usable.
- **May not say:** that any spot-day had bad water, or any sample result. Any share of the bacteria at a spot. That an
  overflow or a company broke a permit or a rule. How much an overflow discharged. Any comparison or ranking of
  companies. That the model's level is right.
- **The figures are not shares and do not add up.** A day that needs two overflows together counts at each. A day that
  several overflows each reach alone counts at none. `high_no_single` gives how many of a spot's high days are like
  that.
- **The evidence for the chain at rivers is weak.** At 59 unseen river points the production estimate ordered a
  point's days at 0.376, against 0.355 for rain alone (`docs/RIVER-UNSEEN-PROTOCOL-2026-11.md`). `claim.evidence`
  carries this, and a page shows it beside the figures.
- `claim.public_wording` goes beside the figures. `claim.not_claimed` lists what no row says.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version` | `"swimsignal.overflow-ledger-season"`, `"1.0.0"` |
| `generated_at`, `stage` | run time; "development: model accounting from a hindcast of past seasons; not a measurement, a test or a confirmation" |
| `statement` | the statement's path and the commit that pushed it before the run |
| `code_commit`, `code_sha256`, `catch_sim_sha256` | the commit the run was made from, this script's hash, `lab_catch_sim.py`'s hash |
| `ledger` | the v1 file built on: path, SHA-256, version, when made |
| `inputs` | each EA event file with its SHA-256; the committed model, calibration and returns (SHA-256 and MD5); the rain files (count by cache and one SHA-256 over every file's hash); CATCH-SIM's two series files; `unchanged_after`; `fetches` |
| `attribution` | v1's credit lines, then the EA's, Open-Meteo's and Copernicus's |
| `claim` | `public_wording`, `not_claimed`, `evidence` |
| `definitions` | every figure in words |
| `checks` | `inputs_unchanged`, `no_missing_day`, `removal_never_raised` (each must be true) and `reproduction` (below) |
| `comparison` | descriptive, deciding nothing: per season and company, recorded ÷ expected spill days over usable records; Spearman correlations of `high`, run A against run B and 2024 against 2025 |
| `companies` | v1's company names; `overflows.company` indexes into it |
| `spots` | v1's spots in v1's order: `id`, `name`, `status`, `overflows`, and per season a block, null where the spot has no overflow (below) |
| `overflows` | `site_id` and `company`, in v1's order. Names and places are in v1 |
| `seasons` | per season, `"2025"` and `"2024"`, the overflow columns below |

A spot's season block: `weight_share_recorded` (the share of its link weight on usable records), then for each run,
`recorded` and `modelled`: `high_days`, `high_no_single`, `moderate_days`.

## Season columns

Each column is a list in v1's overflow order, or a pair of lists keyed by run (`recorded` for run A, `modelled` for
run B).

| Column | Meaning |
|---|---|
| `first_day`, `last_day`, `days` | the season: 15 May to 30 September, 139 local days |
| `records` | per company: first and last event in that year's EA file (every overflow in it), and whether it covers the season |
| `usable`, `covariates_filled_count`, `events_over_60_days` | how many records are used; how many overflows had a covariate filled; events longer than 60 days at used records that touch the season (the training label counts only their first 60 days) |
| `source` | `recorded` or `modelled`: which state run A used for this overflow |
| `spill_days` | recorded spill days in the season where the record is used; null elsewhere, never 0 |
| `expected_days` | the sum of the modelled daily chances over the season, for every overflow |
| `covariates_filled` | true where a covariate of the return of the year before was missing and filled |
| `high` | **the season figure**: spot-days at high or very high with every overflow, below high with this one taken out |
| `moderate` | spot-days at moderate or above with every overflow, low with this one taken out |
| `lowered` | spot-days whose level falls at all with this one taken out |
| `links` | per spot reached, in v1's link order: `[spot, high A, high B, moderate A, moderate B, lowered A, lowered B]` |

`high`, `moderate` and `lowered` are the sums of their links. At each link `lowered` is at least `high` and at least
`moderate`.

## The reproduction check

`checks.reproduction` compares run B's season at Cromwheel and Waterhead with CATCH-SIM's committed series (rain x1.0,
nothing removed) for each season: days, levels equal, shown scores equal, the largest score difference, and the high
days in each. It passes when every level is equal, every shown score is within 1 point and at least 99% are equal.
The tolerance is for the export's rounding of travel times to 0.1 hours.

## Credits and licences

- Contains OS data © Crown copyright and database right 2026 (OS Open Rivers, Open Government Licence v3.0).
- Overflow names, positions and annual returns; spill events: Environment Agency Event Duration Monitoring data, Open
  Government Licence v3.0. No company's own event history is used.
- Weather data by Open-Meteo.com (CC BY 4.0). Contains modified Copernicus Climate Change Service information 2026
  (ERA5-Land).

## Rules for a page that shows it

v1's rules hold, and these:

- Every figure says which run it is from, and a recorded figure says where the record was not usable.
- No figure is shown as a share or a percentage of a spot's days.
- A season is always named. One season's figure is not called typical.
- **A single season's per-overflow figure is unstable.** In the run of 19 November 2026 the overflows' `high` figures
  correlated at 0.18 between 2024 and 2025 (run A), and at 0.14 (2025) and 0.11 (2024) between runs A and B. A page
  shows both seasons and says so. The statement fixed this rule before the run, for a correlation below 0.5.
- Most high spot-days count at no overflow: 60% in both seasons need two or more overflows out. A page says so beside
  the figures.
- Until Ethan accepts the diagnosis of the reproduction check (`checks.reproduction.passed` is false: the export's
  rounding of travel times, every level equal), no page shows the figure.

## Limits

- Weights and travel times are fixed and are v1's, from the overflow table of 30 October 2026, for both seasons.
- A recorded spill day is a UTC day placed on the local day of the same date, and is 1 however long the spill.
- Companies define an event differently. Recorded days compare better within a company than across.
- The modelled chance for United Utilities' overflows is in-sample: the model was fitted on its 2023-25 spills.
- Two seasons are a spread, not an interval.

## Changing it

A new field or a new season is a minor version. Renaming or removing one is version 2. A rerun with new inputs
records them in `inputs` and keeps this version only if every definition is unchanged.
