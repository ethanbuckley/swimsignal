# Scotland plan, October 2026

Written 4 October 2026 for roadmap rank 11 (`docs/ROADMAP-2026-10.md`, section 3.2) and handoff
task I (`docs/HANDOFF-2026-10-04.md`). It is a plan, not code: nothing here changes the site.

Two marks keep what is known apart from what is not. **Checked** means I read the source or ran
the measurement on 4 October 2026; section 11 gives the URL or command. *Inferred* means a
deduction or estimate that no source or measurement settles; where it matters, the text says what
would settle it.

## 1. Summary

SwimSignal could forecast the daily spill chance of Scotland's monitored overflows with the
model it already has, and the pollution risk on Scottish rivers below them. It should show none of
it until the model has passed a test on Scottish spill records and an outside review.

Ethan decided on 4 October 2026 that Scotland is in for 2027 (section 10). He also wants Wales and
Ireland, including Northern Ireland, where possible. Their plans are being written separately, on
the branches `claude/wales-plan` and `claude/ireland-plan`; this document covers Scotland only.

Two findings change the roadmap's picture of Scotland.

1. **Scottish spill history exists.** The roadmap and the handoff said there was none. Checked: Scottish Water
   publishes start and stop times for each overflow event, under the Open Government Licence v3,
   for about 300 overflows from 2021 to 2025 and for other monitored overflows from 2022 to 2025.
   In August 2026 it added 2025 events for about 1,000 more. In all, 1,287 monitored overflows
   have published annual data. *Inferred*, until task S1 opens the files: the model can be tested
   on Scotland before anyone sees a Scottish forecast, and the per-overflow calibration layer can
   be fitted where an overflow has history.
2. **The live feed's licence is not named.** The roadmap called it OGL. Checked: the API page
   says only "an open license for reuse" and asks users to cite Scottish Water. A catalogue
   record for a copy of the data says "Open Government Licence (OGL)" with no version. Scottish
   Water should confirm which licence applies before the site publishes anything from it.

What stays hard (checked, except where marked):

- **Less is monitored.** The live map shows 2,074 locations. Environmental Standards Scotland
  counted 3,674 storm and emergency overflows in Scotland in 2022/23. *Inferred:* if both counts
  still hold, about 44% of Scottish overflows have no live monitor. A trace that finds no monitored
  overflow upstream can still have unmonitored ones above it.
- **The pooled model needs inputs Scotland lacks.** It uses each overflow's long-term spill count,
  spill hours and monitor uptime from the Environment Agency's annual returns. Scotland has no rows
  there, so the code would give every Scottish overflow fixed defaults: 20 spills, 100 hours, 90%.
- **Lochs fall back to a rough rule.** None of the 564 lake outlines the site uses is in Scotland.
- **No E. coli check exists yet.** The E. coli model was fitted on samples at 32 English
  inland bathing waters. Scotland's designated waters are mostly beaches. By location, three are
  freshwater lochs.
- **River levels need registration.** SEPA's level service is open, but its anonymous daily
  allowance runs out, and SEPA asks web products to register.

Recommended order, as PR-sized tasks in section 9:

1. Ask Scottish Water and SEPA the questions in section 8. They cost nothing and block the release.
2. Load Scottish Water's event history and test the current model on it (a hindcast: forecasts
   made after the fact with the rain that fell, scored against what the overflows did). Stop
   there if it shows no skill.
3. If it does, poll the live feed in shadow: log forecasts for Scottish overflows, score them, show
   nothing, through at least one wet autumn and winter month.
4. Add loch outlines and SEPA river levels.
5. Send the hindcast and shadow scores for outside review. Release only after a positive review.

*Inferred:* steps 2 to 5 are a winter's work, about 8 to 10 PRs. A release before the 2027 bathing
season is possible only if the hindcast passes by January.

## 2. What the sources publish

### 2.1 Scottish Water's near-real-time overflow API

Checked: one plain request from this Mac, 14:37 UTC on 4 October 2026, to
`https://api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time`, with SwimSignal's
User-Agent and no key. It answered.

| Item | What I found |
|---|---|
| Answer | HTTP 200, 2,961,021 bytes of JSON in 2.9 s. A second request, asking for gzip, got the same 2,961,021 bytes: no compression. No cache, ETag or rate-limit headers |
| Shape | `{"results": [...], "last_updated": <epoch ms>}`. `last_updated` was 14:01:07 UTC |
| Assets | 2,074 rows, 2,074 distinct `ASSET_ID`s. Latitude 54.79 to 60.76 |
| Fields | 33 on every row, every value a string (the API page's example shows numbers and lists 31; the live answer adds `OVERFLOW_DISCHARGEID` and `OVERFLOW_DISCHARGEID_PREVIOUS`) |
| Events | The latest event and the one before it: start, end and duration in minutes, each with a discharge id. An overflowing asset has no end time (40 of 40) |
| Status | 1,303 "No Overflows" (15), 455 "Recent Overflow" (14, an event in the last 48 hours), 40 "Overflowing" (13), 276 "No Data Available" (16) |
| Why no data | Of the 276: 203 under maintenance, 41 no data in 48 hours, 27 not monitored in real time, 2 no valid data, 2 inactive device, 1 inactive site |
| Freshness | 1,834 rows carry `DEVICE_LAST_TRANSMITTED_DATETIME`; 1,721 of them within 6 hours, median age 1.5 hours. The 276 with no data: median age 149.5 hours |
| Types | CSO 1,734; settled storm sewage overflow (SSSO) 177; emergency overflow (EO) 102; mixed 61 |
| Other | Receiving water name, licence number, postcode, British National Grid position, local authority, investment priority and drivers, and `RAINFALL_HISTORY`: 48-hour rain in mm at 1,791 assets (its source is not stated) |
| Long events | Two "Overflowing" rows had run 218 and 682 hours without a stop |
| Clustering | 242 assets had their previous event start less than 3 hours before their latest |

What the API page says (checked): updated every 60 minutes, "not all the overflows record data and
update data at the same frequency"; times are UTC in the API and local on the map; "No
authentication is required, but users should respect rate limits and cache data where possible"
(no rate is given); "Data is provided under an open license for reuse. Scottish Water is not liable
for third-party interpretations. Users must cite Scottish Water as the data source." It also says
the monitors "do not confirm overflow events, they only indicate them", and "We can't say there has
been any pollution or promise the water is safe to swim in."

A copy of the feed on ArcGIS, published by the Scottish Government's spatial data service, carries
the 31 fields of the API page's example (no discharge ids). Checked: its data was last edited at
23:03 UTC on 2 October, 39 hours before I read it. It is not a live fallback.

Not checked: whether the API answers GitHub's runners. Several UK sources refuse them, and testing
needs a throwaway workflow, which this session may not run. Section 9, task S4, puts the test first.

### 2.2 Scottish Water's spill history

Checked, from Scottish Water's "Published Overflow Data" page and the two data.gov.uk records:

- **Reported to SEPA, 2021 to 2025.** Overflows with annual reporting in their discharge permits,
  "around 300 locations". Start and stop times, duration and volume for each event longer than
  15 minutes 30 seconds, and a yearly summary per measurement point. OGL v3 on data.gov.uk
  (version 2, published 5 August 2026). File:
  `sw-reported-overflow-event-data-to-sepa-20212025--summary--v2-050826.xlsx`, 5,454,175 bytes.
- **Not reported to SEPA, 2022 to 2025.** Other monitored overflows "only where data has been
  verified": event start and stop times and durations, and a yearly summary. OGL v3 on
  data.gov.uk (version 2, published 31 August 2026). File:
  `scottish-water-non-reported-overflow-event-data-2022-2025-and-summary--310826.xlsx`, 7,549,740 bytes.
- **2025 expansion.** "In August 2026, we published 2025's annual overflow event data, where
  verified, for around 1,000 additional locations". These include all events, short ones too;
  earlier years kept only events over 15 minutes 30 seconds. Water Briefing (1 September 2026)
  gives the total with annual data as 1,287, "from 6% to 30%".
- **Next.** 2026 events "for all locations shown on the map" in March 2027.

Not checked: I did not open either file. Downloading files was outside what this session could do
without Ethan's approval, so I read only their size and type (HEAD requests). How many overflows
and events each holds, and whether its ids match the API's `ASSET_ID`, is task S1's first job.

**Added 4 October 2026, evening: SEPA's own event file.** Checked, the page and SEPA's data
terms; the file was not opened. SEPA's improving urban waters page
(sepa.org.uk/environment/water/improving-urban-waters/) offers "Overflow events reported to SEPA",
January 2020 to December 2025, for Scottish Water and PFI permits in one spreadsheet (6,315,560
bytes, modified 13 August 2026). PFI overflows are run by private contractors, so they are not in
Scottish Water's files. The page states no licence. SEPA's default data terms allow
non-commercial use of "Our Data", narrowly defined, and exclude third-party data. *Inferred:* it
could fill the PFI gap. Email 8.2 should ask SEPA whether the Open Government Licence applies.

*Inferred:* the 2025-only overflows have one year of history, too little for the calibration layer
to move far from the pooled model (its prior is worth 15 spill-days), but enough to score it.

### 2.3 SEPA river levels (KiWIS time series API)

Checked, from SEPA's API documentation and one listing request at 14:41 UTC:

- "The data are provided as open data under the Open Government Licence with no requirement for
  registration." Attribution to SEPA is required.
- Anonymous access has 5,000 credits a day, counted per IP address. SEPA warns: "there is currently
  an issue with anonymous access which means that the data limit is quickly exceeded each day", and
  "If you intend to include our data in a web product, you should definitely register." A
  `Referer` header gives a caller its own allowance without registering.
- Credits: 1 per 1,000 values; the latest value of 410 series costs 20; at most 300,000 values in
  one request. Times are GMT.
- 394 stations have a 15-minute river level series (`stationparameter_name=Level`,
  `ts_name=15minute`). 345 had a reading within 3 hours of my request; 43 had none for over 30 days.
- No typical range per station was found. The Environment Agency publishes one, and SwimSignal's
  level index (0 at typical low, 1 at typical high) depends on it. SEPA's own water-levels page shows
  a "State" for each station; how it is defined was not found.
- SEPA's flood warnings: its data catalogue lists an API with access "via ffw@sepa.org.uk".

Not checked: whether `timeseries.sepa.org.uk` answers GitHub's runners. SEPA's map server does
(checked from a runner on 3 October, per `src/dipcast/scotland.py`).

### 2.4 SEPA bathing waters

Checked:

- **The list.** SEPA's "Bathing Water Points" REST layer: 90 waters, fields `description`, `year`,
  `class_description`, `bw_url` and an object id. SEPA's catalogue lists it under OGL v2. It has no
  water-type field. `scotland.py` already reads it for the coverage page.
- **Freshwater sites.** By location, three of the 90 are on freshwater lochs: Luss Bay (Loch
  Lomond), Dores (Loch Ness) and Loch Morlich. *Inferred* from where they are; SEPA's profiles would
  confirm it.
- **Samples.** The catalogue lists the "Locations" results pages under "SEPA website conditions of
  use". SEPA's data terms (version 3.1, February 2016) list among prohibited uses "publishing it or
  making it available to the public by the internet or any other means". Which terms govern the
  results pages is not stated. A second route, "Bathing Water Analysis" on Scotland's Environment
  web, offers CSV under that site's terms: "You may use this Website for non-commercial purposes",
  and "All data presented on the Website is open data unless otherwise identified". That app runs in
  JavaScript; I did not look inside it.
- **Predictions.** "Real-time bathing water quality predictions, posted daily by 1000 from mid-May
  to 15 September", at 30 bathing waters, in an HTML table and on electronic signs. They "are based
  on rain and reflect risks from any overflows acting (as designed)"; a failure such as an
  electrical fault "will not be captured". No licence is stated on the page.
- **Season.** SEPA monitors from 15 May to 15 September.

### 2.5 Rain

Checked: SwimSignal asks Open-Meteo for hourly rain with no model named, so it gets Open-Meteo's
best match, as in England. Open-Meteo's free terms allow fewer than 10,000 calls a day, 5,000 an
hour, 600 a minute and 300,000 a month. A request for more than two weeks of data for one location
counts as more than one call. The Met Office UKV model on Open-Meteo covers "UK and Ireland".

*Inferred:* rain is the one input that works the same in Scotland as in England. Whether forecast
skill for Highland rain matches lowland England is a question for the hindcast (section 6).

## 3. What SwimSignal's code does with Scotland today

Checked by reading the code at `be1c85e`.

| Part | Where | England | Scotland today |
|---|---|---|---|
| River network | `network/rivers.py`, OS Open Rivers `oprvrs_gb.gpkg` | Used | Already loaded: 77,310 of the 193,040 links are in Scotland (section 4) |
| Live overflow status | `config.LIVE_FEEDS`, `ingest/live.py` | Nine company layers on ArcGIS, the National Storm Overflow Hub schema | None. Scottish Water's API is not ArcGIS and has another schema |
| Overflow table | `overflows.build_overflows` | Live rows joined to the EA annual returns, kept inside latitude 49 to 61, longitude -9 to 3 | That box already includes all 2,074 Scottish assets (latitude up to 60.76) |
| Pooled spill model | `model/features.py`, `SITE_FEATURES` | Rain, season and three covariates from the EA annual return | No covariates: `site_static_features` falls back to the company median, then the median of the overflows passed in, then 20 spills, 100 hours and 90%. A Scottish spot's upstream list holds only Scottish overflows, so every one gets those defaults. The EA annual returns have no row north of 55.79 N (checked in the local `annual_returns.parquet`) |
| Calibration layer | `spill_model.fit_site_offsets` | Fitted on United Utilities' event history | None; an overflow without an offset gets 0, the pooled prediction |
| Lead calibration | `data/processed/lead_calibration.json`, `scripts/verify_leads.py` | Fitted on United Utilities, 2025 | Would apply unchanged. It is English evidence, not Scottish |
| Live scoring | `forecast_log.verify_live` | Scores each company's overflows from polled history | Nothing polled. The scores are kept per company, so a polled Scottish history could be scored as its own row (*inferred*) |
| River level | `ingest/flows.py` | EA flood-monitoring API; the spot forecast runs with `gauge=False`, so the level is shown, not used | None |
| Flood alerts | `flows.flood_alerts` | EA | None |
| Lakes | `ingest/lakes.py` | 564 EA WFD lake outlines; lake-area dilution | None of the 564 is in Scotland (checked). Lochs fall back to OS lake centrelines with no area term |
| E. coli | `model/ecoli.py` | Fitted on EA samples at inland bathing waters, May to September | Would run, untested |
| Clicks | `site/anypoint.js`, `data/raw/outside_england.json` | Click anywhere | A click in Wales or Scotland gets "SwimSignal has overflow data for England only, so it has no forecast here." |
| Spot requests | `scripts/spot_request.py` | Answered | Answered with the outside-England message |
| Place search | `scripts/make_places.py`, `COUNTRIES = {"England", "Wales"}` | Searched | No Scottish places |
| Coverage page | `scotland.py` | n/a | SEPA's 90 waters, ratings and links. No samples or predictions |
| Words | `manifest.webmanifest`, `api/app.py` | "in England" | Would need changing at release |

## 4. Measured: Scotland on SwimSignal's network

Checked. A read-only script in my scratch space, run on this Mac with no network calls: the
`data-v1` river network (113,308,879 bytes) and the WFD lakes from the main checkout, the API
answer of 14:37 UTC, `RiverNetwork.snap_many` and `overflows._second_pass` as `build_overflows`
uses them, and `transport.locate_pin` and `transport.upstream_overflows` at the default 0.5 m/s.
"Scotland" is the outside-England shape north of 54.6 N.

| Measure | Scotland | England or GB, for comparison |
|---|---|---|
| Network links | 77,310: 61,576 inland river, 10,802 lake, 4,843 tidal river, 89 canal | 193,040 in all of GB |
| River length, inland and tidal | 51,555 km | not measured |
| Assets snapped within 750 m | 1,796 of 2,074 | |
| Second pass (1,500 m) | 22 by a matching river name, 64 by distance alone, 180 left out as marine, 12 not snapped | |
| Snapped, by form | 1,474 inland river, 362 tidal river, 26 lake, 20 canal | |
| First-pass snaps whose receiving water reads as marine | 220 (the first pass does not check names, as in England) | |
| Assets whose receiving water names a loch, kyle or voe | 113, of which 112 snapped. `overflows.MARINE` has none of the three words | |
| Rain cells (0.1°) | 415 for all assets: 9 requests of 50 | 1,589 for 13,821 overflows in the live click-anywhere build |
| Links within 60 km downstream of a snapped asset | 4,535 | 23,043 traced links |
| 0.25° squares with data | about 162 | 334 |
| 300 random inland river links: overflows within 60 km upstream | mean 0.36, median 0, 90th percentile 0, max 24; none at 93% | mean 2.5, none at 82% (roadmap, 3 October) |
| 300 random links of the 4,535: overflows upstream | mean 9.9, median 4, 90th percentile 26 | |
| Rows in a click-anywhere table | about 45,000 (9.9 × 4,535) | 414,091 |
| Luss Bay, Loch Lomond | Lake by centreline, no area. 15 overflows upstream, total weight 0.018 | |
| Dores, Loch Ness | Lake by centreline, no area. 8 upstream; CSO005667 discharges to Loch Ness 163 m away | |
| Loch Morlich | No monitored overflow upstream | |

*Inferred* from these: most of Scotland's river length has no monitored overflow upstream. The
overflows sit in the Central Belt, the east coast towns and along the Clyde, Forth and Tweed. A
Scottish launch is a set of rivers below towns, not the whole map.

## 5. What could be forecast, and what must abstain

### 5.1 With the pooled model only

*Inferred*, from the code (section 3) and the data (section 2):

1. **Each monitored overflow's daily spill chance**, today and four days ahead, for up to 1,882
   snapped Scottish Water assets. The rain inputs are the same as England's. The three covariates
   would be the fixed defaults, unless task S2 derives them from Scottish history (section 9).
2. **The pollution risk at a river point** within 60 km below monitored overflows: the same
   transport (0.5 m/s, 30-hour die-off, dilution by upstream network length), the same bands.
3. **"Right now"** from the live status through the same transport. This needs no spill model:
   Overflowing maps to discharging, Recent Overflow to a finished event with its end time, No
   Overflows to quiet, No Data Available to offline. Unlike the English feeds, each asset carries
   its own transmit time, so a stale monitor can be marked one by one. Decided: it goes live with
   the forecast, after the review, not before (section 10).
4. **Rain in the last 48 hours at the spot**, as shown in England.

### 5.2 What it must abstain from

Each item says why. "Checked" items rest on section 2 to 4; the rest are *inferred*.

| Abstain from | Why |
|---|---|
| The E. coli figure, everywhere in Scotland | Fitted on 1,548 samples at 32 English inland bathing waters, 2024 to 2026 (checked, `data/processed/ecoli_model.json`). No Scottish sample has been matched to it. On English lakes it showed no ranking skill (checked, `ecoli_scope` in `forecast.py`) |
| A level on lochs | No loch outline, so no area dilution (checked at Luss Bay and Dores). The lake path has no Scottish test. Show the upstream overflows' status instead, until task S6 |
| Tidal rivers, firths, sea lochs and the coast | No tide in the model, as in England. "Loch" names both freshwater and sea lochs, so names cannot sort them (checked: 113 assets name a loch, kyle or voe). Sort by OS form and SEPA's water-body polygons |
| "No sewage risk from monitored overflows" | 2,074 monitored locations against 3,674 storm and emergency overflows (checked; the counts are from different years). The English live feeds list 14,199 overflows (checked, 15:29 BST build); how close that is to every English storm overflow was not checked today. A Scottish trace that finds nothing has found only the monitored ones. The plain level must say so; the wording is decided in section 10 |
| A spill forecast for emergency overflows | They "should only operate in the event of sewer system failure and should not operate in response to rainfall" (Scottish Water, checked). 102 are EO alone, 59 more mixed. Show their live status only |
| Assets with no live data | 276 at 14:37 UTC, 203 of them under maintenance (checked). Same as England's offline state |
| Events Scottish Water cannot see between polls | Builds run a median 2.9 hours apart, at most 8.1 (`site.yml` comment). The feed keeps two events per asset, and 242 assets had two starts within 3 hours (checked). A third event in a gap is lost to the live history; the annual files fill it later |
| Monitors stuck on | Two assets read Overflowing for 218 and 682 hours (checked). England has the same risk; any rule for it should apply to both |
| River level, "too high to swim", flood alerts | All EA-only in the code (checked). Until task S7 |
| Water temperature | No source found |
| Algae | As in England, waiting on UKCEH's licence |

## 6. How it would be validated before release

`docs/EXPANSION-2026-10.md` sets the bar for any region: "positive held-out skill with
uncertainty and external review". The stages below meet it. Each stage writes its gate into the
script before it runs, so the gate cannot move after the results are seen.

**Stage A: hindcast on Scottish history (tasks S1 to S3).** Apply the model as it stands, trained on
United Utilities and not refitted, to Scottish Water's events with ERA5-Land rain, as
`scripts/train.py` does for 2025.

- Arms: the pooled model with the default covariates (what Scotland gets with no new code); the
  pooled model with covariates from Scottish events of the year before (counted by the EA's 12/24
  hour rule, so they match the training data); and, for overflows with two or more years, the
  calibration layer fitted on earlier years only.
- Baselines: each overflow's spill-day rate from earlier years, and where it has none, the rate of
  the other Scottish overflows that month. The flat rate of the test period, as the accuracy page
  shows it.
- Labels: a spill-day is a day with an event longer than 15 minutes 30 seconds, in every year and
  file, because the older files drop shorter events (checked). Whether United Utilities' training
  events used the same cut is not checked; S3 must find out.
- Scores: Brier score, skill against each baseline, log loss, AUC, reliability by band, wet and dry
  days apart, CSO and SSSO apart (EO left out), by local authority. At leads 0 to 3 for 2025 using
  archived forecasts, as `scripts/verify_leads.py` does.
- Uncertainty: resample overflows and weeks together (a cluster bootstrap, 2,000 draws), chosen
  before the run. Spills on the same day share the same rain and are not independent.
- Gate A (proposed): the lower end of the 95% interval of skill against the earlier-years baseline
  is above zero, overall and at leads 1 to 3, for the arm named for release before the run
  (proposed: the pooled model with Scottish covariates). The other arms are reported, not chosen
  from after the fact. If the gate fails, write it up in the accuracy page's terms and stop.

**Stage B: shadow live scoring (tasks S4, S5).** Poll the API each build, log forecasts for Scottish
overflows, score them with `verify_live` as a "Scottish Water" row, and publish nothing on the page.
Run through November 2026 to January 2027 at least.

- Gate B (proposed): skill above zero with its interval clear of zero over at least 200 scored
  spill-days, at leads 1 to 3. The same coverage rules as England's live scores.

**Stage C: outside review (task S9).** Send the reviewer the EXPANSION package plus the Stage A and B
results, the abstentions in section 5.2 and the proposed page words. EXPANSION already names a
possible reviewer at the University of Stirling; that invitation awaits Ethan.

**Stage D: the 2027 season.** If Scotland is released, the 2027 pre-registration (handoff task G,
deadline 30 April 2027) lists it as a separately labelled region with its own eligible sites.

The pollution risk at a river point cannot be checked against water samples in Scotland: the
designated waters are beaches and three lochs, and SEPA's samples there may not be republishable
(section 2.4). *Inferred:* that leaves the risk index in Scotland exactly as tested as in England,
where it is also not calibrated against samples; the spill forecast underneath it is what Stages A
and B test. The page should say that, as the English one does.

## 7. Costs and limits

Checked figures first, then *inferred* ones.

| Item | Size or count | Basis |
|---|---|---|
| Scottish Water live poll | 1 request a build, 2.96 MB, about 3 s, no compression | Checked |
| Builds | median 2.9 h apart, at most 8.1 h (13 to 28 Sep) | Checked, `site.yml` |
| Scottish Water history | Two files, 13.0 MB, once a year (next March 2027), off CI | Checked sizes |
| SEPA latest levels | 1 request a build for all 394 series: about 20 credits, so about 160 a day | Checked price list; *inferred* daily total |
| SEPA typical ranges | One-off: about 20 years of daily values per station, about 8 credits each, about 3,150 in all | *Inferred*, needs registration or the `Referer` route |
| Open-Meteo, spots | Only the cells of a Scottish spot's upstream overflows; at most 393 cells (8 requests of 50) | Checked count |
| Open-Meteo, click anywhere | 300 cells a build today, oldest first. Adding 415 cells takes the full cycle from about 5.3 to 6.7 builds, about 15 to 19 hours at the median gap, inside the 24-hour limit | *Inferred* |
| Open-Meteo, hindcast archive | 415 cells × 5 years = 208 requests of 10 cells. Each year is over two weeks, so each location-year counts as many calls; on the order of 50,000 calls | *Inferred*: Open-Meteo does not say how locations in one request count. Run over at least six days, off CI, never beside a build |
| `overflows.geojson` | 6.34 MB for 14,631 overflows today, about 433 bytes each, so about 0.9 MB more | *Inferred* from a checked size |
| Click-anywhere files | 13.65 MB today. Non-square files 2.0 MB, so about 35 KB a square; 162 squares, about 5.7 MB at most, likely less with a tenth of the rows | *Inferred* from checked sizes |
| `spots.json` | about 9 KB a spot today | *Inferred* from 945,945 bytes for 105 spots |
| GitHub Pages | 1 GB site, 100 GB a month | Roadmap, checked 3 Oct |

Limits that matter more than size:

- Neither `api.scottishwater.co.uk` nor `timeseries.sepa.org.uk` has been tried from a runner.
- SEPA's anonymous allowance is per IP, and runners share IPs. Use the `Referer` route or register.
- Never run the hindcast's rain download beside a build or another local build: one IP got
  Open-Meteo 429s and EA 403s before (handoff, section 5).

## 8. Questions to ask, with draft emails

None of the three emails has been sent. The addresses come from the sources in section 11: Scottish Water's
`opendata@` address is the contact on the data.gov.uk record for its map data; SEPA's are from its
data terms and its data catalogue.

### 8.1 Scottish Water (not sent)

To: opendata@scottishwater.co.uk
Subject: Reusing the near-real-time overflow API on a free swimming site

> Hello,
>
> I run SwimSignal (swimsignal.co.uk), a free, non-commercial website that forecasts sewage
> pollution risk for river and lake swimmers in England from the water companies' overflow data.
> We are planning a careful test of the same method in Scotland, using your near-real-time API and
> your published overflow event data. Before we publish anything, could you help with these
> questions?
>
> 1. Licence. The API page says the data is "provided under an open license" and must cite
>    Scottish Water. Is that the Open Government Licence v3.0, and what attribution wording do
>    you want?
> 2. Rate. We would make one request about every three hours, and never more than once an hour. Is
>    that acceptable? Would you prefer a different schedule, or a compressed response?
> 3. Hosts. Our builds run on GitHub Actions, which uses shared cloud addresses. Will the API accept
>    requests from there?
> 4. Ids. Does `ASSET_ID` in the API match the identifiers in the published event data for 2021 to
>    2025? Is `OVERFLOW_DISCHARGEID` stable, so that an event seen live can be matched to the same
>    event in the annual files?
> 5. Meaning. Is a "Recent Overflow" any event that ended in the last 48 hours? When an event is
>    later found to be false (a monitor triggered by vegetation, for example), is it removed from the
>    annual files?
> 6. `RAINFALL_HISTORY`. Where does this 48-hour rainfall come from?
> 7. 2026 data. Could the 2026 events for the newly monitored locations be shared before the March
>    2027 publication, for testing only?
>
> We would show the data with your credit and a link to your Overflow Map, keep monitors without
> data marked as such, and never present a quiet monitor as clean water. Happy to share a preview
> before anything goes live.
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 8.2 SEPA, bathing waters and data reuse (not sent)

To: DataRequests@sepa.org.uk
Subject: Reusing bathing water results and daily predictions on a free swimming site

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free, non-commercial website about sewage pollution risk for
> swimmers. It already lists Scotland's 90 bathing waters from your Bathing Water Points layer,
> with your credit and a link to each SEPA page. We would like to do more, and want to do it within
> your terms.
>
> 1. Samples. May we show each bathing water's latest sample results (E. coli and intestinal
>    enterococci, with the sample date) with attribution and a link back? Which terms cover the
>    results on bathingwaters.sepa.org.uk, and is there a machine-readable source we should use
>    (for example the Bathing Water Analysis CSV on Scotland's Environment web)?
> 2. Predictions. May we show the day's prediction for the 30 sites with electronic signs, credited
>    to SEPA, during the season? Is there a feed we should read rather than the web page?
> 3. Validation. We would like to test our method against your sample results, including past
>    seasons, without republishing them. Is that allowed under fair dealing for non-commercial
>    research, or do you need a request from us?
> 4. Freshwater sites. Are Luss Bay, Dores and Loch Morlich the only freshwater designated bathing
>    waters?
>
> 5. Overflow events. Your improving urban waters page offers "Overflow events reported to SEPA",
>    2020 to 2025, including PFI permits. Is it under the Open Government Licence? May we use it
>    to test our spill forecasts and publish the scores?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

### 8.3 SEPA, river levels and flood updates (not sent)

To: hydrometry-requests@sepa.org.uk (and ffw@sepa.org.uk for question 3)
Subject: Registering a free website for the time series API

> Hello,
>
> SwimSignal (swimsignal.co.uk) is a free website for swimmers. We would like to show the current
> river level near Scottish swim spots, as we do in England from the Environment Agency.
>
> 1. Access. Your documentation asks web products to register. Please register us, or tell us
>    whether the Referer-header route is the right one. We expect to request the latest 15-minute
>    level of about 400 series every one to three hours (about 20 credits each time), plus a one-off
>    history of daily levels to work out each station's usual range.
> 2. Usual range. Does SEPA publish a typical low and high level per station, like the Environment
>    Agency's typical range? How is the "State" on waterlevels.sepa.org.uk worked out?
> 3. Flood updates. Your data catalogue says access to the flood updates API is by request. May a
>    free website use it to tell swimmers when a flood alert or warning is in force nearby?
>
> Thank you,
> Ethan Buckley, SwimSignal (hello@swimsignal.co.uk)

## 9. PR-sized tasks, in order

Each is one PR against main. Scotland is in for 2027 (decided, section 10), so S1 can start once
Ethan approves downloading the files. S1 to S9 publish nothing on the site.

**S1. Import Scottish Water's event history (off CI).** A script that reads the two files of
section 2.2, keeps one row per event in the `edm_events` schema (`site_id`, start and end in UTC,
duration, source), and writes `data/processed/sw_events.parquet` plus a yearly summary per overflow.
Report in the PR: overflows and events by year and file, the share of `ASSET_ID`s that match the
API, events of 15 minutes 30 seconds or less by year. Tests on a small fixture cut from the files.
Needs Ethan's yes to download the files (13 MB).

**S2. Scottish covariates and rain archive (off CI).** Derive the three covariates per overflow and
year from S1's events, counted by the EA's 12/24 hour rule, with the year-before rule `train.py`
uses. Fetch ERA5-Land rain for the 415 cells, 2021 to 2025, spread over several days. Report the
cell count and calls used.

**S3. Hindcast (Stage A).** `scripts/hindcast_scotland.py`, with Gate A written in its docstring
before the first run. Writes `data/processed/scotland_hindcast.json`. The PR shows the tables of
section 6 and says pass or fail. If it fails, the next PR is a short write-up, and the rest stops.

**S4. Live adapter, shadow only.** Test the API from a runner first (a throwaway workflow on a
throwaway branch, deleted after; needs Ethan's yes). Then `src/dipcast/ingest/scottish_water.py`:
the status mapping of section 5.1, both events per asset into the live history keyed by discharge
id, a data state per asset from its transmit time, and the stuck-monitor rule. Behind a setting that
is off by default; polls and stores, publishes nothing. Tests from a trimmed copy of the 4 October
answer.

**S5. Shadow forecasts and scores (Stage B).** Forecast every snapped Scottish overflow each build
and score it with `verify_live` as its own company. Keep the scores in state or in a block of
`verification.json` that the page does not show. Extend `overflows.MARINE` (or better, use OS form
and SEPA's water bodies) so sea lochs are not inland.

**S6. Loch outlines.** Add SEPA's loch water bodies (catalogue: Open Government Licence; check the
geometry and attribution first) beside the EA's WFD lakes, so a Scottish loch gets the area term.
Tests at Luss Bay, Dores and a sea loch.

**S7. SEPA river levels.** After registration: the latest level per station, the pick by river
name as in `flows.station_pick`, a usual range from each station's history (method written in the
docstring), and the same stale rule. Then "too high to swim" and, if SEPA agrees, flood updates.

**S8. Calibration layer for Scotland.** Only if Stage A shows the calibration layer adds skill for
overflows with history.

**S9. Outside review (Stage C).** A document PR with the review package and the reviewer's dated
assessment, published with their consent.

**S10. Release.** Split `outside_england.json` so Wales stays blocked and Scotland opens; add Scottish
overflows to the click-anywhere data; credits for Scottish Water and SEPA on the terms page and in
the data files; the abstentions of section 5.2 in the page words, with the decided no-level line
of section 10; "right now" and the forecast together; Scottish places in the search; a
first set of hand-checked Scottish river spots in `spots.csv`; "England" changed only where it
stops being true. Screenshots at 320, 375 and 1440 px.

**S11. 2027 pre-registration.** Add Scotland to handoff task G as a separately labelled region.

## 10. Decisions and open questions

### Decided (4 October 2026)

Ethan's answers to the first version of this plan.

1. **Scotland is in for 2027.** In his words: "yes i want this app to work for people in scotland,
   and wales and ireland/northen ireland if its possible too". This answers the roadmap's open
   question 4. The Wales and Ireland plans are separate documents (branches `claude/wales-plan`
   and `claude/ireland-plan`).
2. **The plain level where a Scottish trace finds no monitored overflow** is the grey of no level,
   with the line "Many Scottish overflows have no monitor, so no level is given here". England's
   teal "No sewage risk from monitored overflows" is not used in Scotland.
3. **"Right now" and the forecast go live together, after the outside review.** The live status
   needs no spill model, but it is not released early on its own.

### For Ethan

Still open, and his to do or decide.

1. **Send the three emails** in section 8, or say who should.
2. **Approve the runner test** in S4: a throwaway workflow on a throwaway branch, deleted after.
3. **Approve downloading the two history files** (13 MB) for S1.
4. **Reviewer.** The University of Stirling invitation in EXPANSION is still waiting on him.

## 11. Sources and how each number was obtained

All read or run on 4 October 2026. Times are UTC.

Scottish Water:
- API page, read 14:37: https://www.scottishwater.co.uk/Help-and-Resources/Open-Data/Overflow-Map-Data
- API, one request at 14:37 and one with gzip at 14:38:
  https://api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time
- Published Overflow Data page, read 14:36:
  https://www.scottishwater.co.uk/Your-Home/Your-Waste-Water/Overflows/Overflow-Event-Data
- Document hub with the two files, read 14:37:
  https://www.scottishwater.co.uk/help-and-resources/document-hub/key-publications/urban-waters-improvements
- The two files, HEAD requests only, 14:37:
  https://www.scottishwater.co.uk/-/media/scottishwater/document-hub/key-publications/improving-urban-waters/cso-data/sw-reported-overflow-event-data-to-sepa-20212025--summary--v2-050826.xlsx and
  https://www.scottishwater.co.uk/-/media/scottishwater/document-hub/key-publications/improving-urban-waters/cso-data/scottish-water-non-reported-overflow-event-data-2022-2025-and-summary--310826.xlsx
- data.gov.uk, reported events (OGL v3):
  https://www.data.gov.uk/dataset/c885ee0b-22f9-4184-9a37-cec9b3207216/https-www-scottishwater-co-uk-your-home-your-waste-water-overflow-event-data-v2-published-05-08-26
- data.gov.uk, non-reported events (OGL v3):
  https://www.data.gov.uk/dataset/146660d4-485d-4aec-989a-560f2a64b694/www-scottishwater-co-uk-help-and-resources-document-hub-key-publications-urban-waters-improvements
- data.gov.uk, map data ("Licence: Not set", "Access constraints: Open Government Licence (OGL)",
  contact opendata@scottishwater.co.uk):
  https://www.data.gov.uk/dataset/57fff4dc-b8fd-4baa-a08c-3a5132359866/scottish-water-overflow-map-data
- ArcGIS copy, layer description at 14:50:
  https://services3.arcgis.com/SClJFeTjrkPbtMzT/arcgis/rest/services/Scottish_Water_Overflow_Map_Data/FeatureServer/0?f=json
- Water Briefing, 1 September 2026 (1,287 overflows, "from 6% to 30%"):
  https://www.waterbriefing.org/home/company-news/item/25979-scottish-water-expands-publication-of-2025-overflow-event-data-from-over-1000-additional-monitored-locations
- Environmental Standards Scotland, September 2024 (3,674 overflows in 2022/23):
  https://environmentalstandards.scot/our-work/our-analytical-work/storm-overflows-an-assessment-of-spills-their-impact-on-the-water-environment-and-the-effectiveness-of-legislation-and-policy/

SEPA:
- Time series API documentation and access limits:
  https://timeseriesdoc.sepa.org.uk/ and
  https://timeseriesdoc.sepa.org.uk/api-documentation/before-you-start/what-controls-there-are-on-access/
- KiWIS listing, one request at 14:41 (after one empty and one refused query while finding the
  parameter name):
  https://timeseries.sepa.org.uk/KiWIS/KiWIS?service=kisters&type=queryServices&datasource=0&request=getTimeseriesList&stationparameter_name=Level&ts_name=15minute&returnfields=station_no,station_name,station_latitude,station_longitude,ts_id,ts_name,coverage&format=json
- Water levels page: https://waterlevels.sepa.org.uk/
- Environmental data catalogue and licences: https://www.sepa.org.uk/environment/environmental-data/
- Data terms, version 3.1:
  https://beta.sepa.scot/about-sepa/access-to-information/guide-to-information/terms-and-conditions-of-use-of-data/
- Scotland's Environment web terms: https://www.environment.gov.scot/legal/terms-and-conditions/
- Bathing waters home and predictions: https://bathingwaters.sepa.org.uk/ and
  https://bathingwaters.sepa.org.uk/predictions/
- Bathing Water Points layer, all fields at 14:42 and five loch positions at 14:45:
  https://map.sepa.org.uk/server/rest/services/Open/Environmental_Monitoring/MapServer/1/query

Open-Meteo: https://open-meteo.com/en/terms, https://open-meteo.com/en/pricing,
https://open-meteo.com/en/docs/ukmo-api.

SwimSignal:
- Code at `be1c85e`: the files named in section 3.
- Live files of the 15:29 BST build: `spots.json` (`build.anypoint`, 13,649,110 bytes, 334
  squares, 1,589 rain cells), `overflows.geojson` (6,342,236 bytes, 14,631 features),
  `verification.json`. Sizes of the click-anywhere files from HEAD requests to
  https://swimsignal.co.uk/data/anypoint/.
- Section 4: a read-only Python script run with `DIPCAST_ROOT` on the main checkout's
  `data/processed/river_network.pkl` and `lakes.parquet`, random seed 0. It loads the network,
  snaps the 2,074 assets with `snap_many` (750 m) and `_second_pass` (1,500 m), counts links whose
  midpoint lies in the Scotland shape, follows `downstream_nodes` 60 km from each snapped asset,
  and traces 300 random links of each kind with `locate_pin` and `upstream_overflows`. It made no
  network calls.
- EA annual returns: the main checkout's `data/processed/annual_returns.parquet` of 11 September
  (companies and the most northerly row).
