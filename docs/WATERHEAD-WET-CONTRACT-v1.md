# Waterhead bacteria samples: data contract, version 1

Written 31 October 2026. The file is `data/research/waterhead_wet.v1.json`, schema `swimsignal.waterhead-wet`, made by
`scripts/export_waterhead_wet.py`. The site copies it to `data/research/waterhead_wet.json` and shows it on
`waterhead.html` (`build_site.write_waterhead`). Register entry: WET in
[the recovery register](RESEARCH-RECOVERY-2026-10.md).

## Source

Tim Boden of Ambleside Action for a Future (AAFAF) sent the sheet `25-26 Bacteria Levels.xlsx` by email on
25 October 2026, after a call on 24 October. The original stays outside the repository, in
`swimsignal-private/tim-boden-aafaf/`, with its provenance and a data audit. The export stops unless the sheet's
SHA-256 is `c9f229c8…16b3b5`, the file as received.

The sheet holds 59 samples: 29 from 16 April to 30 October 2025 and 30 from 23 March to 12 October 2026. Each has a
date and E. coli, intestinal enterococci and total coliform counts, headed "cfu/100ml".

## Permission, in Tim's words (25 October 2026)

- "In terms of the bacterial counts, you have my long-term permission to use these as you require - the testing was
  funded by parish council money, so they are public domain."
- "The bacteriological data can be forwarded on- just with the appropriate credit."
- "Credit Ambleside Action for a Future for the data, and myself for the models and document".

His models are a separate matter. Their coefficients are private, and anything drawn from them is checked with him
before it is published. Nothing in this file comes from his models.

## What the file holds

| Field | Content |
|---|---|
| `site` | "Waterhead, Windermere", with `confirmed: false`: the email names Waterhead, but the sheet has no site column |
| `units` | Per 100 ml, as the sheet records them |
| `claim` | `public_wording`, the page's lead, and `not_claimed` |
| `seasons` | Per year: first and last date, sample count, median and highest E. coli and enterococci, how it was sampled |
| `open_questions` | What is not yet confirmed |
| `spots` (1.1) | The SwimSignal spots whose pages link here: `osm-windermere-waterhead`. The build writes `data/research/local-samples.json` from it, by spot id, for the spot page's one link |
| `attribution`, `permission`, `report` | The credit, the permission, and the WET technical report (Tim Boden, 17 Nov 2025) |
| `sources` | The sheet's name, SHA-256 and date received, and the export script's SHA-256 |
| `samples` | Every sample in date order: `date`, `ecoli`, `ie` |

The total coliform column is left out, because the permission names the E. coli and enterococci counts.

## What it may say

The samples are dated measurements at one place by a local group. The page may show them, with their summaries. The open
questions stay in the file and this contract; the page does not list them. The page may not present the samples as:
- the water now, or elsewhere in Windermere
- a forecast
- a bathing water rating, which needs many samples over four years
- evidence that the water is safe
- a check of SwimSignal's forecast

The page does not compare a single count with a bathing water line.

## Not yet confirmed

1. The exact sampling point at Waterhead.
2. The 2026 laboratory, method and time of day. The 2025 samples were taken on Thursday mornings and analysed by
   Simplex Health (the technical report, p. 6).
3. What a recorded 0 means. It is most likely below the method's detection limit, not a true zero.

When Tim answers, the export changes its `open_questions` and `seasons[].how`. That is a minor version.

## Changes

- **1.1.0 (31 Oct 2026):** `spots` added. The lead says "at the time it was taken", not "on that morning" (the 2026 time is unconfirmed); 2025 is "mostly" Thursday mornings (16 Apr 2025 was a Wednesday). The page lists seasons and samples newest first and links back to the spot's forecast.

## Use in tests

These seasons were seen before any SwimSignal test of Waterhead was designed. A comparison on them is exploratory.
A fair test needs samples taken after a forecast or candidate is fixed: the 2027 season at the earliest.
