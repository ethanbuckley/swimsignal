# Satellite observations: the weekly pilot

Written 31 October 2026 for #472. Ethan approved building it now. Five lake sites are checked for new Sentinel-2
images every week, by a scheduled repository run, and the results reach `/lakes.html` through the normal site build.
This is **operational observation display**. It is not a test, it scores nothing, and it changes no frozen study: the
2027 confirmation (`docs/SATELLITE-RECOVERY-2026-10.md`, section 5) stays separate and May-September only.

## 1. Sites

From `data/research/satellite/pilot.json`. Each has a saved mask (`data/research/satellite/cores/<id>.npz`, copied
unchanged from the satellite test's caches) that passes the size rule.

| Lake id | Location | Water body | Kind | Tiles |
|---|---|---|---|---|
| `bw-ukf2208-09702` | Rutland Water Sykes Lane | Rutland Water | bathing water | 30UXD |
| `bw-ukd1101-45800` | Derwent Water at Crow Park | Derwent Water | bathing water | 30UVF |
| `bw-ukj2310-11945` | Frensham Great Pond | Frensham Great Pond | bathing water, deeper | 30UXB |
| `wqa-SW-50900003` | Little Sea | Little Sea | chlorophyll point, shallow | 30UWB |
| `wqa-AN-ANT160` | Barton Broad | Barton Broad | chlorophyll point, shallow | 30UYD, 31UCU |

Why these: five water bodies (the brief asked for at least three), one tile each where possible to keep the cost down,
three bathing waters whose every image the history already holds, and two shallow-lake points of the 2027 kind. The
two shallow points had only images near laboratory samples before; from the pilot's first run every image is read,
and the page says from when.

## 2. How it runs

`.github/workflows/satellite-pilot.yml`:

- **When:** Mondays at about 06:17 UTC (GitHub runs schedules on a best-effort basis), plus a manual run
  (`workflow_dispatch`, input `days` 1-14) to recover a missed or failed week.
- **Read:** `scripts/satellite_pilot.py run` searches Element84 Earth Search (`sentinel-2-c1-l2a`) for the last 14 days
  and reads each new scene's classification window, then B4 and B5 for a scene with at least 80% of its core clear.
  The reading code is the satellite test's own (`scripts/lake_algae_sat_eval/`: `stac.py`, `protocol.py`, `net.py`)
  and the refresher's quality diagnostics (`scripts/refresh_lake_observations.py`). Public hosts only, no account.
- **Publish:** `scripts/satellite_pilot.py publish` applies every recorded run to
  `data/research/lake_observations.v1.json` with contract 1.1's quality rules (`apply_refresh`), sets each site's
  `operation`, recomputes every site's age for today, and runs the contract check.
- **Commit:** the job commits `data/research/satellite/pilot_runs.json` and the observation file to main as
  `dipcast-bot`, with the job's token. The checkout keeps no token, and only the commit step is given one.
- **Reach the page:** a push made with the job's token does not start other workflows, so the next scheduled
  `site.yml` build (about every 3-4 hours lately) copies the file into `data/research/lakes.json` and
  `data/research/lake/<id>.json`, which `/lakes.html` reads. The pilot never dispatches `site.yml`.

## 3. Caps and costs

Per run: **300 requests, 100 MiB, 20 minutes**, enforced by the test's capped client (it stops at a cap or an error
status, and never retries) and a deadline checked before every scene. The job's own limit is 25 minutes.

A cap or the deadline stops the run where it is. What it read is kept, that site is `partial`, the sites after it are
`not_reached`, and the stop reason is recorded. The job then publishes, commits, writes a run summary, raises a warning,
and fails, so a stopped run is visible in Actions and on the page.

A scene that an earlier run read is not read again (`pilot_runs.json` holds every scene read), so overlapping 14-day
windows cost only the searches.

Measured, 31 October 2026, on a clean environment (no private caches reachable):

| Run | Scenes read | Requests | MiB | Seconds |
|---|---|---|---|---|
| First 14 days (18-31 Oct) | 40 | 138 | 22.07 | 37.7 |
| Same window again | 0 | 5 | 0.54 | 5.3 |

A weekly run should read 15-25 new scenes, about 60-90 requests and 10-15 MiB. The caps leave room for a two-week
recovery run. If a run hits a cap, the summary says which. The next step would then be to raise that one cap with the
measured cost, or to drop a tile (Barton Broad's second tile costs most), never to add a paid service.

## 4. What the page shows

For each pilot site, beside the latest reading (`src/dipcast/site/lakes.js`, `lakesOperation`):

- when the last check ran and over which days' images;
- what it found: a new clear image, new images none clear enough (cloud, shadow, low sun, snow, too little water), no
  new images, no images at all, or a partial, failed or unreached check;
- after a failed or stopped check, the last check that finished;
- "No check has run for N days" once the last check is more than 10 days old.

The latest reading keeps its own date and age (recent, older or stale), counted on the day the page is read. Readings
outside May-September are experimental indices with no chlorophyll or algae inference (amendment 1.1). Every other
site stays the historical record, and the release label says so.

## 5. State kept

- `data/research/satellite/pilot_runs.json`: every run's id, trigger, window, caps, costs, status, stop reason, each
  site's counts and status, and every scene read with its diagnostics (clear pixels, valid-index pixels, snow or ice,
  water share, sun elevation, processing baseline). The file is the pilot's history; nothing is deleted.
- `data/research/lake_observations.v1.json`: the readings, `refreshes` (one entry a run), `operation`, `pilot`.

**Re-exporting.** `export_lake_observations.py export` rebuilds the file from the private test caches and does not know
the pilot runs. After any re-export, run `uv run python scripts/satellite_pilot.py publish` to put them back. It is
idempotent.

## 6. Ownership

This research branch owns the pilot runner, its data and contract 1.3. The lake viewer change is the operation line and
the folded weekly refresh sentence only. The product chat owns the rest of the page.

## 7. Real run

Filled in after the first run on GitHub (section added in a follow-up commit).
