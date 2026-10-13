# Residence time at spill-time flow: the test, stated before any flow was fetched or any run

Written 13 October 2026. It follows `docs/LAKE-RESIDENCE-TEST-2026-10.md`: same candidate family, inputs, harness
and conditions. Nothing in this test has been run, and no flow has been fetched. Results go below the line at the
end. Nothing above it changes after a result is seen.

## Why

The first test passed all seven conditions with lake path `residence`. Its section "Which way the errors go" names
three biases, all making a lake remove too much of a spill. One of them can be measured:
- HydroLAKES' residence time is the volume over the long-term **mean** outflow.
- Overflows spill in wet weather, when a lake's inflow is several times its mean. Water then passes through faster.

Ethan asked for this variant on 13 October 2026. Until it is judged, the default is back to lake path `lake`
(commit a46fdd3). So #211 changes nothing the site uses unless this variant passes.

## The variant

`DIPCAST_LAKE_PATH_MODE=residence_spill` (`config.LAKE_PATH_MODE`), off.
- **The rule:** as `residence`, with each lake's τ replaced by τ_spill = τ / max(R, 1). R is the lake's
  spill-time flow ratio.
- **Same formulas:** share alive 1 / (1 + k τ_spill), survivors' hours τ_spill / (1 + k τ_spill),
  k = ln 10 / 30 h.
- **Lakes with no τ** are crossed as in `lake`.
- **The spot's own lake** is unchanged.
- **The times** are read from `data/raw/lake_residence_spill.csv` (`config.LAKE_RESIDENCE_SPILL_FILE`), written by
  `scripts/make_lake_spill_ratio.py` (in this commit).
- **Click-anywhere** follows it, as it follows `residence`. Only the file differs.

### R, the spill-time flow ratio

For each of the 282 WFD lakes with a τ:

**1. Spill days.** The calendar days (UTC) that any part of a discharge event covers, at any United Utilities
overflow:
- upstream of the lake's outlet within the 60 km network cap, or on the lake;
- with the events from `data/processed/edm_events.parquet` (read only). These are United Utilities' event records
  for 2023, 2024 and 2025, the only event records held.
- An event that spans several days counts each day.
- Lakes outside United Utilities' area have no spill days, so they get no R of their own.

**2. Reference gauge.** The rule:
- **Candidates:** stations in the Environment Agency Hydrology API (environment.data.gov.uk/hydrology, OGL v3.0)
  that measure flow and have a daily mean flow measure (`…-flow-m-86400-m3s-qualified`).
- **Placing a station:** snapped to the nearest river link (inland river, tidal river or canal) within 250 m.
  Otherwise it is not used.
- **Which counts:** a station on the lake's outflow (downstream of its outlet node) or on an inflow (its water
  reaches the lake).
- **Distance:** along the network, from the outlet for an outflow station, or to the lake for an inflow station.
  It must be 10 km or less.
- **Choice:** the nearest such station. On a tie, the outflow station.

**3. R.**
- The station's long-term mean flow is the mean of every daily mean in its whole record, as the API returns it
  (one request, up to 100,000 readings).
- R is the median, over the lake's spill days that have a daily mean, of that day's mean over the long-term mean.
- The API's daily date is matched to the UTC spill day.
- At least 30 such days are needed.

**4. Lakes with no R.** A lake with no gauge, no United Utilities overflow upstream, or under 30 days takes the
median R of the lakes that have one.

**5. Requests.**
- EA Hydrology only: one request for the station list, then one per chosen station.
- One process, one request at a time, 2 s apart, with the User-Agent in `config.EA_HEADERS`.
- Each response is cached in the scratchpad.
- No Open-Meteo, NRFA or other source.
- If the EA refuses (403), rate-limits (429) or fails (5xx), the script stops. I report it, and nothing is run.

What the rule cannot capture, stated now:
- A gauge on an inflow sees only that inflow's flow, not the lake's whole inflow.
- R is a median, so the wettest spill days pass more than this.
- The other two biases (full mixing, a low modelled upland mean flow) remain.

## The evaluation

As in `docs/LAKE-RESIDENCE-TEST-2026-10.md`, unchanged but for the mode and the file:
- **Harness:** `scripts/lake_residence_eval/` with `MODE=residence_spill` (`queue.sh`). `run_variant.sh` now gives
  the copied file to both residence settings, so the mode reads it.
- **Inputs:** the same frozen data folder: #205's inputs, overflow table `e6ef0459…`, network `b5724303`, 3,658
  cached rain files.
- **Runs, in a fresh scratch folder:**
  - `lake`: the default, run again;
  - `res`: `residence_spill` with `lake_residence_spill.csv`;
  - `ph01` to `ph20`: `residence_spill` with the R-adjusted times permuted across the same 282 lakes, numpy
    `default_rng(k)` (`make_placebos.py`).
- **Running:** offline (every outgoing connection refused and counted), one run at a time, each waiting for 5 GB
  free plus inactive memory.
- **Check:** `lake` reproduces 1,502 samples and LOYO Brier 0.0938.

## What counts as passing

The seven conditions of the first test, unchanged, with `res` now meaning `residence_spill`. `judge.py` applies
them.
1. **Brier:** LOYO, LOSO and forward; the upper end of the interval of the change is at most +0.0005.
2. **AUC:** all sites and rivers (LOYO); the lower end is at least −0.005.
3. **Cross-site rho:** the lower end is at least −0.05.
4. **Within-site rho:** both point changes are at least −0.01.
5. **Lakes:** the upper end of the lake LOYO Brier change is at most +0.0005.
6. **Placebos:** on each of LOYO Brier, LOYO AUC, LOYO AUC rivers and cross-site rho, at least one of the 20
   placebos is at least as bad as `res`. These are `summary.py`'s rounded figures, as stated before. The unrounded
   counts, from each run's held-out predictions, are reported beside them, as in the first test.
7. **Face check:** `tests/test_lake_residence.py` passes, including its new `residence_spill` test.

Every run must make 0 network attempts.

**What follows:**
- **All seven hold:** `residence_spill` becomes the default in a separate, final commit. Method page, README and
  LICENSE-DATA are updated, and EA Hydrology is credited as the terms page credits it. Left for Ethan to merge.
- **Any fails:** the default stays `lake`. #211 is a record, with `residence` and `residence_spill` as options.

## What will be reported

Whatever the verdict:
- R, its gauge and its number of days for Grasmere, Rydal Water, Windermere (N Basin) and Windermere (S Basin);
- how many of the 282 lakes are gauged with enough days, and the median R;
- Grasmere WwTW's weight at Rydal Water under `lake`, `residence` and `residence_spill`;
- the sum of weights at the Windermere sites (Waterhead, Lakeside YMCA, Fellfoot, Millerground, Rayrigg) under
  the same three;
- the seven conditions, and the record table of the first test.

## Seen before writing

- The first test's results.
- Its quartered-τ sensitivity: Rydal Water 0.0038.
- The coordinator's check (ddba70d) that the 282 rows match HydroSHEDS' own points file.
- No flow, no spill-day count and no R for any lake has been looked at.

---

## Results
