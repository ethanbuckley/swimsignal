# 2026 spill event records: what is held, what was fetched, how they agree

Written 13 November 2026. A data record, not a test. Nothing here trains, fits or scores a model. Nothing is written
to `edm_events.parquet`, the EA event files of the main checkout, an issued forecast, a frozen file or an active
window. Source inventory ranks 10 and 11 (`docs/SOURCE-INVENTORY-2026-11.md`).

Files: `src/dipcast/ingest/company_events.py`, `scripts/import_company_events.py`,
`scripts/compare_live_durations.py`, a `--offsets` option in `scripts/compare_event_sources.py`, tests in
`tests/test_company_events.py` and `tests/test_compare_live_durations.py`, the manifest
[`EVENT-RECORDS-2026-11-manifest.json`](EVENT-RECORDS-2026-11-manifest.json) and the company-by-month table
[`EVENT-RECORDS-2026-11-coverage.csv`](EVENT-RECORDS-2026-11-coverage.csv). Raw files are not in git.

## Answer

- **The EA's 2026 file was already held, and is still the latest.** One copy of
  "2026 year to August Detailed EDM Start-Stop Data.zip" sat in another session's scratch folder (the one #639
  scored from). Its SHA-256 is `d0dbf32f…6c555a1a8f`, as #639 recorded. On 13 Nov the EA still listed only this
  2026 zip. Its server copy is 29,672,650 bytes, last modified 20 Oct 2026, so the held copy (downloaded 6 Nov) is
  the current file. It was not downloaded again. Imported, it holds **983,409 events at nine English companies,
  1 January to 31 August 2026** (Thames to 31 July).
- **The company layers add one month: September 2026, at Wessex and Yorkshire only.** Wessex Water's 2026 layer
  and Yorkshire Water's "Event Duration Monitoring History" run to 30 September. Every other layer stops inside the
  EA file's months. Anglian's last monthly layer is July 2026. Severn Trent's is 2025.
- **Three of the four companies' layers are the EA record.** Severn Trent 2025 is identical to the EA file.
  Wessex agrees with the EA on spill-days at shared overflows to 29 in 20,920 (2026) and adds 77 overflow ids the
  EA file lacks. Yorkshire joins the EA's events into fewer, longer ones but agrees on 98% of spill-days.
- **Anglian's monthly layers are not the same record as the EA file.** Only 30% of their 2026 starts match an EA
  start to the minute, and 281 of their ids are not in the EA file. They should not be used as labels until that
  is explained. Two of them also had day and month swapped; the importer repairs that (below).
- **Duration (scoping section 6):** where the live feed and a company record both hold a spill, the recorded length
  is the same to the minute at Thames (89 of 90) and Wessex (99 of 105, once Wessex's one-hour clock difference
  is allowed for). Yorkshire's history records the shared spills a median 9 minutes longer, ending later, and lacks
  most of the very short spills the feed shows. **Wessex's live feed reads one hour earlier than its own record and
  the EA file in September 2026.** This affects which UTC day a spill near midnight falls on (inferred; not
  measured here).

## 1. Inventory before any fetch

Checked 13 Nov 2026, 15:15-15:20 UTC, by searching the main checkout, `swimsignal-private`, every worktree and
every session scratch folder for start/stop zips and event parquets.

| Record | Where it was | Hash, size | Coverage |
|---|---|---|---|
| EA 2024 and 2025 start/stop files | main checkout `data/raw/ea_events/` (18 per-company files, 16 Oct) and `data/processed/ea_events_<company>.parquet` | parquet hashes in the fingerprint list below | 2024, 2025, nine companies |
| EA 2026 year to August zip | only in another session's scratch: `/private/tmp/claude-501/…amazing-jepsen-2d2156/…/scratchpad/root/data/raw/ea_events/` | `d0dbf32fb8622f98fe072466598d706590e5f8e667619cba7d0639c6555a1a8f`, 29,672,650 bytes | 1 Jan to 31 Aug 2026 (Thames to 31 Jul; ten files including Dŵr Cymru) |
| EA 2026 parquets | the same scratch folder and another session's (sonde-arrival); not in the main checkout | not used: rebuilt here from the zip | as the zip |
| Stream histories | main checkout `data/cache/edm/` and `stream_events_*.parquet` | unchanged | Northumbrian 2020-24, Wessex 2020-23 (2024 for ids), South West Jan 2025 to May 2026, UU 2023-25, Hafren Dyfrdwy 2025 |
| Thames alert stream | main checkout `api_events_thames_water.parquet` | `51910905ff23…` | Apr 2022 to 19 Oct 2026 |
| The four company layers of rank 11 | nowhere | | |

The `/tmp` scratch folder is not a durable store. The 2026 zip and the new raw reads were copied on 13 Nov to
`swimsignal-private/event-layers-2026/` (section 7), not into the main checkout's shared caches.

## 2. Licences, rechecked 13 November 2026

Read from each item's ArcGIS record (`licenseInfo`) and from the EA and data.gov.uk dataset pages, on the day.

| Source | Wording on 13 Nov 2026 |
|---|---|
| EA start/stop data (data.gov.uk) | "Licence information Open Government Licence"; updated 22 October 2026 |
| Anglian Water monthly layers, all nine | "NB for Publisher: Use https://creativecommons.org/chooser/ to create an appropriate sentence. The license selected is CC-BY 4.0" |
| Severn Trent Water EDM 2025 | "Licensed under CC BY 4.0" |
| Wessex Water EDM 2025 | "Wessex Water Event Duration Monitoring 2025 © 2025 by Wessex Water is licensed under CC BY 4.0" |
| Wessex Water EDM Monthly 2026 | "Wessex Water Event Duration Monitoring Monthly 2026 © 2026 by Wessex Water is licensed under CC BY 4.0" |
| Yorkshire Water EDM History | "Event Duration Monitoring History © 2026 by Yorkshire Water is licensed under CC BY 4.0" |

Anglian's text is a note to the publisher, not a finished licence sentence, but it names CC BY 4.0. The EA consents register was not used.

## 3. The fetch

**Found** by four ArcGIS catalogue searches on 13 Nov: the 13 layers in `LAYERS`. Wessex's "Monthly 2026 mk1"
item has no layers; its "view2" item, edited 29 Oct, is the one read.

**Sized before reading:** 703,861 rows at 2,000 a page is about 365 requests. At a 0.5 s pace and about 0.4 s a
response that is about 6 minutes. Cap: 450 requests. Stop rule: the first HTTP status other than 200 or ArcGIS error
body, with no retry.

**Ledger:** 371 requests, all HTTP 200, 161.8 MB, 15:23:44 to 15:29:02 UTC. Before that, 77 small requests to
find, count and date the layers and recheck the EA page (2.8 MB; one search response was not saved and is logged by
hand). The EA platform got 2 page reads, 1 signed-link request and 1 HEAD request; the zip was not downloaded. No
Open-Meteo call. Every read matched its layer's count with no repeated object id.

| Layer | Rows | Kept | Repairs and drops | First and last start (UTC) |
|---|---|---|---|---|
| Anglian Apr-Oct 2025 | 25,300 | 23,088 | 2,212 repeated rows | 1 Apr 2025 to 31 Oct 2025 |
| Anglian Nov 2025 | 10,830 | 10,830 | | 1 to 30 Nov 2025 |
| Anglian Dec 2025 | 12,118 | 12,118 | 6,157 starts and 6,146 stops with day and month swapped back | 1 to 31 Dec 2025 |
| Anglian Jan 2026 | 15,658 | 15,658 | | 1 to 31 Jan 2026 |
| Anglian Feb 2026 | 23,377 | 23,368 | 9 repeated | 1 to 28 Feb 2026 |
| Anglian Mar 2026 | 7,342 | 7,340 | 3,374 starts and 2,951 stops swapped back; 2 repeated | 1 to 31 Mar 2026 |
| Anglian Apr 2026 | 1,947 | 1,947 | | 1 to 30 Apr 2026 |
| Anglian May-Jun 2026 | 4,668 | 4,668 | | 1 May to 30 Jun 2026 |
| Anglian Jul 2026 | 1,023 | 1,023 | | 1 to 31 Jul 2026 |
| Severn Trent 2025 | 91,791 | 91,790 | 1 negative length | 1 Jan to 31 Dec 2025 |
| Wessex 2025 | 235,428 | 235,428 | | 1 Jan to 31 Dec 2025 |
| Wessex 2026 | 246,148 | 246,148 | | 1 Jan to 30 Sep 2026 |
| Yorkshire 2026 | 28,231 | 28,231 | | 1 Jan to 30 Sep 2026 |

**Anglian's two date faults.** Measured, not assumed:
1. *Day and month swapped.* The December 2025 layer's raw starts run from "12 January" to 31 December, and the
   March 2026 layer's from "3 January" to "3 December". Every raw March start falls on day 2, day 3, or day 13 and
   later: day-first text read month-first for days 1 to 12. The importer swaps back any start or stop outside the
   layer's stated months that a swap brings inside them (`swap_day_month`).
2. *GMT stored as UK local time.* Against the EA's 2026 file, before the repair, Anglian's April to September
   starts in the April-October 2025 and May-June 2026 layers sat 60 minutes before the EA's nearest start at the
   same overflow (6.6-6.7% of starts) far more often than at 0 minutes (1.6-1.7%). In winter months the peak was at
   0. The May-June 2026 layer's first start was "30 April
   23:00 UTC". So the importer reads Anglian's times back as UK wall-clock (`london_wall_as_utc`) before swapping.
   After both repairs every Anglian start lies inside its layer's months, and the summer peak is at 0 (2-17% of
   starts by layer) with almost none at 60 minutes (0.0-0.3%).

## 4. How each layer agrees with the EA file

`scripts/compare_event_sources.py A B --year Y --months … --offsets`, layer as A, EA as B. Spill-days are any UTC day
an event touches, the label the spill model trains on. "Start at 0" is the share of the layer's events at overflows
in both whose nearest EA start at that overflow is within a minute.

| Layer vs EA | Months | Events (layer / EA) | Overflow ids (both / layer only / EA only) | Spill-days at ids in both (shared / layer only / EA only) | Start at 0, at +60, at -60 |
|---|---|---|---|---|---|
| Wessex 2026 | Jan-Aug 2026 | 245,834 / 239,943 | 1,069 / 77 / 2 | 20,891 / 13 / 16 | 0.999, 0.000, 0.000 |
| Yorkshire 2026 | Jan-Aug 2026 | 27,153 / 111,686 | 1,737 / 6 / 8 | 30,825 / 529 / 145 | 0.957, 0.000, 0.000 |
| Anglian 2026 | Jan-Jul 2026 | 54,004 / 98,179 | 890 / 281 / 46 | 9,752 / 5,206 / 3,136 | 0.296, 0.001, 0.001 |
| Wessex 2025 | 2025 | 235,428 / 230,487 | 1,095 / 85 / 17 | 24,514 / 25 / 0 | 0.995, 0.000, 0.000 |
| Severn Trent 2025 | 2025 | 91,790 / 91,790 | 2,002 / 0 / 0 | 36,900 / 0 / 0 | 1.000, 0.000, 0.000 |
| Anglian 2025 | Apr-Dec 2025 | 46,036 / 59,459 | 1,064 / 153 / 44 | 10,060 / 6,483 / 1,196 | 0.228, 0.001, 0.001 |

The EA 2025 files are the main checkout's 17 Oct import, read only.

- **Wessex**: the same events as the EA file, plus 77 (2026) and 85 (2025) overflow ids the EA file does not
  carry, with 1,071 and 1,150 spill-days. Why the EA lacks them is not known. They are in the layer, so they are
  kept; a training use would need to decide.
- **Yorkshire**: a quarter as many events with the same spill-days, so the layer joins events the EA file lists
  separately [inferred from counts; the joining rule is not published on the item].
- **Anglian**: not the same record. The disagreement is in both directions and is not a clock offset. Which of the
  two is right is not settled here.
- **Severn Trent 2025**: adds nothing to the EA file.

## 5. 2026 coverage by month

Events by month of start (UTC). The full table, with overflow counts and the 2025 layers, is the coverage CSV. **New**
marks a month no other held record covers.

| Record | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep |
|---|---|---|---|---|---|---|---|---|---|
| EA, Anglian | 32,265 | 45,314 | 15,303 | 1,498 | 1,336 | 2,388 | 75 | 3,378 | |
| EA, Northumbrian | 22,051 | 32,788 | 8,303 | 1,349 | 6,052 | 4,458 | 1,365 | 5,585 | |
| EA, Severn Trent | 25,778 | 39,828 | 9,186 | 1,142 | 2,415 | 3,364 | 60 | 8,316 | |
| EA, South West | 72,208 | 76,786 | 30,593 | 7,545 | 4,777 | 6,699 | 145 | 3,527 | |
| EA, Southern | 28,065 | 37,811 | 5,466 | 2,141 | 1,448 | 2,287 | 13 | 922 | |
| EA, Thames | 5,171 | 5,515 | 1,188 | 180 | 81 | 646 | 66 | 231 | |
| EA, United Utilities | 8,995 | 14,213 | 15,094 | 3,802 | 4,691 | 7,551 | 595 | 9,731 | |
| EA, Wessex | 92,832 | 114,848 | 19,490 | 5,431 | 1,727 | 3,559 | 23 | 2,033 | |
| EA, Yorkshire | 32,650 | 51,214 | 10,204 | 1,296 | 5,381 | 3,119 | 139 | 7,683 | |
| Layer, Anglian | 15,658 | 23,368 | 7,340 | 1,947 | 2,068 | 2,600 | 1,023 | | |
| Layer, Wessex | 95,173 | 117,244 | 20,635 | 5,434 | 1,739 | 3,540 | 23 | 2,046 | **314 (new)** |
| Layer, Yorkshire | 6,662 | 7,436 | 3,104 | 804 | 2,741 | 2,170 | 52 | 4,184 | **1,078 (new)** |

September 2026 at Wessex: 314 events at 104 overflows. At Yorkshire: 1,078 events at 628 overflows. South West's
Stream layer (already held) covers January to May 2026 and adds no month past the EA file. The Thames alert stream
(already held) runs to 19 October.

## 6. Duration: the same spill in the live feed and in a record

Scoping section 6, "Duration: recording differences". Description only.

**Method.** `scripts/compare_live_durations.py`. A live spill is one (overflow, `latest_event_start`,
`latest_event_end`) the company's feed reported at a poll, from `live_history.parquet` (a state copy taken on
10 Nov, SHA-256 `3a4847bd1b69…`, read from another session's scratch, unchanged). Spills starting from 12 Sep (polling began
11 Sep) and ending before the record's end and before **18 Oct 2026**, the first target day of the earliest window
still open (lead calibration B, 18 Oct to 14 Nov). Rows ending later were dropped on reading. The file was loaded
whole and filtered at once; nothing after the cut-off was counted or looked at. Records: Wessex 2026 and Yorkshire
2026 layers (to 30 Sep) and the held Thames alert stream (to 17 Oct). The EA 2026 file ends before polling began,
so it covers no polled spill. Each live spill is matched to the record's events at the same overflow that overlap it
within a minute.

| | Wessex (as read) | Wessex (feed +60 min) | Yorkshire | Thames (alert stream) |
|---|---|---|---|---|
| Live spills | 155 | 155 | 519 | 105 |
| Same start and stop, within a minute | 0 | 99 | 10 | 89 |
| One record event, differs | 10 | 3 | 176 | 1 |
| Two or more record events | 5 | 3 | 0 | 0 |
| Record lacks it | 140 | 50 | 333 | 15 |
| Record events the feed lacks | 111 | 47 | 17 | 41 |
| Record minus live length, median (10th, 90th), minutes | 9 (-24, 262) | 0 (0, 0) | 8.2 (-5.0, 404) | 0 (0, 0) |
| Length within 1 minute / 15 minutes | 13% / 47% | 94% / 98% | 20% / 65% | 99% / 100% |

- **Wessex: same length, one hour apart.** As read, the record's nearest start at the same overflow is +60 minutes
  from the feed's for 72 of 155 spills and between +40 and +59 for 20 more; 12 lie elsewhere within two hours and
  51 have no record start within two hours. Shifted by 60 minutes, 99 of the 105 spills
  both hold match to the minute. The record agrees with the EA file to the minute (section 4), so it is the feed's
  `latest_event_start` and `latest_event_end` that differ from the EA's GMT [established for 12-30 Sep 2026, all in
  summer time]. Whether the feed is UK local time labelled as UTC, and whether it is so in winter, is not settled
  here. The 50 spills the record lacks after the shift are short (median 2 minutes).
- **Yorkshire: the history runs longer and drops short spills.** Where one record event overlaps the spill, it starts at
  much the same time (median -0.9 minutes) and stops later (median +4.7 minutes), so it is a median 9.1 minutes
  longer. The 333 it lacks have a median live length of 1.8 minutes. This fits the joined events of section 4.
- **Thames: the alert stream and the status feed are the same system** and agree almost exactly, as
  `docs/LIVE-VS-EDM-LABELS-2026-10.md` found against the EA file. The 15 the alert stream lacks have a median live
  length of 6 minutes.

What this does not show: how the EA's own file records these September spills (it ends 31 August), or any company
other than these three.

## 7. What the new months make possible, and what is still missing

- **Held now, to a known hash:** a second labelled year, January to August 2026 at nine companies (EA), with the
  importer and hashes. #639 and #666 already scored these months, so for the live-status candidates and combined-v1
  they are **seen** data: development evidence only.
- **New and unseen for combined-v1: September 2026 at Wessex and Yorkshire** [inferred from #666's record:
  combined-v1 was frozen at `4d66d7c7` on 10 Nov; its P and R were fitted on the live poll record 29 Sep to 23 Oct;
  its 2026 scoring used January to August only]. A rerun of #666's backtest script, unchanged, on 1-28 September at these two companies
  would be a small frozen-model backtest on unseen labels. It needs rain to 30 September and a reader in that script for
  the layer parquets. 29 and 30 September overlap the P and R fit window and should be left out. One month at two
  companies gives a wide interval; it is a check, not a release case. Not run here.
- **The unseen backtest the register names still waits for the EA:** September to December 2026 at all nine
  companies, from the EA's next 2026 file. On 13 Nov the EA lists only "2026 year to August" (modified 20 Oct). The
  importer finds a renamed or newer zip by itself (`scripts/import_ea_events.py --years 2026 --refresh`).
- **A duration refit or calibration check on 2026** can use the EA file now (seen data, development).
- **Not usable as labels yet:** Anglian's monthly layers (section 4).
- **Kept durable, 13 Nov 2026 17:13 UTC:** `/Users/ethanbuckley/Documents/GitHub/swimsignal-private/event-layers-2026/`
  (42 MB, a new folder; nothing there was overwritten). It holds `ea_events/` (the 2026 zip), `company_events/` (the
  13 raw layer reads and the fetch ledger), `discovery_ledger.jsonl` (the 77 finding and recheck requests) and a copy
  of the manifest. Every file was checked against this PR's manifest after copying: the zip's and all 13 raw reads'
  SHA-256 match, and the ledger has the stated 371 requests and bytes. Nothing was refetched. To use them from a
  checkout, copy `ea_events/*.zip` into `data/raw/ea_events/` and `company_events/*` into
  `data/cache/company_events/`; `scripts/import_company_events.py` then reads the cache and sends no request.

## 8. Reproduce

From a checkout with `data/processed/annual_returns.parquet` and `id_lookup.parquet`, in a scratch root:

    export DIPCAST_ROOT=<scratch>/root DIPCAST_STATE=<scratch>/root/state DIPCAST_CACHE=<scratch>/root/data/cache
    uv run python scripts/import_ea_events.py --years 2026            # uses a zip already in data/raw/ea_events/
    uv run python scripts/import_company_events.py --manifest docs/EVENT-RECORDS-2026-11-manifest.json \
        --coverage docs/EVENT-RECORDS-2026-11-coverage.csv           # about 371 requests if nothing is cached
    uv run python scripts/compare_event_sources.py <layer>.parquet <ea>.parquet --year 2026 --months 1-8 --offsets
    uv run python scripts/compare_live_durations.py <live_history>.parquet <record>.parquet --company "Wessex Water" \
        --record-before 2026-10-01 [--live-offset 60]

A layer can be republished or edited in place, so a later run can differ. The manifest's raw-read hashes say which
read this record used. Shared inputs (main checkout event parquets, annual returns, id lookup, Thames files, the EA
zip's source copy and the live history copy) had the same SHA-256 before and after the run.

## Credits

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed under the Open
Government Licence v3.0. Company layers, each licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/): Anglian Water Event Duration Monitoring (monthly layers, April 2025
to July 2026), Anglian Water, via Stream; Severn Trent Water Event Duration Monitoring 2025, Severn Trent Water, via
Stream; Wessex Water Event Duration Monitoring 2025 © 2025 by Wessex Water; Wessex Water Event Duration Monitoring
Monthly 2026 © 2026 by Wessex Water; Event Duration Monitoring History © 2026 by Yorkshire Water. Changes made: times
read as UTC, Anglian dates repaired as described, repeated rows dropped. Thames Water alert stream as in
`docs/EARLIER-SPILL-HISTORY-2026-10.md`.
