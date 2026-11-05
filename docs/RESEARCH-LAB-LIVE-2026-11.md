# The Research Lab on the site

Written 1 November 2026. Ethan asked to put the Research Lab live and link it into the app. This puts the Lab's
exhibits on the site at `lab/` as they are. **It changes no forecast, level, model or evaluation window.**

## What the build does

`scripts/build_site.py`, `write_lab`:
- copies `prototypes/research-lab/` to `site/lab/`, leaving out the screenshots (`shots/`) and the notes (`*.md`);
- copies the research files the exhibits read into `site/lab/data/`, a frozen copy:
  - `ecoli_evidence.v1.json`
  - `lake_observations.v1.json`
  - `lake_imagery.v1.json` and `lake-img/`
  - `satellite/pilot_runs.json`
  - `research_catalogue.v1.json`
  - `sampling_planner.v1.json` (exhibit 5, from 2 November 2026)
- changes three things in the copied pages, scripts and stylesheet:
  - each exhibit's data path, `../../../data/research/`, becomes `../data/`;
  - the stylesheet's fonts point at the site's own `fonts/`;
  - the SwimSignal link points at the site's root, so a preview build links to itself.

The build fetches nothing for the Lab. `prototypes/research-lab/` still runs from the repository root as before.

About 5 MB is written, 1.6 MB of it the data copy. Each exhibit loads only its own files.

Any exhibit added to the folder, such as the catchment workspace in #590, is copied with the rest. No change to the
build is needed.

## Where it is linked

- **Research page:** a "Research Lab" section first, with the exhibits (four once the workspace, #590, merged) and a status line.
- **Accuracy page:** one sentence in the opening links exhibit 3, "every past E. coli sample one by one".
- **Lake viewer:** each location links "Its pictures in the Research Lab" (exhibit 1 at that lake).
- **Spot pages:** the Upstream tile links "The rivers joining each one, in the Research Lab" (exhibit 2 at that spot).
  - Only on a spot's own page, never on a clicked point.
  - All 109 spot ids on the live site match the Lab's export (checked against `https://swimsignal.co.uk/data/spots.json`, 1 November).
  - A spot added after the export opens a note in the exhibit: "That spot is not in this export, made 1 November
    2026. Showing Ilkley instead". It no longer shows another spot without saying so.

The header and phone navigation are unchanged.

## Wording

"Prototype" became "exploratory" on the pages, which is what the analyses are. The footer now says the work changes
nothing in the forecast and that each spot's own page gives the forecast and official advice. The review corrections
stay:
- the model weight is a 0-to-1 factor;
- hindsight estimates "would have flagged";
- the lake coverage is pooled.

Search engines may list the pages (Ethan, 1 November 2026). Each page has a description for search results and
is in the sitemap (`lab_pages`, every exhibit folder with a page). The build drops any `noindex` left in an exhibit.
The risks, accepted: a visitor from a search lands without the spot page's forecast and advice, and the frozen data
ages until a refresh exists. Each page says it is exploratory and gives its export date. **Next:** a way to refresh
the data.

## Checks

- `tests/test_lab_build.py`: writes the Lab into a temporary site and checks:
  - every data path, `fetch`, `src` and `href` in the copied pages and scripts resolves inside it;
  - every satellite picture and every spot's path file is copied;
  - fonts resolve to the site's;
  - nothing points back into the repository;
  - screenshots and notes are left out;
  - pages have a search description, no `noindex`, and say no "prototype";
  - every page is in the sitemap.
- Full suites on this branch: Python 1940 passed, 4 skipped, 1 xfailed; site JS 964 passed; ruff clean.
- The Lab written by `write_lab` into a scratch site and served:
  - every request returned 200 (fonts, data, pictures, path files) and there were no console errors;
  - 375 px wide on all four pages, with no horizontal scroll;
  - Safari on an iPhone 18 Pro simulator (iOS): front page and pollution exhibit drawn, fonts loaded.
- Not checked: a real phone, a screen reader, the full site build (it needs live sources; the Lab step is offline
  and is called beside `write_lakes`).

## Refresh (1 November 2026, steps 1 and 2 of the plan)

How each part stays current:

| Part | How it is refreshed | Called old after |
|---|---|---|
| Satellite pictures, readings and the weekly log (exhibit 1) | `satellite-pilot.yml` commits them each Monday; `write_lab` copies them at every build | 14 days |
| Overflows and the rivers joining them (exhibit 2) | Made at every site build by `write_lab_paths`, from the build's own network and overflow table (`scripts/lab_pollution_paths.py` `export`) | 2 days |
| Research records | Copied at every build | never |
| Wide cover pictures | By hand, `scripts/lab_wide_pictures.py` | 120 days |
| Catchment workspace | By hand, `scripts/lab_catchment_workspace.py` | 90 days |
| Sampling gaps (exhibit 5) | By hand after each bathing season: `scripts/export_sampling_planner.py`, then `scripts/lab_sampling_gaps.py` | never (dated to its last sample) |
| Analysis of the satellite readings; forecast record | Dated analyses on outcomes already read. A new season brings a new version; the old one is kept | never |

- **`lab/refresh.json`** (`write_lab_refresh`) holds each part's date, taken from the file itself, and how it is
  refreshed.
- **"Data as of" line.** Every exhibit shows one under its opening, for the parts it draws on. A part older than its
  limit is named with its age.
- **Exhibit 2 at build time.** The build makes it after the pages, about 8 seconds offline, and never stops the site:
  on a failure the repository's copy stays and its date shows.
- **Checks.** Run against the cached network and overflows in a scratch root (caches hashed before and after,
  unchanged), the build-made files match the committed copy: the same 109 spots and settings, and the same lines
  once order is ignored. The lines are now sorted, so each build writes the same file.

## One product (1 November 2026, the polish pass)

Ethan picked the Lab's look as the reference for the deeper evidence. This pass made the Lab part of the same
product and carried a restrained share of its manner into the forecast pages (docs/DESIGN.md, "The Research Lab").
No forecast, level, model, threshold or evaluation window changed.

- **Shell.** The Lab loads the site's `page.css`; the build gives it the site's header (Research Lab marked) and the
  phone bar. The header's desktop links are now "Research Lab" and "Research &amp; data"; the phone's More has both.
- **Inside the Lab.** Its own bar (overview and four numbered exhibits), previous and next at each exhibit's foot,
  "Back to the forecasts". Each opening is the question, a short answer, "The figures behind it" folded, a scope line,
  and "Data as of" folded to its dates (a part past its limit is said outside the fold). The front page is shorter; its
  cards are one link each, with inert covers. On phones the overflow table is one block per overflow.
- **Places.** `build_site.attach_lab_links` puts, on each spot whose record an exhibit holds, the key that opens it:
  39 spots on 1 November 2026. A spot's page lists those exhibits under "Explore the evidence", after its detail.
  Each exhibit links back to the place's forecast, and says so when a link names a place it lacks.
- **The forecast pages.** Research shows four routes with covers; Accuracy one route to exhibit 3; the home page a
  compact Lab block after the list; a spot's Upstream map is framed and captioned as a Lab figure.
- **Checks.** A preview build from the live spots.json, every missing file served from the live site read-only:
  each exhibit opened by a spot page's link on that spot (Windermere, Rayrigg Meadow: all four; the workspace with the
  spot in focus); a catchment, bathing water and lake an exhibit lacks each said in a status line; stepping to the next
  sample moved the day, the link, the panel and the CSV together (29 July 2025, Rayrigg Meadow 36 per 100 ml in
  both); a backdated part showed its warning outside the fold; the front page's gallery has four tab stops and no
  focusable point inside a cover; the header stays on one line at 820 and 1,030 px.

## Left for later

- **The rest of the refresh plan.**
  - A local `scripts/refresh_lab.py` that reruns the by-hand exports in a scratch folder and opens a PR, monthly.
  - After the evaluation windows are read (by 2 December 2026): import the EA's 2026 spill file and move the
    workspace's outcome date forward.
  - Each season: new versions of the two analyses.
- **Percentages elsewhere on the site.** The site's own pages show the model weight as a percentage ("model weight
  98%"): the spot overflow list, the map tooltip, the organisers and record pages. The Lab now shows it as a 0-to-1
  factor. Making the site match is a wording decision for Ethan.
