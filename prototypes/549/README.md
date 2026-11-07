# #549 / #550 prototype: clearer core screens and a satellite explorer

A working mobile prototype for review, not the live site. It reads the live site's public data
(`swimsignal.co.uk/data`, which allows any origin) and the live level rules (`levels.js`, `experience.js`,
`eatoday.js`), so every level and headline is the site's own. Nothing here is built or deployed by `site.yml`.

## Run it

```bash
cd prototypes/549 && python3 -m http.server 8794
```

Open `http://localhost:8794/` for the before/after review, or `http://localhost:8794/app.html` on its own, best at
phone width. Saved spots and a plan are kept in this browser under `proto549.*` keys, apart from the live site's.

## What it shows

| View | Route | Real state shown (31 Oct 2026) |
|---|---|---|
| Explore / My waters | `#/explore` | Three saved waters: one with official advice, one with a stale gauge |
| Spot, normal | `#/spot/eden-lazonby` | Moderate risk, a live gauge, an estimated water temperature |
| Spot, official advice | `#/spot/bw-ukj2310-11945` | Frensham: EA advice against bathing, and no live status upstream |
| Spot, stale | `#/spot/dove-dovedale` | Gauge silent since 15 Oct |
| Spot, a feed not updating | `#/spot/cam-grantchester` | Raised right now by a recent spill; one upstream feed stale |
| Spot, missing data | `#/spot/loughrigg-tarn` | No river drawn in, no gauge |
| Plan | `#/plan?spot=grasmere&backup=rydal-water` | When, Where, Your plan side by side, Save |
| Research | `#/research` | Entry cards with freshness; methods in named sections |
| Satellite, cloudy | `#/lakes/bw-ukd1101-45800` | The last weekly check found no new clear image |
| Satellite, a date | `#/lakes/bw-ukj2310-11945?date=2026-08-23` | Map, footprint, linked date stepper, chart and table |

Values move with the live forecast, so a state can change between reviews. Before screenshots are in `before/`
and after ones in `after/`, both full-length at 375 px.

## Measured, before and after

Phone at 375 × 812, same script (`tools/measure.js`) on both. "Grey blocks" is visible text in the muted colour.

| Screen | Screens before | after | Words before | after | Grey blocks before | after |
|---|---|---|---|---|---|---|
| Explore, 3 saved | 17.3 | 1.0 | 2,952 | 75 | 34 | 1 |
| Spot, normal | 3.8 | 1.7 | 578 | 151 | 57 | 8 |
| Spot, official advice | 3.7 | 2.0 | 539 | 191 | 67 | 10 |
| Spot, stale gauge | 3.5 | 1.7 | 490 | 146 | 71 | 8 |
| Spot, missing data | 3.7 | 1.4 | 510 | 124 | 13 | 9 |
| Plan | 10.0 | 1.5 | 1,679 | (a) | 67 | 4 |
| Research | 5.2 | 1.2 | 854 | 102 | 0 | 2 |
| Satellite viewer | 3.2 | 2.0 | 623 | 339 | 1 | 12 |

(a) The prototype's Plan counts 983 words because every spot's name in its two dropdowns is counted. The visible
text is about a fifth of that. The spot page's first screen has more words than before (100 against 72) because
temperature, river level and weather moved onto it, which is the point.

Shorter is not the aim in itself. The full list of spots, every suggestion and the methods are still one tap away
in named sections, and the live page is linked from each.

## Checked

- 320 px and 375 px: no horizontal overflow on any view (the map's own tiles are clipped by the map).
- Desktop at 1440 px: one centred column, no overflow.
- Satellite explorer:
  - The prev/next buttons, clicking a chart dot, Enter on a focused dot (focus stays on the dot) and the year
    chips all change the selected reading and the deep link (`?date=`).
  - A lake's whole series is also in a table.
- Plan: a suggested backup, a day change and Save all work. The plan is kept and the button says so.
- Every touch target is at least 44 px. Focus rings use the site's `--focus`.

## What is real and what is not

- **Real:**
  - Every value, from the live public data at the time of viewing.
  - The level rules, from the live levels.js.
  - The satellite readings and scene IDs.
  - The open-water core pixels each reading uses (`data/cores.geojson`). These are rebuilt from the repository's
    `data/research/satellite/cores/*.npz` by `tools/cores_geojson.py`, so they are a reconstruction of the grid. The
    research manifest's `core.png` will replace them.
- **Not built here:**
  - True-colour images. The image slot says so, and nothing is shown until #550 milestone 2 extracts real
    Sentinel-2 B4/B3/B2 windows.
  - Calendar files and date alerts, which link to the live Plan a swim.
  - The map view, which links to the live map.
- **Map tiles:** OpenStreetMap's own tiles, because the live site's CARTO key is tied to its domain.

## Proposed implementation, one PR each

The order is chosen so that each PR ships on its own and is checked live before the next.

1. **Spot opening.** Official advice once and first, the answer, then the conditions grid with kind and time at each
   value (Measured, Estimated, Forecast, Observed; Stale or Missing in place of the value). It removes the repeated
   separation sentences and the duplicated temperature line. Files: `index.html` (spot view), page.css tokens.
2. **Spot details.** The reasoning, limits and sources move into three named sections: "Why this level", "What
   this forecast cannot see" and "Methods and sources". There is one primary action, "Choose a swim time", and
   one secondary, "Compare another spot". At most two nearby alternatives are shown, each with "Same river" where
   true.
3. **My waters.** Compact saved rows with the level, the temperature, and a flag for advice or stale data. The
   search comes next, then the map, then the full list in a named section.
4. **Plan as one flow.** When, Where (spot, backup with three suggestions), Your plan side by side, Save. The
   suggestion lists, Find a window and Compare move under it. It reuses #491's conditions rather than adding a
   second panel.
5. **Research entry cards** with freshness, and the prototypes and tests in named sections.
6. **Satellite explorer, milestone 1** in `lakes.html`/`lakes.js`: the map, the core footprint, a linked date
   stepper, chart and table, and deep links. It keeps `lakesOperation`'s states and wording and the
   `site_lakes` tests.
7. **Satellite imagery (#550 milestone 2).** The research chat extracts the images and writes the
   `lake_imagery.v1` manifest. This PR then shows the images in the slot, with side-by-side or swipe comparison.
