# Met Office data: what is free, and what SwimSignal should do with it

Written 24 October 2026. Every page named here was read that day. Labels: **[read]** on a fetched
page; **[checked]** by a request to the live service or by opening its files; **[inferred]** my
reading, not on any page. The review of 16 October (`docs/REVIEW-2026-10-16.md`, section 4, "Ruled
out") set aside Met Office DataHub and CEDA radar. It did not know about the Met Office's radar on
AWS, which needs no account.

## In short

- One new free source matters: **UK radar rain rate on AWS**. It is a 1 km UK composite every 15
  minutes, out within 20 minutes, with no account and no key. Licence CC BY-SA 4.0.
- **The bucket keeps about two years and then deletes.** Its oldest file is 21 Nov 2024 09:30 UTC
  [checked]. If the window is exactly two years, that month starts to go on about 21 Nov 2026.
- This PR adds `scripts/fetch_met_office_radar.py`. It keeps hourly radar rain per SwimSignal rain
  cell, in `data/raw/met_office_radar/`. It adds no model input and changes nothing on the site.
- **Ethan's step:** run the backfill before 20 November (section 6). It takes about 7 hours.
- For training truth, **HadUK-Grid** (1 km daily rain from gauges, OGL) should beat ERA5-Land,
  which has no gauges in it [inferred]. It runs only to the end of 2025 and needs a free CEDA
  account.

## 1. What SwimSignal already gets from the Met Office

- **Forecast rain.** The build's rain is Open-Meteo's forecast, which for England is the Met
  Office's (`src/dipcast/pages/methods.html`). The terms page credits it under CC BY-SA 4.0.
- **Ensemble rain.** The MOGREPS-UK members, through Open-Meteo (`config.ENSEMBLE_MODEL`,
  `ukmo_uk_ensemble_2km`), for the band on days 3 to 5.
- **Nothing observed.** The models were trained on ERA5-Land, a reanalysis from Copernicus, not
  the Met Office. No observed rain reaches the site. The "right now" rule holds the forecast
  (review task D6).

So the Met Office's share-alike licence is already in play. The radar adds no new kind of licence.

## 2. What exists, ranked by use to SwimSignal

| # | Source | What | Licence | Cost and limits | Account or key | Latest data |
|---|---|---|---|---|---|---|
| 1 | **AWS: Met Office UK Radar Observations** (registry.opendata.aws/met-office-uk-radar-observations) | Rain rate, 1 km, every 15 min, UK composite | CC BY-SA 4.0 [read] | Free. "Non-operational", no uptime promise [read] | None [checked] | Today, within 20 min [checked] |
| 2 | **HadUK-Grid** (CEDA, Met Office) | Daily rain from gauges, 1 km, 1891 on | OGL v3 [read] | Free | Free CEDA account [inferred] | v1.3.2, June 2026, to end of 2025 [read] |
| 3 | **CEDA Nimrod radar** | 1 km, 5-minute rain rate, 2004 on, NIMROD binary | OGL v3 [read] | Free | Free CEDA account [read] | Record says "Latest data update: 2025-07-18" [read] |
| 4 | EA real-time rainfall API (not Met Office) | About 1,000 gauges, 15-minute totals, sent "once or twice per day" | OGL v3 [read] | Free, no stated limit | None | About 28 days kept |
| 5 | AWS: UKV 2 km forecasts, 2-year archive; also on Microsoft Planetary Computer | Every run of the UK model, NetCDF | CC BY-SA 4.0 [read] | Free, "unsupported basis" [read] | None | 3 to 6 h after each run [read] |
| 6 | AWS: MOGREPS-UK, 30-day archive | Ensemble runs, 2.2 km | CC BY-SA 4.0 [read] | Free | None | 10 to 11 h after each run [read] |
| 7 | AWS land and marine observations; OSTIA sea temperature; NWS ocean model | Station and buoy readings, 7 days kept; 5 km SST | CC BY-SA 4.0; OSTIA CC BY 4.0 [read] | Free; OSTIA needs an order form and up to 15 working days | None; OSTIA by email | Hourly; daily |
| 8 | Met Office Weather DataHub, free tiers | Site forecasts 360 calls a day, land obs 360 a day, blended probabilistic 55 a day for one site, map PNGs 1,000 a day | Unnamed licence; the full terms sit behind a login [read] | Free tiers; paid from £9 a month | Key | Live |
| 9 | MIDAS Open (CEDA) | Station rain, hourly and daily | OGL v3 [read] | Free | Free CEDA account | Yearly; 10 to 22 months old [read] |
| 10 | DataPoint | — | — | Retired 1 Dec 2025 [read] | — | — |

Notes on the ranking:

- Rows 1 to 3 are the only ones that give observed rain on a grid. Rows 5, 6 and 8 duplicate what
  Open-Meteo already serves. Their only gain would be a lead-by-lead archive without Open-Meteo's
  ration, at hundreds of GB for two years of UKV [inferred].
- Row 3 and row 1 overlap from Nov 2024 to Jul 2025, so together they could give one radar series
  from 2004 [inferred]. Whether CEDA's record really stops in July 2025 was not checked.
- DataHub's free site forecasts are the same Met Office models as Open-Meteo's, at 360 calls a day
  against our 499 rain cells. The old AWS listing (registry.opendata.aws/uk-met-office) was CC BY-NC-ND
  and is retired. Do not use anything from its buckets.

## 3. What each new source would be for

**Observed rain for the "right now" rule (review task D6).** D6 plans the EA gauges, which arrive
"once or twice per day", so a day late. The radar is out within 20 minutes and covers every cell,
including the hills where gauges are few. It is the other candidate for D6, and the two could be
tested side by side. Live use would mean the build fetching the last few composites, about 0.5 MB
each [checked]. That is not in this PR.

**Truth for verifying forecast rain.** From Nov 2024 the radar gives observed hourly rain per cell.
Against it we can measure how wrong the forecast rain was at each lead, per cell and per season. The
same series can say whether the MOGREPS-UK band marks the days the rain forecast missed. The
ensemble test (`docs/ENSEMBLE-RAIN-TEST-2026-11.md`) is already stated, so this would be a separate
question, written down before it is run.

**HadUK-Grid as offline training truth.** The models train on ERA5-Land, about 0.1 degree, with no
rain gauges in it. HadUK-Grid is built from gauges at 1 km. It is daily only, so it fits the daily
rain features but not hourly timing. The Met Office's rain day runs 09:00 to 09:00 [inferred, not
read today]: check before joining it to our UTC days. It lags: 2026 arrives in about June 2027.

**Radar as training truth.** 15-minute, 1 km, and from Nov 2024 only. That covers the 2025 season,
which the evaluations already use. It is raw radar: see section 5 on what it measures.

## 4. Rules that apply

- **Any model use goes through a pre-stated test.** The question and the pass rule are written and
  committed before any result is seen (`docs/PREREGISTRATION-2027.md` and the test documents). This
  PR adds no model input.
- **The 2027 evaluation.** A logged forecast counts as the frozen model's only if its stamp says
  `rain=open-meteo-forecast` (`docs/PREREGISTRATION-2027.md`, section 2). Observed radar as a live
  input would change that stamp. Before 1 May 2027 it would need a dated amendment (section 17).

## 5. The radar files, as checked

Checked on 24 Oct 2026 from the bucket listing and three files opened with h5py: two from 24 Oct
2026 (00:00 and 00:15 UTC) and the oldest, 21 Nov 2024 09:30.

- **Where.** `https://met-office-radar-obs-data.s3.amazonaws.com/radar/YYYY/MM/DD/YYYYMMDDHHMM_ODIM_ng_radar_rainrate_composite_1km_UK.h5`.
  Anonymous HTTPS works. The S3 listing (`?list-type=2&prefix=radar/2026/10/24/`) needs no signing.
- **How many.** 96 files a day, at :00, :15, :30 and :45. 67,064 files, 33.6 GB, from 21 Nov 2024
  09:30 to 24 Oct 2026: 0.5 MB a file on average, from 0.2 MB (Jul 2026) to 0.8 MB (Nov 2024) by
  month. Wet days make bigger files.
- **Gaps.** Dec 2024 has 2,645 files on 29 of its 31 days, where a full month is 2,976. Six months
  from Aug 2025 are short by 1 to 15 files (Jul 2026: 2,961). Every other full month is complete.
- **Layout.** ODIM_H5 version 2.2. One array, `dataset1/data1/data`, float32, 2175 rows by 1725
  columns, gzip. Quantity `RATE`. gain 1.0, offset 0.0. `nodata` -1.0 (outside radar range: 2.58
  million of the 3.75 million pixels). `undetect` 0.0 (no rain seen).
- **Grid.** 1 km pixels. Origin "UPPER LEFT". `projdef` is a transverse Mercator with British
  National Grid's numbers but no datum: `+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.999601 +x_0=400000
  +y_0=-100000 +ellps=airy`. The corner coordinates put the outer edges at x -405 km to 1,320 km
  and y -625 km to 1,550 km. The script uses EPSG:27700, British National Grid with its datum. The
  two place a point at 52 N 1 W about 115 m apart, an eighth of a pixel.
- **Units.** ODIM's `RATE` is rain rate in mm/h [inferred from the ODIM standard; not read today].
  The one-day check in section 7 gives totals of the same size as the forecast's, which fits mm/h.
- **Time.** Each file is a snapshot, not a total. Its scan window lasts about a minute, within a
  minute of the time in its name: the 00:15 file of 24 Oct scanned 00:14:07 to 00:15:09, the 00:00
  file 23:58:42 to 23:59:44.
- **How it is made.** `software` RADARNET, `zr_a` 200 and `zr_b` 1.6 (the Marshall-Palmer
  relation from reflectivity to rain), `VPRCorr` True (corrected for the vertical profile). 15
  radars named in Nov 2024 and 17 in Oct 2026. The node names include one in Ireland (`iesha`) and
  one on Jersey (`ukjer`) [inferred from the names].
- **Not known.** Whether it is adjusted to gauges. Nothing in the file says so. Treat it as raw
  radar, which can over-read in bright bands and under-read far from a radar or behind hills
  [inferred].

## 6. The fetcher

`scripts/fetch_met_office_radar.py`, off CI, with h5py from the optional `radar` group. The site
build does not install it.

    uv run --extra radar python scripts/fetch_met_office_radar.py 2024-11-21 2026-10-23

- **Cells.** By default every cell with a `forecast_` or `leads_` file in the rain cache: 499 cells
  in the main checkout's cache on 24 Oct. Or `--cells` with a CSV.
- **Per cell.** The mean rate over the radar pixels whose centre falls in the cell, by the same
  `rainfall.grid_cell` the sites use. A 0.1 degree cell holds 66 to 84 pixels.
- **Per hour.** Hour-ending UTC, as Open-Meteo labels its hours. The hour ending T is the trapezoid
  over the snapshots at T-60, T-45, T-30, T-15 and T. Pixels with no data are left out.
  `coverage` is the share of the hour's pixel samples that had data, so a missing file shows.
- **Output.** `data/raw/met_office_radar/radar_<cell>_<YYYY-MM>.parquet`: cell_lat, cell_lon, time,
  radar_mm, coverage. The credit travels in the parquet metadata. Raw files are not kept.
- **Resumable.** A cell's day is skipped when its month file has all 24 hours. A stopped run starts
  again where it stopped. One request at a time, 0.2 s apart, five tries with a growing wait.
- **Time and disk.** One day took 37 s for 97 files. The cell count hardly matters. The 702 days
  from 21 Nov 2024 to 23 Oct 2026 are about 7 hours and 34 GB downloaded. The cell totals are about 11.5 KB per cell-month, so 499
  cells for two years is about 140 MB.

- **Per overflow.** With `--overflows` (an overflows table) the script also keeps the rain at each storm
  overflow's own position. It takes the 1 km pixel whose square holds the overflow's lat/lon, and the eight around
  it (fewer at the grid's edge). `radar_mm` and `coverage` pool that 3 x 3 block the same way as a cell;
  `centre_mm` and `centre_coverage` are the one pixel. One file per UTC day,
  `<out>/overflows/radar_overflows_<YYYY-MM-DD>.parquet`, with `overflow_pixels.parquet` listing each overflow's
  pixel. Every file carries the overflow table's SHA-256, its `network_key` and the pixel rule in its metadata, and
  a folder refuses a second table. A day is skipped when its file exists. `--no-cells` skips the rain cells.

      uv run --extra radar python scripts/fetch_met_office_radar.py 2024-11-21 2026-10-25 --no-cells \
          --overflows data/processed/overflows.parquet --out ~/somewhere-outside-the-checkout

  Trial, 23 Nov 2024 (Storm Bert), 14,630 overflows: 97 composites in 46 s, 351,120 rows, 0.8 MB with zstd. The
  overflows' day totals follow their cells' (r 0.96 over 470 cells) but spread within a cell, from 19.7 to 30.0 mm
  among 49 overflows in one. A wet day is the largest file, so the 702 days come to a few hundred MB, not the tens
  of MB first guessed.

**A decision for Ethan: keep the raw files too?** The cell totals cover today's cells only. A spot
added next year in a new cell would have no radar history before it was added, and a catchment
mean could not be made later. Keeping the raw files costs about 34 GB now and 1.4 GB a month. The
script does not keep them. If wanted, it is a small change, or a plain `aws s3 sync
--no-sign-request` to a spare disk.

## 7. One day, run for real: 6 Feb 2026

Eight cells, chosen spread across England, on a day of rain almost everywhere. Radar against
lead 0 of the cached forecast (`leads_<cell>_2026.parquet`, Open-Meteo's latest run for each
hour). 97 composites read, none missing, coverage 1.0 in every hour.

| Cell | Pixels | Radar mm | Lead 0 mm | Radar / lead 0 | Hourly r | Wet hours radar / lead 0 |
|---|---|---|---|---|---|---|
| 50.9, -1.8 | 77 | 8.2 | 9.4 | 0.87 | 0.46 | 11 / 16 |
| 51.5, -0.2 | 75 | 8.3 | 12.0 | 0.69 | 0.41 | 13 / 17 |
| 51.7, -1.6 | 77 | 18.5 | 20.5 | 0.90 | 0.39 | 18 / 21 |
| 52.3, 1.2 | 76 | 7.2 | 15.4 | 0.47 | 0.62 | 13 / 18 |
| 52.6, -2.9 | 74 | 7.9 | 24.3 | 0.33 | 0.56 | 19 / 20 |
| 53.0, -1.4 | 78 | 26.9 | 29.6 | 0.91 | 0.70 | 21 / 23 |
| 54.1, -1.7 | 77 | 22.0 | 31.3 | 0.70 | 0.21 | 23 / 24 |
| 54.4, -2.9 | 77 | 46.5 | 16.8 | 2.77 | 0.12 | 21 / 17 |

All eight: radar 145.6 mm, lead 0 159.3 mm. Hourly correlation 0.31, mean absolute difference
0.66 mm an hour. A wet hour is 0.1 mm or more. Shifting the radar by one hour either way lowers the
pooled correlation (0.26 one way, 0.18 the other), which fits the hour-ending labels.

This shows the script runs and the numbers are the right size. One day says nothing about which
source is nearer the truth. The Lake District cell (54.4, -2.9) reads almost three times the
forecast. That could be real hill rain the model missed, or radar error. A gauge would settle it.

## 8. Licence and terms

- **Credit.** "British Crown copyright 2024-2025, the Met Office, licensed under CC BY-SA 4.0"
  (registry page). The script writes it into every file.
- **ShareAlike.** Our cell totals are Adapted Material. Internal evaluation is fine. Shared
  outside SwimSignal, they must go out under CC BY-SA 4.0 with the credit. Publishing a radar grid
  or the cell files would make them CC BY-SA.
- **Derived scores.** Whether a spill risk or a pilot briefing computed with radar rain is Adapted
  Material is the same open question as for the Met Office forecast rain we already use
  (`docs/ORGANISER-PIVOT-2026-10.md`, "Met Office share-alike"). **Add to the solicitor's list**,
  with paid pilots in view: does a forecast or briefing computed from CC BY-SA rain inherit the
  licence?
- **No support.** The registry says "non-operational" and the Met Office calls these channels
  "public BETA", with replies in 3 to 5 business days. A paid pilot must not depend on the radar
  without a fallback to the forecast.
- **DataPoint** was retired on 1 Dec 2025. Its radar images moved to a paid service.
- **DataHub** commercial use rests on its FAQ. The terms themselves were not readable without a
  login.

## 9. Open

- Run the backfill before about 20 Nov 2026 (Ethan; section 6). Decide on keeping raw files.
- Units mm/h rest on the ODIM standard, not on a Met Office page. Gauge adjustment is unknown.
  The Met Office service desk (servicedesk@metoffice.gov.uk) could answer both.
- The exact deletion rule (two years to the day, or by month) is not stated. Run the backfill
  oldest first, which the script does.
- Whether radar helps D6 or forecast-rain checks needs its own pre-stated test.
- **Rain at each overflow, not each cell (deadline about 20 Nov 2026).** Built: section 6, "Per overflow". The
  backfill is a data save only; using it still needs everything below. The fetcher averages the 1 km radar into
  0.1° rain cells (about 10 km), so the backfill keeps the measured rain but loses where in the cell it fell. A storm
  over one town and not the next is averaged out. Keeping it means a second output: the radar at each overflow's own
  position (its pixel and the eight around it), for the ~14,600 overflows, tens of MB rather than the 34 GB of raw
  files. Then the backfill runs once more, before the bucket deletes Nov 2024 (about 21 Nov 2026). Using it in the
  model needs a retrain on local rain (the model learned rain at ERA5-Land's ~9 km) and its own pre-stated test.
  It would help the "right now" level most; forecasts for the days ahead cannot be that local.

Sources read on 24 Oct 2026: the AWS registry pages for radar, UKV, MOGREPS-UK, land and marine
observations, NWS ocean and the retired uk-met-office listing; the Met Office radar factsheet
(asdi-radar-1km.pdf); metoffice.gov.uk pages on external data channels, DataPoint retirement,
the marine data service, HadUK-Grid and the Planetary Computer blog; DataHub's pricing pages and
FAQ; CEDA catalogue records for HadUK-Grid, MIDAS Open and Nimrod; the EA rainfall API docs.
