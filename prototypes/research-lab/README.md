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

## Run it

1. From the repository root, start a static server:

   ```bash
   python3 -m http.server 8823
   ```

2. Open http://localhost:8823/prototypes/research-lab/

It worked if the front page lists four exhibits and each one opens with figures in its opening paragraph.
"Could not read the research files" means the server was started in the wrong folder. A page showing the main
SwimSignal app means another server or an old service worker holds that port: pick another.

## Shared
- `lab.js`: the drawn map of Great Britain (`LAB.drawMap`) and the dot-and-interval chart (`LAB.dots`).
- `assets/wide/`: one 4 km true-colour picture per weekly lake, made by `scripts/lab_wide_pictures.py` (1 Nov 2026: 18
  requests, 25.3 MiB, caps 80 requests and 60 MiB; scratch `DIPCAST_ROOT`/`DIPCAST_STATE`; `data/research` hashed
  before and after, unchanged). `wide.json` records each scene, its time and hash. Pictures, not readings.
- `assets/paths/`: each spot's upstream overflows (the forecast's own distance, travel time and weight) and the mapped
  rivers joining them, from `scripts/lab_pollution_paths.py` (offline; scratch root linking the cached network).
- `workspace/data/`: one file per catchment (Windermere, the Wharfe at Ilkley) with every layer the workspace draws, from
  `scripts/lab_catchment_workspace.py` (offline; scratch `DIPCAST_ROOT` linking the rain cache and the EA event files,
  hashed before and after, unchanged). Outcomes to 30 Sep 2026 only.
- `assets/britain.json`: England, Wales and Scotland outlines from ONS (OGL), simplified on the server, one request
  (`scripts/lab_britain_outline.py`).

- `lab.css`: the field-journal stylesheet every exhibit uses (the site's type pair and colours).
- Each exhibit: a question and a plain answer with figures; numbered sections; real data only, missing data drawn as
  missing; notes labelled "stated in advance" or "exploratory"; what it cannot tell you; next questions with what
  would be unconvincing. Every figure is read from a committed file when the page loads.
- Screenshots: `shots/` here and in each exhibit, clock fixed at 1 Nov 2026 14:00 UTC.
