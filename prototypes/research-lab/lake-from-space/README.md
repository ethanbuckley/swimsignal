# Research Lab, exhibit 1: The lake from space (prototype)

A local prototype for review. It is not built by `site.yml`, not linked from the site, and changes nothing in the
forecast. Findings and limits: `docs/LAKE-FROM-SPACE-EXPLORATION-2026-11.md`.

## Run it

1. From the repository root (not this folder), start a static server:

   ```bash
   python3 -m http.server 8823
   ```

2. Open http://localhost:8823/prototypes/research-lab/lake-from-space/

It worked if the dark header shows five small satellite pictures and the answer paragraph has figures in it. If it says
"Could not read the research files", the server was started in the wrong folder: the page reads
`../../../data/research/` and the fonts and Leaflet from `src/`.

Likely mistake: opening `localhost` on a port another session already uses. A sibling worktree's server, or an old
SwimSignal service worker on that port, will show the main app instead. Pick an unused port.

## What it reads

- `data/research/lake_observations.v1.json` and `lake_imagery.v1.json` with `lake-img/`, as committed.
- `exploration.json`, made by `uv run python scripts/lake_from_space_explore.py`.
- `data/research/satellite/pilot_runs.json`, for the flipbook: every pass the weekly checks read, clear or not.
- `../assets/wide/` and `../assets/britain.json` (see the Lab README). No map tiles.

## Files

- `index.html`, `exhibit.js`: the exhibit; the shared stylesheet is `../lab.css`.
- `exploration.json`: the analysis output.
- `shots/`: 1440 × 900 and 375 × 812 screenshots, clock fixed at 1 Nov 2026 14:00 UTC.

## Format for the other exhibits

What this one sets up, for exhibits 2 and 3 to reuse:

- A frontispiece with the question and a plain, figure-bearing answer, including what it cannot show.
- Numbered sections in a fixed order: choose, look, the record with gaps, what it shows, what it cannot, next questions.
- Field-journal plates: real data only, captioned with date, source and a monospaced log line.
- Notes labelled by evidence kind: "stated in advance" against "exploratory".
- Every figure read from a committed file at view time; nothing typed into the page by hand.
