# Source inventory: the data contract, version 1

Written 31 October 2026 for issue [#486](https://github.com/ethanbuckley/swimsignal/issues/486). File:
`data/research/source_inventory.v1.json`. Readable version: `docs/SOURCE-INVENTORY-2026-11.md`. Checked by
`tests/test_source_inventory.py`. The file is written by hand: there is no exporter, and no build reads it.

## What it is and is not

- **Is:** one row per candidate or in-use data source, with what it measures, where, when, how fast, under what
  licence, at what cost, whether a local copy exists, which status bucket it is in, what it would let SwimSignal
  show or test, and a rank.
- **Is not:** a promise to integrate anything, a licence opinion from a lawyer, or a record of what the site shows
  today. A "ready" row still needs its own PR, test and page check.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version` | `"swimsignal.source-inventory"`, `"1.0.0"` |
| `generated_at` | date the file was last edited |
| `statuses` | the five buckets and their definitions (below) |
| `measurement_kinds` | `measurement`, `proxy`, `model`, `metadata`, `directory`, defined in the file |
| `rank_method` | how ranks were chosen |
| `recheck` | the date and method of the primary-source recheck, and the four results |
| `sources[]` | the rows (below) |
| `follow_on_issues[]` | suggested issue titles, each naming the rows it would act on; none were created |

Each `sources[]` row:

| Field | Meaning |
|---|---|
| `id` | stable lower-case id; never reuse one for a different source |
| `rank`, `rank_reason` | 1 is first to work on; ranks are unique and contiguous; one line of reason |
| `name`, `publisher`, `region`, `theme` | `theme` is one of `samples_sondes`, `discharge_load`, `rain_flow`, `upgrade_metadata`, `spill_history`, `regional_directory`, `coastal_model` |
| `measures`, `measurement_kind`, `measurement_note` | what is measured, and plainly whether it is a measurement, a proxy, a model, metadata or a directory |
| `coverage`, `date_range`, `latency` | where, when, and how fast new data appears |
| `licence` | `name`, `url`, `permits` (what the terms allow, in words) |
| `access` | `route`, `cost`, `account` (true when a key, login or order form is needed) |
| `local_cache` | `null`, or `path` (relative to the main checkout or `swimsignal-private/`), `bytes`, `files`, `newest` (newest file date), `note`. Measured read-only on 31 Oct 2026; `bytes` is `null` for committed files |
| `status` | one of the five buckets |
| `enables` | the product or model question it serves |
| `recheck` | `result`, `urls` read, `note`; when `changed`, `changes[]` with `claim`, `was`, `now`, `doc` |
| `docs` | repo docs that hold the detail |

## Status buckets

- `ready_to_integrate`: open licence that covers publishing, reachable without an account, not yet used for this.
- `needs_permission`: needs a licence statement, written permission, an account or key, a budget decision or an outside
  contact. All of these are Ethan's actions.
- `unavailable`: not published, refused by its terms, or not usable for publishing at all.
- `stale_archive`: published but no longer updated, or a discontinued service.
- `already_used`: read by a build, test or export already; `enables` says what is still unused.

## Changing it

- Add a row: new `id`, then renumber ranks so they stay unique and contiguous, and add the row to the readable doc's
  ranked table (the test checks both).
- A recheck: update `recheck`, keep the old claim in `changes[].was`, and bump `version` (minor for new rows or
  fields, patch for corrections).
- Do not delete a row because a source failed or was refused. Change its status and say why.
