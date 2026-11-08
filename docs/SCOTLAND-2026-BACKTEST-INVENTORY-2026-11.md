# Scotland trial: can 2026 records replace Gate B's wait? 8 November 2026

Asked by the session that ran PR #638, whose candidate table listed "Scotland trial, Gate B: possibly Scottish
Water's 2026 records (not checked whether published)". Rule: [Backtest instead of waiting](RESEARCH-WORKFLOW.md).

## Answer

**No, not now.** No complete record of Scottish Water's 2026 overflow events is published or held anywhere this
project can use. The first will be Scottish Water's annual file for 2026, planned for March 2027. So no protocol was
written and no score was computed. No 2026 outcome was read beyond counting the rows of one saved API answer.

**A route that can run now uses older years, not 2026.** The Internet Archive keeps earlier editions of Scottish
Water's annual files, with events from 2017 to 2020. With one of them, the trial's frozen model and map could be
scored on 2021, a year neither was fitted or checked on. That needs Ethan's yes to download two files (section 5).

**Checked** means read or run on 8 November 2026. *Inferred* means a deduction no source settles.

## 1. The forecast a backtest would test

| Part | File and hash | Fitted on |
|---|---|---|
| Spill model | `data/processed/spill_model.pkl`, MD5 prefix `808da63d`, SHA-256 `faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e`, committed 13 Sep 2026 (8ac835f1) | United Utilities 2023-25 (the map file's `model` field). No Scottish and no 2026 data |
| Scotland's map | `data/processed/scotland_calibration.json`, SHA-256 `447a02a1556fd811719bc49776131ef1a2e386020ad5449030624755b172811d`, a = 0.449, b = 0.750 | Scottish set G 2022-24. Rule 4e6734b1 and result 42efc002, both 1 Nov 2026. Checked on 2025, seen in aggregate |
| Covariates | `data/processed/sw_covariates.parquet`, SHA-256 `1ee52787be8b78fda1d7f44cee31deb0f35a0f3c9c1d9d9c31317c63c5f3e672`, committed 11 Oct 2026 (d0656520) | Counts of 2021-25. A 2026 forecast uses 2025's count |

All three hashes checked on the committed files. The main checkout's spill model and covariates are byte-identical; it has no copy of the map.

## 2. Which 2026 days are unused

| Period | Status |
|---|---|
| 1 Jan to 10 Oct 2026 | Unused. Nothing in section 1 was fitted, chosen or checked on 2026 |
| 11 to 31 Oct 2026 | Seen. The shadow scored these days with England's calibration, and the trial record of 1 Nov reports them (Gate B "not passed", five pieces, every interval crossing zero). The map was not chosen from them; its rule names its years |
| 1 Nov 2026 to Jan 2027 | Gate B's window. Frozen. Not to be read early |

## 3. Where 2026 outcomes could come from

| Source | What it holds for 2026 | Licence | Usable? |
|---|---|---|---|
| Scottish Water's annual files ("Published Overflow Data") | Nothing. The local copy, `sw_events.parquet`, holds 179,572 events from 1 Jan 2021 to 31 Dec 2025 (2021: 10,712; 2022: 19,517; 2023: 24,906; 2024: 24,396; 2025: 100,041). data.gov.uk lists only the two 2025 editions (checked, CKAN API) | OGL v3 ([source note](SOURCE-SCOTTISH-WATER-2026-10.md)) | Not until 2026 is published: "In March 2027, we plan to publish annual available overflow event data for 2026 for all locations shown on the map" |
| Near-real-time API | The latest and the previous event per asset. No query for past dates | "an open license for reuse", unnamed | No. See the row count below |
| Scottish Water's ArcGIS copy | Queried 8 Nov: one layer, 2,014 rows, one per asset, the same latest and previous events. No archiving, no time settings. Data last edited 6 Nov 22:04 UTC | "free to use, share, and adapt", with attribution | No history |
| SwimSignal's own polls (`ingest/scottish_water.py`) | Every polled event since 11 Oct 2026, in the build's Actions cache only. Not in the state release (its assets checked) and no local copy (checked) | As the API | No: 11-31 Oct is seen, and November on is Gate B's window |
| sewagedata.co.uk (code: GitHub `Deveroonie/SewageData`) | A third party polls the same API. Its code dates from 3 Mar 2026; it stores events in its own database and serves them per asset. Its fetcher commit of 13 Oct 2026 starts recording events "already finished when first seen" and recovering "the previous event from Scottish Water's *_PREVIOUS fields" | Code MIT. No data licence stated | No. *Inferred:* before 13 Oct its record misses events that began and ended between its polls. Using it would also need its maintainer's agreement. No request was made to its API |
| Top of the Poops | Its Scottish Water page says its 2025 and 2026 numbers do not include Scottish Water (read by a page-text fetch, not in a browser) | | No |
| Internet Archive | No capture of the API's URL since 2025 (CDX query) | | No |
| SEPA | Receives the annual returns. Its published file covers 2020-25 | Unanswered; its reuse permission is pending | No. No contact made |

**Row count of the saved API answer** (`data/raw/scottish_water/near_real_time.json`, fetched 4 Oct 2026, 2,074
assets). Event starts in 2026, latest and previous together, by month: Jan 20, Feb 31, Mar 27, Apr 43, May 25,
Jun 113, Jul 97, Aug 167, Sep 1,460, Oct 718. In 2025 the annual files hold 100,041 events, about 8,300 a month.
*Inferred:* each asset keeps only its two most recent events, so the answer holds a small and recent-biased fraction.
It cannot stand in for a record.

## 4. When a 2026 backtest could run

- **Data:** Scottish Water's 2026 file, planned for March 2027. Then 1 Jan to 10 Oct 2026 is unused, if the model and
  map are unchanged. Leads 1 to 3 would need Open-Meteo's archived forecasts for 2026, as Gate A used for 2025
  (*inferred* available; not checked for these cells).
- **To keep it a frozen-model test:** push the protocol before the file is downloaded, so by the end of February 2027.
- **If the spill model changes first:** the trial switches itself off and needs a new map. 2026 would test the new
  pair only if the new map is not fitted on 2026.
- **Sooner:** question 7 of the draft email in the [Scotland plan](SCOTLAND-PLAN-2026-10.md), section 8.1, asks
  Scottish Water to share 2026 events before March 2027. Sending it is Ethan's.

## 5. A route that can run now: 2021, from archived editions

**Established (checked):**

- The Internet Archive holds earlier editions of the reported-to-SEPA file, for example 2017-2021 (captured 19 Dec
  2022, 3,817,619 bytes) and 2020-2024 (`…SEPA-20202024--Summary---280325-v1.xlsx`, captured 7 Oct 2025,
  5,033,567 bytes). Editions for 2018-22 and 2019-23 are there too. The non-reported file starts in 2022.
- 2021's events are already local. 133 overflows have a 2021 count; 95 are eligible by Gate A's rules
  (`SCOTLAND-HINDCAST-2026-11.json`, coverage).
- Gate A's set G starts in 2022 and the map was fitted on 2022-24. No 2021 day was ever scored. 2021's annual
  counts were used, as inputs: the covariates and earlier-years baseline of 2022's rows. A record must say so.
- Missing for 2021: the 2020 counts (its covariates) and 2020's events (its earlier-years baseline). Both are in
  the archived editions.
- Rain: 2021's 133 overflows sit in 66 rain cells. 48 of 66 cells have 2021 cached, none has 2020. About
  (18 + 66) × 26.1 ≈ 2,190 Open-Meteo calls, by the hindcast's own count.

**What it would show:** the frozen model and map on a year neither saw, with Gate A's metric and baseline. That
fills the trial's main gap: the map's only check, on 2025, used a year already seen in aggregate.

**What it would not show (*inferred* limits):** lead 0 only, with the rain that fell (ERA5-Land), not issue-time
forecasts. Whether archived forecasts exist for 2021 is not checked. Reported overflows only, about 95, larger than
the trial's 1,485. Not the live feed's behaviour. Gate B would still run, as monitoring.

**Work needed:** a loader for the older layout (not opened), and `FIRST_YEAR` in `ingest/sw_covariates.py` and
`FIRST_RAIN_YEAR` in `scripts/hindcast_scotland.py` moved back for the test only. 2018-20 would add roughly 1,700
calls a year (*inferred*, if the same cells).

**Licence:** the 2020-24 edition was published under the same data.gov.uk record that names OGL v3 now
(`c885ee0b…`). The 2017-21 edition's licence is not checked.

## 6. Continuation

| Field | Content |
|---|---|
| Identity | SCOT-TRIAL. This record; no code changed |
| Evidence | No 2026 outcome record exists. Nothing scored |
| Stage | Unchanged: limited forecast, labelled trial. Gate B window runs to January 2027 |
| Next deliverable | A frozen-model backtest of the trial's model and map on 2021, protocol pushed before the download. Done when it is scored and recorded |
| Milestone and budget | On Ethan's yes to download the two archived files (about 8.9 MB). About 2,190 Open-Meteo calls, capped at 1,000 a day while D4 runs (to 19 Nov) |
| Also | Protocol for a 2026 backtest pushed by the end of February 2027, before Scottish Water's 2026 file |
| Release route | Unchanged. The trial switch stays Ethan's. A pass would support the existing limited release and change no level or threshold |

## 7. Sources

All checked on 8 November 2026.

- data.gov.uk, Scottish Water's records: https://ckan.publishing.service.gov.uk/api/action/package_search?fq=organization:scottish-water
- ArcGIS service list and layer: https://services3.arcgis.com/SClJFeTjrkPbtMzT/arcgis/rest/services/Scottish_Water_Overflow_Map_Data/FeatureServer/0?f=json
- Internet Archive CDX, the API: `https://web.archive.org/cdx/search/cdx?url=api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time&from=2025`
- Internet Archive CDX, the files: `https://web.archive.org/cdx/search/cdx?url=scottishwater.co.uk/-/media/ScottishWater/Document-Hub/Key-Publications/&matchType=prefix`
- sewagedata.co.uk code: https://github.com/Deveroonie/SewageData (`fetcher/main.go`, its commit history)
- Top of the Poops: https://top-of-the-poops.org/company/scottish-water
- The state release's assets: `gh api repos/ethanbuckley/swimsignal/releases/tags/state`
