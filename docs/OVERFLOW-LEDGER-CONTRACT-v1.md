# The overflow ledger: the data contract, version 1

Written 17 November 2026, register row **LEDGER** (`docs/RESEARCH-RECOVERY-2026-10.md`), route "bounded exploration"
(`docs/RESEARCH-WORKFLOW.md`). Produced by `scripts/export_overflow_ledger.py`. Checked by the same script
(`--check`) and by `tests/test_overflow_ledger.py`. File: `data/research/overflow_ledger.v1.json` (222 kB, 71 kB
gzipped). The record of how it was made is [OVERFLOW-LEDGER-2026-11.md](OVERFLOW-LEDGER-2026-11.md).

The file is not copied into the site build and no published page reads it. Whether it is published is Ethan's decision.

## What it is

An account of the forecast model. For each monitored storm overflow, it adds up the weight the model gives that
overflow at every listed swim spot it reaches.

The script makes no exposure calculation of its own. Each weight is the forecast's own, as Research Lab exhibit 2
exports it (`scripts/lab_pollution_paths.py` `export`, which calls `transport.upstream_overflows` with the production
settings). The ledger reads that export and adds.

## What it may and may not say

- **May say:** how many listed spots the model traces an overflow to; that overflow's weights added over those spots;
  its largest weight; the Environment Agency's long-term average spill count for it; the product of the two.
- **May not say:** that an overflow caused a sample result, or any share of the bacteria at a spot. That an overflow or
  a company broke a permit or a rule. How much an overflow discharged. That the weights match real water.
- **The weight is a factor, not a share.** It is survival times a dilution factor, from 0 to 1. Dilution lowers
  concentration by mixing and removes no bacteria. The exhibit 2 record corrected this wording on 1 November 2026
  (`docs/POLLUTION-PATHS-EXHIBIT-2026-11.md`), and the same rule holds here.
- **The evidence for the chain at rivers is weak.** At 59 river points no model here had seen, the production estimate
  ordered a point's days at 0.376. Rain in the last 48 hours alone gave 0.355
  (`docs/RIVER-UNSEEN-PROTOCOL-2026-11.md`, read 16 November 2026). `claim.evidence` carries this, and a page shows it
  beside the figures.
- `claim.public_wording` goes beside the figures. `claim.not_claimed` lists what no row says.
- The totals by company depend on which spots SwimSignal lists. They do not compare companies.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version` | `"swimsignal.overflow-ledger"`, `"1.0.0"` |
| `generated_at`, `stage` | export time; "exploratory: model accounting, not a measurement and not a test" |
| `source_export` | the exhibit 2 export it was added up from: when made, its settings (river speed, T90, dilution mode, lake path mode, trace limit) and its named inputs |
| `inputs` | the shared caches the export read, each with its SHA-256 and `unchanged_after` |
| `code_sha256` | the script's own hash |
| `attribution` | the export's credit lines, carried through unchanged |
| `claim` | `public_wording`, `not_claimed`, and `evidence` (text, record, date read) |
| `definitions` | each figure in words, and why no season figure is made |
| `coverage` | spots listed, with overflows, with none, off the mapped rivers; overflows; links; overflows reaching one spot; overflows with no average; groups |
| `spots` | every listed spot in list order: `id`, `name`, `kind`, `area`, `status` (`traced`, `no_overflow`, `off_network`, `error`), `overflows`, `weight_sum`. Other fields index into this list |
| `companies` | company names; `overflows.company` indexes into it |
| `company` | per company: overflows traced, links, spots reached, summed weight, weighted spills a year, overflows with no average |
| `groups` | spots joined by a shared upstream overflow: `id`, `name` (the spot with most overflows), `spots`, `overflows`, `links` |
| `overflows` | one column per field, same order in each, largest summed weight first (below) |

Overflow columns:

| Column | Meaning |
|---|---|
| `site_id`, `name`, `company`, `water`, `lat`, `lon` | the overflow as the Environment Agency's annual return names and places it. `name` and `water` are null where the return gives none |
| `spills_a_year` | the EA's long-term average spill count from the latest return in the overflow table. A count of spills, not days and not volume. Null where the return gives none |
| `spots_reached` | listed spots with this overflow upstream within the trace limit |
| `weight_sum`, `weight_max`, `max_spot` | its weights added over those spots; the largest; the spot where it is largest |
| `top_at` | spots where it has the largest weight of all the spot's overflows |
| `weighted_spills` | the year figure: `spills_a_year` times `weight_sum`. Null where there is no average, never 0 |
| `group` | the group it belongs to |
| `links` | each spot reached: `[spot, weight, travel_h]`, largest weight first |

## The year figure, and the season figure that is not made

The brief asked for a season figure such as modelled high-level spot-days. Version 1 does not make one.

- **What the existing outputs support (established).** The export holds a weight and a yearly average for each link.
  So the ledger can give `weighted_spills`: the model's long-run accounting for an average year.
- **What they do not support.** A count of spot-days at a level needs each overflow's chance on each day of a season.
  The forecast log holds those only from 12 October 2026 (`docs/CATCH-SIM-2026-12.md`, "Reproduction"), after the
  bathing season. A season hindcast would be a second calculation. CATCH-SIM ran one at two spots.
- `weighted_spills` is not a count of days at any level. A spill count is the EA's count for the year, not for the
  bathing season.

## Credits and licences

- Contains OS data © Crown copyright and database right 2026 (OS Open Rivers, Open Government Licence v3.0).
- Overflow names, positions and annual spill counts: Environment Agency Event Duration Monitoring returns, Open
  Government Licence v3.0.
- No company event history is in the file. Southern Water's and Yorkshire Water's event histories carry no licence
  and are not used.

## Rules for a page that shows it

- The page's first screen says "An account of the model, not of measured bacteria".
- Every table says its figures are model weights, not measurements.
- The evidence line (0.376 against 0.355) is shown with the figures, not in a fold.
- No ranking word: no "worst", no "polluter", no "responsible". The order is by summed weight and says so.
- A spot with no overflow traced is not called clean. An overflow not in the file is not called harmless.

## Limits

- The overflow table is the main checkout's cache of 30 October 2026. A site build makes its own.
- Weights use a fixed river speed. A real spill moves faster in a flood and slower in a dry spell.
- A spot is one of 121 that SwimSignal lists. An overflow upstream of no listed spot is absent, whatever it does.
- The 60 km trace limit drops overflows further upstream. How much weight that drops is not measured.

## Changing it

A new field is a minor version. Renaming or removing one is version 2. A season figure, when one is made, is a minor
version with its own definition here.
