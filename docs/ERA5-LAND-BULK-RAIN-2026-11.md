# ERA5-Land bulk rain from the Copernicus CDS

Written 15 November 2026, before a CDS account exists and before any ERA5-Land value is downloaded or compared. Main
was at `6743baf2`. Code: `scripts/era5land/` (`fetch.py`, `to_cells.py`, `match_check.py`, `neighbour_check.py`,
`era5land_core.py`); tests: `tests/test_era5land.py`.

**Nothing on the site changes.** No forecast, frozen file, active window or the 2027 primary evaluation is touched.
This work sent no Open-Meteo request and no CDS request, and wrote nothing in a shared cache.

## Purpose

Backtests fetch archive rain from Open-Meteo, inside the same 9,000-call daily ration as the live builds
(`rainfall.DAILY_CALLS`). The coastal C1 protocol alone plans 3,171.4 weighted calls at 1,000 a day
([C1 protocol](COASTAL-C1-PROTOCOL-2026-11.md), section 3). One bulk ERA5-Land download from the CDS would hold every
hour, at every 0.1° point over Great Britain and Northern Ireland, from 1990 on, for no Open-Meteo call.

This record covers the download, a converter to the cached files' shape, and a check of whether the values match.
The thresholds for that check are stated here, before any comparison is run. It also records what the cached rain
is, measured on the cache itself.

## What the cached archive rain is

### Read in the code

- `rainfall.fetch_archive` sends `latitude` and `longitude` (10 cells a request, the 0.1° cell centres from
  `grid_cell`), `start_date` 1 January, `end_date` 31 December or 6 days ago, `hourly=precipitation` and
  `timezone=UTC` to `https://archive-api.open-meteo.com/v1/archive`. **It sends no `models` parameter.**
- The other rain fetchers (`fetch_rain_nine.py`, `train_multi_year.py`, `check_ecoli_wales.py`,
  `fetch_rain_validation.py`) either call `fetch_archive` or build their own hourly precipitation request. None
  names a model. Only the
  C1 fetcher names one (`era5_land`), and it has not run: its first allowed day is 22 November 2026.
- With no model named, Open-Meteo uses its default, `best_match`.
- `_to_frame` stores the requested cell centre and drops the `latitude` and `longitude` that Open-Meteo returns. So
  the cache does not record which grid point served each cell.
- Files: `data/cache/rain/archive_<lat>_<lon>_<year>.parquet`, and the same names in `rain_nine`, `rain_multi`,
  `rain_w10` and `rain_rivers` (some tags are `2023dec` or `2026a`). Columns: `cell_lat`, `cell_lon` (double),
  `time` (timestamp[us, UTC]), `precip_mm` (double). The newest files add `air_c` and `elevation_m`. One row an hour,
  00:00 on 1 January to 23:00 on 31 December, UTC.
- Code comments call this rain ERA5-Land (`rainfall.py`'s docstring, `config.py`, `training.load_rain`,
  `fetch_rain_archive.py`). The request does not ask for ERA5-Land. This PR does not change those comments.

### Read in Open-Meteo's published source (GitHub, 15 November 2026)

- The historical API's documentation page says the default Best Match "combines IFS HRES, ERA5 and ERA5-Land". It
  lists ERA5 at 0.25° from 1940, ERA5-Land at 0.1° from 1950 and ECMWF IFS at 9 km from 2017.
- The server code: the archive's default (`archive_best_match`) reads three sources, `era5`, `era5_land` and
  `ecmwf_ifs`. Their grids in that code: ERA5-Land a regular 0.1° grid from −90, −180 (so points sit on multiples of
  0.1°, like our cell centres); ERA5 a regular 0.25° grid; IFS the reduced Gaussian grid O1280.
- Hourly precipitation is the "Preceding hour sum": the value at 10:00 is the rain from 09:00 to 10:00.
- **Not read:** the rule that chooses among the three sources for a given place and hour. I did not find it in the
  files I opened.

### Measured in the cache (read only, 15 November 2026)

- 234 cached files sampled, 1,435,488 hourly values: every one a multiple of 0.1 mm, none negative, none missing.
- If the rain came from ERA5-Land's 0.1° grid, no two neighbouring 0.1° cells would hold the same series. Many do.
  `neighbour_check.py` takes each pair of neighbouring cached cells (east-west and north-south), compares the year's
  hourly series, and asks how often each grid's nearest-point rule predicts exactly the identical pairs:

| Cache, year | Neighbour pairs | Identical | Rule agrees: IFS O1280 nearest | ERA5 0.25° nearest | ERA5-Land 0.1° |
|---|---|---|---|---|---|
| `rain_multi` 2020 | 390 | 88 | 94.1% | 53.3% | 77.4% |
| `rain_multi` 2021 | 384 | 89 | 93.5% | 55.2% | 76.8% |
| `rain_multi` 2022 | 395 | 91 | 93.4% | 54.4% | 77.0% |
| `rain` 2023 | 605 | 133 | 95.2% | 43.8% | 78.0% |
| `rain` 2024 | 1,026 | 228 | 94.0% | 46.1% | 77.8% |
| `rain_nine` 2025 | 2,034 | 437 | 95.3% | 36.0% | 78.5% |
| `rain` 2026 (to 6 Oct) | 243 | 48 | 96.3% | 38.3% | 80.2% |

- Identical pairs run east-west far more than north-south (`rain` 2024: 215 of 539 east-west, 13 of 487
  north-south). O1280 points over the UK are about 0.07° apart in latitude and about 0.16° apart in longitude, so two
  0.1° cells side by side often share one point.
- The three cache folders' file listing (name, size, modified time) had the same SHA-256 before and after these reads
  (`4b52dd43…`).

### Inferred

- The cached archive rain for 2020 to 2026 most likely comes from the IFS analysis, not from ERA5-Land. The 4% to 7%
  of pairs the O1280 rule does not explain may be Open-Meteo's choice of a land point near the coast. Not checked.
- IFS in `best_match` starts in 2017, so earlier years would come from ERA5-Land or ERA5. No cached file is older than
  December 2019, so this is not measured. A backtest on `best_match` rain that spans 2016 and 2017 may change source
  partway.
- So ERA5-Land from the CDS is not expected to equal the cached files hour by hour. It may still be close day by day.
  The match check asks the two questions separately.

## How the model takes rain (read in the code)

- `training.load_rain` reads `config.CACHE / "rain"` and `config.CACHE / "rain_nine"`, by file tag, from a start date.
- `features.daily_rain_features` takes hourly UTC rows and makes each day from `time.dt.floor("D")` of the
  hour-ending label. So a model day is the 24 hours ending at 23:00 UTC. A day with fewer than 20 finite hours is
  unknown. From the hours it takes the day's total and its wettest 1, 3 and 6 hours; from the days, 1- and 2-day lags,
  3-, 7- and 30-day sums and the antecedent index.
- A drop-in must therefore be hourly, in UTC, labelled by the end of the hour, in mm, one file per cell-year with the
  same columns. `to_cells.py` writes exactly that, and a test runs `daily_rain_features` on its output.

## ERA5-Land facts used

From ECMWF's "ERA5-Land: data documentation" (confluence.ecmwf.int), read 15 November 2026:

- `tp` (total precipitation) is in metres.
- Accumulations run from 00 UTC. At 00 UTC "the accumulations are over the 24 hours ending at 00 UTC".
- The CDS serves only a regular 0.1° × 0.1° grid.
- Final data come about two months after the month. ERA5-Land-T (preliminary) runs about 5 days behind. The record
  starts in January 1950.
- Total precipitation is a forcing field: ERA5's, interpolated to the ERA5-Land grid, not made by the land model.

From the `cdsapi` source on GitHub (master, version 0.7.8.dev0; latest tag 0.7.7, 30 September 2025):

- `~/.cdsapirc` holds `url: https://cds.climate.copernicus.eu/api` and `key: <PERSONAL-ACCESS-TOKEN>`.
- `CDSAPI_URL` and `CDSAPI_KEY` override the file; `CDSAPI_RC` names another file.
- A key without a colon goes to the new CDS client (`ecmwf.datastores.legacy_client.LegacyClient`, from the
  `ecmwf-datastores-client` package, which master's `setup.py` requires; the 0.7.7 release itself was not read). A
  `UID:KEY` key is the old CDS's form.
- `retrieve(name, request, target)` downloads to `target`.
- The README says to accept the terms of every dataset before downloading it.

## The download: `fetch.py`

| | |
|---|---|
| Dataset, variable | `reanalysis-era5-land`, `total_precipitation`, every hour |
| Area (N, W, S, E) | 61.0, −8.3, 49.8, 2.0: Great Britain, Northern Ireland and Shetland. Every cached cell lies inside (49.9 to 60.2 N, 6.5 W to 1.8 E). `--area` changes it |
| Grid | 113 rows × 104 columns = 11,752 points |
| Requests | One a month, as NetCDF, not zipped. January 1990 to August 2026 (three months before today, so no preliminary month): 440 requests. Newest first, so the years the match check needs arrive first |
| Size | At most 15.1 GB (every point, every hour, as 4-byte floats; 35 MB a 31-day month). The files should be smaller: the NetCDF is compressed and sea points hold no value. Not measured: the first month gives the real size |
| Time | Not known. At an assumed 3 to 20 minutes a request (the CDS queue varies), 22 to 147 hours one at a time. Two shells with separate `--start`/`--end` ranges may run two at a time (the CDS's limit per user was not checked). The ledger measures the real figure; `--status` projects from it |
| Disk | 49 GiB free on this Mac on 15 November. Converted cells: cached full-year files average 80 KiB (787 files in `rain` 2024; 78.8 KiB in `rain_nine` 2025). For the 2,076 cached cells over 37 years that would be about 6 GB, if ERA5-Land files compress the same (inferred) |

Rules:

- `--dry-run` and `--status` send nothing and need no key.
- A month whose file is on disk is never asked for again, so the same command resumes. The file is written as
  `.part` and renamed only when whole and when it starts like NetCDF or a zip.
- The first failure stops the run, since a missing licence or key fails every month alike. The CDS client retries
  passing errors itself.
- Ceilings per run: 480 requests, 30 GB, 24 hours, and 2 GB of disk kept free. Reaching one stops the run cleanly.
- Every request is one line of `<out>/ledger.jsonl`: the request, start time, seconds, bytes, SHA-256 and outcome.
- `--out` may not be inside a `data/cache` folder. The key is checked for the new CDS's form before any request and
  is never printed.

## The conversion: `to_cells.py`

- **Hourly rain from the running total.** For the hour ending at t: `tp(t) − tp(t − 1 h)`, except the hour ending at
  01 UTC, which is `tp(01)` itself. The hour ending at 00 UTC is the day's total less its first 23 hours. Metres × 1000
  gives mm. A difference below 0 is set to 0 (stored precision); differences below −0.05 mm are counted in the
  manifest, since many would mean the times are wrong. An hour whose previous step is missing is NaN, never 0.
- **Labels.** The value is labelled by its valid time, the end of the hour, as Open-Meteo labels its "preceding hour
  sum". The first hour of a year (00:00 on 1 January) needs the previous 31 December's 23:00 value, so that month is
  read too. Without it the hour is NaN.
- **Rounding.** To 0.1 mm by default, the cached files' step, so wet-hour counts and the wettest hour behave as in
  the files the models were fitted on. `--round 0` keeps full precision.
- **Cells.** The same snapping as `rainfall.grid_cell` (a test checks they agree). A cell takes its own grid point when
  that point has data. ERA5-Land has no value over the sea, so a coastal cell whose own point is sea takes the nearest
  point with data within one grid step. Otherwise it gets no file. Each choice is in `ERA5LAND_CELLS.csv`.
- **Output.** `<out>/cache/rain/archive_<lat>_<lon>_<year>.parquet`, with the cached files' four columns and types,
  and `ERA5LAND_MANIFEST.json` (rules, each month's SHA-256, months used per year, code commit).
- **Pointing a backtest at it.** With `DIPCAST_CACHE=<out>/cache`, `training.load_rain` reads these files instead of
  the shared cache. A loader that fetches missing cells (`rainfall.fetch_archive`) would ask Open-Meteo for any cell
  not converted, so convert every cell a backtest needs first.

## The match check: `match_check.py`

It pairs converted cells with Open-Meteo files for the same cell and hour, and reports hourly and daily correlation,
mean difference, share within a tolerance, and the worst cells. Days are model days (above), with at least 20 paired
hours. Hourly correlation at lags of −1 and +1 hour is reported, not judged, to show a one-hour label shift. The
reference files are only read; their SHA-256 is taken before and after, and the report says whether any changed.

Which ERA5-Land series a reference cell is paired with: its own cell. For an `era5_land` reference whose files record
the grid point Open-Meteo used (`grid_lat`, `grid_lon`, as C1's files do), that point instead, so a coastal cell is
compared with the same point on both sides. Convert those points too (`to_cells.py --all-land` covers every one).

`--kind` says what the reference is, and so which thresholds apply. **These are fixed now, before any comparison, and
do not change after a result is seen.**

**`era5_land`: the reference was fetched from Open-Meteo with `models=era5_land`.** Same product, so this tests the
pipeline: times, units, de-accumulation and cell mapping. PASS needs all four.

| Test | Measure | Pass when |
|---|---|---|
| S1 | Share of paired hours with \|ERA5-Land − reference\| ≤ 0.1 mm | ≥ 0.99 |
| S2 | Share of cells (100 or more hours of 0.1 mm or more) with hourly r ≥ 0.99 | ≥ 0.98 |
| S3 | \|mean daily difference\| | ≤ 0.02 mm, or 1% of the reference's mean daily total if that is larger |
| S4 | Share of paired cell-days within 0.5 mm | ≥ 0.99 |

**`best_match`: the reference is the cached archive files.** Most likely a different product from 2017 on (above),
so this asks
whether ERA5-Land can stand in for the cached rain without refitting. PASS needs all four.

| Test | Measure | Pass when |
|---|---|---|
| B1 | Pooled daily r | ≥ 0.90 |
| B2 | \|mean daily difference\| ÷ the reference's mean daily total | ≤ 0.10 |
| B3 | Share of paired cell-days within 0.5 mm | ≥ 0.85 |
| B4 | Share of cells (30 or more days of 1 mm or more) with daily r ≥ 0.80 | ≥ 0.90 |

No verdict with fewer than 10 cells, or fewer than 1,000 (`era5_land`) or 10,000 (`best_match`) paired cell-days.

What each result decides:

- `era5_land` PASS: a backtest that names `era5_land` (C1, and later ones) can read the CDS files instead of fetching
  from Open-Meteo. FAIL: do not substitute. The lag correlations and per-cell ratios show whether it is a label
  shift, units or cell mapping.
- `best_match` PASS: ERA5-Land may stand in for the cached rain in a frozen-model backtest without refitting, recorded
  as a source change. FAIL: a backtest on ERA5-Land fits and tests on ERA5-Land throughout, as C1 already plans. Never
  fit on one source and test on the other.

**Expectation, written before any data:** the `best_match` check is more likely to fail than the `era5_land` check,
because the cached rain from 2017 on appears to be IFS, not ERA5-Land. This is a prediction, not a result.

**The `era5_land` reference does not exist yet.** No Open-Meteo `era5_land` rain is on disk. The cheapest source
already planned is C1's first fit season: 2026, 185 coastal cells, 19 requests, 211.4 weighted calls, allowed from 22
November. Whether C1 then takes the rest of its rain from the CDS instead of Open-Meteo is a change to its protocol,
for Ethan to decide in a dated amendment. This record does not make it.

## What Ethan does to start it

Run these from a checkout that has this PR.

1. **Register** at https://cds.climate.copernicus.eu ("Login - Register", top right). You will know it worked when you
   can log in and open your profile page.
2. **Accept the ERA5-Land licence.** Open the ERA5-Land hourly dataset page (search "ERA5-Land hourly data from 1950
   to present" on the CDS; I believe the address is https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land,
   not checked). Go to the Download tab, scroll to "Terms of use", and accept. You will know it worked when that box
   says the licence is accepted.
3. **Save the key.** Copy the Personal Access Token from your profile page, then in Terminal (paste the token in place
   of `TOKEN`):

   ```
   printf 'url: https://cds.climate.copernicus.eu/api\nkey: %s\n' 'TOKEN' > ~/.cdsapirc
   chmod 600 ~/.cdsapirc
   cat ~/.cdsapirc
   ```

   You will know it worked when `cat` shows two lines and the key has no colon in it.
4. **Dry run:**

   ```
   uv run python scripts/era5land/fetch.py --out "$HOME/dipcast-scratch/era5land" --dry-run
   ```

   It prints 440 requests, the first `2026-08` and the last `1990-01`, and sends nothing.
5. **Fetch:**

   ```
   uv run --extra era5 --with "cdsapi>=0.7.7" python scripts/era5land/fetch.py --out "$HOME/dipcast-scratch/era5land"
   ```

   You will know it works when it prints one line a month, `2026-08: <size> MB in <minutes> min`, starting with
   `2026-08`. Leave it running.
   After any stop, run the same command again: it carries on from the first month not on disk.
6. **Check progress** at any time (sends nothing):

   ```
   uv run python scripts/era5land/fetch.py --out "$HOME/dipcast-scratch/era5land" --status
   ```

   After the first month it shows the real MB a month, minutes a request and the projected hours left.

**The likeliest mistake: not accepting the dataset's licence (step 2).** The account and the key work, but every CDS
dataset has its own terms, accepted on its own page. The first request then fails with an error saying the required
licences are not accepted. The fetcher stops, logs the outcome `licence` and prints what to do. Accept the terms and
run step 5 again. The next likeliest: a key copied from an old guide in the form `12345:abcd...`, or a url ending
`/api/v2`. The fetcher refuses both before sending anything.

Once months are on disk, the next steps (for Ethan or a session):

```
uv run --extra era5 python scripts/era5land/to_cells.py --out "$HOME/dipcast-scratch/era5land" \
    --cells-from ~/Documents/GitHub/dipcast/data/cache/rain --cells-from ~/Documents/GitHub/dipcast/data/cache/rain_nine \
    --years 2023-2025
uv run python scripts/era5land/match_check.py --era5land "$HOME/dipcast-scratch/era5land/cache/rain" \
    --reference ~/Documents/GitHub/dipcast/data/cache/rain --reference ~/Documents/GitHub/dipcast/data/cache/rain_nine \
    --kind best_match --years 2023-2025 --report "$HOME/dipcast-scratch/era5land/match_best_match.json"
```

## What I could not check

- The CDS's per-request size limit. One month over this area is assumed to fit; no request was sent.
- The exact wording of the licence error. The fetcher matches "licence", "license" or "terms".
- What the new CDS's NetCDF looks like for ERA5-Land. The reader takes `valid_time` or `time`, packed or plain
  floats, NaN or a fill value, an extra `expver` axis, a zip, and longitudes from 0 to 360. GRIB is refused.
- Time per request and real file size.
- The new CDS client's own `retrieve` (in `ecmwf-datastores-client`). I read `cdsapi`'s code, which hands a token key
  to that client, but not the client.
- `cdsapi` is not in `uv.lock`. Adding it needs a lookup on PyPI, which this work did not make. The `era5` extra holds
  only `h5py` for now, and the fetch command adds `cdsapi` with `--with`. To lock it:
  `uv add --optional era5 "cdsapi>=0.7.7"`.
- Open-Meteo's rule for choosing among `best_match`'s three sources.
- The dataset page's address in step 2.

## What follows

- Ethan: the six steps above. Owner of the download: Ethan. Next check: the first month's ledger line (size and
  minutes), then `--status`.
- Then convert 2023 to 2025 for the cached cells and run the `best_match` check. Record the result under a results
  line in this file, with the report's SHA-256.
- Then the `era5_land` check, once an `era5_land` reference exists (C1's first season, or another named fetch).
- If the cached rain is confirmed as IFS from 2017, correct the code comments that call it ERA5-Land, in their own PR.
