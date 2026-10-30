# Spill durations: the observation contract, version 1

Written 30 October 2026, register row **4 / DURATION** (`docs/RESEARCH-RECOVERY-2026-10.md`), route "public research
observations" (`docs/RESEARCH-WORKFLOW.md`). Produced by `scripts/export_spill_durations.py` from the Environment
Agency's 2024 and 2025 start/stop records; checked by the same script and by CI. File:
`data/research/spill_durations.v1.json` (about 150 KB gzipped). The product chat owns where and how it is shown.

## What it may and may not say

- **May say:** how long a given overflow's spills lasted in 2024 and 2025 (typical length, long end, longest); how
  often, across a company's overflows, a spill that had already run some hours was still running hours later.
- **May not say:** when a running spill will end (that is a forecast; the duration tests #459 and #461 have not
  produced one that can be shown); how much was discharged; that a short spill was harmless; that companies record
  events the same way (they do not: United Utilities changed its recording in 2026, and median event lengths
  differ several-fold between companies).
- `claim.public_wording` goes beside the figures. Every figure names its years.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version` | `"swimsignal.spill-durations"`, `"1.0.0"` |
| `generated_at`, `period` | export time; the records' span (`2024-01-01` to `2025-12-31`) |
| `method` | the spill rule (events joined when overlapping or less than 1 hour apart), `few_below` (5), code SHA-256 |
| `sources` | each company's EA event file and its SHA-256 |
| `attribution` | the Environment Agency's Open Government Licence line, shown with the figures |
| `claim` | `public_wording` and `not_claimed` |
| `company` | per company: overflows, spills, `median_h`, `p90_h`, `share_over_6h`, `share_over_24h` |
| `still_running` | per company and all nine, for spills that had run at least `running_at_least_h` (0, 1, 3, 6, 12, 24): the share of such hours at which the spill was still running 1, 3, 6, 12 and 24 hours later (`still_after_<h>h`); `hours` behind each row. A description of 2024-25, measured over every whole hour a spill was running in its first 72 hours |
| `companies` | company names; `overflows.company` indexes into it |
| `overflows` | one column per field, same order in each: `site_id`, `company`, `spills_2024`, `spills_2025`, `median_h`, `p90_h`, `longest_h`, `share_over_6h`, `few` (true when the overflow had fewer than 5 spills, so its typical length rests on little) |
| `coverage` | overflows, spills, overflows with `few` |

Overflows with no recorded spill in 2024-25 are absent: absence means no recorded spill, or no record, and the page
should not show it as "no spills" without the annual return's own figure.

## How a page might use it (suggestions for the product owner)

- On a spot's overflow history (`spot/<id>/profile/`): each upstream overflow's typical and longest spill.
- Beside the "If it stops now" clearing time: "Spills already running 3 hours were still running 6 hours later about
  7 times in 10 (2024-25 records)". That is a description, not a forecast for this spill; the comprehension sessions'
  task 3b tests wording near the clearing time first.
