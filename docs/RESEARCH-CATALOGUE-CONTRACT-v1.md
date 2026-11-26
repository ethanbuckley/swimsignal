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
| `prs` | Every PR an entry names, by number: `state` (merged, closed, open), `branch`, `branch_exists` and the merge or close date, as `gh pr list --state all` and `git ls-remote --heads origin` gave them on the date in `checked.prs` (first 31 October 2026) |
| `entries` | One per register record, below |
| `bases` | Since 1.1.0. The fixed words for how a figure was tested: `held_out` "Tested on data it never saw", `seen` "Development result, on data already seen", `checked` "Checked against samples: no gain shown", `untested` "Not tested" |
| `figures` | Since 1.1.0. One row for each figure a place's page can show, below ("Figures") |

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

## Figures (version 1.1.0, 25 November 2026)

What each figure on a place's page was tested on (`docs/RESEARCH-ON-THE-SITE-2026-11.md`). The build writes the rows,
without their sources, to `data/research/figures.json` (`build_site.write_figures`), which a place's page reads
(`preview/app.js`, `testedHtml`), and into the method page's "What each figure was tested on"
(`build_site.with_figures`). `tests/test_research_figures.py` checks them.

| Field | Content |
|---|---|
| `id` | The row's own id, and its anchor on the method page (`#tested-<id>`) |
| `figure` | The key a place's page draws the figure by (`preview/model.js`, `figuresShown`). Rows for the same figure at different kinds of water share the key |
| `kinds` | Where the row applies: `river`, `lake`, `coast` |
| `label` | The figure's name, as a heading |
| `basis` | One of `bases`. The page shows the base's words, never words of the row's own |
| `tested_on` | Years and places. Empty when, and only when, `basis` is `untested` |
| `result` | The result in one or two plain sentences, with its numbers |
| `not_known` | What the test does not tell. A gap is said as not known, never as a negative |
| `links` | The test's record or the page that explains it |
| `shown_on` | Optional: the page that shows the figure where it is not a place's page, such as a beach card on `coverage.html`. Such a row needs no key in `figuresShown`, and shows on the method page |
| `entries`, `models`, `quotes` | What the row rests on: catalogue entries, scorecard models, and verbatim quotes with their file. Every number in `tested_on`, `result` and `not_known` must appear in their text |

Adding one: a new result for a figure already drawn is a changed row. A new figure is a row and its key in
`figuresShown`, where the page draws it; a beach's has `"kinds": ["coast"]` and a key of its own, or `shown_on` where it is drawn on another page. A row about a
satellite index says it is not a toxin measurement (checked). No row says safe, clean or accurate (checked).

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
