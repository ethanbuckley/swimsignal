# SwimSignal Research Lab

Exploratory exhibits on data already read. They change nothing in the forecast. The site build copies this folder to
`lab/` (`scripts/build_site.py` `write_lab`, record `docs/RESEARCH-LAB-LIVE-2026-11.md`), with a frozen copy of the
research files it reads. Run from the repository root, as below, the exhibits read `data/research/` as committed.

| Exhibit | Folder | State | Record |
|---|---|---|---|
| 1. The lake from space | `lake-from-space/` | live, exploratory | `docs/LAKE-FROM-SPACE-EXPLORATION-2026-11.md` |
| 2. Where does the pollution go? | `pollution/` | live, exploratory | `docs/POLLUTION-PATHS-EXHIBIT-2026-11.md` |
| 3. How good are the forecasts? | `forecasts/` | live, exploratory | `docs/FORECAST-RECORD-EXPLORATION-2026-11.md` |
| 4. Catchment workspace | `workspace/` | live, exploratory | `docs/CATCHMENT-WORKSPACE-2026-11.md` |
| 5. Sampling gaps | `sampling/` | exploratory planning aid | `docs/SAMPLING-GAPS-EXHIBIT-2026-11.md` |

## Run it

1. From the repository root, start a static server:

   ```bash
   python3 -m http.server 8823
   ```

2. Open http://localhost:8823/prototypes/research-lab/

It worked if the front page lists five exhibits and each one opens with its answer and "The figures behind it".
"This exhibit's data could not be loaded" means the server was started in the wrong folder. From the repository the
header is a stand-in with the name only; the site build puts the site's own header and phone bar there. A page showing the main
SwimSignal app means another server or an old service worker holds that port: pick another.

## Shared
- `lab.js`: the drawn map of Great Britain (`LAB.drawMap`) and the dot-and-interval chart (`LAB.dots`).
- `assets/wide/`: one 4 km true-colour picture per weekly lake, made by `scripts/lab_wide_pictures.py` (1 Nov 2026: 18
  requests, 25.3 MiB, caps 80 requests and 60 MiB; scratch `DIPCAST_ROOT`/`DIPCAST_STATE`; `data/research` hashed
  before and after, unchanged). `wide.json` records each scene, its time and hash. Pictures, not readings.
- `refresh.json` exists only in a site build (`build_site.write_lab_refresh`): each part's date, read by the
  "Data as of" line in `lab.js`. Run from the repository, that line stays empty.
- `assets/paths/` (the site build remakes these every build from its own network): each spot's upstream overflows (the forecast's own distance, travel time and weight) and the mapped
  rivers joining them, from `scripts/lab_pollution_paths.py` (offline; scratch root linking the cached network).
- `workspace/data/`: one file per catchment (Windermere, the Wharfe at Ilkley) with every layer the workspace draws, from
  `scripts/lab_catchment_workspace.py` (offline; scratch `DIPCAST_ROOT` linking the rain cache and the EA event files,
  hashed before and after, unchanged). Outcomes to 30 Sep 2026 only.
- `assets/britain.json`: England, Wales and Scotland outlines from ONS (OGL), simplified on the server, one request
  (`scripts/lab_britain_outline.py`).

- The shell: every page links the site's `src/dipcast/pages/page.css` before `lab.css`, so the fonts, header, phone bar,
  fields and tables are the site's. The build swaps the stand-in header for `build_site.site_header` and adds the phone
  bar. Each page has the Lab's own bar (`.labnav`) and each exhibit ends with the previous and next one
  (docs/DESIGN.md, "The Research Lab").
- `lab.css`: the Lab's editorial variant over `page.css`: the warmer paper, the deep frontispiece, plates and captions.
- `sampling/gaps.json`: every spot's place and samples, the calendar and the fixed-day rain shares, from
  `scripts/lab_sampling_gaps.py` (committed files only; `check` matches it to the planner's file, which exhibit 5 also reads).
- `assets/covers/`: the five exhibits' covers as 320 px pictures, for the Research page, Accuracy, the home page and a
  spot's "Explore the evidence". Taken on 1 Nov 2026 from this front page's own drawn covers (headless Chrome, the big
  numbers hidden). Retake them if an exhibit's cover changes.
- Links in: `#lake=`, `#spot=`, `#bw=` and `#c=…&spot=` open an exhibit on a place; a place an exhibit lacks is said in a
  status line, never swapped quietly. Each exhibit links back to "Today's forecast for" the place it shows.
- Each exhibit: a question and a plain answer with figures; numbered sections; real data only, missing data drawn as
  missing; notes labelled "stated in advance" or "exploratory"; what it cannot tell you; next questions with what
  would be unconvincing. Every figure is read from a committed file when the page loads.
- Screenshots: `shots/` here and in each exhibit, clock fixed at 1 Nov 2026 14:00 UTC.
