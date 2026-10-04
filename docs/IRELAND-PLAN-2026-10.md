# Ireland plan, October 2026

Written 4 October 2026, after Ethan asked whether SwimSignal can work for people in Northern
Ireland and the Republic of Ireland. It is a plan, not code: nothing here changes the site.

The plan treats the island as one river system: the Erne and the Foyle cross the border, so a
trace from a swim spot can run into the other jurisdiction. It treats the two jurisdictions as
separate for data, licences and regulators.

Two marks keep what is known apart from what is not. **Checked** means I read the source or ran
the measurement on 4 October 2026; section 12 gives the URL, the time and the command. *Inferred*
means a deduction or estimate that no source or measurement settles; where it matters, the text
says what would settle it. **Not checked** names a question I left open.

## 1. Summary

SwimSignal cannot forecast sewage pollution risk anywhere on the island of Ireland today, and it
should not try yet. The forecast needs each storm overflow's spill record, and neither
jurisdiction publishes one that SwimSignal may reuse. What SwimSignal can do now is list official
bathing-water information for both jurisdictions on the coverage page, as it does for Wales and
Scotland, and stop giving map clicks in Ireland a wrong answer.

**Northern Ireland: the data exists, but not under a licence SwimSignal can use.**

- Checked: NI Water has 2,458 storm overflows and 500 event duration monitors (EDMs: sensors that
  record when an overflow spills and for how long), both as of August 2026. It plans about 1,000
  monitors by 2028, which it says is about 40% of its overflows. *Inferred:* about 20% are
  monitored now (500 of 2,458).
- Checked: NI Water publishes a yearly summary per monitored overflow for 2023 to 2025, on a map
  and in a spreadsheet. It publishes no live status. Its legal notice limits downloaded content to
  personal, non-commercial use and forbids showing it in public without written approval. The map
  item says it is for use on niwater.com only, and the map's data layer refused a direct request.
- Checked: DAERA (the Department of Agriculture, Environment and Rural Affairs) publishes the
  latest result for each of 33 bathing waters, as a quality word and a sampling time, under the
  Open Government Licence. 32 are coastal. The one inland water, Rea's Wood on Lough Neagh,
  carries advice against bathing in 2026.
- Checked: DfI Rivers runs 130 water level stations under the Open Government Licence, but
  publishes them through a viewer with no documented API.

**Republic of Ireland: no overflow spill data is published at all.**

- Checked: the Environmental Protection Agency (EPA) estimates 2,469 storm water overflows.
  Uisce Éireann (the national water utility) had fitted monitors to 888 of them by the end of
  2022. On the pages listed in section 12, I found no published spill record, annual or live,
  for any of them.
- Checked: an EPA layer under CC BY 4.0 lists 1,739 storm water overflow points. 1,180 of them
  have a placeholder or impossible position, which leaves 559 that can be placed. It carries no
  spill data.
- Checked: the EPA's bathing-water API, under CC BY 4.0, covers 243 sites with 25,978 sample
  results since 2014 and the current bathing restrictions. It answered a plain request.
- Checked: the Office of Public Works (OPW) publishes 464 water level series every 15 minutes
  under CC BY 4.0, and asks automated users to tell it first.

**The river network.** Checked: SwimSignal's network (OS Open Rivers) has no link on the island.
The EPA's river network covers the Republic. It also returned segments in two Northern Irish
boxes, around Enniskillen and Omagh (*inferred* from their ids: the Erne and Foyle basins), and
nothing around Belfast or Ballymena. DAERA publishes a separate network of Northern Ireland's
main rivers under the Open Government Licence. *Inferred:* an all-island network can be joined
from the two, but only a measured study (task IE5) can say how well they meet at the border.

**How this compares with Islandswim.** Checked: Islandswim scores all 276 Irish and Northern
Irish bathing waters from rain alone. For the Republic it uses 546 discharge points with spill
thresholds borrowed from the nearest Welsh overflows; for Northern Ireland it uses no overflows,
for the licence reason above. *Inferred:* SwimSignal's own rule for a new region (positive
held-out skill with uncertainty, and an outside review, `docs/EXPANSION-2026-10.md`) rules that
out, because neither jurisdiction has spill records to test a forecast against. SwimSignal will
show less than Islandswim in Ireland for some time, on purpose.

Recommended order, as PR-sized tasks in section 10:

1. **IE1, now, whatever Ethan decides.** A click anywhere in Ireland today gets "No river or lake
   near this point has a monitored storm overflow within 60 km upstream" (checked, by running the
   site's own code). That is wrong: overflows there are monitored, and SwimSignal has none of their
   data. Give Ireland the England-only answer that Wales and Scotland already get.
2. **IE2 and IE3.** Add the Republic (EPA) and Northern Ireland (DAERA) to the coverage page as
   directories of official information, with no SwimSignal forecast.
3. **Send the emails in section 9.** They cost nothing. NI Water's answer decides whether a
   Northern Irish forecast is possible at all; Uisce Éireann's decides it for the Republic.
4. **Only if NI Water agrees:** study the network (IE5), load its event history and test the model
   on it (IE6, IE7), as the Scotland plan does. Stop there if the test shows no skill.
5. **The Republic waits** until Uisce Éireann publishes spill records. I found no date for that.

*Inferred:* steps 1 and 2 are three or four small PRs and need no one's permission beyond the
licences already stated. Step 4 cannot start before NI Water answers, so no Irish forecast is
likely before the 2028 bathing season.

## 2. What the sources publish

### 2.1 Northern Ireland: NI Water's storm overflows

Checked, from NI Water's storm overflow pages, map item and legal notice (read 15:02 to 15:12
UTC):

| Item | What I found |
|---|---|
| Overflows | 2,458 storm overflows, as of August 2026. 209 spill within 2 km of designated bathing waters |
| Monitors | 500 EDMs operating, as of August 2026, including at bathing and shellfish waters. About 1,000 planned by 2028, "circa 40% coverage" |
| 2025 totals | 12,938 spills and 48,688 hours. 173 overflows spilled fewer than 10 times; 43 did not spill |
| Map | An ArcGIS app on niwater.maps.arcgis.com. Each pin shows a summary for the 12 months to 31 December 2025 |
| Map item | Outfalls with 2023, 2024 and 2025 EDM data. "Updated 19/05/2026", to be updated once a year. Built from NI Water's asset register, discharge register and telemetry database. Licence field: for use on www.niwater.com only, usage limitations apply |
| Map layer | A proxied ArcGIS layer. A plain request at 15:07 UTC got HTTP 403, "You do not have permissions to access this resource". I did not retry with other headers |
| Spreadsheets | "Event Duration Monitor Data August 2026", 1,039,567 bytes, last modified 25 September 2026; "Modelled Spills November 2025", 263,199 bytes. HEAD requests only |
| Live status | None found. Both pages describe annual data only |
| Legal notice | Downloaded content is for "your own personal and domestic, non-commercial use". Copying, storing or showing it in public needs NI Water's prior written approval |

Not checked: I did not open either spreadsheet, because downloading files needs Ethan's yes. So I
do not know whether it gives positions, per-event times or only yearly counts. Islandswim's page
says the per-outfall annual data "carries no coordinates at all"; I have not confirmed that.

*Inferred:* NI Water holds event-level records, because its map is built from its telemetry
database. Whether it will release them, and under what licence, is the first question in
section 9.1.

### 2.2 Northern Ireland: DAERA bathing waters

Checked:

- **The list.** DAERA's dashboard reads an ArcGIS layer, "Bathing Water Monitoring Points Public
  View". One request at 15:08 UTC returned 33 sites: 32 coastal and 1 inland; 32 confirmed and 1
  candidate. Fields: site name, region, type, status, operator, profile and poster links, a water
  quality indicator, the sampling time and an override flag.
- **The latest state.** 30 sites read Excellent, 2 Good and 1 "NoBathing" (Rea's Wood). The
  latest samples were taken between 24 August and 16 September 2026. The layer's data was last
  edited at 12:30 UTC on 4 October.
- **Licence.** The dashboard item says the information may be reused under the Open Government
  Licence, and that not all of its datasets can be downloaded yet. DAERA's site content is under
  the Open Government Licence v3.0.
- **Samples.** The 2026 results (E. coli and intestinal enterococci, with dates) are HTML tables
  on DAERA's website, one per site, updated until mid-September. No file is offered.
- **Season.** June to mid-September, 20 samples per site. Results go up weekly, and sooner when
  temporary advice against bathing applies.
- **Advice.** Rea's Wood has advice against bathing for 2026 after a Poor rating in 2025. DAERA's
  general advice is to avoid bathing during or up to 48 hours after heavy rain.
- **Forecasts.** None found on the dashboard, the 2026 results page or the "about" page.

Not checked: a search result says DAERA was developing a short-term pollution prediction system
with INTERREG VA funding. I did not find it published.

### 2.3 Northern Ireland: DfI Rivers levels

Checked, from the Department for Infrastructure's page: 130 active hydrometric stations; the
"almost live" readings are in a viewer at hydrometcloud.de that offers downloads; reuse under the
Open Government Licence; the data is provisional and unchecked. The page gives no API and no
contact address. A plain fetch of the viewer failed with a redirect loop. A third-party
developer's issue (aquascope #318) also reports finding no documented API.

*Inferred:* SwimSignal should not read the viewer's undocumented calls. River levels in Northern
Ireland need DfI's agreement to a route (section 9.6).

### 2.4 Republic of Ireland: storm water overflows

Checked:

- **Counts.** The EPA's "Urban Wastewater Treatment in 2024" (October 2025) estimates 2,469 storm
  water overflows. Uisce Éireann had assessed 2,184 by the end of 2024 and found 238 below the
  national standards; 285 assessments were overdue. The 2022 report says monitors were fitted to
  888 overflows by the end of 2022, up from 790 a year before.
- **Publication.** Uisce Éireann's open data page offers eight datasets under CC BY 4.0: supply
  zones, metered areas, agglomerations, treatment plants, pumping stations and reservoirs. None is
  about overflows or spills. Its Water Action Plan page describes a survey and monitoring
  programme for overflows, with no numbers and no data.
- **Annual environmental reports.** Licensed wastewater areas file a yearly report with a storm
  water overflow section. The one I opened (Castletownshend, a small village) has no overflows.
  Not checked: whether larger reports give a spill count per overflow.
- **The EPA's overflow points.** The layer "Licence Enforcement and Monitoring Application
  Emission Points" (CC BY 4.0; catalogue revision 3 December 2022) returned 3,108 points in one
  request at 15:13 UTC. 1,739 are typed "Storm Water Overflow" and 69 "Emergency Overflow". Of
  the 1,739: 891 sit exactly on the Irish Grid's origin, off the Kerry coast, a placeholder; 289
  sit at latitude 89.995° S; 559 have plausible positions, at 548 distinct places. The layer has
  no spill data and no receiving-water name.
- **Live status.** None found.

*Inferred:* Uisce Éireann holds spill records for the monitored overflows, since the monitors
exist to record them. Until it publishes them, nothing can be forecast or tested in the Republic.

Not checked: the recast EU Urban Wastewater Treatment Directive (2024/3019) requires public
information online, and a search summary says that includes estimated overflow loads for larger
towns. I did not read the directive's text, so I do not know whether it will require spill
records per overflow, or when Ireland must apply it.

### 2.5 Republic of Ireland: EPA bathing waters

Checked: three plain requests to `https://data.epa.ie/bw/api/v1/` at 15:03 and 15:04 UTC, and one
at 15:18. Each answered HTTP 200. The API page states CC BY 4.0 and gives no rate limit. The
locations response carried no cache or rate-limit headers.

| Endpoint | What I found |
|---|---|
| `locations` (757,192 bytes, 0.66 s) | 243 sites: 154 "Identified" (designated) and 89 "Non-Identified" (monitored, not designated). Positions in Irish Grid metres; Loughrea Lake converts to Loughrea. 66 fields: ratings for 2022 to 2025, profile link, an all-season restriction flag, a `short_term_pollution_risk` flag (143 yes, 10 no, 90 empty), amenities, lifeguards, dogs |
| Ratings (2025) | 120 Excellent, 23 Good, 7 Sufficient, 1 Poor, 1 not classified, 91 none |
| Water type | Not a field. By the id's letter, the 154 designated sites are 139 coastal, 10 lake, 5 transitional and no river (*inferred* meaning of the letter; every "L" site is named for a lake). Ten of the non-designated sites are lakes in County Monaghan |
| `measurements` | 25,978 results, from 22 May 2014 to 15 September 2026: beach id, date, E. coli, intestinal enterococci, a status word. Values are text and can read "<10". Only `page` and `per_page` are documented, no date or site filter |
| `alerts` (1,394 bytes) | 2 in force: Lilliput, Lough Ennell (bathing temporarily prohibited since 8 September, suspected agricultural runoff) and Ballyallia Lake (since 11 September, algal bloom). Fields: start date, expected days, restriction type, cause, notice PDF, end date. The API page lists three kinds: Prior Warning, Advice Not to Swim, Do Not Swim |

Checked, from beaches.ie: the bathing season runs from 1 June to 15 September, and the site
updates hourly from 7am to 7pm. No forecast is published. I did not find an Irish-language
version.

*Inferred:* "Prior Warning" is the Republic's nearest thing to the EA's pollution risk forecast.
A directory that shows it, dated and credited, gives swimmers official advance warning without
SwimSignal making one.

### 2.6 Republic of Ireland: OPW river levels

Checked, from waterlevel.ie's API page and one request at 15:08 UTC:

- Licence CC BY 4.0, with a set attribution sentence. Automated users should tell OPW at
  waterlevel@opw.ie, giving their IP address and server URL. No bulk download more often than
  every 15 minutes. Only stations numbered 00001 to 41000 are suitable for republication.
- `geojson/latest/`: 736,639 bytes, 2,024 series. 464 are water level (sensor 0001); 461 of those
  are numbered within the republishable range, and 454 of them had a reading within 3 hours. The
  median age was 8 minutes.
- 452 series are temperature (sensor 0002), "in degrees Celcius". *Inferred:* water temperature;
  the station page does not say. If so, it could play the part the EA's sondes play in England
  (`ingest/water_temperature.py`).
- Each station's CSV holds 5 weeks of 15-minute values. Longer records are on OPW's Hydro-Data
  site.

Not checked: whether OPW publishes a typical range per station, as the Environment Agency does.
SwimSignal's level index depends on one.

### 2.7 The river network

Checked:

- **SwimSignal's network.** 193,040 OS Open Rivers links, in British National Grid (EPSG:27700),
  which `network/rivers.py` assumes throughout. No link has its midpoint in Ireland (a read-only
  count; the only links west of 5.4° W and south of 55.25° N are on the Isles of Scilly).
- **The EPA's "River Network Routes".** CC BY 4.0; last modified 1 November 2017; Irish Grid
  (EPSG:29902); built from 1:50,000 mapping and updated from surveys; Strahler stream order;
  lines carry route measures. Five bounding-box requests in Irish Grid metres, at 15:10 and 15:11
  UTC:

  | Box | Where | Segments |
  |---|---|---|
  | 195,000–215,000 E, 235,000–250,000 N | Athlone, Republic (control) | 261 |
  | 220,000–235,000 E, 335,000–350,000 N | Enniskillen, Northern Ireland | 399, ids starting `36_` |
  | 245,000–290,000 E, 360,000–390,000 N | Omagh to Cookstown, Northern Ireland | 800, ids such as `01_73_2` and `GBNI0101084` |
  | 325,000–340,000 E, 365,000–380,000 N | Belfast (Lagan) | 0 returned (1 matched) |
  | 300,000–320,000 E, 395,000–410,000 N | Ballymena (River Main) | 0 |

  *Inferred:* the id prefixes are Irish hydrometric areas, 36 the Erne and 01 the Foyle.

- **DAERA's "River Segments" (2010).** Open Government Licence (data.gov.uk record); "Rivers
  defined under Article 2(4)" of the Water Framework Directive; shapefile 7.79 MB, GML 9.89 MB.
  Not opened. *Inferred* from the description: it holds the main rivers that make up water bodies,
  not every stream.
- **EU-Hydro (Copernicus).** Covers Europe including the UK, in EPSG:3035, delineated at
  1:30,000. Its licence and flow direction were not readable from the pages I reached.
- **Projection.** Lengths measured in British National Grid are 0.04% too long at Belfast, 0.23%
  at Galway and 0.35% at Dingle (pyproj scale factors). Irish Transverse Mercator (EPSG:2157)
  keeps the whole island within 0.02%.

*Inferred:* the EPA network covers the Republic and the Northern Irish parts of the Erne and Foyle
basins, but not the rest of Northern Ireland. Joining it to DAERA's network would give an
all-island network whose two halves were drawn to different specifications. The 0.35% length
error is small beside the model's other uncertainties, so the joined network could be projected
into British National Grid and added to the same graph as a separate piece, which avoids changing
`rivers.py`. Task IE5 settles both points by measurement.

### 2.8 Rain

Checked: SwimSignal asks Open-Meteo for hourly rain with no model named (`ingest/rainfall.py`), so
it gets Open-Meteo's best match. The Met Office UKV model on Open-Meteo covers "UK and Ireland" at
2 km for 2 days; the Met Office global model covers 7 days at about 10 km.

*Inferred:* rain is the one input that works the same in Ireland as in England.

### 2.9 What Islandswim uses

Checked, from Islandswim's home page at 15:12 UTC. I read only what the page says.

- 942 sites in all, including 33 in Northern Ireland and 243 in Ireland. The 243 match the EPA's
  count above.
- Northern Ireland: no overflows. The page says NI Water's per-outfall annual data has no
  positions, and that NI Water's legal notice restricts reuse without written approval. Each
  Northern Irish site scores on rain alone, and its page says so.
- Ireland: 546 outlets from "EPA urban wastewater discharges", which the page describes as
  licensed treatment-plant discharge points with no spill history. Each outlet's rain threshold is
  borrowed from the three nearest calibrated outlets, which for Ireland are Welsh.
- Water bodies: DAERA and EPA classifications, matched by point in polygon. Council boundaries
  from ONS and Tailte Éireann. Rivers: OS Open Rivers, Great Britain only.
- The page says its scores do not replace DAERA's or the EPA's classifications or advisories.

Not checked: which EPA layer gave the 546 outlets. The EPA layer in section 2.4 has 548 distinct
plausible overflow positions, which may or may not be the same set.

## 3. What SwimSignal's code does with Ireland today

Checked by reading the code at `be1c85e`, and again at `139e032` (main when this was committed),
except where marked.

| Part | Where | England | Ireland today |
|---|---|---|---|
| River network | `network/rivers.py`, `oprvrs_gb.gpkg` | OS Open Rivers, EPSG:27700 | No link on the island (section 2.7) |
| Live overflow status | `config.LIVE_FEEDS`, `ingest/live.py` | Nine company layers on ArcGIS | None, and no live source found (section 2) |
| Overflow table | `overflows.build_overflows` | Kept inside latitude 49 to 61, longitude −9 to 3 | 91 of the 559 placeable EPA overflow points, and 96 of the 243 EPA bathing waters, lie west of 9° W, outside that box |
| Pooled spill model | `model/features.py` | Rain, season and three covariates from the EA annual returns | No covariates: every overflow would get the fixed defaults of 20 spills, 100 hours and 90% uptime |
| Calibration and lead calibration | `spill_model.fit_site_offsets`, `lead_calibration.json` | Fitted on United Utilities | English evidence only |
| River level, flood alerts | `ingest/flows.py` | EA | None |
| Lakes | `ingest/lakes.py` | EA WFD lake outlines | None on the island |
| E. coli | `model/ecoli.py` | Fitted on English inland bathing waters | Untested |
| Map clicks | `site/anypoint.js`, `data/raw/outside_england.json` | Click anywhere | The outside-England shape covers Wales and Scotland only. Checked by running `AnyPoint.place` in Node with the live `tiles.json` (15:15 UTC) at six points: the Lagan in Belfast, the Erne at Enniskillen, the Foyle at Derry, the Liffey in Dublin, the Shannon at Athlone and Lough Derg. Each got "No river or lake near this point has a monitored storm overflow within 60 km upstream, so SwimSignal has no sewage spills to forecast here." The click-anywhere squares stop at 5.75° W |
| Spot requests | `scripts/spot_request.py` | Answered | Its Great Britain box (latitude 49.8 to 60.95, longitude −8.7 to 1.8) contains Belfast and Dublin. *Inferred*, not run: such a request gets "no river or lake on SwimSignal's map within 1.5 km", with no mention that Ireland is not covered |
| Place search | `scripts/make_places.py` | OS Open Names, England and Wales | No Irish places |
| Coverage page | `api/static/coverage.html` | English coasts, Wales, Scotland | Nothing on Ireland. Its search compares lower-cased text without folding accents, so a search for "Tra" would not find "Trá"; the main page's search does fold them (`fold` in `index.html`) |
| Health words | `site/illness.js`, `terms.html` | "Call 111 or go to 111.nhs.uk"; "NHS 111" | *Inferred:* 111.nhs.uk is NHS England's service, so the words are wrong for the Republic and need checking for Northern Ireland |
| Words | footer, `manifest.webmanifest`, `api/app.py` | "in England" | Already true; would need changing only at a release |

## 4. Measured: the island in numbers

Checked. Every figure comes from the requests in section 12 and read-only scripts in my scratch
space; none came from the forecast pipeline.

| Measure | Northern Ireland | Republic of Ireland |
|---|---|---|
| Storm overflows | 2,458 (NI Water, August 2026) | about 2,469 (EPA, end of 2024) |
| Monitored | 500 (August 2026) | 888 (end of 2022); later count not found |
| Spill data published | Yearly per overflow, 2023 to 2025, not reusable | None |
| Live status | None | None |
| Overflow positions usable | Not published openly (layer refused) | 559 of 1,739 EPA points |
| Rain cells (0.1°) for those positions | Unknown | 256 |
| Bathing waters | 33: 32 coastal, 1 inland | 243: 154 designated, 89 other; 10 designated lakes, no rivers |
| Bathing-water licence | OGL v3 | CC BY 4.0 |
| Current restrictions | 1 (Rea's Wood, all season) | 2 alerts in force |
| Water level series | 130 stations, no API | 464 series; 454 of the 461 republishable ones read within 3 hours |
| Open river network | DAERA main rivers, plus EPA's in the Erne and Foyle | EPA |

## 5. What SwimSignal could offer, and what must abstain

### 5.1 By jurisdiction

| Offer | Northern Ireland | Republic of Ireland |
|---|---|---|
| Pollution risk forecast (spill chance, river risk, five days) | No. Blocked on NI Water: permission, event history and positions | No. Blocked on Uisce Éireann publishing spill records |
| "Right now" from live overflow status | No: there is no live feed | No: there is no live feed |
| Directory of official bathing-water information | Yes, now: DAERA's 33 sites, latest result and date, profile link, advice against bathing (IE3) | Yes, now: the EPA's 243 sites, ratings, latest sample, restrictions and prior warnings in force (IE2) |
| River levels | Not until DfI agrees a route | Possible (OPW, CC BY 4.0), but only useful at a spot, so not before a forecast |
| Overflow locations without spill data | Not without NI Water's permission | Possible from the EPA layer. *Inferred:* not worth showing; a dot without a spill record says nothing about risk |
| A correct answer to a map click | Yes, now (IE1) | Yes, now (IE1) |

### 5.2 What it must abstain from

Each item says why. "Checked" items rest on sections 2 to 4; the rest are *inferred*.

| Abstain from | Why |
|---|---|
| Any risk level, including "No sewage risk from monitored overflows", anywhere on the island | No spill data SwimSignal may use (checked) |
| A rain-only score, as Islandswim gives | Nothing in either jurisdiction to test it against, so it cannot meet the expansion rule (*inferred*) |
| Thresholds or covariates borrowed from England or Wales | The same reason. The defaults of 20 spills, 100 hours and 90% are English fallbacks (checked) |
| A level on a trace that crosses the border into a jurisdiction without data | One river system, two data regimes. If Northern Ireland opens first, a Fermanagh spot below Cavan's overflows would miss them all. Such a trace must say so and give no level (*inferred*; rule for IE7) |
| A level where most overflows have no monitor | In Northern Ireland about 80% have none today (checked counts; *inferred* share) |
| The E. coli figure | Fitted on 1,548 samples at 32 English inland bathing waters; its stated scope is rivers, May to September, with "no ranking skill on lakes" (checked, `data/processed/ecoli_model.json`). Every designated inland water in the Republic is a lake |
| Coasts and estuaries | No tide in the model, as in England. 32 of Northern Ireland's 33 and 144 of the Republic's 154 designated waters are coastal or transitional (checked) |
| Lakes, as forecasts | No Irish lake outlines in the code (checked). The EPA's lake water bodies and DAERA's would be needed first |
| Overflow positions at the Irish Grid origin | 891 placeholders and 289 impossible points (checked) |
| River levels from the DfI viewer | No documented API (checked) |
| Algae | Not researched for this plan. The EPA's alerts include algal-bloom restrictions (checked: Ballyallia Lake), so the directory shows them as official notices |

## 6. How a forecast would be validated before release

`docs/EXPANSION-2026-10.md` sets the bar for any region: "positive held-out skill with
uncertainty and external review". These stages meet it. Each stage writes its gate into the
script before it runs, so the gate cannot move after the results are seen. They apply to
whichever jurisdiction first has data; on today's evidence that can only be Northern Ireland.

**Stage 0: data and permission.** Written permission to reuse and republish the data, overflow
positions, and event start and stop times for at least two years. Without event times there are
no daily labels, so no test of a daily forecast is possible. Yearly counts alone allow only a weak
check: whether the model's expected spill-days per year rank the overflows as their counts do. The
plan's proposal is that yearly counts alone never justify a release.

**Stage A: hindcast (task IE7).** As in the Scotland plan, section 6: the current model,
not refitted, applied to the events with ERA5-Land rain (the reanalysis `scripts/train.py` uses).
Arms: the pooled model with default covariates; the pooled model with covariates from the year
before; the calibration layer where an overflow has two or more years. Baselines: each overflow's
spill-day rate from earlier years. Scores: Brier score and skill, log loss, AUC, reliability by
band, wet and dry days apart, at leads 0 to 3. Uncertainty: a cluster bootstrap over overflows and
weeks, 2,000 draws, chosen before the run. Gate A (proposed): the lower end of the 95% interval
of skill against the earlier-years baseline is above zero, overall and at leads 1 to 3, for the
arm named before the run.

**Stage B: shadow scoring.** Only possible with a live or at least monthly event feed. Log
forecasts, score them as their own company row in `verification.json`, publish nothing. Gate B
(proposed): skill above zero with its interval clear of zero over at least 200 scored
spill-days. *Inferred:* without any feed after the yearly files, Stage B cannot run, and the
plan's proposal is not to release on a hindcast alone.

**Stage C: outside review.** The EXPANSION package plus the Stage A and B results, the
abstentions in section 5.2 and the cross-border rule.

**Stage D: the season.** A released jurisdiction joins the pre-registered evaluation for its
first full season as a separately labelled region.

What cannot be validated here: the river risk index against water samples. Northern Ireland has
one inland bathing water and the Republic ten lakes, against 32 English inland sites for the
current E. coli fit (checked counts). *Inferred:* as in England, the spill forecast underneath is
what Stages A and B test.

## 7. Costs and limits

| Item | Size or count | Basis |
|---|---|---|
| EPA locations | 757,192 bytes, 0.66 s, one request | Checked |
| EPA alerts | 1,394 bytes, one request | Checked |
| EPA latest samples | No filter, so the last page or two by `page`; about 16.5 KB per 50 results | Checked size; *inferred* page count |
| DAERA bathing layer | 19,374 bytes, one request | Checked |
| OPW latest levels | 736,639 bytes, 0.74 s, one request; no more often than every 15 minutes | Checked |
| Builds | median 2.9 hours apart, at most 8.1 | Checked, `site.yml` comment |
| Directory data files | About 330 KB for 276 sites, scaling the Welsh snapshot `data/raw/wales_bathing_waters.json` (138,339 bytes for 114 sites) | *Inferred* from a checked size |
| Open-Meteo, Republic overflows | 256 cells of 0.1° for the 559 placeable points: 6 requests of 50 | Checked count; *inferred* use, only if a forecast ever runs |
| Open-Meteo, bathing sites | 148 cells for the EPA's 243 sites | Checked count; not needed for a directory |
| EPA network | Size not checked; WFS answers in pages | Not checked |
| DAERA river segments | 7.79 MB shapefile, once | Checked size |
| NI Water spreadsheet | 1.04 MB, once a year | Checked size |
| GitHub Pages | 1 GB site, 100 GB a month | Roadmap, checked 3 October |

Limits that matter more than size:

- None of `data.epa.ie`, DAERA's ArcGIS layer or `waterlevel.ie` has been tried from a GitHub
  runner. Several UK sources refuse runners (handoff section 5). Test with a throwaway workflow
  first.
- OPW asks for the requester's IP address. GitHub's runners have no fixed address, so the
  question goes in the email (section 9.5).
- No network calls beside a build or another local build (handoff section 5).

## 8. Access and language

- **Irish-language names.** Checked: the EPA data uses Irish names, for example "Trá Inis Oírr
  (Main Beach)", "Béal Bán" and "An Trá Mór, Gorumna Island". Show them as the source gives them,
  with their accents. The main page's search already folds accents; the coverage page's does not
  (section 3), so IE2 fixes it. *Inferred:* marking names as Irish for screen readers
  (`lang="ga"`) needs a reliable flag, and the EPA data has none, so leave it.
- **An Irish-language page.** *Inferred:* not needed for a directory. SwimSignal is a private,
  non-commercial site, not a public body; the Official Languages Act's duties fall on public
  bodies. Not legal advice; revisit if Irish users ask.
- **Northern Ireland.** No language need found beyond English for this scope.
- **Units.** The Republic uses kilometres on roads. SwimSignal's travel distances are in miles
  (`docs/DESIGN.md`, 4 October 2026). A question for Ethan before any Irish spot exists.
- **Health contacts.** The illness note points to NHS 111 online. *Inferred:* a Republic page
  needs the HSE and 112 or 999 instead; Northern Ireland's route needs checking. Health-advice
  wording is Ethan's.
- **Law and privacy.** *Inferred, not advice:* the terms are governed by the law of England and
  Wales and mention consumers in Scotland and Northern Ireland only. Features that keep data
  about people in the Republic (alerts, reviews) may bring EU rules into play as well as UK ones.
  Ethan should ask an adviser before promoting any feature there. A directory keeps nothing new.
- **Time.** *Inferred:* Ireland and the UK share the same clock changes, so the site's
  Europe/London times read correctly in both.

## 9. Questions to ask, with draft emails

None of these emails has been sent. Each address comes from the source named in section 12.

### 9.1 NI Water (not sent)

To: waterline@niwater.com (the contact on NI Water's storm overflow page)
Subject: Permission to reuse storm overflow monitoring data on a free swimming website

> Hello,
>
> I run SwimSignal (swimsignal.co.uk), a free, non-commercial website that forecasts sewage
> pollution risk for river and lake swimmers in England from the water companies' overflow data.
> We would like to do the same for Northern Ireland, carefully and only after testing it. Your
> legal notice asks for written approval before content is reused, so I am writing first.
>
> 1. Permission. May we use your event duration monitor data, with credit to NI Water and a link
>    to your map, to build and publish forecasts? Under what licence or conditions?
> 2. Positions. Could we have the outfall position of each monitored overflow, as shown on your
>    map?
> 3. Event history. Do you hold start and stop times for each spill for 2023 to 2025? We would use
>    them to test our method before anyone sees a forecast. We would not republish the raw
>    events without your agreement.
> 4. Live status. Do you plan a near-real-time feed, like those of the English companies and
>    Scottish Water? If so, when?
> 5. Coverage. Which overflows will gain monitors by 2028, and is there a list of all 2,458
>    overflows with positions, monitored or not?
>
> We would never show a quiet or unmonitored overflow as clean water. Happy to share a preview
> before anything goes live.
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 9.2 Uisce Éireann (not sent)

To: OpenData@water.ie (the contact on Uisce Éireann's open data page)
Subject: Storm water overflow spill data for a free swimming website

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free, non-commercial website that forecasts sewage pollution
> risk for river and lake swimmers from storm overflow data. We are looking at whether it could
> work in Ireland.
>
> 1. Spill records. The EPA reports that monitors were fitted to 888 storm water overflows by the
>    end of 2022. Do you publish, or plan to publish, how often and how long each one spills? If
>    so, where, and under what licence?
> 2. Event times. Could start and stop times for each spill be shared for testing, under CC BY 4.0
>    or another licence?
> 3. Live status. Do you plan a near-real-time overflow map or feed?
> 4. Register. Is there an open list of storm water overflows with positions and monitoring
>    status? The EPA's emission points layer has many overflows at placeholder positions.
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 9.3 EPA, bathing water data and overflow points (not sent)

To: bathingwater@epa.ie (the contact in the EPA catalogue record for bathing water alerts)
Subject: Reusing the Bathing Water Open Data API on a free swimming website

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free, non-commercial website for swimmers. We would like to
> list Ireland's bathing waters with their latest results and any restriction in force, read from
> your Bathing Water Open Data API, credited to the EPA under CC BY 4.0 with a link to each
> beaches.ie page.
>
> 1. Use. We would make about three requests every three hours. Is that acceptable from automated
>    builds on GitHub Actions, which use shared cloud addresses? What attribution wording do you
>    prefer?
> 2. Latest samples. Is there a way to ask for the latest result per site, or results since a
>    date, rather than paging through all of them?
> 3. Alerts. Is a "Prior Warning" issued ahead of expected pollution, for example after heavy rain?
>    Does an alert stay in the feed until its end date is set?
> 4. Overflow points. In the layer "Licence Enforcement and Monitoring Application Emission
>    Points", 891 storm water overflows sit at the Irish Grid origin and 289 at an impossible
>    position. Is a corrected version available?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 9.4 DAERA, bathing waters (not sent)

To: Marine.InfoRequests@daera-ni.gov.uk (the address on DAERA's bathing water page)
Subject: Reusing bathing water results on a free swimming website

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free, non-commercial website for swimmers. We would like to
> list Northern Ireland's 33 bathing waters with their latest result and date, and a link to each
> profile, under the Open Government Licence as your dashboard states.
>
> 1. Source. May we read the "Bathing Water Monitoring Points Public View" layer that feeds your
>    dashboard, a few times a day? Or is there a source you would rather we used?
> 2. Meaning. What does "NoBathing" mean in the water quality field? Does it mark both temporary
>    advice against bathing and the season-long advice at Rea's Wood?
> 3. Samples. May we show the E. coli and intestinal enterococci values from your yearly results
>    pages, credited to DAERA? Is there a machine-readable copy?
> 4. Forecasts. Are short-term pollution predictions planned for Northern Irish bathing waters?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 9.5 OPW, river levels (not sent)

To: waterlevel@opw.ie (the address waterlevel.ie asks automated users to write to)
Subject: Automated access to waterlevel.ie for a free swimming website

> Hello,
>
> As your API page asks, I am letting you know that SwimSignal (swimsignal.co.uk), a free website
> for swimmers, may read `geojson/latest/` once every one to three hours, crediting the OPW with
> your attribution sentence.
>
> 1. Address. Our builds run on GitHub Actions, which has no fixed IP address. Is that acceptable?
> 2. Usual range. Do you publish a typical low and high level per station? If not, may we work one
>    out from Hydro-Data's daily means?
> 3. Temperature. Is sensor 0002 water temperature?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 9.6 DfI Rivers, river levels (not sent)

To: no address found on DfI's water level page; send through DfI's general contact route.
Subject: Reusing DfI Rivers water levels on a free swimming website

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free website for swimmers. Your water level page says the
> data may be reused under the Open Government Licence. Is there a supported way for a website to
> read the latest level at each station automatically, once every one to three hours? We would
> not want to rely on the viewer's internal calls without your agreement.
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

## 10. PR-sized tasks, in order

Each is one PR against main. IE1 to IE3 need no decision beyond Ethan's yes to this plan. IE5
onwards waits for NI Water's answer.

**IE1. A correct answer for clicks and requests in Ireland.** Add Northern Ireland (the ONS
countries layer that `make_outside_england.py` already reads includes it; *inferred*) and the
Republic (an open boundary: Tailte Éireann's under CC BY 4.0 or Natural Earth; licence to check)
to the outside shape, widened over loughs and estuaries as Wales and Scotland are. The click then
gets "SwimSignal has overflow data for England only, so it has no forecast here." In
`spot_request.py`, give Irish coordinates the outside-England answer rather than "no river or
lake on SwimSignal's map". Tests at the six points of section 3 and one each side of the
Foyle and the Erne. Screenshots at 320, 375 and 1440 px.

**IE2. The Republic on the coverage page.** A small adapter in the pattern of `wales.py` and
`scotland.py`: the EPA's 243 sites (designated first, the others labelled as monitored but not
designated), the latest rating, the latest sample with its date, and any alert in force with its
type, start date and notice link. Explicit states for missing and old data. Credit under CC BY
4.0. The page's search folds accents. A runner test first (a throwaway workflow; needs Ethan's
yes). Words: "SwimSignal does not issue forecasts in Ireland." Tests from a trimmed copy of the
4 October answers.

**IE3. Northern Ireland on the coverage page.** The same for DAERA's 33 sites: latest indicator
with its sampling date, profile link, and the advice against bathing at Rea's Wood. Credit under
the Open Government Licence v3.0. Send email 9.4 alongside; DAERA's answer on "NoBathing" sets the
words. Runner test as in IE2.

**IE4. Send the emails** in section 9, and record the answers in this file.

**IE5. Network study (off CI; publishes nothing; only after NI Water agrees to email 9.1).**
Download the EPA River Network Routes and DAERA's river segments (Ethan's yes to the downloads). Measure:
flow direction and connectivity in each; where the two meet at the border (Erne, Foyle,
Blackwater); which Northern Irish basins the EPA set lacks; snap rates for NI Water's outfalls
and the 559 EPA points; the length error of each projection choice. Compare EU-Hydro if its
licence allows. Report in the PR; choose the network there.

**IE6. Import NI Water's data (off CI; only with written permission).** One row per event in the
`edm_events` schema, or one row per overflow-year if only counts are given. Report overflows,
events and years, and how many positions snap.

**IE7. Hindcast for Northern Ireland (Stage A).** As Scotland's S3, with Gate A in the docstring
before the first run, and the cross-border rule of section 5.2 written into it. If it fails,
the next PR is a short write-up and the rest stops.

**IE8. Shadow scoring (Stage B),** only if a live or monthly event feed exists.

**IE9. Lake outlines and river levels.** EPA and DAERA lake water bodies beside the EA's; OPW
levels with a usual range; DfI levels only through an agreed route.

**IE10. Outside review (Stage C).** A document PR with the reviewer's dated assessment, published
with their consent.

**IE11. Release, per jurisdiction.** Split the outside shape so a released jurisdiction opens;
Irish places in the search (gazetteer and licence to choose then); credits; units and health
words as Ethan decides; screenshots at 320, 375 and 1440 px.

**IE12. The Republic's forecast.** Restart at IE5 when Uisce Éireann publishes spill records.

## 11. For Ethan

1. **Is Ireland in, as a directory now and a forecast later?** The plainest choice, taken here:
   IE1 to IE3 now; no forecast work until NI Water answers.
2. **Send the six emails** in section 9, or say who should. 9.1 (NI Water) and 9.2 (Uisce
   Éireann) decide whether a forecast is ever possible.
3. **Approve the runner tests** for IE2 and IE3 (a throwaway workflow, as before).
4. **Approve downloads** for IE5 (the EPA network, size unknown; DAERA's segments, 7.79 MB) and,
   if NI Water agrees, its 1.04 MB spreadsheet.
5. **Rain in the last 48 hours on directory entries?** DAERA advises against bathing for 48 hours
   after heavy rain, and the figure would help a swimmer apply that. The plan's choice is to leave
   it out, so the directory holds official information only. The alternative is the measured rain
   with no level.
6. **Units in the Republic.** Miles, as in England, or kilometres. Only matters at IE11.
7. **Health wording** for Northern Ireland and the Republic, replacing NHS 111 where it does not
   apply. Only matters once Irish spot pages exist.
8. **Legal advice** on EU privacy rules before promoting alerts or reviews in the Republic.

## 12. Sources and how each number was obtained

All read or run on 4 October 2026. Times are UTC. Requests used SwimSignal's User-Agent and no
key; each was a single request unless stated.

NI Water:
- EDM page, read 15:02 and 15:06:
  https://www.niwater.com/about-your-water/storm-overflows/storm-event-duration-monitors and
  https://www.niwater.com/storm/event-duration-monitors/
- Storm overflows page (2,458 overflows; map iframe; spreadsheet links; waterline@ address),
  HTML fetched 15:06: https://www.niwater.com/about-your-water/storm-overflows
- Map app item and its web map, 15:07:
  https://www.arcgis.com/sharing/rest/content/items/7edc8fd1ce1e4b119076ecfe4fe46969?f=json and
  https://www.arcgis.com/sharing/rest/content/items/b22c916a42c94ecfa7b16742552a287b/data?f=json
- Map layer, HTTP 403 at 15:07:
  https://utility.arcgis.com/usrsvcs/servers/abe1dd14d11f4200b97bf6b8c994ac67/rest/services/Discharge_Locations_view/FeatureServer/0?f=json
- Spreadsheets, HEAD only, 15:07:
  https://www.niwater.com/media/3mwndn2k/event-duration-monitor-data-august-2026.xlsx and
  https://www.niwater.com/media/0jdlj0ex/niwatermodelledspillsnovember2025.xlsx
- Legal notice, read 15:12: https://www.niwater.com/legal-notice

DAERA:
- Dashboard page, 15:07: https://www.daera-ni.gov.uk/articles/bathing-water-quality-dashboard
- Dashboard item and its map, 15:08:
  https://www.arcgis.com/sharing/rest/content/items/d676449ba9794912aa21ac8904e14cb8?f=json and
  https://www.arcgis.com/sharing/rest/content/items/1b3330c87dc1438ba0ca0f73c2b94286/data?f=json
- Monitoring points layer, fields and one query (all 33 features), 15:08:
  https://services-eu1.arcgis.com/kswen6BYexuc1SUk/arcgis/rest/services/Bathing_Water_Monitoring_Points_Public_View_PRD/FeatureServer/0
- 2026 results: https://www.daera-ni.gov.uk/articles/bathing-water-data-2026
- About bathing water quality (season, samples, Rea's Wood, contact address):
  https://www.daera-ni.gov.uk/articles/about-bathing-water-quality
- Crown copyright (OGL v3): https://www.daera-ni.gov.uk/crown-copyright
- River segments: https://www.daera-ni.gov.uk/publications/rivers-digital-datasets and
  https://www.data.gov.uk/dataset/c734ecd3-7603-4397-8da9-57e79e398599/https-www-daera-ni-gov-uk-sites-default-files-publications-doe-riversegmentgml-zip

DfI Rivers:
- https://www.infrastructure-ni.gov.uk/articles/dfi-rivers-water-level-network (read 15:09);
  viewer https://www.hydrometcloud.de/Rivers_Agency/index.jsp?menu=index (redirect loop)
- Third-party note: https://github.com/Rekin226/aquascope/issues/318

Uisce Éireann and the EPA, overflows:
- Open data page (eight datasets, CC BY 4.0, OpenData@ address), 15:05 and 15:19:
  https://www.water.ie/open-data
- Water Action Plan measure page: https://www.water.ie/node/13511
- Urban Wastewater Treatment in 2024 (2,469; 2,184; 238; 285), text extracted with pdftotext:
  https://www.epa.ie/publications/monitoring--assessment/waste-water/Urban-Wastewater-Treatment-in-2024-report.pdf
- Urban Waste Water Treatment in 2022 (888 monitored):
  https://www.epa.ie/publications/monitoring--assessment/waste-water/Urban-Waste-Water-Treatment-in-2022-Report.pdf
- Castletownshend annual environmental report: https://epawebapp.epa.ie/licences/lic_eDMS/090151b28042968f.pdf
- Emission points: catalogue https://gis.epa.ie/geonetwork/srv/api/records/32863d1b-6175-4918-af35-9a76e3336be0;
  one WFS request at 15:13 (3,108 features, 1,560,057 bytes):
  https://gis.epa.ie/geoserver/EPA/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=EPA:LEMA_EMISSIONPTSSNAPPED&maxFeatures=20000&outputFormat=application%2Fjson&srsName=EPSG:4326

EPA, bathing waters:
- API page: https://data.epa.ie/api-list/bathing-water-open-data/
- Requests: https://data.epa.ie/bw/api/v1/locations?page=1&per_page=1000 (15:03),
  https://data.epa.ie/bw/api/v1/alerts?page=1&per_page=1000 and
  https://data.epa.ie/bw/api/v1/measurements?page=1&per_page=50 (15:04),
  https://data.epa.ie/bw/api/v1/measurements?page=520&per_page=50 (15:18)
- Catalogue record with the bathingwater@ address:
  https://gis.epa.ie/geonetwork/srv/api/records/d0f854d7-1555-4a27-a9a6-ee366d9dca5c
- beaches.ie: https://www.beaches.ie/about/

OPW:
- API page: https://waterlevel.ie/page/api/
- Latest readings, 15:08: https://waterlevel.ie/geojson/latest/
- Station page (temperature units): https://waterlevel.ie/0000001041/0002/

River networks:
- EPA River Network Routes: https://data.gov.ie/dataset/river-network-routes; five WFS requests
  at 15:10 and 15:11 to
  `https://gis.epa.ie/geoserver/EPA/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=EPA:WATER_RIVNETROUTES&outputFormat=application%2Fjson&bbox=<box>`
  with the boxes of section 2.7 (two earlier requests with latitude-longitude boxes returned
  nothing, including the control, and are not used)
- EU-Hydro: https://land.copernicus.eu/en/products/eu-hydro/eu-hydro-river-network-database

Rain: https://open-meteo.com/en/docs/ukmo-api

Islandswim: https://islandswim.co.uk/, HTML fetched at 15:12 and read as text.

SwimSignal:
- Code at `be1c85e` and `139e032`: the files named in section 3.
- Clicks: `AnyPoint.place` from `src/dipcast/site/anypoint.js`, run in Node with
  https://swimsignal.co.uk/data/anypoint/tiles.json (fetched 15:15; 334 squares of 0.25°) and
  `data/raw/outside_england.json`.
- Network: a read-only script on the main checkout's `data/processed/river_network.pkl`, counting
  link midpoints by position. No network calls.
- Positions and scale factors: pyproj, Irish Grid (EPSG:29903) to WGS84 for the EPA sites, and
  `Proj.get_factors` for EPSG:27700, 2157 and 29903.
