# Wales plan, October 2026

Written 4 October 2026, after Ethan decided that SwimSignal should work for people in Wales. It
covers roadmap ranks 12 (Wales) and 18 (Welsh language) in `docs/ROADMAP-2026-10.md`, section 3.2,
and follows the shape of `docs/SCOTLAND-PLAN-2026-10.md`. It is a plan, not code: nothing here
changes the site.

Two marks keep what is known apart from what is not. **Checked** means I read the source or ran
the measurement on 4 October 2026; section 11 gives the URL or command and the time. *Inferred*
means a deduction or estimate that no source or measurement settles; where it matters, the text
says what would settle it.

## 1. Summary

SwimSignal can reach almost everything it needs for Wales today. What it lacks is permission.
Checked: Dŵr Cymru Welsh Water's storm overflow map reads a public data layer, and that layer
answered plain requests on 4 October: 2,362 overflows, 2,222 of them in Wales, each with a status
and its latest discharge. No item in Dŵr Cymru's map service carries a licence. The plan is to ask
first, test the model on Welsh history while waiting, and show nothing Welsh until Dŵr Cymru agrees
and the tests pass.

Five findings change the roadmap's picture of Wales.

1. **The live data is reachable.** The roadmap says Dŵr Cymru's "site refused our requests and no
   API or licence was confirmed". Checked: the website still refuses automated requests (HTTP 403,
   twice). Its map reads a public ArcGIS layer, and the layer answers anonymous requests. Its last
   update was 13:40 UTC, 85 minutes before I read it. The README recorded the layer on 29
   September. What is missing is a licence, not an API.
2. **Almost every Welsh overflow is monitored.** Checked, NRW's 2024 report: Dŵr Cymru had monitors
   on 2,060 of the 2,064 storm overflows in its Welsh return, Hafren Dyfrdwy on all 50. *Inferred:*
   in Wales, a trace that finds no monitored overflow is close to a trace that finds none at all.
   In Scotland about 44% have no live monitor (Scotland plan, section 1).
3. **Welsh spill history is mostly annual.** Checked: Dŵr Cymru publishes each overflow's yearly
   spill count, hours and monitor uptime. Hafren Dyfrdwy publishes its 2025 discharges (start and
   stop) under CC BY 4.0. I found no event history for Dŵr Cymru's overflows in Wales. The
   Environment Agency (EA) lists 2024 and 2025 event files for Dŵr Cymru's overflows in England,
   marked "No Licence Provided".
4. **English spots gain too.** Checked, live build of 4 October: three English spots (the Wye at
   Hereford and at Symonds Yat, the Dee at Chester) have only Dŵr Cymru overflows upstream, and
   none of them has a live status. Checked on the network: the trace from Chester misses 65 Welsh
   overflows within 60 km, because no overflow in Wales is in SwimSignal's overflow table.
5. **Hafren Dyfrdwy is not in Severn Trent's feed.** Checked: every row of Severn Trent's live
   layer says "Severn Trent Water", and none lies in Wales. Hafren Dyfrdwy's own map reads a layer
   that answers "Token Required".

What stays hard (checked, except where marked):

- **No licence.** No Dŵr Cymru map or annual-return item carries licence text. Its datasets on
  Stream, the water industry's open data portal, are CC BY 4.0, but its overflow data is not there.
- **A third of the statuses say "Under Investigation".** 732 of 2,362 rows. Nothing in the layer
  defines it. These rows still record new discharges: 64 had a discharge start on or after 3
  October, and 8 have a discharge with no end while their status does not say "Operating".
- **The pooled model needs an input Wales does not publish.** The model uses each overflow's
  long-term average spill count, spill hours and monitor uptime. Welsh returns give the yearly
  count, hours and uptime. The long-term average is filled for 1 of 2,139 Dŵr Cymru rows in Wales
  (Rivers Trust 2025 compilation).
- **Dŵr Cymru's Welsh overflows spill more than any English company's.** 2025 averages: 44.2
  counted spills per Dŵr Cymru overflow in Wales; 20.5 across England's overflows; 26.8 for
  United Utilities, whose events trained the model. *Inferred:* in Wales the model would work
  beyond its training data. Only a test says how well.
- **Lakes fall back to a rough rule.** None of the 564 lake outlines the site uses is in Wales.
  Llyn Padarn is traced by its centreline with no area term.
- **No E. coli check exists for Wales.** The E. coli model was fitted on English samples.
- **River levels need a key.** NRW's river levels API answered 401, "missing subscription key".
- **Welsh language.** *Inferred:* a private website has no legal duty to publish in Welsh
  (section 2.8). The roadmap pairs Welsh with Wales. How much is Ethan's call.

Recommended order, as PR-sized tasks in section 9:

1. Ask Dŵr Cymru, Hafren Dyfrdwy, NRW and the EA the questions in section 8. Ethan's earlier
   email to Dŵr Cymru shows as sent (handoff, section 4). The repo records no reply.
2. While waiting, load the annual returns and Hafren Dyfrdwy's events, and test the model on them
   (a hindcast: forecasts made after the fact with the rain that fell, scored against what the
   overflows did). This publishes nothing. Stop if it shows no skill.
3. When Dŵr Cymru agrees, read its layer each build. The first thing to show can be the live
   status of its 140 overflows in England, which ends "no live feed" at three English spots.
4. Score Welsh forecasts in shadow (logged and scored, not shown) through at least one wet winter
   month.
5. Add Welsh lake outlines, NRW river levels and an E. coli check on NRW samples.
6. Send the results for outside review. Release Wales only after a positive review.

*Inferred:* about 13 PRs. The date of a Welsh release depends more on Dŵr Cymru's answer than on
the work. A release before the 2027 bathing season needs that answer by about January.

## 2. What the sources publish

### 2.1 Dŵr Cymru's live overflow layer

Checked: plain requests from this Mac between 15:04 and 15:24 UTC on 4 October 2026, with
SwimSignal's User-Agent and no key, to Dŵr Cymru's ArcGIS Online organisation
(`services3.arcgis.com/KLNF7YxtENPLYVey`). The organisation lists 88 public items. Its production
web map, "LiveSpill-Prod", draws the layer `Spill_Prod__view`. The README traced the map on Dŵr
Cymru's page to the same layer on 29 September; the page itself refused me (below).

| Item | What I found |
|---|---|
| Answer | Two pages, since the layer gives at most 2,000 rows a request. HTTP 200, 1,465,924 bytes of JSON in 1.9 s. The layer's last data edit was 13:40:38 UTC |
| Rows | 2,362, with 2,362 distinct `GlobalID`s and 2,357 distinct names. No asset id field |
| Twin layer | `Spill_Prod__External` has the same rows (same `GlobalID`s) and two more fields: `DCWW_ID` (for example "DCWW1001") and `context_of_asset`, the map's "Additional Information". `context_of_asset` was empty in all 2,000 rows I read |
| Where | An outlet position in British National Grid on every row. 2,222 inside the Wales shape, 140 in England |
| Types | 2,057 storm overflows, 305 emergency overflows |
| Status, as text | 1,611 "Overflow Not Operating"; 15 "Overflow Not Operating (Has in the last 24 hours)"; 732 "Under Investigation"; 4 "Overflow Operating" |
| Events | The latest discharge only: start, stop and duration in hours, all as text. 1,868 rows have a latest start in 2026, 194 in 2025 (the earliest on 10 October 2025), 300 none |
| Open discharges | The 4 "Operating" rows have no stop. They had run 12.1, 47.6, 58.8 and 59.8 hours. 8 "Under Investigation" rows also have a start and no stop |
| Time zone | None given. *Inferred:* UK local time. All four open discharges' durations run to 14:35, which is 13:35 UTC, five minutes before the layer's last edit. Read as UTC, they would end after it |
| Row edit time | `EditDate` on every row: 1,421 rows edited on 4 October (998 of them at 13:40 UTC), 659 last edited on 27 September, the oldest 174 hours before. For "Not Operating" rows the median age is 57.9 hours. *Inferred:* it marks a change, not a check, so it cannot show whether a monitor is current |
| 7-day hours | `discharge_duration_last_7_daysH` is filled on 211 rows. The map's pop-up labels it "Duration of Events Over Last 48 hours" |
| Other fields | Receiving water (2,361 rows), linked bathing water (171), an impact class in `WaterQualityURL` (26) |
| Licence | None. All 88 items in the organisation's listing have an empty licence field. The item "Spill_Prod  view" (created 19 January 2024) has empty licence and access fields too. Its description: "Storm Overflow View Feature Layer contains the updated overflow data". The layer has no copyright text |

What Dŵr Cymru said at launch (checked, Water Briefing, 15 May 2024): the beta went live on 1
February 2024. The map shows whether monitors "indicate if they are operating, not operating or if
they have operated recently (in the past 24 hours)". All "2,300" assets were to show by March
2025. And "The data received from the monitors is not always accurate and does not confirm if a
storm overflow is operating, it only provides an indication." The map's own page refused my
request (HTTP 403), so I could not read its words, its update interval or its terms.

"Under Investigation": checked, the map's pop-up turns a status of "Under Maintenance" into "Under
Investigation" (web map expression `expr6`). *Inferred:* the status flags an asset or monitor under
maintenance or investigation. It does not say the outfall is dry. Question 8.1.4 asks.

Dŵr Cymru also publishes a Welsh-language map. Checked: its layer, `Spill_Prod_Welsh`, holds the
same English status strings; the Welsh words live in the map app.

Not checked: whether the layer answers GitHub's runners. *Inferred* likely: Anglian Water's live
layer sits on the same host, `services3.arcgis.com`, and every build reads it. Task W5 tests it
first.

### 2.2 Annual returns (EDM) for Wales

Each company sends NRW a return per overflow by the end of February (checked, NRW's 2024 report).
EDM, event duration monitoring, is the monitor on each overflow. Sources found:

- **Dŵr Cymru's own layers**, in the same ArcGIS organisation. Checked row counts: `EDM2022_view`
  2,337; `EDM_2024_update_view` 2,340; `EDM_2025` 2,352, last edited 29 April 2026.
  `EDM_2023_view` answered "Invalid URL" at layer 0; I did not look further. `EDM_2025` holds the
  permit reference, site name, asset and outlet grid references, receiving water, total spill
  hours, block-counted spills, spills in the bathing season, % complete data, years of EDM
  operation, asset type and `Associated_Asset_ID`. 2,331 rows carry a spill count and a %
  complete. At 1,501 rows the monitor has run 8 to 10 years. No licence on any of them.
- **The Rivers Trust's compilations**, "Event Duration Monitoring - Storm Overflows", for 2019
  (Wales) and 2020 to 2025 (England and Wales). Checked, the item records and the 2025 layer. The
  licence text reads: "Available under the Open Government Licence. Attribution statement: Produced
  by The Rivers Trust. © Environment Agency copyright and/or database right 2025. All rights
  reserved. © Dŵr Cymru/Welsh Water. © Hafren Dyfrydwy." The 2025 layer has 45 fields, including
  `countedSpills` (12/24 hour counting), `totalDurationAllSpillsHrs`, `edmOperationPercent`,
  `longTermAverageSpillCount` and `country`. Rows: Dŵr Cymru 2,139 in Wales, 125 in England and 2
  with no country; Hafren Dyfrdwy 54 in Wales. *Inferred:* the Rivers Trust cannot license Dŵr
  Cymru's data under the Open Government Licence (OGL). Dŵr Cymru should confirm the terms.
- **NRW** publishes summaries, not tables per overflow. Checked, the 2024 spill data report:
  Dŵr Cymru had 2,064 storm overflows in its 2024 return, 2,060 with monitors and 2,051 with spill
  data. They spilled 48.9 times on average, and 86.5% had monitors working at least 90% of the
  time. Hafren Dyfrdwy: 50, 50, 50, 36.2 and 80.0%. The report says Dŵr Cymru's 2024 submission had
  "data validation issues" and was resubmitted. I found no NRW data set with a row per overflow.
- **The EA's event files for Dŵr Cymru's English overflows.** Checked from the catalogue page
  only: the EA dataset "Event Duration Monitoring-Storm Overflow-Start/Stop Detailed Data"
  (created 1 May 2026, updated 24 September 2026) lists "Welsh 2024 Detailed EDM Data.xlsx" and
  "Welsh Water 2025 Detailed EDM Data.xlsx" among the files for the ten companies that operate in
  England. Licence: "No Licence Provided". Its summary says "All rights reserved". I did not open
  the files. *Inferred:* they hold the events of Dŵr Cymru's overflows in England, which the EA
  regulates, not those in Wales.

What the model needs, against what Wales publishes. Checked in `ingest/annual_returns.py` and
`model/features.py`:

| Model input | EA field (England) | Welsh source |
|---|---|---|
| `log_lta_spills` | `longterm_average_spill_count_calculated` | Not published for Wales: 1 of 2,139 Dŵr Cymru rows and 0 of 54 Hafren Dyfrdwy rows. It could be derived from the yearly counts, but I did not find the EA's rule. The mean of the last 2 to 5 years in SwimSignal's table matches the EA's value within 0.5 at no more than 36% of English overflows (checked), so the EA uses earlier years or another rule |
| `log_spill_hours` | `total_spill_duration_hrs_calculated` | Yearly hours, from Dŵr Cymru and the Rivers Trust |
| `edm_pct` | `edm_operation_percent_calculated` | Dŵr Cymru's "% complete data"; the Rivers Trust's `edmOperationPercent` |

Joining the returns to the live rows. Checked: the live layer has no permit or asset id, and
`DCWW_ID` matched no `Associated_Asset_ID` (different formats), so I matched by outlet position.
1,820 of the 2,362 live rows have an `EDM_2025` outlet within 10 m, 2,037 within 50 m, and 2,219
within 200 m. Of the EA's 128 Dŵr Cymru overflows in England, 100 have a live row within 10 m, 111
within 50 m and 122 within 200 m.

### 2.3 Hafren Dyfrdwy

Checked:

- **It is not in Severn Trent's live feed.** All 2,416 rows of Severn Trent's layer have `Company`
  "Severn Trent Water", and the most westerly lies at longitude -3.083. In SwimSignal's 4 October
  build, no Severn Trent overflow lies inside Wales.
- **Its map needs a token.** The map page (hdcymru.co.uk) loads the layer `River_Data_PP_26_05_23`
  from Severn Trent's ArcGIS organisation. An anonymous request answered
  `{"code": 499, "message": "Token Required"}`. I stopped there.
- **Its 2025 discharges are open.** "Hafren Dyfrdwy Event Duration Monitoring 2025" on Stream,
  "Licensed under CC BY 4.0": 3,942 discharges at 43 site ids, 1 January to 23 December 2025. The
  fields are `SiteId`, `SiteName`, outfall latitude and longitude, `EventStart` and `EventEnd` (text
  ending in "Z"). Last modified 31 July 2026.
- **Size.** 54 overflows in the Rivers Trust's 2025 compilation; 50 in NRW's 2024 report.
- **Contact.** Its open data page names no address, only the general contact form.

### 2.4 Stream and the National Storm Overflow Hub

Checked: the Hub's web map is titled "National Storm Overflow Hub for England Web Map". It lists
the nine companies in `config.LIVE_FEEDS`, plus a layer named "ST Connect Storm Overflow Activity".
Dŵr Cymru (`dwrcymru1`) and Hafren Dyfrdwy (`SevernTrent2`) publish other datasets on Stream:
boundaries, reservoir levels, consumption, performance reports and drinking water quality. Every one
that shows a licence says CC BY 4.0. A search of Stream for "Welsh", "Cymru", "Hafren", "Wales" or
"Dyfrdwy" returned 62 items; the only overflow data among them is Hafren Dyfrdwy's 2025
discharges. *Inferred:* the Hub's schema and Stream's CC BY 4.0 are the form to ask Dŵr Cymru
for, since it already uses Stream and that licence for other data.

### 2.5 NRW river levels and flood warnings

Checked:

- The River Levels API, `api.naturalresources.wales/rivers-and-seas/v1/api/StationData`, answered
  HTTP 401 at 15:11 UTC: "Access denied due to missing subscription key."
- The API portal says "Sign up now for an API key", "All the open data products in our API portal
  are free to share and reuse for personal, research or commercial purposes under the Open
  Government License", and that the APIs "should not be relied upon for safety critical
  applications".
- The dataset record: readings usually every 15 minutes; "Data may be re-used under the terms of
  the Open Government Licence"; attribution "Contains Natural Resources Wales information © Natural
  Resources Wales and Database Right". It also warns the data "is retrieved automatically and is
  unvalidated".
- The EA's level stations within 20 km of Hay-on-Wye: 5, all in England. The nearest on the Wye is
  Bredwardine, 12 km downstream.

From a search result only, record not opened: NRW lists a "Live Flood Warnings and Alerts" API,
updated every 15 minutes. Not found: a typical low and high level per station. SwimSignal's level
index (0 at typical low, 1 at typical high) needs one.

### 2.6 NRW bathing waters, samples and forecasts

Checked:

- **The list.** 114 designated waters, which `wales.py` already reads. Inland: Llyn Padarn and
  Llanishen Reservoir (lakes); Llandeilo Swing Bridge on the Tywi and The Warren at Hay-on-Wye
  (rivers). Three more are estuaries: Aberafan, Swansea Bay and Aberdyfi.
- **Forecasts.** NRW's latest pollution-risk forecasts, one request at 15:11 UTC: 16 records. 15
  are dated 30 September 2026, the season's last day, and one 21 May 2021. All 15 current ones are
  at coastal sites or Aberdyfi; none is inland. 10 read "increased", 5 "normal".
- **Samples.** Each water's latest in-season E. coli and enterococci, under the OGL; the coverage
  page already shows them. NRW's Water Quality Archive on DataMapWales holds samples from 2000
  onwards, from rivers, lakes, the coast and sewage discharges. It is updated monthly, under the
  OGL; contact opendata@naturalresourceswales.gov.uk. Its record does not say whether it includes
  E. coli at river sites, and I did not open the download.
- **Access.** NRW's bathing-water API refused GitHub's runners on 3 October (`wales.py`). It
  answers this Mac and sends `access-control-allow-origin: *`.

### 2.7 Rain

As the Scotland plan, section 2.5: the build asks Open-Meteo for its best-match model. Open-Meteo's
Met Office UKV model covers the UK and Ireland. *Inferred:* rain works the same in Wales as in
England. Upland Welsh rain is heavier than most of the training area's, so the hindcast should
report wet days apart.

### 2.8 The Welsh language

- *Inferred*, from search results that summarise the Welsh Language Commissioner's material (I
  could not open the document; its certificate failed): private organisations and charities are
  not required to meet the Welsh Language Standards, though some utilities are. SwimSignal is a
  private, non-commercial site.
- Checked: NRW publishes in Welsh and English, and Dŵr Cymru's map has a Welsh version (2.1).
- Checked: the Welsh Government's Helo Blod service offers "free translations up to 500 words per
  month" and "text checking up to 1,000 words per year". The page does not say whether a site run
  from England qualifies.
- Checked, a count of the site's sources: 15,211 words of visible text in 13 HTML pages, plus
  about 10,000 words in string literals in `site/*.js`. The page script inside `index.html` is
  not counted. *Inferred:* a full Welsh site is over 25,000 words. A spot card's fixed words (the
  level words, "right now", the action lines and the main warnings) are a small part of that.

## 3. What SwimSignal's code does with Wales today

Checked by reading the code at `b5dc9b9`.

| Part | Where | England | Wales today |
|---|---|---|---|
| River network | `network/rivers.py`, OS Open Rivers `oprvrs_gb.gpkg` | Used | Already loaded: 25,807 of the 193,040 links are in Wales (section 4) |
| Live overflow status | `config.LIVE_FEEDS`, `ingest/live.py` | Nine company layers in the National Storm Overflow Hub's schema | None. `config.py` line 46 says Dŵr Cymru "publishes no live feed to ArcGIS", which is out of date (2.1). Its layer has another schema: status as text, one discharge, no id |
| Overflow table | `overflows.build_overflows` | Live rows joined to the EA annual returns, kept inside latitude 49 to 61, longitude -9 to 3 | Only Dŵr Cymru's 128 English overflows, from the EA returns, with status -2 and data state `no_feed`. 2 of the 128 sit just inside the Wales shape. No other overflow in Wales is in the table |
| Pooled spill model | `model/features.py`, `site_static_features` | Rain, season and three covariates from the EA returns | A Welsh overflow would have no covariates. It would get the median of the overflows passed in, then 20 spills, 100 hours and 90%. Dŵr Cymru's Welsh overflows averaged 44.2 spills and 362 hours in 2025, so the defaults would understate them (*inferred*) |
| Calibration layer | `spill_model.fit_site_offsets` | Fitted on United Utilities' discharges | None; an overflow without an offset gets the pooled prediction |
| Lead calibration | `data/processed/lead_calibration.json` | Fitted on United Utilities, 2025 | Would apply unchanged. It is English evidence |
| Live scoring | `forecast_log.verify_live` | Each company's overflows, scored from polled history | Nothing polled |
| State | `site.yml` publishes `live_history.parquet` and other state files to the `state` release | Published there | Any Welsh rows polled would be published there. The repository is public (checked, `gh repo view`) |
| River level | `ingest/flows.py`, `station_pick` | EA flood-monitoring stations within 15 km, by river name | No Welsh stations. Near the border an English station can be picked: for Hay-on-Wye, Bredwardine on the Wye, 12 km away (*inferred* from the code and the station list in 2.5) |
| Flood alerts | `flows.flood_alerts` | EA | None |
| Lakes | `ingest/lakes.py` | 564 EA WFD lake outlines; dilution by lake area | None of the 564 is in Wales (checked). Llyn Padarn is traced by its centreline with no area term |
| E. coli | `model/ecoli.py` | Fitted on EA samples at inland bathing waters | Would run, untested |
| Clicks | `site/anypoint.js` line 288, `data/raw/outside_england.json` | Click anywhere | "SwimSignal has overflow data for England only, so it has no forecast here." The shape holds Wales and Scotland as one geometry |
| Spot requests | `scripts/spot_request.py` | Answered | Answered with the outside-England message |
| Place search | `scripts/make_places.py`, `COUNTRIES = {"England", "Wales"}` | Searched | Welsh places are already searchable: Plan a swim starts from a Welsh town (`index.html` line 2414) |
| River names | `network/names.py`, `WELSH` | Welsh names read as English for matching | Already covers 21 Welsh river words (Gwy, Hafren, Tywi, Wysg, Dyfrdwy, Dyfi and others) |
| Coverage page | `wales.py` | n/a | NRW's 114 waters, ratings and latest samples; the reader's browser asks NRW for current forecasts |
| Pollution reports | `site/visits.js` line 278, `reviews.py` line 367 | The EA's number | Already gives NRW's number for Wales, 0300 065 3000 |
| Words | `index.html` lines 12, 16, 1942, 2015; `about.html` lines 3, 15; `coverage.html` line 13; `terms.html` line 21; `api/app.py` line 57; `manifest.webmanifest` line 4 | "in England" | Would change at release |

## 4. Measured: Wales on SwimSignal's network

Checked. A read-only script in my scratch space, run on this Mac with no network calls. It used the
`data-v1` river network, the WFD lakes, the EA annual returns of 11 September and the overflow
table of 12 September from the main checkout; the live layer as read at 15:05 UTC; and Hafren
Dyfrdwy's 43 discharge sites from its 2025 file. It snapped the outlets with `snap_many` (750 m)
and `overflows._second_pass` (1,500 m), as `build_overflows` does, and traced with
`transport.locate_pin` and `transport.upstream_overflows` at the default 0.5 m/s. "Wales" is the
outside-England shape south of 54° N. Random seed 0.

| Measure | Wales | England or GB, for comparison |
|---|---|---|
| Network links | 25,807: 21,646 inland river, 2,445 lake, 1,620 tidal river, 96 canal | 193,040 in all of GB |
| River length, inland and tidal | 17,427 km | not measured |
| Dŵr Cymru rows snapped within 750 m | 2,189 of 2,362 | |
| Of those, receiving water has a word from `overflows.MARINE` | 165 (the first pass does not check names, as in England). "Menai Strait" names 32 snapped rows, and `overflows.MARINE` has no "strait" | |
| Second pass (1,500 m) | 30 by a matching river name, 51 by distance alone, 84 left out as marine, 8 not snapped | |
| Snapped, by form | 1,942 inland river, 281 tidal river, 28 canal, 19 lake. 2,133 of the snapped rows are in Wales | |
| Hafren Dyfrdwy's 43 sites | All 43 snapped to inland river | |
| Rain cells (0.1°) | 276 for the snapped Dŵr Cymru and Hafren Dyfrdwy outlets (6 requests of 50); 254 of them in Wales | 1,589 for 13,821 overflows in the live click-anywhere build (Scotland plan) |
| Links within 60 km downstream of a snapped Welsh outlet | 4,449, of which 151 in England | 23,043 traced links (Scotland plan) |
| 0.25° squares with data | about 73 | 334 (Scotland plan) |
| 300 random Welsh inland river links: monitored overflows within 60 km upstream | mean 3.52, median 0, 90th percentile 9, max 208; none at 70% | mean 2.5, none at 82% (roadmap, 3 October: links from all of GB, English overflows only); Scotland none at 93% |
| 300 random links of the 4,449 in Wales | mean 9.56, median 3, 90th percentile 27 | |
| Rows in a click-anywhere table | about 42,500 (9.56 × 4,449) | 414,091 (Scotland plan) |
| WFD lake outlines in Wales | 0 of 564 | |

At named places. "Today" is the overflow table the build uses now. "Added" is the Dŵr Cymru live
rows plus Hafren Dyfrdwy's sites. Weight is the sum of the transport weights (die-off times
dilution), a rough guide to how much each set counts.

| Place | Today: overflows, weight | Added: overflows (in Wales), weight of those in Wales | Of the added: emergency, "Under Investigation", Hafren Dyfrdwy |
|---|---|---|---|
| Llyn Padarn (lake, bathing water) | 0, 0 | 4 (4), 0.820 with no area term | 0, 2, 0 |
| Llanishen Reservoir (lake, bathing water) | 0, 0 | 0 | |
| Tywi at Llandeilo Swing Bridge (bathing water) | 0, 0 | 16 (16), 1.582 | 3, 11, 0 |
| Wye at The Warren, Hay-on-Wye (bathing water) | 0, 0 | 41 (41), 3.183 | 8, 19, 0 |
| Wye at Hereford (spot) | 14, 6.663 | 20 (6), 0.055 | 3, 11, 0 |
| Wye at Symonds Yat (spot) | 14, 2.317 | 15 (0), 0 | 2, 9, 0 |
| Dee at Sandy Lane, Chester (bathing water) | 10, 2.822 | 79 (65), 1.321 | 9, 17, 0 |
| Severn in Shrewsbury (bathing water) | 15, 7.101 | 7 (7), 0.022 | 0, 0, 7 |
| Severn at Ironbridge (bathing water) | 87, 1.995 | 0 | |
| Teme in Ludlow (bathing water) | 11, 0.881 | 4 (4), 0.079 | 0, 0, 4 |

*Inferred* from these:

- A Welsh launch covers the rivers below towns. 70% of Welsh river links have no monitored
  overflow within 60 km upstream. The roadmap's 82% is not a like-for-like England figure, since
  its sample included Welsh and Scottish links with no overflows in the table.
- At Hereford and Symonds Yat the added rows are mostly the same English overflows the table
  already holds, now with a live status. The Welsh ones there are far upstream and weigh little.
- At Chester the Welsh overflows add about half again to the weight. Chester's forecast today
  leaves out the whole Welsh Dee within 60 km.
- "Under Investigation" covers a large share of what lies upstream of the Welsh bathing waters
  (11 of 16 at Llandeilo, 19 of 41 at Hay). How SwimSignal reads that status decides what those
  pages say.

## 5. What could be forecast, and what must abstain

### 5.1 With the pooled model only

*Inferred*, from the code (section 3) and the data (sections 2 and 4):

1. **"Right now" at a river point**, from Dŵr Cymru's live status through the same transport. This
   needs no spill model. Proposed mapping: "Overflow Operating" to discharging; "Not Operating (Has
   in the last 24 hours)" and "Not Operating" to not discharging, with the last stop time, which
   the existing 48-hour rule uses; "Under Investigation" to an unknown status, as `stale` is in
   England, showing the last discharge and its time, never "not discharging". Times converted from
   UK local time to UTC. The feed's time is the layer's last data edit, as `fetch_live` already
   reads for companies whose rows carry no time.
2. **Each overflow's daily spill chance**, today and four days ahead, for the 2,270 snapped Dŵr
   Cymru outlets (emergency overflows aside, see 5.2) and Hafren Dyfrdwy's 43 sites. Rain inputs
   as in England. Covariates from the Welsh returns, joined by position (task W2), or else the
   fixed defaults.
3. **The pollution risk at a river point** within 60 km below monitored overflows: the same
   transport (0.5 m/s, 30-hour die-off, dilution by upstream network length) and the same bands.
4. **Rain in the last 48 hours** at the spot, as in England.
5. **For England**: a live status for Dŵr Cymru's 140 English overflows. Their forecasts already
   run, with EA covariates.

### 5.2 What it must abstain from

Each item says why. "Checked" items rest on sections 2 to 4; the rest are *inferred*.

| Abstain from | Why |
|---|---|
| Any Welsh page or click before Dŵr Cymru gives reuse terms | No licence on its data (checked). The state release is public, so even shadow polling publishes the rows (checked, section 3) |
| The E. coli figure, everywhere in Wales | Fitted on English samples only (checked, `data/processed/ecoli_model.json`). No Welsh sample has been matched to it. Until task W10 |
| A level on lakes | No Welsh lake outline, so no area dilution (checked at Llyn Padarn). Show the upstream overflows' status instead, until task W8 |
| Tidal rivers, estuaries and the coast | No tide in the model, as in England. 281 Welsh outlets snapped to tidal river links (checked). Add "strait" to `MARINE`, or better, use OS form |
| A spill forecast for emergency overflows | 305 in the layer (checked). *Inferred:* they operate when something fails, not because of rain; Scottish Water says so of its own (Scotland plan, 5.2). Show their live status only |
| A "not discharging" reading for "Under Investigation" rows | 732 rows, meaning not published, new discharges still recorded on some, 8 open (checked). Until Dŵr Cymru explains (question 8.1.4) |
| "Right now" for Hafren Dyfrdwy's overflows | No public live feed (checked: its layer needs a token). Show its overflows as "no live feed", as Dŵr Cymru's English ones are today |
| Discharges between polls | The layer keeps one discharge per overflow (checked). Builds run a median 2.9 hours apart, at most 8.1 (`site.yml` comment). A second discharge inside one gap is lost to the live history. The 7-day hours field (211 rows) may show such losses |
| Monitors stuck on | Two open discharges had run 58.8 and 59.8 hours (checked); whether they are real is not known. England has the same risk; any rule should cover both |
| River level, "too high to swim", flood alerts | EA-only in the code (checked); NRW's API needs a key. Until task W9 |
| Water temperature | No source found |
| Algae | As in England, waiting on UKCEH's licence |

Unlike Scotland, Wales can keep England's plain level where a trace finds nothing: "No sewage risk
from monitored overflows". Checked: NRW counts monitors on 99.8% of Dŵr Cymru's storm overflows.
*Inferred:* the sentence is as true in Wales as in England. The exception is Hafren Dyfrdwy's area,
where overflows are monitored but have no live status.

## 6. How it would be validated before release

`docs/EXPANSION-2026-10.md` sets the bar for any region: "positive held-out skill with uncertainty
and external review". The stages below meet it. Each stage writes its gate into the script before
it runs, so the gate cannot move after the results are seen.

**Stage A: hindcast (tasks W2 to W4).** Apply the model as it stands, trained on United Utilities
and not refitted, with ERA5-Land rain, as `scripts/train.py` does for 2025. Three test sets:

- **A1, Hafren Dyfrdwy 2025.** 43 sites, 3,942 discharges, CC BY 4.0. Covariates from its 2024
  return (the Rivers Trust's 2024 compilation; whether it holds Hafren Dyfrdwy's rows is not
  checked).
- **A2, Dŵr Cymru's English overflows, 2024 and 2025**, from the EA's event files, with EA
  covariates. Only if Ethan accepts the licence position (section 10) or the EA confirms the OGL.
- **A3, Dŵr Cymru's Welsh overflows, 2025, as yearly totals.** Each overflow's expected spill-days
  in 2025 (the sum of its daily chances) against its counted spills. United Utilities' history
  gives 1.004 spill-days per counted spill (checked, `data/processed/spill_day_ratio.json`). This
  tests the model's level per overflow, not its day-to-day skill.

Arms: the pooled model with the default covariates (what Wales gets with no new code), and with
Welsh covariates from the year before. Baselines: each overflow's spill-day rate from the year
before; the flat rate of the test period, as the accuracy page shows it. Labels: a spill-day is a
day with any discharge, as `features.spill_days` counts it. Whether Hafren Dyfrdwy's file keeps
short discharges that United Utilities' did not is not checked; W3 must find out, and the Scotland
plan's S3 asks the same. Scores: Brier score, skill against each baseline, log loss, AUC,
reliability by band, wet and dry days apart, leads 0 to 3 from archived forecasts as
`scripts/verify_leads.py` does. Uncertainty: resample overflows and weeks together (a cluster
bootstrap, 2,000 draws), chosen before the run.

- Gate A (proposed): in A1, and in A2 if it is used, the lower end of the 95% interval of skill
  against the year-before baseline is above zero, at lead 0 and at leads 1 to 3, for the arm named
  before the run (proposed: Welsh covariates). A3 is reported. If its total expected spill-days are
  off by more than a factor of 1.5 (proposed), the model's level is wrong for Dŵr Cymru, and Stage
  B must show otherwise before release. If Gate A fails, write it up in the accuracy page's terms
  and stop.

*Inferred:* A1 is 43 overflows in one part of mid-Wales over one year. It cannot stand for 2,200
Dŵr Cymru overflows. Stage B therefore matters more in Wales than in Scotland, where years of
discharge records exist.

**Stage B: shadow live scoring (tasks W5, W7), after Dŵr Cymru agrees.** Poll the layer each build,
log forecasts for the Welsh overflows, score them with `verify_live` as a "Dŵr Cymru Welsh Water"
row, and show nothing. Score "Under Investigation" rows apart. Run for at least three months from
Dŵr Cymru's answer, including at least one wet winter month.

- Gate B (proposed): skill above zero, with its interval clear of zero, over at least 200 scored
  spill-days at leads 1 to 3. The same coverage rules as England's live scores.

**Stage C: outside review (task W12).** Send the reviewer the EXPANSION package plus the Stage A and
B results, the abstentions in 5.2 and the proposed page words. One review can cover Wales and
Scotland together.

**Stage D: the 2027 season (task W13).** `docs/PREREGISTRATION-2027.md` excludes Welsh waters
(section 1). If Wales is released, add it as a separately labelled region by a dated amendment in
section 17, before 1 May 2027.

**E. coli (task W10).** *Inferred:* Wales can test the E. coli model where Scotland cannot. NRW
samples two inland river bathing waters with monitored overflows upstream (41 within 60 km at
Hay-on-Wye, 16 at Llandeilo; section 4) under the OGL, and its archive may hold more river
samples. The figure stays hidden unless the test
shows skill.

## 7. Costs and limits

Checked figures first, then *inferred* ones.

| Item | Size or count | Basis |
|---|---|---|
| Dŵr Cymru live poll | 2 requests a build, 1.47 MB, about 2 s | Checked |
| Builds | median 2.9 h apart, at most 8.1 h (13 to 28 Sep) | Checked, `site.yml` comment |
| Dŵr Cymru annual returns | `EDM_2025`: 2 requests, 1.89 MB; once a year, off CI | Checked |
| Hafren Dyfrdwy discharges | 3,942 rows, once a year, off CI | Checked count |
| Open-Meteo, spots | Only the cells of a Welsh spot's upstream overflows; at most 276 cells, 6 requests of 50 | Checked count |
| Open-Meteo, click anywhere | 300 cells a build today, oldest first. Adding 254 cells takes the full cycle from about 5.3 to 6.1 builds, about 18 hours at the median gap, inside the 24-hour limit | *Inferred* |
| Open-Meteo, hindcast archive | 276 cells for 2024 and 2025. By the Scotland plan's estimate (415 cells, 5 years, about 50,000 calls), about 13,000 calls. Run over two or more days, off CI, never beside a build | *Inferred* |
| `overflows.geojson` | 6.34 MB for 14,631 overflows today, about 433 bytes each. About 2,300 new rows, so about 1.0 MB more | *Inferred* from a checked size |
| Click-anywhere files | About 35 KB a square today (Scotland plan); about 73 squares, some already present near the border, so at most about 2.6 MB more | *Inferred* |
| NRW river levels | Unknown until a key is issued and the rate limit is known | Checked: key required |
| Welsh translation | Over 25,000 words for a full site; Helo Blod's free service is 500 words a month | *Inferred* from a checked word count and a checked offer |
| GitHub Pages | 1 GB site, 100 GB a month | Roadmap, checked 3 Oct |

Limits that matter more than size:

- Dŵr Cymru's layer has not been tried from a runner (2.1).
- NRW's bathing-water API refuses runners (checked 3 October, `wales.py`). Its river levels API
  is on another host, `api.naturalresources.wales`; not tried from a runner.
- The `state` release is public, so polling Welsh rows publishes them. No polling before Dŵr
  Cymru's answer.
- Never run the hindcast's rain download beside a build or another local build: one IP got
  Open-Meteo 429s and EA 403s before (handoff, section 5).

## 8. Questions to ask, with draft emails

None of the four emails has been sent. Each source of an address is given.

### 8.1 Dŵr Cymru Welsh Water (not sent)

Ethan's earlier email to Dŵr Cymru shows as sent in the launch-kit tracker (handoff, section 4).
If it has been answered, send only the questions the answer leaves open. The address comes from
SwimSignal's notes of 29 September 2026. I could not check it again, because the company's site
refuses automated requests.

To: EnvironmentalInformationRequests@dwrcymru.com
Subject: Reusing your storm overflow map data on a free swimming site

> Hello,
>
> I run SwimSignal (swimsignal.co.uk), a free, non-commercial website that forecasts sewage
> pollution risk for river and lake swimmers from water companies' storm overflow data. We would
> like to cover Wales. We would also like to show your overflows' status at the English swim spots
> on the Wye and the Dee below them. Your storm overflow map reads the public layer
> Spill_Prod__view on ArcGIS Online. Before we use it, could you help with these questions?
>
> 1. Licence. The layer and its item show no licence. May we reuse the data, and under which
>    licence? Your datasets on Stream use CC BY 4.0. What attribution would you like?
> 2. Which layer. Should a third party read Spill_Prod__view, Spill_Prod__External or another
>    service? Is DCWW_ID stable over time?
> 3. Rate and hosts. We would make two requests (about 1.5 MB) every one to three hours, from
>    GitHub Actions, which uses shared cloud addresses. Is that acceptable?
> 4. Status meanings. What does "Under Investigation" mean? Some of those overflows still show new
>    discharges. Does "Overflow Not Operating (Has in the last 24 hours)" count from the start or
>    the end of the last discharge?
> 5. Times. Are the start and stop times in UK local time? How often is the layer updated?
> 6. History. Could you share the start and stop times of discharges at your Welsh overflows for
>    2021 to 2025? We would use them to test our forecasts before showing any in Wales. If it
>    helps, please treat this question as a request under the Environmental Information
>    Regulations 2004.
> 7. Annual returns. May we reuse your EDM layers (EDM_2025 and earlier) on the same terms? Does
>    Associated_Asset_ID or the permit reference link them to the map's overflows? Do you publish a
>    long-term average spill count per overflow?
> 8. Stream. Do you plan to publish the live data on Stream, in the National Storm Overflow Hub's
>    format?
>
> We would credit Dŵr Cymru Welsh Water and link to your map. We would mark overflows without
> current data as such, and never present a quiet monitor as clean water. I am happy to share a
> preview before anything goes live.
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 8.2 Hafren Dyfrdwy (not sent)

No data address was found (2.3). Send through the contact form at
https://www.hdcymru.co.uk/help-and-contact/contact-us/. A form is Ethan's to submit.

Subject: Reusing your storm overflow data on a free swimming site

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free, non-commercial website that forecasts sewage pollution
> risk for river swimmers from water companies' storm overflow data. It already uses Severn Trent's
> live layer for England, and we would like to cover your area too. Your 2025 EDM data on Stream,
> under CC BY 4.0, lets us test our method in your area.
>
> 1. Live status. Your storm overflow map reads a layer that needs a sign-in token. Could your
>    overflows' live status be published openly, for example on Stream as Severn Trent's is, under
>    CC BY 4.0?
> 2. History. Are discharges for 2021 to 2024 available in the same form as the 2025 file?
> 3. Ids. Does SiteId match the identifiers in your annual return to Natural Resources Wales?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 8.3 Natural Resources Wales (not sent)

The address is the contact on NRW's Water Quality Archive record (checked).

To: opendata@naturalresourceswales.gov.uk
Subject: River levels, bathing-water data and storm overflow returns for a free swimming site

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free, non-commercial website about sewage pollution risk for
> river and lake swimmers. It lists Wales's 114 bathing waters from your API, with NRW's credit. We
> are planning a careful extension to Welsh rivers and want to stay within your terms.
>
> 1. River levels. We will register on the API portal for a key. We expect to ask for the latest
>    level of every station every one to three hours. Is there a rate limit? Does NRW publish a
>    typical low and high level per station, like the Environment Agency's typical range?
> 2. Flood warnings. May a free website show the live flood warnings and alerts near a swim spot,
>    with NRW's credit?
> 3. Bathing-water API. On 3 October your service at environment.data.gov.uk/wales/bathing-waters
>    refused requests from GitHub's servers (HTTP 403), though it answers home connections. Is
>    there an accepted route for a scheduled build, and a rate you would like us to keep to?
> 4. Water Quality Archive. Does the open archive include E. coli or other faecal indicator
>    results at river and lake sites? We would use them to test our method, and show only summaries
>    with your credit.
> 5. Storm overflow returns. Does NRW publish the per-overflow EDM returns from Dŵr Cymru and
>    Hafren Dyfrdwy as open data? We would rather use the regulator's copy than a third party's.
> 6. Lakes. Is there an open layer of Welsh lake water body outlines we may reuse?
> 7. Welsh wording. If we publish in Welsh, which Welsh terms does NRW use for "increased risk"
>    and "no increased risk" in its bathing-water forecasts?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 8.4 Environment Agency, the event files (not sent)

The route is the Data Services Platform's support form, environment.data.gov.uk/support, from
SwimSignal's notes of 29 September 2026. This question matters for England as well: the files
cover all ten companies that operate there.

Subject: Licence of the storm overflow start/stop detailed data

> Hello,
>
> The dataset "Event Duration Monitoring-Storm Overflow-Start/Stop Detailed Data" on data.gov.uk
> shows "No Licence Provided", and its summary says "All rights reserved". Its parent dataset, the
> storm overflow annual returns, is under the Open Government Licence. May SwimSignal, a free,
> non-commercial website, use the start/stop files to test its spill forecasts and publish the
> resulting scores, with your credit? Is the Open Government Licence intended?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

## 9. PR-sized tasks, in order

Each is one PR against main. W2 to W4 publish nothing and can start now. W5 onwards waits for Dŵr
Cymru's answer to question 8.1.1.

**W1. Correct the docs that say Dŵr Cymru has no feed.** Roadmap rank 12 and open question 3,
the EXPANSION Wales row, README line 75 and the comment at `config.py` line 46. They should say:
a public layer exists, it has no licence, and SwimSignal waits for Dŵr Cymru's terms. Docs and a
comment only.

**W2. Welsh annual returns and positions (off CI).** A script that reads Dŵr Cymru's `EDM_2022`
to `EDM_2025` layers and the Rivers Trust's Hafren Dyfrdwy rows. It keeps, per overflow and year,
the counted spills, hours, uptime and outlet position, and matches them to the live rows by outlet
within 50 m. It derives a long-term average by a rule written in the docstring before the first
run (proposed: the mean count over the years with uptime of at least 90%), and compares that rule
with the EA's values on English overflows. It writes `data/processed/wales_annual.parquet`, which
stays out of git until Dŵr Cymru answers question 8.1.7 (`data/processed/*` is ignored by
default). Report in the PR: rows by year, match rates, and the rule's error against the EA's
values. Tests on a small fixture.

**W3. Discharge history and rain archive (off CI).** Import Hafren Dyfrdwy's 2025 discharges into
the `edm_events` schema (`site_id`, start and end in UTC, source), with its CC BY 4.0 credit.
Import the EA's 2024 and 2025 files for Dŵr Cymru's English overflows only if Ethan says yes
(section 10). Fetch ERA5-Land rain for the 276 cells, 2024 and 2025, spread over several days.
Report the cells and calls used.

**W4. Hindcast (Stage A).** `scripts/hindcast_wales.py`, with Gate A written in its docstring
before the first run. Writes `data/processed/wales_hindcast.json`. The PR shows the tables of
section 6 and says pass or fail. If it fails, the next PR is a short write-up, and the Welsh
forecast stops. The live status (W5, W6) can still go ahead, since it needs no spill model.

**W5. Runner test and live adapter, off by default.** First test the layer from a runner, on a
throwaway branch with a throwaway workflow, deleted after (needs Ethan's yes). Then
`src/dipcast/ingest/dwr_cymru.py`: the status mapping of 5.1, times from UK local to UTC, the
layer's last data edit as the feed time, emergency overflows marked, and "Under Investigation" as
Dŵr Cymru defines it. Behind a setting that is off by default. Tests from a trimmed copy of the 4
October answer.

**W6. Live status for Dŵr Cymru's English overflows.** Turn the adapter on for the 140 English
rows only, matched to the EA's 128 by position. This replaces "no live feed" at Hereford, Symonds
Yat and Chester. Credit on the terms page and in the data files, as Dŵr Cymru asks. Screenshots of
the three spots at 320, 375 and 1440 px.

**W7. Shadow scores for Wales (Stage B).** Poll the Welsh rows, forecast every snapped Welsh
overflow each build, and score them with `verify_live` as their own company. Keep the scores in a
block of `verification.json` that the page does not show. Add "strait" to `overflows.MARINE`, or
better, use OS form, so the Menai Strait outlets are not inland.

**W8. Welsh lake outlines.** Add Welsh lake water bodies beside the EA's WFD lakes, so a Welsh lake
gets the area term. Check the source and licence first (question 8.3.6). Tests at Llyn Padarn,
Llanishen Reservoir and Llyn Tegid.

**W9. NRW river levels and flood warnings.** After Ethan registers for a key (section 10): the
latest level per station, the pick by river name as in `flows.station_pick`, a usual range from
each station's history (method in the docstring), and the same stale rule. Then "too high to swim"
and NRW's flood warnings. The key is read from a secret, never logged.

**W10. E. coli check in Wales.** Match NRW's samples at Hay-on-Wye and Llandeilo, and any river
E. coli in the Water Quality Archive, to the model's same-day estimate. Report skill with
intervals. Keep the figure hidden unless it shows skill.

**W11. Welsh words.** Only if Ethan chooses it (section 10, item 7): the spot card's fixed words,
the level words and the main warnings in Welsh, behind a language switch, translated by a person
and checked. Level words keep their noun, as DESIGN.md requires in English.

**W12. Outside review (Stage C).** A document PR with the review package and the reviewer's dated
assessment, published with their consent.

**W13. Release and pre-registration.** Split `outside_england.json` so that Wales opens and
Scotland stays blocked. The Scotland plan's S10 splits the same file the other way; whichever
lands second builds on the first. Add Welsh overflows to the click-anywhere data, credits for Dŵr
Cymru, Hafren Dyfrdwy and NRW, the abstentions of 5.2 in the page words, and a first set of hand-checked Welsh spots in
`spots.csv`, starting with the four inland bathing waters. Change "England" only where it stops
being true. Screenshots at 320, 375 and 1440 px. Then a dated amendment to
`docs/PREREGISTRATION-2027.md`, section 17, before 1 May 2027.

## 10. For Ethan

1. **Send the four emails** in section 8, or say who should. For Dŵr Cymru, check first whether
   your earlier email has a reply.
2. **Register for an NRW API key** when you want task W9. Steps:
   1. Open https://api-portal.naturalresources.wales/ and sign up with hello@swimsignal.co.uk.
   2. Subscribe to the river levels product and copy its primary key. (*Inferred:* I could not
      see the portal's product list, which needs JavaScript. On portals of this kind a key belongs
      to one product, so a flood-warnings key may not open river levels.)
   3. Run `gh secret set NRW_API_KEY --repo ethanbuckley/swimsignal` and paste the key when asked.
   4. You will know it worked when `gh secret list --repo ethanbuckley/swimsignal` shows
      `NRW_API_KEY`.
   The likely mistake is pasting the key into a chat, an issue or a PR. It then counts as public,
   because the repository and its discussions are public. Regenerate it on the portal if that
   happens.
3. **Approve the runner test** in W5 (a throwaway workflow, as before).
4. **The EA's event files.** They say "No Licence Provided". The plainest choice is to wait for
   the EA's answer (8.4) and test on Hafren Dyfrdwy alone. The alternative is to use them for
   testing now and publish only scores. They also cover every English company for 2024 and 2025,
   while SwimSignal trains on United Utilities only. That is worth its own task, outside this plan.
5. **"Under Investigation", if Dŵr Cymru does not explain it.** The plainest choice is to treat it
   as status unknown: show the last discharge with its time, never "not discharging". The
   alternative is to read the row's discharge times as if the status were normal.
6. **Release Dŵr Cymru's live status in England first?** W6 needs only Dŵr Cymru's yes and the
   runner test, not the Welsh tests. The plan's choice is yes.
7. **How much Welsh.** (a) English only, with Welsh place and river names as published; (b) the
   spot card's fixed words and the level words in Welsh (*inferred:* a few hundred to about 2,000
   words), translated by a person and checked (W11); (c) the whole site, over 25,000 words. The plan's choice is (b) at the
   Welsh release, since the roadmap pairs Welsh with Wales. A paid translator is a cost; Helo Blod
   is free for 500 words a month if SwimSignal qualifies.
8. **Reviewer.** The invitation in EXPANSION is still waiting on you. One reviewer could take
   Wales and Scotland together.

## 11. Sources and how each number was obtained

All read or run on 4 October 2026. Times are UTC. "Item" requests are
`https://www.arcgis.com/sharing/rest/content/items/<id>?f=json`; "layer" requests are
`<service>/FeatureServer/0?f=json`; "query" requests are `<service>/FeatureServer/0/query`.

Dŵr Cymru Welsh Water:
- Storm overflow map and EDM pages, HTTP 403 to WebFetch at about 15:03 and 15:20:
  https://corporate.dwrcymru.com/en/community/environment/storm-overflow-map and
  https://corporate.dwrcymru.com/en/community/environment/event-duration-monitoring
- The organisation's public items, 15:04:58:
  https://www.arcgis.com/sharing/rest/search?q=orgid:KLNF7YxtENPLYVey&num=100&f=json
- Items `11a7cda2ddfb44e0a76c1e1178359548` (Spill_Prod view) and `b6c91246de4c42a09877c569ef4f387c`
  (EDM Data 2025), 15:05:16
- Layers, 15:05:26:
  https://services3.arcgis.com/KLNF7YxtENPLYVey/arcgis/rest/services/Spill_Prod__view/FeatureServer/0?f=json
  and https://services3.arcgis.com/KLNF7YxtENPLYVey/arcgis/rest/services/EDM_2025/FeatureServer/0?f=json
- `Spill_Prod__view` query: status counts grouped by `status` at 15:05:41; all rows in two pages
  (`outFields=*`, `outSR=4326`, offsets 0 and 2000) at 15:05:52
- Map app `217cf21cd3d34e3c9ea384c32b7c4641` and web map `95c6992ee2a947089f7b09a3aaef4eb6`
  (`/data?f=json`), 15:06:38 and 15:06:57
- `EDM_2025` query, all rows in two pages, 15:09:02 and 15:13:46; row counts of `EDM2022_view`,
  `EDM_2023_view` and `EDM_2024_update_view`, 15:18:46
- `Spill_Prod_Welsh` status counts, 15:16:25; `Spill_Prod__External` layer and 2,000 rows (ids and
  notes, no geometry), 15:21:55 and 15:22:10
- Water Briefing, 15 May 2024:
  https://www.waterbriefing.org/home/company-news/item/22101-d%C5%B5r-cymru-welsh-water-launches-storm-overflow-map

Hafren Dyfrdwy and Severn Trent:
- Stream's Welsh items, 15:07:54: https://www.arcgis.com/sharing/rest/search with
  `q=orgid:XxS6FebPX29TRGDJ AND (Welsh OR Cymru OR Hafren OR Wales OR Dyfrdwy)`
- 2025 discharges, layer at 15:09:02, counts and sites at 15:09:19:
  https://services-eu1.arcgis.com/XxS6FebPX29TRGDJ/arcgis/rest/services/HD_EDM_2025_Final_File/FeatureServer/0
- Map page, 15:09:57: https://www.hdcymru.co.uk/in-my-area/storm-overflow-map/ ; its layer, 15:10:22:
  https://services1.arcgis.com/NO7lTIlnxRMMG9Gw/arcgis/rest/services/River_Data_PP_26_05_23/FeatureServer/0?f=json
- Open data page: https://www.hdcymru.co.uk/about-us/open-data-strategy
- Severn Trent's live layer, counts grouped by `Company` with the minimum longitude, 15:09:30: the
  `config.LIVE_FEEDS` URL

Stream and the Hub:
- ArcGIS search for overflow and EDM items naming Wales, 15:08:09
- Hub web map item and data, 15:23:55: item `d0d61f9f88a34ef5adb83dbff938c537`

The Rivers Trust:
- 2025 compilation, layer at 15:08:28 and counts grouped by company and country at 15:08:39:
  https://services3.arcgis.com/Bb8lfThdhugyc4G3/arcgis/rest/services/Event_Duration_Monitoring_Storm_Overflows_2025/FeatureServer/0
- Licence text from the item records in the 15:08:09 search (2025: `c0a57d7a953f48c681f8868ace281bbd`)

Environment Agency:
- Start/stop detailed data:
  https://ckan.publishing.service.gov.uk/dataset/event-duration-monitoring-storm-overflow-start-stop-detailed-data
- Annual returns dataset:
  https://www.data.gov.uk/dataset/19f6064d-7356-466f-844e-d20ea10ae9fd/event-duration-monitoring-storm-overflows-annual-returns
- Level stations near Hay-on-Wye, 15:18:05:
  https://environment.data.gov.uk/flood-monitoring/id/stations?parameter=level&lat=52.0765&long=-3.137&dist=20

Natural Resources Wales:
- Storm overflow spill data report 2024, read in full:
  https://cdn.cyfoethnaturiol.cymru/pv2krr3s/storm-overflow-spill-data-report-2024.pdf
- Storm overflows page:
  https://naturalresources.wales/about-us/what-we-do/our-roles-and-responsibilities/water/storm-overflows/?lang=en
- River Levels API, one request without a key at 15:11:02:
  https://api.naturalresources.wales/rivers-and-seas/v1/api/StationData
- API portal: https://api-portal.naturalresources.wales/
- River levels record: https://metadata.naturalresources.wales/geonetwork/srv/api/records/NRW_DS116446?language=eng
- Flood warnings record, from a search result only:
  https://metadata.naturalresources.wales/geonetwork/srv/api/records/NRW_DS116251?language=eng
- Bathing-water forecasts, 15:11:18:
  https://environment.data.gov.uk/wales/bathing-waters/doc/bathing-water-quality/stp-risk-prediction/latest.json?_pageSize=200
- Bathing-water list with sampling points, 15:13:26:
  https://environment.data.gov.uk/wales/bathing-waters/doc/bathing-water.json?_pageSize=200
- Water Quality Archive: https://metadata.naturalresources.wales/geonetwork/srv/api/records/NRW_DS124903?language=all
  and https://datamap.gov.wales/layers/geonode:nrw_water_quality_archive_stations/metadata_detail

Welsh language:
- Helo Blod: https://www.gov.wales/free-welsh-language-services-businesses
- Welsh Language Commissioner, from search results only (the PDF's certificate failed):
  https://www.welshlanguagecommissioner.wales/media/pi0owks2/presentation-4-comisiynydd.pdf

SwimSignal:
- Code at `b5dc9b9`: the files named in section 3.
- Live files of the 15:29 BST build: `spots.json` (the three spots with only Dŵr Cymru
  overflows upstream, their `upstream_summary` and contributors) and `overflows.geojson` (14,631
  features; Dŵr Cymru's 128; none of Severn Trent's inside Wales).
- Section 4: a read-only Python script run with `DIPCAST_ROOT` on the main checkout and
  `DIPCAST_STATE` in scratch space, as described there. It made no network calls.
- EA annual returns: the main checkout's `data/processed/annual_returns.parquet` of 11 September.
  Dŵr Cymru's 128 rows; the long-term average compared with 2- to 5-year means for 2023 to 2025.
- Word count: the visible text of `api/static/*.html` and `site/*.html` without scripts, styles
  and comments, and the string literals of 12 or more characters in `site/*.js`.
