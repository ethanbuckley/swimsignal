# Research catalogue: data contract, version 1

Written 31 October 2026 for issue #489. The file is `data/research/research_catalogue.v1.json`, schema
`swimsignal.research-catalogue`. It is edited by hand; there is no exporter. The site copies it to
`data/research/research_catalogue.json` and shows it on `research-catalogue.html` (`build_site.write_research_catalogue`),
linked from the Research page. `tests/test_research_catalogue.py` checks it.

## What it is for

The [recovery register](RESEARCH-RECOVERY-2026-10.md) holds the current decisions. This file makes the same records
findable by anyone: what each test found when it was run, kept apart from what is happening to the work now, with its
record files, PRs and branches, so a negative result or an adopted change can be found without rerunning it.

## What the file holds

| Field | Content |
|---|---|
| `stages` | The current-stage names: `adopted`, `live`, `scheduled`, `development`, `waiting`, `archived`, `reference` |
| `sections` | The register's sections, in its order |
| `prs` | Every PR an entry names, by number: `state` (merged, closed, open), `branch`, `branch_exists` and the merge or close date, as `gh pr list --state all` and `git ls-remote --heads origin` gave them on 31 October 2026 |
| `entries` | One per register record, below |

Each entry:

| Field | Content |
|---|---|
| `id`, `title`, `section`, `topics`, `project` | Identity. `project` is the register's delivery ID (SAT-OBS, REGIONAL, LAKE-CONC, DURATION, LAKE-TEMP, WET) where there is one |
| `verdict` | The original verdict as recorded, with its numbers, in plain words. Never restated more favourably than the record |
| `scope` | What the result covers, and what it does not rule out |
| `stage`, `stage_note` | Where the work stands now. Kept apart from `verdict` |
| `next`, `read_on` | The next agreed step and its date. Every `scheduled` entry has `read_on` |
| `reopen_when` | Only on `archived` entries, and required there: the new data, mechanism or need that would reopen this version. It is not a rerun budget |
| `records` | Record files. `quote` is a verbatim line fragment of the verdict, checked by the test. A record only on a closed PR's branch has `branch` instead |
| `prs`, `links` | PR numbers (see `prs` above) and links to the site's pages for the work |
| `register_note` | Where the register's summary and the record differ, said rather than settled silently |

## Rules

- A failed test is described by what it tested. No entry says an idea is impossible or proved wrong.
- Adopted, live, scheduled and waiting work has no `reopen_when`, so it does not read as archived.
- Every record the register links has an entry (checked). The closed, unmerged #181, #187, #208, #219 and #396 are
  named with their branches.
- Adding a record: add the entry in the same PR that updates the register, with a quote from the record. A new stage or
  field is a minor version; renaming or removing one is version 2, which the site will not publish until the page is
  changed with it.

## Limits

The PR states are a snapshot from 31 October 2026. Several records were checked by reading the record, not by rerunning
anything. The records of #181, #187, #219 and #396 are only on their branches, so their entries carry no quote; their verdicts
were read from the branch record or the PR description.
