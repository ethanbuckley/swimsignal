# SwimSignal Research Lab (prototype)

Local prototypes for review. Not built by `site.yml`, not linked from the site, and they change nothing in the forecast.

| Exhibit | Folder | State | Record |
|---|---|---|---|
| 1. The lake from space | `lake-from-space/` | prototype | `docs/LAKE-FROM-SPACE-EXPLORATION-2026-11.md` |
| 2. Where does the pollution go? | | not started | |
| 3. How good are the forecasts? | `forecasts/` | prototype | `docs/FORECAST-RECORD-EXPLORATION-2026-11.md` |

## Run it

1. From the repository root, start a static server:

   ```bash
   python3 -m http.server 8823
   ```

2. Open http://localhost:8823/prototypes/research-lab/

It worked if the front page lists three exhibits and the two built ones open with figures in their opening paragraph.
"Could not read the research files" means the server was started in the wrong folder. A page showing the main
SwimSignal app means another server or an old service worker holds that port: pick another.

## Shared

- `lab.css`: the field-journal stylesheet every exhibit uses (the site's type pair and colours).
- Each exhibit: a question and a plain answer with figures; numbered sections; real data only, missing data drawn as
  missing; notes labelled "stated in advance" or "exploratory"; what it cannot tell you; next questions with what
  would be unconvincing. Every figure is read from a committed file when the page loads.
- Screenshots: `shots/` here and in each exhibit, clock fixed at 1 Nov 2026 14:00 UTC.
