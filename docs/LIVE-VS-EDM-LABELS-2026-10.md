# Live spill labels against the EA's start/stop files

Written 17 October 2026. A record of checks, not a test: nothing here changes a model, a map or a score.
The question came from two results that disagree in direction:
- On 2025, scored against the EA's Event Duration Monitoring (EDM) start/stop files, the production model and the
  map in use forecast too **low** at all nine English companies (mean 0.050 against 0.064 observed;
  `docs/NINE-COMPANY-MODEL-TEST-2026-10.md`, PR #251).
- On the live scored rows, 29 Sep to 16 Oct 2026, the same system forecasts too **high** (0.039 against 0.030),
  at six of nine companies (`docs/LEAD-CALIBRATION-B-TEST-2026-10.md`, PR #252, step 3).

One explanation offered was that the live feeds record fewer spill-days than EDM for the same overflows and days.

## Answer

**The direct check cannot be done yet.** No day is in both sources:
- The EA's "Thames Water Detailed Data 2026.xlsx" runs from 1 January to 31 July 2026. Its sheets are "January -
  April", "May", "June" and "July".
- SwimSignal's live history starts on 11 September 2026. The scored rows start on 29 September.
- Welsh Water cannot be compared at all. SwimSignal polls no Dŵr Cymru feed (no such company in
  `live_history.parquet`), and the EA's Welsh Water 2026 file ends on 26 July.

**Three indirect checks say the labels are not the main cause.**
1. **When Thames's live feed shows an event, it matches the EA file.** At 281 of 342 overflows, the feed's latest
   event matches an EA event to the minute, start and stop. Where the two disagree, the feed mostly shows an event
   the EA file lacks (56 overflows). The EA file shows events the feed missed at only 5.
2. **The polling method loses about 1% of spill-days.** The live labelling method was replayed on the 2025 EDM
   events, using the real 2026 poll times. It found 99.7% of EDM spill-days over the year, and 98.9% in the
   29 Sep to 16 Oct window. It added none.
3. **The same calendar window over-forecast in 2025 too, against EDM truth.** On the same overflows and days of the
   year, 29 Sep to 16 Oct 2025, the forecast mean was 0.0398 and the observed 0.0374. The whole of 2025 on those
   overflows was the other way: 0.0566 against 0.0738. Thames over-forecast in the 2025 window by twelve times
   (0.0192 against 0.0016), which is more than live in 2026 (0.0225 against 0.0042).

So most of the disagreement in direction comes from comparing a whole year with an 18-day autumn window. A part is
left over (below, "What is not explained").

## The sources

| | Thames EA 2026 file | Live history (state release, 17 Oct 05:22 UTC) | Published live scores |
|---|---|---|---|
| Days | 1 Jan to 31 Jul 2026 | polls from 11 Sep 2026 | target days 29 Sep to 16 Oct 2026 |
| Overflows | 435 with an event | 573 Thames, 14,206 in all | 1,145, of which 194 Thames |
| Rows | 12,847 events | 53,278 (1,006 Thames) | 79,084 scored forecasts, 16,114 overflow-days, 472 spill-days |

- The EA file was downloaded on 17 Oct 2026 through the signed-link route in `scripts/import_ea_events.py`
  (386,493 bytes; dataset e9677ac1-fd32-4ceb-88a0-2735be5f27c7). It was read with `edm_events.read_ea_events` from
  PR #251 (branch `claude/nine-company-model`).
- Ids match: 434 of the EA file's 435 ids are in the live feed. Both use the `TWL00nnn` form.
- The live history keeps one row per (overflow, status, status start), the last seen (`ingest.live.save_live`).
  Its oldest row for an overflow therefore holds the latest event the feed showed when polling began.

## Check 1: Thames's live latest event against the EA file

For each Thames overflow, the latest event the feed showed at its first poll (11 Sep 2026 or later) was compared with
the EA file. That event is the most recent the feed had. So:
- if it falls between January and July, the EA file should hold the same event and no later one before August;
- if it is from before 2026, the EA file should hold no 2026 event at that overflow.

| Live latest event at first sight | Overflows | With EA 2026 events | What the EA file shows |
|---|---|---|---|
| January to July 2026 | 342 | 322 | 281 exact matches (start and stop to the minute); 1 inside a longer EA event; 36 later than the EA file's last event; 20 at overflows with no EA 2026 event. At 4 of these 342, the EA file has later events the feed missed (below) |
| Before 2026 | 78 | 1 | 1 overflow (TWL00787) has 2 EA events on 23 June, 1 spill-day, that the feed did not show |
| None (no event times in the feed) | 57 | 20 | 756 EA events, about 470 spill-days. 85 of these overflows' 133 history rows are offline (status -1) |
| August 2026 or later | 96 | 91 | nothing to check: the EA file stops at 31 July |

By month of the live event (the January to July row):

| Month | Exact | Feed has an event the EA file lacks | EA has later events the feed missed | Other | All |
|---|---|---|---|---|---|
| Jan | 16 | 4 | 0 | 0 | 20 |
| Feb | 73 | 3 | 0 | 1 | 77 |
| Mar | 48 | 5 | 2 | 0 | 55 |
| Apr | 3 | 10 | 0 | 0 | 13 |
| May | 4 | 11 | 1 | 0 | 16 |
| Jun | 135 | 12 | 0 | 1 | 148 |
| Jul | 2 | 11 | 0 | 0 | 13 |
| All | 281 | 56 | 3 | 2 | 342 |

"Other" is TWL00806, whose live event (15 Feb, 11:15-14:45) spans the EA's last one (14:26-14:34), and TWL00684, inside an EA event.
TWL00411 is counted as exact: its live event (10 Feb) matches an EA event, but 2 later EA events, 3 spill-days,
were not shown by the feed. With the 3 in the "EA has later events" column, 4 overflows in this row have missed
events: 23 events, 14 spill-days. With TWL00787, 5 overflows have missed events: 25 events, 15 spill-days. At 4 of
the 5, the last missed event was on 23 June.

**Verified:**
- Where the feed reports an event, it is the EA's event in 82% of cases, to the minute.
- Where they differ, the feed shows more events, not fewer: 56 overflows against 5.
- Most of the feed-only events are short (median 30 minutes) and fall in April, May and July. The EA's sheets for
  those months are thin: 180, 81 and 66 events, against 5,171 in January. *Inferred, not checked:* the EA's 2026
  file may still be incomplete for those months.

**The one way the feed can hide spills:** an overflow whose feed shows no event times. If its status is known (0),
its days can be scored as dry. 4 Thames overflows of this kind have EA events in 2026 and are scored live:
64 overflow-days, all 0. That is at most 64 of Thames's 2,909 scored overflow-days. It cannot explain Thames's live
gap (about 65 spill-days forecast, 12 observed).

**Not verified:** that the feed behaved the same way in September and October 2026. This check covers events up to
31 July.

## Check 2: the live labelling method replayed on EDM 2025

This asks: if every feed reported exactly the EDM events, how many spill-days would SwimSignal's method record?
- **Poll times:** the real ones, from `poll_log.parquet`, 28 Sep to 17 Oct 2026, moved back 365 days. That is about
  13 polls a day; the nine feeds are polled in the same runs.
- **At each poll,** each overflow shows its latest EDM event that has started. If the event has not ended, the
  overflow shows "discharging" with no end time.
- **The history** keeps rows as `save_live` does.
- **Labels** come from `forecast_log.observed_spill_days`.
- **Covered days** are those the poll times alone would pass, under the rules of 6 polls, an 8 h gap and the next
  day. Feed outages are not modelled.
- **For the whole year,** the 18-day poll pattern was repeated from 1 January 2025.

| Company | EDM spill-days, window | Found, window | EDM spill-days, 2025 covered days | Found, 2025 |
|---|---|---|---|---|
| Anglian | 196 | 100.0% | 15,372 | 99.5% |
| Northumbrian | 874 | 98.1% | 24,596 | 99.5% |
| Severn Trent | 586 | 99.7% | 32,198 | 99.9% |
| South West | 375 | 98.1% | 40,620 | 99.6% |
| Southern | 218 | 98.6% | 14,084 | 99.8% |
| Thames | 51 | 100.0% | 7,827 | 99.9% |
| United Utilities | 2,764 | 98.6% | 54,267 | 99.8% |
| Wessex | 251 | 99.6% | 21,262 | 99.6% |
| Yorkshire | 1,724 | 99.5% | 45,997 | 99.7% |
| **All nine** | 7,039 | **98.9%** | 256,223 | **99.7%** |

The method added no spill-day that EDM lacks. It misses a day only when two events fall between polls on different
days, so the later one hides the earlier one.

**Verified:**
- The method itself loses 0.3% to 1.1% of spill-days.
- The live forecast is 33% above the observed rate (0.0393 against 0.0295), about thirty times that loss.

**Assumed:** that the feeds report the companies' EDM events. Check 1 supports this for Thames only. Day-level
agreement between United Utilities' EA file and its Stream data (PR #251) concerns Stream's annual data, not the
live feed.

## Check 3: the same window in 2025, against EDM

This is the 2025 replay of PR #251 and #252:
- the production model, `spill_model.pkl`;
- the map in use, `lead_calibration.json` on main;
- leads 0 to 4;
- EDM labels;
- the same rows and code path as `scripts/verify_leads.py` at `1a81ca2`.

The rows were cut to the target days 29 Sep to 16 Oct 2025, and to the live-scored overflows. 714 of the 1,145
live-scored overflows are in the replay's lead cells.

| Company | Rows 2025 | Observed 2025 (EDM) | Forecast 2025 | Rows 2026 | Observed 2026 (live) | Forecast 2026 |
|---|---|---|---|---|---|---|
| Anglian | 7,200 | 0.0069 | 0.0107 | 10,599 | 0.0215 | 0.0134 |
| Northumbrian | 270 | 0.0000 | 0.0329 | 908 | 0.0529 | 0.0224 |
| Severn Trent | 9,630 | 0.0104 | 0.0200 | 8,225 | 0.0242 | 0.0304 |
| South West | 180 | 0.0000 | 0.0039 | 1,330 | 0.0474 | 0.0620 |
| Southern | 1,350 | 0.0296 | 0.0163 | 5,130 | 0.0099 | 0.0373 |
| Thames | 12,330 | 0.0016 | 0.0192 | 14,238 | 0.0042 | 0.0225 |
| United Utilities | 12,150 | 0.1086 | 0.1113 | 9,740 | 0.1137 | 0.1331 |
| Wessex | 10,710 | 0.0131 | 0.0222 | 19,464 | 0.0061 | 0.0241 |
| Yorkshire | 10,440 | 0.0704 | 0.0412 | 9,370 | 0.0416 | 0.0356 |
| **All nine** | 64,260 | **0.0374** | **0.0398** | 79,084 | **0.0295** | **0.0393** |

- The production model saw United Utilities' 2025. That row says where its forecasts go, not whether they are right.
- Northumbrian and South West have few 2025 rows, so their rates mean little.

The same overflows across the whole of 2025: forecast 0.0566 against 0.0738 observed. By month, all nine companies
(all replay rows), observed then forecast:

| | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Observed | 0.120 | 0.044 | 0.016 | 0.010 | 0.021 | 0.050 | 0.045 | 0.018 | 0.105 | 0.061 | 0.146 | 0.136 |
| Forecast | 0.080 | 0.029 | 0.009 | 0.009 | 0.020 | 0.046 | 0.035 | 0.020 | 0.079 | 0.056 | 0.117 | 0.105 |

**Verified:**
- 2025's under-forecast is mostly in the wet months: January, September, November and December.
- In the 18 days matching the live window, on the live overflows, 2025 was slightly over-forecast (ratio 1.06).
- Thames, Wessex, Severn Trent and Anglian were over-forecast there against EDM truth, as Thames, Wessex and Severn
  Trent are live.

### What is not explained

The live window is still more over-forecast than its 2025 twin: ratio 1.33 against 1.06. The difference is in the
upper bins.

| Bin of the calibrated forecast | 0.0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 |
|---|---|---|---|---|---|---|---|---|---|
| 2025 window, observed (EDM) | 0.007 | 0.140 | 0.232 | 0.345 | 0.480 | 0.597 | 0.697 | 0.826 | 0.930 |
| 2026 live, observed | 0.016 | 0.084 | 0.112 | 0.210 | 0.268 | 0.437 | 0.408 | 0.452 | 0.541 |
| Mean forecast in the bin (2026) | 0.015 | 0.141 | 0.242 | 0.345 | 0.446 | 0.547 | 0.651 | 0.751 | 0.825 |

- **The labels are the same at every lead, and the over-forecast is already there at lead 0.** On the 15,514
  overflow-days scored at all five leads, the observed rate is 0.0294. The mean forecast is 0.0365 at lead 0,
  then 0.0413, 0.0406, 0.0424 and 0.0359.
- **It is concentrated in a few days.** Of the 16 scored days:
  - 7 Oct alone holds 161 of the 775 excess forecast spill-days;
  - 16 Oct holds 173;
  - 30 Sep holds 132;
  - 12 Oct holds 130.
- There are 472 live spill-days in all. Neighbouring overflows share the same rain, so the rows are far from
  independent.

*Inferred, not checked:* candidates for the residual.
- Wet days that forecast rain made wetter than they were. The live system runs on Open-Meteo's Met Office feed,
  while the 2025 replay uses Open-Meteo's archived lead forecasts, which may come from a different model.
- A real difference between this autumn and last.
- Live labels missing events at companies other than Thames, which check 1 cannot see.

The first two would show in a comparison of the forecast rain for each scored day against ERA5-Land or gauge rain
for that day.

## What this means

**For the lead calibration (PR #252, option B).**
- The secondary check (B worse on 29 Sep to 16 Oct) is not evidence that EDM truth and live truth disagree. A map
  fitted on the whole of 2025 is pulled up by wet months. An 18-day autumn window over-forecast in 2025 too, under
  EDM truth.
- The pre-stated decision window, 18 Oct to 14 Nov, falls in a season that 2025 under-forecast (November 2025:
  0.117 against 0.146). So the secondary check says less about how B will do there than its numbers suggest.
  *Inferred.*
- Nothing in PR #252's statement changes. The live four weeks still decide.
- The 2025 by-month table suggests the error of the map in use depends on the season. Any fix of that kind needs
  its own pre-stated test. *Inferred.*

**For scoring.**
- No evidence was found that the live labels under-count spill-days:
  - the method loses about 1%;
  - Thames's feed matches the EA's events where both exist, and where they differ it shows more.
- The live score can be read as a score against what the overflows did, to within a few per cent. This holds for
  the Thames evidence; the other eight companies' feeds are assumed.
- One known gap: overflows whose feed gives a known status but no event times can be scored dry while spilling. At
  Thames that is 4 overflows and 64 overflow-days. A follow-up could stop scoring such overflows. That would be a
  scoring-rule change, so it needs its own note before it is made.

**To settle the question directly.** Repeat check 1 at day level when the EA's Thames 2026 file covers 29 Sep to
16 Oct. The file gains a sheet a month, and July was in it by 17 Oct, so October may be there by mid-January 2027.
*Inferred from the sheet names, not from a published schedule.* The same comparison works for any other company
whose 2026 file the EA publishes.

## Reproducing

The scripts are kept outside the repository with this session's notes (the side-session notes folder of
local_19f309d4-81a1-4071-ae6c-27a87a767948, `live-vs-edm-labels/`):
- `check_a.py` to `check_a4.py`: check 1;
- `check_b.py`: check 2, `window` or `year`;
- `replay_window2.py` and `window_compare.py`: check 3, run with the `claude/nine-company-model` code and
  `DIPCAST_CACHE` pointing at the main checkout's `data/cache`;
- `by_day.py` and `by_lead.py`: the residual.

Inputs:
- the state release as of 17 Oct 2026 05:22 UTC (`live_history`, `live_coverage`, `poll_log`);
- `verification_live.csv` as published at 13:41 BST on 17 Oct (6,555,677 bytes, the same size as PR #252 read);
- the EA files in `data/raw/ea_events/` and the Thames 2026 workbook above.

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed under the Open
Government Licence v3.0.
