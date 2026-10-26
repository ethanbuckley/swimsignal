# Nine-company spill model v2: the data check

Written 25 October 2026, before the v2 statement (`docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md`). A record of checks,
not a test. No model was fitted, no forecast was made or read, and no rain was fetched. Counts of 2026 events and
spill-days were read; they are listed in the statement's "Seen before writing".

## Answer

**January to August 2026 is usable as a test set, all eight months and all nine English companies. No month is
excluded.**

- **Every company's 2026 file runs from 1 January to 31 August.** No company has a missing day or month.
- **July is tiny because July 2026 was very dry, not because data is missing.** ERA5-Land gives 3 to 5 mm for the
  month over Anglian, Severn Trent, South West, Thames and Wessex cells, against 43 to 92 mm in July 2024 and 2025.
  Radar gives 1 to 3 mm there, and 1 mm over Southern Water's cells. Spill-days fell with it.
- **The EA file matches the companies' own records.** South West Water's own 2025-26 history file and the EA file
  agree on 27,641 spill-days from January to May 2026; 50 are only in the company file and 112 only in the EA file.
  Thames's alert stream agrees with the EA file on 8,442 spill-days from January to August; 552 are only in the
  stream and 628 only in the EA file.
- **The live feeds show events the EA file lacks, mostly short ones.** Of 8,392 overflow events the live feeds
  reported as an overflow's latest event in January to August, the EA file has an event on the same local day for
  6,475 (77%). The ones it lacks have a median length of 4.5 minutes, and 75% of those with a stop time are under
  15 minutes. At South West Water, none of the 153 missing ones is in the company's own file either. *Inferred:*
  companies leave short or invalid activations out of what they report to the EA. This matters for scoring on live
  labels, not for a test on the EA file.
- **United Utilities' January is low, with no missing day.** It has 4,010 spill-days against 10,052 (2024) and 8,348
  (2025), with rain close to January 2025. Every day has spills, and they follow the rain day by day. Fewer
  overflows spill per storm. The cause is not known. United Utilities publishes no 2026 Stream layer to check against.
  It stays in, with a reported sensitivity without it.
- **A few rows have ids that are not overflows in the annual returns.** 706 events, 0.07% of 2026's 983,409:
  Severn Trent's `TBC` (144 events) and three other ids, four Wessex ids ending in `T`, and Yorkshire's `YWS02298`.
  None has a position, so the position rule drops them.

Rows must still pass a dead-monitor rule, because the file cannot tell a dry day from a dead monitor and there is no
2026 annual return yet. The statement takes option B's (`docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`). On the 19
reference days so far, 13,474 of 13,988 candidate overflows pass it (96%).

**Rain for 2026 is the only missing input.** 1,622 cells hold the nine companies' overflows in the 2025 return.
ERA5-Land 2026 is cached for 200 of them. The fetch is counted below.

## The files

Downloaded 25 October 2026 at 21:38 to 21:39 GMT through `scripts/import_ea_events.py --years 2024 2025 2026`, into a
scratch `DIPCAST_ROOT` (nothing written to the main checkout). Dataset c95ecc47-fa70-4a24-b8cc-098232987526 on the
EA's file platform. Open Government Licence v3.0, "© Environment Agency copyright and/or database right".

| Zip | Bytes | SHA-256 |
|---|---|---|
| 2024 Detailed EDM Start-Stop Data.zip | 32,364,631 | `733a6d02c50c6b865a1c144f76773baccd876a1e3917716d0992995babac7f13` |
| 2025 Detailed EDM Start-Stop Data.zip | 27,970,711 | `75b8a7fa25970812a6287c26e010200da4373b55383c98d2344dfa33188bc001` |
| 2026 year to August Detailed EDM Start-Stop Data.zip | 29,672,650 | `d0dbf32fb8622f98fe072466598d706590e5f8e667619cba7d0639c6555a1a8f` |

- The three are byte for byte the zips other sessions downloaded on 24 October. The EA has not revised them since.
- **2024 and 2025 are unchanged from the 17 October import** (PR #251's `-events.csv`): the same events, overflows,
  median lengths and gaps for every company and year. So the 20 October repackaging into yearly zips changed nothing
  in them.
- The 2026 zip holds one workbook per company, Dŵr Cymru's included.

## 2026 per company

From the importer's own summary (`ea_events_summary.csv`). Lengths and gaps are medians.

| Company | Events 2026 | Overflows | First start | Last start (local) | Event length | Gap to next start |
|---|---|---|---|---|---|---|
| Anglian | 101,557 | 1,036 | 1 Jan | 1 Sep 00:52 | 6 min | 4 min |
| Northumbrian | 81,951 | 1,301 | 1 Jan | 31 Aug | 4 min | 6 min |
| Severn Trent | 90,089 | 1,943 | 1 Jan | 31 Aug | 16 min | 21 min |
| South West | 202,280 | 1,122 | 1 Jan | 1 Sep 00:42 | 2 min | 4 min |
| Southern | 78,153 | 768 | 1 Jan | 31 Aug | 5 min | 8 min |
| Thames | 13,078 | 438 | 1 Jan | 31 Aug | 60 min | 75 min |
| United Utilities | 64,672 | 1,744 | 1 Jan | 31 Aug | 20 min | 102 min |
| Wessex | 239,943 | 1,071 | 1 Jan | 31 Aug | 2 min | 4 min |
| Yorkshire | 111,686 | 1,745 | 1 Jan | 31 Aug | 15 min | 15 min |

The file's times are UTC instants (headed "(GMT)"). Two companies' last events start just after local midnight on
1 September, which is 31 August in UTC.

**United Utilities' events changed shape in 2026.** Its median gap between one event's stop and the next start at the
same overflow is 102 minutes, against 26 to 28 in 2024 and 2025. Its January has 8,995 events against 27,207 (2025)
and 34,890 (2024), and only 47% of its gaps are under an hour, against 69-70%. *Inferred:* United Utilities may
record or merge activations differently in 2026. The label is "spilled that day", so merging alone changes event
counts much more than spill-days. It does not explain the January spill-day drop below.

## Spill-days per month

A spill-day is a UK local day an event touches (Europe/London, the day the 2027 scoring and PR #334 use). Ratio is
2026 against the mean of 2024 and 2025 in the same month. Full counts: `-monthly.csv`.

| Company | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Jan-Aug 2026 (2024, 2025) |
|---|---|---|---|---|---|---|---|---|---|
| Anglian | 0.97 | 1.06 | 0.62 | 0.13 | 0.26 | 0.85 | **0.02** | 2.41 | 14,553 (29,959, 9,187) |
| Northumbrian | 0.98 | 2.30 | 1.47 | 0.32 | 0.79 | 1.52 | **0.12** | 2.65 | 20,303 (27,895, 11,398) |
| Severn Trent | 1.15 | 1.85 | 0.93 | 0.22 | 0.59 | 1.64 | **0.01** | 6.61 | 31,512 (38,222, 14,853) |
| South West | 1.69 | 1.58 | 0.60 | 0.13 | 0.62 | 1.09 | **0.06** | 1.19 | 30,772 (37,312, 21,347) |
| Southern | 1.66 | 1.52 | 0.35 | 0.09 | 0.39 | 2.65 | **0.01** | 1.07 | 14,367 (19,338, 7,953) |
| Thames | 1.21 | 1.38 | 0.44 | 0.10 | 0.12 | 3.50 | **0.05** | 0.87 | 9,070 (15,087, 5,579) |
| United Utilities | **0.44** | 0.94 | 1.56 | 0.47 | 0.69 | 0.91 | **0.11** | 1.75 | 29,792 (52,284, 24,541) |
| Wessex | 1.36 | 1.53 | 0.43 | 0.16 | 0.45 | 3.10 | **0.02** | 1.63 | 20,917 (26,914, 11,614) |
| Yorkshire | 0.83 | 1.77 | 1.04 | 0.20 | 0.80 | 0.86 | **0.02** | 4.14 | 31,251 (46,229, 19,955) |

July 2026 spill-days: Southern 8, Wessex 20, Severn Trent 35, Thames 37, Anglian 44, Yorkshire 67, South West 101,
United Utilities 432, Northumbrian 446. April is the other low month (0.09 to 0.47).

## Rain in the same months

To tell a dry month from missing data. ERA5-Land (`-rain.csv`): the cached 2026 cells, mean monthly total over each
company's cells (200 cells in all; none for Northumbrian or Southern, 1 for South West). Radar: the Met Office
composite as kept by `scripts/fetch_met_office_radar.py`, on the 499 radar cells, hours with coverage of at least
0.9, given here as summary figures only (CC BY-SA 4.0; no radar series is published).

| July, mm | ERA5 2024 | ERA5 2025 | ERA5 2026 | Radar 2025 | Radar 2026 |
|---|---|---|---|---|---|
| Anglian | 87 | 70 | 3 | 45 | 2 |
| Northumbrian | | | | 80 | 29 |
| Severn Trent | 92 | 60 | 4 | 52 | 3 |
| South West | 72 | 43 | 5 | 29 | 1 |
| Southern | | | | 94 | 1 |
| Thames | 77 | 75 | 3 | 48 | 1 |
| United Utilities | 125 | 117 | 62 | 95 | 29 |
| Wessex | 85 | 48 | 5 | 38 | 2 |
| Yorkshire | 85 | 85 | 23 | 94 | 11 |

April 2026 was also dry in the south (ERA5 12 to 26 mm at Anglian, Severn Trent, South West, Thames, Wessex). The
months where spill-days rose most (Severn Trent August 6.6 times, Yorkshire August 4.1, Thames June 3.5) are months
where 2026 was wetter than both earlier years.

**July and April are kept.** Their low counts follow the rain. Dropping a month because its spill count is low would
choose the test set on its outcome. A forecast must also stay low in a drought; those rows test that.

## The live feeds, where they overlap

SwimSignal's polls start on 11 September 2026, after the EA file ends. So no day is in both. But each poll carries
the overflow's latest event (`latest_event_start`, `latest_event_end`). From the `state` release of 25 October
(`live_history.parquet`, SHA-256 `08a71197f5a8d5d4b511b5c71a695b5c7f7bbee5022408e966d0f0738b82064d`), every
distinct (overflow, latest event) with a start in January to August 2026 was looked up in the EA file. Ids match
across every company: the feeds use the annual returns' ids. This extends check 1 of
`docs/LIVE-VS-EDM-LABELS-2026-10.md` from Thames to all nine.

| Company | Feed events | EA event same local day | Share | At an overflow with no EA 2026 event |
|---|---|---|---|---|
| Anglian | 902 | 467 | 52% | 203 |
| Northumbrian | 973 | 834 | 86% | 76 |
| Severn Trent | 1,244 | 1,078 | 87% | 82 |
| South West | 908 | 548 | 60% | 128 |
| Southern | 570 | 495 | 87% | 62 |
| Thames | 404 | 333 | 82% | 23 |
| United Utilities | 765 | 486 | 64% | 128 |
| Wessex | 1,501 | 1,382 | 92% | 100 |
| Yorkshire | 1,125 | 852 | 76% | 97 |
| All | 8,392 | 6,475 | 77% | 899 |

By month, all nine together: January 75%, February 87%, March 76%, **April 18%**, May 54%, June 75%, **July 21%**,
August 85%. Per company and month: `-live-feed.csv`.

**What the missing ones are.** Feed events the EA file lacks: median 4.5 minutes, 75% under 15 minutes (of the 1,892
with a stop time). Feed events it holds: median 26 minutes, 37% under 15 minutes. By company, the missing ones are
shortest at Northumbrian and South West (median 2 minutes) and longest at Thames (30) and Southern (22).

**South West Water's own file decides it there.** SwimSignal holds South West Water's 2025-26 event layer to 31 May
2026 (`stream_events_south_west_water.parquet`). Of the 153 feed events from January to May with no EA event that
day, none is in the company's file either. Of the 216 the EA file holds, 210 are in the company's file. And on
spill-days the two files agree almost exactly (`-own-feeds.csv`):

| South West Water 2026 | Both | Company file only | EA only |
|---|---|---|---|
| January | 11,710 | 14 | 33 |
| February | 11,506 | 28 | 60 |
| March | 2,953 | 7 | 19 |
| April | 536 | 0 | 0 |
| May | 936 | 1 | 0 |

**Thames's alert stream** (`api_events_thames_water.parquet`, to 19 Oct 2026) against the EA file, spill-days:

| Thames 2026 | Both | Stream only | EA only |
|---|---|---|---|
| January to March | 7,833 | 299 | 460 |
| April to May | 166 | 88 | 15 |
| June | 354 | 81 | 75 |
| July | 6 | 47 | 31 |
| August | 83 | 37 | 47 |

The alert stream is a live feed too. Its events missing from the EA file have a median of 30 minutes in most months
and 10 minutes in August.

So where SwimSignal has a company's own history, the EA file matches it. The live feeds report extra short events,
mostly in dry months, when a short blip is more often an overflow's latest event. **For a test on the EA file this is
not a fault.** It is a difference between the two kinds of truth: the 2027 scoring and the live Accuracy page use
the polls, which see those blips. A model trained and tested on EA spill-days will meet them as surprises live. That
belongs in any live confirmation (option B's window L, a shadow), not here.

## United Utilities' January

| | Spill-days | Overflows with a spill | Radar, UU cells (188) | ERA5, UU cells (16) |
|---|---|---|---|---|
| January 2024 | 10,052 | 1,446 | | 194 mm |
| January 2025 | 8,348 | 1,693 | 137 mm | 134 mm |
| January 2026 | 4,010 | 948 | 119 mm | 132 mm |

Day by day, every day of January 2026 has between 9 and 546 United Utilities overflows spilling, and the busy days are
the rainy ones (6 January 8.7 mm on the radar: 546; 11 January 16.7 mm: 292; 27 January 14.4 mm: 516). In January
2025, days of similar rain had more (5 January 26.6 mm: 1,073; 27 January 12.3 mm: 965). So there is no gap in the
file. The 2026 record has fewer overflows spilling per storm.

Other signs do not point to dead monitors:
- Of the United Utilities overflows in the 2025 return, 76.8% have an event in January to August 2026, against 83.0%
  and 81.9% in the two earlier years. Lower, but not by half.
- Overflows with 10 or more spills in the previous return and no event at all in January to August: 34 in 2026 and 34
  in 2025.
- The live feeds' January events at United Utilities: 7 of 20 found in the EA file. Too few to weigh.

*Not established:* whether the drop is in United Utilities' network (its storm overflow work), in how it now records
events, or in what it sent to the EA. Nothing SwimSignal holds can separate these. The statement keeps January and
reports the result without United Utilities' January.

## Overflows with no event

The test rows need a rule for an overflow with no 2026 event. In 2024 and 2025 the 17 October test kept it only if
that year's annual return gave 0 spills. There is no 2026 return yet.

- Overflows in the 2025 return with a position and no event in January to August 2026: 3,022 of 14,180. The same
  count for 2025 (in the 2024 return, no event January to August 2025): 3,005 of 14,157.
- Of those, the ones that spilled 10 or more times in the previous return: 117 in 2026, against 340 in 2025.
- In 2025, of the 3,005 silent from January to August, the 2025 return gave 0 spills for the whole year to 2,186 and
  above 0 to 708. Many of the 708 will have spilled from September to December, so a January to August silence cannot
  be judged against a whole-year return.

So a 2026 rule must come from the monitors, not the returns. Option B already states one: the **dead-monitor check**
on the live polls over the reference period 5 October to 1 November 2026 (known status on at least 80% of polls, at
most 20% stale where a company stamps every record, a known poll on at least 20 of 28 days). On the 20 days from 5 to
24 October in the 25 October release (`live_coverage.parquet`, SHA-256
`4cded9b094308372ca016fea8f83ace45dc0c30d1a8a9020836666c880458f48`), with 20 × 20/28 = 14 days needed for the third
condition (the release's newest day, still being polled, left out):

| Company | In 2025 return, EDM ≥ 50% | In the feed | Pass |
|---|---|---|---|
| Anglian | 1,407 | 1,402 | 1,323 |
| Northumbrian | 1,544 | 1,530 | 1,486 |
| Severn Trent | 2,421 | 2,398 | 2,390 |
| South West | 1,353 | 1,336 | 1,288 |
| Southern | 941 | 896 | 892 |
| Thames | 578 | 568 | 535 |
| United Utilities | 2,265 | 2,250 | 2,222 |
| Wessex | 1,338 | 1,279 | 1,253 |
| Yorkshire | 2,141 | 2,135 | 2,085 |
| All | 13,988 | 13,794 | 13,474 |

The check counts polls, not discharges. The real count needs the full period, so it waits for a release made on or
after 2 November.

## Dŵr Cymru (the Welsh test set)

The 2026 zip's `Dwr Cymru Detailed Data 2026.xlsx`, read with `edm_events.read_ea_dcww_events`: 5,353 events at 112
overflows, 1 January to 31 August 2026 (the 17 October revision ended on 26 July). 99 of them are among the 122
Dŵr Cymru overflows in England in the 2025 return. By month: 1,782, 2,389, 506, 96, 132, 177, 7, 264.

## Rain for 2026: what is cached and what a fetch costs

**Cells.** The nine companies' overflows with a position in the 2025 return lie in 1,622 rain cells of 0.1°
(`rainfall.grid_cell`). The 2023 and 2024 returns' cells are 1,629 and 1,620; one cell is new in 2025.

**Cached** (main checkout, `data/cache/`):
- ERA5-Land 2024 and 2025: every cell of the 2023, 2024 and 2025 returns, and December 2023 or all of 2023 for every
  2023-return cell. Training needs no fetch.
- ERA5-Land 2026: 200 of the 1,622 cells, in `data/cache/rain/` (206 files in all), each complete from 1 January to
  31 August (5,832 hours, no gap). 161 end on 6 September and 45 on 6 October. By company: Anglian 32 of 330 cells,
  Northumbrian 0 of 121, Severn Trent 51 of 261, South West 1 of 168, Southern 0 of 147, Thames 61 of 156, United
  Utilities 16 of 188, Wessex 25 of 140, Yorkshire 21 of 181. (A cell can hold several companies' overflows.)
- Forecast leads 2026: the same 200 cells, to 13 September. Not needed for this test (reanalysis rain only).

**Cost**, by `rainfall.call_weight` (per location max(1, v/10, v/10 × days/14), one variable):

| Fetch | Cells | Days | Calls a cell | Calls |
|---|---|---|---|---|
| A. v2 only, 1 Jan to 31 Aug 2026, missing cells | 1,422 | 243 | 1.736 | 2,468 |
| B. v2 only, 1 Jan to the archive's latest day (today − 6), fetched on 27 Oct | 1,422 | 294 | 2.100 | 2,986 |
| **C. v2 and option B together, 1 Jan to 31 Oct 2026, every cell, on or after 6 Nov** | **1,622** | **304** | **2.171** | **3,522** |

- `rainfall.fetch_archive` always asks up to six days before today, so fetch A needs an end-date argument in
  `scripts/fetch_rain_nine.py`. Fetch C needs none.
- Option B needs 1 January to 31 October for every cell (its own "Data this depends on" guessed about 3,600 calls).
  The 200 cached cells end in September or early October, so fetch C refetches them too. One fetch then serves both
  tests, and every 2026 cell has the same fetch date.
- `training.load_rain` reads a tag from both cache folders, so a cell with 2026 in both would be read twice. Fetch C
  writes `data/cache/rain_nine/archive_<cell>_2026.parquet`, and the v2 harness reads 2026 from there only.
- All three fit inside Open-Meteo's free limits (5,000 an hour, 10,000 a day). Paced at 3,000 an hour, fetch C takes
  about 70 minutes.

## How to rerun

The scripts are in `scripts/nine_v2_data_check/`. They read the scratch root, a `state` release folder and the main
checkout, and write CSVs to an output folder:

```bash
DIPCAST_ROOT=<scratch> uv run python scripts/import_ea_events.py --years 2024 2025 2026
PYTHONPATH=src uv run python scripts/nine_v2_data_check/data_check.py <scratch> <state dir> <main checkout> <out>
```

Then, printing the follow-up tables:
- `follow_ups.py <scratch> <out> <main checkout>`: South West Water's own file, the feed events' lengths, Thames's
  alert stream;
- `united_utilities.py <scratch> <out> <main checkout>`: the reporting shares, United Utilities' event shape and
  January day by day;
- `no_event_rule.py <scratch> <state dir> <main checkout>`: overflows with no event, ids in no return, and the
  dead-monitor preview. The run of 25 October peaked at 1.3 GB and made no Open-Meteo call.

Tables beside this file:
- `-monthly.csv`: events, overflows with an event, median event length and spill-days, per company, year and month;
- `-live-feed.csv`: the feed check per company and month;
- `-own-feeds.csv`: Thames's alert stream and South West Water's own file against the EA file, per month;
- `-rain.csv`: the ERA5-Land monthly totals above (radar figures are in this file's text only).
