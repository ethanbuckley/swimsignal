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
| UKCEH lake buoys (Cumbria, Loch Leven, Llyn Conwy) | From Ethan's research, 27 Oct, not re-checked here: real-time viewing, data on request. | Best lead for Windermere and Esthwaite, by agreement. |

## The Hydrology API sondes within 100 m of a lake

Method: the 1,964 Hydrology API stations with a temperature measure, of which 173 are open (no `dateClosed`), tested against the 564 Environment Agency WFD lake outlines the site publishes (`data/anypoint/lakes.json`, simplified to 15 m). Five open stations are inside or within 100 m of an outline. **The five are four places:** the two River Ehen stations are either side of one footbridge.

Each has a water-temperature measure (`-temp-i-subdaily-C`, parameter "Temperature", unit °C, every 900 s). The latest readings were fetched at 20:12 UTC on 27 October 2026; all were flagged **Unchecked**.

| Station | Where it is | Relation to the lake | Latest reading (UTC) | Nearest listed spot | Nearest listed lake spot |
|---|---|---|---|---|---|
| `E08275A` Hoveton Great Broad, opened 16 May 2025, NGR 631734,316282 | Norfolk Broads | **Inside** the lake (WFD Hoveton Great Broad, 0.38 km²) | 20:01:03, 11.4 °C, Unchecked | 26.2 km (River Waveney, Outney Common) | 137.6 km (Rutland Water, Sykes Lane) |
| `E04568A` Cunsey Beck, Esthwaite outfall, opened 24 Mar 2023 | Cumbria | Outflow stream, 54 m from Esthwaite Water | 20:01:12, 10.51 °C, Unchecked | 4.9 km (Windermere, Rayrigg Meadow) | same |
| `E04592A` Mill Beck at the Windermere museum, opened 13 Apr 2023 | Bowness, Cumbria | **Inflow stream: measures stream water, not Windermere water**; 85 m from Windermere's north basin | 20:01:22, 10.377 °C, Unchecked | 0.8 km (Windermere, Rayrigg Meadow) | same |
| `ME1011` / `ME1011A` River Ehen footbridge, right and left bank, opened 1 May 2014 | Ennerdale, Cumbria | Outflow river, 40 and 49 m from Ennerdale Water | 20:04:21, 10.21 °C / **19:08:34**, 10.37 °C; both Unchecked | 7.9 km (Crummock Water) | same |

`ME1011A`'s latest reading was an hour old against a 15-minute step. Its neighbour `ME1011` was current.

**Mill Beck (`E04592A`) measures stream water, not Windermere water.** It is the station nearest any listed spot, 0.8 km from Rayrigg Meadow, but it reads the beck before it enters the lake.

**The in-lake sensor, exactly:**
- Measure: `https://environment.data.gov.uk/hydrology/id/measures/E08275A-temp-i-subdaily-C`
- Parameter "Temperature", unit °C, every 900 s.
- Latest reading at the 20:12 UTC fetch on 27 Oct 2026: `2026-10-27T20:01:03`, **11.4 °C**, quality **Unchecked**.
- Hoveton Great Broad is not a listed spot. The nearest listed spot is 26.2 km away, and the nearest listed lake spot 137.6 km.

## What can and cannot be said

- **Established:** the Hydrology API carries live, unchecked lake-water temperature at one in-lake site, Hoveton Great Broad, which is not a SwimSignal spot.
- **Inferred, not tested:**
  - An outflow (Esthwaite, Ennerdale) carries water from the lake's surface layer, so it may track the lake's surface temperature.
  - An inflow (Mill Beck) carries stream water into the lake, so it says little about the lake at Rayrigg Meadow, 0.8 km away.
  - Neither was compared with a lake reading.
- **Not done:** no sensor here is shown on a spot page. Before any is:
  1. a listed spot must sit on the same water;
  2. the sonde's readings must be compared with samples or a buoy at the spot;
  3. the unchecked status must be stated on the page, as the river sensor tile already does.
- **For the lake spots that matter most (Windermere, Coniston, Ullswater, Derwentwater, Rutland Water)**, the routes are:
  - a UKCEH buoy-data request for Windermere and Esthwaite;
  - an operator's own sensor, such as a water company at a reservoir;
  - or the swimmers' own thermometer readings.
  None is an open feed today.
