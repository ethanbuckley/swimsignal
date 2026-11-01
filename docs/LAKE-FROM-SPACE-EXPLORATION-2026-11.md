# The lake from space: exploration and Research Lab prototype

Written 1 November 2026. Bounded exploration under [the research workflow](RESEARCH-WORKFLOW.md), project SAT-OBS in
[the recovery register](RESEARCH-RECOVERY-2026-10.md). **Exploratory, on data #386 had already examined.** Nothing here
is a test, changes a verdict, or touches the live forecast, the site or an active window.

## What was asked

Can changes seen from space tell us anything useful about algae in English lakes? Propose next research questions,
run a bounded analysis where existing data allows, and build a reviewable "Lake from Space" exhibit as the first of
three Research Lab exhibits.

## Inputs and budget

- Committed files only: `data/research/lake_observations.v1.json` (1.3.0), `data/research/lake_imagery.v1.json` (1.0.0)
  with its pictures, and #386's own counts in `docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-score.json`.
- No download, no private cache, no dipcast import, no Open-Meteo call. The script hashes its inputs before and after and
  stops if one changed (none did). It runs in about 5 seconds.
- Code: `scripts/lake_from_space_explore.py`. Output: `prototypes/research-lab/lake-from-space/exploration.json`.
  Bootstrap over lakes, 2,000 draws, seed 20261101, fixed before any figure was computed.

## Results

| Question | Figure | Interval (95%, by lake) | What it means |
|---|---|---|---|
| Can the published file rebuild #386's pairs? | 216 pairs, 38 lakes, ρ 0.491 | 0.295 to 0.653 | Close to #386's 207 pairs, ρ 0.502. Three Windermere and Frensham points use the bathing water's 300 m core here, not the WQA point's own |
| Within one lake's summer (lake-season means removed) | ρ 0.345, 168 rows, 29 lakes | 0.190 to 0.496 | The index moves with lab values inside a summer |
| The same, each month's mean also removed | ρ 0.245 | 0.071 to 0.405 | Part of the within-summer agreement is both rising or falling with the time of year. A weak signal beyond the calendar remains |
| Direction of change between consecutive pairs | 68.1% same direction, 94 changes | 59.1% to 75.6% | Above a coin toss, but see the next row |
| Direction: index against a calendar guess (other lakes' monthly means), changes across months | index 68.5%, calendar 75.3%, 89 changes | difference −6.7 points, −23.3 to +9.1 | **The index did not call direction better than the calendar.** The interval cannot rule out a modest gain either |
| Repeat noise against a summer's spread | repeat median 0.032, 1 in 10 ≥ 0.166; typical summer spread (10th to 90th percentile) 0.170 | | Only 51% of 84 lake-summers spread wider than the 1-in-10 repeat difference |
| Waits between clear readings (14 every-image lakes, May-September) | median 5 days; 21% over 14 days; longest 78 | | Gaps of weeks are normal |
| Shallow-lake pairs a summer (#386's counts) | 8, 9, 22, 16, 34 (2021, 2023-26) | | The draft 2027 minimum is 30 pairs at 6 lakes; only 2026 reached it |
| Readings far outside their lake's range (robust z > 5) | 47 flagged, e.g. Barton Broad 21 Jun 2024 −0.50 against a usual 0.15 | | Kept, not removed. Cause unknown offline because raw bands were not kept |

By lake type (#386's split, stated before its run), the within-summer correlation is similar: shallow 0.341
(0.069 to 0.556, 11 lakes), deeper 0.360 (0.121 to 0.636, 13 lakes). Neither group is a lead finding here.

## What is established and what is inferred

- **Established (this run, seen data):** the figures above, from the committed files, reproducibly.
- **Established (#386, stated in advance):** fails as stated; promising, not validated. Unchanged.
- **Inferred, not tested:** #386's placebo shuffled readings within lake and season. A shared seasonal rise survives in
  the real data but not in a shuffle, so beating that placebo does not by itself show day-specific signal. The
  month-removed figure (0.245) is the better estimate of signal on the day, and it is weaker than 0.50 suggests.
- **Inferred, not checked:** 2026's higher pairing rate (60% of shallow samples, against 18-38% before) may come from
  a third Sentinel-2 satellite in orbit.
- **Correction to the draft 2027 protocol** (`SATELLITE-RECOVERY-2026-10.md` section 5, "weekly logging and three
  satellites should raise the pairing rate"): weekly logging does not add pairs, because every image stays in the
  archive. It matters for prospective dating, not for counts. Pairs are limited by a lab sample falling within a day of
  a clear image.

## Proposed next questions

Each is a proposal. None is started.

1. **Does the index add anything to the calendar inside a lake's summer?** Can establish whether day-to-day readings are
   worth showing as change. Needs a statement written before 1 May 2027, scored on 2027 pairs only: month-removed
   within-summer correlation, and direction against the calendar guess, each with lake intervals. Unconvincing: the
   "index minus calendar" interval again spans zero, or the month-removed interval reaches zero.
2. **Shallow-lake calibration to chlorophyll with honest intervals** (the existing draft). Decide before the season
   whether 2027 and 2028 pool under one frozen calibration, since one summer gave 8-34 pairs. A partner who samples
   anyway could time some samples to clear overpasses (outside contact: Ethan's). Unconvincing: skill interval reaching
   zero, or 80% intervals holding outside 70-90%.
3. **Which outlying readings are artefacts?** Re-read bands and scene classification for the flagged scenes (about 10
   requests each, inside the pilot allocation) and write a screening rule that never looks at lab values.
   Unconvincing: a rule that improves lab agreement only because it was tuned on those lab values.
4. **Does 300 m of open water speak for the lake?** For the five pilot lakes, compare the circle with a whole-lake
   reading on the same clear dates. Measure one lake's cost first. Unconvincing as a limiting factor: differences no
   larger than the repeat noise.

## The prototype

`prototypes/research-lab/lake-from-space/`, run as in its README. Not built by `site.yml`, not linked from the site.

- A dark frontispiece with the question, a plain answer, and a contact sheet of the newest real picture at each weekly lake.
- A lake index by region, a select on phones, and a desaturated map of all 55 sites.
- A plate of the real Sentinel-2 picture (pixels shown as pixels, 300 m circle, scale bar), with true colour, the index on
  the pixels read, and the not-clear mask; side-by-side compare; previous and next reading; deep links `#lake=…&date=…`.
- The record: one barcode row per summer (readings above, lab samples below, reasons for empty summers), and the
  chosen summer in detail. Gaps over 14 days are hatched where every image was read. Where only images near lab samples
  were read, the gaps are said to be unread, and lab samples without an image are marked ×. Dots are never joined.
- Seven notes from the analysis, a list of what the index cannot tell you, and the four questions above.

Checked at 1440 × 900 and 375 × 812 in headless Chrome and the app's browser: no horizontal scroll at 375, no console
errors, layer toggles, compare, stepper, year rows, chart dots by mouse and keyboard, and deep links. Not checked:
Safari, a real phone, screen readers.

**Decision before any publication:** the observation contract's release checklist (item 7) bans algae wording on the
lakes page. This exhibit asks the algae question in its title. Publishing it means either rewording to chlorophyll or
treating a Research Lab exhibit as a different kind of page from the observation viewer. That is Ethan's call.

## Readout

| Field | Content |
|---|---|
| Identity | SAT-OBS, exploration "lake-from-space-explore 0.1.0"; this PR |
| Evidence | Seen 2021-26 pairs; month-removed within-summer ρ 0.245 (0.071 to 0.405); direction no better than calendar (−6.7 points, −23.3 to +9.1) |
| Stage and claim | Exploration. Supports "a weak signal beyond the time of year"; does not support "shows when chlorophyll is rising" |
| Next deliverable | Ethan's review of the prototype; then fold questions 1-2 into the 2027 protocol review before 1 May 2027 |
| Budget | None spent: offline, committed files |
| Release route | Product owner (LABS) decides whether parts move into `/lakes.html`; rollback is not linking it |
