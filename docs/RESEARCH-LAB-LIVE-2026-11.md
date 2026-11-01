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
- changes three things in the copied pages, scripts and stylesheet:
  - each exhibit's data path, `../../../data/research/`, becomes `../data/`;
  - the stylesheet's fonts point at the site's own `fonts/`;
  - the SwimSignal link points at the site's root, so a preview build links to itself.

The build fetches nothing for the Lab. `prototypes/research-lab/` still runs from the repository root as before.

About 5 MB is written, 1.6 MB of it the data copy. Each exhibit loads only its own files.

Any exhibit added to the folder, such as the catchment workspace in #590, is copied with the rest. No change to the
build is needed.

## Where it is linked

- **Research page:** a "Research Lab" section first, with the three exhibits and a status line.
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

## Left for later

- **Refreshing the copy (next).** The data is frozen at its export date, which each exhibit shows. Today a refresh
  means rerunning the export scripts by hand, then rebuilding.
- **Percentages elsewhere on the site.** The site's own pages show the model weight as a percentage ("model weight
  98%"): the spot overflow list, the map tooltip, the organisers and record pages. The Lab now shows it as a 0-to-1
  factor. Making the site match is a wording decision for Ethan.
