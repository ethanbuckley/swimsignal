# River rise history: the observation contract, version 1

Written 6 November 2026, register row **River rises** (`docs/RESEARCH-RECOVERY-2026-10.md`), route "public research
observations" (`docs/RESEARCH-WORKFLOW.md`). It is the deliverable the C3 outcome map fixed for the branch "C3 not
shown better than R1" ([the C3 record](RIVER-RISES-C3-2026-11.md), "Results" and "Continuation"): the gauge-month base
rate as an observation, worded as history. Produced and checked by `scripts/export_river_rise_history.py` from
committed files only (no request); file `data/research/river_rise_history.v1.json` (about 66 kB, 44 gauges). The site
shows one line of it on a river spot's River level tile and links it from the Research page.

## Identity and source

- **What.** For each spot gauge of the river-rises run with a Hydrology series (44 gauges, 18 river systems) and each
  calendar month: the hours counted, how many of them were followed within 3 hours by a rise of more than a fifth of
  the gauge's usual range, the separate rises those hours form, the share, and the years behind the month.
- **Period.** Every whole hour from 21 November 2024 to 24 October 2026. November and December are 2024 and 2025
  (November 2024 from the 21st); January to October are 2025 and 2026 (October 2026 to the 24th).
- **Source.** The record's table `docs/RIVER-RISES-C3-2026-11-base-rates.csv` (made by `scripts/river_rises_eval/c3.py
  observe` from the Environment Agency's archived 15-minute level series on the Hydrology API), and the run's gauge list
  `docs/RIVER-RISES-SCOPE-2026-10-gauges.csv` for each gauge's usual range and the spots it serves. `sources` holds both
  files' SHA-256, the commits that last changed the table and the record, and the export script's SHA-256.

## Definition

- **Usual range.** The Environment Agency's typical range for the gauge (`typicalRangeLow` to `typicalRangeHigh` on its
  stage scale, flood-monitoring API): the range the site's River level tile draws. `typical_low_m`, `typical_high_m`.
- **Hours counted (`hours`).** Whole hours when the gauge had a reading at most 24 hours old, published 1 hour before
  (as the site would have had it), and the site would have shown no word: the level not above its usual range and not
  already "rising fast" (the site's `RISING_SHARE` rule, a rise of more than 0.2 of the range over its recent readings).
- **A quick rise (`rise_hours`).** Of those hours, the ones followed within 3 hours by a reading more than a fifth (0.2)
  of the usual range above the hour's own reading. In words: the river "rose by more than a fifth of its usual range
  within 3 hours".
- **Rises (`rises`).** Runs of consecutive rise hours at the gauge: about one for each separate rise.
- **Share.** `rise_hours / hours`, five places.

## What it may and may not say

- **May say:** how often, in a named calendar month of the named years, an hour at this gauge was followed by a quick
  rise; how many separate rises that was; that a month had none recorded.
- **May not say:** a forecast or warning of a rise; anything about swimming safety or water quality; the level now or
  at the swim spot; that a month with none recorded will have none; anything about other years. No colour, no level
  word and no figure in the tile's figure place.
- `claim.public_wording` goes with the figures where a page shows more than one line.

## Display rule (fixed before any page line was written)

A month is shown only with at least **480 hours counted** (20 days of hours) **and readings in both of its years**
(`display.min_hours`, `display.min_years`). Otherwise the page says nothing for that month. The minimum was chosen on 6
November 2026 from the spread of hours counted (127 to 1,488 a gauge-month), before any line was drafted and without
looking at which spots or months it would drop. It leaves out 29 of the 525 gauge-months, all with one year only; 2 of
them are also under 480 hours. A gauge's missing calendar month (3 of 528: Low Moor's November and December, Salisbury's
February) shows nothing either. In November and December the line can show at 42 gauges serving 50 spots.

On the site (`build_site.attach_rise_history`, `index.html` `riseHistoryLine`): a river spot gets the line only where
its tile's gauge (`river_state.measure`'s station) is the gauge the history is for; lakes never. The line, after the
gauge's sentence, for the device's month: "In November 2024 and 2025, about 1 hour in 80 at this gauge was followed
within 3 hours by a rise of more than a fifth of its usual range (4 rises in all)." The "1 in N" is rounded: whole
numbers under 20, tens under 1,000, hundreds above. A month with none: "In April 2025 and 2026, no hour at this gauge
was followed within 3 hours by a rise of more than a fifth of its usual range." The tile's fold adds which hours are
counted, the period, that it is history and not a forecast, and links the Research page.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version`, `generated_at` | `"swimsignal.river-rise-history"`, `"1.0.0"`, export time |
| `period` | `first`, `last` and which years each month holds (`years_by_month`) |
| `definition` | `words`, `rise_share` (0.2), `horizon_h` (3), `delay_h` (1), and the definitions above |
| `display` | `min_hours` (480), `min_years` (2) and the rule in words |
| `claim`, `limits`, `attribution` | `public_wording` and `not_claimed`; the limits below; the Environment Agency's licence lines |
| `sources` | the record, the table and the gauge list with their SHA-256, commits, and the code's SHA-256 |
| `gauges` | one per gauge: `gauge` (station reference), `label`, `river`, `typical_low_m`, `typical_high_m`, `has_upstream_gauge`, `spots` (the spot ids it serves in the run), `months` |
| `months` | one per calendar month in the table: `month`, `hours`, `rise_hours`, `rises`, `share`, `years_in_month`, `years` (the two years, or null with one) |
| `coverage` | `gauges`, `gauge_months`, `gauge_months_shown`, `spots` |

As exported on 6 November 2026: 44 gauges, 525 gauge-months, 496 shown, 52 spots. The site copies the file whole to
`data/research/river_rise_history.json`; each matched spot's own `data/spot/<id>.json` carries `rise_history` (the
gauge, the period and twelve months, null where nothing is shown).

## Limits

- **Two years at most behind each month.** Two winters are not a climate; a wet or dry year moves a month's figure.
- **Archived, corrected readings.** The Hydrology series are checked and corrected after the fact. The live feed the
  site reads has gaps and errors these do not.
- **Hours already high or rising fast are not counted**, nor hours with no recent reading.
- **A fifth of the range is a different rise in metres at each gauge.** A lock or weir reach can rise with the weir's
  setting rather than the river: Trowlock Island on the Thames is the record's 5.4%, the lock pair, not a river wave.
- **The gauge can be some way from the spot.** The tile names the gauge and its distance; the line says "at this gauge".
- **History, not what tomorrow will do.** The record's model using this history with radar and upstream gauges (C3) was
  not shown better than the history alone (skill 0.077, river-system interval −0.062 to 0.174), and this file makes no
  claim about the next hours.

## Checks

`scripts/export_river_rise_history.py check` and `tests/test_river_rise_history.py`: schema and version, the record's
definition and period, counts in order (rises ≤ rise hours ≤ hours), share = rise hours / hours, years matching the
period, months once each in order, no spot served by two gauges, coverage matching the display rule, and the committed
file equal to a fresh export of the committed table. `tests/site_river_rise_history.test.cjs` checks the page's words.
