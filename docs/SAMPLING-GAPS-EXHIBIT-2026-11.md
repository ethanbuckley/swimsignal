# Sampling gaps: Research Lab exhibit 5

Written 2 November 2026, for issue #482 (register row "Sampling priorities #381"). The fifth Research Lab exhibit, at
`lab/sampling/`, made from `prototypes/research-lab/sampling/`. It builds on the sampling planner
(`sampling-planner.html`, [its contract](SAMPLING-PLANNER-CONTRACT-v1.md)), merged in #566. **It changes no forecast,
level, model, threshold or evaluation window.** Route: public research observations plus a planning aid
([RESEARCH-WORKFLOW.md](RESEARCH-WORKFLOW.md)).

## What it is for

A researcher or a sampling group asks two things: where are the lab samples behind the forecast thin, and what would
a season of extra samples fill, at what cost? The planner page answers with tables. This exhibit draws the same
gaps, and lets the reader compare three candidate seasons side by side.

It is a planning aid. It allocates no sample, sends nothing to anyone, and says nothing about which season would
teach the model more.

## What the page shows

The Lab's anatomy (docs/DESIGN.md, "The Research Lab"): the question, a short answer, "The figures behind it" folded,
a scope line, "Data as of", numbered sections, what it cannot tell you, questions worth asking next, the pager.

1. **Where the samples are.** A map of every spot in the export: filled where the Environment Agency samples (sized
   by how many), teal where a local group does (Waterhead), a dashed ring where there are none. A picker by area, the
   chosen spot's samples by year and month and after rain, and a table of spots by area. The chosen spot can be
   added to any of the three seasons.
2. **When they were taken.** A calendar: each place with samples by month, January 2023 to December 2026. A month
   with none is hatched; months after September 2026 are plain, "not in this record yet".
3. **How many came after rain.** The share of the EA's 2024-26 samples that followed more than 10 mm in 48 hours,
   by area and by month, with the sample count beside each.
4. **Compare candidate seasons.** Three columns. Each takes spots (from the map, a list, or a group such as "the
   bathing waters with one season of samples"), months and a frequency. The reader sets a lab price and a travel
   and time cost per sample. A table compares spots, spots with no samples, months, samples, cost, spot-months never
   sampled before, samples after rain on fixed days, and what the simulation says at that many samples per new site.
   The seasons and costs live in the address, so a link reopens them.
5. **What a simulation found about choosing.** The four policies, their errors, and the information policy's gain
   against equal coverage in each run with its interval. The failed verdict is copied from the planner's file.

The three starting seasons are examples to change, labelled so: A, the six one-season bathing waters fortnightly,
May to September; B, Yorkshire's nine spots with no samples, monthly, May to September; C, A's spots in April and
October. They show a change of place and a change of month. They are not suggestions.

## Honest limits, beside the figures

- Under the comparison: the one rule tested, an information score, failed its test against equal coverage in a
  simulation (58.5% of worlds, 60% needed), and no rule here has been tried in real water.
- In each comparison cell for the simulation: "The test needed 60%: it failed. Made-up worlds, not real water."
- A spot with no samples "says nothing about whether the water is clean".
- **Population and cutoff.** The page says, in its scope line and above the map: "This export holds the 109 spots in
  SwimSignal's list on 2 Nov 2026 and lab samples to 28 Sept 2026. Spots added to the site since are not in it."
  The site's spot list grows (112 on the live site on 2 November). A spot linked by `#spot=` that the export lacks is
  said in a status line, never swapped quietly.

## The after-rain figure

The EA fixes its sampling days in advance, so the share of its samples that followed rain is about what a fixed
schedule in the same area and months would get. The comparison uses the area's share for May to September only. A
month outside that, or an area with no bathing water with an overflow upstream (North East, Peak District and
Sheffield), has no figure and is counted apart. This is exploratory, on seen data, and pools the bathing waters in an
area: a spot can be wetter or drier. It is archived lead-0 forecast rain, not a gauge. A wet-day rule's yield is not
estimated: it was not simulated as such, and nobody has tried it here.

## Data

- `data/research/sampling_planner.v1.json`, as committed (#566). The build copies it to `lab/data/`
  (`build_site.LAB_DATA`).
- `prototypes/research-lab/sampling/gaps.json`, schema `swimsignal.lab-sampling-gaps` 1.0.0, made by
  `scripts/lab_sampling_gaps.py export`: every spot's place, kind, area and sample count; each place's samples by year
  and month; the fixed-day rain shares by area and month. `check` confirms its spot, sample and rain totals match the
  planner's file.

From committed files only: no fetch, no model, no simulation. Run on 2 November 2026 from this worktree. The inputs'
SHA-256 were taken before and after (`data/research/*.json`, the atlas rows, `spots.csv`, `spots-osm.csv`):
unchanged. The build step was run with scratch `DIPCAST_ROOT` and `DIPCAST_STATE`, writing to a scratch site.

| Input | SHA-256 (first 12) |
|---|---|
| `data/research/ecoli_evidence.v1.json` | 4b706230bb53 |
| `data/research/waterhead_wet.v1.json` | 5a04c8ba7673 |
| `data/research/sampling_planner.v1.json` | 3893e43690b9 |
| `docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv` | 3dad94f4323f |
| `spots.csv` | 1c00d9c64784 |
| `spots-osm.csv` | 912bf3d48408 |

**Refresh.** By hand, after each bathing season: rerun `export_sampling_planner.py` and then this script. In
`lab/refresh.json` the part is "Lab samples and sampling gaps", with its outcome date and no age limit: a season's
samples do not age between seasons. A new spot on the site appears here only after a new export.

## Where it is linked

The Lab's bar on every page (sixth link), the Lab front page (a fifth card with a drawn cover:
`assets/covers/sampling.jpg`, taken from that card in headless Chrome), exhibit 4's pager, the Research page's
routes and its sampling planner entry, and the home page's Research Lab block. Not on a spot's "Explore the
evidence" tile: the tile lists exhibits holding a spot's own record, and adding every spot to it is a separate
decision.

## Checks

- `tests/test_lab_build.py`: the shell, bar (six links), pager, covers (five), sitemap and refresh with a fifth
  exhibit; the exhibit reads the planner's file and its own, which agree (`lab_sampling_gaps.check`); the population
  and cutoff sentence; the failed verdict and "not tried in real water" beside the comparison; no efficiency words.
- A scratch site from `write_lab`, served and opened in the in-app browser at 1440 and 375 px: no console errors, no
  element past the phone's gutter; adding a spot, a month and a price updated the table and the address, and a
  reload restored them. Captures in `prototypes/research-lab/sampling/shots/`.

## What next

- **The field study** in the planner's contract is the only route to an efficiency claim. Offering it to a partner is
  outreach and Ethan's decision (issue #482).
- **Rain at unsampled spots.** Archived forecast rain at each spot on a fixed weekly day, 2024-26, would replace the
  area share. Needs the rain archive in a scratch root; not started.
- **A refresh after the 2027 season**, with any new spots.
