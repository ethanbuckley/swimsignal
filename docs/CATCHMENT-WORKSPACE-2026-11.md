# Catchment workspace, Research Lab exhibit 4 (1 November 2026)

A local prototype in `prototypes/research-lab/workspace/`. It is not built by `site.yml`, not linked from the site, and
changes nothing in the forecast. Stage: bounded exploration (docs/RESEARCH-WORKFLOW.md). Not a test.

## What it is

An outside review on 1 November 2026 recommended one connected catchment workspace before more separate exhibits.
This first version does that for two catchments:

- **Windermere**: Waterhead (WET samples) and the four EA bathing waters (Rayrigg Meadow, Millerground Landing,
  Lakeside YMCA, Fellfoot). Six United Utilities overflows upstream of one or more of them.
- **The Wharfe at Ilkley**: the Cromwheel bathing water. Sixteen Yorkshire Water overflows within 60 km upstream.

A person chooses a catchment and dates (1 Jan 2024 to 30 Sep 2026), switches layers on or off, and taps a day. The
timeline shows rain, each overflow's spills, E. coli samples, water temperature and the satellite index on one date
axis. The map shows which overflows spilled on the chosen day or the two before, sized by the model's weight at the
spot in focus. The investigation (catchment, dates, layers, day, spot) is kept in the URL, so a copied link reopens it.
"Download these rows" saves a CSV of exactly the rows the timeline draws, with a header naming each source, its
licence, its gaps, the investigation link and the commit the data was exported at.

## Where each layer comes from

| Layer | File | Licence | Gaps shown |
|---|---|---|---|
| Rain | `data/cache/rain/archive_*` (Open-Meteo ERA5-Land, the forecast's cache), daily by UK date, mean of the 0.1° cells holding the spots and their overflows (Windermere 4 cells, Ilkley 5) | CC BY 4.0 (Open-Meteo); Copernicus C3S | A day any cell lacks is a gap. The cache ends 6 Sep 2026, so 7–30 Sep 2026 (24 days) is hatched |
| Spills | `data/processed/ea_events_{united_utilities,yorkshire_water}.parquet` (EA detailed EDM start/stop, 2024 and 2025) | OGL v3.0 | 2026 is hatched: the EA publishes 2026 records to the end of August (data.gov.uk, "2026 year to August Detailed EDM Start-Stop Data.zip", updated 22 Oct 2026, checked 1 Nov 2026), but they are not imported here. September 2026 is not published. Bridge Lane CSO (Ilkley) has no event in the file, labelled, not drawn as zero |
| E. coli | `data/research/ecoli_evidence.v1.json` (EA) and `data/research/waterhead_wet.v1.json` (WET) | OGL v3.0; WET public domain with credit | Days without a sample are empty. Two WET samples after 30 Sep 2026 are left out |
| Hindsight | `ecoli_evidence.v1.json` (`hindsight`, P(over 900), refitted leaving out each year) | SwimSignal's own | "No estimate" with its reason (before 2024, not in the study's file, WET) |
| Water temperature | `data/research/lake_temperature_obs.v1.json` (EA WQA, 10 points in Windermere's two basins) | OGL v3.0 | Only May to September was fetched: October to April is shaded "not fetched". Ilkley: none in the repository, said in the lane |
| Satellite | `data/research/lake_observations.v1.json` (NDCI at the four bathing waters) | Copernicus Sentinel data | Clear images only. Ilkley: not processed for rivers, said in the lane |
| Map | `prototypes/research-lab/assets/paths/` (the forecast's own network, distances and weights) | OGL v3.0 (OS Open Rivers); Waterhead position ODbL (OpenStreetMap) | Lake paths dashed |

Rows exported (1 Jan 2024 to 30 Sep 2026): Windermere 980 rain days, 4,322 spill events, 298 samples (228 EA bathing
water service, 13 EA archive, 57 WET), 307 temperature readings, 196 satellite readings. Ilkley 980 rain days, 2,696
spill events, 60 samples (57 and 3), no temperature, no satellite.

## How it was made

`scripts/lab_catchment_workspace.py`, offline: no request, no dipcast import. Run 1 Nov 2026 with scratch
`DIPCAST_ROOT`/`DIPCAST_STATE` whose `data/` linked the rain cache folder and the two EA event files of the main
checkout. The 29 cached inputs it read were hashed before and after: unchanged (the script fails otherwise).
Committed research files are read in place and their hashes are written into each output file. Output:
`workspace/data/windermere.json` (544 kB), `wharfe-ilkley.json` (304 kB), `index.json`.

Checked 1 Nov 2026 in the browser pane and headless Chrome at 1440×900 and 375×812: page width equals the viewport
(no horizontal scroll), no console errors. The CSV's row count equals the rows drawn (1,062 for Windermere, May to
September 2025, all layers). Screenshots in `workspace/shots/`, clock fixed at 1 Nov 2026 14:00 UTC.

## The one figure on the page (exploratory)

On outcomes already read, a count and not a test. For each sample in 2024–25 (the years with spill records), was
there a recorded spill at any overflow upstream of that spot in the 48 hours before it was taken?

- **Ilkley:** 11 of 13 samples over 900 (85%) followed a spill; so did 15 of 27 under 900 (56%).
- **Windermere:** no sample over 900 in 2024–25; 55 of 189 samples under 900 (29%) followed a spill.

High Ilkley samples followed spills more often, but most low ones did too. A spill alone does not separate them. The
48-hour window and "any overflow upstream" were chosen for the page, not stated in advance; a different window would
give different counts.

## Wording kept

- Hindsight estimates say "would have flagged" (P(over 900) at or above 0.25), never "warned". At lakes the page says
  the 0.25 line is the river line, for comparison only.
- Weight is "a factor from 0 to 1", never a share of bacteria arriving.
- NDCI is "an index of how green the water looked", not a toxin, chlorophyll or safety measure.
- A hatched stretch is "no record: not zero". An overflow with no event in the file may have had a broken monitor.

## What it cannot tell you

Lining things up is not cause. Rain is a 9 km reanalysis, not a gauge. Monitored overflows are not the only source.
Spill records imported here stop at 31 Dec 2025. The EA's 2026 records to August exist but are not imported, so the
2026 season can be read for rain, samples, temperature and the satellite index, but not spills.

## Next

| Field | Content |
|---|---|
| Identity | LAB-WORKSPACE; Claude (Research Lab session); this PR; `prototypes/research-lab/workspace/`, `scripts/lab_catchment_workspace.py` |
| Evidence | No verdict: a tool over existing data. One exploratory count above. Data boundary 30 Sep 2026 |
| Stage and claim | Bounded exploration, local prototype. Claim: these records, lined up, with gaps shown |
| Next deliverable | Ethan's review alongside #586. Then: import the EA's 2026 January to August spill records for the two companies (published, not yet imported; a bounded follow-up, outside the frozen evaluation windows), and a third catchment chosen by a count of catchments with samples, spill records and rain in the same window (question 4 on the page) |
| Milestone and budget | Review with #586. No fetch is needed for the next step; the third catchment uses cached files only |
| Release route | Prototype only. A public version would need the Research page owner, a refresh for rain and spills, and the source terms rechecked (ODbL for OpenStreetMap spots). Rollback: delete the folder |
