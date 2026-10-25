# Sea currents and coastal E. coli: what the repo has, and what a test would need

Written 24 October 2026. Main was at 9be5601. This is a scoping note, not a test. No current data was fetched and
nothing was scored.

## The answer

**A sea-currents test cannot be run yet, because there is no coastal model to add currents to.**
- The samples exist. The EA Water Quality Archive holds 32,874 statutory E. coli samples at 404 of the 426 English
  coastal and estuary bathing waters for 2022 to 2026. They are not in the repo as a table.
- The site does not forecast coastal waters. It shows the EA's own advice, rating and latest sample beside a
  directory. Overflows that discharge to the sea are left out of river tracing, so no coastal spot has a SwimSignal
  risk.
- Overflow positions exist for all of them, but nothing joins an overflow to a coastal bathing water.

A currents feature says which way an overflow's water went after a spill. It is only worth testing once there is a
coastal figure for how much spilled nearby. Building that figure is a new model, so this note stops here, as the task
said it should. The staged plan below says what each step would take, if coastal spots become a priority.

## 1. Coastal E. coli samples

Fetched today from the EA Water Quality Archive, for the archive sampling points in
`data/raw/coastal_wqa_points.json` (407 of the 426 sites are mapped; `scripts/map_coastal_wqa.py`). Statutory
samples only (`MS`), determinand 2348 (E. coli, confirmed, membrane filtration), as `coastal.latest_samples` reads
them.

| Year | Samples | Bathing waters | First | Last |
|---|---|---|---|---|
| 2022 | 6,758 | 400 | 28 Apr | 7 Dec |
| 2023 | 6,735 | 401 | 24 Feb | 26 Sep |
| 2024 | 6,464 | 400 | 1 May | 25 Sep |
| 2025 | 6,579 | 399 | 1 May | 3 Oct |
| 2026 | 6,338 | 403 | 15 May | 26 Sep |

Established, from that fetch:
- 404 bathing waters have at least one sample: 359 coastal and 45 estuary. 19 sites are not mapped to an archive
  point, and 3 mapped sites have no sample in these years.
- 20 to 105 samples a site, median 85. All but 7 samples fall in May to September.
- 64.7% of results are below the detection limit (a "<" result). A rank test on log E. coli has many ties.
- Bad results are rare: 1.5% are over 500 cfu/100 ml, and 223 samples (0.7%) are 1,000 or more.
- The archive goes back further. Two sites checked hold about 280 statutory samples each, back to at least 2012.

The archive refuses a query for several points over more than one year ("the maximum temporal range is 1 year").
`ingest/wqa._observations` sends no end date, so it fails for a multi-year range over several points. The fetch above
asked one calendar year at a time, 25 points a request. That is the recipe if the table is built.

For comparison, the inland E. coli model is fitted and tested on 2,165 samples at 38 bathing waters. The coast has
about fifteen times as many samples.

## 2. How the site handles the coast today

- **No forecast.** `spots.csv` has 89 spots, all river (58) or lake (31). `spots-osm.csv` has 16, also river or lake.
  The coverage page says the inland model "is not a coastal forecast".
- **A directory** of the 426 coastal and estuary bathing waters (`coastal.py`, `data/coastal.json`), with the EA's
  rating, the latest archived sample, and "Today's EA advice", which loads the EA's own widget in the reader's browser.
- **The EA's own forecast.** In season the EA publishes a daily pollution risk forecast at some sites. On
  15 September 2026, 175 sites had one (`PRF_PROVIDED`) and 276 did not (`docs/ROADMAP-2026-10.md`). The site passes
  this on. It does not make its own.
- **Overflows to the sea are not traced.** An overflow whose receiving water reads as marine gets
  `snap_confidence = "marine"` and is left out of river tracing (`overflows._second_pass`). 473 overflows are marked
  marine in the frozen evaluation table. Others near the coast snap to the river they discharge into.
- **The 2027 pre-registration** leaves coastal out (`docs/PREREGISTRATION-2027.md`, "Not tested here"). The
  expansion rules require positive held-out skill and an outside review before any coastal release
  (`docs/EXPANSION-2026-10.md`).

## 3. Overflows near each bathing water

Positions: yes. Joins: no. Every overflow in the table has a position: the live feed's, or the annual return's
outlet where the rules in `docs/OVERFLOW-POSITIONS-2026-10.md` and
`docs/OVERFLOW-SEA-OUTFALLS-2026-10.md` moved it. Distances below are from each bathing water's sampling point (from the
EA's catalogue, fetched today) to every positioned overflow in the frozen evaluation table (14,630 overflows).

| Within | Bathing waters with at least one overflow | Overflows a site, median | Most at one site |
|---|---|---|---|
| 1 km | 280 of 426 | 1 | 21 |
| 2 km | 369 | 2 | 30 |
| 5 km | 423 | 9 | 99 |
| 10 km | 426 | 25 | 162 |

The nearest overflow is 0.68 km away at the median site (a quarter of sites within 0.33 km, a quarter beyond
1.33 km).

The annual returns have a "bathing water" field. A plain name match finds 304 coastal bathing waters named by at least
one overflow, 1,546 pairs in all. The median overflow that names a beach is 2.4 km from its sampling point; a tenth
are over 11.7 km away. This match was not checked by hand. Short names (for example "Seaton") will catch the wrong
beach.

Spill records: the EA's detailed EDM files in the frozen evaluation folder cover 2024 and 2025 for all nine English
companies. They hold events at 1,449 (2024) and 1,446 (2025) of the 1,786 overflows within 5 km of a coastal bathing
water. Earlier years exist for some companies (`docs/EARLIER-SPILL-HISTORY-2026-10.md`: Northumbrian 2020–24, Wessex
2020–23, Thames API from December 2022, South West Water monthly).

Inferred, not established:
- **The position is often not where the water enters the sea.** A storm overflow's position is the overflow
  structure or the end of a short pipe. A long sea outfall can carry the spill 1 to 3 km offshore. The bearing from
  overflow to beach, which a currents feature needs, can point the wrong way when the true outlet is offshore. The
  EA's bathing-water `features.json` files draw outfalls at 10 m, but carry no name or permit
  (`docs/OVERFLOW-SEA-OUTFALLS-2026-10.md`), so they cannot fix this alone.

## 4. Current data, re-checked today

| Source | Grid | Hours | Archive | Access | Licence |
|---|---|---|---|---|---|
| Open-Meteo Marine API (MeteoFrance SMOC) | 0.08°, about 8 km | hourly | from January 2022, plus a 10-day forecast | open, no key for non-commercial use | attribution required |
| Copernicus Marine, `NWSHELF_ANALYSISFORECAST_PHY_004_013` (AMM15) | 1.5 km | hourly and 15-minute surface currents | **29 Sep 2023 to 31 Oct 2026** for `cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT1H-i` | free Copernicus Marine account | Copernicus Marine licence |
| Copernicus Marine, `NWSHELF_MULTIYEAR_PHY_004_009` (reanalysis) | about 7 km | hourly surface currents | 1 Jan 1993 to 1 Sep 2026 | free Copernicus Marine account | Copernicus Marine licence |
| Met Office UKMCAS, AMM15 PHY | 1.5 km, 33 depths | hourly and 15-minute | **none**: each day's files run from 47 hours before to 168 hours after the run, and the folder keeps 3 days | order form by email, up to 15 working days | OGL v3, "© Crown copyright, Met Office" |

Established:
- **Open-Meteo.** `ocean_current_velocity` (km/h by default) and `ocean_current_direction`, which is the direction the
  current flows towards (0° north, 90° east). The data set is named "SMOC Currents, Tides": tides are in it. `sea_level_height_msl` is also
  hourly and includes tides. The docs page says "Accuracy at coastal areas is limited".
- **Copernicus AMM15.** The task brief said its temporal extent ended on 1 May 2024. The product page and its public
  catalogue (`stac.marine.copernicus.eu`) now give 29 September 2023 to 31 October 2026 for the hourly surface
  currents, so the 2024, 2025 and 2026 bathing seasons are there at 1.5 km. That covers the years with EDM files for
  all companies. The download needs a free account, which Ethan must register.
- **UKMCAS.** The Met Office's FAQ says historical data is not available through UKMCAS, and that only three days of
  files are kept. The order page says the Copernicus copy of AMM15 is there "for a limited time only".
- **AMM15 product sheet** (linked as 19 Nov 2025): surface currents `SSC` (`uo`, `vo`) hourly and every 15 minutes, sea
  surface height `SSH` hourly, NetCDF-4 by FTP or SFTP, about 08:30 UTC daily. The title says a 7-day forecast;
  the order page says 6.

So UKMCAS cannot back-test anything. It is a live feed for after a test passes. The order-form answers and the email
are drafted in `docs/UKMCAS-ORDER-DRAFT-2026-10.md`.

## 5. What 8 km currents can and cannot show

The median bathing water has its nearest overflow 0.68 km away. One Open-Meteo cell is about 8 km across. So the
overflow and the beach almost always share one cell, and the model's current there is an offshore current, smoothed
over the bay. Inshore, headlands, sandbanks and estuary mouths turn the flow in ways an 8 km grid cannot hold.

- **A pass at 8 km** would mean the broad tidal and wind-driven flow, projected onto the overflow-to-beach bearing,
  carries some signal. 1.5 km data would then most likely do at least as well.
- **A fail at 8 km** would not rule out currents. It would say the 8 km field does not resolve them. Only AMM15 at
  1.5 km, or a site model, could answer that. A fail at 1.5 km would be stronger evidence, though AMM15 also smooths
  the surf zone.
- **Both** depend on the bearing being right, which depends on where the outlet really is (section 3).

## 6. If coastal spots become a priority: a staged plan

Each stage is its own pre-stated test, in the house pattern (`docs/DRY-SPELL-TEST-2026-10.md` with
`scripts/dry_spell_eval/`): statement pushed first, then the harness, then the fetch, then an offline run from a
`git archive`, then results below the line. Each stage only starts if the one before passes.

**Stage A, the sample table.** Fetch the coastal samples as above into `data/raw`, with sampling time, result and
qualifier, for 2022 to 2026. A few hundred small EA requests. No Open-Meteo calls.

**Stage B, does spilling nearby explain coastal E. coli at all?** The coastal analogue of the inland model's
`risk_observed`: hours of recorded spill at overflows within a stated distance of the beach, in a stated window before
the sample, weighted by distance. Scored within site (Spearman on log10 E. coli) and by AUC over 500 cfu/100 ml, on
2024 and 2025, where every company has EDM files. If spilling nearby does not rank samples, the direction it went
cannot help, and the currents test should not be run.

**Stage C, currents.** Only if Stage B passes, with Stage B's exposure as the reference. A sketch for that statement,
not a statement:
- For each overflow in Stage B's set, the current's displacement over the stated window (the sum of hourly velocity
  vectors times one hour), projected onto the unit bearing from the overflow to the sampling point. Positive is towards
  the beach. Each overflow's spill weight is multiplied by a fixed function of that projection.
- The tide state at the sample hour, from `sea_level_height_msl` (rising or falling, and height against the day's
  range), as one extra fixed input. Fixed before any data is seen, not searched.
- Run first on Open-Meteo (cheap, no account), then on Copernicus AMM15 for the same rows. Both are reported,
  whatever they show.

**Open-Meteo cost for Stage C.** Three hourly variables over one May-to-September season are weight 3.3 a location
by Open-Meteo's rule (`rainfall.call_weight`). About 400 bathing waters over the 2024 to 2026 seasons is about 4,000
calls, or about 3 days at the 1,500-a-day share for this machine. Grouping sites by 0.08° cell would cut it.

**Power.** Exceedances are rare (0.7% at 1,000 or more) and two thirds of results sit at the detection limit. An AUC
over 500 rests on about 100 bad samples a year across all sites. The within-site rank score carries most of the test.

## 7. What Ethan decides

1. **Is coastal a priority before the 2027 season?** If not, nothing else here needs doing, and the order form can
   wait.
2. **If yes:** register a free Copernicus Marine account (steps in the order draft). Then say go for Stage A and
   Stage B.
3. **Send the UKMCAS order only after Stage C passes**, or if you want a 1.5 km live feed for another reason. It is
   free, but its files must be collected every day or they are gone.

## Sources fetched for this note

- EA Water Quality Archive, `environment.data.gov.uk/water-quality/data/observation`: about 170 requests, E. coli only.
- EA bathing-water catalogue, `environment.data.gov.uk/doc/bathing-water.json`: 3 pages, and the coastal snapshot
  through `coastal.fetch()`.
- Open-Meteo Marine API docs page (read only; no data request).
- Copernicus Marine product pages and public STAC catalogue for the two products above (metadata only).
- Met Office marine data service page, FAQ, AMM15 product sheet, Service Information Sheet and order form.

No Open-Meteo data requests were made. The frozen evaluation folder from the die-off test was read, not changed.
