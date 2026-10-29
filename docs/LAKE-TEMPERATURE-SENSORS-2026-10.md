# Live lake water temperature: what open sensors exist (27 October 2026)

This note is research, not a test. It was written after the second lake test failed (`docs/LAKE-TEMPERATURE-TEST-2026-10.md`), to see whether a measured lake temperature could stand in where the model cannot. Nothing on the site changes.

**In short:**
- No open feed covers a listed SwimSignal lake spot today.
- No England-wide live lake-temperature feed was found.
- There is some open, live lake-water data: one Environment Agency sonde sits inside a lake (Hoveton Great Broad), and three more sit on streams within 100 m of a lake.
- None is at, or a direct measure of the water at, a listed swim spot.
- No sensor here is to be wired into spot advice without a site match and a quality review.

## Sources checked, and what each is

| Source | What it is | Live lake water temperature? |
|---|---|---|
| EA dataset record "National Real Time Water Quality Data" ([record](https://environment.data.gov.uk/dataset/365df16f-1b80-4e0e-9ed9-1450e0238aef)) | Metadata only. OGL; attribution "© Environment Agency copyright and/or database right 2015. All rights reserved"; update frequency "continual". Its stated period is **1 January 2019 to 31 December 2022**, and its revision date is 12 January 2022, although data.gov.uk shows the record updated 1 August 2025. Its live link `telemetry-data.com/open?profile=EAWQLIVE` now redirects to the Hydrology Data Explorer (`environment.data.gov.uk/hydrology/explore`). The record proves the link is current, not that the feed is fresh: the freshness below comes from the API itself. | Leads to the next row. |
| EA Hydrology API, water-quality sondes ([API](https://environment.data.gov.uk/hydrology/doc/reference)) | Measurements of water at fixed sondes, every 15 minutes, published unchecked. This is what the Explorer's "Water Quality" layer shows, and what the site already uses for river temperatures. | **Yes, at 4 places near lakes** (below). |
| EA Flood Monitoring API ([reference](https://environment.data.gov.uk/flood-monitoring/doc/reference)) | Its "Temperature" parameter is dry-bulb **air** temperature; its scope is levels and flows. | No: air, not water. Excluded. |
| EA Water Quality Archive / Explorer ([FAQ](https://environment.data.gov.uk/support/faqs/275879249/275879414)) | Lab and field **samples**, lakes included, updated within two working days of a new sample. The two lake tests trained on it (determinand 0076). | Not real time. A possible future source for checking estimates, never a live safety signal. |
| UKCEH Upland Waters Monitoring Network ([data](https://uwmn.uk/data)) | "UWMN datasets are available on request for non-commercial purposes" (page read 27 Oct). | Not open; on request. |
| UKCEH/NERC EIDC 2025 lake monitoring datasets ([collection](https://catalogue.ceh.ac.uk/documents/bf30d6aa-345a-4771-8417-ffbcf8c08c28)) | Published CSVs contain fortnightly surface-temperature observations for Blelham Tarn, Esthwaite Water, Windermere North Basin and Windermere South Basin, 14 Jan–16 Dec 2025. Each dataset is under the Open Government Licence. EIDC says the observations are raw and not yet quality-controlled/calibrated, though TEMP is double-entered and visually checked. Sampling is at a marked buoy/deep point (Esthwaite's location is published). | Historical cross-check, not a live feed or a reading at a swim entry. Check date/location overlap with the EA training rows before calling any score independent; it must not change #419's preregistered verdict. |
| UKCEH lake buoys (Cumbria, Loch Leven, Llyn Conwy) ([long-term lakes monitoring](https://www.ceh.ac.uk/our-science/projects/long-term-lakes-monitoring)) | UKCEH's page (checked by Ethan, 27 Oct) says six automatic buoys (four in Cumbria, plus Loch Leven and Llyn Conwy) measure temperature at 12 depths, and real-time viewing is available. It does not state the licence of the raw data: **reuse and access terms need confirmation with UKCEH** (its "Work with us" section gives a Cumbrian lakes contact). Separate from the UWMN's non-commercial request terms above. | Best lead for Windermere and Esthwaite, on terms still to be confirmed. |

## The Hydrology API sondes within 100 m of a lake

Method: the 1,964 Hydrology API stations with a temperature measure, of which 173 are open (no `dateClosed`), tested against the 564 Environment Agency WFD lake outlines the site publishes (`data/anypoint/lakes.json`, simplified to 15 m; source: the EA's [WFD Lake Water Bodies Cycle 3](https://services1.arcgis.com/JZM7qJpmv7vJ0Hzx/arcgis/rest/services/WFD_Lake_Water_Bodies_Cycle_3/FeatureServer/1) layer, `src/dipcast/ingest/lakes.py`). Station list: [https://environment.data.gov.uk/hydrology/id/stations.json?observedProperty=temperature&_limit=3000](https://environment.data.gov.uk/hydrology/id/stations.json?observedProperty=temperature&_limit=3000). Five open stations are inside or within 100 m of an outline. **The five are four places:** the two River Ehen stations are either side of one footbridge.

Each has a water-temperature measure (`-temp-i-subdaily-C`, parameter "Temperature", unit °C, every 900 s). The latest readings were fetched at **20:12 UTC on 27 October 2026**. Every reading below is that observation, and every one was flagged **Unchecked**, which the Environment Agency defines as "raw input data that has not been inspected manually" ([quality flags](https://environment.data.gov.uk/support/faqs/275875350/275875384); see also [checked and unchecked data](https://environment.data.gov.uk/support/faqs/275875350/275875473)). So these are not quality-assured readings. The API's metadata gives the Open Government Licence v3. The API's times carry no zone suffix; the Environment Agency records all hydrology data in GMT, all year ([GMT](https://environment.data.gov.uk/support/faqs/275875350/275875667)), so the times below are UTC. The newest readings were 11 minutes before the fetch.

| Station | Where it is | Relation to the lake | Latest reading (UTC) | Nearest listed spot | Nearest listed lake spot |
|---|---|---|---|---|---|
| [`E08275A`](https://environment.data.gov.uk/hydrology/id/stations/E08275A) ([readings](https://environment.data.gov.uk/hydrology/id/measures/E08275A-temp-i-subdaily-C/readings.json?latest)) Hoveton Great Broad, opened 16 May 2025, NGR 631734,316282 | Norfolk Broads | **Inside** the lake ([WFD Hoveton Great Broad, GB30535977](https://environment.data.gov.uk/catchment-planning/WaterBody/GB30535977), 0.38 km²) | 20:01:03, 11.4 °C, Unchecked | 26.2 km (River Waveney, Outney Common) | 137.6 km (Rutland Water, Sykes Lane) |
| [`E04568A`](https://environment.data.gov.uk/hydrology/id/stations/E04568A) ([readings](https://environment.data.gov.uk/hydrology/id/measures/E04568A-temp-i-subdaily-C/readings.json?latest)) Cunsey Beck, Esthwaite outfall, opened 24 Mar 2023 | Cumbria | Outflow stream, 54 m from [Esthwaite Water, GB31229328](https://environment.data.gov.uk/catchment-planning/WaterBody/GB31229328) | 20:01:12, 10.51 °C, Unchecked | 4.9 km (Windermere, Rayrigg Meadow) | same |
| [`E04592A`](https://environment.data.gov.uk/hydrology/id/stations/E04592A) ([readings](https://environment.data.gov.uk/hydrology/id/measures/E04592A-temp-i-subdaily-C/readings.json?latest)) Mill Beck at the Windermere museum, opened 13 Apr 2023 | Bowness, Cumbria | **Inflow stream: measures stream water, not Windermere water**; 85 m from [Windermere (N Basin), GB31247007](https://environment.data.gov.uk/catchment-planning/WaterBody/GB31247007) | 20:01:22, 10.377 °C, Unchecked | 0.8 km (Windermere, Rayrigg Meadow) | same |
| [`ME1011`](https://environment.data.gov.uk/hydrology/id/stations/ME1011) ([readings](https://environment.data.gov.uk/hydrology/id/measures/ME1011-temp-i-subdaily-C/readings.json?latest)) / [`ME1011A`](https://environment.data.gov.uk/hydrology/id/stations/ME1011A) ([readings](https://environment.data.gov.uk/hydrology/id/measures/ME1011A-temp-i-subdaily-C/readings.json?latest)) River Ehen footbridge, right and left bank, opened 1 May 2014 | Ennerdale, Cumbria | Outflow river, 40 and 49 m from [Ennerdale Water, GB31229062](https://environment.data.gov.uk/catchment-planning/WaterBody/GB31229062) | 20:04:21, 10.21 °C / **19:08:34**, 10.37 °C; both Unchecked | 7.9 km (Crummock Water) | same |

`ME1011A`'s latest reading was an hour old against a 15-minute step. Its neighbour `ME1011` was current.

**Mill Beck (`E04592A`) measures stream water, not Windermere water.** It is the station nearest any listed spot, 0.8 km from Rayrigg Meadow, but it reads the beck before it enters the lake.

**The in-lake sensor, exactly:**
- Station: [https://environment.data.gov.uk/hydrology/id/stations/E08275A](https://environment.data.gov.uk/hydrology/id/stations/E08275A)
- Measure: [https://environment.data.gov.uk/hydrology/id/measures/E08275A-temp-i-subdaily-C](https://environment.data.gov.uk/hydrology/id/measures/E08275A-temp-i-subdaily-C); latest reading: [readings.json?latest](https://environment.data.gov.uk/hydrology/id/measures/E08275A-temp-i-subdaily-C/readings.json?latest)
- Parameter "Temperature", unit °C, every 900 s.
- Latest reading at the fetch at 20:12 UTC on 27 Oct 2026: `2026-10-27T20:01:03`, **11.4 °C**, quality **Unchecked**.
- Water body: [GB30535977 on the Catchment Data Explorer](https://environment.data.gov.uk/catchment-planning/WaterBody/GB30535977).
- Hoveton Great Broad is not a listed spot. The nearest listed spot is 26.2 km away, and the nearest listed lake spot 137.6 km.

## What can and cannot be said

- **Established:** the Hydrology API carries live, unchecked lake-water temperature at one in-lake site, Hoveton Great Broad, which is not a SwimSignal spot.
- **Historical data checked:** EIDC publishes 2025 OGL surface-temperature datasets for four monitored lakes. Windermere North's CSV has 25 fortnightly readings at the red CEH buoy by Wray Castle. The EA archive has the same named station (`NW-88022315`), so this is not an independent lake/site holdout; 2025 was also part of the earlier lake evaluation. On 1 July the EIDC value is 18.7 °C and the EA value is 19.8 °C, a 1.1 °C cross-source difference that needs source/measurement review before pooling. The dataset is useful for a cross-source consistency check, not a new validation score. It does not reverse or replace #419's fixed 2026 result.
- **Historical buoy sources:** EIDC publishes OGL hourly buoy series for Blelham Tarn, 2016–2018 ([DOI](https://doi.org/10.5285/603629d9-618c-4a26-8a1d-235a4c8f4791)) and 2019 ([DOI](https://doi.org/10.5285/467942bd-2cd5-4038-bc4f-5d77535d99f1)), and Windermere South Basin, 2016–2018 ([DOI](https://doi.org/10.5285/e1b6e387-1bd6-444a-8de9-035df0b8baec)). They contain water temperature at fixed depths (Blelham from 0.5 m; Windermere South from 1 m), plus colocated air temperature, hourly in GMT.
  - **Windermere South's 1 m column is empty** in the published 2016–2018 CSV: no row has a 1 m value. Its shallowest depth with data is **2 m**, so the Windermere South figures below are for 2 m. That is subsurface water, not the surface a swimmer meets.
  - The archive has no Blelham lake samples in 2016–2019; its Blelham lake sample years are 2000, 2010 and 2021.
  - In each check below, every row from the test WFD waterbody was out of fitting: the exact #419 primary outer-fold model whose test fold holds that waterbody was refitted from the committed code and features. Blelham Tarn (GB31229270) is in fold 4. Windermere South Basin (GB31247008) is in fold 0.
  - **Windermere South is a held-out WFD basin, not an independent lake.** Windermere North Basin (GB31247007, fold 3) is connected to it and stays in fold 0's training rows.
  - The buoy series are raw and uncalibrated, though visually screened. These checks are exploratory sensor-level diagnostics on one independent lake and one held-out basin, not spot-level or confirmatory pass/fail tests.
- **Exploratory score runs (27 October; verified by an independent rerun the same evening).**
  - **Method:** the fixed primary outer-fold models from #419, applied to daily buoy means (GMT days) for May–September.
  - **Weather features:** the HadUK 5 km cell of the lake's EA point, picked by #419's rule (nearest valid cell centre).
    - Blelham's published bounding box lies wholly in that cell, 5828.
    - Windermere South's box spans cells 5613, 5684 and 5756. Its centre and the EA "Windermere South Basin" point use 5684, the cell used. The buoy's exact position is not published.
  - **Days kept:** those with at least 18 valid hourly readings.
  - **Reproducible offline** with `scripts/lake_temperature_eval/lt_buoy_check.py`, from the EIDC zips, the private features file and the HadUK series.

  | Held-out WFD water | Depth | Days (2016 / 2017 / 2018 / 2019) | Fit rows / waters | Candidate RMSE (bias, P90) | 7-day air RMSE | 5-day air RMSE | Day-of-year RMSE |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | Blelham Tarn (independent lake) | 0.5 m | 608 (149 / 153 / 153 / 153) | 11,427 / 500 | **1.38 °C** (+0.08, 2.32) | 1.77 °C | 1.80 °C | 2.22 °C |
  | Windermere South Basin (held-out basin) | 2 m, subsurface | 459 (153 / 153 / 153 / —) | 12,017 / 492 | **1.20 °C** (−0.35, 2.03) | 1.48 °C | 1.33 °C | 2.02 °C |

  **Sensitivity, reported separately and not a substitute for the exact fold score:** the same Windermere South check with **both** Windermere basins (GB31247007 and GB31247008) out of training (11,346 rows / 491 waters) gives candidate RMSE **1.51 °C** (bias −1.02, P90 2.59). That is worse than the 5-day line (1.33) and about level with the 7-day line (1.48). So the basin result above depends on the connected North Basin being in training. Blelham is the cleaner independent-lake check.
  Candidate RMSE by year was 1.12, 1.30, 1.58 and 1.46 °C for Blelham (2016–2019), and 0.96, 0.96 and 1.57 °C for Windermere South at 2 m (2016–2018). The 18-hour coverage cutoff was exploratory: including the four Blelham 2016 days below it gives 612 days, candidate RMSE 1.37 °C and P90 2.30 °C, effectively the same.

  **What this is and is not.**
  - It is one independent lake at 0.5 m (Blelham), encouraging for small lakes like it.
  - It is one held-out basin at 2 m whose advantage disappears when its connected basin is removed from training.
  - There are no uncertainty intervals, and daily readings are correlated.
  - It does not change #419's preregistered 2026 failure, does not establish performance across lakes or at the surface, does not show estimates are ready for swimmers, and does not alter the May–September 2027 confirmatory gate.
- **Inferred, not tested:**
  - An outflow (Esthwaite, Ennerdale) carries water from the lake's surface layer, so it may track the lake's surface temperature.
  - An inflow (Mill Beck) carries stream water into the lake, so it says little about the lake at Rayrigg Meadow, 0.8 km away.
  - Neither was compared with a lake reading.
- **Not done:** no sensor here is shown on a spot page. Before any is:
  1. a listed spot must sit on the same water;
  2. the sonde's readings must be compared with samples or a buoy at the spot;
  3. the unchecked status must be stated on the page, as the river sensor tile already does.
- **For the lake spots that matter most (Windermere, Coniston, Ullswater, Derwentwater, Rutland Water)**, the routes are:
  - asking UKCEH about access to, and reuse terms for, its Windermere and Esthwaite buoy data;
  - an operator's own sensor, such as a water company at a reservoir;
  - or the swimmers' own thermometer readings.
  None is an open feed today.
