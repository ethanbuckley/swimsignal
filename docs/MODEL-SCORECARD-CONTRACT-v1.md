# Model scorecard: data contract, version 1

Written 31 October 2026. The file is `data/research/model_scorecard.v1.json`, schema `swimsignal.model-scorecard`,
made by `scripts/export_model_scorecard.py`. The site copies it to `data/research/model_scorecard.json` and shows it on
`models.html` (`build_site.write_model_scorecard`), linked from Research. Register: the line under "Active or
scheduled" in [the recovery register](RESEARCH-RECOVERY-2026-10.md).

## Why

One public place where each forecast model or candidate shows its evidence and stage, so a model reaches the main
forecast only after it earns its place, and one that cannot beat a simple reference visibly stays in the lab. It adds
no test, changes no window, threshold or verdict, and reads no score from a running test.

## What it covers

The live forecast, every running or scheduled test in the register's "Active or scheduled" table that predicts
spills (regional routing `shadow_regional_v1`, live-status shadow, lead calibration B, company calibration A8,
ensemble rain D4, upgraded overflows option B, winter recalibration), spill duration (in the lab), and the 2027
primary evaluation, as not started. River rises and missing event ends are not forecast models and are left out.

## What the file holds

| Field | Content |
|---|---|
| `as_of` | The export's date. The check compares read dates with it |
| `claim` | `public_wording`, the page's lead, and `not_claimed` |
| `stages`, `data_kinds`, `measures` | What each stage, kind of rows and measure means, in words |
| `counted_from` | Where row counts came from, or null |
| `models[]` | One per model, below |
| `sources` | The register, and the export script's SHA-256 |

Each model: `id`, `name`, `stage` (`live`, `shadow`, `scheduled`, `lab`, `not_started`), `predicts`, `tested`,
`reference`, `results[]`, `verdict` (or null), `misses`, `wrong`, `window` (`start`, `end`, `read_on`, `rule`,
`extension`; or null), `milestones` (optional), `log` (table and filter; with `rows`, `first`, `last` once counted),
`how` (optional: what is logged where there is no separate log), `show` (`shown`, `why`), `records[]`.

Each result: `label`, `measure` (Brier, ECE or Skill), `model`, `reference` (null for a skill, which is already
against its reference), `reference_name`, `difference`, `interval` (95%, as the record gives it, or null), `data`,
`note`, and `quote` and `source`: the record's own words holding the figure, and its file. A verdict has `quote`,
`source` and `plain`, the page's sentence.

`data` is one of: `held_out` (rows the model never saw), `seen` (rows that chose or built it: a direction only),
`live` (SwimSignal's own scored forecasts), `pre_window` (live rows from before its window: not deciding),
`prospective` (inside its window).

## The rules the check enforces

1. **Figures cannot drift from their records.** Every `quote` must appear in its `source` file, with bold and code
   marks dropped and white space collapsed. A changed figure, or a verdict reworded, fails the check.
2. **No score from a running window before its read.** A result with `data` `prospective` fails the check while
   `as_of` is before its model's `read_on`. The build also drops one before its own date, whatever the file holds.
3. A `shadow` or `scheduled` model has a window with a read date, in order. The 2027 evaluation has no results.
4. Every model says whether a result is shown, and why.

## Row counts

With `--state` the export opens a copy of the state release's `dipcast.duckdb` read only and counts the rows each
logged test has written so far (`shadow_regional_v1`; `forecast_overflows` rows with `p_status`, or with
`p_cal_members`), with the first and last issue time. Counts only: no forecast or outcome column is read. Lead
calibration B, A8, upgraded overflows B and winter recalibration log nothing of their own; their candidates are
worked out at the read from the live forecast's own rows, and the page says so. The committed counts come from the
state release of 31 October 2026, 13:26 UTC; they are a snapshot and say so by their dates.

## What it may say

The page may show each test's record as written, its stage, its window and read date, and counts of logged rows.
It may not show a score from inside a window before the read date, call a candidate adopted or dropped before its
read, or present a seen-data figure as evidence. A model's figures are past results on the rows they name, not a
promise about tomorrow, and nothing on the page is a water test.

## Keeping it current

The page works out each stage line from the build date, so a closed window says so without a new export. After a
read, add the result with `data` `prospective`, the verdict's quote and its record, change the stage, and bump the
minor version. A new candidate gets a new entry. A new field is a minor version; a renamed or removed field is
version 2.
