# Source and coverage inventory, November 2026

Written 31 October 2026 for issue [#486](https://github.com/ethanbuckley/swimsignal/issues/486), the first bounded
work package. Machine-readable file: `data/research/source_inventory.v1.json`, to the contract in
`docs/SOURCE-INVENTORY-CONTRACT-v1.md`. Register row: "Overflow sources" in `docs/RESEARCH-RECOVERY-2026-10.md`.

Nothing was downloaded, no account was made, no enquiry was sent, and no model, page or cache changed. Labels:
**[checked 31 Oct]** a primary page read on 31 October 2026; **[doc]** taken from the cited repo doc and not re-read;
**[inferred]** my reading.

## In short

- **46 sources** are listed. 8 are ready to integrate, 12 already used (with something still unused), 18 need
  someone's permission, an account or a budget decision, 6 are unavailable and 2 are stale archives.
- **The six cheapest useful steps need nobody's permission.** All are open-licence observations or metadata:
  the EA annual returns' improvement columns, WINEP deadlines, Wessex Water's river E. coli samples, the EA's live
  ammonium and oxygen sondes, the EA coastal sample archive and Scottish Water's OGL event files.
- **No true overflow discharge volume or load exists in any open source.** The nearest are proxies: treated flow at
  works (no licence), EA gauged river flow (lagged archive) and population equivalent (no open table). Section 82
  water-quality monitoring, the source that would measure ammonia and oxygen at overflows, has no regulations and is
  not expected before about 2030 [checked 31 Oct: no regulations listed under s141DB].
- **No source gives the day an overflow upgrade was finished.** WINEP gives deadlines, the annual returns give
  "completed in year X", and company plans give planned years.
- **Regional observations come before regional forecasts.** Scotland has open event files now. Wales and Northern
  Ireland need the water companies' permission for event data. The Republic publishes no overflow data at all.
- **Four claims changed on recheck and four sources could not be re-read** (section 3). None changes a status bucket.
  The material one: the EA consents register's licence limits permitted use to one year.

## 1. How to read the ranking

Rank 1 is first to work on. User benefit (a dated measurement at or near a listed swim spot, a new region's
observations, or a fix to a known product gap) is weighed against cost (licence work, permission or account, fetch
size, new code). Sources that need someone else's permission rank below open ones of similar benefit, because the
next step is not ours. "Measurement kind" says plainly whether a row is a measurement, a proxy, a model field,
metadata or a directory of official labels. A cache "yes" means a local copy exists outside git (path, size and date
in the JSON, measured read-only on 31 Oct).

| Rank | Id | Source | Region | Kind | Licence | Status | Cache | Why this rank |
|---|---|---|---|---|---|---|---|---|
| 1 | `ea-annual-returns-improvement` | EDM annual returns: improvement, investigation and monitor-action columns | England | metadata | Open Government Licence v3 | ready | yes | Open, covers every English overflow, and the build already reads the layer; only three columns are dropped. |
| 2 | `ea-winep-pr24` | PR24 Water Industry National Environment Programme (WINEP) | England | metadata | Open Government Licence (catalogue field); attribution line says 'All rights reserved' | ready | no | One open file gives a dated regulatory deadline for 92% of improvement actions; small fetch, clear use, one licence wording to settle. |
| 3 | `wessex-river-samples` | Wessex Water Environmental Water Quality 2019-2025 | England (Wessex) | measurement | CC BY 4.0 | ready | yes | Real E. coli lab counts at three listed spots that have no other samples; open licence; already cached. |
| 4 | `ea-hydrology-sondes` | EA Hydrology API water-quality sondes | England | proxy | Open Government Licence v3 | ready | yes | Only live in-river water-quality feed found; open; but proxies, thin and moving coverage. |
| 5 | `ea-coastal-bathing-samples` | EA statutory E. coli samples at coastal and estuary bathing waters (Water Quality Archive) | England (coast) | measurement | Open Government Licence v3 | ready | yes | Fifteen times the inland sample count, open, and the register's named next coastal step; a few hundred small requests, off CI. |
| 6 | `scottish-water-event-files` | Scottish Water published overflow event data (reported to SEPA 2021-25; non-reported 2022-25) | Scotland | measurement | Open Government Licence v3 | ready | yes | New-region observations under OGL v3, already downloaded and parsed; the first Scottish step that needs nobody's permission. |
| 7 | `epa-ireland-bathing` | EPA Bathing Water Open Data API | Republic of Ireland | measurement | CC BY 4.0 | already used | no | The directory shows the latest result; the full 25,978-sample history since 2014 is open and unused, the cheapest new Irish observation. |
| 8 | `nrw-water-quality-archive` | NRW Water Quality Archive | Wales | measurement | Open Government Licence v3 | already used | yes | Open Welsh river, lake and coast samples back to 2000; partly cached; W10 used only 213 river rows. |
| 9 | `met-office-radar` | Met Office UK Radar Observations (AWS Open Data) | UK | measurement | CC BY-SA 4.0 | already used | yes | Already cached; ranked for its deadline: the bucket keeps two years, so November 2024 goes from about 21 Nov 2026. |
| 10 | `ea-edm-start-stop` | EDM Storm Overflow Start/Stop Detailed Data | England (ten companies, including Dŵr Cymru's English overflows) | measurement | Open Government Licence | already used | yes | Already the training labels; the 2026-to-August file adds months of labels for live checks and is not in the main checkout's cache. |
| 11 | `stream-company-layers-unfetched` | Company event layers on Stream not yet fetched (Anglian monthly from Apr 2025, Severn Trent 2025, Wessex 2025-26, Yorkshire EDM History Jan-Aug 2026) | England | measurement | CC BY 4.0 (as listed on 19 Oct) | ready | no | Open CC BY 4.0 event layers left unread; they fill 2026 months the EA files lack, at small cost. |
| 12 | `sepa-river-levels` | SEPA river levels (KiWIS time series API) | Scotland | measurement | Open Government Licence | ready | no | Open Scottish river levels; useful context for a Scottish observation page; registration advised for web use. |
| 13 | `opw-water-levels` | OPW waterlevel.ie | Republic of Ireland | measurement | CC BY 4.0 | needs permission | no | Open Irish levels and probable water temperature; a courtesy email to OPW comes first, which is Ethan's. |
| 14 | `hafren-dyfrdwy-2025` | Hafren Dyfrdwy Event Duration Monitoring 2025 | Wales | measurement | CC BY 4.0 | already used | yes | Small, open Welsh event file already used in the Wales hindcast; little left to gain until 2026 is published. |
| 15 | `stream-history-northumbrian-wessex-sww` | Earlier event histories: Northumbrian 2020-24, Wessex 2020-24, South West Jan 2025-May 2026, United Utilities 2023-25 | England | measurement | CC BY 4.0 (all four, as read on 19 Oct and in Sep for UU) | already used | yes | Already held and used; Northumbrian's layer sits on a personal account, so the cache is the durable copy. |
| 16 | `thames-discharge-api` | Thames Water Discharge to Environment API (alerts and status) | England (Thames) | measurement | Unnamed licence with CC BY 4.0's wording (portal terms, read 19 Oct) | already used | yes | Already polled live and cached back to Dec 2022; nothing new to fetch. |
| 17 | `ea-flow-gauges` | EA river flow (Hydrology API archive and flood-monitoring real-time) | England | measurement | Open Government Licence v3 | already used | yes | The only measured river flow; already used; archive flows lag and the dynamic dilution variant failed, so the next use needs a new mechanism. |
| 18 | `ea-bathing-water-inland` | EA bathing water samples and pollution risk forecasts (inland) | England | measurement | Open Government Licence v3 | already used | yes | Core truth already shipped to a contract; the next gain is 2027 lake samples, which arrive on their own. |
| 19 | `daera-bathing-waters` | DAERA Bathing Water Monitoring Points and results | Northern Ireland | directory | Open Government Licence v3 (Crown copyright) | already used | no | Already in the Northern Ireland directory; per-site sample tables are HTML only. |
| 20 | `nrw-bathing-waters` | NRW bathing waters (list, latest samples, pollution-risk forecasts) | Wales | directory | Open Government Licence v3 | already used | yes | Already in the Wales directory, with latest samples and coastal forecasts. |
| 21 | `sepa-bathing-waters` | SEPA bathing waters (list, results pages, daily predictions) | Scotland | directory | List: OGL v2. Results: SEPA terms v3.1 prohibit publishing. Predictions: none stated | needs permission | no | List already used; sample results and daily predictions carry terms that forbid or do not state publishing. |
| 22 | `southern-water-event-history` | Southern Water individual spill data 2017-2025 | England (Southern) | measurement | None stated; footer 'All Rights Reserved' | needs permission | no | Eight extra years at a company outside UU, but no licence; one permission email unlocks it. |
| 23 | `yorkshire-water-event-history` | Yorkshire Water individual stop/start events 2021-2026 | England (Yorkshire) | measurement | None stated | needs permission | no | Five extra years with current EA ids, but no licence stated. |
| 24 | `dwr-cymru-live-layer` | Dŵr Cymru live overflow layer (Spill_Prod view) | Wales and the English border | measurement | None; empty licence and access fields | needs permission | no | Would end 'no live feed' at three English spots and open Wales, but carries no licence; Ethan's email has no recorded reply. |
| 25 | `dwr-cymru-history` | Dŵr Cymru start/stop files 2020-2025 and annual EDM layers | Wales | measurement | Legal notice: personal download only, no reuse without prior written permission | needs permission | yes | The Welsh event history a full Welsh test needs; the legal notice forbids reuse without written permission. |
| 26 | `rivers-trust-edm-compilations` | The Rivers Trust EDM Storm Overflows compilations 2019-2025 | England and Wales | measurement | 'Open Government Licence' with attribution to The Rivers Trust, EA, Dŵr Cymru and Hafren Dyfrdwy | needs permission | no | Convenient England-and-Wales annual tables, but the OGL claim over Dŵr Cymru rows is the Rivers Trust's, not Dŵr Cymru's. |
| 27 | `scottish-water-live-api` | Scottish Water Overflow Map API (near real time) | Scotland | measurement | 'an open license for reuse', unnamed; data.gov.uk copy: licence 'Not set', access constraints 'OGL' | needs permission | yes | Live Scottish status with reuse wording, but the licence is unnamed and showing it waits on a passed hindcast anyway. |
| 28 | `sepa-overflow-events` | SEPA overflow events reported to SEPA 2020-2025 | Scotland | measurement | None stated on the page | needs permission | no | Fills the PFI overflows Scottish Water's files lack, but states no licence. |
| 29 | `nrw-river-levels` | NRW River Levels API | Wales | measurement | Open Government Licence | needs permission | no | Open licence but a subscription key is needed, which is an account; no typical range per station found. |
| 30 | `copernicus-amm15-currents` | Copernicus Marine NWSHELF_ANALYSISFORECAST_PHY_004_013 (AMM15) surface currents | UK shelf seas | model | Copernicus Marine licence (STAC 'proprietary') | needs permission | no | 1.5 km currents for coastal seasons 2024-26, but only useful after a coastal exposure stage passes; needs a free account. |
| 31 | `open-meteo-marine-sst` | Open-Meteo Marine API sea surface temperature (and SMOC currents) | Global | model | CC BY 4.0 data; free API non-commercial only | needs permission | no | Modelled sea temperature for 426 beaches; blocked by the free call budget and the D4 window, not by data. |
| 32 | `ukceh-lake-buoys` | UKCEH lake monitoring buoys (Cumbria, Loch Leven, Llyn Conwy) | England, Scotland, Wales (six lakes) | measurement | Raw buoy data: not stated; EIDC 2025 datasets: OGL | needs permission | no | Best lead for live Windermere and Esthwaite temperature; reuse terms need an outside contact. |
| 33 | `company-plan-layers` | Southern 'Clean Rivers and Seas Plan' investment layer; Wessex overflow_context and pr24_storm_overflow_improvements | England (Southern, Wessex) | metadata | None on any item | needs permission | no | Planned dates and sizes per overflow (Southern, Wessex), but plans say what should happen, and no licence. |
| 34 | `ni-water-edm` | NI Water storm overflow EDM data | Northern Ireland | measurement | Legal notice: personal, non-commercial use only; no public display without written approval | needs permission | no | The only Northern Irish spill data; yearly only, 20% monitored, and the legal notice forbids public display without approval. |
| 35 | `ni-water-consented-wastewater` | Northern Ireland Water - Consented Wastewater Results | Northern Ireland | measurement | License not specified | needs permission | no | New find: yearly treatment-works compliance, not overflows; licence not specified. |
| 36 | `company-tdv-flows` | Total daily volume (TDV) at treatment works | England | proxy | None stated | needs permission | no | Measured treated flow at works, the nearest thing to a load, but says nothing about network overflows; no licence. |
| 37 | `ea-consents-register` | Consented Discharges to Controlled Waters with Conditions | England | metadata | Environment Agency Conditional Licence | unavailable | no | Internal use only and no PE field; can never feed a published output. |
| 38 | `s82-continuous-wq-monitoring` | Section 82 (s141DB) continuous water quality monitoring | England | proxy | Not yet published | unavailable | no | The source that would give upstream/downstream ammonia and DO at overflows; not published before about 2030. |
| 39 | `uisce-eireann-overflows` | Uisce Éireann storm water overflow monitoring | Republic of Ireland | metadata | Open data page: 'most datasets' CC BY 4.0; none covers overflows | unavailable | no | No Irish overflow spill record is published at all. |
| 40 | `water-uk-plan` | Water UK National Storm Overflows Plan data | England | metadata | Water UK terms: no copying or use without written permission | unavailable | no | Terms forbid use without written permission, and the plan is superseded. |
| 41 | `pe-per-overflow` | Population equivalent per overflow (DWMP PDFs, Wessex RiverHub per works) | England | proxy | Not checked or none stated | unavailable | no | No open population-equivalent per overflow exists; the parked reopen rule is unmet. |
| 42 | `wessex-wq-live-test-layer` | Wessex Water river water quality live test layer (rwq_test_data) | England (Wessex) | proxy | None | unavailable | no | A three-row test layer with empty sensor fields; not a source yet. |
| 43 | `ukmcas-amm15-live` | Met Office UKMCAS AMM15 physics | UK shelf seas | model | Open Government Licence v3 | needs permission | no | A live 1.5 km feed with no archive, useful only after a coastal currents test passes; needs an order form. |
| 44 | `glofas-flow` | GloFAS river discharge (Open-Meteo Flood API) | Global | model | CC BY 4.0 via Open-Meteo; free API non-commercial | already used | no | Already checked; relative hydrologic state only, nearest cell often off-river. |
| 45 | `met-office-aws-legacy` | Met Office legacy AWS listing (uk-met-office) | UK | model | CC BY-NC-ND 4.0; derivatives internal use only | stale archive | no | Discontinued service under a no-derivatives, internal-use licence. |
| 46 | `ireland-river-networks` | EPA River Network Routes (2017) and DAERA River Segments (2010) | Island of Ireland | metadata | CC BY 4.0 (EPA); OGL (DAERA) | stale archive | no | Needed only for an Irish forecast, which waits on overflow data that does not exist; both networks are old. |

## 2. The top ten, and what each would deliver

1. **Annual returns improvement columns.** Keep three dropped columns in `annual_returns.parquet`. Then a dated page
   line per upstream overflow: "improvement completed in 2025, as the company reported". It is a company report for a
   year, not a verified completion. It missed Ilkley's work under way in 2025 [doc].
2. **WINEP deadlines.** One 6.9 MB XLSX. 92% of improvement actions join to a permit in the 2025 returns [doc]. A
   deadline line ("due by 31 March 2030 under the EA's programme") and a cross-check for option B before its 2 Dec
   read. The catalogue says OGL and the attribution line says "All rights reserved" [checked 31 Oct]; the same
   mismatch on the EA event files was settled as OGL [doc].
3. **Wessex Water river E. coli.** 4,123 lab results at 99 river points, 2019-2025, CC BY 4.0, already cached
   (`data/cache/wessex_wq/`). Warleigh Weir, Farleigh Hungerford and Tellisford Weir are listed spots with no EA
   samples. A dated sample view like `/samples.html` is the deliverable; a held-out check is secondary.
4. **EA sondes.** 15-minute ammonium, oxygen and turbidity, OGL. Twelve live ammonium stations within 5 km of a
   listed spot on 25 Oct, eight on Windermere becks [doc; live count not rechecked]. A sensor reading of a sewage
   marker, not a bacteria count. #403's test gate stays as written.
5. **EA coastal samples.** 32,874 statutory E. coli samples at 404 coastal and estuary bathing waters, 2022-26 [doc].
   No sample table is cached; only the point mapping is. About 170 small requests, off CI. The register names a
   coastal sample and coverage explorer as the first coastal step.
6. **Scottish Water event files.** OGL v3, 2021-25, about 1,287 overflows, cached and parsed
   (`data/raw/scottish_water/`, `sw_events.parquet`). A Scottish spill-history observation page needs no one's
   permission. The Scotland plan's hindcast has not run.
7. **EPA Ireland samples.** 25,978 results since 2014 under CC BY 4.0. The directory shows only the latest. A
   sample-history view, no forecast.
8. **NRW Water Quality Archive.** OGL, monthly, 2000 onwards. Two catchments cached. W10 scored 213 river rows; a
   dated Welsh sample view at Hay-on-Wye and Llandeilo is unused.
9. **Met Office radar.** Already cached (971 MB across two places). Ranked for its deadline: the bucket is a "2-year
   rolling archive" and its oldest day, 21 Nov 2024, was still listed on 31 Oct [checked 31 Oct]. A second backfill
   pass before about 21 Nov keeps November 2024.
10. **EA start/stop files, 2026 to August.** The labels the model trains on. The EA now packages them as yearly zips,
    updated 22 Oct [checked 31 Oct]. No English 2026 file was found in the main checkout's `data/raw/ea_events/`.

## 3. Recheck against primary sources, 31 October 2026

All reads were page reads (WebFetch) on 31 Oct 2026. URLs are in each JSON row's `recheck.urls`. No request went to
an API the builds poll (EA Hydrology readings, EA bathing water, Stream live feeds, Open-Meteo).

### Claims that changed

| Source | Was (doc) | Now (31 Oct) | URL |
|---|---|---|---|
| EA start/stop detailed data | Updated 24 Sep 2026; files one per company-year, including "Welsh Water Detailed Data 2026.xlsx" (WALES-PLAN 2.2) | Updated 22 Oct 2026; yearly zips "2024 / 2025 / 2026 year to August Detailed EDM Start-Stop Data.zip" plus "Technical Detail DSP October 2026 .docx". Licence still OGL | https://www.data.gov.uk/dataset/39ba1e24-69ca-4031-badf-e02649b74a7b/event-duration-monitoring-storm-overflow-start-stop-detailed-data |
| Copernicus AMM15 hourly currents | 29 Sep 2023 to 31 Oct 2026 (SEA-CURRENTS 4) | Dataset STAC: 29 Sep 2023 01:00 UTC to 7 Nov 2026. The end is the rolling forecast horizon; the start is unchanged. The product page says "2 Aug 2024 to 7 Nov 2026", which disagrees with the dataset record; unresolved | https://stac.marine.copernicus.eu/metadata/NWSHELF_ANALYSISFORECAST_PHY_004_013/cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT1H-i_202511/dataset.stac.json |
| EA consents register | "Internal or personal use", no publishing (PE-SIZE-TEST) | Also: "The period of permitted use is one year"; use restricted because of personal data; sublicensing only under matching written terms. Record updated 18 Sep 2026 | https://www.data.gov.uk/dataset/55b8eaa8-60df-48a8-929a-060891b7a109/consented-discharges-to-controlled-waters-with-conditions1 |
| Uisce Éireann open data | Eight datasets under CC BY 4.0 (IRELAND-PLAN 2.4) | "Most datasets are available under" CC BY 4.0; no per-dataset licence. Still no overflow dataset | https://www.water.ie/open-data |

The consents change matters most: an offline copy held for the 13 Oct test-only use should be dated, and re-obtained
or deleted after a year [inferred from the record's wording].

### Could not verify

| Source | What happened |
|---|---|
| Scottish Water Overflow Map API terms | HTTP 403 to an automated fetch (read on 16 Oct). The data.gov.uk copy still shows licence "Not set", access constraints "OGL", updated 4 Jun 2026 |
| Dŵr Cymru EDM page and legal notice | HTTP 403, as on 4 Oct |
| Thames Water API portal terms | The portal renders only with JavaScript |
| SEPA daily predictions | Out of season the table lists no sites, so "about 30 waters" could not be recounted |

Also not re-read: Yorkshire Water's site terms (`/legal/` returned 404), the EA sonde live station count and the
Water Quality Archive's one-year query limit (both need API calls), and the ten rows marked `not_rechecked` in the
JSON (held locally, refused earlier, or low rank).

### Unchanged, as checked

EA annual returns (OGL v3, modified 20 Oct); WINEP (OGL vs "All rights reserved", updated 18 Sep); Wessex samples
(CC BY 4.0); EA Hydrology and bathing-water and Water Quality pages (OGL v3); Southern Water (files 2017-19 to 2025,
no licence, "All Rights Reserved" footer); Yorkshire Water (files 2021 to 2026, no licence text); Scottish Water
non-reported file (OGL, record updated 9 Sep); SEPA KiWIS (OGL, 5,000 credits, register for web use); SEPA event
file (2020-25, no licence); NRW API portal (key needed, OGL); NRW Water Quality Archive (OGL, monthly, from 2000);
Dŵr Cymru live layer items (empty licence fields); Hafren Dyfrdwy 2025 (CC BY 4.0); Rivers Trust 2025 (OGL with
four-way attribution); Southern and Wessex plan layers (no licence); NI Water (500 EDMs, legal notice unchanged);
DAERA (OGL v3 Crown copyright); EPA bathing water (CC BY 4.0); OPW (CC BY 4.0, courtesy email, stations 00001-41000);
s141DB (in force only for specified purposes, no regulations, text up to date to 31 Oct); Met Office radar (oldest
day 21 Nov 2024 still present); Open-Meteo terms (non-commercial, 10,000 a day); Wessex RiverHub (sensors "not yet
available").

## 4. Coverage by what the issue asked for

- **Samples and sondes.** Ready: Wessex river samples, EA sondes, EA coastal samples. Used: EA inland bathing water,
  NRW archive (partly), EPA Ireland (latest only), Waterhead WET (register row). Not yet: section 82 (about 2030),
  Wessex's live sensors (test layer), UKCEH buoys (terms).
- **True discharge, load and flow.** None measures overflow volume or load openly. EA gauged flow is used and lagged;
  TDV has no licence; PE has no open table; the consents register cannot be published. The register's rule stands:
  a size or load variant reopens only with measured discharge or load, correctly linked.
- **Verified upgrade and improvement metadata.** Annual-return flags (company-reported, yearly) and WINEP deadlines
  are open. Company plan layers have no licence. Nothing records an actual completion day.
- **Historic spill feeds.** EA files 2024-26 and four company histories are held. Southern 2017-25 and Yorkshire
  2021-26 exist without a licence. Four open Stream layers for 2025-26 are unread.
- **Regional labels and directories.** Wales, Scotland, Northern Ireland and the Republic each have an official
  bathing-water directory in use. Event data: Scotland open (OGL files); Wales mostly permission-bound (Hafren
  Dyfrdwy and the EA's English-overflow files open); Northern Ireland permission-bound; Republic none.

## 5. Follow-on issues (suggested titles; not created)

The lead session decides which to open. Each names the JSON rows it acts on (`follow_on_issues` in the file).

1. Keep the annual returns' improvement, investigation and EDM-action columns in `annual_returns.parquet`.
2. Import PR24 WINEP storm-overflow deadlines and join them to overflows by permit.
3. Show Wessex Water river E. coli samples at Warleigh Weir, Farleigh Hungerford and Tellisford Weir.
4. Dated EA sonde readings (ammonium, oxygen, turbidity) on spot pages within 5 km of a live sonde.
5. Coastal sample and coverage explorer from the EA archive, 2022-2026.
6. Scottish spill-history observation page from Scottish Water's OGL event files.
7. Irish bathing-water sample history from the EPA API.
8. Second Met Office radar backfill before November 2024 is deleted (about 21 Nov 2026).
9. Fetch the EA 2026-to-August start/stop files and the unfetched Stream company layers for 2026 labels.
10. Permission requests for Ethan to send: Southern and Yorkshire event files, Dŵr Cymru live and history, Scottish
    Water API licence name, SEPA results and PFI file, NI Water. Drafts already exist in the Wales, Scotland and
    Ireland plans and in `docs/OVERFLOW-DATA-SOURCES-2026-10.md`.
11. Record the EA consents register's one-year permitted-use term and check the age of any offline copy.

## 6. The next decision

Which of the open, ready rows (ranks 1 to 6) goes first. My recommendation [inferred]: items 1 and 2 together, as
one data PR, because both feed the upgraded-overflows option B read on or after 2 Dec, and any addendum must be
dated before that read. Item 8 has the only hard deadline (about 21 Nov) and belongs to the radar row's owner.

## Sources

Every URL read is in the JSON (`recheck.urls` per row). Repo docs this inventory draws on:
`docs/OVERFLOW-DATA-SOURCES-2026-10.md`, `docs/EARLIER-SPILL-HISTORY-2026-10.md`, `docs/PE-SOURCES-2026-10.md`,
`docs/WALES-PLAN-2026-10.md`, `docs/SCOTLAND-PLAN-2026-10.md`, `docs/IRELAND-PLAN-2026-10.md`,
`docs/SOURCE-SCOTTISH-WATER-2026-10.md`, `docs/SEA-CURRENTS-SCOPING-2026-10.md`, `docs/SONDE-SIGNAL-TEST-2026-10.md`,
`docs/COASTAL-SEA-TEMPERATURE-BRIEF-2026-10.md`, `docs/MET-OFFICE-DATA-2026-10.md`,
`docs/LAKE-TEMPERATURE-SENSORS-2026-10.md`, `docs/PE-SIZE-TEST-2026-10.md`.
