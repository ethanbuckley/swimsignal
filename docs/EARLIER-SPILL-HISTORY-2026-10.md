# Earlier spill history: what exists before 2024, fetched and checked

Written 19 October 2026. Review tasks D3 and D8 (`docs/REVIEW-2026-10-16.md`, section 4 items 1, 2
and 7). Data only: no model was trained or scored, and nothing on the site changed except one credit
line on the terms page. "Measured" means fetched or counted here; "inferred" is marked.

## Why

The neural challenger lost to the boosted model (PR #239), and every run overfitted after one pass.
The inferred cause is that training had one year of weather. The boosted model's per-overflow
offsets were also fitted on one year (PR #251). Both need more years of event-level truth: one row
per discharge, with a start and a stop, so that days can be labelled. Annual returns give only
yearly totals and cannot label days.

## The answer

Event-level records before 2024 are openly available for **three companies besides United
Utilities**: Northumbrian Water from 2020, Wessex Water from 2020, and Thames Water from April 2022.
Wessex was not in the review's list; it turned up in a search of every company's ArcGIS services.
No open event-level record before 2024 was found for Anglian, Severn Trent, South West, Southern or
Yorkshire.

## Company by year

What is now held at event level, off the repo in `data/processed/` (git-ignored). Counts are events
after the reader's filters (an unreadable start, or a negative length, or one over 60 days, drops a
row; 7, 12 and 6 rows in the three new layers).

| Company | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| Northumbrian | **82,186** | **100,022** | **66,407** | **116,994** | **106,346** + EA | EA | none |
| Wessex | **262,733** | **174,019** | **143,235** | **354,362** | EA (+ Wessex's own, for ids) | EA | not fetched |
| Thames | none | none | **API from Apr** | **API** | EA + API | EA + API | API |
| United Utilities | none | none | none | 352,911 | 215,468 + EA | 175,356 + EA | none |
| South West | none | none | none | none | EA | EA + **138,372** (Jan to Nov) | **191,900** (Jan to May) |
| Anglian | none | none | none | none | EA | EA | not fetched |
| Severn Trent | none | none | none | none | EA | EA | none |
| Southern | none | none | none | none | EA | EA | none |
| Yorkshire | none | none | none | none | EA | EA | not fetched |

Bold is new in this task. "EA" is the Environment Agency's start/stop file for that year, already
read by `scripts/import_ea_events.py` (events per company-year in
`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`, step 1). United Utilities' Stream layers were already
held (`edm_events.parquet`). Thames API counts are in the Thames section below.

"Not fetched" means an open layer exists but was left alone because the EA files or nothing in this
task needed it: Anglian's monthly layers from April 2025, Severn Trent's 2025 layer, Wessex's 2025
and 2026 layers, Yorkshire's "Event Duration Monitoring History" (January to August 2026 only), all
CC BY 4.0 on Stream or the company's own ArcGIS (measured: listed and counted on 19 Oct).

**Still missing, plainly:** 2020 to 2023 for Anglian, Severn Trent, South West, Southern and
Yorkshire; 2020 to 2022 for United Utilities; 2020 to March 2022 for Thames. Nothing before 2020 for
anyone. South West Water's December 2025 is missing from its Stream layer (the EA file has it).

## Each source

### Northumbrian Water, 2020 to 2024 (D3)

- **Layer:** `EDM_Spill_Data_Northumbrian_Water_2020_2023`, item 2fae6e66f9074272aaf67d3b7b4c7211,
  title "EDM Spill Data Northumbrian Water", on Stream's ArcGIS. **Still there on 19 Oct 2026**:
  public, created 13 Mar 2025, item modified 12 Dec 2025, data last edited 28 May 2025.
- **Owner:** an individual's account inside the Stream organisation, not a company account like
  United Utilities' (`UnitedUtilities3`) or Severn Trent's (`SevernTrent2`). This is what the review
  flagged. Inferred risk: the item could go if that account is removed. The raw read is kept in
  `data/cache/edm/Northumbrian_Water_2020-2024.parquet`, so the data survives that.
- **The service name is out of date.** It says 2020_2023, the snippet says "from 2020 to-date", and
  the layer runs to 31 Dec 2024 (measured per year: 82,189, 100,022, 66,408, 116,995 and 106,348
  events, summing to the layer's 471,962).
- **Read:** 471,962 rows, equal to the layer's count on 16 Oct and 19 Oct, 471,962 distinct object
  ids. 471,955 kept.
- **Fields:** `Monitor_Unique_ID` (the annual returns' id), outfall latitude and longitude, and
  `Event_start` / `Event_end` as `dd/mm/yyyy hh:mm` text. No site name, no watercourse.
- **Time zone (measured):** the text is GMT all year. Every one of the EA's 106,346 Northumbrian
  starts for 2024 has a Stream start at the same overflow 0 or 1 minute earlier. That holds in the
  summer-time months as in winter: 45,566 of 45,566 GMT-period starts and 60,780 of 60,780 BST-period
  starts. The minute is floored, as the layer drops the seconds. `edm_events.dmy_times` reads it so,
  with a test.
- **Ids join:** all 1,346 overflows with a 2024 event are in the EA file and the annual returns.
  For 2020 to 2023, 99.4 to 99.5% of ids are in the annual returns of some year. Same-year joins
  look worse for 2021 and 2022 (817 and 820 of about 1,250) because those years' returns have no
  id on about 550 rows.
- **Event definition:** median event 15 minutes, 43% under 15 minutes. The EA's 2024 file gives
  6 to 15 minutes and 45 to 64%.

### Wessex Water, 2020 to 2023 (found here)

- **Layer:** `Wessex_Water_Event_Duration_Monitoring_2020_23_view` on Wessex Water's own ArcGIS,
  item 4fca49fcd50e44928c23f8400f6e6322, owner `WessexWaterData`. The licence reads "Wessex Water
  Event Duration Monitoring 2020-2023 © 2025 by Wessex Water is licensed under CC BY 4.0".
- **Read:** 934,361 rows, equal to the layer's count, all object ids distinct; 934,349 kept. Per
  year 262,738, 174,024, 143,235 and 354,364.
- **Fields:** the Stream schema (`SiteId`, `SiteName`, outfall position, `EventStart`, `EventEnd`
  as dates). `EventVerified`, `EventId`, `Duration` and `PermitReference` are empty on every row.
- **Ids are Wessex's own** ("17385C"), in neither the annual returns nor the Stream ID lookup.
  Wessex's 2024 layer (447,277 rows, CC BY 4.0, read only for this) uses the same ids, and the EA's
  2024 file has the same events under the annual returns' `WXW` ids. So the crosswalk is built by
  matching events (`edm_events.crosswalk_by_events`). Each Wessex id goes to the `WXW` id with the
  most events starting in the same minute, if those are at least 80% of the events of both.
  - **Result:** 1,098 of 1,153 Wessex ids map one to one, no `WXW` id used twice. The 55 unmapped
    ids hold 0.6% of the 2024 events. Written to `data/processed/wessex_id_crosswalk.csv`.
  - **Why both ways:** asked one way only, 48 `WXW` ids received two Wessex ids. These were ids
    with a single 2024 event that shared its minute with a storm's start elsewhere, a median 40 km
    apart.
  - **Position check (independent of times):** the Wessex outfall position and the annual returns'
    position of the mapped id are a median 2 m apart. 99% are within 432 m, and 3 of 1,098 are more
    than 2 km apart.
  - **Applied to 2020 to 2023:** 930,598 of 934,349 events (99.6%) carry an annual-returns id.
    Per year 784 of 827, 873 of 926, 947 of 996 and 1,055 of 1,117 overflows (94 to 95%). The rest
    keep Wessex's own id.
- **Event definition:** median event 2.2 minutes, 83% under 15 minutes, as in the EA's 2024 file
  (2 minutes, 84 to 85%).

### South West Water, January 2025 to May 2026 (D3)

- **Layer:** `South_West_Water_Storm_Overflow_EDM_Monthly` on Stream, item
  8ae355c11a5d443a9085004410246e93, licensed CC BY 4.0, item modified 1 Jul 2026.
- **Read:** 330,278 rows, equal to the layer's count on 16 Oct and 19 Oct; 330,272 kept. 152 rows
  carry pre-2024 ids, which the reader maps to current ones.
- **Not pre-2024.** It starts on 1 Jan 2025 and runs to 31 May 2026, not to January 2026 as the
  review said. **December 2025 has no events** (measured per month: 29,072 in November, 0 in
  December, 72,207 in January 2026).
- **`eventVerified` is "TRUE" on all 330,278 rows**, so it separates nothing.
- **What it adds:** January to May 2026, which no EA file covers for South West Water yet.

### Thames Water alert stream from April 2022 (D8)

- **Key: none needed** (measured). `GET https://api.thameswater.co.uk/opendata/v2/discharge/alerts`
  returned HTTP 200 with data and no credentials on 19 Oct 2026 12:50 UTC, as did `/discharge/status`.
  The portal's API specification lists no security scheme.
- **How far back (measured):** the portal's overview says the alert stream "provides historical
  event data from April 2022", with "specific rules governing the visibility" of events before the
  30 December 2022 go-live, which it does not spell out. A request for January to March 2022 returns
  nothing; April 2022 returns rows. The developer write-up's April 2022 is confirmed.
- **Licence (read in full on the portal's terms page):** "a worldwide, royalty-free, perpetual,
  non-exclusive licence to use the Information", free to share and adapt, on condition of
  attribution, a link to the licence, saying if changes were made, and no added restrictions. The
  wording is CC BY 4.0's, but the licence is not named. Its table names "Storm discharge to
  environment alerts" as the information covered. Every API answer links that page as its
  `licence`. One sentence elsewhere on the page says portal access is "for your use only" unless
  agreed in writing. Inferred: that governs access to the portal, not reuse of the information,
  which the licence grants.
- **Parameters (from the spec):** `offset`, `limit` (at most 1,000: `limit=5000` returns nothing),
  `dateStart` and `dateEnd` (inclusive days), and location and alert-type filters. Newest first.
  Rate guidance is 5 requests a second. Times are UTC. Alert types are "Start", "Stop", "Offline
  start" and "Offline stop".
- **Read:** THAMES-READ
- **Ids:** THAMES-IDS

## Agreement checks, counted as spill-days per overflow

A spill-day is any UTC day an event touches at an overflow (`features.spill_days`, the model's
label). The comparisons use `scripts/compare_event_sources.py`, the way
`docs/NINE-COMPANY-MODEL-TEST-2026-10.md` compared United Utilities' Stream and EA files. Those
figures are repeated here for context.

| Check | Overflows (both / only first / only second) | Spill-days shared | Only first | Only second |
|---|---|---|---|---|
| Northumbrian 2024, Stream vs EA | 1,346 / 0 / 0 | 40,397 | 0 | 0 |
| Wessex 2024, Wessex's own (crosswalked) vs EA | 1,098 / 0 / 53 | 44,422 | 0 | 258 (3 on shared ids) |
| South West Jan to Nov 2025, Stream vs EA | 1,157 / 23 / 9 | 34,325 | 634 | 255 |
| South West Dec 2025 | | | 0 | about 11,700 |
| United Utilities 2024, Stream vs EA (from the nine-company test) | | 76,958 | 846 | 1,333 |
| United Utilities 2025 | | 61,764 | 0 | 0 |
| Thames 2024, API vs EA, grid ids | THAMES-GRID-ROW |
| Thames 2024, API vs EA, event ids | THAMES-EV-ROW |

What they show (measured unless marked):

- **Northumbrian's 2024 Stream layer and the EA file are the same record**: identical events,
  overflows and days. Inferred: the 2020 to 2023 rows come from the same system as the EA's
  2024 file, so they should be as reliable as that file. No EA file for 2020 to 2023 exists to
  test this.
- **Wessex 2024 agrees**, but partly by construction. The crosswalk needed matching starts, so
  close agreement on mapped ids is expected. The 53 EA ids Wessex's layer does not reach hold 255
  spill-days, 0.6% of the year. The independent check is the position agreement above.
- **South West 2025 agrees on 98% of days** where both have the month. The EA file adds December,
  which the Stream layer lacks.
- **Thames:** THAMES-AGREE

## Coverage against the annual returns

Per company-year: overflows with at least one event in the record, against the annual returns'
count of overflows with an EDM reporting (`has_data`) and with at least one counted spill.

| Company | Year | Overflows with an event | Returns: EDM reporting | Returns: spilled |
|---|---|---|---|---|
| Northumbrian | 2020 | 1,232 | (returns held from 2021) | |
| Northumbrian | 2021 | 1,251 | 1,440 | 1,261 |
| Northumbrian | 2022 | 1,256 | 1,463 | 1,255 |
| Northumbrian | 2023 | 1,381 | 1,546 | 1,382 |
| Northumbrian | 2024 | 1,346 | 1,551 | 1,346 |
| Wessex | 2020 | 827 | (returns held from 2021) | |
| Wessex | 2021 | 926 | 1,048 | 923 |
| Wessex | 2022 | 996 | 1,182 | 993 |
| Wessex | 2023 | 1,117 | 1,295 | 1,118 |
| South West (Stream) | 2025 | 1,180 | 1,357 | 1,179 |
| United Utilities | 2023 | 1,944 | 2,147 | 1,944 |
THAMES-COVERAGE

In every company-year the overflows with an event match the returns' count of overflows that
spilled to within ten. Overflows that never spilled have no events, so the gap to "EDM reporting"
is expected. The EA's 2024 and 2025 files show the same pattern for all nine companies (for
example Anglian 2024: 1,283 with an event, 1,284 spilled).

## Licences and credits

| Source | Licence | Credit |
|---|---|---|
| Northumbrian Water EDM spill data 2020 to 2024 (Stream) | CC BY 4.0 ("Licensed under CC BY 4.0") | EDM Spill Data Northumbrian Water, Northumbrian Water, via Stream, CC BY 4.0 |
| Wessex Water EDM 2020 to 2023 and 2024 (Wessex Water's ArcGIS) | CC BY 4.0 | Wessex Water Event Duration Monitoring 2020-2023 (and 2024) © 2025 by Wessex Water, CC BY 4.0 |
| South West Water EDM Monthly (Stream) | CC BY 4.0 | South West Water Storm Overflow EDM Monthly © 2025 by South West Water, CC BY 4.0 |
| Thames Water alert stream (Open Data API) | Thames Water API Portal terms: share and adapt with attribution (CC BY 4.0's wording, unnamed) | Thames Water Utilities Limited, discharge alert stream, used under the Thames Water API Portal terms of use |

The credits are in `edm_events.HISTORY_CREDITS`, `edm_events.WESSEX_2024_CREDIT` and
`thames_alerts.CREDIT`, in the README Data table, and on the terms page, which says the data is held
for testing and not used in any forecast.

## Kept out of training on purpose

The new feeds are in `config.EDM_HISTORY_FEEDS`, not `config.EDM_EVENT_FEEDS` as the review
suggested. `train.py` builds a year of site-days for every year it finds in `edm_events.parquet`,
and `validate_ecoli.py` and `make_lake_spill_ratio.py` read the same file. A feed added there would
add 2020 to 2022 to the model's training at the next refit. Each history goes to its own
`stream_events_<company>.parquet` or `api_events_thames_water.parquet` instead. Using them is a
model change for a later, pre-stated test (D2's successor, or the neural-net retry).

## Requests that would help (drafts for Ethan, not sent)

The five companies with nothing open before 2024 could be asked, under the Environmental Information
Regulations 2004, for event-level EDM records for 2020 to 2023. Yorkshire Water's own layer
description says it publishes event data to cut down such requests, which suggests the companies
hold these records and expect to be asked (inferred).

> Subject: Request for storm overflow EDM start and stop records, 2020 to 2023
>
> Dear [company] Environmental Information team,
>
> Under the Environmental Information Regulations 2004, I am requesting the event duration
> monitoring records for all your storm overflows for 1 January 2020 to 31 December 2023: one row
> per activation, with the overflow's Unique ID (as in the Environment Agency's annual returns), the
> start time and the stop time, in the same layout as the Environment Agency's "Event Duration
> Monitoring - Storm Overflow - Start/Stop Detailed Data" files for 2024 and 2025.
>
> A CSV or spreadsheet is ideal. If you already publish these records, a link would be enough. I
> would like to reuse the data under an open licence (CC BY 4.0 or the Open Government Licence),
> credited to [company], in a free, non-commercial forecast of sewage risk at swimming spots
> (swimsignal.co.uk).
>
> Thank you,
> Ethan Buckley

Recipients: Anglian Water, Severn Trent Water, South West Water, Southern Water, Yorkshire Water,
and United Utilities (for 2020 to 2022). One optional note to Northumbrian Water: ask whether the
2020 to 2024 layer could move to the company's Stream account, so it does not depend on one
person's account.

## How to reproduce

All off CI, from a checkout with `data/processed/annual_returns.parquet` and the EA parquets:

    uv run python scripts/import_stream_events.py      # Northumbrian, Wessex (+ crosswalk), South West
    uv run python scripts/import_thames_alerts.py      # Thames, about 1,700 requests
    uv run python scripts/compare_event_sources.py data/processed/stream_events_northumbrian_water.parquet \
        data/processed/ea_events_northumbrian_water.parquet --year 2024

The raw reads are cached in `data/cache/edm/` and `data/cache/thames_alerts/`. The import script
stops if a read's row count differs from the layer's or repeats an object id.
